import pytest
import asyncio
from unittest.mock import patch, MagicMock

from agent.pipeline import run_agent_pipeline
from main import run_background_triage


def test_agent_pipeline_parallel_tools_and_on_step():
    """Verify that parallel tools run and on_step async callback is triggered for each step."""
    steps_received = []

    async def _on_step(step_data):
        steps_received.append(step_data)

    async def _run():
        with patch("agent.pipeline._get_client", return_value=None):
            res = await run_agent_pipeline(
                title="Pothole in residential lane",
                description="Small road surface depression",
                category="road_damage",
                location="Sector 4, Rohini",
                latitude=28.7041,
                longitude=77.1025,
                on_step=_on_step,
            )
            assert res is not None
            assert len(steps_received) >= 4
            step_names = [s["step"] for s in steps_received]
            assert "understand_evidence" in step_names
            assert "reverse_geocode" in step_names
            assert "weather" in step_names
            assert "sensitive_sites" in step_names
            assert "recurrence" in step_names
            assert "decide" in step_names

    asyncio.run(_run())


def test_submit_report_returns_triaging_status(client, citizen_headers):
    """POST /api/reports must return immediately with triage_status='triaging'."""
    with patch("main.run_background_triage"):
        resp = client.post(
            "/api/reports",
            data={
                "title": "Broken storm water drain cover",
                "description": "Concrete slab fractured on pedestrian footpath",
                "category": "drainage",
                "location": "Lajpat Nagar, New Delhi",
                "latitude": "28.5672",
                "longitude": "77.2433",
            },
            headers=citizen_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["triage_status"] == "triaging"
        assert data["id"] is not None
        assert data["docket_no"] is not None

        # Public trace lookup
        trace_resp = client.get(f"/api/reports/{data['id']}/trace")
        assert trace_resp.status_code == 200
        trace_data = trace_resp.json()
        assert trace_data["report_id"] == data["id"]
        assert trace_data["triage_status"] == "triaging"
        assert trace_data["is_complete"] is False
