import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from agent.pipeline import run_agent_pipeline
from agent.schemas import EvidenceAnalysis, TriageDecision, CriticEvaluation, AuthenticityVerdict


def test_critic_disagreement_flags_human_review():
    """When the Critic disagrees with the decision, needs_human_review must be set to True and flagged in trace."""
    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_client.aio.models = mock_models

    # Mock Evidence, Decide, and Critic responses in order
    ev_resp = MagicMock()
    ev_resp.text = EvidenceAnalysis(
        detected_language="English",
        issue_type="Deep pothole",
        visible_hazards=["Tripping hazard"],
        estimated_dimensions="1m wide",
        evidence_severity="medium",
        confidence=0.85,
    ).model_dump_json()

    dec_resp = MagicMock()
    dec_resp.text = TriageDecision(
        final_severity="medium",
        sla_hours=168,
        department="Public Works Department",
        safety_advice="Place warning cones",
        action_plan="Patch asphalt surface",
        rationale="Standard secondary road repair",
        confidence=0.8,
    ).model_dump_json()

    critic_resp = MagicMock()
    critic_resp.text = CriticEvaluation(
        agrees=False,
        issues=["Nearby school entrance requires high priority 72h SLA, not medium 168h"],
        suggested_severity="high",
    ).model_dump_json()

    auth_resp = MagicMock()
    auth_resp.text = AuthenticityVerdict(
        verdict="genuine",
        confidence=0.95,
        reason="Genuine civic complaint",
        signals=["valid defect"],
    ).model_dump_json()

    mock_models.generate_content = AsyncMock(side_effect=[auth_resp, ev_resp, dec_resp, critic_resp])

    async def _run():
        with patch("agent.pipeline._get_client", return_value=mock_client):
            res = await run_agent_pipeline(
                title="Pothole near primary school gate",
                description="Hole on approach road used by students",
                category="road_damage",
                location="Sector 12, Dwarka",
                latitude=28.5921,
                longitude=77.0460,
            )
            assert res["needs_human_review"] is True
            critic_step = next((s for s in res["agent_trace"] if s["step"] == "critic_audit"), None)
            assert critic_step is not None
            assert critic_step["status"] == "warning"
            assert "Nearby school entrance" in critic_step["summary"]

    asyncio.run(_run())


def test_critic_agreement_keeps_human_review_false():
    """When Critic agrees and confidence >= 0.6, needs_human_review remains False."""
    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_client.aio.models = mock_models

    ev_resp = MagicMock()
    ev_resp.text = EvidenceAnalysis(
        detected_language="English",
        issue_type="Overflowing dumpster",
        visible_hazards=["Litter scatter"],
        estimated_dimensions="2 bins",
        evidence_severity="low",
        confidence=0.9,
    ).model_dump_json()

    dec_resp = MagicMock()
    dec_resp.text = TriageDecision(
        final_severity="low",
        sla_hours=336,
        department="Municipal Sanitation",
        safety_advice="Avoid handling debris without gloves",
        action_plan="Dispatch municipal sanitation compactor",
        rationale="Routine collection overflow",
        confidence=0.92,
    ).model_dump_json()

    critic_resp = MagicMock()
    critic_resp.text = CriticEvaluation(
        agrees=True,
        issues=[],
        suggested_severity=None,
    ).model_dump_json()

    auth_resp = MagicMock()
    auth_resp.text = AuthenticityVerdict(
        verdict="genuine",
        confidence=0.95,
        reason="Genuine civic complaint",
        signals=["valid defect"],
    ).model_dump_json()

    mock_models.generate_content = AsyncMock(side_effect=[auth_resp, ev_resp, dec_resp, critic_resp])

    async def _run():
        with patch("agent.pipeline._get_client", return_value=mock_client):
            res = await run_agent_pipeline(
                title="Full trash bin in park",
                description="Litter overflowing on walking path",
                category="garbage",
                location="Lodhi Gardens",
                latitude=28.5931,
                longitude=77.2197,
            )
            assert res["needs_human_review"] is False
            critic_step = next((s for s in res["agent_trace"] if s["step"] == "critic_audit"), None)
            assert critic_step is not None
            assert critic_step["status"] == "success"

    asyncio.run(_run())
