"""
utils/otp.py
------------
OTP generation and Gmail SMTP email sending for the Alumni Platform.
Production-ready — sends email in a background thread to prevent
HTTP 502 timeouts caused by slow SMTP connections on Render.
"""

import random
import string
import threading
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message
from extensions import mail


def generate_otp(length: int = 6) -> str:
    """Return a secure 6-digit numeric OTP."""
    otp = ''.join(random.choices(string.digits, k=length))
    try:
        current_app.logger.info(f"[OTP] Generated new OTP: {otp}")
    except RuntimeError:
        pass  # Outside of app context during testing
    return otp


def get_otp_expiry(minutes: int = 5) -> datetime:
    """Return a UTC datetime `minutes` from now."""
    return datetime.utcnow() + timedelta(minutes=minutes)


def _send_mail_sync(app, msg):
    """Synchronously send the email within the app context."""
    with app.app_context():
        try:
            mail.send(msg)
            app.logger.info(f"[Email] Successfully sent OTP email to {msg.recipients}")
            return True, ""
        except Exception as e:
            app.logger.error(f"[Email] Exact exception during send: {str(e)}")
            return False, str(e)


def send_otp_email(recipient_email: str, otp_code: str, recipient_name: str = "User") -> tuple[bool, str]:
    """
    Send OTP via Gmail SMTP using Flask-Mail.
    Attempts to send synchronously with a timeout to catch bad passwords
    and prevent silent failures, while avoiding HTTP 502 errors.
    Returns (success_bool, error_message).
    """
    try:
        app = current_app._get_current_object()

        mail_username = app.config.get('MAIL_USERNAME')
        sender_email = app.config.get('MAIL_DEFAULT_SENDER') or mail_username
        
        if not sender_email:
            app.logger.warning("MAIL_USERNAME / MAIL_DEFAULT_SENDER is not set. Cannot send OTP.")
            return False, "Email configuration missing."

        sender = ("AlumniConnect", sender_email)

        if not app.config.get('MAIL_PASSWORD'):
            app.logger.warning("MAIL_PASSWORD is not set. Cannot send OTP.")
            return False, "Email configuration missing (MAIL_PASSWORD)."

        subject = "Alumni Platform – Email Verification OTP"

        body = (
            f"Hello {recipient_name},\n\n"
            f"Your One-Time Password (OTP) for the Alumni Platform is:\n\n"
            f"    {otp_code}\n\n"
            f"This OTP is valid for 5 minutes.\n"
            f"Do NOT share it with anyone.\n\n"
            f"If you didn't request this, please ignore this email.\n\n"
            f"Regards,\nAlumni Platform Team — MGM College of Engineering\n"
        )

        html_body = f"""
        <div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:auto;
                    padding:32px;border:1px solid #E5E7EB;border-radius:12px;
                    background:#ffffff;">
            <h2 style="color:#4F46E5;margin-bottom:8px;">Alumni Platform</h2>
            <p style="color:#6B7280;font-size:14px;margin-bottom:24px;">
                MGM College of Engineering — Email Verification
            </p>

            <p style="color:#1F2937;margin-bottom:8px;">Hello <strong>{recipient_name}</strong>,</p>
            <p style="color:#1F2937;margin-bottom:24px;">
                Use the OTP below to verify your email address and complete registration.
            </p>

            <div style="background:#F0F0FF;border:1px solid #C7D2FE;border-radius:8px;
                        padding:20px;text-align:center;margin-bottom:24px;">
                <span style="font-size:36px;font-weight:700;letter-spacing:12px;color:#4F46E5;">
                    {otp_code}
                </span>
            </div>

            <p style="color:#6B7280;font-size:13px;margin-bottom:8px;">
                ⏱ This OTP expires in <strong>5 minutes</strong>.
            </p>
            <p style="color:#6B7280;font-size:13px;margin-bottom:8px;">
                🔒 Do <strong>NOT</strong> share this code with anyone.
            </p>
            <p style="color:#F59E0B;font-size:12px;margin-bottom:0;">
                📬 Don't see this email? Check your <strong>Spam / Junk</strong> folder.
            </p>

            <hr style="border:none;border-top:1px solid #E5E7EB;margin:24px 0;">
            <p style="color:#9CA3AF;font-size:12px;">
                If you didn't register on the Alumni Platform, please ignore this email.
            </p>
        </div>
        """

        msg = Message(
            subject=subject,
            sender=sender,
            recipients=[recipient_email],
            body=body,
            html=html_body,
        )

        def _send_mail_sync_thread(app_obj, message):
            with app_obj.app_context():
                try:
                    mail.send(message)
                    app_obj.logger.info(f"[Email] Successfully sent OTP email to {message.recipients}")
                except Exception as e:
                    app_obj.logger.error(f"[Email] Exact exception during send: {str(e)}")

        # Start a background thread
        thread = threading.Thread(target=_send_mail_sync_thread, args=(app, msg))
        thread.start()
        
        return True, ""

    except Exception as e:
        current_app.logger.error(f"[Email] Failed to queue OTP email: {e}")
        return False, str(e)


def send_reset_email(recipient_email: str, reset_url: str, recipient_name: str = "User") -> tuple[bool, str]:
    try:
        app = current_app._get_current_object()

        mail_username = app.config.get('MAIL_USERNAME')
        sender_email = app.config.get('MAIL_DEFAULT_SENDER') or mail_username

        if not sender_email:
            app.logger.warning("MAIL_USERNAME / MAIL_DEFAULT_SENDER is not set. Cannot send reset email.")
            return False, "Email configuration missing."

        sender = ("AlumniConnect", sender_email)

        subject = "Alumni Platform – Password Reset"
        
        body = (
            f"Hello {recipient_name},\n\n"
            f"You have requested to reset your password on the Alumni Platform.\n"
            f"Click the link below to reset your password:\n\n"
            f"{reset_url}\n\n"
            f"This link will expire in 30 minutes.\n"
            f"If you didn't request this, please ignore this email.\n"
        )
        
        html_body = f"""
        <div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:auto;
                    padding:32px;border:1px solid #E5E7EB;border-radius:12px;
                    background:#ffffff;">
            <h2 style="color:#4F46E5;margin-bottom:8px;">Alumni Platform</h2>
            <p style="color:#1F2937;margin-bottom:8px;">Hello <strong>{recipient_name}</strong>,</p>
            <p style="color:#1F2937;margin-bottom:24px;">
                You have requested to reset your password. Click the button below to reset it.
            </p>
            <div style="text-align:center;margin-bottom:24px;">
                <a href="{reset_url}" style="background-color:#4F46E5;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:bold;">Reset Password</a>
            </div>
            <p style="color:#6B7280;font-size:13px;margin-bottom:8px;">
                ⏱ This link expires in <strong>30 minutes</strong>.
            </p>
            <p style="color:#9CA3AF;font-size:12px;">
                If you didn't request this, please ignore this email.
            </p>
        </div>
        """

        msg = Message(
            subject=subject,
            sender=sender,
            recipients=[recipient_email],
            body=body,
            html=html_body,
        )

        def _send_reset_sync_thread(app_obj, message):
            with app_obj.app_context():
                try:
                    mail.send(message)
                    app_obj.logger.info(f"[Email] Successfully sent reset email to {message.recipients}")
                except Exception as e:
                    app_obj.logger.error(f"[Email] Failed to send reset email: {str(e)}")

        thread = threading.Thread(target=_send_reset_sync_thread, args=(app, msg))
        thread.start()
        
        return True, ""

    except Exception as e:
        current_app.logger.error(f"[Email] Failed to queue reset email: {e}")
        return False, str(e)

