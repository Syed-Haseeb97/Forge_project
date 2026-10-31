import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agent.pipeline import generate_why_now_rationales
from agent.schemas import WhyNowList, WhyNowItem


def test_authority_queue_guard_blocks_citizens(client, citizen_headers):
    """GET /api/authority/queue must reject citizen credentials with 403 Forbidden."""
    resp = client.get("/api/authority/queue", headers=citizen_headers)
    assert resp.status_code == 403, resp.text


def test_authority_queue_ranking_and_batches(client, authority_headers):
    """GET /api/authority/queue must return prioritized queue and 300m crew batches for authority users."""
    resp = client.get("/api/authority/queue", headers=authority_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "total_queued" in data
    assert "items" in data
    assert "crew_batches" in data

    if data["items"]:
        # Verify descending order of composite score
        scores = [item["score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

        first = data["items"][0]
        assert "score_breakdown" in first
        assert "severity_pts" in first["score_breakdown"]
        assert "sla_pts" in first["score_breakdown"]


def test_generate_why_now_with_mocked_gemini():
    """Verify Gemini why_now generator returns punchy operational reasons for top tickets."""
    import asyncio

    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_client.aio.models = mock_models

    mock_resp = MagicMock()
    mock_resp.text = WhyNowList(
        items=[
            WhyNowItem(
                report_id="rep-1",
                why_now="Critical structural risk under heavy rain forecast threatening adjacent school.",
            )
        ]
    ).model_dump_json()

    mock_models.generate_content = AsyncMock(return_value=mock_resp)

    tickets = [
        {"id": "rep-1", "title": "Collapsed culvert", "severity": "critical", "category": "drainage", "sla_remaining_hours": 4.5, "is_overdue": False, "upvotes": 5, "rain_risk": True, "hotspot_count": 2}
    ]

    async def _run():
        with patch("agent.pipeline._get_client", return_value=mock_client):
            res = await generate_why_now_rationales(tickets)
            assert "rep-1" in res
            assert "heavy rain" in res["rep-1"]

    asyncio.run(_run())
