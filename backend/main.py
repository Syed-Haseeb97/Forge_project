"""
Jan Aawaz (जनAawaz) – Autonomous Civic Grievance & Infrastructure Redressal System
Backend: FastAPI + SQLite + Gemini API + Open311 GeoReport v2
"""
import os
import json
import math
import time
import uuid
import csv
import io
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from database import engine, AsyncSessionLocal, Base
from models import Report, ReportTimeline, Citizen, Dispatch, Explanation, Upvote, StatusEnum, SeverityEnum
from gemini_service import analyze_report, ROUTING_MAP
from storage_service import save_media, UPLOAD_DIR, get_storage_mode
from agent.dispatch import draft_and_send_dispatch
from agent.watchdog import (
    start_watchdog_background_task,
    stop_watchdog_background_task,
    run_watchdog_check,
    get_sla_time_scale,
    is_watchdog_running,
)
from agent.verification import verify_repair_evidence
from agent.explainer import generate_plain_language_explanation
from agent.insights import generate_civic_insights
from agent.schemas import ExplanationOut
from agent.tokens import generate_tracking_token
from email_service import send_tracking_email
from email_service import (
    generate_and_store_otp,
    verify_otp_code,
    pop_otp,
    get_stored_otp_data,
    send_verification_email,
    check_rate_limit,
    is_email_configured,
)
from auth import (
    get_current_user,
    get_optional_current_user,
    require_authority,
    create_access_token,
    get_role_for_email,
)
from migrations import ensure_schema
from sqlalchemy import select, text, func

logger = logging.getLogger("janaawaz")

load_dotenv()

DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")

# In-memory per-IP rate limiting: ip -> List[timestamp]
_IP_RATE_LIMITS: Dict[str, List[float]] = {}
_IP_RATE_LIMIT_LOCK = asyncio.Lock()


async def check_ip_rate_limit(request: Request, limit: int = 30, window_secs: float = 60.0):
    client_ip = request.client.host if request and request.client else "unknown"
    now = time.time()
    async with _IP_RATE_LIMIT_LOCK:
        times = _IP_RATE_LIMITS.setdefault(client_ip, [])
        times = [t for t in times if now - t < window_secs]
        if len(times) >= limit:
            _IP_RATE_LIMITS[client_ip] = times
            raise HTTPException(
                status_code=429,
                detail=f"Too Many Requests: rate limit of {limit} requests/min exceeded. Please slow down.",
            )
        times.append(now)
        _IP_RATE_LIMITS[client_ip] = times

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Jan Aawaz (जनAawaz) API",
    version="2.0.0",
    description="Transparent Civic Grievance & Infrastructure Triage System with Gemini Multimodal AI and Open311 compliance.",
)

cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
allow_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]
allow_credentials = "*" not in allow_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*" not in allow_origins else None,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
async def startup():
    await ensure_schema()
    await sweep_stale_triaging_reports()
    start_watchdog_background_task()


@app.on_event("shutdown")
async def shutdown():
    stop_watchdog_background_task()


@app.get("/api/health")
async def health_check():
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "app": "Jan Aawaz (जनAawaz)",
        "version": "2.0.0",
        "database": db_status,
        "storage_mode": get_storage_mode(),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "email_configured": is_email_configured(),
        "watchdog_running": is_watchdog_running(),
        "sla_time_scale": get_sla_time_scale(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────
class ReportOut(BaseModel):
    id: str
    docket_no: Optional[str] = None
    tracking_token: Optional[str] = None
    title: str
    description: str
    category: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    severity: str
    status: str
    ai_analysis: Optional[str]
    action_plan: Optional[str]
    safety_precautions: Optional[str]
    sla_hours: Optional[int]
    routed_to: Optional[str]
    upvotes: int
    media_url: Optional[str]
    resolved_media_url: Optional[str]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    agent_trace: Optional[str] = None
    confidence: Optional[float] = None
    severity_rationale: Optional[str] = None
    detected_language: Optional[str] = None
    locality: Optional[str] = None
    escalation_level: Optional[int] = 0
    is_overdue: Optional[bool] = False
    demo_accel: Optional[bool] = False
    triage_status: Optional[str] = "done"
    needs_human_review: Optional[bool] = False
    resolution_verdict: Optional[str] = None
    resolution_confidence: Optional[float] = None
    resolution_explanation: Optional[str] = None
    citizen_feedback: Optional[str] = None
    feedback_notes: Optional[str] = None
    authenticity: Optional[str] = "unchecked"
    authenticity_reason: Optional[str] = None
    authenticity_confidence: Optional[float] = None
    appeal_submitted: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReportTraceOut(BaseModel):
    report_id: str
    docket_no: Optional[str] = None
    triage_status: str
    severity: str
    routed_to: Optional[str] = None
    sla_hours: Optional[int] = None
    agent_trace: List[Dict[str, Any]] = []
    is_complete: bool
    needs_human_review: bool = False


class DispatchOut(BaseModel):
    id: str
    report_id: str
    kind: str
    to_email: str
    cc_emails: Optional[str] = None
    recipient_office: Optional[str] = None
    subject: str
    body: str
    sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PublicTrackingOut(BaseModel):
    docket_no: str
    tracking_token: str
    title: str
    description: str
    category: str
    locality: str
    severity: str
    status: str
    sla_hours: int
    sla_deadline: str
    sla_remaining_hours: float
    sla_countdown: str
    escalation_level: int
    is_overdue: bool
    timeline: List[Dict[str, Any]] = []
    dispatch_info: Optional[Dict[str, Any]] = None
    media_url: Optional[str] = None
    resolved_media_url: Optional[str] = None
    authenticity: Optional[str] = "unchecked"
    authenticity_reason: Optional[str] = None
    status_text: Optional[str] = None
    created_at: str
    updated_at: str


class FeedbackRequest(BaseModel):
    feedback: str  # "confirmed" | "disputed"
    notes: Optional[str] = None


class TimelineOut(BaseModel):
    id: str
    report_id: str
    status: str
    actor: str
    action_type: str
    notes: Optional[str]
    media_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NearbyReportOut(ReportOut):
    distance_km: float
    likely_duplicate: bool = False
    duplicate_reason: Optional[str] = None


class ScoreBreakdown(BaseModel):
    severity_pts: int
    sla_pts: int
    upvote_pts: int
    hotspot_pts: int
    rain_pts: int
    total: int


class QueueItemOut(BaseModel):
    id: str
    docket_no: Optional[str] = None
    title: str
    category: str
    location: str
    severity: str
    status: str
    created_at: datetime
    sla_hours: Optional[int] = 72
    sla_remaining_hours: float
    is_overdue: bool
    upvotes: int
    score: int
    score_breakdown: ScoreBreakdown
    why_now: Optional[str] = None
    media_url: Optional[str] = None
    authenticity: Optional[str] = "unchecked"
    authenticity_reason: Optional[str] = None


class CrewBatchOut(BaseModel):
    batch_id: str
    center_location: str
    category: str
    ticket_count: int
    dockets: List[str]
    report_ids: List[str]


class AuthorityQueueOut(BaseModel):
    total_queued: int
    items: List[QueueItemOut]
    crew_batches: List[CrewBatchOut]
    held_items: List[ReportOut] = []


class StatsOut(BaseModel):
    total: int
    open: int
    in_progress: int
    resolved: int
    closed: int
    critical: int
    high: int
    medium: int
    low: int
    critical_active: int
    avg_resolution_hours: float
    sla_compliance_rate: float
    sla_time_scale: float = 1.0
    overdue: int = 0
    by_category: Dict[str, int]
    by_department: Dict[str, int]


# ── Distance Helper ────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def log_timeline(
    session,
    report_id: str,
    status: str,
    actor: str,
    action_type: str,
    notes: Optional[str] = None,
    media_url: Optional[str] = None,
):
    entry = ReportTimeline(
        id=str(uuid.uuid4()),
        report_id=report_id,
        status=status,
        actor=actor,
        action_type=action_type,
        notes=notes,
        media_url=media_url,
        created_at=datetime.utcnow(),
    )
    session.add(entry)


class CitizenOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    dob: str
    phone: Optional[str] = None
    aadhaar_last4: Optional[str] = None
    address: str
    is_verified: bool
    role: str = "citizen"
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterSendCodeRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    dob: str
    phone: Optional[str] = None
    address: str
    aadhaar_last4: Optional[str] = None


class RegisterVerifyCodeRequest(BaseModel):
    email: str
    code: str
    registration_data: Optional[Dict[str, Any]] = None


class LoginSendCodeRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    code: str


# ── Citizen Authentication Routes ──────────────────────────────────────────────
@app.post("/api/auth/register-send-code")
async def register_send_code(payload: RegisterSendCodeRequest):
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    # Rate limiting: 1 request per 30 seconds per email
    remaining = check_rate_limit(email, 30)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {remaining} seconds before requesting a new code.",
        )

    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First name and last name are required.")

    dob = payload.dob.strip()
    if not dob:
        raise HTTPException(status_code=400, detail="Date of birth is required.")

    address = payload.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Primary residence address is required.")

    phone_val = None
    if payload.phone and payload.phone.strip():
        raw_digits = "".join(filter(str.isdigit, payload.phone))
        if len(raw_digits) == 12 and raw_digits.startswith("91"):
            raw_digits = raw_digits[2:]
        if len(raw_digits) == 10:
            phone_val = f"+91 {raw_digits}"
        else:
            raise HTTPException(status_code=400, detail="Indian mobile number must be exactly 10 digits under +91.")

    # Check if citizen already registered
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Citizen).where(Citizen.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="An account with this email is already registered. Please sign in instead.",
            )

    citizen_dict = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "dob": dob,
        "phone": phone_val,
        "address": address,
    }

    code = generate_and_store_otp(email, citizen_dict)

    sent = await asyncio.to_thread(
        send_verification_email,
        email,
        code,
        "Citizen Registration Verification",
        first_name,
    )

    resp: Dict[str, Any] = {
        "ok": True,
        "message": "Verification code sent to your email inbox! (Please check your Spam/Junk folder if not in Inbox)",
    }
    if DEV_MODE:
        resp["dev_code"] = code

    return resp


@app.post("/api/auth/register-verify-code")
async def register_verify_code(payload: RegisterVerifyCodeRequest):
    email = payload.email.strip().lower()
    if not verify_otp_code(email, payload.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new code.",
        )

    stored = get_stored_otp_data(email)
    citizen_info = payload.registration_data or (stored.get("citizen_data") if stored else None)
    if not citizen_info:
        raise HTTPException(
            status_code=400,
            detail="Registration session expired. Please re-submit your registration form.",
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Citizen).where(Citizen.email == email))
        citizen = result.scalar_one_or_none()
        if not citizen:
            raw_phone = citizen_info.get("phone")
            final_phone = None
            if raw_phone:
                digits = "".join(filter(str.isdigit, str(raw_phone)))
                if len(digits) == 12 and digits.startswith("91"):
                    digits = digits[2:]
                final_phone = f"+91 {digits}" if len(digits) == 10 else str(raw_phone)

            citizen = Citizen(
                id=str(uuid.uuid4()),
                first_name=citizen_info["first_name"],
                last_name=citizen_info["last_name"],
                email=email,
                dob=citizen_info["dob"],
                phone=final_phone,
                aadhaar_last4=None,
                address=citizen_info["address"],
                is_verified=True,
            )
            session.add(citizen)
            await session.commit()
            await session.refresh(citizen)

    pop_otp(email)
    role = get_role_for_email(email)
    token = create_access_token(email=email, user_id=citizen.id, role=role)

    return {
        "ok": True,
        "token": token,
        "user": {
            "id": citizen.id,
            "first_name": citizen.first_name,
            "last_name": citizen.last_name,
            "email": citizen.email,
            "dob": citizen.dob,
            "phone": citizen.phone,
            "address": citizen.address,
            "verified": True,
            "role": role,
        },
    }


@app.post("/api/auth/login-send-code")
async def login_send_code(payload: LoginSendCodeRequest):
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    # Rate limiting: 1 request per 30 seconds per email
    remaining = check_rate_limit(email, 30)
    if remaining:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {remaining} seconds before requesting a new code.",
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Citizen).where(Citizen.email == email))
        citizen = result.scalar_one_or_none()
        if not citizen:
            raise HTTPException(
                status_code=404,
                detail="This email is not registered. Want to create an account?",
            )

    code = generate_and_store_otp(email, {"citizen_id": citizen.id})

    sent = await asyncio.to_thread(
        send_verification_email,
        email,
        code,
        "Citizen Sign-In Verification",
        citizen.first_name,
    )

    resp: Dict[str, Any] = {
        "ok": True,
        "message": "Verification code sent to your email inbox! (Please check your Spam/Junk folder if not in Inbox)",
    }
    if DEV_MODE:
        resp["dev_code"] = code

    return resp


@app.post("/api/auth/verify-code")
async def verify_auth_code(payload: VerifyOtpRequest):
    email = payload.email.strip().lower()
    if not verify_otp_code(email, payload.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new code.",
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Citizen).where(Citizen.email == email))
        citizen = result.scalar_one_or_none()

    pop_otp(email)
    role = get_role_for_email(email)
    user_id = citizen.id if citizen else None
    token = create_access_token(email=email, user_id=user_id, role=role)

    if citizen:
        user_data = {
            "id": citizen.id,
            "first_name": citizen.first_name,
            "last_name": citizen.last_name,
            "email": citizen.email,
            "dob": citizen.dob,
            "phone": citizen.phone,
            "address": citizen.address,
            "verified": True,
            "role": role,
        }
    else:
        user_data = {
            "email": email,
            "verified": True,
            "role": role,
        }

    return {
        "ok": True,
        "token": token,
        "user": user_data,
    }


# Backwards compatibility alias
@app.post("/api/auth/send-code")
async def send_auth_code(payload: LoginSendCodeRequest):
    return await login_send_code(payload)


def _apply_triage_fallback(
    rep: Report,
    title: Optional[str] = None,
    category: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    from agent.pipeline import _fallback_triage_result
    cat_val = category or (rep.category.value if hasattr(rep.category, "value") else str(rep.category or "other"))
    fb = _fallback_triage_result(
        title=title or rep.title or "Civic Incident",
        category=cat_val,
        description=description or rep.description or "",
        location=location or rep.location or "Reported Location",
        latitude=rep.latitude,
        longitude=rep.longitude,
    )
    rep.severity = SeverityEnum(fb["severity"])
    rep.routed_to = fb["routed_to"]
    rep.action_plan = fb["action_plan"]
    rep.safety_precautions = fb["safety_precautions"]
    rep.sla_hours = fb["sla_hours"]
    rep.ai_analysis = fb["ai_analysis"]
    rep.confidence = fb["confidence"]
    rep.severity_rationale = fb["severity_rationale"]
    rep.detected_language = rep.detected_language or fb.get("detected_language", "English")
    rep.locality = rep.locality or location or rep.location
    rep.triage_status = "done"

    trace_list = []
    if rep.agent_trace:
        try:
            trace_list = json.loads(rep.agent_trace)
        except Exception:
            trace_list = []

    trace_list.append({
        "step": "fallback_recovery",
        "tool": "heuristic_fallback_agent",
        "status": "fallback",
        "duration_ms": 50,
        "summary": "Heuristic fallback applied: severity, department routing, and SLA established",
        "data": {
            "severity": fb["severity"],
            "department": fb["routed_to"],
            "sla_hours": fb["sla_hours"],
            "rationale": fb["severity_rationale"],
        },
    })
    rep.agent_trace = json.dumps(trace_list)
    return fb


async def sweep_stale_triaging_reports():
    """Sweeps reports stuck in 'triaging' older than 3 minutes, applying heuristic fallback."""
    cutoff = datetime.utcnow() - timedelta(minutes=3)
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(
                select(Report).where(
                    Report.triage_status == "triaging",
                    Report.created_at < cutoff,
                )
            )
            stale_reports = res.scalars().all()
            if not stale_reports:
                return

            logger.info(f"Sweeping {len(stale_reports)} stale triaging reports older than 3 minutes...")
            for rep in stale_reports:
                fb = _apply_triage_fallback(rep)
                await log_timeline(
                    session=session,
                    report_id=rep.id,
                    status=StatusEnum.open.value,
                    actor="Jan Aawaz Startup Sweeper",
                    action_type="ai_triage",
                    notes=f"Stale triage recovery: assessed via fallback as {fb['severity'].upper()} priority ({rep.sla_hours}h SLA). Routed to {rep.routed_to}.",
                )
            await session.commit()

            # Trigger initial dispatch for swept tickets in background tasks
            for rep in stale_reports:
                try:
                    asyncio.create_task(draft_and_send_dispatch(rep.id, "initial"))
                except Exception as e:
                    logger.warning(f"Error scheduling dispatch for swept ticket {rep.id}: {e}")
    except Exception as e:
        logger.error(f"Error during startup triage sweeper: {e}", exc_info=True)


# ── Background Pipeline Task ──────────────────────────────────────────────────
async def run_background_triage(
    report_id: str,
    title: str,
    description: str,
    category: str,
    location: str,
    latitude: Optional[float],
    longitude: Optional[float],
    media_bytes: Optional[bytes],
    media_mime: Optional[str],
):
    """Executes the multi-signal AI triage pipeline in background, streaming trace steps to DB."""
    try:
        async def on_step(step_data: Dict[str, Any]):
            try:
                async with AsyncSessionLocal() as s:
                    rep = await s.get(Report, report_id)
                    if rep:
                        trace_list = json.loads(rep.agent_trace) if rep.agent_trace else []
                        trace_list.append(step_data)
                        rep.agent_trace = json.dumps(trace_list)
                        if step_data.get("step") == "decide":
                            dec_data = step_data.get("data", {})
                            if dec_data.get("final_severity"):
                                rep.severity = SeverityEnum(dec_data["final_severity"])
                            if dec_data.get("department"):
                                rep.routed_to = dec_data["department"]
                            if dec_data.get("sla_hours"):
                                rep.sla_hours = dec_data["sla_hours"]
                        if step_data.get("step") == "critic_audit":
                            crit_data = step_data.get("data", {})
                            if not crit_data.get("agrees", True):
                                rep.needs_human_review = True
                        await s.commit()
            except Exception as e:
                logger.warning(f"Error persisting live trace step for {report_id}: {e}")

        async with AsyncSessionLocal() as session:
            analysis_res = await analyze_report(
                title=title,
                description=description,
                category=category,
                location=location,
                latitude=latitude,
                longitude=longitude,
                media_bytes=media_bytes,
                media_mime=media_mime,
                db_session=session,
                on_step=on_step,
            )

        async with AsyncSessionLocal() as session:
            rep = await session.get(Report, report_id)
            if rep:
                severity_str = analysis_res.get("severity", "medium")
                rep.severity = SeverityEnum(severity_str)
                rep.routed_to = analysis_res.get("routed_to") or ROUTING_MAP.get(category, ROUTING_MAP["other"])
                rep.action_plan = analysis_res.get("action_plan")
                rep.safety_precautions = analysis_res.get("safety_precautions")
                rep.sla_hours = analysis_res.get("sla_hours", 72)
                rep.ai_analysis = analysis_res.get("ai_analysis")
                rep.confidence = analysis_res.get("confidence")
                rep.severity_rationale = analysis_res.get("severity_rationale")
                rep.detected_language = analysis_res.get("detected_language")
                rep.locality = analysis_res.get("locality") or location
                
                rep.authenticity = analysis_res.get("authenticity", "unchecked")
                rep.authenticity_reason = analysis_res.get("authenticity_reason")
                rep.authenticity_confidence = analysis_res.get("authenticity_confidence")

                if rep.authenticity == "suspicious" or analysis_res.get("needs_human_review"):
                    rep.needs_human_review = True

                agent_trace_data = analysis_res.get("agent_trace")
                rep.agent_trace = json.dumps(agent_trace_data) if agent_trace_data else "[]"
                rep.triage_status = "done"

                if analysis_res.get("timeline_note"):
                    await log_timeline(
                        session=session,
                        report_id=report_id,
                        status=StatusEnum.open.value,
                        actor="Jan Aawaz Authenticity Gate",
                        action_type="held_for_review",
                        notes=analysis_res["timeline_note"],
                    )
                else:
                    await log_timeline(
                        session=session,
                        report_id=report_id,
                        status=StatusEnum.open.value,
                        actor="Jan Aawaz AI Triage",
                        action_type="ai_triage",
                        notes=f"Assessed as {severity_str.upper()} priority ({rep.sla_hours}h SLA). Routed to {rep.routed_to}. Rationale: {rep.severity_rationale or 'Evaluated based on multi-signal evidence'}",
                    )
                await session.commit()

        # Phase M: dispatch gate: only genuine or (unchecked and demo mode)
        async with AsyncSessionLocal() as session:
            r_cur = await session.get(Report, report_id)
            cur_auth = getattr(r_cur, "authenticity", "unchecked") if r_cur else "unchecked"
            cur_rev = getattr(r_cur, "needs_human_review", False) if r_cur else False

        disp_mode = os.getenv("DISPATCH_MODE", "demo").lower()
        if (cur_auth == "genuine" or (cur_auth == "unchecked" and disp_mode == "demo")) and not cur_rev:
            try:
                await draft_and_send_dispatch(report_id, "initial")
            except Exception as e:
                logger.warning(f"Error sending dispatch for {report_id}: {e}")

    except Exception as e:
        logger.error(f"Background triage failed for {report_id}: {e}", exc_info=True)
        try:
            async with AsyncSessionLocal() as session:
                rep = await session.get(Report, report_id)
                if rep:
                    fb = _apply_triage_fallback(
                        rep=rep,
                        title=title,
                        category=category,
                        description=description,
                        location=location,
                    )
                    await log_timeline(
                        session=session,
                        report_id=report_id,
                        status=StatusEnum.open.value,
                        actor="Jan Aawaz AI Fallback",
                        action_type="ai_triage",
                        notes=f"Assessed via fallback as {fb['severity'].upper()} priority ({rep.sla_hours}h SLA). Routed to {rep.routed_to}.",
                    )
                    await session.commit()

            # Continue to dispatch even on failure
            try:
                await draft_and_send_dispatch(report_id, "initial")
            except Exception as disp_err:
                logger.warning(f"Error sending dispatch after fallback for {report_id}: {disp_err}")
        except Exception:
            pass


# ── Core Routes ────────────────────────────────────────────────────────────────
@app.post("/api/reports", response_model=ReportOut)
async def submit_report(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    citizen_email: Optional[str] = Form(None),
    media: Optional[UploadFile] = File(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    # Derive citizen_email from authenticated JWT token; ignore the form field
    actual_citizen_email = current_user.get("sub")
    citizen_id = current_user.get("user_id")

    report_id = str(uuid.uuid4())
    media_url = None
    content = None

    # Save uploaded media (Supabase storage or local disk)
    if media and media.filename:
        content = await media.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "File size exceeds maximum allowed limit (10 MB)")
        ext = Path(media.filename).suffix or ".jpg"
        filename = f"{report_id}{ext}"
        media_url = await save_media(filename, content, media.content_type)

    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        if not citizen_id and actual_citizen_email:
            res = await session.execute(select(Citizen).where(Citizen.email == actual_citizen_email.strip().lower()))
            cit = res.scalar_one_or_none()
            if cit:
                citizen_id = cit.id

        # Phase M: Abuse limit check - if same citizen has >=3 spam verdicts in 24h, return 429
        from sqlalchemy import and_, func
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        spam_filters = [Report.authenticity == "spam", Report.created_at >= cutoff_24h]
        if citizen_id:
            spam_filters.append(Report.citizen_id == citizen_id)
        elif actual_citizen_email:
            spam_filters.append(Report.citizen_email == actual_citizen_email.strip().lower())
        
        spam_count_res = await session.execute(select(func.count(Report.id)).where(and_(*spam_filters)))
        spam_count = spam_count_res.scalar() or 0
        if spam_count >= 3:
            raise HTTPException(
                status_code=429,
                detail="Submission limit reached. You have 3 complaints flagged as non-civic/spam in the last 24 hours. Submissions temporarily restricted.",
            )

        from sqlalchemy.exc import IntegrityError

        max_docket_retries = 3
        for attempt in range(max_docket_retries):
            try:
                # Determine sequential docket_no (JA-2026-00001)
                docket_stmt = select(Report.docket_no).where(Report.docket_no.like("JA-2026-%"))
                all_dockets = (await session.execute(docket_stmt)).scalars().all()
                max_seq = 0
                for d in all_dockets:
                    if d:
                        part = d.split("-")[-1]
                        if part.isdigit():
                            num = int(part)
                            if num > max_seq:
                                max_seq = num
                docket_no = f"JA-2026-{max_seq + 1 + attempt:05d}"
                tracking_token = generate_tracking_token()

                is_demo_accel = DEV_MODE or (get_sla_time_scale() > 1.0)
                default_dept = ROUTING_MAP.get(category, ROUTING_MAP["other"])

                report = Report(
                    id=report_id,
                    docket_no=docket_no,
                    tracking_token=tracking_token,
                    citizen_id=citizen_id,
                    citizen_email=actual_citizen_email.strip().lower() if actual_citizen_email else None,
                    title=title,
                    description=description,
                    category=category,
                    location=location,
                    latitude=latitude,
                    longitude=longitude,
                    severity=SeverityEnum.medium,
                    status=StatusEnum.open,
                    triage_status="triaging",
                    needs_human_review=False,
                    ai_analysis="Autonomous AI multi-signal triage pipeline is analyzing evidence, GIS layers, weather, and recurrence...",
                    action_plan=None,
                    safety_precautions=None,
                    sla_hours=72,
                    routed_to=default_dept,
                    upvotes=0,
                    media_url=media_url,
                    agent_trace="[]",
                    confidence=None,
                    severity_rationale=None,
                    detected_language="English",
                    locality=location,
                    demo_accel=is_demo_accel,
                    created_at=now,
                    updated_at=now,
                )
                session.add(report)

                # Log initial timeline event
                await log_timeline(
                    session=session,
                    report_id=report_id,
                    status=StatusEnum.open.value,
                    actor="Citizen Reporter",
                    action_type="submitted",
                    notes=f"Civic grievance registered at {location}. Initializing agentic triage pipeline.",
                    media_url=media_url,
                )

                await session.commit()
                await session.refresh(report)
                break
            except IntegrityError as ie:
                await session.rollback()
                logger.warning(f"IntegrityError on docket insertion (attempt {attempt + 1}/{max_docket_retries}): {ie}")
                if attempt == max_docket_retries - 1:
                    raise

        # Send citizen confirmation email with tracking token and direct tracking link
        if actual_citizen_email:
            public_app_url = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
            track_url = f"{public_app_url}/track/{tracking_token}"
            background_tasks.add_task(
                send_tracking_email,
                to_email=actual_citizen_email.strip().lower(),
                docket_no=docket_no,
                tracking_token=tracking_token,
                tracking_url=track_url,
            )

        # Enqueue background triage pipeline
        background_tasks.add_task(
            run_background_triage,
            report_id,
            title,
            description,
            category,
            location,
            latitude,
            longitude,
            content,
            media.content_type if media else None,
        )

        return report


@app.get("/api/reports/{report_id}/trace", response_model=ReportTraceOut)
async def get_report_trace(report_id: str):
    """Public endpoint to poll live agent trace steps as they stream in."""
    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_id)
        if not report:
            res = await session.execute(select(Report).where(Report.docket_no == report_id))
            report = res.scalar_one_or_none()
            if not report:
                raise HTTPException(404, "Report not found")

        trace_data = []
        if report.agent_trace:
            try:
                trace_data = json.loads(report.agent_trace)
            except Exception:
                trace_data = []

        sev_str = report.severity.value if hasattr(report.severity, "value") else str(report.severity)
        return ReportTraceOut(
            report_id=report.id,
            docket_no=report.docket_no,
            triage_status=report.triage_status or "done",
            severity=sev_str,
            routed_to=report.routed_to,
            sla_hours=report.sla_hours,
            agent_trace=trace_data,
            is_complete=(report.triage_status in ["done", "failed"]),
            needs_human_review=bool(report.needs_human_review),
        )


@app.post("/api/ai/prefill")
async def ai_prefill(
    request: Request,
    media: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Analyze attached photo/audio/notes and return suggested title, category, description, and language."""
    await check_ip_rate_limit(request, limit=20, window_secs=60.0)
    from agent.pipeline import prefill_from_media

    media_bytes = None
    media_mime = None
    if media and media.filename:
        media_bytes = await media.read()
        if len(media_bytes) > 10 * 1024 * 1024:
            raise HTTPException(413, "File size exceeds maximum allowed limit (10 MB)")
        media_mime = media.content_type

    res = await prefill_from_media(
        media_bytes=media_bytes,
        media_mime=media_mime,
        text_hint=text,
    )
    return res


@app.get("/api/reports", response_model=List[ReportOut])
async def list_reports(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    from sqlalchemy import select, and_

    from sqlalchemy import or_
    filters = [or_(Report.authenticity != "spam", Report.authenticity.is_(None))]
    if status:
        filters.append(Report.status == StatusEnum(status))
    if severity:
        filters.append(Report.severity == SeverityEnum(severity))
    if category:
        filters.append(Report.category == category)

    async with AsyncSessionLocal() as session:
        q = select(Report).where(and_(*filters)).order_by(Report.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(q)
        reports = result.scalars().all()
        if search:
            s = search.lower()
            reports = [
                r for r in reports
                if s in r.title.lower() or s in r.description.lower() or s in r.location.lower()
            ]
        return reports


@app.get("/api/reports/reverse-geocode")
async def reverse_geocode_lookup(
    request: Request,
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
):
    """Resolve coordinates to clean street / locality address for citizen form auto-fill."""
    await check_ip_rate_limit(request, limit=20, window_secs=60.0)
    from agent.tools import reverse_geocode
    try:
        geo = await reverse_geocode(latitude, longitude)
        parts = [p for p in [geo.get("road"), geo.get("locality"), geo.get("city")] if p]
        address = ", ".join(parts) if parts else (geo.get("display_name") or f"Near coordinates ({latitude:.5f}, {longitude:.5f})")
        return {
            "address": address,
            "road": geo.get("road"),
            "locality": geo.get("locality"),
            "city": geo.get("city"),
            "display_name": geo.get("display_name"),
            "degraded": geo.get("degraded", False),
        }
    except Exception as e:
        return {
            "address": f"Near coordinates ({latitude:.5f}, {longitude:.5f})",
            "road": None,
            "locality": None,
            "city": None,
            "display_name": None,
            "degraded": True,
        }


@app.get("/api/reports/nearby", response_model=List[NearbyReportOut])
async def get_nearby_reports(
    request: Request,
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(0.5, description="Search radius in kilometers"),
    category: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    description: Optional[str] = Query(None),
):
    """Detect nearby existing reports for duplicate mitigation and semantic duplicate matching (FixMyStreet / Mark-a-Spot pattern)"""
    await check_ip_rate_limit(request, limit=30, window_secs=60.0)
    from sqlalchemy import select, and_

    filters = [
        Report.latitude.isnot(None),
        Report.longitude.isnot(None),
        Report.status.in_([StatusEnum.open, StatusEnum.in_progress]),
    ]
    if category:
        filters.append(Report.category == category)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(and_(*filters)))
        all_reports = result.scalars().all()

        nearby = []
        for r in all_reports:
            d = haversine_km(latitude, longitude, r.latitude, r.longitude)
            if d <= radius_km:
                data = ReportOut.model_validate(r).model_dump()
                data["distance_km"] = round(d, 3)
                nearby.append(NearbyReportOut(**data))

        nearby.sort(key=lambda x: x.distance_km)

        if nearby:
            from agent.pipeline import check_semantic_duplicates
            cand_dicts = [n.model_dump() for n in nearby[:3]]
            try:
                dup_map = await check_semantic_duplicates(
                    new_title=title,
                    new_description=description,
                    new_category=category,
                    candidates=cand_dicts,
                )
                for n in nearby[:3]:
                    if n.id in dup_map:
                        n.likely_duplicate = dup_map[n.id].get("likely_duplicate", False)
                        n.duplicate_reason = dup_map[n.id].get("duplicate_reason")
            except Exception as e:
                logger.warning(f"Error checking semantic duplicates in get_nearby_reports: {e}")

        return nearby


@app.get("/api/reports/export")
async def export_reports(
    format: str = Query("csv", pattern="^(csv|json)$"),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """Export public civic grievance data in CSV or JSON for citizen researchers and open data portals"""
    from sqlalchemy import select, and_

    from sqlalchemy import or_
    filters = [or_(Report.authenticity != "spam", Report.authenticity.is_(None))]
    if status:
        filters.append(Report.status == StatusEnum(status))
    if severity:
        filters.append(Report.severity == SeverityEnum(severity))
    if category:
        filters.append(Report.category == category)

    async with AsyncSessionLocal() as session:
        q = select(Report).where(and_(*filters)).order_by(Report.created_at.desc())
        result = await session.execute(q)
        reports = result.scalars().all()

        if format == "json":
            data = [ReportOut.model_validate(r).model_dump(mode="json") for r in reports]
            return JSONResponse(content=data)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "Category", "Severity", "Status",
            "Location", "Latitude", "Longitude", "Routed Department",
            "Upvotes", "SLA Hours", "Created At", "Resolved At", "Resolution Notes"
        ])
        for r in reports:
            writer.writerow([
                r.id,
                r.title,
                r.category,
                r.severity.value if hasattr(r.severity, "value") else r.severity,
                r.status.value if hasattr(r.status, "value") else r.status,
                r.location,
                r.latitude or "",
                r.longitude or "",
                r.routed_to or "",
                r.upvotes,
                r.sla_hours or "",
                r.created_at.isoformat() if r.created_at else "",
                r.resolved_at.isoformat() if r.resolved_at else "",
                r.resolution_notes or "",
            ])
        output.seek(0)
        filename = f"janaawaz_civic_reports_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@app.get("/api/reports/lookup", response_model=ReportOut)
async def lookup_report(q: str = Query(..., description="Docket number, UUID, or 8-char ID prefix")):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query 'q' cannot be empty.")

    clean_q = query.lstrip("#").strip()

    async with AsyncSessionLocal() as session:
        # 0. Direct tracking_token match (case-insensitive)
        res_tok = await session.execute(
            select(Report).where(func.upper(Report.tracking_token) == clean_q.upper()).order_by(Report.created_at.desc())
        )
        rep_tok = res_tok.scalars().first()
        if rep_tok:
            return rep_tok

        # 1. Direct docket_no match (case-insensitive)
        res = await session.execute(
            select(Report).where(func.lower(Report.docket_no) == clean_q.lower()).order_by(Report.created_at.desc())
        )
        report = res.scalars().first()
        if report:
            return report

        # 2. Try adding prefix if query is digits or 2026-XXXXX
        if clean_q.isdigit():
            padded = f"JA-2026-{int(clean_q):05d}"
            res = await session.execute(
                select(Report).where(func.lower(Report.docket_no) == padded.lower()).order_by(Report.created_at.desc())
            )
            report = res.scalars().first()
            if report:
                return report
        elif clean_q.lower().startswith("2026-"):
            res = await session.execute(
                select(Report).where(func.lower(Report.docket_no) == f"ja-{clean_q.lower()}").order_by(Report.created_at.desc())
            )
            report = res.scalars().first()
            if report:
                return report

        # 3. Exact full UUID match
        res = await session.execute(select(Report).where(Report.id == clean_q))
        report = res.scalars().first()
        if report:
            return report

        # 4. ID prefix match (e.g. 8-char prefix)
        if len(clean_q) >= 6:
            res = await session.execute(
                select(Report).where(Report.id.like(f"{clean_q}%")).order_by(Report.created_at.desc()).limit(1)
            )
            report = res.scalars().first()
            if report:
                return report

        raise HTTPException(
            status_code=404,
            detail=f"No civic docket found matching reference '{q}'. Please verify your reference number.",
        )


@app.get("/api/track/{token}", response_model=PublicTrackingOut)
async def public_track_ticket(token: str, request: Request):
    """Public zero-PII tracking endpoint for citizens using their private tracking token."""
    await check_ip_rate_limit(request, limit=30, window_secs=60.0)
    clean_token = token.strip().upper()
    if not clean_token:
        raise HTTPException(status_code=400, detail="Tracking token cannot be empty.")

    async with AsyncSessionLocal() as session:
        # Match by tracking_token first
        res = await session.execute(
            select(Report).where(func.upper(Report.tracking_token) == clean_token)
        )
        report = res.scalars().first()

        # Fallback: support looking up by docket_no as well
        if not report:
            res = await session.execute(
                select(Report).where(func.upper(Report.docket_no) == clean_token)
            )
            report = res.scalars().first()

        if not report:
            raise HTTPException(
                status_code=404,
                detail=f"Tracking reference '{token}' not found in active records. Please check the token sent in your email.",
            )

        # Timeline (strictly zero PII)
        t_res = await session.execute(
            select(ReportTimeline).where(ReportTimeline.report_id == report.id).order_by(ReportTimeline.created_at.asc())
        )
        timeline_entries = t_res.scalars().all()
        clean_timeline = [
            {
                "status": t.status,
                "actor": t.actor,
                "action_type": t.action_type,
                "notes": t.notes,
                "media_url": t.media_url,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in timeline_entries
        ]

        # Dispatch info
        d_res = await session.execute(
            select(Dispatch).where(Dispatch.report_id == report.id).order_by(Dispatch.created_at.asc())
        )
        dispatches = d_res.scalars().all()
        latest_dispatch = dispatches[-1] if dispatches else None

        dispatch_info = None
        if latest_dispatch:
            from agent.directory import mask_email
            dispatch_info = {
                "designation": latest_dispatch.recipient_office or report.routed_to or "Municipal Engineering Division",
                "time_sent": latest_dispatch.created_at.isoformat() if latest_dispatch.created_at else None,
                "provider_accepted": bool(latest_dispatch.sent),
                "status_text": "Sent to municipal authority" if latest_dispatch.sent else "Transmission queued",
                "masked_recipient": mask_email(latest_dispatch.to_email),
            }

        # Calculate SLA countdown
        created_dt = report.created_at or datetime.utcnow()
        sla_hours = report.sla_hours or 72
        deadline_dt = created_dt + timedelta(hours=sla_hours)
        now = datetime.utcnow()
        diff_secs = (deadline_dt - now).total_seconds()
        remaining_hours = round(max(0.0, diff_secs / 3600.0), 1)

        if diff_secs > 0:
            hrs = int(diff_secs // 3600)
            mins = int((diff_secs % 3600) // 60)
            countdown_str = f"{hrs}h {mins}m remaining"
        else:
            overdue_hrs = int(abs(diff_secs) // 3600)
            countdown_str = f"Overdue by {overdue_hrs}h"

        track_status = report.status.value if hasattr(report.status, "value") else str(report.status)
        track_status_text = None
        if getattr(report, "authenticity", None) in ("spam", "suspicious"):
            track_status = "Held for review"
            track_status_text = f"Held for review: {report.authenticity_reason or 'Could not confirm this is a civic issue'}"
            if dispatch_info:
                dispatch_info["status_text"] = "Held for review"

        return PublicTrackingOut(
            docket_no=report.docket_no or f"JA-2026-{str(report.id)[:8].upper()}",
            tracking_token=report.tracking_token or "PENDING",
            title=report.title,
            description=report.description,
            category=report.category,
            locality=report.locality or report.location,
            severity=report.severity.value if hasattr(report.severity, "value") else str(report.severity),
            status=track_status,
            authenticity=report.authenticity or "unchecked",
            authenticity_reason=report.authenticity_reason,
            status_text=track_status_text,
            sla_hours=sla_hours,
            sla_deadline=deadline_dt.isoformat(),
            sla_remaining_hours=remaining_hours,
            sla_countdown=countdown_str,
            escalation_level=report.escalation_level or 0,
            is_overdue=bool(report.is_overdue),
            timeline=clean_timeline,
            dispatch_info=dispatch_info,
            media_url=report.media_url,
            resolved_media_url=report.resolved_media_url,
            created_at=created_dt.isoformat(),
            updated_at=(report.updated_at or created_dt).isoformat(),
        )


@app.get("/api/reports/{report_id}", response_model=ReportOut)
async def get_report(report_id: str):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")
        return report


@app.get("/api/reports/{report_id}/timeline", response_model=List[TimelineOut])
async def get_report_timeline(report_id: str):
    """Retrieve full chronological audit trail and civic lifecycle events"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ReportTimeline)
            .where(ReportTimeline.report_id == report_id)
            .order_by(ReportTimeline.created_at.asc())
        )
        return result.scalars().all()


@app.patch("/api/reports/{report_id}/status")
async def update_status(
    report_id: str,
    status: str,
    note: Optional[str] = None,
    actor: Optional[str] = None,
    current_authority: Dict[str, Any] = Depends(require_authority),
):
    from sqlalchemy import select
    clean_status = status.strip().lower()
    if clean_status in ("resolved", "closed"):
        raise HTTPException(
            status_code=400,
            detail="use /resolve with an after-photo",
        )

    authority_email = current_authority.get("sub", "authority")
    authority_actor = actor or f"Authority ({authority_email})"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        report.status = StatusEnum(clean_status)
        now = datetime.utcnow()
        report.updated_at = now

        if note:
            report.resolution_notes = note

        await log_timeline(
            session=session,
            report_id=report_id,
            status=clean_status,
            actor=authority_actor,
            action_type="status_update",
            notes=note or f"Ticket status transitioned to {clean_status.replace('_', ' ').title()}.",
        )

        await session.commit()
        return {"message": "Status updated", "status": clean_status}


@app.get("/api/authority/queue", response_model=AuthorityQueueOut)
async def get_authority_priority_queue(
    current_authority: Dict[str, Any] = Depends(require_authority),
):
    """Ranks open tickets by transparent composite urgency score, adds Gemini 'why now' for top 5,
    and clusters tickets within 300m into crew dispatch batches."""
    from agent.pipeline import generate_why_now_rationales

    now = datetime.utcnow()
    from sqlalchemy import or_, and_
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Report).where(
                and_(
                    Report.status.in_([StatusEnum.open, StatusEnum.in_progress]),
                    or_(Report.authenticity != "spam", Report.authenticity.is_(None)),
                )
            )
        )
        reports = result.scalars().all()

        held_res = await session.execute(
            select(Report).where(
                or_(
                    Report.authenticity.in_(["suspicious", "spam"]),
                    Report.needs_human_review.is_(True),
                )
            ).order_by(Report.created_at.desc())
        )
        held_reports = held_res.scalars().all()

        if not reports:
            return AuthorityQueueOut(total_queued=0, items=[], crew_batches=[])

        # 1. Precalculate 300m hotspot counts
        geo_reports = [r for r in reports if r.latitude is not None and r.longitude is not None]
        cluster_counts = {}
        for r in reports:
            count = 0
            if r.latitude is not None and r.longitude is not None:
                for other in geo_reports:
                    if other.id != r.id:
                        d = haversine_km(r.latitude, r.longitude, other.latitude, other.longitude)
                        if d <= 0.3:
                            count += 1
            cluster_counts[r.id] = count

        # 2. Transparent score formula
        sev_weights = {"critical": 100, "high": 60, "medium": 30, "low": 10}
        scored_items = []

        for r in reports:
            sev_str = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
            sev_pts = sev_weights.get(sev_str.lower(), 30)

            sla = r.sla_hours or 72
            elapsed = (now - r.created_at).total_seconds() / 3600
            sla_rem = round(sla - elapsed, 1)
            is_overdue = sla_rem <= 0

            if is_overdue:
                sla_pts = 50
            elif sla_rem < 12:
                sla_pts = 30
            elif sla_rem < 24:
                sla_pts = 15
            else:
                sla_pts = 5

            upvote_pts = min((r.upvotes or 0) * 5, 25)

            h_count = cluster_counts.get(r.id, 0)
            hotspot_pts = 20 if h_count >= 2 else (10 if h_count == 1 else 0)

            rain_pts = 0
            has_rain_risk = False
            if r.agent_trace:
                try:
                    trace_steps = json.loads(r.agent_trace)
                    for step in trace_steps:
                        if step.get("step") == "weather":
                            w_data = step.get("data", {})
                            if w_data.get("heavy_rain_risk"):
                                rain_pts = 15
                                has_rain_risk = True
                                break
                except Exception:
                    pass

            total = sev_pts + sla_pts + upvote_pts + hotspot_pts + rain_pts

            breakdown = ScoreBreakdown(
                severity_pts=sev_pts,
                sla_pts=sla_pts,
                upvote_pts=upvote_pts,
                hotspot_pts=hotspot_pts,
                rain_pts=rain_pts,
                total=total,
            )

            scored_items.append({
                "report": r,
                "score": total,
                "score_breakdown": breakdown,
                "sla_remaining_hours": sla_rem,
                "is_overdue": is_overdue,
                "rain_risk": has_rain_risk,
                "hotspot_count": h_count,
                "why_now": None,
            })

        scored_items.sort(key=lambda x: x["score"], reverse=True)

        # 3. Gemini "why now" for top 5 tickets
        top_5 = scored_items[:5]
        if top_5:
            top_5_data = [
                {
                    "id": item["report"].id,
                    "title": item["report"].title,
                    "category": item["report"].category,
                    "severity": item["report"].severity.value if hasattr(item["report"].severity, "value") else str(item["report"].severity),
                    "sla_remaining_hours": item["sla_remaining_hours"],
                    "is_overdue": item["is_overdue"],
                    "upvotes": item["report"].upvotes or 0,
                    "rain_risk": item["rain_risk"],
                    "hotspot_count": item["hotspot_count"],
                }
                for item in top_5
            ]
            try:
                why_now_map = await generate_why_now_rationales(top_5_data)
                for item in top_5:
                    item["why_now"] = why_now_map.get(item["report"].id)
            except Exception as e:
                logger.warning(f"Error generating why_now: {e}")

        # 4. Suggest 300m crew batches
        crew_batches = []
        assigned = set()
        batch_counter = 1

        for item in scored_items:
            r = item["report"]
            if r.id in assigned or r.latitude is None or r.longitude is None:
                continue

            cluster = [r]
            for other_item in scored_items:
                o_r = other_item["report"]
                if o_r.id != r.id and o_r.id not in assigned and o_r.latitude is not None and o_r.longitude is not None:
                    d = haversine_km(r.latitude, r.longitude, o_r.latitude, o_r.longitude)
                    if d <= 0.3:
                        cluster.append(o_r)

            if len(cluster) >= 2:
                for c_rep in cluster:
                    assigned.add(c_rep.id)
                cats = [c.category for c in cluster]
                top_cat = max(set(cats), key=cats.count)
                crew_batches.append(CrewBatchOut(
                    batch_id=f"CREW-BATCH-{batch_counter:02d}",
                    center_location=r.locality or r.location or "Cluster Vicinity",
                    category=top_cat,
                    ticket_count=len(cluster),
                    dockets=[c.docket_no or c.id[:8] for c in cluster],
                    report_ids=[c.id for c in cluster],
                ))
                batch_counter += 1

        queue_items = [
            QueueItemOut(
                id=item["report"].id,
                docket_no=item["report"].docket_no,
                title=item["report"].title,
                category=item["report"].category,
                location=item["report"].location,
                severity=item["report"].severity.value if hasattr(item["report"].severity, "value") else str(item["report"].severity),
                status=item["report"].status.value if hasattr(item["report"].status, "value") else str(item["report"].status),
                created_at=item["report"].created_at,
                sla_hours=item["report"].sla_hours,
                sla_remaining_hours=item["sla_remaining_hours"],
                is_overdue=item["is_overdue"],
                upvotes=item["report"].upvotes or 0,
                score=item["score"],
                score_breakdown=item["score_breakdown"],
                why_now=item["why_now"],
                media_url=item["report"].media_url,
            )
            for item in scored_items
        ]

        held_items_out = [ReportOut.model_validate(r) for r in held_reports]
        return AuthorityQueueOut(
            total_queued=len(queue_items),
            items=queue_items,
            crew_batches=crew_batches,
            held_items=held_items_out,
        )


@app.post("/api/reports/{report_id}/resolve", response_model=ReportOut)
async def resolve_report_with_proof(
    report_id: str,
    status: str = Form("resolved"),
    resolution_notes: str = Form(...),
    actor: Optional[str] = Form(None),
    media: Optional[UploadFile] = File(None),
    current_authority: Dict[str, Any] = Depends(require_authority),
):
    """Closeout ticket with verified resolution notes and photographic completion proof (Authority only)"""
    from sqlalchemy import select
    authority_email = current_authority.get("sub", "authority")
    authority_actor = actor or f"Authority ({authority_email})"

    if not media or not media.filename:
        raise HTTPException(
            status_code=400,
            detail="An after-photo is required to resolve a grievance. Please upload remediation completion evidence.",
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        ext = Path(media.filename).suffix or ".jpg"
        filename = f"resolved_{report_id}{ext}"
        content = await media.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "File size exceeds maximum allowed limit (10 MB)")
        resolved_media_url = await save_media(filename, content, media.content_type)
        report.resolved_media_url = resolved_media_url

        # Multimodal AI Resolution Verification with EXIF GPS cross-check
        verification_result = await verify_repair_evidence(
            original_media_url=report.media_url,
            after_bytes=content,
            after_mime=media.content_type or "image/jpeg",
            title=report.title,
            description=report.description,
            resolution_notes=resolution_notes,
            upload_dir=str(UPLOAD_DIR),
            report_latitude=report.latitude,
            report_longitude=report.longitude,
        )

        report.resolution_verdict = verification_result.verdict
        report.resolution_confidence = verification_result.confidence
        report.resolution_explanation = verification_result.explanation

        now = datetime.utcnow()
        report.updated_at = now
        report.resolution_notes = resolution_notes

        # If verdict is unclear, not_fixed, or different_location: do NOT resolve
        if verification_result.verdict in ("unclear", "not_fixed", "different_location"):
            report.status = StatusEnum.in_progress
            timeline_note = (
                "evidence inconclusive, resubmit a clearer photo"
                if verification_result.verdict == "unclear"
                else f"AI verification rejected closure ({verification_result.verdict.replace('_', ' ').title()}): {verification_result.explanation}"
            )
            await log_timeline(
                session=session,
                report_id=report_id,
                status=StatusEnum.in_progress.value,
                actor="Jan Aawaz AI Inspector",
                action_type="closure_rejected",
                notes=timeline_note,
                media_url=resolved_media_url,
            )
            await session.commit()
            await session.refresh(report)
            return report

        # Approved resolution (fixed or partially_fixed)
        report.status = StatusEnum.resolved
        report.resolved_at = now

        verdict_str = f" · AI Verdict: {verification_result.verdict.replace('_', ' ').title()}"
        await log_timeline(
            session=session,
            report_id=report_id,
            status=StatusEnum.resolved.value,
            actor=authority_actor,
            action_type="resolution_proof",
            notes=f"Issue resolved: {resolution_notes}{verdict_str}",
            media_url=resolved_media_url,
        )

        await session.commit()
        await session.refresh(report)
        return report


@app.post("/api/reports/{report_id}/upvote")
async def upvote_report(
    report_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    from sqlalchemy import select
    from models import Upvote
    user_email = current_user.get("sub") or current_user.get("email")
    if not user_email:
        raise HTTPException(401, "Citizen authentication required to upvote")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        # Enforce one upvote per user per report
        existing_upvote = (
            await session.execute(
                select(Upvote).where(
                    Upvote.report_id == report_id,
                    Upvote.user_email == user_email.strip().lower(),
                )
            )
        ).scalar_one_or_none()

        if existing_upvote:
            raise HTTPException(400, "Already upvoted this report")

        new_upvote = Upvote(
            id=str(uuid.uuid4()),
            report_id=report_id,
            user_email=user_email.strip().lower(),
        )
        session.add(new_upvote)
        report.upvotes += 1
        report.updated_at = datetime.utcnow()
        await session.commit()
        return {"upvotes": report.upvotes}


@app.get("/api/reports/{report_id}/dispatches", response_model=List[DispatchOut])
async def list_report_dispatches(report_id: str):
    """Fetch formal dispatch letters and escalation transmissions for a docket."""
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Dispatch).where(Dispatch.report_id == report_id).order_by(Dispatch.created_at.desc())
        )
        return res.scalars().all()


@app.post("/api/reports/{report_id}/feedback", response_model=ReportOut)
async def submit_citizen_feedback(
    report_id: str,
    payload: FeedbackRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Citizen confirms or disputes ticket resolution."""
    citizen_email = current_user.get("sub", "citizen")
    fb = payload.feedback.lower().strip()
    if fb not in ("confirmed", "disputed"):
        raise HTTPException(400, "Feedback must be 'confirmed' or 'disputed'")

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Report).where(Report.id == report_id))
        report = res.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        report.citizen_feedback = fb
        report.feedback_notes = payload.notes
        now = datetime.utcnow()
        report.updated_at = now

        if fb == "disputed":
            report.status = StatusEnum.in_progress
            report.resolved_at = None
            await log_timeline(
                session=session,
                report_id=report_id,
                status=StatusEnum.in_progress.value,
                actor=f"Citizen ({citizen_email})",
                action_type="citizen_disputed",
                notes=f"Citizen disputed resolution: {payload.notes or 'Reported issue persists on ground.'}",
            )
        else:
            await log_timeline(
                session=session,
                report_id=report_id,
                status=report.status.value,
                actor=f"Citizen ({citizen_email})",
                action_type="citizen_confirmed",
                notes=f"Citizen confirmed resolution: {payload.notes or 'Work completed satisfactorily.'}",
            )

        await session.commit()
        await session.refresh(report)
        return report


@app.post("/api/admin/watchdog/run")
async def trigger_watchdog_run(
    current_authority: Dict[str, Any] = Depends(require_authority),
):
    """Authority trigger to immediately evaluate active dockets against SLA limits."""
    res = await run_watchdog_check()
    return res


@app.post("/api/reports/{report_id}/explain", response_model=ExplanationOut)
async def explain_report(
    report_id: str,
    request: Request,
    lang: str = Query("en", description="Target language code: en, hi, ta, ml, te, kn, bn, mr"),
):
    """Generate or retrieve a cached plain-language explanation of a civic docket."""
    await check_ip_rate_limit(request, limit=30, window_secs=60.0)
    valid_langs = {"en", "hi", "ta", "ml", "te", "kn", "bn", "mr"}
    normalized_lang = lang.lower().strip()
    if normalized_lang not in valid_langs:
        raise HTTPException(400, f"Language '{lang}' not supported. Must be one of: {', '.join(sorted(valid_langs))}")

    async with AsyncSessionLocal() as session:
        # Check cache in DB table explanations
        stmt = select(Explanation).where(
            Explanation.report_id == report_id,
            Explanation.lang == normalized_lang,
        )
        res = await session.execute(stmt)
        cached_exp = res.scalars().first()
        if cached_exp:
            return ExplanationOut(
                report_id=report_id,
                lang=normalized_lang,
                text=cached_exp.text,
                cached=True,
            )

        # Fetch report from DB
        r_stmt = select(Report).where(Report.id == report_id)
        r_res = await session.execute(r_stmt)
        report = r_res.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        report_dict = {
            "id": report.id,
            "title": report.title,
            "description": report.description,
            "category": report.category,
            "severity": report.severity.value if hasattr(report.severity, "value") else str(report.severity),
            "status": report.status.value if hasattr(report.status, "value") else str(report.status),
            "sla_hours": report.sla_hours,
            "routed_to": report.routed_to,
            "locality": report.locality or report.location,
            "location": report.location,
            "safety_precautions": report.safety_precautions,
            "action_plan": report.action_plan,
        }

        explanation_text = await generate_plain_language_explanation(report_dict, normalized_lang)

        # Cache in explanations table
        new_exp = Explanation(
            id=str(uuid.uuid4()),
            report_id=report_id,
            lang=normalized_lang,
            text=explanation_text,
            created_at=datetime.utcnow(),
        )
        session.add(new_exp)
        await session.commit()

        return ExplanationOut(
            report_id=report_id,
            lang=normalized_lang,
            text=explanation_text,
            cached=False,
        )


@app.get("/api/insights")
async def get_insights(
    request: Request,
    refresh: bool = Query(False, description="Force recomputation of insights"),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
):
    """Compute live 300m spatial clusters, department metrics, and Gemini civic brief."""
    await check_ip_rate_limit(request, limit=30, window_secs=60.0)
    if refresh:
        if not current_user or current_user.get("role") != "authority":
            raise HTTPException(
                status_code=403,
                detail="Refreshing civic insights requires municipal authority credentials.",
            )
    insights = await generate_civic_insights(force_refresh=refresh)
    return insights



@app.get("/api/stats", response_model=StatsOut)
async def get_stats():
    from sqlalchemy import select, or_
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Report).where(or_(Report.authenticity != "spam", Report.authenticity.is_(None)))
        )
        all_reports = result.scalars().all()

        by_cat = {}
        by_dept = {}
        resolution_hours_list = []
        sla_compliant_count = 0
        resolved_count = 0

        for r in all_reports:
            by_cat[r.category] = by_cat.get(r.category, 0) + 1
            if r.routed_to:
                by_dept[r.routed_to] = by_dept.get(r.routed_to, 0) + 1

            if r.status in [StatusEnum.resolved, StatusEnum.closed] and r.resolved_at and r.created_at:
                resolved_count += 1
                hours = (r.resolved_at - r.created_at).total_seconds() / 3600.0
                resolution_hours_list.append(hours)
                if r.sla_hours and hours <= r.sla_hours:
                    sla_compliant_count += 1

        avg_res_hours = round(sum(resolution_hours_list) / len(resolution_hours_list), 1) if resolution_hours_list else 0.0
        sla_rate = round((sla_compliant_count / resolved_count) * 100.0, 1) if resolved_count > 0 else 100.0

        critical_active = sum(
            1 for r in all_reports
            if r.severity == SeverityEnum.critical and r.status in [StatusEnum.open, StatusEnum.in_progress]
        )
        overdue_count = sum(
            1 for r in all_reports
            if (bool(getattr(r, "is_overdue", False)) or ((getattr(r, "escalation_level", 0) or 0) >= 3)) and r.status in [StatusEnum.open, StatusEnum.in_progress]
        )

        return StatsOut(
            total=len(all_reports),
            open=sum(1 for r in all_reports if r.status == StatusEnum.open),
            in_progress=sum(1 for r in all_reports if r.status == StatusEnum.in_progress),
            resolved=sum(1 for r in all_reports if r.status == StatusEnum.resolved),
            closed=sum(1 for r in all_reports if r.status == StatusEnum.closed),
            critical=sum(1 for r in all_reports if r.severity == SeverityEnum.critical),
            high=sum(1 for r in all_reports if r.severity == SeverityEnum.high),
            medium=sum(1 for r in all_reports if r.severity == SeverityEnum.medium),
            low=sum(1 for r in all_reports if r.severity == SeverityEnum.low),
            critical_active=critical_active,
            avg_resolution_hours=avg_res_hours,
            sla_compliance_rate=sla_rate,
            sla_time_scale=get_sla_time_scale(),
            overdue=overdue_count,
            by_category=by_cat,
            by_department=by_dept,
        )


# ── Open311 GeoReport v2 Compliance Endpoints ─────────────────────────────────
# Standard specification compatibility (FixMyStreet / Mark-a-Spot interoperability)
@app.get("/api/open311/v2/services.json")
async def open311_services():
    """List service types in Open311 GeoReport v2 standard format"""
    services = [
        {"service_code": "road_damage", "service_name": "Road Damage & Potholes", "description": "Potholes, broken asphalt, curb damage", "metadata": False, "type": "realtime", "keywords": "road, pothole, asphalt", "group": "Infrastructure"},
        {"service_code": "bridge_damage", "service_name": "Bridge & Structural Damage", "description": "Cracks, joint issues, safety rails", "metadata": False, "type": "realtime", "keywords": "bridge, concrete, structure", "group": "Infrastructure"},
        {"service_code": "water_leak", "service_name": "Water Leak / Main Break", "description": "Burst pipes, high pressure leaks, flooding", "metadata": False, "type": "realtime", "keywords": "water, pipe, leak", "group": "Utilities"},
        {"service_code": "pollution", "service_name": "Environmental Pollution", "description": "Illegal dumping, toxic discharge, air quality", "metadata": False, "type": "realtime", "keywords": "pollution, chemical, environment", "group": "Environment"},
        {"service_code": "streetlight", "service_name": "Streetlight Outage", "description": "Dark streetlight, damaged pole, flickering", "metadata": False, "type": "realtime", "keywords": "streetlight, light, electricity", "group": "Utilities"},
        {"service_code": "garbage", "service_name": "Garbage & Waste Accumulation", "description": "Uncollected trash, illegal debris", "metadata": False, "type": "realtime", "keywords": "garbage, waste, trash", "group": "Sanitation"},
        {"service_code": "drainage", "service_name": "Drainage & Stormwater Blockage", "description": "Clogged storm sewers, overflow hazards", "metadata": False, "type": "realtime", "keywords": "drain, sewer, flood", "group": "Sanitation"},
        {"service_code": "other", "service_name": "Other Civic Issues", "description": "General non-categorized municipal matter", "metadata": False, "type": "realtime", "keywords": "general, municipal", "group": "General"},
    ]
    return services


@app.get("/api/open311/v2/requests.json")
async def open311_requests(
    service_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Retrieve service requests in Open311 standard format"""
    from sqlalchemy import select, and_
    from sqlalchemy import or_
    filters = [or_(Report.authenticity != "spam", Report.authenticity.is_(None))]
    if service_code:
        filters.append(Report.category == service_code)
    if status:
        if status.lower() == "open":
            filters.append(Report.status.in_([StatusEnum.open, StatusEnum.in_progress]))
        elif status.lower() == "closed":
            filters.append(Report.status.in_([StatusEnum.resolved, StatusEnum.closed]))

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(and_(*filters)).order_by(Report.created_at.desc()).limit(100))
        reports = result.scalars().all()
        return [
            {
                "service_request_id": r.id,
                "status": "open" if r.status in [StatusEnum.open, StatusEnum.in_progress] else "closed",
                "status_notes": r.resolution_notes or r.ai_analysis,
                "service_name": r.category.replace('_', ' ').title(),
                "service_code": r.category,
                "description": r.description,
                "agency_responsible": r.routed_to,
                "requested_datetime": r.created_at.isoformat() if r.created_at else None,
                "updated_datetime": r.updated_at.isoformat() if r.updated_at else None,
                "address": r.location,
                "lat": r.latitude,
                "long": r.longitude,
                "media_url": r.media_url,
            }
            for r in reports
        ]




# ── Phase M: Authenticity Gate Management & Citizen Appeals ────────────────────
class AuthenticityOverrideRequest(BaseModel):
    verdict: str  # "genuine" | "spam" | "suspicious"
    note: Optional[str] = None


class CitizenAppealRequest(BaseModel):
    note: Optional[str] = None


@app.post("/api/reports/{report_id}/authenticity")
async def override_authenticity(
    report_id: str,
    payload: AuthenticityOverrideRequest,
    current_authority: Dict[str, Any] = Depends(require_authority),
):
    """Authority override for complaint authenticity (genuine / spam / suspicious)."""
    authority_email = current_authority.get("sub", "authority")
    verdict = payload.verdict.strip().lower()
    if verdict not in ("genuine", "spam", "suspicious"):
        raise HTTPException(status_code=400, detail="Verdict must be 'genuine', 'spam', or 'suspicious'.")

    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        report.authenticity = verdict
        report.authenticity_reason = payload.note or f"Authority review verdict: {verdict}"
        report.updated_at = datetime.utcnow()

        if verdict == "genuine":
            report.needs_human_review = False
            await log_timeline(
                session=session,
                report_id=report.id,
                status=report.status.value if hasattr(report.status, "value") else str(report.status),
                actor=f"Authority ({authority_email})",
                action_type="authority_approved",
                notes=f"Authority approved: {payload.note or 'Report verified as genuine civic issue.'}",
            )
            await session.commit()
            try:
                await draft_and_send_dispatch(report.id, "initial")
            except Exception as e:
                logger.warning(f"Error triggering dispatch on authority approval: {e}")
        elif verdict == "spam":
            report.needs_human_review = False
            await log_timeline(
                session=session,
                report_id=report.id,
                status=report.status.value if hasattr(report.status, "value") else str(report.status),
                actor=f"Authority ({authority_email})",
                action_type="authority_marked_spam",
                notes=f"Authority marked spam: {payload.note or 'Report classified as non-civic/spam.'}",
            )
            await session.commit()
        else:  # suspicious
            report.needs_human_review = True
            await log_timeline(
                session=session,
                report_id=report.id,
                status=report.status.value if hasattr(report.status, "value") else str(report.status),
                actor=f"Authority ({authority_email})",
                action_type="authority_flagged_suspicious",
                notes=f"Authority marked suspicious: {payload.note or 'Held for manual inspection.'}",
            )
            await session.commit()

        return {"message": f"Authenticity updated to {verdict}", "authenticity": verdict}


@app.post("/api/reports/{report_id}/appeal")
async def appeal_authenticity(
    report_id: str,
    payload: Optional[CitizenAppealRequest] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Citizen appeal against a suspicious or spam authenticity flag (owner only, once)."""
    citizen_email = current_user.get("sub")
    citizen_id = current_user.get("user_id")

    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        is_owner = False
        if citizen_id and report.citizen_id and str(report.citizen_id) == str(citizen_id):
            is_owner = True
        elif citizen_email and report.citizen_email and report.citizen_email.strip().lower() == citizen_email.strip().lower():
            is_owner = True

        if not is_owner:
            raise HTTPException(status_code=403, detail="Only the reporting citizen can appeal this ticket.")

        if getattr(report, "appeal_submitted", False):
            raise HTTPException(status_code=400, detail="An appeal has already been submitted for this report.")

        appeal_note = (payload.note if payload and payload.note else "Citizen requested authority review of held grievance.")
        report.authenticity = "suspicious"
        report.needs_human_review = True
        report.appeal_submitted = True
        report.authenticity_reason = f"Appealed by citizen: {appeal_note}"
        report.updated_at = datetime.utcnow()

        await log_timeline(
            session=session,
            report_id=report.id,
            status=report.status.value if hasattr(report.status, "value") else str(report.status),
            actor="Citizen Reporter",
            action_type="appeal_submitted",
            notes=f"Citizen appealed: {appeal_note}",
        )
        await session.commit()

        return {"message": "Appeal submitted successfully", "authenticity": "suspicious"}
