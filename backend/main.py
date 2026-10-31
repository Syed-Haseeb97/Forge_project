"""
Fordge – Transparent Civic Grievance & Infrastructure Triage System
Backend: FastAPI + SQLite + Gemini API + Open311 GeoReport v2
"""
import os
import math
import uuid
import csv
import io
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from database import engine, AsyncSessionLocal, Base
from models import Report, ReportTimeline, Comment, Citizen, StatusEnum, SeverityEnum
from gemini_service import analyze_report, ROUTING_MAP
from storage_service import save_media, UPLOAD_DIR
from email_service import (
    generate_and_store_otp,
    verify_otp_code,
    pop_otp,
    get_stored_otp_data,
    send_verification_email,
)
from sqlalchemy import select

load_dotenv()

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fordge Civic Triage API",
    version="2.0.0",
    description="Transparent Civic Grievance & Infrastructure Triage System with Gemini Multimodal AI and Open311 compliance.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Schemas ────────────────────────────────────────────────────────────────────
class ReportOut(BaseModel):
    id: str
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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
    phone: Optional[str]
    aadhaar_last4: str
    address: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterSendCodeRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    dob: str
    phone: Optional[str] = None
    aadhaar_last4: str
    address: str


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

    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=400, detail="First name and last name are required.")

    aadhaar_clean = payload.aadhaar_last4.strip()
    if len(aadhaar_clean) != 4 or not aadhaar_clean.isdigit():
        raise HTTPException(status_code=400, detail="Last 4 digits of Aadhaar must be exactly 4 digits.")

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
        "aadhaar_last4": aadhaar_clean,
        "address": address,
    }

    code = generate_and_store_otp(email, citizen_dict)

    loop = asyncio.get_event_loop()
    sent = await loop.run_in_executor(
        None,
        send_verification_email,
        email,
        code,
        "Citizen Registration Verification",
        first_name,
    )

    if not sent:
        print(f"[AUTH DEV FALLBACK] Registration code for {email}: {code}")
        return {
            "ok": True,
            "message": "Verification code dispatched to your email.",
            "dev_code": code,
        }

    return {"ok": True, "message": "Verification code sent to your email inbox."}


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
                aadhaar_last4=citizen_info["aadhaar_last4"],
                address=citizen_info["address"],
                is_verified=True,
            )
            session.add(citizen)
            await session.commit()
            await session.refresh(citizen)

    pop_otp(email)
    token = f"civic_{uuid.uuid4().hex}"

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
            "aadhaar_last4": citizen.aadhaar_last4,
            "address": citizen.address,
            "verified": True,
        },
    }


@app.post("/api/auth/login-send-code")
async def login_send_code(payload: LoginSendCodeRequest):
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Citizen).where(Citizen.email == email))
        citizen = result.scalar_one_or_none()
        if not citizen:
            raise HTTPException(
                status_code=404,
                detail="This email is not registered. Want to create an account?",
            )

    code = generate_and_store_otp(email, {"citizen_id": citizen.id})

    loop = asyncio.get_event_loop()
    sent = await loop.run_in_executor(
        None,
        send_verification_email,
        email,
        code,
        "Citizen Sign-In Verification",
        citizen.first_name,
    )

    if not sent:
        print(f"[AUTH DEV FALLBACK] Login code for {email}: {code}")
        return {
            "ok": True,
            "message": "Verification code dispatched to your email.",
            "dev_code": code,
        }

    return {"ok": True, "message": "Verification code sent to your email inbox."}


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
    token = f"civic_{uuid.uuid4().hex}"

    if citizen:
        user_data = {
            "id": citizen.id,
            "first_name": citizen.first_name,
            "last_name": citizen.last_name,
            "email": citizen.email,
            "dob": citizen.dob,
            "phone": citizen.phone,
            "aadhaar_last4": citizen.aadhaar_last4,
            "address": citizen.address,
            "verified": True,
        }
    else:
        user_data = {
            "email": email,
            "verified": True,
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
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    citizen_email: Optional[str] = Form(None),
    media: Optional[UploadFile] = File(None),
):
    report_id = str(uuid.uuid4())
    media_url = None
    content = None

    # Save uploaded media (Supabase storage or local disk)
    if media and media.filename:
        ext = Path(media.filename).suffix or ".jpg"
        filename = f"{report_id}{ext}"
        content = await media.read()
        media_url = await save_media(filename, content, media.content_type)

    # AI multimodal analysis
    analysis_res = await analyze_report(
        title=title,
        description=description,
        category=category,
        location=location,
        media_path=str(UPLOAD_DIR / f"{report_id}{Path(media.filename).suffix}") if media and media.filename else None,
        media_bytes=content if media and media.filename else None,
        media_mime=media.content_type if media else None,
    )

    severity_str = analysis_res.get("severity", "medium")
    severity = SeverityEnum(severity_str)
    routed_to = analysis_res.get("routed_to") or ROUTING_MAP.get(category, ROUTING_MAP["other"])
    action_plan = analysis_res.get("action_plan")
    safety_precautions = analysis_res.get("safety_precautions")
    sla_hours = analysis_res.get("sla_hours", 72)
    ai_analysis = analysis_res.get("ai_analysis")

    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        citizen_id = None
        if citizen_email:
            clean_email = citizen_email.strip().lower()
            res = await session.execute(select(Citizen).where(Citizen.email == clean_email))
            cit = res.scalar_one_or_none()
            if cit:
                citizen_id = cit.id

        report = Report(
            id=report_id,
            citizen_id=citizen_id,
            citizen_email=citizen_email.strip().lower() if citizen_email else None,
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
            notes=f"Civic grievance registered at {location}.",
            media_url=media_url,
        )

        await log_timeline(
            session=session,
            report_id=report_id,
            status=StatusEnum.open.value,
            actor="Fordge AI Triage",
            action_type="ai_triage",
            notes=f"Assessed severity: {severity_str.upper()}. Routed to {routed_to}. Target SLA: {sla_hours} hours.",
        )

        await session.commit()
        await session.refresh(report)
        return report


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
        filename = f"fordge_civic_reports_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    actor: str = "Authorized Official",
):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        report.status = StatusEnum(status)
        now = datetime.utcnow()
        report.updated_at = now
        if status in [StatusEnum.resolved.value, StatusEnum.closed.value] and not report.resolved_at:
            report.resolved_at = now

        if note:
            report.resolution_notes = note

        await log_timeline(
            session=session,
            report_id=report_id,
            status=status,
            actor=actor,
            action_type="status_update",
            notes=note or f"Ticket status transitioned to {status.replace('_', ' ').title()}.",
        )

        await session.commit()
        return {"message": "Status updated", "status": status}


@app.post("/api/reports/{report_id}/resolve", response_model=ReportOut)
async def resolve_report_with_proof(
    report_id: str,
    status: str = Form("resolved"),
    resolution_notes: str = Form(...),
    actor: str = Form("Municipal Engineer"),
    media: Optional[UploadFile] = File(None),
):
    """Closeout ticket with verified resolution notes and photographic completion proof"""
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        resolved_media_url = None
        if media and media.filename:
            ext = Path(media.filename).suffix or ".jpg"
            filename = f"resolved_{report_id}{ext}"
            content = await media.read()
            resolved_media_url = await save_media(filename, content, media.content_type)
            report.resolved_media_url = resolved_media_url

        report.status = StatusEnum(status)
        report.resolution_notes = resolution_notes
        now = datetime.utcnow()
        report.resolved_at = now
        report.updated_at = now

        await log_timeline(
            session=session,
            report_id=report_id,
            status=status,
            actor=actor,
            action_type="resolution_proof",
            notes=f"Issue resolved: {resolution_notes}",
            media_url=resolved_media_url,
        )

        await session.commit()
        await session.refresh(report)
        return report


@app.post("/api/reports/{report_id}/upvote")
async def upvote_report(report_id: str):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")
        report.upvotes += 1
        report.updated_at = datetime.utcnow()
        await session.commit()
        return {"upvotes": report.upvotes}


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
async def add_comment(report_id: str, body: CommentIn):
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        r = await session.execute(select(Report).where(Report.id == report_id))
        report = r.scalar_one_or_none()
        if not report:
            raise HTTPException(404, "Report not found")

        comment = Comment(
            id=str(uuid.uuid4()),
            report_id=report_id,
            author=body.author[:100] or "Anonymous",
            role=body.role if body.role in ("citizen", "authority") else "citizen",
            content=body.content,
            created_at=datetime.utcnow(),
        )
        session.add(comment)

        # Log timeline comment note if official
        if body.role == "authority":
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
