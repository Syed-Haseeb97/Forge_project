"""Pydantic schemas for the agentic triage pipeline and API responses."""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class EvidenceAnalysis(BaseModel):
    detected_language: str = Field(
        default="English",
        description="Detected language of citizen input (e.g. English, Hindi, Hinglish, Tamil, Bengali, Telugu, Marathi)"
    )
    transcript: Optional[str] = Field(
        default=None,
        description="Verbatim or summarized transcript if audio evidence is provided"
    )
    issue_type: str = Field(
        ...,
        description="Specific infrastructure or civic defect observed (e.g. pothole, ruptured pipeline, collapsed culvert, overflowing garbage bin)"
    )
    visible_hazards: List[str] = Field(
        default_factory=list,
        description="List of immediate risks observed in evidence (e.g. exposed live cables, deep road cavity, flooding risk, structural cracks)"
    )
    estimated_dimensions: Optional[str] = Field(
        default=None,
        description="Estimated physical size or extent (e.g. 'approx 1.5m diameter, 20cm depth' or '50m section of pavement')"
    )
    evidence_severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Initial severity assessed purely from visual/audio evidence"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence score of evidence understanding between 0.0 and 1.0"
    )


class TriageDecision(BaseModel):
    final_severity: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Final evaluated priority level after correlating environmental, weather, and sensitive site context"
    )
    sla_hours: int = Field(
        ...,
        description="Target SLA resolution turnaround in hours. Must be one of 24, 72, 168, or 336"
    )
    department: str = Field(
        ...,
        description="Responsible municipal department or utility board"
    )
    safety_advice: str = Field(
        ...,
        description="Actionable safety precaution for pedestrians, motorists, and nearby residents"
    )
    action_plan: str = Field(
        ...,
        description="Engineering dispatch protocol or repair workflow"
    )
    rationale: str = Field(
        ...,
        description="Detailed justification explicitly citing which environmental/recurrence/weather signals influenced or escalated the decision"
    )
    confidence: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence in final triage decision between 0.0 and 1.0"
    )


class PrefillSuggestion(BaseModel):
    title: str = Field(
        ...,
        description="Concise, descriptive title for the incident (e.g. 'Hazardous deep pothole on arterial road')"
    )
    category: Literal[
        "road_damage",
        "bridge_damage",
        "water_leak",
        "pollution",
        "streetlight",
        "garbage",
        "drainage",
        "other",
    ] = Field(
        ...,
        description="Primary infrastructure category"
    )
    description: str = Field(
        ...,
        description="Detailed description summarizing the observable defect, hazards, and surrounding context"
    )
    detected_language: str = Field(
        default="English",
        description="Language detected from the evidence or text"
    )


class TraceStep(BaseModel):
    step: str
    tool: str
    status: Literal["success", "skipped", "error", "fallback"]
    duration_ms: int
    summary: str
    data: Optional[Dict[str, Any]] = None


class DispatchDraft(BaseModel):
    subject: str = Field(
        ...,
        description="Formal bureaucratic subject line with docket ID, locality, and priority"
    )
    body_english: str = Field(
        ...,
        description="Formal dispatch work order in English detailing the incident, coordinates, hazards, SLA deadline, and required departmental work order"
    )
    body_regional: Optional[str] = Field(
        default=None,
        description="Full formal letter translation in the citizen's detected language if not English, otherwise null"
    )


class ResolutionVerification(BaseModel):
    verdict: Literal["fixed", "partially_fixed", "not_fixed", "different_location", "unclear"] = Field(
        ...,
        description="Visual verification verdict comparing before vs after repair images"
    )
    confidence: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Confidence rating of repair verification"
    )
    explanation: str = Field(
        ...,
        description="Detailed visual comparison explaining whether the physical defect was remediated, unchanged, or taken at a different angle/location"
    )


class CivicBriefDraft(BaseModel):
    brief: str = Field(
        ...,
        description="Concise civic intelligence pulse brief synthesizing live counts, hotspots, and department bottlenecks. Must use only provided numbers."
    )
    recommended_actions: List[str] = Field(
        ...,
        min_items=3,
        max_items=3,
        description="Exactly 3 actionable, prioritized municipal interventions."
    )


class ExplanationOut(BaseModel):
    report_id: str
    lang: str
    text: str
    cached: bool = False


