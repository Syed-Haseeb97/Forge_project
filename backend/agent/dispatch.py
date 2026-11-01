"""Autonomous Dispatch Agent for Jan Aawaz.

Resolves real municipal authority contacts, generates formal bureaucratic grievance letters
(English + citizen's detected language), and dispatches work orders via configured provider
with demo/live mode isolation and human-review safety gates.
"""
import os
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Report, Dispatch, ReportTimeline
from email_service import send_dispatch_email
from agent.directory import resolve_recipient, mask_email
from agent.schemas import DispatchDraft

logger = logging.getLogger("janaawaz.agent.dispatch")


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Dispatch agent could not init Gemini: {e}")
        return None


def _get_models() -> List[str]:
    raw = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


async def draft_and_send_dispatch(
    report_id: str,
    kind: str = "initial",
    escalation_level: int = 0,
) -> Optional[Dict[str, Any]]:
    """Draft formal dispatch letter and send to the resolved municipal office or fallback inbox.
    
    Adheres strictly to:
    - DISPATCH_MODE (demo vs live)
    - Safety gate: skips reports flagged with needs_human_review=True
    - Appends public ticket link {PUBLIC_APP_URL}/reports/{id} and Google Maps link
    - Records actual to/cc, recipient designation, and timeline notes
    """
    dispatch_mode = os.getenv("DISPATCH_MODE", "demo").lower().strip()
    fallback_inbox = os.getenv("DISPATCH_EMAIL", "dispatch@janaawaz.in")
    public_app_url = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
    reply_to = os.getenv("REPLY_TO")

    client = _get_client()
    models = _get_models()

    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Report).where(Report.id == report_id))
            report = res.scalar_one_or_none()
            if not report:
                logger.error(f"Dispatch agent: report {report_id} not found.")
                return None

            # Safety gate: Only dispatch reports that are not needs_human_review
            if getattr(report, "needs_human_review", False):
                logger.info(f"Report {report_id} flagged for human review (needs_human_review=True); skipping autonomous dispatch.")
                tl_gate = ReportTimeline(
                    id=str(uuid.uuid4()),
                    report_id=report.id,
                    status=report.status.value if hasattr(report.status, "value") else str(report.status),
                    actor="Jan Aawaz Dispatch Guard",
                    action_type="dispatch_held",
                    notes="Autonomous dispatch held: incident flagged for manual human verification before municipal transmission.",
                    created_at=datetime.utcnow(),
                )
                session.add(tl_gate)
                await session.commit()
                return None

            # 1. Resolve Recipient from Directory (no DB table)
            locality_str = report.locality or report.location or ""
            recip = resolve_recipient(
                category=report.category,
                locality_or_city=locality_str,
                escalation_level=escalation_level,
            )

            recipient_office = recip["designation"]
            is_matched = recip.get("matched", False)

            # Determine target TO and CC based on DISPATCH_MODE
            if dispatch_mode == "live":
                target_to = recip["to"]
                team_cc_raw = os.getenv("TEAM_CC_EMAILS", "")
                team_cc_list = [c.strip() for c in team_cc_raw.split(",") if c.strip()]
                target_cc = list(dict.fromkeys(recip.get("cc", []) + team_cc_list))
                is_demo = False
            else:
                # Demo mode: send ONLY to DISPATCH_EMAIL, label [DEMO]
                target_to = fallback_inbox
                target_cc = []
                is_demo = True

            # Fetch previous dispatches if escalating
            prev_dispatches_text = ""
            if kind == "escalation":
                d_res = await session.execute(
                    select(Dispatch).where(Dispatch.report_id == report_id).order_by(Dispatch.created_at.asc())
                )
                prev_d = d_res.scalars().all()
                if prev_d:
                    prev_dispatches_text = "\n\nPrevious Dispatches on this Docket:\n" + "\n".join(
                        [f"- [{d.created_at.strftime('%Y-%m-%d %H:%M')}] Kind: {d.kind}, Subject: {d.subject}" for d in prev_d]
                    )

            # Public links & coordinates
            docket_id = report.docket_no or f"JA-2026-{str(report.id)[:8].upper()}"
            public_ticket_link = f"{public_app_url}/reports/{report.id}"
            public_track_link = f"{public_app_url}/track/{report.tracking_token}" if getattr(report, "tracking_token", None) else public_ticket_link
            maps_link = (
                f"https://www.google.com/maps?q={report.latitude},{report.longitude}"
                if report.latitude and report.longitude
                else "Location coordinates not registered"
            )
            created_dt = report.created_at or datetime.utcnow()
            deadline_dt = created_dt + timedelta(hours=report.sla_hours or 72)
            deadline_str = deadline_dt.strftime("%Y-%m-%d %H:%M UTC")

            language = report.detected_language or "English"
            needs_regional = language.strip().lower() not in ["english", "en"]

            draft_res: Optional[DispatchDraft] = None

            if client:
                prompt = (
                    f"You are the Jan Aawaz Chief Dispatcher drafting a civic grievance transmission work order.\n"
                    f"Draft a formal complaint letter addressed to {recipient_office}.\n\n"
                    f"DOCKET DETAILS:\n"
                    f"- Docket Reference: {docket_id}\n"
                    f"- Issue Title: {report.title}\n"
                    f"- Category: {report.category}\n"
                    f"- Physical Locality: {locality_str}\n"
                    f"- Geographic Coordinates: {maps_link}\n"
                    f"- Public Ticket Dossier: {public_ticket_link}\n"
                    f"- Evaluated Severity: {report.severity.upper() if hasattr(report.severity, 'upper') else str(report.severity).upper()}\n"
                    f"- Target SLA Deadline: {deadline_str} ({report.sla_hours}h limit)\n"
                    f"- AI Triage Rationale: {report.severity_rationale or 'Evaluated via multi-signal civic triage'}\n"
                    f"- Citizen Evidence Media URL: {report.media_url or 'N/A'}\n"
                    f"- Dispatch Kind: {kind.upper()} (Escalation Level: {escalation_level})\n"
                    f"- Citizen Input Language: {language}\n"
                    f"{prev_dispatches_text}\n\n"
                    f"INSTRUCTIONS:\n"
                    f"1. Generate a formal subject line (e.g. '[URGENT WORK ORDER #{docket_id}] {report.title} - {locality_str}').\n"
                    f"2. Write a professional, assertive municipal dispatch letter in English citing the exact coordinates, Google Maps link, "
                    f"public ticket link ({public_ticket_link}), SLA deadline, hazard rationale, and evidence URL.\n"
                    f"3. {'Also write a full formal version in ' + language + ' in body_regional.' if needs_regional else 'Set body_regional to null.'}\n"
                )

                for model_name in models:
                    try:
                        resp = await asyncio.wait_for(
                            client.aio.models.generate_content(
                                model=model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    response_mime_type="application/json",
                                    response_schema=DispatchDraft,
                                ),
                            ),
                            timeout=12.0,
                        )
                        if resp.text:
                            draft_res = DispatchDraft.model_validate_json(resp.text)
                            break
                    except Exception as e:
                        logger.warning(f"Dispatch drafting failed on {model_name}: {e}")

            if not draft_res:
                # Deterministic fallback draft
                subject = f"[{'ESCALATION L' + str(escalation_level) if kind == 'escalation' else 'DISPATCH WORK ORDER'} #{docket_id}] {report.title}"
                body_eng = (
                    f"To: {recipient_office}\n"
                    f"From: Jan Aawaz Autonomous Civic Triage System\n"
                    f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"SUBJECT: Incident Work Order Transmission for Docket #{docket_id}\n\n"
                    f"Please be advised that an infrastructure failure requiring departmental redressal has been verified:\n"
                    f"- Title: {report.title}\n"
                    f"- Locality: {locality_str}\n"
                    f"- Location Coordinates: {maps_link}\n"
                    f"- Public Ticket Dossier: {public_ticket_link}\n"
                    f"- Priority / Severity: {report.severity.upper() if hasattr(report.severity, 'upper') else str(report.severity).upper()}\n"
                    f"- Target Resolution Deadline: {deadline_str}\n"
                    f"- Multi-Signal Triage Rationale: {report.severity_rationale or 'Direct citizen report'}\n"
                    f"- Photographic/Audio Evidence: {report.media_url or 'None attached'}\n\n"
                    f"You are formally requested to dispatch an engineering inspection crew to remediate the defect within the SLA window."
                )
                draft_res = DispatchDraft(subject=subject, body_english=body_eng, body_regional=None)

            # Apply [DEMO] tag if demo mode or demo recipient
            final_subject = draft_res.subject
            if is_demo or dispatch_mode == "demo":
                if not final_subject.startswith("[DEMO]"):
                    final_subject = f"[DEMO] {final_subject}"

            # Assemble complete dispatch document with public links and hackathon prototype disclaimer
            full_body = (
                f"=== JAN AAWAZ MUNICIPAL WORK ORDER DISPATCH NOTICE ===\n"
                f"Docket Reference: {docket_id}\n"
                f"Recipient Office: {recipient_office}\n"
                f"Locality: {locality_str}\n"
                f"Public Ticket Link: {public_ticket_link}\n"
                f"Citizen Tracking Link: {public_track_link}\n"
                f"Google Maps Link: {maps_link}\n"
                f"SLA Target Window: {deadline_str} ({report.sla_hours} hours)\n"
                f"Notice: Hackathon prototype, not an official government service\n\n"
                f"{draft_res.body_english.strip()}"
            )
            if draft_res.body_regional:
                full_body += f"\n\n=== {language.upper()} REGIONAL COMPANION ===\n{draft_res.body_regional.strip()}"

            # Transmit via configured email provider without blocking event loop
            sent = await asyncio.to_thread(
                send_dispatch_email,
                to_email=target_to,
                subject=final_subject,
                body_text=full_body,
                cc=target_cc,
                reply_to=reply_to,
            )

            # Persist in dispatches table (including cc_emails and recipient_office)
            dispatch_id = str(uuid.uuid4())
            dispatch_record = Dispatch(
                id=dispatch_id,
                report_id=report.id,
                kind=kind,
                to_email=target_to,
                cc_emails=",".join(target_cc) if target_cc else None,
                recipient_office=recipient_office,
                subject=final_subject,
                body=full_body,
                sent=sent,
                created_at=datetime.utcnow(),
            )
            session.add(dispatch_record)

            # Determine timeline audit note
            if is_matched:
                masked_addr = mask_email(recip["to"])
                if dispatch_mode == "demo":
                    timeline_notes = f"Sent to {recipient_office} ({masked_addr}) [Demo mode: routed to {target_to}]."
                else:
                    cc_str = f" CC: {', '.join(mask_email(c) for c in target_cc)}" if target_cc else ""
                    timeline_notes = f"Sent to {recipient_office} ({masked_addr}).{cc_str}"
            else:
                timeline_notes = f"no matching department, sent to fallback inbox ({target_to})."

            action_type_val = "dispatch_sent" if kind == "initial" else f"escalation_level_{escalation_level}"
            actor_name = "Jan Aawaz Dispatch Agent" if kind == "initial" else "SLA Watchdog Agent"

            timeline_entry = ReportTimeline(
                id=str(uuid.uuid4()),
                report_id=report.id,
                status=report.status.value if hasattr(report.status, "value") else str(report.status),
                actor=actor_name,
                action_type=action_type_val,
                notes=timeline_notes,
                created_at=datetime.utcnow(),
            )
            session.add(timeline_entry)

            await session.commit()
            logger.info(
                f"Dispatch {dispatch_id} recorded for report {report_id} "
                f"(mode={dispatch_mode}, to={target_to}, cc={target_cc}, sent={sent})."
            )

            return {
                "id": dispatch_id,
                "report_id": report_id,
                "kind": kind,
                "to_email": target_to,
                "cc_emails": target_cc,
                "recipient_office": recipient_office,
                "subject": final_subject,
                "body": full_body,
                "sent": sent,
            }

    except Exception as e:
        logger.error(f"Dispatch agent error for report {report_id}: {e}", exc_info=True)
        return None
