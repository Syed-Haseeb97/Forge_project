"""Autonomous Civic Intelligence & Hotspot Analytics Agent for Jan Aawaz.

Computes live spatial clusters (300m grid), per-department performance & overdue counts,
and recurring problem corridors from live database records only.
Drafts an executive civic brief and 3 actionable recommendations via Gemini.
Enforces a 10-minute cache and strictly verifies data sufficiency (>= 3 reports).
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Report, StatusEnum
from agent.schemas import CivicBriefDraft

logger = logging.getLogger("janaawaz.agent.insights")

# 10-minute in-memory cache
_INSIGHTS_CACHE: Dict[str, Any] = {
    "cached_at": None,
    "data": None,
}


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Insights agent could not init Gemini: {e}")
        return None


def _get_models() -> List[str]:
    raw = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _build_deterministic_brief(stats: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback brief using only real supplied numbers without Gemini."""
    total = stats["total_reports"]
    active = stats["active_count"]
    resolved = stats["resolved_count"]
    overdue = stats["overdue_count"]
    hotspots_count = len(stats["hotspots"])
    top_dept = stats["department_metrics"][0]["department"] if stats["department_metrics"] else "Municipal Services"

    brief = (
        f"The Jan Aawaz civic telemetry platform is actively tracking {total} reported grievances across municipal sectors. "
        f"Currently, {active} issues remain active, {resolved} have completed verified resolution, and {overdue} dockets are flagged overdue under SLA citizen charters. "
        f"Spatial grid clustering has isolated {hotspots_count} active 300-meter cluster(s) with concentrated citizen complaints, heavily impacting {top_dept}."
    )

    actions = [
        f"Deploy rapid engineering inspection crews to the top 300m hotspot clusters identified in civic map.",
        f"Prioritize clearance of the {overdue} overdue dockets currently escalated to departmental commissioners.",
        f"Mobilize preventive maintenance teams under {top_dept} to address repeat structural failures."
    ]

    return {
        "brief": brief,
        "recommended_actions": actions,
    }


async def generate_civic_insights(force_refresh: bool = False) -> Dict[str, Any]:
    """Compute spatial clusters, department resolution times, and AI civic brief from live DB only.
    
    Cached for 10 minutes unless force_refresh is True.
    """
    now = datetime.utcnow()

    # 1. Check in-memory cache
    if not force_refresh and _INSIGHTS_CACHE["data"] and _INSIGHTS_CACHE["cached_at"]:
        elapsed = (now - _INSIGHTS_CACHE["cached_at"]).total_seconds()
        if elapsed < 600:  # 10 minutes = 600 seconds
            cached_data = dict(_INSIGHTS_CACHE["data"])
            cached_data["cached_until"] = (_INSIGHTS_CACHE["cached_at"] + timedelta(seconds=600)).isoformat()
            return cached_data

    # 2. Query all reports from live DB
    async with AsyncSessionLocal() as session:
        stmt = select(Report).order_by(Report.created_at.desc())
        res = await session.execute(stmt)
        reports = res.scalars().all()

    total_count = len(reports)

    # Rule: If fewer than 3 reports, return "not enough data yet"
    if total_count < 3:
        not_enough = {
            "status": "not_enough_data",
            "message": "not enough data yet",
            "total_reports": total_count,
            "hotspots": [],
            "department_metrics": [],
            "recurring_locations": [],
            "brief": "not enough data yet",
            "recommended_actions": [],
            "cached_until": (now + timedelta(seconds=600)).isoformat(),
        }
        _INSIGHTS_CACHE["cached_at"] = now
        _INSIGHTS_CACHE["data"] = not_enough
        return not_enough

    # 3. Compute 300m spatial grid clusters
    # 300 meters latitude delta ≈ 0.0027 degrees (1 deg lat ≈ 111,139 m)
    # 300 meters longitude delta ≈ 0.0030 degrees
    GRID_LAT_STEP = 0.0027
    GRID_LON_STEP = 0.0030

    spatial_cells: Dict[tuple, List[Report]] = defaultdict(list)
    active_count = 0
    resolved_count = 0
    overdue_count = 0

    dept_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "total": 0,
        "resolved": 0,
        "active": 0,
        "overdue": 0,
        "resolution_seconds": [],
    })

    locality_counter = Counter()

    for r in reports:
        dept = r.routed_to or "General Civic Administration"
        dept_stats[dept]["total"] += 1

        if r.status == StatusEnum.resolved:
            resolved_count += 1
            dept_stats[dept]["resolved"] += 1
            if r.resolved_at and r.created_at:
                dur = (r.resolved_at - r.created_at).total_seconds()
                if dur > 0:
                    dept_stats[dept]["resolution_seconds"].append(dur)
        else:
            active_count += 1
            dept_stats[dept]["active"] += 1

        if r.is_overdue or (r.escalation_level and r.escalation_level >= 3):
            overdue_count += 1
            dept_stats[dept]["overdue"] += 1

        loc_label = (r.locality or r.location or "").strip()
        if loc_label:
            locality_counter[loc_label] += 1

        if r.latitude is not None and r.longitude is not None:
            cell_key = (
                round(float(r.latitude) / GRID_LAT_STEP),
                round(float(r.longitude) / GRID_LON_STEP)
            )
            spatial_cells[cell_key].append(r)

    # Format hotspot clusters (300m radius around centroid)
    hotspots = []
    for cell_key, cell_reports in spatial_cells.items():
        count = len(cell_reports)
        centroid_lat = round(sum(float(r.latitude) for r in cell_reports) / count, 6)
        centroid_lon = round(sum(float(r.longitude) for r in cell_reports) / count, 6)
        cat_counts = Counter(r.category for r in cell_reports)
        dominant_cat = cat_counts.most_common(1)[0][0]
        sev_counts = Counter(r.severity for r in cell_reports)

        hotspots.append({
            "lat": centroid_lat,
            "lon": centroid_lon,
            "count": count,
            "dominant_category": dominant_cat,
            "severity_breakdown": dict(sev_counts),
            "sample_titles": [r.title for r in cell_reports[:3]],
            "radius_meters": 300,
            "is_cluster": count >= 2,
        })

    # Sort hotspots by count descending
    hotspots.sort(key=lambda h: h["count"], reverse=True)

    # Department performance metrics
    department_metrics = []
    for dept_name, d_data in dept_stats.items():
        durations = d_data["resolution_seconds"]
        avg_hrs = round(sum(durations) / (len(durations) * 3600.0), 1) if durations else None
        department_metrics.append({
            "department": dept_name,
            "total_reports": d_data["total"],
            "active_count": d_data["active"],
            "resolved_count": d_data["resolved"],
            "overdue_count": d_data["overdue"],
            "avg_resolution_hours": avg_hrs,
        })
    department_metrics.sort(key=lambda d: d["total_reports"], reverse=True)

    # Recurring locations
    recurring_locations = [
        {"locality": loc, "count": c}
        for loc, c in locality_counter.most_common(5)
        if c >= 2
    ]

    base_stats = {
        "total_reports": total_count,
        "active_count": active_count,
        "resolved_count": resolved_count,
        "overdue_count": overdue_count,
        "hotspots": hotspots,
        "department_metrics": department_metrics,
        "recurring_locations": recurring_locations,
    }

    # 4. Gemini writes executive brief and 3 recommended actions
    client = _get_client()
    brief_data = None

    if client:
        hotspots_summary = "\n".join(
            f"- Lat {h['lat']}, Lon {h['lon']}: {h['count']} report(s), Dominant Category: {h['dominant_category']}, Samples: {', '.join(h['sample_titles'])}"
            for h in hotspots[:5]
        ) or "No localized spatial clusters detected."

        dept_summary = "\n".join(
            f"- {d['department']}: Total {d['total_reports']}, Active {d['active_count']}, Overdue {d['overdue_count']}, Avg Resolution Time: {d['avg_resolution_hours'] or 'N/A'} hours"
            for d in department_metrics[:6]
        )

        recurring_summary = "\n".join(
            f"- {r['locality']}: {r['count']} incidents"
            for r in recurring_locations
        ) or "No recurring multi-incident locations detected."

        system_instruction = (
            "You are an executive civic data analyst and public infrastructure strategist for the municipal government. "
            "Write a concise, professional civic pulse brief and exactly 3 prioritized actions for city leadership. "
            "STRICT MANDATORY CONSTRAINT: Use ONLY the exact numbers, counts, categories, and department names provided in the prompt. "
            "NEVER invent, extrapolate, or fabricate any numbers, percentages, or facts not explicitly listed."
        )

        prompt = f"""Live Municipal Redressal Data:
- Total Logged Incidents: {total_count}
- Currently Active Grievances: {active_count}
- Resolved Incidents: {resolved_count}
- Overdue Tickets: {overdue_count}

Spatial 300m Hotspot Clusters:
{hotspots_summary}

Department Performance:
{dept_summary}

Recurring Grievance Corridors:
{recurring_summary}

Write an executive civic brief and exactly 3 recommended actions based strictly on these metrics."""

        models = _get_models()
        for model_name in models:
            try:
                # External API call timeout <= 5.8s
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2,
                            response_mime_type="application/json",
                            response_schema=CivicBriefDraft,
                        ),
                    ),
                    timeout=5.8,
                )
                if response and response.text:
                    import json
                    parsed = json.loads(response.text)
                    if "brief" in parsed and "recommended_actions" in parsed and len(parsed["recommended_actions"]) == 3:
                        brief_data = parsed
                        break
            except Exception as e:
                logger.warning(f"Insights Gemini brief generation failed on {model_name}: {e}")
                continue

    if not brief_data:
        brief_data = _build_deterministic_brief(base_stats)

    result = {
        "status": "ok",
        "message": "Live civic pulse insights computed successfully",
        "total_reports": total_count,
        "active_count": active_count,
        "resolved_count": resolved_count,
        "overdue_count": overdue_count,
        "hotspots": hotspots,
        "department_metrics": department_metrics,
        "recurring_locations": recurring_locations,
        "brief": brief_data["brief"],
        "recommended_actions": brief_data["recommended_actions"][:3],
        "cached_until": (now + timedelta(seconds=600)).isoformat(),
    }

    _INSIGHTS_CACHE["cached_at"] = now
    _INSIGHTS_CACHE["data"] = result
    return result
