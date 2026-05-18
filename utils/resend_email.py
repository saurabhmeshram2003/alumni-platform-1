"""
utils/resend_email.py
---------------------
Resend API email helper for Railway production deployment.
Supports any subject + HTML content (not just OTPs).

Usage:
    from utils.resend_email import send_email_with_resend
    success = send_email_with_resend("user@example.com", "Subject", "<h1>Hello</h1>")
"""

import os
import resend


def send_email_with_resend(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an email via the Resend API.

    Args:
        to_email:     Recipient email address.
        subject:      Email subject line.
        html_content: HTML body of the email.

    Returns:
        True on success, False on any failure.
    """
    try:
        # Load API key at runtime — never cache at module level
        api_key = os.getenv("RESEND_API_KEY")
        print("RESEND API KEY:", api_key)

        if not api_key:
            print("❌ RESEND ERROR: RESEND_API_KEY is not set in environment")
            return False

        resend.api_key = api_key

        print("SENDING EMAIL TO:", to_email)
        print("SUBJECT:", subject)

        response = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [to_email],           # MUST be a list
            "subject": subject,
            "html": html_content,
        })

        print("RESEND SUCCESS RESPONSE:", response)
        return True

    except Exception as e:
        print("❌ RESEND ERROR:", str(e))
        return False
