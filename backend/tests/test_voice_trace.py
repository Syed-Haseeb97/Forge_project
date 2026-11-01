import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from agent.pipeline import run_agent_pipeline
from agent.schemas import EvidenceAnalysis, TriageDecision, CriticEvaluation, AuthenticityVerdict


def test_voice_recording_evidence_captures_transcript_and_translation():
    """Verify that spoken complaints in regional language capture transcript, language, and English translation in trace."""
    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_client.aio.models = mock_models

    ev_resp = MagicMock()
    ev_resp.text = EvidenceAnalysis(
        detected_language="Hindi",
        transcript="यहाँ मुख्य सड़क पर बहुत बड़ा गड्ढा हो गया है, गाड़ियों का निकलना मुश्किल है।",
        english_translation="There is a huge pothole here on the main road, making it difficult for vehicles to pass.",
        issue_type="Major arterial road pothole",
        visible_hazards=["Vehicle collision risk", "Suspension damage"],
        estimated_dimensions="2m diameter, 25cm depth",
        evidence_severity="high",
        confidence=0.92,
    ).model_dump_json()

    dec_resp = MagicMock()
    dec_resp.text = TriageDecision(
        final_severity="high",
        sla_hours=72,
        department="Public Works Department",
        safety_advice="Cordon off affected road section immediately",
        action_plan="Mobilize hot-mix asphalt road repair team",
        rationale="Hazardous road crater on primary vehicular corridor",
        confidence=0.9,
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
        reason="Genuine voice complaint",
        signals=["valid audio"],
    ).model_dump_json()

    mock_models.generate_content = AsyncMock(side_effect=[auth_resp, ev_resp, dec_resp, critic_resp])

    async def _run():
        with patch("agent.pipeline._get_client", return_value=mock_client):
            res = await run_agent_pipeline(
                title="Voice complaint recorded via browser",
                description="Audio recording submitted by commuter",
                category="road_damage",
                location="Ring Road, New Delhi",
                latitude=28.6139,
                longitude=77.2090,
                media_bytes=b"dummy-audio-bytes",
                media_mime="audio/webm",
            )
            assert res["detected_language"] == "Hindi"
            ev_step = next((s for s in res["agent_trace"] if s["step"] == "understand_evidence"), None)
            assert ev_step is not None
            assert "Hindi" in ev_step["summary"]
            assert ev_step["data"]["transcript"] is not None
            assert "बहुत बड़ा गड्ढा" in ev_step["data"]["transcript"]
            assert ev_step["data"]["english_translation"] is not None
            assert "huge pothole" in ev_step["data"]["english_translation"]

    asyncio.run(_run())
