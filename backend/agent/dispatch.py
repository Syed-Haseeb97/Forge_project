"""Autonomous Dispatch Agent for Jan Aawaz.

Drafts formal bureaucratic complaint letters (in English + citizen's detected language)
and dispatches them to the configured dispatch inbox.
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
    """Draft formal dispatch letter and send to the configured dispatch inbox.
    
    Must never crash or slow down the caller.
    """
    to_email = os.getenv("DISPATCH_EMAIL", "dispatch@janaawaz.in")
    client = _get_client()
    models = _get_models()

    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Report).where(Report.id == report_id))
            report = res.scalar_one_or_none()
            if not report:
                logger.error(f"Dispatch agent: report {report_id} not found.")
                return None

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

            # Metadata formatting
            docket_id = report.docket_no or f"JA-2026-{str(report.id)[:8].upper()}"
            maps_link = (
                f"https://www.google.com/maps?q={report.latitude},{report.longitude}"
                if report.latitude and report.longitude
                else "Location coordinates not registered"
            )
            created_dt = report.created_at or datetime.utcnow()
            deadline_dt = created_dt + timedelta(hours=report.sla_hours or 72)
            deadline_str = deadline_dt.strftime("%Y-%m-%d %H:%M UTC")

            recipient_office = report.routed_to or "Municipal Engineering Division"
            if escalation_level == 1:
                recipient_office = f"Head of Department / Chief Engineer ({report.routed_to})"
            elif escalation_level == 2:
                recipient_office = "Office of the Municipal Commissioner"
            elif escalation_level >= 3:
                recipient_office = "Civic Oversight & Escalations Desk"

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
                    f"- Physical Locality: {report.locality or report.location}\n"
                    f"- Geographic Coordinates: {maps_link}\n"
                    f"- Evaluated Severity: {report.severity.upper()}\n"
                    f"- Target SLA Deadline: {deadline_str} ({report.sla_hours}h limit)\n"
                    f"- AI Triage Rationale: {report.severity_rationale or 'Evaluated via multi-signal civic triage'}\n"
                    f"- Citizen Evidence Media URL: {report.media_url or 'N/A'}\n"
                    f"- Dispatch Kind: {kind.upper()} (Escalation Level: {escalation_level})\n"
                    f"- Citizen Input Language: {language}\n"
                    f"{prev_dispatches_text}\n\n"
                    f"INSTRUCTIONS:\n"
                    f"1. Generate a formal subject line (e.g. '[URGENT WORK ORDER #{docket_id}] {report.title} - {report.locality}').\n"
                    f"2. Write a professional, assertive municipal dispatch letter in English citing the exact coordinates, Google Maps link, "
                    f"SLA deadline, hazard rationale, and evidence URL.\n"
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
                # Heuristic formal draft
                subject = f"[{'ESCALATION L' + str(escalation_level) if kind == 'escalation' else 'DISPATCH WORK ORDER'} #{docket_id}] {report.title}"
                body_eng = (
                    f"To: {recipient_office}\n"
                    f"From: Jan Aawaz Autonomous Civic Triage System\n"
                    f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"SUBJECT: Incident Work Order Transmission for Docket #{docket_id}\n\n"
                    f"Please be advised that an infrastructure failure requiring departmental redressal has been verified:\n"
                    f"- Title: {report.title}\n"
                    f"- Locality: {report.locality or report.location}\n"
                    f"- Location Coordinates: {maps_link}\n"
                    f"- Priority / Severity: {report.severity.upper()}\n"
                    f"- Target Resolution Deadline: {deadline_str}\n"
                    f"- Multi-Signal Triage Rationale: {report.severity_rationale or 'Direct citizen report'}\n"
                    f"- Photographic/Audio Evidence: {report.media_url or 'None attached'}\n\n"
                    f"You are formally requested to dispatch an engineering inspection crew to remediate the defect within the SLA window."
                )
                draft_res = DispatchDraft(subject=subject, body_english=body_eng, body_regional=None)

            # Assemble complete dispatch document
            full_body = (
                f"=== JAN AAWAZ DISPATCH NOTICE (PROTOTYPE) ===\n"
                f"Docket Reference: {docket_id}\n"
                f"Recipient Office: {recipient_office}\n"
                f"Locality: {report.locality or report.location}\n"
                f"Google Maps Link: {maps_link}\n"
                f"SLA Target Window: {deadline_str} ({report.sla_hours} hours)\n\n"
                f"{draft_res.body_english.strip()}"
            )
            if draft_res.body_regional:
                full_body += f"\n\n=== {language.upper()} REGIONAL COMPANION ===\n{draft_res.body_regional.strip()}"

            # Transmit via configured provider without blocking event loop
            sent = await asyncio.to_thread(
                send_dispatch_email,
                to_email,
                draft_res.subject,
                full_body,
            )

            # Persist in dispatches table
            dispatch_id = str(uuid.uuid4())
            dispatch_record = Dispatch(
                id=dispatch_id,
                report_id=report.id,
                kind=kind,
                to_email=to_email,
                subject=draft_res.subject,
                body=full_body,
                sent=sent,
                created_at=datetime.utcnow(),
            )
            session.add(dispatch_record)

            # Log timeline
            if kind == "initial":
                timeline_entry = ReportTimeline(
                    id=str(uuid.uuid4()),
                    report_id=report.id,
                    status=report.status.value if hasattr(report.status, "value") else str(report.status),
                    actor="Jan Aawaz Dispatch Agent",
                    action_type="dispatch_sent",
                    notes=f"Formal dispatch letter sent to configured dispatch inbox ({to_email}). Routed to {report.routed_to}.",
                    created_at=datetime.utcnow(),
                )
            else:
                timeline_entry = ReportTimeline(
                    id=str(uuid.uuid4()),
                    report_id=report.id,
                    status=report.status.value if hasattr(report.status, "value") else str(report.status),
                    actor="SLA Watchdog Agent",
                    action_type=f"escalation_level_{escalation_level}",
                    notes=f"Escalation Level {escalation_level} ({recipient_office}) notice dispatched to configured dispatch inbox ({to_email}).",
                    created_at=datetime.utcnow(),
                )
            session.add(timeline_entry)

            await session.commit()
            logger.info(f"Dispatch {dispatch_id} recorded for report {report_id} (kind={kind}, sent={sent}).")

            return {
                "id": dispatch_id,
                "report_id": report_id,
                "kind": kind,
                "to_email": to_email,
                "subject": draft_res.subject,
                "body": full_body,
                "sent": sent,
            }

    except Exception as e:
        logger.error(f"Dispatch agent error for report {report_id}: {e}", exc_info=True)
        return None
