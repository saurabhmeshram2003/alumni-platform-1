"""
routes/otp_api.py
-----------------
REST API Blueprint for Resend-powered OTP verification.

Routes:
    POST /send-otp    – Generate OTP, store in MongoDB, deliver via Resend.
    POST /verify-otp  – Validate submitted OTP against MongoDB record.
    GET  /test-mail   – Railway smoke-test: sends a real email to verify Resend works.

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


def _build_otp_html(otp: str) -> str:
    """Return a professional dark-themed HTML email body for the OTP."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>Email Verification OTP</title>
    </head>
    <body style="margin:0;padding:0;background-color:#0F0F1A;font-family:Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0F0F1A;padding:40px 16px;">
        <tr>
          <td align="center">
            <table width="520" cellpadding="0" cellspacing="0"
                   style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                          border-radius:16px;border:1px solid #2d2d5e;overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="background:linear-gradient(135deg,#4F46E5,#7C3AED);
                            padding:32px 40px;text-align:center;">
                  <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">
                    🎓 AlumniConnect
                  </h1>
                  <p style="margin:8px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
                    MGM College of Engineering
                  </p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px;">
                  <p style="margin:0 0 20px;color:#C4C4D4;font-size:15px;">
                    Use the OTP below to verify your email. Valid for
                    <strong style="color:#A5B4FC;">5 minutes</strong>.
                  </p>

                  <!-- OTP Box -->
                  <div style="background:linear-gradient(135deg,#1e1e3f,#252550);
                               border:2px solid #4F46E5;border-radius:12px;
                               padding:28px 20px;text-align:center;margin-bottom:28px;">
                    <p style="margin:0 0 12px;color:#9090A8;font-size:12px;
                               text-transform:uppercase;letter-spacing:2px;">
                      Your One-Time Password
                    </p>
                    <span style="font-size:44px;font-weight:800;letter-spacing:14px;color:#818CF8;">
                      {otp}
                    </span>
                  </div>

                  <p style="margin:0;color:#FCD34D;font-size:13px;">
                    ⏱ Expires in <strong>5 minutes</strong> &nbsp;|&nbsp;
                    🔒 Do <strong>NOT</strong> share this code
                  </p>

                  <p style="margin:20px 0 0;color:#6060A0;font-size:12px;text-align:center;">
                    📬 Can't find this? Check your <strong>Spam / Promotions</strong> folder.
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td style="border-top:1px solid #2d2d5e;padding:20px 40px;
                            background:#0d0d1f;text-align:center;">
                  <p style="margin:0;color:#404060;font-size:12px;">
                    Alumni Platform · MGM College of Engineering · Automated message
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


# ── GET /test-mail ─────────────────────────────────────────────────────────────

@otp_api_bp.route("/test-mail", methods=["GET"])
def test_mail():
    """
    Railway smoke-test route.
    Hit GET /test-mail to verify Resend is working end-to-end.
    Check Railway logs for RESEND SUCCESS RESPONSE / RESEND ERROR.

    Query param (optional): ?to=your@email.com
    Default sends to the address passed, or a hardcoded fallback.
    """
    test_email = request.args.get("to", "academicsmaterial7474@gmail.com")

    print(f"[test-mail] Sending test email to: {test_email}")

    success, err = send_email_with_resend(
        test_email,
        "Railway Test – AlumniConnect Email Working ✅",
        """
        <div style="font-family:sans-serif;padding:32px;background:#0F0F1A;color:#ffffff;">
            <h1 style="color:#818CF8;">Railway Email Working ✅</h1>
            <p style="color:#C4C4D4;">
                If you're reading this, your Resend integration is configured correctly
                and emails are being delivered from Railway.
            </p>
            <p style="color:#9090A8;font-size:13px;">Sent by AlumniConnect · MGM College of Engineering</p>
        </div>
        """
    )

    if success:
        return jsonify({"success": True, "message": f"Test email sent to {test_email}. Check Railway logs."}), 200
    else:
        return jsonify({"success": False, "message": "Email failed. Check Railway logs for RESEND ERROR.", "detail": err}), 502


# ── POST /send-otp ────────────────────────────────────────────────────────────

@otp_api_bp.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Generate and send a 6-digit OTP to the given email via Resend.

    Request JSON:
        { "email": "user@example.com" }

    Response JSON (success):
        { "success": true, "message": "OTP sent successfully", "demo_otp": "XXXXXX" }
    """
    # ── 1. Parse + validate ───────────────────────────────────────────────────
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"success": False, "error": "Email required"}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"success": False, "error": "Invalid email format"}), 400

    # ── 2. Generate OTP ───────────────────────────────────────────────────────
    otp = _generate_otp()
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=5)

    print(f"[send-otp] Generating OTP for {email}")

    # ── 3. Upsert in MongoDB ──────────────────────────────────────────────────
    try:
        _otp_collection().update_one(
            {"email": email},
            {"$set": {"email": email, "otp": otp, "created_at": now, "expires_at": expires_at}},
            upsert=True,
        )
    except Exception as exc:
        print(f"[send-otp] ❌ MongoDB write failed for {email}: {exc}")
        return jsonify({"success": False, "error": "Database error. Please try again."}), 500

    # ── 4. Send via Resend ────────────────────────────────────────────────────
    print("🚀 CALLING RESEND FUNCTION for:", email)
    success, error_detail = send_email_with_resend(
        email,
        "AlumniConnect – Your Email Verification OTP",
        _build_otp_html(otp),
    )

    if not success:
        print(f"[send-otp] ❌ Resend failed for {email}: {error_detail}")
        return jsonify({
            "success": False,
            "error": "Email sending failed. Check Railway logs.",
            "detail": error_detail,   # exact Resend error — remove in production
        }), 502

    return jsonify({
        "success": True,
        "message": "OTP sent successfully",
        "demo_otp": otp,   # ⚠ Remove before going fully live
    }), 200


# ── POST /verify-otp ──────────────────────────────────────────────────────────

@otp_api_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify the OTP submitted by the user.

    Request JSON:
        { "email": "user@example.com", "otp": "123456" }
    """
    data = request.get_json(silent=True) or {}
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

    # ── Look up record ────────────────────────────────────────────────────────
    try:
        record = _otp_collection().find_one({"email": email})
    except Exception as exc:
        print(f"[verify-otp] ❌ MongoDB read failed for {email}: {exc}")
        return jsonify({"success": False, "message": "Database error. Please try again."}), 500

    if not record:
        return jsonify({"success": False, "message": "No OTP found. Please request a new one."}), 404

    # ── Check expiry ──────────────────────────────────────────────────────────
    expires_at = record.get("expires_at")
    if not expires_at or datetime.utcnow() > expires_at:
        try:
            _otp_collection().delete_one({"email": email})
        except Exception:
            pass
        return jsonify({"success": False, "message": "OTP has expired. Please request a new one."}), 410

    # ── Check match ───────────────────────────────────────────────────────────
    if otp != record.get("otp", ""):
        return jsonify({"success": False, "message": "Invalid OTP. Please try again."}), 401

    # ── SUCCESS — delete used record ──────────────────────────────────────────
    try:
        _otp_collection().delete_one({"email": email})
    except Exception:
        pass

    print(f"[verify-otp] ✅ OTP verified for {email}")
    return jsonify({"success": True, "message": "OTP verified successfully"}), 200
