import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from agent.pipeline import check_semantic_duplicates
from agent.schemas import SemanticDuplicateList, SemanticDuplicateItem


def test_semantic_duplicates_with_mocked_gemini():
    """Verify that Gemini comparison returns structured likely_duplicate and reason for top candidate reports."""
    mock_client = MagicMock()
    mock_models = MagicMock()
    mock_client.aio.models = mock_models

    mock_resp = MagicMock()
    mock_resp.text = SemanticDuplicateList(
        candidates=[
            SemanticDuplicateItem(
                report_id="rep-101",
                likely_duplicate=True,
                duplicate_reason="Both reports refer to the massive crater pothole outside Gate 3 of Metro station.",
            ),
            SemanticDuplicateItem(
                report_id="rep-102",
                likely_duplicate=False,
                duplicate_reason="Describes broken sidewalk tiles 200m away, distinct from the roadway defect.",
            ),
        ]
    ).model_dump_json()

    mock_models.generate_content = AsyncMock(return_value=mock_resp)

    candidates = [
        {"id": "rep-101", "title": "Big crater on road outside gate 3", "description": "Vehicles getting stuck", "category": "road_damage", "distance_km": 0.05},
        {"id": "rep-102", "title": "Broken pavement tiles", "description": "Pedestrian pathway cracked", "category": "road_damage", "distance_km": 0.20},
    ]

    async def _run():
        with patch("agent.pipeline._get_client", return_value=mock_client):
            res = await check_semantic_duplicates(
                new_title="Massive road pothole near metro gate 3",
                new_description="Cars braking abruptly, deep crater in pavement",
                new_category="road_damage",
                candidates=candidates,
            )
            assert res["rep-101"]["likely_duplicate"] is True
            assert "Gate 3" in res["rep-101"]["duplicate_reason"]
            assert res["rep-102"]["likely_duplicate"] is False

    asyncio.run(_run())


def test_semantic_duplicates_fallback_heuristic():
    """Verify fallback keyword/category heuristic detects duplicates when Gemini is unavailable."""
    candidates = [
        {"id": "rep-201", "title": "Burst water pipeline flooding street", "description": "Drinking water wasting", "category": "water_leak", "distance_km": 0.08},
    ]

    async def _run():
        with patch("agent.pipeline._get_client", return_value=None):
            res = await check_semantic_duplicates(
                new_title="Pipeline burst and flooding road",
                new_description="Clean water gushing on main street",
                new_category="water_leak",
                candidates=candidates,
            )
            assert res["rep-201"]["likely_duplicate"] is True
            assert res["rep-201"]["duplicate_reason"] is not None

    asyncio.run(_run())
