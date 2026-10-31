import pytest
import asyncio
from unittest.mock import patch

from gemini_service import _fallback_triage
from agent.pipeline import run_agent_pipeline


def test_fallback_triage_keyword_rules():
    """Fallback triage must accurately evaluate severity and routing based on civic failure keywords."""
    # Critical infrastructure hazards
    crit_res = _fallback_triage(
        title="Deep sinkhole opening near bridge support",
        description="Dangerous ground collapse with potential structure failure",
        category="bridge_damage",
    )
    assert crit_res["severity"] == "critical"
    assert crit_res["sla_hours"] == 24
    assert crit_res["suggested_department"] == "Civil Engineering Division"
    assert "perimeter" in crit_res["action_plan"].lower() or "rapid" in crit_res["action_plan"].lower()

    # High severity hazards
    high_res = _fallback_triage(
        title="Hazardous deep pothole on major highway",
        description="Multiple vehicles damaged, high traffic speed",
        category="road_damage",
    )
    assert high_res["severity"] == "high"
    assert high_res["sla_hours"] == 72
    assert high_res["suggested_department"] == "Public Works Department"

    # Medium issues
    med_res = _fallback_triage(
        title="Overflowing street garbage bin",
        description="Trash accumulation on pavement",
        category="garbage",
    )
    assert med_res["severity"] == "medium"
    assert med_res["sla_hours"] == 168


def test_agent_pipeline_graceful_fallback():
    """Agent pipeline must degrade gracefully and mark the trace step status as 'fallback' if Gemini is unavailable."""
    async def _test():
        # Force Gemini client to return None to simulate API outage
        with patch("agent.pipeline._get_client", return_value=None):
            result = await run_agent_pipeline(
                title="Ruptured high-pressure water main flooding roadway",
                description="Water gushing across traffic lanes, risk of roadbed erosion",
                category="water_leak",
                location="Ring Road Junction, New Delhi",
                latitude=28.6139,
                longitude=77.2090,
                media_bytes=None,
                media_mime=None,
                db_session=None,
            )

            assert result is not None
            assert result["severity"] in ("critical", "high", "medium", "low")
            assert result["sla_hours"] in (24, 72, 168, 336)
            assert result["routed_to"] == "Water & Sewage Authority"
            assert "Water & Sewage" in result["routed_to"]
            assert len(result["safety_precautions"]) > 10

            # Verify that the agent trace honestly records the fallback
            trace = result.get("agent_trace", [])
            assert len(trace) > 0

            fallback_steps = [s for s in trace if s.get("status") == "fallback"]
            assert len(fallback_steps) > 0, "Trace must contain at least one step with status 'fallback'"
            assert fallback_steps[0]["step"] == "decide"

    asyncio.run(_test())
