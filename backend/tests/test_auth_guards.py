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
