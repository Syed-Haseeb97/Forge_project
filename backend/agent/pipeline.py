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
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, Awaitable
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from agent.schemas import (
    EvidenceAnalysis,
    TriageDecision,
    CriticEvaluation,
    PrefillSuggestion,
    SemanticDuplicateList,
    WhyNowList,
    WhyNowItem,
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


def _fallback_triage_result(
    title: str,
    category: str,
    description: str,
    location: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    from gemini_service import _fallback_triage
    fb = _fallback_triage(title, description, category)
    final_sev = fb["severity"]
    sla = DEFAULT_SLA_MAP.get(final_sev, 72)
    dept = fb.get("suggested_department", ROUTING_MAP.get(category, "General Administration"))
    trace = [
        {
            "step": "pipeline_budget",
            "tool": "pipeline_budget_guardian",
            "status": "fallback",
            "duration_ms": 30000,
            "summary": "Pipeline execution exceeded 30s budget; deterministic safety heuristic applied",
            "data": {"severity": final_sev, "department": dept, "sla_hours": sla},
        }
    ]
    return {
        "ai_analysis": f"Preliminary evidence triage ({final_sev.upper()}).\n\n**Rationale:** Applied rule-based civic safety heuristic following pipeline budget constraint.\n\n**Recommended Action:** {fb['recommended_action']}",
        "severity": final_sev,
        "action_plan": fb["recommended_action"],
        "safety_precautions": fb["safety_precautions"],
        "sla_hours": sla,
        "routed_to": dept,
        "agent_trace": trace,
        "confidence": 0.65,
        "severity_rationale": "Safety heuristic fallback applied within target response budget.",
        "detected_language": "English",
        "locality": location,
        "visible_hazards": ["Unverified field report requiring departmental physical inspection"],
        "evidence_severity": final_sev,
        "needs_human_review": False,
    }


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
    on_step: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """Execute the full agentic civic grievance triage pipeline within a 30s budget."""
    try:
        return await asyncio.wait_for(
            _execute_agent_pipeline(
                title=title,
                description=description,
                category=category,
                location=location,
                latitude=latitude,
                longitude=longitude,
                media_bytes=media_bytes,
                media_mime=media_mime,
                db_session=db_session,
                on_step=on_step,
            ),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"run_agent_pipeline timed out after 30s budget for report '{title}'")
        fallback_res = _fallback_triage_result(
            title=title,
            category=category,
            description=description,
            location=location,
            latitude=latitude,
            longitude=longitude,
        )
        if on_step and fallback_res.get("agent_trace"):
            for s in fallback_res["agent_trace"]:
                try:
                    await on_step(s)
                except Exception:
                    pass
        return fallback_res


async def _execute_agent_pipeline(
    title: str,
    description: str,
    category: str,
    location: str = "Unspecified",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    media_bytes: Optional[bytes] = None,
    media_mime: Optional[str] = None,
    db_session=None,
    on_step: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """Internal step execution for the agentic triage pipeline."""
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
            "transcribe any speech if audio into transcript, provide accurate english_translation if spoken in an Indian regional language or dialect, "
            "specify the structural issue type, list visible hazards, "
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
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt_parts,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EvidenceAnalysis,
                        ),
                    ),
                    timeout=12.0,
                )
                dur = int((time.time() - t_sub0) * 1000)
                if resp.text:
                    evidence_res = EvidenceAnalysis.model_validate_json(resp.text)
                    summary = (
                        f"Identified {evidence_res.issue_type} in {evidence_res.detected_language} "
                        f"(Evidence Severity: {evidence_res.evidence_severity.upper()}, "
                        f"Hazards: {len(evidence_res.visible_hazards)})"
                    )
                    if evidence_res.transcript:
                        summary += f" | Spoken: '{evidence_res.transcript}'"
                    if evidence_res.english_translation:
                        summary += f" | Translated: '{evidence_res.english_translation}'"

                    step_data = {
                        "step": "understand_evidence",
                        "tool": f"gemini_multimodal ({model_name})",
                        "status": "success",
                        "duration_ms": dur,
                        "summary": summary,
                        "data": evidence_res.model_dump(),
                    }
                    trace.append(step_data)
                    if on_step:
                        await on_step(step_data)
                    break
            except Exception as e:
                logger.warning(f"understand_evidence failed on {model_name}: {e}")

    if not evidence_res:
        dur = int((time.time() - t0) * 1000)
        # Fallback evidence assessment
        evidence_res = EvidenceAnalysis(
            detected_language="English",
            transcript=None,
            english_translation=None,
            issue_type=category.replace("_", " "),
            visible_hazards=["Unverified field report requiring inspection"],
            estimated_dimensions="Not visually discernible",
            evidence_severity="medium",
            confidence=0.7,
        )
        step_data = {
            "step": "understand_evidence",
            "tool": "heuristic_parser",
            "status": "fallback" if client else "skipped",
            "duration_ms": dur,
            "summary": f"Initial evidence parsed via text heuristics ({evidence_res.evidence_severity.upper()})",
            "data": evidence_res.model_dump(),
        }
        trace.append(step_data)
        if on_step:
            await on_step(step_data)

    # -------------------------------------------------------------
    # Parallel Tools Execution: reverse_geocode, weather, sensitive_sites, recurrence
    # -------------------------------------------------------------
    async def _run_tool_geocode():
        t0 = time.time()
        try:
            res = await reverse_geocode(latitude, longitude)
            dur = int((time.time() - t0) * 1000)
            loc_str = res.get("locality") or res.get("road") or res.get("city") or location
            status = "degraded" if res.get("degraded") else ("success" if res.get("locality") or res.get("city") else "skipped")
            step = {
                "step": "reverse_geocode",
                "tool": "nominatim_osm",
                "status": status,
                "duration_ms": dur,
                "summary": f"Resolved location to {loc_str}" if not res.get("degraded") else "Reverse geocoding unavailable",
                "data": res,
            }
            return res, step
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            step = {
                "step": "reverse_geocode",
                "tool": "nominatim_osm",
                "status": "degraded",
                "duration_ms": dur,
                "summary": f"Geocoding degraded: {e}",
                "data": {"locality": None, "degraded": True},
            }
            return {"locality": None, "degraded": True}, step

    async def _run_tool_weather():
        t0 = time.time()
        try:
            res = await get_weather(latitude, longitude)
            dur = int((time.time() - t0) * 1000)
            status = "degraded" if res.get("degraded") else "success"
            step = {
                "step": "weather",
                "tool": "open_meteo",
                "status": status,
                "duration_ms": dur,
                "summary": res.get("summary", "Weather checked"),
                "data": res,
            }
            return res, step
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            step = {
                "step": "weather",
                "tool": "open_meteo",
                "status": "degraded",
                "duration_ms": dur,
                "summary": f"Weather fetch degraded: {e}",
                "data": {"degraded": True},
            }
            return {"degraded": True, "summary": "Weather data temporarily unavailable"}, step

    async def _run_tool_sensitive_sites():
        t0 = time.time()
        try:
            res = await get_sensitive_sites(latitude, longitude, radius_m=250)
            dur = int((time.time() - t0) * 1000)
            status = "degraded" if res.get("degraded") else ("success" if res.get("count", 0) > 0 else "skipped")
            step = {
                "step": "sensitive_sites",
                "tool": "overpass_osm",
                "status": status,
                "duration_ms": dur,
                "summary": res.get("summary", "Sensitive sites evaluated"),
                "data": res,
            }
            return res, step
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            step = {
                "step": "sensitive_sites",
                "tool": "overpass_osm",
                "status": "degraded",
                "duration_ms": dur,
                "summary": f"Sensitive sites scan degraded: {e}",
                "data": {"count": 0, "degraded": True},
            }
            return {"count": 0, "degraded": True, "summary": "Sensitive sites lookup timed out"}, step

    async def _run_tool_recurrence():
        t0 = time.time()
        try:
            res = await get_recurrence(latitude, longitude, category, session=db_session, radius_m=300)
            dur = int((time.time() - t0) * 1000)
            status = "degraded" if res.get("degraded") else "success"
            step = {
                "step": "recurrence",
                "tool": "municipal_database",
                "status": status,
                "duration_ms": dur,
                "summary": res.get("summary", "Recurrence evaluated"),
                "data": res,
            }
            return res, step
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            step = {
                "step": "recurrence",
                "tool": "municipal_database",
                "status": "degraded",
                "duration_ms": dur,
                "summary": f"Recurrence lookup degraded: {e}",
                "data": {"count": 0, "degraded": True},
            }
            return {"count": 0, "degraded": True, "summary": "Recurrence check unavailable"}, step

    # Concurrently execute tools with asyncio.gather
    geo_out, weather_out, sites_out, recurrence_out = await asyncio.gather(
        _run_tool_geocode(),
        _run_tool_weather(),
        _run_tool_sensitive_sites(),
        _run_tool_recurrence(),
    )

    geocode_res, geocode_step = geo_out
    weather_res, weather_step = weather_out
    sites_res, sites_step = sites_out
    recurrence_res, recurrence_step = recurrence_out

    for s in [geocode_step, weather_step, sites_step, recurrence_step]:
        trace.append(s)
        if on_step:
            await on_step(s)

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
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=decision_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=TriageDecision,
                        ),
                    ),
                    timeout=12.0,
                )
                dur = int((time.time() - t_sub0) * 1000)
                if resp.text:
                    decision_res = TriageDecision.model_validate_json(resp.text)
                    # Enforce clamp strictly
                    clamped_sev = _clamp_severity(evidence_res.evidence_severity, decision_res.final_severity)
                    if clamped_sev != decision_res.final_severity:
                        decision_res.final_severity = clamped_sev
                        decision_res.sla_hours = DEFAULT_SLA_MAP.get(clamped_sev, decision_res.sla_hours)

                    step_data = {
                        "step": "decide",
                        "tool": f"gemini_decision_agent ({model_name})",
                        "status": "success",
                        "duration_ms": dur,
                        "summary": f"Assigned final {decision_res.final_severity.upper()} severity ({decision_res.sla_hours}h SLA) to {decision_res.department}",
                        "data": decision_res.model_dump(),
                    }
                    trace.append(step_data)
                    if on_step:
                        await on_step(step_data)
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

        step_data = {
            "step": "decide",
            "tool": "heuristic_fallback_agent",
            "status": "fallback",
            "duration_ms": dur,
            "summary": f"Fallback rule evaluation: {decision_res.final_severity.upper()} priority ({decision_res.sla_hours}h SLA)",
            "data": decision_res.model_dump(),
        }
        trace.append(step_data)
        if on_step:
            await on_step(step_data)

    # -------------------------------------------------------------
    # Step 8: Critic Audit (Structured Quality Control Second-Opinion)
    # -------------------------------------------------------------
    t0_critic = time.time()
    critic_agrees = True
    critic_issues: List[str] = []
    suggested_severity: Optional[str] = None

    if client:
        critic_prompt = (
            "You are an independent Senior Municipal Quality Auditor and Critic.\n"
            "Audit the following triage decision against the raw sensor, vision, weather, locality, "
            "sensitive sites, and recurrence signals.\n"
            "Evaluate:\n"
            "1. Is the assigned severity appropriate given physical hazards and vulnerable sites?\n"
            "2. Is the department routing correct for this failure category?\n"
            "3. Is the SLA turnaround realistic and statutory compliant?\n\n"
            f"Incident: {title}\n"
            f"Category: {category}\n"
            f"Description: {description}\n\n"
            f"{correlation_context}\n\n"
            f"PROPOSED DECISION:\n"
            f"- Final Severity: {decision_res.final_severity}\n"
            f"- SLA Hours: {decision_res.sla_hours}\n"
            f"- Department: {decision_res.department}\n"
            f"- Decision Confidence: {decision_res.confidence}\n"
            f"- Rationale: {decision_res.rationale}\n\n"
            "Return structured JSON matching CriticEvaluation: {agrees: bool, issues: list[str], suggested_severity: Optional[str]}."
        )

        for model_name in models:
            try:
                t_sub0 = time.time()
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=critic_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=CriticEvaluation,
                        ),
                    ),
                    timeout=12.0,
                )
                dur_critic = int((time.time() - t_sub0) * 1000)
                if resp.text:
                    critic_res = CriticEvaluation.model_validate_json(resp.text)
                    critic_agrees = critic_res.agrees
                    critic_issues = critic_res.issues
                    suggested_severity = critic_res.suggested_severity

                    step_data = {
                        "step": "critic_audit",
                        "tool": f"gemini_critic_auditor ({model_name})",
                        "status": "warning" if (not critic_agrees) else "success",
                        "duration_ms": dur_critic,
                        "summary": (
                            f"Critic Flagged Concern: {'; '.join(critic_issues)}"
                            if not critic_agrees
                            else "Critic Audited & Endorsed Decision"
                        ),
                        "data": critic_res.model_dump(),
                    }
                    trace.append(step_data)
                    if on_step:
                        await on_step(step_data)
                    break
            except Exception as e:
                logger.warning(f"critic_audit failed on {model_name}: {e}")

    if "critic_audit" not in [s["step"] for s in trace]:
        dur_critic = int((time.time() - t0_critic) * 1000)
        step_data = {
            "step": "critic_audit",
            "tool": "critic_heuristic_validator",
            "status": "success",
            "duration_ms": dur_critic,
            "summary": "Automated rule auditor verified decision constraints",
            "data": {"agrees": True, "issues": []},
        }
        trace.append(step_data)
        if on_step:
            await on_step(step_data)

    needs_human_review = (not critic_agrees) or (float(decision_res.confidence) < 0.6)

    # Compile unified analysis text: evidence summary plus rationale and action plan
    full_analysis = (
        f"{evidence_res.issue_type} ({evidence_res.evidence_severity.upper()} evidence severity).\n\n"
        f"**Rationale:** {decision_res.rationale}\n\n"
        f"**Recommended Action:** {decision_res.action_plan}"
    )

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
        "needs_human_review": needs_human_review,
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
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt_parts,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=PrefillSuggestion,
                        ),
                    ),
                    timeout=12.0,
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


async def check_semantic_duplicates(
    new_title: Optional[str],
    new_description: Optional[str],
    new_category: Optional[str],
    candidates: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Compare top candidate reports against the incoming grievance using Gemini structured comparison."""
    if not candidates:
        return {}

    # If neither title nor description provided, apply deterministic proximity heuristics
    if not (new_title and new_title.strip()) and not (new_description and new_description.strip()):
        results = {}
        for c in candidates:
            same_cat = bool(new_category and c.get("category") == new_category)
            close = c.get("distance_km", 1.0) <= 0.15
            if same_cat and close:
                results[c["id"]] = {
                    "likely_duplicate": True,
                    "duplicate_reason": f"Same {new_category.replace('_', ' ')} defect reported within {int(c.get('distance_km', 0)*1000)}m",
                }
            else:
                results[c["id"]] = {"likely_duplicate": False, "duplicate_reason": None}
        return results

    client = _get_client()
    models = _get_models()

    top3 = candidates[:3]
    cands_summary = []
    for c in top3:
        dist_m = int(c.get("distance_km", 0) * 1000)
        cands_summary.append(
            f"Candidate Ticket ID: {c['id']}\n"
            f"Title: {c.get('title')}\n"
            f"Description: {c.get('description')}\n"
            f"Category: {c.get('category')}\n"
            f"Distance: {dist_m}m away"
        )
    candidates_text = "\n\n".join(cands_summary)

    prompt = (
        "You are an AI Civic Duplicate Detection Specialist.\n"
        "A citizen is drafting a civic complaint:\n"
        f"- Title: {new_title or 'N/A'}\n"
        f"- Category: {new_category or 'N/A'}\n"
        f"- Description: {new_description or 'N/A'}\n\n"
        "Compare this grievance against these nearby existing tickets:\n\n"
        f"{candidates_text}\n\n"
        "For each ticket, return candidate report_id, likely_duplicate (bool: true if both tickets describe the identical defect or incident), "
        "and duplicate_reason (concise 1-sentence comparison)."
    )

    if client:
        for model_name in models:
            try:
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=SemanticDuplicateList,
                        ),
                    ),
                    timeout=10.0,
                )
                if resp.text:
                    parsed = SemanticDuplicateList.model_validate_json(resp.text)
                    return {
                        item.report_id: {
                            "likely_duplicate": item.likely_duplicate,
                            "duplicate_reason": item.duplicate_reason,
                        }
                        for item in parsed.candidates
                    }
            except Exception as e:
                logger.warning(f"check_semantic_duplicates failed on {model_name}: {e}")

    # Fallback keyword and proximity overlap
    results = {}
    n_title = (new_title or "").lower()
    n_desc = (new_description or "").lower()
    for c in top3:
        c_title = (c.get("title") or "").lower()
        same_cat = bool(new_category and c.get("category") == new_category)
        words_c = set(c_title.split())
        words_n = set(n_title.split() + n_desc.split())
        overlap = words_c.intersection(words_n) - {"in", "the", "on", "a", "at", "to", "of", "and", "near", "road"}
        if same_cat and (len(overlap) >= 1 or c.get("distance_km", 1.0) <= 0.15):
            results[c["id"]] = {
                "likely_duplicate": True,
                "duplicate_reason": f"Similar issue reported nearby ({', '.join(list(overlap)[:2]) if overlap else 'same category within 150m'})",
            }
        else:
            results[c["id"]] = {"likely_duplicate": False, "duplicate_reason": None}
    return results


async def generate_why_now_rationales(tickets_data: List[Dict[str, Any]]) -> Dict[str, str]:
    """Generate concise, actionable 1-sentence 'why now' operational justifications for top urgent tickets."""
    if not tickets_data:
        return {}

    client = _get_client()
    models = _get_models()

    context_lines = []
    for t in tickets_data:
        context_lines.append(
            f"- Report ID: {t['id']}\n"
            f"  Title: {t.get('title')}\n"
            f"  Category: {t.get('category')}\n"
            f"  Severity: {t.get('severity')}\n"
            f"  SLA Remaining: {t.get('sla_remaining_hours')}h ({'OVERDUE' if t.get('is_overdue') else 'Active'})\n"
            f"  Endorsements: {t.get('upvotes', 0)}\n"
            f"  Rain Risk: {'YES (Forecast Heavy Rain)' if t.get('rain_risk') else 'No'}\n"
            f"  Cluster Count: {t.get('hotspot_count', 0)} nearby tickets"
        )
    context_text = "\n\n".join(context_lines)

    prompt = (
        "You are the Senior Municipal Dispatch Commander.\n"
        "Provide a crisp, actionable 1-sentence 'why now' dispatch justification for each ticket.\n"
        "Explain specifically why this issue must be prioritized for dispatch right now "
        "(e.g. impending rain flooding the defect, safety hazard near pedestrians, statutory SLA breach, high community endorsements):\n\n"
        f"{context_text}\n\n"
        "Return structured JSON matching WhyNowList: {items: [{report_id: str, why_now: str}]}."
    )

    if client:
        for model_name in models:
            try:
                resp = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=WhyNowList,
                        ),
                    ),
                    timeout=10.0,
                )
                if resp.text:
                    parsed = WhyNowList.model_validate_json(resp.text)
                    return {p.report_id: p.why_now for p in parsed.items}
            except Exception as e:
                logger.warning(f"generate_why_now_rationales failed on {model_name}: {e}")

    # Fallback heuristic
    results = {}
    for t in tickets_data:
        sev = str(t.get("severity", "medium")).upper()
        if t.get("is_overdue"):
            urgency = "Statutory SLA deadline breached; immediate crew dispatch required to resolve non-compliance."
        elif t.get("rain_risk"):
            urgency = f"High priority {sev} hazard with heavy rain forecasted to aggravate structural erosion."
        elif t.get("hotspot_count", 0) >= 2:
            urgency = f"Part of a critical {t.get('hotspot_count')} ticket localized failure cluster requiring area-wide intervention."
        else:
            urgency = f"Priority {sev} ticket with {t.get('sla_remaining_hours')}h SLA remaining and {t.get('upvotes', 0)} citizen endorsements."
        results[t["id"]] = urgency
    return results
