"""
utils/resend_email.py
---------------------
Email delivery helper using the Resend API (https://resend.com).
Replaces Flask-Mail/SMTP for OTP delivery.

Usage:
    from utils.resend_email import send_email_with_resend
    success, error = send_email_with_resend("user@example.com", "123456")
"""

import os
import resend
from flask import current_app

# ── Debug: confirm key is loaded ────────────────────────────────────────────
print("RESEND KEY:", os.getenv("RESEND_API_KEY"))


def send_email_with_resend(to_email: str, otp: str, recipient_name: str = "User") -> tuple[bool, str]:
    """
    Send a professional OTP email via the Resend API.

    Args:
        to_email:        Recipient email address.
        otp:             6-digit OTP string.
        recipient_name:  Recipient's name (used in salutation).

    Returns:
        (True, "")            on success.
        (False, error_msg)    on failure.
    """
    # Set the API key on every call so it always reflects the current env var
    resend.api_key = os.getenv("RESEND_API_KEY")

    if not resend.api_key:
        msg = "RESEND_API_KEY is not set in environment variables."
        try:
            current_app.logger.error(f"[Resend] {msg}")
        except RuntimeError:
            print(f"[Resend] {msg}")
        return False, msg

    html_body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>Email Verification OTP</title>
    </head>
    <body style="margin:0;padding:0;background-color:#0F0F1A;font-family:'Inter',Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0F0F1A;padding:40px 16px;">
        <tr>
          <td align="center">
            <table width="520" cellpadding="0" cellspacing="0"
                   style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);
                          border-radius:16px;border:1px solid #2d2d5e;
                          box-shadow:0 20px 60px rgba(79,70,229,0.3);
                          overflow:hidden;">

              <!-- Header -->
              <tr>
                <td style="background:linear-gradient(135deg,#4F46E5,#7C3AED);
                            padding:32px 40px;text-align:center;">
                  <h1 style="margin:0;color:#ffffff;font-size:24px;
                              font-weight:700;letter-spacing:0.5px;">
                    🎓 AlumniConnect
                  </h1>
                  <p style="margin:8px 0 0;color:rgba(255,255,255,0.8);
                             font-size:13px;">MGM College of Engineering</p>
                </td>
              </tr>

              <!-- Body -->
              <tr>
                <td style="padding:40px;">
                  <p style="margin:0 0 8px;color:#C4C4D4;font-size:15px;">
                    Hello <strong style="color:#ffffff;">{recipient_name}</strong>,
                  </p>
                  <p style="margin:0 0 28px;color:#9090A8;font-size:14px;line-height:1.6;">
                    Use the OTP below to verify your email address and complete registration.
                    This code is valid for <strong style="color:#A5B4FC;">5 minutes</strong>.
                  </p>

                  <!-- OTP Box -->
                  <div style="background:linear-gradient(135deg,#1e1e3f,#252550);
                               border:2px solid #4F46E5;border-radius:12px;
                               padding:28px 20px;text-align:center;margin-bottom:28px;">
                    <p style="margin:0 0 12px;color:#9090A8;font-size:12px;
                               text-transform:uppercase;letter-spacing:2px;">
                      Your One-Time Password
                    </p>
                    <span style="font-size:44px;font-weight:800;
                                  letter-spacing:14px;color:#818CF8;
                                  font-variant-numeric:tabular-nums;">
                      {otp}
                    </span>
                  </div>

                  <!-- Warnings -->
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding:10px 14px;background:#1a1a35;
                                  border-left:3px solid #F59E0B;
                                  border-radius:0 8px 8px 0;margin-bottom:8px;">
                        <p style="margin:0;color:#FCD34D;font-size:13px;">
                          ⏱ Expires in <strong>5 minutes</strong>
                        </p>
                      </td>
                    </tr>
                    <tr><td style="height:8px;"></td></tr>
                    <tr>
                      <td style="padding:10px 14px;background:#1a1a35;
                                  border-left:3px solid #EF4444;
                                  border-radius:0 8px 8px 0;">
                        <p style="margin:0;color:#FCA5A5;font-size:13px;">
                          🔒 Do <strong>NOT</strong> share this code with anyone
                        </p>
                      </td>
                    </tr>
                  </table>

                  <p style="margin:28px 0 0;color:#6060A0;font-size:12px;
                              text-align:center;line-height:1.5;">
                    📬 Can't see this email? Check your <strong>Spam / Promotions</strong> folder.<br/>
                    If you didn't request this, please ignore this email.
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

    try:
        params = {
            "from": "onboarding@resend.dev",
            "to": [to_email],
            "subject": "AlumniConnect – Your Email Verification OTP",
            "html": html_body,
        }

        response = resend.Emails.send(params)

        try:
            current_app.logger.info(
                f"[Resend] OTP email sent to {to_email} | Response: {response}"
            )
        except RuntimeError:
            print(f"[Resend] OTP email sent to {to_email} | Response: {response}")

        return True, ""

    except Exception as exc:
        error_msg = str(exc)
        try:
            current_app.logger.error(f"[Resend] Failed to send OTP email to {to_email}: {error_msg}")
        except RuntimeError:
            print(f"[Resend] Failed to send OTP email to {to_email}: {error_msg}")
        return False, error_msg
