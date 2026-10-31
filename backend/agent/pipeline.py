"""Jan Aawaz Agentic Triage Pipeline.

Orchestrates multi-step civic triage:
1. understand_evidence (multimodal Gemini)
2. reverse_geocode (Nominatim API)
3. weather (Open-Meteo API)
4. sensitive_sites (Overpass API)
5. recurrence (Database proximity)
6. decide (Gemini correlation decision)
7. fallback (Honest heuristic fallback if Gemini is unavailable)
"""
import os
import time
import json
import logging
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

from agent.schemas import (
    EvidenceAnalysis,
    TriageDecision,
    PrefillSuggestion,
)
from agent.tools import (
    reverse_geocode,
    get_weather,
    get_sensitive_sites,
    get_recurrence,
)

logger = logging.getLogger("janaawaz.agent.pipeline")

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

DEFAULT_SLA_MAP = {
    "critical": 24,
    "high": 72,
    "medium": 168,
    "low": 336,
}

ROUTING_MAP = {
    "road_damage": "Public Works Department",
    "bridge_damage": "Civil Engineering Division",
    "water_leak": "Water & Sewage Authority",
    "pollution": "Environmental Protection Agency",
    "streetlight": "Electricity Board",
    "garbage": "Municipal Sanitation Department",
    "drainage": "Storm Water Management",
    "other": "General Civic Administration",
}


def _get_models() -> List[str]:
    raw = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Could not initialize genai.Client: {e}")
        return None


def _clamp_severity(evidence_sev: str, decided_sev: str) -> str:
    """Enforce rule: final severity may differ from evidence_severity by at most one level."""
    if evidence_sev not in SEVERITY_LEVELS:
        evidence_sev = "medium"
    if decided_sev not in SEVERITY_LEVELS:
        decided_sev = evidence_sev

    idx_ev = SEVERITY_LEVELS.index(evidence_sev)
    idx_dec = SEVERITY_LEVELS.index(decided_sev)

    if abs(idx_dec - idx_ev) <= 1:
        return decided_sev
    elif idx_dec > idx_ev:
        return SEVERITY_LEVELS[idx_ev + 1]
    else:
        return SEVERITY_LEVELS[idx_ev - 1]


async def run_agent_pipeline(
    title: str,
    description: str,
    category: str,
    location: str = "Unspecified",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    media_bytes: Optional[bytes] = None,
    media_mime: Optional[str] = None,
    db_session=None,
) -> Dict[str, Any]:
    """Execute the full agentic civic grievance triage pipeline."""
    trace: List[Dict[str, Any]] = []
    client = _get_client()
    models = _get_models()

    # Context values to populate across steps
    evidence_res: Optional[EvidenceAnalysis] = None
    geocode_res: Dict[str, Any] = {"locality": None, "road": None, "city": None}
    weather_res: Dict[str, Any] = {"current_precipitation_mm": 0, "max_precip_probability_24h": 0, "summary": "N/A"}
    sites_res: Dict[str, Any] = {"count": 0, "sites": [], "summary": "N/A"}
    recurrence_res: Dict[str, Any] = {"count": 0, "summary": "N/A"}

    # -------------------------------------------------------------
    # Step 1: understand_evidence (Gemini multimodal, structured)
    # -------------------------------------------------------------
    t0 = time.time()
    if client:
        prompt_parts: List[Any] = []
        if media_bytes and media_mime:
            prompt_parts.append(types.Part.from_bytes(data=media_bytes, mime_type=media_mime))

        sys_prompt = (
            "You are a municipal safety engineer and civic multimodal triage expert. "
            "Analyze the provided photographic/audio/textual civic grievance evidence. "
            "Identify the exact language (e.g. English, Hindi, Hinglish, Tamil, Telugu, Marathi, Bengali), "
            "transcribe any speech if audio, specify the structural issue type, list visible hazards, "
            "estimate physical dimensions where visible, and assign initial evidence-based severity "
            "(low, medium, high, critical) with confidence."
        )
        user_text = (
            f"Title: {title}\n"
            f"Category: {category}\n"
            f"Location text: {location}\n"
            f"Description: {description}"
        )
        prompt_parts.append(types.Part.from_text(text=f"{sys_prompt}\n\n{user_text}"))

        for model_name in models:
            try:
                t_sub0 = time.time()
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=EvidenceAnalysis,
                    ),
                )
                dur = int((time.time() - t_sub0) * 1000)
                if resp.text:
                    evidence_res = EvidenceAnalysis.model_validate_json(resp.text)
                    trace.append({
                        "step": "understand_evidence",
                        "tool": f"gemini_multimodal ({model_name})",
                        "status": "success",
                        "duration_ms": dur,
                        "summary": (
                            f"Identified {evidence_res.issue_type} in {evidence_res.detected_language} "
                            f"(Evidence Severity: {evidence_res.evidence_severity.upper()}, "
                            f"Hazards: {len(evidence_res.visible_hazards)})"
                        ),
                        "data": evidence_res.model_dump(),
                    })
                    break
            except Exception as e:
                logger.warning(f"understand_evidence failed on {model_name}: {e}")

    if not evidence_res:
        dur = int((time.time() - t0) * 1000)
        # Fallback evidence assessment
        evidence_res = EvidenceAnalysis(
            detected_language="English",
            transcript=None,
            issue_type=category.replace("_", " "),
            visible_hazards=["Unverified field report requiring inspection"],
            estimated_dimensions="Not visually discernible",
            evidence_severity="medium",
            confidence=0.7,
        )
        trace.append({
            "step": "understand_evidence",
            "tool": "heuristic_parser",
            "status": "fallback" if client else "skipped",
            "duration_ms": dur,
            "summary": f"Initial evidence parsed via text heuristics ({evidence_res.evidence_severity.upper()})",
            "data": evidence_res.model_dump(),
        })

    # -------------------------------------------------------------
    # Step 2: reverse_geocode (Nominatim reverse API)
    # -------------------------------------------------------------
    t0 = time.time()
    try:
        geocode_res = await reverse_geocode(latitude, longitude)
        dur = int((time.time() - t0) * 1000)
        loc_str = geocode_res.get("locality") or geocode_res.get("road") or geocode_res.get("city") or location
        trace.append({
            "step": "reverse_geocode",
            "tool": "nominatim_osm",
            "status": "success" if geocode_res.get("locality") or geocode_res.get("city") else "skipped",
            "duration_ms": dur,
            "summary": f"Resolved location to {loc_str}",
            "data": geocode_res,
        })
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "reverse_geocode",
            "tool": "nominatim_osm",
            "status": "error",
            "duration_ms": dur,
            "summary": f"Geocoding degraded: {e}",
            "data": {"locality": None},
        })

    # -------------------------------------------------------------
    # Step 3: weather (Open-Meteo forecast API)
    # -------------------------------------------------------------
    t0 = time.time()
    try:
        weather_res = await get_weather(latitude, longitude)
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "weather",
            "tool": "open_meteo",
            "status": "success",
            "duration_ms": dur,
            "summary": weather_res.get("summary", "Weather checked"),
            "data": weather_res,
        })
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "weather",
            "tool": "open_meteo",
            "status": "error",
            "duration_ms": dur,
            "summary": f"Weather fetch degraded: {e}",
            "data": weather_res,
        })

    # -------------------------------------------------------------
    # Step 4: sensitive_sites (Overpass API, 250m)
    # -------------------------------------------------------------
    t0 = time.time()
    try:
        sites_res = await get_sensitive_sites(latitude, longitude, radius_m=250)
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "sensitive_sites",
            "tool": "overpass_osm",
            "status": "success" if sites_res.get("count", 0) > 0 else "skipped",
            "duration_ms": dur,
            "summary": sites_res.get("summary", "Sensitive sites evaluated"),
            "data": sites_res,
        })
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "sensitive_sites",
            "tool": "overpass_osm",
            "status": "error",
            "duration_ms": dur,
            "summary": f"Sensitive sites scan degraded: {e}",
            "data": sites_res,
        })

    # -------------------------------------------------------------
    # Step 5: recurrence (Database nearby open reports within 300m)
    # -------------------------------------------------------------
    t0 = time.time()
    try:
        recurrence_res = await get_recurrence(latitude, longitude, category, session=db_session, radius_m=300)
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "recurrence",
            "tool": "municipal_database",
            "status": "success",
            "duration_ms": dur,
            "summary": recurrence_res.get("summary", "Recurrence evaluated"),
            "data": recurrence_res,
        })
    except Exception as e:
        dur = int((time.time() - t0) * 1000)
        trace.append({
            "step": "recurrence",
            "tool": "municipal_database",
            "status": "error",
            "duration_ms": dur,
            "summary": f"Recurrence lookup degraded: {e}",
            "data": recurrence_res,
        })

    # -------------------------------------------------------------
    # Step 6: decide (Gemini structured triage decision)
    # -------------------------------------------------------------
    t0 = time.time()
    decision_res: Optional[TriageDecision] = None

    if client:
        correlation_context = (
            f"=== SENSOR & REGISTRY SIGNALS ===\n"
            f"1. Visual/Evidence Assessment: {evidence_res.evidence_severity.upper()} severity. "
            f"Hazards: {', '.join(evidence_res.visible_hazards) or 'None'}. "
            f"Dimensions: {evidence_res.estimated_dimensions or 'N/A'}.\n"
            f"2. Geographic Locality: {geocode_res.get('locality') or 'Unknown'}, Road: {geocode_res.get('road') or 'Unknown'}, City: {geocode_res.get('city') or 'Unknown'}.\n"
            f"3. Weather Context: {weather_res.get('summary')}.\n"
            f"4. Sensitive Public Sites (250m): {sites_res.get('summary')}.\n"
            f"5. Cluster Recurrence (300m): {recurrence_res.get('summary')}.\n"
        )

        decision_prompt = (
            "You are the Lead Municipal Dispatcher. Formulate the final triage decision.\n"
            "MANDATORY CONSTRAINTS:\n"
            "- Final severity MUST be one of: 'low', 'medium', 'high', 'critical'.\n"
            "- The final severity MAY differ from evidence_severity by AT MOST one level (e.g. medium -> high, or high -> critical). "
            "Never jump two levels.\n"
            "- sla_hours MUST be exactly one of: 24 (critical), 72 (high), 168 (medium), 336 (low).\n"
            "- rationale MUST explicitly cite which specific signals (e.g. rain forecast, nearby schools/hospitals, or recurring open complaints) "
            "influenced or validated the final severity decision.\n"
            "- Provide department, safety_advice, and actionable engineering action_plan.\n\n"
            f"Incident: {title}\n"
            f"Category: {category}\n"
            f"Description: {description}\n\n"
            f"{correlation_context}"
        )

        for model_name in models:
            try:
                t_sub0 = time.time()
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=decision_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=TriageDecision,
                    ),
                )
                dur = int((time.time() - t_sub0) * 1000)
                if resp.text:
                    decision_res = TriageDecision.model_validate_json(resp.text)
                    # Enforce clamp strictly
                    clamped_sev = _clamp_severity(evidence_res.evidence_severity, decision_res.final_severity)
                    if clamped_sev != decision_res.final_severity:
                        decision_res.final_severity = clamped_sev
                        decision_res.sla_hours = DEFAULT_SLA_MAP.get(clamped_sev, decision_res.sla_hours)

                    trace.append({
                        "step": "decide",
                        "tool": f"gemini_decision_agent ({model_name})",
                        "status": "success",
                        "duration_ms": dur,
                        "summary": f"Assigned final {decision_res.final_severity.upper()} severity ({decision_res.sla_hours}h SLA) to {decision_res.department}",
                        "data": decision_res.model_dump(),
                    })
                    break
            except Exception as e:
                logger.warning(f"decide failed on {model_name}: {e}")

    # -------------------------------------------------------------
    # Step 7: Fallback heuristic if Gemini failed entirely
    # -------------------------------------------------------------
    if not decision_res:
        dur = int((time.time() - t0) * 1000)
        from gemini_service import _fallback_triage
        fb = _fallback_triage(title, description, category)

        # Apply basic environmental bump if heavy rain or sensitive sites exist
        fallback_sev = fb["severity"]
        signals_cited: List[str] = []
        if weather_res.get("heavy_rain_risk"):
            signals_cited.append("heavy rain risk")
        if sites_res.get("count", 0) > 0:
            signals_cited.append(f"{sites_res['count']} sensitive site(s)")
        if recurrence_res.get("count", 0) > 0:
            signals_cited.append(f"{recurrence_res['count']} nearby recurring complaints")

        if signals_cited and fallback_sev in ["low", "medium"]:
            next_sev = {"low": "medium", "medium": "high"}[fallback_sev]
            rationale = f"Escalated {fallback_sev} to {next_sev}: detected {', '.join(signals_cited)}."
            fallback_sev = next_sev
        else:
            rationale = f"Evaluated based on primary heuristic keywords: {', '.join(signals_cited) if signals_cited else 'standard parameters'}."

        decision_res = TriageDecision(
            final_severity=fallback_sev,
            sla_hours=DEFAULT_SLA_MAP.get(fallback_sev, 72),
            department=fb.get("suggested_department", ROUTING_MAP.get(category, "General Administration")),
            safety_advice=fb["safety_precautions"],
            action_plan=fb["recommended_action"],
            rationale=rationale,
            confidence=0.75,
        )

        trace.append({
            "step": "decide",
            "tool": "heuristic_fallback_agent",
            "status": "fallback",
            "duration_ms": dur,
            "summary": f"Fallback rule evaluation: {decision_res.final_severity.upper()} priority ({decision_res.sla_hours}h SLA)",
            "data": decision_res.model_dump(),
        })

    # Compile unified analysis text for backward compatibility
    full_analysis = f"{decision_res.action_plan}\n\n**Recommended Action:** {decision_res.action_plan}"

    return {
        "ai_analysis": full_analysis,
        "severity": decision_res.final_severity,
        "action_plan": decision_res.action_plan,
        "safety_precautions": decision_res.safety_advice,
        "sla_hours": decision_res.sla_hours,
        "routed_to": decision_res.department,
        # New agentic fields to persist
        "agent_trace": trace,
        "confidence": float(decision_res.confidence),
        "severity_rationale": decision_res.rationale,
        "detected_language": evidence_res.detected_language,
        "locality": geocode_res.get("locality") or geocode_res.get("city") or location,
        "visible_hazards": evidence_res.visible_hazards,
        "evidence_severity": evidence_res.evidence_severity,
    }


async def prefill_from_media(
    media_bytes: Optional[bytes] = None,
    media_mime: Optional[str] = None,
    text_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate smart autofill suggestions (title, category, description, language) from photo/voice evidence."""
    client = _get_client()
    models = _get_models()

    if client and (media_bytes or text_hint):
        prompt_parts: List[Any] = []
        if media_bytes and media_mime:
            prompt_parts.append(types.Part.from_bytes(data=media_bytes, mime_type=media_mime))

        sys_prompt = (
            "You are an assistant for Jan Aawaz civic reporting. "
            "Analyze the attached photo, audio recording, or preliminary text notes. "
            "Provide an appropriate, concise civic incident title (3-7 words), "
            "categorize it into EXACTLY ONE OF: road_damage, bridge_damage, water_leak, pollution, "
            "streetlight, garbage, drainage, other. "
            "Draft a helpful description detailing the observable defect and context, "
            "and specify the detected language (e.g. English, Hindi, Hinglish, Tamil, Telugu, etc.)."
        )
        if text_hint:
            sys_prompt += f"\nCitizen's rough notes: {text_hint}"

        prompt_parts.append(types.Part.from_text(text=sys_prompt))

        for model_name in models:
            try:
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=PrefillSuggestion,
                    ),
                )
                if resp.text:
                    prefill = PrefillSuggestion.model_validate_json(resp.text)
                    return prefill.model_dump()
            except Exception as e:
                logger.warning(f"prefill_from_media failed on {model_name}: {e}")

    # Fallback default suggestion
    category = "other"
    if text_hint:
        t = text_hint.lower()
        if any(w in t for w in ["pothole", "road", "tar", "asphalt"]):
            category = "road_damage"
        elif any(w in t for w in ["pipe", "water", "leak", "burst"]):
            category = "water_leak"
        elif any(w in t for w in ["trash", "garbage", "waste", "dump"]):
            category = "garbage"
        elif any(w in t for w in ["drain", "sewage", "gutter", "clog"]):
            category = "drainage"
        elif any(w in t for w in ["light", "dark", "pole", "wire"]):
            category = "streetlight"

    return {
        "title": text_hint[:60] if text_hint else "Reported Civic Hazard",
        "category": category,
        "description": text_hint or "Civic infrastructure issue observed at site requiring departmental attention.",
        "detected_language": "English",
    }
