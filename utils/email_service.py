"""
utils/email_service.py
----------------------
Clean Gmail SMTP email helper using Flask-Mail.
Works with Railway environment variables.

Usage:
    from utils.email_service import send_otp_email
    success = send_otp_email("user@example.com", "123456")
"""

import os
import threading
from flask import current_app
from flask_mail import Message
from extensions import mail


def send_otp_email(to_email: str, otp: str, recipient_name: str = "User") -> bool:
    """
    Send a 6-digit OTP to the given email via Gmail SMTP (Flask-Mail).
    Runs in a background thread to avoid blocking the request.

    Args:
        to_email:        Recipient email address.
        otp:             6-digit OTP string.
        recipient_name:  Name shown in the salutation.

    Returns:
        True  – email queued successfully in background thread.
        False – configuration missing (logged clearly).
    """
    # ── Debug prints visible in Railway logs ──────────────────────────────────
    print("MAIL USER:", os.getenv("MAIL_USERNAME"))
    print("SENDING TO:", to_email)

    try:
        app = current_app._get_current_object()

        mail_user = app.config.get("MAIL_USERNAME")
        mail_pass = app.config.get("MAIL_PASSWORD")
        sender_email = app.config.get("MAIL_DEFAULT_SENDER") or mail_user

        if not mail_user:
            print("❌ EMAIL ERROR: MAIL_USERNAME is not set")
            app.logger.error("[Email] MAIL_USERNAME not set — cannot send OTP.")
            return False

        if not mail_pass:
            print("❌ EMAIL ERROR: MAIL_PASSWORD is not set")
            app.logger.error("[Email] MAIL_PASSWORD not set — cannot send OTP.")
            return False

        html_body = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"/></head>
        <body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 16px;">
            <tr><td align="center">
              <table width="520" cellpadding="0" cellspacing="0"
                     style="background:#ffffff;border-radius:12px;
                            border:1px solid #E5E7EB;overflow:hidden;">

                <!-- Header -->
                <tr>
                  <td style="background:linear-gradient(135deg,#4F46E5,#7C3AED);
                              padding:28px 40px;text-align:center;">
                    <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;">
                      🎓 AlumniConnect
                    </h1>
                    <p style="margin:6px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">
                      MGM College of Engineering
                    </p>
                  </td>
                </tr>

                <!-- Body -->
                <tr>
                  <td style="padding:36px 40px;">
                    <p style="margin:0 0 8px;color:#1F2937;font-size:15px;">
                      Hello <strong>{recipient_name}</strong>,
                    </p>
                    <p style="margin:0 0 24px;color:#6B7280;font-size:14px;line-height:1.6;">
                      Use the OTP below to verify your email and complete registration.
                    </p>

                    <!-- OTP Box -->
                    <div style="background:#F0F0FF;border:1px solid #C7D2FE;
                                border-radius:10px;padding:24px;
                                text-align:center;margin-bottom:24px;">
                      <p style="margin:0 0 8px;color:#6B7280;font-size:12px;
                                 text-transform:uppercase;letter-spacing:2px;">
                        Your One-Time Password
                      </p>
                      <span style="font-size:40px;font-weight:800;
                                    letter-spacing:12px;color:#4F46E5;">
                        {otp}
                      </span>
                    </div>

                    <p style="margin:0 0 6px;color:#6B7280;font-size:13px;">
                      ⏱ This OTP expires in <strong>5 minutes</strong>.
                    </p>
                    <p style="margin:0 0 6px;color:#6B7280;font-size:13px;">
                      🔒 Do <strong>NOT</strong> share this code with anyone.
                    </p>
                    <p style="margin:16px 0 0;color:#F59E0B;font-size:12px;">
                      📬 Can't find it? Check your <strong>Spam / Junk</strong> folder.
                    </p>
                  </td>
                </tr>

                <!-- Footer -->
                <tr>
                  <td style="border-top:1px solid #E5E7EB;padding:18px 40px;
                              background:#F9FAFB;text-align:center;">
                    <p style="margin:0;color:#9CA3AF;font-size:12px;">
                      Alumni Platform · MGM College of Engineering · Automated message
                    </p>
                  </td>
                </tr>

              </table>
            </td></tr>
          </table>
        </body>
        </html>
        """

        plain_body = (
            f"Hello {recipient_name},\n\n"
            f"Your OTP for AlumniConnect is: {otp}\n\n"
            f"Valid for 5 minutes. Do NOT share it with anyone.\n\n"
            f"If you didn't request this, ignore this email.\n\n"
            f"— AlumniConnect, MGM College of Engineering"
        )

        msg = Message(
            subject="AlumniConnect – Email Verification OTP",
            sender=("AlumniConnect", sender_email),
            recipients=[to_email],
            body=plain_body,
            html=html_body,
        )

        # ── Send in background thread to avoid gunicorn timeouts ──────────────
        def _send_in_thread(app_obj, message):
            with app_obj.app_context():
                try:
                    mail.send(message)
                    print(f"✅ EMAIL SENT SUCCESSFULLY to {message.recipients}")
                    app_obj.logger.info(f"[Email] OTP sent to {message.recipients}")
                except Exception as exc:
                    print(f"❌ EMAIL SEND ERROR: {exc}")
                    app_obj.logger.error(f"[Email] Failed to send OTP email: {exc}")

        thread = threading.Thread(target=_send_in_thread, args=(app, msg), daemon=True)
        thread.start()

        print(f"🚀 EMAIL QUEUED for {to_email} (background thread started)")
        return True

    except Exception as exc:
        print(f"❌ EMAIL SETUP ERROR: {exc}")
        try:
            current_app.logger.error(f"[Email] Failed to queue OTP email: {exc}")
        except RuntimeError:
            pass
        return False
