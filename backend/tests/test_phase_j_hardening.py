import pytest
import uuid
import json
from unittest.mock import patch
from sqlalchemy.exc import IntegrityError


def test_lookup_report_variations(client, citizen_headers):
    """Test GET /api/reports/lookup handles exact docket, lowercase, bare number, uuid prefix, and 404."""
    with patch("main.run_background_triage"):
        res = client.post(
            "/api/reports",
            data={
                "title": "Lookup Test Hazard",
                "description": "Testing lookup endpoint variations",
                "category": "road_damage",
                "location": "Connaught Place Block A",
                "latitude": "28.6315",
                "longitude": "77.2167",
            },
            headers=citizen_headers,
        )
        assert res.status_code == 200, res.text
        created = res.json()
        test_id = created["id"]
        test_docket = created["docket_no"]
        assert test_docket is not None

    # 1. Exact docket
    res1 = client.get(f"/api/reports/lookup?q={test_docket}")
    assert res1.status_code == 200, res1.text
    assert res1.json()["id"] == test_id
    assert res1.json()["docket_no"] == test_docket

    # 2. Lowercase docket
    res2 = client.get(f"/api/reports/lookup?q={test_docket.lower()}")
    assert res2.status_code == 200, res2.text
    assert res2.json()["id"] == test_id

    # 3. Bare number (extract digits from docket)
    number_part = test_docket.split("-")[-1].lstrip("0")
    if not number_part:
        number_part = "0"
    res3 = client.get(f"/api/reports/lookup?q={number_part}")
    assert res3.status_code == 200, res3.text
    assert res3.json()["id"] == test_id

    # 4. UUID 8-character prefix
    prefix = test_id[:8]
    res4 = client.get(f"/api/reports/lookup?q={prefix}")
    assert res4.status_code == 200, res4.text
    assert res4.json()["id"] == test_id

    # 5. Nonexistent returns 404
    res5 = client.get("/api/reports/lookup?q=NONEXISTENT_99999")
    assert res5.status_code == 404


def test_triage_failure_path_recovers_to_done(client, citizen_headers):
    """Triage failure path must apply heuristic fallback, set triage_status='done', and append fallback trace."""
    placeholder_text = "Autonomous AI multi-signal triage pipeline is analyzing evidence, GIS layers, weather, and recurrence..."
    
    # Simulate pipeline failure during background triage executed by TestClient
    with patch("main.analyze_report", side_effect=RuntimeError("Simulated Gemini & GIS timeout/failure")), \
         patch("main.draft_and_send_dispatch"):
        res = client.post(
            "/api/reports",
            data={
                "title": "Severe Pothole in Market",
                "description": "Deep crater in crowded market road",
                "category": "road_damage",
                "location": "Lajpat Nagar Market",
                "latitude": "28.57",
                "longitude": "77.24",
            },
            headers=citizen_headers,
        )
        assert res.status_code == 200, res.text
        created = res.json()
        report_id = created["id"]

    # Verify report recovered to done with fallback rationale
    rep_res = client.get(f"/api/reports/{report_id}")
    assert rep_res.status_code == 200, rep_res.text
    recovered = rep_res.json()

    assert recovered["triage_status"] == "done"
    assert recovered["ai_analysis"] != placeholder_text
    assert "fallback" in recovered["ai_analysis"].lower() or "safety" in recovered["ai_analysis"].lower()
    assert recovered["severity"] in ["medium", "high", "critical"]
    assert recovered["routed_to"] is not None

    # Verify live trace includes the fallback trace step
    trace_res = client.get(f"/api/reports/{report_id}/trace")
    assert trace_res.status_code == 200, trace_res.text
    trace_payload = trace_res.json()
    steps = trace_payload.get("agent_trace", [])
    assert len(steps) > 0
    fallback_steps = [s for s in steps if isinstance(s, dict) and s.get("status") == "fallback"]
    assert len(fallback_steps) > 0


def test_docket_retry_on_integrity_error(client, citizen_headers):
    """Test report creation retries when an IntegrityError occurs during insertion."""
    call_count = 0
    from database import AsyncSessionLocal as RealASL

    class MockSessionWrapper:
        def __init__(self, original_session):
            self._session = original_session

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self._session.close()

        def __getattr__(self, name):
            if name == "commit":
                async def mock_commit():
                    nonlocal call_count
                    call_count += 1
                    if call_count == 1:
                        # Fail first attempt with simulated conflict
                        raise IntegrityError("UNIQUE constraint failed: reports.docket_no", params=None, orig=Exception("Conflict"))
                    # Subsequent attempts succeed
                    return await self._session.commit()
                return mock_commit
            return getattr(self._session, name)

    with patch("main.run_background_triage"), \
         patch("main.AsyncSessionLocal", side_effect=lambda: MockSessionWrapper(RealASL())):
        res = client.post(
            "/api/reports",
            data={
                "title": "Docket Collision Retry Test",
                "description": "Testing retry loop on simulated docket conflict",
                "category": "road_damage",
                "location": "Nehru Place",
                "latitude": "28.5494",
                "longitude": "77.2536",
            },
            headers=citizen_headers,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "docket_no" in data
        assert data["docket_no"].startswith("JA-2026-")
        assert call_count >= 2
