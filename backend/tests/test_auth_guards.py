import pytest


def test_public_read_endpoints(client):
    """Public read endpoints must remain accessible without authentication."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert "status" in res_health.json()

    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200

    res_reports = client.get("/api/reports")
    assert res_reports.status_code == 200
    assert isinstance(res_reports.json(), list)

    res_insights = client.get("/api/insights")
    assert res_insights.status_code == 200

    res_open311 = client.get("/api/open311/v2/services.json")
    assert res_open311.status_code == 200


def test_citizen_auth_guard_rejects_unauthenticated(client):
    """Citizen mutation endpoints must reject unauthenticated requests with 401."""
    # POST /api/reports
    res_report = client.post("/api/reports", data={
        "title": "Unauthorized Test Pothole",
        "description": "Attempting to create report without token",
        "category": "road_damage",
        "location": "Connaught Place",
    })
    assert res_report.status_code == 401

    # POST /api/reports/{id}/upvote
    res_upvote = client.post("/api/reports/sample-id/upvote")
    assert res_upvote.status_code == 401



def test_authority_auth_guard_rejects_citizens(client, citizen_headers, authority_headers):
    """Authority-only administrative endpoints must reject citizen credentials with 403 and unauthenticated with 401."""
    # PATCH /api/reports/{id}/status
    res_unauth_status = client.patch("/api/reports/sample-id/status?status=in_progress")
    assert res_unauth_status.status_code == 401

    res_citizen_status = client.patch(
        "/api/reports/sample-id/status?status=in_progress",
        headers=citizen_headers,
    )
    assert res_citizen_status.status_code == 403

    # POST /api/reports/{id}/resolve
    res_unauth_resolve = client.post("/api/reports/sample-id/resolve", data={
        "resolution_notes": "Attempting unauthorized closure"
    })
    assert res_unauth_resolve.status_code == 401

    res_citizen_resolve = client.post(
        "/api/reports/sample-id/resolve",
        data={"resolution_notes": "Attempting unauthorized closure"},
        headers=citizen_headers,
    )
    assert res_citizen_resolve.status_code == 403

    # POST /api/admin/watchdog/run
    res_unauth_watchdog = client.post("/api/admin/watchdog/run")
    assert res_unauth_watchdog.status_code == 401

    res_citizen_watchdog = client.post("/api/admin/watchdog/run", headers=citizen_headers)
    assert res_citizen_watchdog.status_code == 403

    # GET /api/insights?refresh=true requires authority
    res_unauth_insights_refresh = client.get("/api/insights?refresh=true")
    assert res_unauth_insights_refresh.status_code == 403

    res_citizen_insights_refresh = client.get("/api/insights?refresh=true", headers=citizen_headers)
    assert res_citizen_insights_refresh.status_code == 403

    # Authority token allows watchdog execution
    res_auth_watchdog = client.post("/api/admin/watchdog/run", headers=authority_headers)
    assert res_auth_watchdog.status_code == 200
    assert "checked" in res_auth_watchdog.json()

def test_upvote_toggle_and_has_upvoted(client, citizen_headers):
    """Test that authenticated citizen upvoting increments, sets has_upvoted, and toggles cleanly."""
    import uuid, asyncio
    from database import AsyncSessionLocal
    from models import Report
    from datetime import datetime

    rep_id = str(uuid.uuid4())
    async def create_rep():
        async with AsyncSessionLocal() as session:
            r = Report(
                id=rep_id,
                docket_no=f"JA-2026-{uuid.uuid4().hex[:5].upper()}",
                title="Pothole for upvote test",
                description="Testing upvote toggle",
                category="road_damage",
                location="Main Gate",
                upvotes=0,
                authenticity="genuine",
                created_at=datetime.utcnow(),
            )
            session.add(r)
            await session.commit()

    asyncio.run(create_rep())

    # 1. First upvote -> has_upvoted = True, count = 1
    res1 = client.post(f"/api/reports/{rep_id}/upvote", headers=citizen_headers)
    assert res1.status_code == 200
    assert res1.json()["upvotes"] == 1
    assert res1.json()["has_upvoted"] is True

    # 2. Check get_report has_upvoted = True
    res_get = client.get(f"/api/reports/{rep_id}", headers=citizen_headers)
    assert res_get.status_code == 200
    assert res_get.json()["has_upvoted"] is True

    # 3. Second upvote toggles off -> has_upvoted = False, count = 0
    res2 = client.post(f"/api/reports/{rep_id}/upvote", headers=citizen_headers)
    assert res2.status_code == 200
    assert res2.json()["upvotes"] == 0
    assert res2.json()["has_upvoted"] is False

