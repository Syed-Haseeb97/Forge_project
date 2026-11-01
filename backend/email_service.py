import html
import os
import random
import smtplib
import logging
import httpx
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("janaawaz.email")

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp").lower().strip()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# Sender must come strictly from environment variables (EMAIL_FROM or GMAIL_USER)
EMAIL_FROM = os.getenv("EMAIL_FROM") or (f"Jan Aawaz Portal <{GMAIL_USER}>" if GMAIL_USER else "Jan Aawaz Portal <noreply@example.com>")


def is_email_configured() -> bool:
    """Return True if the selected email provider is fully configured with credentials."""
    provider = os.getenv("EMAIL_PROVIDER", "smtp").lower().strip()
    if provider == "resend":
        return bool(os.getenv("RESEND_API_KEY"))
    if provider == "brevo":
        return bool(os.getenv("BREVO_API_KEY"))
    return bool(os.getenv("GMAIL_USER") and os.getenv("GMAIL_APP_PASSWORD"))


# In-memory OTP storage: { normalized_email: { "code": str, "citizen_data": dict, "expires_at": datetime, "last_sent_at": datetime, "attempts": int } }
_otp_store: Dict[str, Dict[str, Any]] = {}


def check_rate_limit(email: str, min_interval_seconds: int = 30) -> Optional[int]:
    """Returns seconds remaining if an OTP was sent to this email within min_interval_seconds, else None."""
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
    <tr>
      <td style="background-color: #0d3035; padding: 18px 24px; text-align: center;">
        <div style="margin-bottom: 4px;">
          <span style="color: #e8b855; font-size: 24px; font-weight: 800;">जन</span><span style="color: #ffffff; font-size: 24px; font-weight: 800;">Aawaz</span>
        </div>
        <span style="color: rgba(255, 255, 255, 0.7); font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;">
          PUBLIC GRIEVANCE & INFRASTRUCTURE REDRESSAL PORTAL
        </span>
      </td>
    </tr>
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
          A citizen verification request was initiated for <strong style="color: #0d3035;">{email}</strong> on the <strong>Jan Aawaz (जनAawaz)</strong> Public Grievance Portal. Use your 6-digit authentication code below:
        </p>
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
    <tr>
      <td style="background-color: #08272b; padding: 16px 32px; text-align: center; color: rgba(255, 255, 255, 0.5); font-size: 10px;">
        © 2026 Jan Aawaz (जनAawaz) Public Grievance & Infrastructure Portal
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_via_resend(
    to_email: str,
    subject: str,
    plain_text: str,
    html_text: str,
    cc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send transactional email via Resend REST API."""
    if not RESEND_API_KEY:
        logger.warning("[EmailService] Resend delivery disabled: RESEND_API_KEY not configured.")
        return False

    sender = EMAIL_FROM or "Jan Aawaz Portal <onboarding@resend.dev>"
    payload: Dict[str, Any] = {
        "from": sender,
        "to": [to_email] if isinstance(to_email, str) else to_email,
        "subject": subject,
        "html": html_text,
        "text": plain_text,
    }
    if cc:
        payload["cc"] = [c.strip() for c in cc if c.strip()]
    if reply_to:
        payload["reply_to"] = reply_to.strip()

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code in (200, 201):
                return True
            logger.error(f"[EmailService Resend] API error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"[EmailService Resend Error] Failed to send email to {to_email}: {e}")
        return False


def _send_via_brevo(
    to_email: str,
    subject: str,
    plain_text: str,
    html_text: str,
    cc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send transactional email via Brevo (Sendinblue) v3 REST API."""
    if not BREVO_API_KEY:
        logger.warning("[EmailService] Brevo delivery disabled: BREVO_API_KEY not configured.")
        return False

    sender_email = os.getenv("BREVO_SENDER_EMAIL") or os.getenv("EMAIL_FROM_ADDR") or (GMAIL_USER if GMAIL_USER else "dispatch@janaawaz.in")
    sender_name = os.getenv("BREVO_SENDER_NAME") or "Jan Aawaz Portal"

    payload: Dict[str, Any] = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {"email": to_email}
        ],
        "subject": subject,
        "htmlContent": html_text,
        "textContent": plain_text,
    }
    if cc:
        payload["cc"] = [{"email": c.strip()} for c in cc if c.strip()]
    if reply_to:
        payload["replyTo"] = {"email": reply_to.strip()}

    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json",
                    "accept": "application/json",
                },
                json=payload,
            )
            if resp.status_code in (200, 201):
                logger.info(f"[EmailService Brevo] Successfully sent email to {to_email}")
                return True
            logger.error(f"[EmailService Brevo] API error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"[EmailService Brevo Error] Failed to send email to {to_email}: {e}")
        return False


def send_verification_email(to_email: str, code: str, title: str = "Verify your email address", greeting: str = "") -> bool:
    plain_text = f"Your Jan Aawaz (जनAawaz) citizen verification code is: {code}\nValid for 10 minutes."
    html_text = build_verification_html(code, to_email, title=title, greeting=greeting)
    subject = f"Jan Aawaz (जनAawaz) Verification Code: {code}"

    # Route according to EMAIL_PROVIDER
    if EMAIL_PROVIDER == "resend":
        return _send_via_resend(to_email, subject, plain_text, html_text)
    if EMAIL_PROVIDER == "brevo":
        return _send_via_brevo(to_email, subject, plain_text, html_text)

    # Default: SMTP
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.info("[EmailService] Email delivery disabled: GMAIL_USER or GMAIL_APP_PASSWORD not set in environment.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM or f"Jan Aawaz Portal <{GMAIL_USER}>"
        msg["To"] = to_email

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_text, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        logger.error(f"[EmailService Error] Failed to send verification email to {to_email}: {e}")
        return False


def send_dispatch_email(
    to_email: str,
    subject: str,
    body_text: str,
    cc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send formal departmental dispatch or escalation notice with CC and Reply-To support."""
    effective_reply_to = reply_to or os.getenv("REPLY_TO")
    clean_cc = [c.strip() for c in (cc or []) if c and c.strip()]

    escaped_body = html.escape(body_text)
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f4ee; padding: 24px; color: #102a2f;">
  <div style="max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid rgba(23,62,66,0.15); overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
    <div style="background-color: #0d3035; padding: 20px 28px; color: #ffffff;">
      <h2 style="margin: 0; font-size: 18px; font-weight: 700; color: #e8b855;">Jan Aawaz (जनAawaz) Prototype Dispatch Notice</h2>
      <p style="margin: 4px 0 0 0; font-size: 11px; opacity: 0.8; letter-spacing: 0.1em; text-transform: uppercase;">MUNICIPAL INFRASTRUCTURE & CIVIC REDRESSAL</p>
    </div>
    <div style="padding: 28px; font-size: 13px; line-height: 1.7; color: #334e4c; white-space: pre-wrap;">
{escaped_body}
    </div>
    <div style="background-color: #08272b; padding: 14px 28px; text-align: center; color: rgba(255,255,255,0.4); font-size: 10px;">
      Sent via Jan Aawaz Autonomous Civic Infrastructure · Hackathon prototype, not an official government service
    </div>
  </div>
</body>
</html>"""

    if EMAIL_PROVIDER == "resend":
        return _send_via_resend(to_email, subject, body_text, html_content, cc=clean_cc, reply_to=effective_reply_to)
    if EMAIL_PROVIDER == "brevo":
        return _send_via_brevo(to_email, subject, body_text, html_content, cc=clean_cc, reply_to=effective_reply_to)

    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.info("[EmailService] Dispatch email skipped: SMTP credentials not set. Notice recorded in database.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM or f"Jan Aawaz Dispatch Office <{GMAIL_USER}>"
        msg["To"] = to_email
        if clean_cc:
            msg["Cc"] = ", ".join(clean_cc)
        if effective_reply_to:
            msg["Reply-To"] = effective_reply_to.strip()

        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        destinations = [to_email] + clean_cc
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(msg["From"], destinations, msg.as_string())

        return True
    except Exception as e:
        logger.error(f"[EmailService Error] Failed to send dispatch email to {to_email}: {e}")
        return False


def send_tracking_email(
    to_email: str,
    docket_no: str,
    tracking_token: str,
    tracking_url: str,
) -> bool:
    """Send citizen confirmation email with docket number, tracking token, and tracking link. Never blocks caller."""
    if not to_email:
        return False

    subject = f"Jan Aawaz Grievance Registered #{docket_no} [Tracking Token]"
    plain_text = (
        f"Your civic grievance has been registered on Jan Aawaz (जनAawaz).\n\n"
        f"Docket Reference: #{docket_no}\n"
        f"Citizen Tracking Token: {tracking_token}\n"
        f"Public Live Tracking Link: {tracking_url}\n\n"
        f"Save your tracking code to monitor live SLA countdown, AI evaluation rationale, and departmental dispatch updates without exposing your personal information."
    )

    esc_docket = html.escape(docket_no)
    esc_token = html.escape(tracking_token)
    esc_url = html.escape(tracking_url)

    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f4ee; padding: 24px; color: #102a2f;">
  <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid rgba(23,62,66,0.15); overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05);">
    <div style="background-color: #0d3035; padding: 20px 28px; color: #ffffff; text-align: center;">
      <h2 style="margin: 0; font-size: 20px; font-weight: 700; color: #e8b855;">जनAawaz Civic Grievance Logged</h2>
      <p style="margin: 4px 0 0 0; font-size: 11px; opacity: 0.8; letter-spacing: 0.1em; text-transform: uppercase;">DOCKET CONFIRMATION & CITIZEN TRACKING TOKEN</p>
    </div>
    <div style="padding: 28px; font-size: 13px; line-height: 1.6; color: #334e4c;">
      <p style="margin-top: 0;">Your municipal infrastructure report has been registered and is undergoing autonomous multimodal triage.</p>
      
      <div style="background-color: #fffaf0; border: 1px solid rgba(189,127,35,0.3); border-radius: 12px; padding: 18px; margin: 20px 0; text-align: center;">
        <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #ba7c29;">OFFICIAL DOCKET NUMBER</div>
        <div style="font-size: 20px; font-weight: 800; color: #0d3035; font-family: monospace; margin: 4px 0 12px 0;">#{esc_docket}</div>
        
        <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: #347161;">CITIZEN TRACKING TOKEN</div>
        <div style="font-size: 24px; font-weight: 800; color: #2f7661; font-family: monospace; letter-spacing: 0.1em; margin: 4px 0;">{esc_token}</div>
        <div style="font-size: 11px; color: #70817e; margin-top: 6px;">Save this tracking code to verify live progress anytime.</div>
      </div>

      <div style="text-align: center; margin: 26px 0;">
        <a href="{esc_url}" style="display: inline-block; background-color: #0d3035; color: #e8b855; font-size: 12px; font-weight: 800; text-decoration: none; padding: 12px 24px; border-radius: 9999px; letter-spacing: 0.05em;">TRACK YOUR DOCKET LIVE →</a>
      </div>

      <p style="font-size: 11px; color: #718481; line-height: 1.5; border-top: 1px solid rgba(23,62,66,0.1); padding-top: 16px; margin-bottom: 0;">
        Privacy note: Your personal details remain confidential. The public tracking dashboard provides SLA countdowns and departmental work order audit records without showing your contact information.
      </p>
    </div>
  </div>
</body>
</html>"""

    reply_to = os.getenv("REPLY_TO")
    if EMAIL_PROVIDER == "resend":
        return _send_via_resend(to_email, subject, plain_text, html_content, reply_to=reply_to)
    if EMAIL_PROVIDER == "brevo":
        return _send_via_brevo(to_email, subject, plain_text, html_content, reply_to=reply_to)

    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        logger.info(f"[EmailService] Citizen tracking email skipped: SMTP not configured. Token is {tracking_token}.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM or f"Jan Aawaz Portal <{GMAIL_USER}>"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to.strip()

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=6) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"[EmailService] Failed sending tracking email to {to_email}: {e}")
        return False
