import os
import random
import smtplib
import logging
import httpx
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("janaawaz.email")

def _email_provider() -> str:
    return os.getenv("EMAIL_PROVIDER", "resend").lower().strip()


def is_email_configured() -> bool:
    """Return whether the selected provider has credentials needed to attempt sending."""
    provider = _email_provider()
    if provider == "resend":
        return bool(os.getenv("RESEND_API_KEY"))
    if provider == "smtp":
        return bool(os.getenv("GMAIL_USER") and os.getenv("GMAIL_APP_PASSWORD"))
    return False



def send_verification_email(to_email: str, code: str, title: str = "Verify your email address", greeting: str = "") -> bool:
    plain_text = f"Your Jan Aawaz (जनAawaz) citizen verification code is: {code}\nValid for 10 minutes."
    html_text = build_verification_html(code, to_email, title=title, greeting=greeting)
    subject = f"Jan Aawaz (जनAawaz) Verification Code: {code}"

    provider = _email_provider()
    if provider == "resend":
        return _send_via_resend(to_email, subject, plain_text, html_text)
    if provider == "smtp":
        return _send_via_smtp(to_email, subject, plain_text, html_text)
    logger.error("[EmailService] Unsupported EMAIL_PROVIDER=%r", provider)
    return False


def send_dispatch_email(to_email: str, subject: str, body_text: str) -> bool:
    """Send formal departmental dispatch or escalation notice."""
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f4ee; padding: 24px; color: #102a2f;">
  <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid rgba(23,62,66,0.15); overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
    <div style="background-color: #0d3035; padding: 20px 28px; color: #ffffff;">
      <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #e8b855;">Jan Aawaz (जनAawaz) Prototype Dispatch Notice</h2>
      <p style="margin: 4px 0 0 0; font-size: 11px; opacity: 0.8; letter-spacing: 0.1em; text-transform: uppercase;">MUNICIPAL INFRASTRUCTURE & CIVIC REDRESSAL</p>
    </div>
    <div style="padding: 28px; font-size: 13px; line-height: 1.7; color: #334e4c; white-space: pre-wrap;">
{body_text}
    </div>
    <div style="background-color: #08272b; padding: 14px 28px; text-align: center; color: rgba(255,255,255,0.4); font-size: 10px;">
      Sent to configured demo dispatch inbox · Jan Aawaz Autonomous Civic Infrastructure
    </div>
  </div>
</body>
</html>"""

    provider = _email_provider()
    if provider == "resend":
        return _send_via_resend(to_email, subject, body_text, html_content)
    if provider == "smtp":
        return _send_via_smtp(to_email, subject, body_text, html_content)
    logger.error("[EmailService] Unsupported EMAIL_PROVIDER=%r", provider)
    return False
