import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM") or (f"Jan Aawaz (जनAawaz) Portal <{GMAIL_USER}>" if GMAIL_USER else None)

# In-memory OTP storage: { normalized_email: { "code": str, "citizen_data": dict, "expires_at": datetime, "last_sent_at": datetime, "attempts": int } }
_otp_store: Dict[str, Dict[str, Any]] = {}


def check_rate_limit(email: str, min_interval_seconds: int = 30) -> Optional[int]:
    """
    Returns seconds remaining if an OTP was sent to this email within min_interval_seconds, else None.
    """
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
    normalized = email.strip().lower()
    return _otp_store.get(normalized)


def verify_otp_code(email: str, input_code: str) -> bool:
    normalized = email.strip().lower()
    record = _otp_store.get(normalized)
    if not record:
        return False

    if datetime.utcnow() > record["expires_at"]:
        _otp_store.pop(normalized, None)
        return False

    if record["attempts"] >= 5:
        _otp_store.pop(normalized, None)
        return False

    record["attempts"] += 1

    if record["code"] == input_code.strip():
        # Do not immediately pop so caller can read citizen_data if needed
        return True

    return False


def pop_otp(email: str) -> Optional[Dict[str, Any]]:
    normalized = email.strip().lower()
    return _otp_store.pop(normalized, None)


def build_verification_html(code: str, email: str, title: str = "Verify your email address", greeting: str = "") -> str:
    greeting_html = f"<p style='font-size: 15px; font-weight: 600; color: #0d3035; margin: 0 0 10px 0;'>Dear {greeting},</p>" if greeting else ""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Jan Aawaz (जनAawaz) Citizen Verification</title>
</head>
<body style="margin: 0; padding: 32px 16px; background-color: #f6f4ee; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #102a2f;">
  <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 560px; background-color: #ffffff; border: 1px solid rgba(23, 62, 66, 0.12); border-radius: 20px; overflow: hidden; box-shadow: 0 16px 45px rgba(26, 53, 52, 0.08);">
    <!-- Official Top Strip with Logo -->
    <tr>
      <td style="background-color: #0d3035; padding: 18px 24px; text-align: center;">
        <div style="margin-bottom: 4px;">
          <span style="color: #e8b855; font-size: 24px; font-weight: 800; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">जन</span><span style="color: #ffffff; font-size: 24px; font-weight: 800; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">Aawaz</span>
        </div>
        <span style="color: rgba(255, 255, 255, 0.7); font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;">
          PUBLIC GRIEVANCE & INFRASTRUCTURE REDRESSAL PORTAL
        </span>
      </td>
    </tr>
    <!-- Main Content -->
    <tr>
      <td style="padding: 36px 32px;">
        <div style="font-size: 11px; font-weight: 700; letter-spacing: 0.16em; color: #ba7c29; text-transform: uppercase; margin-bottom: 8px;">
          SECURE CITIZEN ACCESS
        </div>
        <h1 style="font-size: 26px; font-weight: 700; color: #0d3035; margin: 0 0 14px 0; font-family: Georgia, serif;">
          {title}
        </h1>
        {greeting_html}
        <p style="font-size: 14px; line-height: 1.6; color: #5f716e; margin: 0 0 24px 0;">
          A citizen verification request was initiated for <strong style="color: #0d3035;">{email}</strong> on the <strong>Jan Aawaz (जनAawaz)</strong> Public Grievance Portal. Use your official 6-digit authentication code below:
        </p>

        <!-- Code Box -->
        <div style="background-color: #fffaf0; border: 1px solid rgba(189, 127, 35, 0.3); border-radius: 14px; padding: 22px; text-align: center; margin: 24px 0;">
          <span style="font-size: 11px; font-weight: 700; letter-spacing: 0.16em; color: #956018; text-transform: uppercase; display: block; margin-bottom: 6px;">
            ONE-TIME CITIZEN VERIFICATION CODE
          </span>
          <span style="font-size: 38px; font-weight: 800; letter-spacing: 0.25em; color: #0d3035; font-family: monospace;">
            {code}
          </span>
          <span style="font-size: 11px; color: #8a7a58; display: block; margin-top: 8px;">
            Valid for 10 minutes · Do not share this code
          </span>
        </div>

        <p style="font-size: 13px; line-height: 1.6; color: #5f716e; margin: 24px 0 0 0;">
          Once verified, you will be able to file municipal complaints, attach photo/audio evidence, and receive transparent updates as engineering teams resolve your docket.
        </p>

        <div style="margin-top: 28px; padding-top: 20px; border-top: 1px solid rgba(23, 62, 66, 0.1); font-size: 11px; color: #8a9996; line-height: 1.5;">
          If you did not request this verification, you can safely disregard this email. Your citizen record is kept strictly confidential and is never displayed publicly.
        </div>
      </td>
    </tr>
    <!-- Footer -->
    <tr>
      <td style="background-color: #08272b; padding: 16px 32px; text-align: center; color: rgba(255, 255, 255, 0.5); font-size: 10px;">
        © 2026 Jan Aawaz (जनAawaz) Public Grievance & Infrastructure Portal
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_verification_email(to_email: str, code: str, title: str = "Verify your email address", greeting: str = "") -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print(f"[EmailService] Email delivery disabled: GMAIL_USER or GMAIL_APP_PASSWORD not set in environment.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Jan Aawaz (जनAawaz) Verification Code: {code}"
        msg["From"] = EMAIL_FROM or f"Jan Aawaz Portal <{GMAIL_USER}>"
        msg["To"] = to_email

        plain_text = f"Your Jan Aawaz (जनAawaz) citizen verification code is: {code}\nValid for 10 minutes."
        html_text = build_verification_html(code, to_email, title=title, greeting=greeting)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_text, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"[EmailService Error] Failed to send verification email to {to_email}: {e}")
        return False


def send_dispatch_email(to_email: str, subject: str, body_text: str) -> bool:
    """Send formal departmental dispatch or escalation notice."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print(f"[EmailService] Dispatch email skipped: SMTP credentials not set. Notice recorded in database.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM or f"Jan Aawaz Dispatch Office <{GMAIL_USER}>"
        msg["To"] = to_email

        html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f4ee; padding: 24px; color: #102a2f;">
  <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid rgba(23,62,66,0.15); overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
    <div style="background-color: #0d3035; padding: 20px 28px; color: #ffffff;">
      <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #e8b855;">Jan Aawaz (जनAawaz) Official Dispatch Notice</h2>
      <p style="margin: 4px 0 0 0; font-size: 11px; opacity: 0.8; letter-spacing: 0.1em; text-transform: uppercase;">MUNICIPAL INFRASTRUCTURE & CIVIC REDRESSAL</p>
    </div>
    <div style="padding: 28px; font-size: 13px; line-height: 1.7; color: #334e4c; white-space: pre-wrap;">
{body_text}
    </div>
    <div style="background-color: #08272b; padding: 14px 28px; text-align: center; color: rgba(255,255,255,0.4); font-size: 10px;">
      Sent to configured dispatch inbox · Jan Aawaz Autonomous Governance Infrastructure
    </div>
  </div>
</body>
</html>"""

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"[EmailService Error] Failed to send dispatch email to {to_email}: {e}")
        return False
