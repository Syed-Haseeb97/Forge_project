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
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from database import engine, AsyncSessionLocal, Base
from models import Report, ReportTimeline, Comment, Citizen, Dispatch, Explanation, Upvote, StatusEnum, SeverityEnum
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
from sqlalchemy import select, text

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
    resolution_verdict: Optional[str] = None
    resolution_confidence: Optional[float] = None
    resolution_explanation: Optional[str] = None
    citizen_feedback: Optional[str] = None
    feedback_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DispatchOut(BaseModel):
    id: str
    report_id: str
    kind: str
    to_email: str
    subject: str
    body: str
    sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


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
        "message": "Verification code dispatched to your email inbox." if sent else "Verification code generated.",
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
        "message": "Verification code sent to your email inbox." if sent else "Verification code dispatched.",
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
        # AI multimodal analysis with live database session for recurrence check
        analysis_res = await analyze_report(
            title=title,
            description=description,
            category=category,
            location=location,
            latitude=latitude,
            longitude=longitude,
            media_path=str(UPLOAD_DIR / f"{report_id}{Path(media.filename).suffix}") if media and media.filename else None,
            media_bytes=content if media and media.filename else None,
            media_mime=media.content_type if media else None,
            db_session=session,
        )

        severity_str = analysis_res.get("severity", "medium")
        severity = SeverityEnum(severity_str)
        routed_to = analysis_res.get("routed_to") or ROUTING_MAP.get(category, ROUTING_MAP["other"])
        action_plan = analysis_res.get("action_plan")
        safety_precautions = analysis_res.get("safety_precautions")
        sla_hours = analysis_res.get("sla_hours", 72)
        ai_analysis = analysis_res.get("ai_analysis")

        # Serialized trace & new audit fields
        agent_trace_data = analysis_res.get("agent_trace")
        agent_trace_str = json.dumps(agent_trace_data) if agent_trace_data else None
        confidence = analysis_res.get("confidence")
        severity_rationale = analysis_res.get("severity_rationale")
        detected_language = analysis_res.get("detected_language")
        locality = analysis_res.get("locality") or location

        if not citizen_id and actual_citizen_email:
            res = await session.execute(select(Citizen).where(Citizen.email == actual_citizen_email.strip().lower()))
            cit = res.scalar_one_or_none()
            if cit:
                citizen_id = cit.id

        # Determine sequential docket_no (JA-2026-00001)
        docket_stmt = select(Report.docket_no).where(Report.docket_no.like("JA-2026-%")).order_by(Report.docket_no.desc()).limit(1)
        last_docket = (await session.execute(docket_stmt)).scalar_one_or_none()
        next_seq = 1
        if last_docket:
            try:
                next_seq = int(last_docket.split("-")[-1]) + 1
            except ValueError:
                next_seq = 1
        docket_no = f"JA-2026-{next_seq:05d}"

        report = Report(
            id=report_id,
            docket_no=docket_no,
            citizen_id=citizen_id,
            citizen_email=actual_citizen_email.strip().lower() if actual_citizen_email else None,
            title=title,
            description=description,
            category=category,
            location=location,
            latitude=latitude,
            longitude=longitude,
            severity=severity,
            status=StatusEnum.open,
            ai_analysis=ai_analysis,
            action_plan=action_plan,
            safety_precautions=safety_precautions,
            sla_hours=sla_hours,
            routed_to=routed_to,
            upvotes=0,
            media_url=media_url,
            agent_trace=agent_trace_str,
            confidence=confidence,
            severity_rationale=severity_rationale,
            detected_language=detected_language,
            locality=locality,
            created_at=now,
            updated_at=now,
        )
        session.add(report)

        # Log timeline events
        await log_timeline(
            session=session,
            report_id=report_id,
            status=StatusEnum.open.value,
            actor="Citizen Reporter",
            action_type="submitted",
            notes=f"Civic grievance registered at {locality or location}.",
            media_url=media_url,
        )

        await log_timeline(
            session=session,
            report_id=report_id,
            status=StatusEnum.open.value,
            actor="Jan Aawaz AI Triage",
            action_type="ai_triage",
            notes=f"Assessed as {severity_str.upper()} priority ({sla_hours}h SLA). Routed to {routed_to}. Rationale: {severity_rationale or 'Evaluated based on multi-signal evidence'}",
        )

        await session.commit()
        await session.refresh(report)

        # Schedule autonomous dispatch drafting & transmission in the background
        background_tasks.add_task(draft_and_send_dispatch, report_id, "initial")

        return report


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

    filters = []
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


@app.get("/api/reports/nearby", response_model=List[NearbyReportOut])
async def get_nearby_reports(
    latitude: float = Query(...),
    longitude: float = Query(...),
    radius_km: float = Query(0.5, description="Search radius in kilometers"),
    category: Optional[str] = Query(None),
):
    """Detect nearby existing reports for duplicate mitigation (FixMyStreet / Mark-a-Spot pattern)"""
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

    filters = []
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
        # 1. Direct docket_no match (case-insensitive)
        res = await session.execute(
            select(Report).where(func.lower(Report.docket_no) == clean_q.lower())
        )
        report = res.scalar_one_or_none()
        if report:
            return report

        # 2. Try adding prefix if query is digits or 2026-XXXXX
        if clean_q.isdigit():
            padded = f"JA-2026-{int(clean_q):05d}"
            res = await session.execute(
                select(Report).where(func.lower(Report.docket_no) == padded.lower())
            )
            report = res.scalar_one_or_none()
            if report:
                return report
        elif clean_q.lower().startswith("2026-"):
            res = await session.execute(
                select(Report).where(func.lower(Report.docket_no) == f"ja-{clean_q.lower()}")
            )
            report = res.scalar_one_or_none()
            if report:
                return report

        # 3. Exact full UUID match
        res = await session.execute(select(Report).where(Report.id == clean_q))
        report = res.scalar_one_or_none()
        if report:
            return report

        # 4. ID prefix match (e.g. 8-char prefix)
        if len(clean_q) >= 6:
            res = await session.execute(
                select(Report).where(Report.id.like(f"{clean_q}%")).limit(1)
            )
            report = res.scalar_one_or_none()
            if report:
                return report

        raise HTTPException(
            status_code=404,
            detail=f"No civic docket found matching reference '{q}'. Please verify your reference number.",
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
    official_actor = actor or f"Municipal Authority ({authority_email})"

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
            actor=official_actor,
            action_type="status_update",
            notes=note or f"Ticket status transitioned to {clean_status.replace('_', ' ').title()}.",
        )

        await session.commit()
        return {"message": "Status updated", "status": clean_status}


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
    official_actor = actor or f"Municipal Authority ({authority_email})"

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
            actor=official_actor,
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
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report))
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
    filters = []
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


# ── Public Comments ────────────────────────────────────────────────────────────
class CommentIn(BaseModel):
    author: str = "Anonymous"
    role: str = "citizen"
    content: str


class CommentOut(BaseModel):
    id: str
    report_id: str
    author: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


@app.get("/api/reports/{report_id}/comments", response_model=List[CommentOut])
async def get_comments(report_id: str):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Comment).where(Comment.report_id == report_id).order_by(Comment.created_at.asc())
        )
        return result.scalars().all()


@app.post("/api/reports/{report_id}/comments", response_model=CommentOut)
async def add_comment(
    report_id: str,
    body: CommentIn,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(Report).where(Report.id == report_id))
        report = r.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        user_role = current_user.get("role", "citizen")
        if body.role == "authority" and user_role != "authority":
            raise HTTPException(
                status_code=403,
                detail="Municipal authority credentials required to append official updates.",
            )

        effective_role = "authority" if (user_role == "authority" and body.role == "authority") else "citizen"
        author_name = body.author.strip() if body.author and body.author != "Anonymous" else current_user.get("sub", "Citizen")

        comment = Comment(
            id=str(uuid.uuid4()),
            report_id=report_id,
            author=author_name[:100],
            role=effective_role,
            content=body.content,
            created_at=datetime.utcnow(),
        )
        session.add(comment)

        # Log timeline comment note if official
        if effective_role == "authority":
            await log_timeline(
                session=session,
                report_id=report_id,
                status=report.status.value,
                actor=f"Official ({comment.author})",
                action_type="official_note",
                notes=body.content[:300],
            )

        await session.commit()
        await session.refresh(comment)
        return comment
