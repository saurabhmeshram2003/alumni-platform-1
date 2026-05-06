"""
routes/auth.py
--------------
Authentication routes: login, register (→ pending_users), OTP verify
(pending_users → users), resend OTP, logout.

Flow:
  Register  →  save to pending_users  →  send OTP  →  /verify-otp
  Verify OK →  promote to users       →  /login
  Login     →  checks users only (unverified never land there)
"""

import re
import os
from datetime import datetime

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, PendingUser
from utils.otp import generate_otp, get_otp_expiry, send_otp_email

auth_bp = Blueprint('auth', __name__)

# Seconds a user must wait before requesting another OTP
OTP_RESEND_COOLDOWN = 30


# ─────────────────────────────────────────────────────────────────
# LOGIN  (unchanged logic — users collection only)
# ─────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        try:
            user_data = User.find_by_email(email)

            if user_data and check_password_hash(user_data['password'], password):

                # Legacy / admin accounts have no 'verified' key → default True
                if not user_data.get('verified', True):
                    session['otp_email'] = email
                    flash('Please verify your email address before logging in. '
                          'Check your inbox for the OTP.', 'warning')
                    return redirect(url_for('auth.verify_otp'))

                from models import UserMixin
                user_obj = UserMixin(user_data)

                if not user_obj.is_approved:
                    flash('Your account is pending admin approval.', 'warning')
                    return redirect(url_for('auth.login'))

                login_user(user_obj, remember=remember)
                flash('Logged in successfully.', 'success')

                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard.index'))

            else:
                # Check if they exist in pending_users and redirect them to verify
                pending = PendingUser.find_by_email(email)
                if pending:
                    session['otp_email'] = email
                    flash('Your email is not verified yet. Please enter your OTP.', 'warning')
                    return redirect(url_for('auth.verify_otp'))

                flash('Please check your login details and try again.', 'danger')

        except Exception as exc:
            current_app.logger.error(f"[Login] Error: {exc}")
            flash('A server error occurred. Please try again in a moment.', 'danger')

    return render_template('login.html')


# ─────────────────────────────────────────────────────────────────
# REGISTER  →  saves to pending_users (NOT users)
# ─────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name             = request.form.get('name', '').strip()
        email            = request.form.get('email', '').strip()
        password         = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role             = request.form.get('role', '')
        graduation_year  = request.form.get('graduation_year', '')
        department       = request.form.get('department', '')
        company          = request.form.get('company', '').strip() if role == 'alumni' else None

        # ── Validations (all original logic preserved) ─────────────────

        # 1. Name
        if not re.match(r'^[a-zA-Z\s]{3,}$', name):
            flash('Invalid name. Only alphabets and spaces, min 3 characters allowed.', 'danger')
            return redirect(url_for('auth.register'))

        # 2. Email format
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Invalid email format.', 'danger')
            return redirect(url_for('auth.register'))

        # 2b. Email must start with a letter
        if not re.match(r'^[a-zA-Z]', email):
            flash('Email must start with a letter.', 'danger')
            return redirect(url_for('auth.register'))

        # 3. Role-based email domain check
        if role == 'student':
            if not email.endswith('@mgmcen.ac.in'):
                flash('Students must use their college email (@mgmcen.ac.in).', 'danger')
                return redirect(url_for('auth.register'))
        elif role == 'alumni':
            pass  # Alumni may use any email
        else:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('auth.register'))

        # 4. Password strength
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$', password):
            flash('Password must be at least 8 chars, 1 uppercase, 1 lowercase, 1 number, and 1 special character.', 'danger')
            return redirect(url_for('auth.register'))

        # 5. Password confirmation
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))

        # 6. Role
        if role not in ['student', 'alumni']:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('auth.register'))

        # 7. Department
        valid_departments = [
            'CSE', 'IT', 'Mechanical', 'Civil',
            'AI DS', 'ENTC', 'Computer Science', 'Information Technology'
        ]
        if department not in valid_departments:
            flash('Please select a valid department.', 'danger')
            return redirect(url_for('auth.register'))

        # 8. Graduation year
        try:
            year_int = int(graduation_year)
            if not (1980 <= year_int <= 2035):
                raise ValueError
        except (ValueError, TypeError):
            flash('Graduation year must be between 1980 and 2035.', 'danger')
            return redirect(url_for('auth.register'))

        # 9. Company for alumni
        if role == 'alumni' and not company:
            flash('Company is required for Alumni.', 'danger')
            return redirect(url_for('auth.register'))

        # 10. Skills
        skills_raw = request.form.get('skills', '')
        skills = [s.strip() for s in skills_raw.split(',')] if skills_raw else []

        # 11. LinkedIn (optional)
        linkedin = request.form.get('linkedin', '').strip() or None

        # 12–17: All DB operations wrapped in try/except
        try:
            # 12. Email uniqueness — check BOTH collections
            if User.find_by_email(email):
                flash('That email address is already registered. Please log in instead.', 'warning')
                return redirect(url_for('auth.login'))

            # 12a. Check pending_users — prevent duplicate in-flight registrations
            if PendingUser.find_by_email(email):
                session['otp_email'] = email
                flash(
                    'A registration with that email is already in progress. '
                    'Please enter the OTP sent to your inbox, or request a new one.',
                    'warning'
                )
                return redirect(url_for('auth.verify_otp'))

            # 12.5 Alumni proof document upload (existing logic preserved)
            proof_filename = None
            proof_type     = None
            if role == 'alumni':
                proof_type = request.form.get('proof_type')
                if not proof_type:
                    flash('Proof type is required for Alumni.', 'danger')
                    return redirect(url_for('auth.register'))

                if 'resume' not in request.files:
                    flash('Proof document is required for Alumni.', 'danger')
                    return redirect(url_for('auth.register'))

                proof_file = request.files['resume']
                if proof_file.filename == '':
                    flash('No proof document selected.', 'danger')
                    return redirect(url_for('auth.register'))

                from werkzeug.utils import secure_filename
                import os
                import time

                proofs_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'proofs')
                os.makedirs(proofs_dir, exist_ok=True)

                sec_filename   = secure_filename(proof_file.filename)
                _, ext         = os.path.splitext(sec_filename)
                proof_filename = f"proof_{int(time.time())}{ext}"
                proof_file.save(os.path.join(proofs_dir, proof_filename))

            # 13. Hash password once here (PendingUser stores it pre-hashed)
            hashed_password = generate_password_hash(password)

            # 14. Generate OTP
            otp_code   = generate_otp()
            otp_expiry = get_otp_expiry(minutes=5)

            # 15. Save to pending_users  (NOT users collection)
            PendingUser.create(
                name, email, hashed_password, role, year_int, department,
                company, skills, linkedin,
                proof_type=proof_type, proof_file=proof_filename,
                otp=otp_code, otp_expiry=otp_expiry,
            )

            # 16. Send OTP email
            success = send_otp_email(email, otp_code, name)
            if not success:
                PendingUser.delete(email)
                flash(
                    'We could not send the verification email. '
                    'Please check your email address and try again.',
                    'danger'
                )
                return redirect(url_for('auth.register'))

            flash(
                f'Registration successful! A 6-digit OTP has been sent to '
                f'<strong>{email}</strong>. Please verify your email to continue.',
                'success'
            )
            session['otp_email'] = email
            return redirect(url_for('auth.verify_otp'))

        except Exception as exc:
            current_app.logger.error(f"[Register] DB error: {exc}")
            flash('A database error occurred. Please try again in a moment.', 'danger')
            return redirect(url_for('auth.register'))

    return render_template('register.html')


# ─────────────────────────────────────────────────────────────────
# VERIFY OTP  →  promotes pending_user → users on success
# ─────────────────────────────────────────────────────────────────
@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    email = session.get('otp_email', '').strip()

    if not email:
        flash('Session expired. Please register again or log in.', 'danger')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()
        email       = request.form.get('email', email).strip()

        if not entered_otp or not entered_otp.isdigit() or len(entered_otp) != 6:
            flash('Please enter a valid 6-digit OTP.', 'danger')
            return render_template('verify_otp.html', email=email)

        # ── Look in pending_users only ────────────────────────────────
        pending = PendingUser.find_by_email(email)
        if not pending:
            # Maybe already promoted (double-submit)
            if User.find_by_email(email):
                flash('Your email is already verified. Please login.', 'info')
                session.pop('otp_email', None)
                return redirect(url_for('auth.login'))
            flash('Registration record not found. Please register again.', 'danger')
            return redirect(url_for('auth.register'))

        stored_otp = pending.get('otp')
        otp_expiry = pending.get('otp_expiry')

        # ── Expiry check ─────────────────────────────────────────────
        if not otp_expiry or datetime.utcnow() > otp_expiry:
            flash('OTP expired. Please request a new one.', 'danger')
            return render_template('verify_otp.html', email=email)

        # ── OTP match ────────────────────────────────────────────────
        if entered_otp != stored_otp:
            flash('Invalid OTP. Please try again.', 'danger')
            return render_template('verify_otp.html', email=email)

        # ── SUCCESS — promote pending_user → users ────────────────────
        PendingUser.promote_to_users(email)
        session.pop('otp_email', None)

        flash('🎉 Email verified! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('verify_otp.html', email=email)


# ─────────────────────────────────────────────────────────────────
# RESEND OTP  →  updates pending_users record
# ─────────────────────────────────────────────────────────────────
@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    email = (request.form.get('email', '') or session.get('otp_email', '')).strip()

    if not email:
        flash('Session expired. Please register again.', 'danger')
        return redirect(url_for('auth.register'))

    pending = PendingUser.find_by_email(email)
    if not pending:
        if User.find_by_email(email):
            flash('Email is already verified. Please login.', 'info')
            session.pop('otp_email', None)
            return redirect(url_for('auth.login'))
        flash('Registration record not found. Please register again.', 'danger')
        return redirect(url_for('auth.register'))

    # ── Cooldown enforcement ──────────────────────────────────────────
    last_resend = pending.get('otp_resend_at')
    if last_resend:
        elapsed = (datetime.utcnow() - last_resend).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN:
            remaining = int(OTP_RESEND_COOLDOWN - elapsed)
            flash(f'Please wait {remaining} second(s) before requesting a new OTP.', 'warning')
            session['otp_email'] = email
            return redirect(url_for('auth.verify_otp'))

    # ── Generate + persist new OTP in pending_users ───────────────────
    new_otp    = generate_otp()
    new_expiry = get_otp_expiry(minutes=5)
    PendingUser.update_otp(email, new_otp, new_expiry)

    # ── Send email — production: surface real errors to user ────────
    success = send_otp_email(email, new_otp, pending.get('name', 'User'))
    if success:
        flash('A new OTP has been sent to your email address.', 'success')
    else:
        flash(
            'Could not send the OTP email. Please check your connection and try again.',
            'danger'
        )

    session['otp_email'] = email
    return redirect(url_for('auth.verify_otp'))


# ─────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))