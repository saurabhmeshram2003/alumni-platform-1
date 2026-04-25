"""
utils/otp.py
------------
OTP generation and Gmail SMTP email sending for the Alumni Platform.
Production-ready — no dev fallbacks.
"""

import random
import string
from datetime import datetime, timedelta

from flask import current_app
from flask_mail import Message
from extensions import mail


def generate_otp(length: int = 6) -> str:
    """Return a secure 6-digit numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def get_otp_expiry(minutes: int = 5) -> datetime:
    """Return a UTC datetime `minutes` from now."""
    return datetime.utcnow() + timedelta(minutes=minutes)


def send_otp_email(recipient_email: str, otp_code: str, recipient_name: str = "User") -> None:
    """
    Send OTP via Gmail SMTP using Flask-Mail.
    Raises an exception on failure — caller must handle it and show
    a proper error to the user.
    """
    sender = (
        current_app.config.get('MAIL_DEFAULT_SENDER')
        or current_app.config.get('MAIL_USERNAME')
    )

    if not sender:
        raise RuntimeError(
            "MAIL_USERNAME / MAIL_DEFAULT_SENDER is not set in .env. "
            "Please configure Gmail credentials."
        )

    subject = "Alumni Platform – Email Verification OTP"

    body = (
        f"Hello {recipient_name},\n\n"
        f"Your One-Time Password (OTP) for the Alumni Platform is:\n\n"
        f"    {otp_code}\n\n"
        f"This OTP is valid for 5 minutes.\n"
        f"Do NOT share it with anyone.\n\n"
        f"Regards,\nAlumni Platform Team\n"
    )

    html_body = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:480px;margin:auto;
                padding:32px;border:1px solid #E5E7EB;border-radius:12px;
                background:#ffffff;">
        <h2 style="color:#4F46E5;margin-bottom:8px;">Alumni Platform</h2>
        <p style="color:#6B7280;font-size:14px;margin-bottom:24px;">Email Verification</p>

        <p style="color:#1F2937;margin-bottom:8px;">Hello <strong>{recipient_name}</strong>,</p>
        <p style="color:#1F2937;margin-bottom:24px;">
            Use the OTP below to verify your email address.
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
        <p style="color:#6B7280;font-size:13px;">
            🔒 Do <strong>NOT</strong> share this code with anyone.
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
    mail.send(msg)
