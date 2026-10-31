"""SQLAlchemy ORM models"""
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean, Enum as SAEnum, ForeignKey
from database import Base


class StatusEnum(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class SeverityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(String(36), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    dob = Column(String(20), nullable=False)  # Date of birth (YYYY-MM-DD)
    phone = Column(String(30), nullable=True)  # Optional phone number
    aadhaar_last4 = Column(String(4), nullable=True)  # Deprecated / Nullable statutory identifier
    address = Column(Text, nullable=False)  # Primary residence address
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True)
    citizen_id = Column(String(36), ForeignKey("citizens.id", ondelete="SET NULL"), nullable=True, index=True)
    citizen_email = Column(String(255), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    location = Column(String(300), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    severity = Column(SAEnum(SeverityEnum), default=SeverityEnum.medium)
    status = Column(SAEnum(StatusEnum), default=StatusEnum.open)
    ai_analysis = Column(Text, nullable=True)
    action_plan = Column(Text, nullable=True)
    safety_precautions = Column(Text, nullable=True)
    sla_hours = Column(Integer, default=72)
    routed_to = Column(String(200), nullable=True)
    upvotes = Column(Integer, default=0)
    media_url = Column(String(500), nullable=True)
    resolved_media_url = Column(String(500), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    # Agentic triage pipeline audit fields
    agent_trace = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    severity_rationale = Column(Text, nullable=True)
    detected_language = Column(String(50), nullable=True)
    locality = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReportTimeline(Base):
    __tablename__ = "report_timeline"

    id = Column(String(36), primary_key=True)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False, default="System")
    action_type = Column(String(50), nullable=False, default="status_update")
    notes = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(String(36), primary_key=True)
    report_id = Column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    author = Column(String(100), nullable=False, default="Anonymous")
    role = Column(String(50), nullable=False, default="citizen")  # "citizen" | "authority"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
