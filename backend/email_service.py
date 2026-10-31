import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

GMAIL_USER = os.getenv("GMAIL_USER", "syed424893@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "eeyi tjub jsvy yehk")
EMAIL_FROM = os.getenv("EMAIL_FROM", "Jan Aawaz Public Portal <syed424893@gmail.com>")

# In-memory OTP storage: { normalized_email: { "code": str, "citizen_data": dict, "expires_at": datetime, "attempts": int } }
_otp_store: Dict[str, Dict[str, Any]] = {}


def generate_and_store_otp(email: str, citizen_data: Optional[Dict[str, Any]] = None) -> str:
    normalized = email.strip().lower()
    code = f"{random.randint(100000, 999999)}"
    _otp_store[normalized] = {
        "code": code,
        "citizen_data": citizen_data or {},
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
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
        # Do not immediately pop so caller can read citizen_data if needed, or pop explicitly
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
  <title>CivicLine Citizen Verification</title>
</head>
<body style="margin: 0; padding: 32px 16px; background-color: #f6f4ee; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #102a2f;">
  <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 560px; background-color: #ffffff; border: 1px solid rgba(23, 62, 66, 0.12); border-radius: 20px; overflow: hidden; box-shadow: 0 16px 45px rgba(26, 53, 52, 0.08);">
    <!-- Official Top Strip -->
    <tr>
      <td style="background-color: #0d3035; padding: 12px 24px; text-align: center;">
        <span style="color: rgba(255, 255, 255, 0.85); font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;">
          AN OFFICIAL DIGITAL PUBLIC SERVICE
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
          A citizen verification request was initiated for <strong style="color: #0d3035;">{email}</strong> on the CivicLine Public Grievance Portal. Use the official 6-digit authentication code below:
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
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"जनAawaz Verification Code: {code}"
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email

        plain_text = f"Your Jan Aawaz (जनAawaz) citizen verification code is: {code}\nValid for 10 minutes."
        html_text = build_verification_html(code, to_email, title=title, greeting=greeting)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_text, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=12) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"[EmailService Error] Failed to send verification email to {to_email}: {e}")
        return False
