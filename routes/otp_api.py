"""
routes/otp_api.py
-----------------
REST API Blueprint for OTP-based email verification using Gmail SMTP.

Routes:
    POST /send-otp    – Generate OTP, store in MongoDB, send via Gmail.
    POST /verify-otp  – Validate OTP, check expiry, delete on success.

MongoDB collection: otp_verifications
Schema:
    {
        email:      str,
        otp:        str,       # 6-digit numeric string
        created_at: datetime,
        expires_at: datetime   # created_at + 5 minutes
    }
"""

import re
import random
import string
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from extensions import mongo, csrf
from utils.email_service import send_otp_email

otp_api_bp = Blueprint("otp_api", __name__)

# Exempt from CSRF — these are JSON API routes, not HTML form submissions
csrf.exempt(otp_api_bp)

# ── Helpers ───────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def _generate_otp(length: int = 6) -> str:
    """Return a secure random 6-digit numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def _otp_col():
    """Return the otp_verifications collection."""
    return mongo.db.otp_verifications


# ── POST /send-otp ────────────────────────────────────────────────────────────

@otp_api_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Generate a 6-digit OTP, store it in MongoDB, and send via Gmail SMTP.

    Request JSON:  { "email": "user@example.com" }
    Success:       { "success": true, "message": "OTP sent successfully" }
    """
    # 1. Parse + validate
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    # 2. Generate OTP
    otp        = _generate_otp()
    now        = datetime.utcnow()
    expires_at = now + timedelta(minutes=5)

    print(f"🔥 OTP GENERATED for {email}: {otp}")

    # 3. Save / overwrite in MongoDB (upsert)
    try:
        _otp_col().update_one(
            {"email": email},
            {"$set": {
                "email":      email,
                "otp":        otp,
                "created_at": now,
                "expires_at": expires_at,
            }},
            upsert=True,
        )
        current_app.logger.info(f"[OTP] Saved OTP record for {email}")
    except Exception as exc:
        print(f"❌ MONGODB ERROR for {email}: {exc}")
        current_app.logger.error(f"[OTP] MongoDB write failed: {exc}")
        return jsonify({"success": False, "message": "Database error. Please try again."}), 500

    # 4. Send email via Gmail SMTP
    print(f"🚀 CALLING send_otp_email for {email}")
    email_queued = send_otp_email(email, otp)

    if not email_queued:
        return jsonify({
            "success": False,
            "message": "Failed to send OTP email. Check server logs.",
        }), 502

    return jsonify({
        "success": True,
        "message": "OTP sent successfully. Please check your inbox.",
    }), 200


# ── POST /verify-otp ──────────────────────────────────────────────────────────

@otp_api_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify a submitted OTP against the MongoDB record.

    Request JSON:  { "email": "user@example.com", "otp": "123456" }
    Success:       { "success": true, "message": "OTP verified successfully" }
    """
    # 1. Parse + validate
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp")   or "").strip()

    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    if not otp:
        return jsonify({"success": False, "message": "OTP is required."}), 400

    if not otp.isdigit() or len(otp) != 6:
        return jsonify({"success": False, "message": "OTP must be a 6-digit number."}), 400

    # 2. Look up record
    try:
        record = _otp_col().find_one({"email": email})
    except Exception as exc:
        print(f"❌ MONGODB READ ERROR for {email}: {exc}")
        current_app.logger.error(f"[OTP] MongoDB read failed: {exc}")
        return jsonify({"success": False, "message": "Database error. Please try again."}), 500

    if not record:
        return jsonify({
            "success": False,
            "message": "No OTP found for this email. Please request a new one.",
        }), 404

    # 3. Check expiry
    expires_at = record.get("expires_at")
    if not expires_at or datetime.utcnow() > expires_at:
        try:
            _otp_col().delete_one({"email": email})
        except Exception:
            pass
        return jsonify({
            "success": False,
            "message": "OTP has expired. Please request a new one.",
        }), 410

    # 4. Check match
    if otp != record.get("otp", ""):
        return jsonify({"success": False, "message": "Invalid OTP. Please try again."}), 401

    # 5. SUCCESS — delete used record
    try:
        _otp_col().delete_one({"email": email})
    except Exception:
        pass

    print(f"✅ OTP verified successfully for {email}")
    current_app.logger.info(f"[OTP] Verified successfully for {email}")

    return jsonify({"success": True, "message": "OTP verified successfully."}), 200
