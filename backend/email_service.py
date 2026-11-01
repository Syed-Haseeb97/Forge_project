"""Email delivery and short-lived citizen OTP helpers for Jan Aawaz."""
import html
import logging
import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("janaawaz.email")

# In-memory OTP storage is intentionally process-local; production multi-instance
# deployments should move this state to the shared database or cache.
_otp_store: Dict[str, Dict[str, Any]] = {}


def _email_provider() -> str:
    return (os.getenv("EMAIL_PROVIDER") or "resend").lower().strip()


def is_email_configured() -> bool:
    """Return whether the selected provider has credentials needed to attempt sending."""
    provider = _email_provider()
    if provider == "resend":
        return bool(os.getenv("RESEND_API_KEY"))
    if provider == "smtp":
        return bool(os.getenv("GMAIL_USER") and os.getenv("GMAIL_APP_PASSWORD"))
    return False


def check_rate_limit(email: str, min_interval_seconds: int = 30) -> Optional[int]:
    normalized = email.strip().lower()
    record = _otp_store.get(normalized)
    if record and "last_sent_at" in record:
        elapsed = (datetime.utcnow() - record["last_sent_at"]).total_seconds()
        if elapsed < min_interval_seconds:
            return int(min_interval_seconds - elapsed) + 1
    return None


def generate_and_store_otp(email: str, citizen_data: Optional[Dict[str, Any]] = None) -> str:
    normalized = email.strip().lower()
    code = f"{random.randint(100000, 999999)}"
    _otp_store[normalized] = {
        "code": code,
        "citizen_data": citizen_data or {},
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "last_sent_at": datetime.utcnow(),
        "attempts": 0,
    }
    return code


def get_stored_otp_data(email: str) -> Optional[Dict[str, Any]]:
    return _otp_store.get(email.strip().lower())


def verify_otp_code(email: str, input_code: str) -> bool:
    normalized = email.strip().lower()
    record = _otp_store.get(normalized)
    if not record:
        return False
    if datetime.utcnow() > record["expires_at"] or record["attempts"] >= 5:
        _otp_store.pop(normalized, None)
        return False
    record["attempts"] += 1
    return record["code"] == input_code.strip()


def pop_otp(email: str) -> Optional[Dict[str, Any]]:
    return _otp_store.pop(email.strip().lower(), None)


def build_verification_html(code: str, email: str, title: str = "Verify your email address", greeting: str = "") -> str:
    safe_email = html.escape(email)
    safe_title = html.escape(title)
    safe_greeting = html.escape(greeting)
    greeting_html = (
        f"<p style='font-weight:600;color:#0d3035'>Dear {safe_greeting},</p>"
        if safe_greeting else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jan Aawaz citizen verification</title></head>
<body style="margin:0;padding:32px 16px;background:#f6f4ee;font-family:Arial,sans-serif;color:#102a2f">
<table role="presentation" align="center" cellpadding="0" cellspacing="0" width="100%" style="max-width:560px;background:#fff;border:1px solid #e5e5e5;border-radius:16px">
<tr><td style="background:#0d3035;padding:22px;text-align:center;color:#fff">
<strong style="font-size:24px"><span style="color:#e8b855">जन</span>Aawaz</strong>
<p style="font-size:10px;letter-spacing:2px">PUBLIC GRIEVANCE & INFRASTRUCTURE REDRESSAL PORTAL</p>
</td></tr>
<tr><td style="padding:32px">
<p style="font-size:11px;font-weight:bold;letter-spacing:2px;color:#ba7c29">SECURE CITIZEN ACCESS</p>
<h1 style="font-size:25px;color:#0d3035">{safe_title}</h1>
{greeting_html}
<p>A verification request was initiated for <strong>{safe_email}</strong>. Use this six-digit code:</p>
<div style="margin:24px 0;padding:22px;text-align:center;background:#fffaf0;border:1px solid #ead7b5;border-radius:12px">
<strong style="font-family:monospace;font-size:38px;letter-spacing:8px;color:#0d3035">{code}</strong>
<p style="font-size:11px;color:#8a7a58">Valid for 10 minutes. Do not share this code.</p>
</div>
<p style="font-size:12px;color:#687976">If you did not request this verification, you can safely ignore this email.</p>
</td></tr>
<tr><td style="padding:16px;text-align:center;background:#08272b;color:#ddd;font-size:10px">© 2026 Jan Aawaz</td></tr>
</table></body></html>"""


def _send_via_resend(to_email: str, subject: str, plain_text: str, html_text: str) -> bool:
    """Submit a transactional email through Resend's HTTPS API."""
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.error("[EmailService] RESEND_API_KEY is not configured.")
        return False
    sender = os.getenv("EMAIL_FROM") or "Jan Aawaz Portal <onboarding@resend.dev>"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"from": sender, "to": [to_email], "subject": subject, "html": html_text, "text": plain_text},
            )
        if response.status_code in (200, 201):
            try:
                message_id = response.json().get("id", "unknown")
            except ValueError:
                message_id = "unknown"
            logger.info("[EmailService] Resend accepted message id=%s recipient=%s", message_id, to_email)
            return True
        logger.error("[EmailService] Resend rejected recipient=%s status=%s response=%s",
                     to_email, response.status_code, response.text[:1000])
        return False
    except httpx.HTTPError as exc:
        logger.exception("[EmailService] Resend HTTPS request failed recipient=%s: %s", to_email, exc)
        return False


def _send_via_smtp(to_email: str, subject: str, plain_text: str, html_text: str) -> bool:
    """Optional local-development SMTP transport. Render deployments should use Resend HTTPS."""
    gmail_user = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not app_password:
        logger.error("[EmailService] SMTP selected but Gmail credentials are missing.")
        return False
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = os.getenv("EMAIL_FROM") or f"Jan Aawaz Portal <{gmail_user}>"
    message["To"] = to_email
    message.attach(MIMEText(plain_text, "plain"))
    message.attach(MIMEText(html_text, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(gmail_user, app_password)
            server.send_message(message)
        logger.info("[EmailService] SMTP accepted message recipient=%s", to_email)
        return True
    except Exception as exc:
        logger.exception("[EmailService] SMTP send failed recipient=%s: %s", to_email, exc)
        return False


def _send_email(to_email: str, subject: str, plain_text: str, html_text: str) -> bool:
    provider = _email_provider()
    if provider == "resend":
        return _send_via_resend(to_email, subject, plain_text, html_text)
    if provider == "smtp":
        return _send_via_smtp(to_email, subject, plain_text, html_text)
    logger.error("[EmailService] Unsupported EMAIL_PROVIDER=%r", provider)
    return False


def send_verification_email(to_email: str, code: str, title: str = "Verify your email address", greeting: str = "") -> bool:
    plain_text = f"Your Jan Aawaz citizen verification code is: {code}\nValid for 10 minutes."
    html_text = build_verification_html(code, to_email, title=title, greeting=greeting)
    subject = f"Jan Aawaz Verification Code: {code}"
    return _send_email(to_email, subject, plain_text, html_text)


def send_dispatch_email(to_email: str, subject: str, body_text: str) -> bool:
    safe_body = html.escape(body_text)
    html_content = f"""<!doctype html><html lang="en"><body style="font-family:Arial,sans-serif;background:#f6f4ee;padding:24px;color:#102a2f">
<div style="max-width:650px;margin:auto;background:#fff;border-radius:16px;overflow:hidden">
<div style="background:#0d3035;padding:20px 28px;color:#fff"><h2 style="color:#e8b855">Jan Aawaz Dispatch Notice</h2></div>
<div style="padding:28px;white-space:pre-wrap">{safe_body}</div>
<div style="background:#08272b;padding:14px;text-align:center;color:#ddd;font-size:10px">Jan Aawaz Autonomous Civic Infrastructure</div>
</div></body></html>"""
    return _send_email(to_email, subject, body_text, html_content)
