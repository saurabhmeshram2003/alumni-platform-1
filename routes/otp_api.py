"""
routes/otp_api.py
-----------------
REST API Blueprint for Resend-powered OTP verification.

Routes:
    POST /send-otp    – Generate OTP, store in MongoDB, deliver via Resend.
    POST /verify-otp  – Validate submitted OTP against MongoDB record.

MongoDB collection:  otp_verifications
Document schema:
    {
        email:      str,
        otp:        str,         # 6-digit numeric string
        created_at: datetime,
        expires_at: datetime     # created_at + 5 minutes
    }
"""

import os
import re
import random
import string
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from extensions import mongo
from utils.resend_email import send_email_with_resend

otp_api_bp = Blueprint("otp_api", __name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def _generate_otp(length: int = 6) -> str:
    """Return a cryptographically random 6-digit numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def _otp_collection():
    """Return the otp_verifications collection via PyMongo."""
    return mongo.db.otp_verifications


# ── POST /send-otp ────────────────────────────────────────────────────────────

@otp_api_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Generate and send a 6-digit OTP to the given email via Resend.

    Request JSON:
        { "email": "user@example.com" }

    Response JSON (success):
        { "success": true, "message": "OTP sent successfully", "demo_otp": "XXXXXX" }

    Response JSON (error):
        { "success": false, "message": "<reason>" }
    """
    # ── 1. Parse request body ─────────────────────────────────────────────────
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    # ── 2. Validate email ─────────────────────────────────────────────────────
    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    # ── 3. Generate OTP ───────────────────────────────────────────────────────
    otp = _generate_otp()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=5)

    current_app.logger.info(f"[OTP API] Generating OTP for {email}")

    # ── 4. Upsert OTP record in MongoDB ──────────────────────────────────────
    try:
        _otp_collection().update_one(
            {"email": email},
            {
                "$set": {
                    "email": email,
                    "otp": otp,
                    "created_at": now,
                    "expires_at": expires_at,
                }
            },
            upsert=True,
        )
        current_app.logger.info(f"[OTP API] OTP record upserted for {email}")
    except Exception as exc:
        current_app.logger.error(f"[OTP API] MongoDB write failed for {email}: {exc}")
        return jsonify({"success": False, "message": "Database error. Please try again."}), 500

    # ── 5. Send email via Resend ──────────────────────────────────────────────
    try:
        success, error_msg = send_email_with_resend(email, otp)
    except Exception as exc:
        current_app.logger.error(f"[OTP API] Unexpected error calling Resend for {email}: {exc}")
        return jsonify({"success": False, "message": "Email service error. Please try again."}), 502

    if not success:
        current_app.logger.error(f"[OTP API] Resend delivery failed for {email}: {error_msg}")
        return jsonify({
            "success": False,
            "message": f"Failed to send OTP email: {error_msg}",
        }), 502

    # ── 6. Return success (demo_otp included for development/demo only) ───────
    current_app.logger.info(f"[OTP API] OTP sent successfully to {email}")
    return jsonify({
        "success": True,
        "message": "OTP sent successfully",
        "demo_otp": otp,   # ⚠ Remove or gate behind DEBUG flag before going live
    }), 200


# ── POST /verify-otp ──────────────────────────────────────────────────────────

@otp_api_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify the OTP submitted by the user.

    Request JSON:
        { "email": "user@example.com", "otp": "123456" }

    Response JSON (success):
        { "success": true, "message": "OTP verified successfully" }

    Response JSON (error):
        { "success": false, "message": "<reason>" }
    """
    # ── 1. Parse request body ─────────────────────────────────────────────────
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp")   or "").strip()

    # ── 2. Input validation ───────────────────────────────────────────────────
    if not email:
        return jsonify({"success": False, "message": "Email is required."}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "Invalid email format."}), 400

    if not otp:
        return jsonify({"success": False, "message": "OTP is required."}), 400

    if not otp.isdigit() or len(otp) != 6:
        return jsonify({"success": False, "message": "OTP must be a 6-digit number."}), 400

    # ── 3. Look up record in MongoDB ──────────────────────────────────────────
    try:
        record = _otp_collection().find_one({"email": email})
    except Exception as exc:
        current_app.logger.error(f"[OTP API] MongoDB read failed for {email}: {exc}")
        return jsonify({"success": False, "message": "Database error. Please try again."}), 500

    if not record:
        current_app.logger.warning(f"[OTP API] No OTP record found for {email}")
        return jsonify({
            "success": False,
            "message": "No OTP found for this email. Please request a new OTP.",
        }), 404

    # ── 4. Check expiry ───────────────────────────────────────────────────────
    expires_at = record.get("expires_at")
    if not expires_at or datetime.utcnow() > expires_at:
        current_app.logger.warning(f"[OTP API] Expired OTP used for {email}")
        # Clean up expired record
        try:
            _otp_collection().delete_one({"email": email})
        except Exception:
            pass
        return jsonify({
            "success": False,
            "message": "OTP has expired. Please request a new one.",
        }), 410

    # ── 5. Check OTP match ────────────────────────────────────────────────────
    stored_otp = record.get("otp", "")
    if otp != stored_otp:
        current_app.logger.warning(f"[OTP API] Invalid OTP attempt for {email}")
        return jsonify({"success": False, "message": "Invalid OTP. Please try again."}), 401

    # ── 6. SUCCESS — remove the used record ───────────────────────────────────
    try:
        _otp_collection().delete_one({"email": email})
    except Exception as exc:
        current_app.logger.warning(f"[OTP API] Could not delete used OTP record for {email}: {exc}")

    current_app.logger.info(f"[OTP API] OTP verified successfully for {email}")
    return jsonify({"success": True, "message": "OTP verified successfully"}), 200
