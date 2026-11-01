import os
import re
import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from agent.tokens import generate_tracking_token, is_valid_tracking_token
from agent.directory import resolve_recipient, mask_email
from agent.dispatch import draft_and_send_dispatch
from models import Report, Dispatch, ReportTimeline, StatusEnum, SeverityEnum
from database import AsyncSessionLocal


def test_tracking_token_uniqueness_and_format():
    """Requirement 5: Format JA-TRK-XXXX-XXXX over unambiguous alphabet (no 0/O/1/I) and uniqueness."""
    token_regex = re.compile(r"^JA-TRK-[2-9A-HJ-NP-Z]{4}-[2-9A-HJ-NP-Z]{4}$")
    forbidden_chars = {"0", "O", "1", "I", "o", "i", "l"}

    tokens = []
    for _ in range(100):
        tok = generate_tracking_token()
        assert token_regex.match(tok), f"Token {tok} does not match required format"
        assert is_valid_tracking_token(tok), f"Token {tok} failed validation helper"
        for ch in forbidden_chars:
            assert ch not in tok, f"Ambiguous character '{ch}' found in token {tok}"
        tokens.append(tok)

    assert len(set(tokens)) == 100, "Collision detected in 100 generated tokens"


def test_recipient_resolution_and_fallback():
    """Requirement 1: Directory lookup for Tiruchirappalli streetlight vs fallback."""
    # Matched test case: Tiruchirappalli streetlight
    matched = resolve_recipient(
        category="streetlight",
        locality_or_city="Cantonment, Tiruchirappalli",
        escalation_level=0,
    )
    assert matched["matched"] is True
    assert matched["to"] == "commr.trichy@tn.gov.in"
    assert "Commissioner, Tiruchirappalli City Municipal Corporation" in matched["designation"]
    assert "tnurbantree.tn.gov.in/trichy" in matched["source_url"]

    # Fallback test case: Unmapped category or locality
    fallback = resolve_recipient(
        category="water_leak",
        locality_or_city="Unknown Outpost Nowhere",
        escalation_level=0,
    )
    assert fallback["matched"] is False
    expected_fallback_inbox = os.getenv("DISPATCH_EMAIL", "dispatch@janaawaz.in")
    assert fallback["to"] == expected_fallback_inbox


def test_demo_mode_never_emails_department():
    """Requirement 2 & 4: In demo mode send only to DISPATCH_EMAIL with [DEMO] and never email department."""
    async def _run():
        test_id = str(uuid.uuid4())
        tok = generate_tracking_token()
        docket_no = f"JA-2026-{uuid.uuid4().hex[:5].upper()}"

        async with AsyncSessionLocal() as session:
            rep = Report(
                id=test_id,
                docket_no=docket_no,
                tracking_token=tok,
                title="Dead streetlight array on main avenue",
                description="Dark stretch of 4 poles posing hazard",
                category="streetlight",
                location="Tiruchirappalli North",
                locality="Tiruchirappalli",
                severity=SeverityEnum.medium,
                status=StatusEnum.open,
                needs_human_review=False,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        with patch.dict(os.environ, {
            "DISPATCH_MODE": "demo",
            "DISPATCH_EMAIL": "test-fallback@janaawaz.in",
            "PUBLIC_APP_URL": "https://janaawaz.example.com",
        }):
            with patch("agent.dispatch.send_dispatch_email", return_value=True) as mock_send:
                res = await draft_and_send_dispatch(test_id, kind="initial", escalation_level=0)
                assert res is not None
                assert res["sent"] is True

                # Assert send_dispatch_email was called with demo target
                assert mock_send.called
                call_kwargs = mock_send.call_args.kwargs
                assert call_kwargs["to_email"] == "test-fallback@janaawaz.in"
                assert call_kwargs["to_email"] != "commr.trichy@tn.gov.in"
                assert call_kwargs["subject"].startswith("[DEMO]")
                # CC should be empty in demo mode
                assert call_kwargs["cc"] == []

        # Check database dispatch and timeline notes
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            tl = (await session.execute(select(ReportTimeline).where(ReportTimeline.report_id == test_id))).scalars().all()
            notes = [t.notes for t in tl]
            assert any("[Demo mode: routed to test-fallback@janaawaz.in]" in n for n in notes)

    asyncio.run(_run())


def test_live_mode_passes_cc_and_reply_to():
    """Requirement 2, 3, 4: In live mode send to department, CC TEAM_CC_EMAILS, set REPLY_TO."""
    async def _run():
        test_id = str(uuid.uuid4())
        tok = generate_tracking_token()
        docket_no = f"JA-2026-{uuid.uuid4().hex[:5].upper()}"

        async with AsyncSessionLocal() as session:
            rep = Report(
                id=test_id,
                docket_no=docket_no,
                tracking_token=tok,
                title="Flickering light cluster near school",
                description="Continuous blinking causing visibility loss",
                category="streetlight",
                location="Tiruchirappalli Central",
                locality="Tiruchirappalli",
                severity=SeverityEnum.medium,
                status=StatusEnum.open,
                needs_human_review=False,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        with patch.dict(os.environ, {
            "DISPATCH_MODE": "live",
            "TEAM_CC_EMAILS": "audit@example.com, observer@example.com",
            "REPLY_TO": "replies@janaawaz.in",
            "PUBLIC_APP_URL": "https://janaawaz.example.com",
        }):
            with patch("agent.dispatch.send_dispatch_email", return_value=True) as mock_send:
                res = await draft_and_send_dispatch(test_id, kind="initial", escalation_level=0)
                assert res is not None

                assert mock_send.called
                call_kwargs = mock_send.call_args.kwargs
                # Target is the resolved real government email
                assert call_kwargs["to_email"] == "commr.trichy@tn.gov.in"
                assert not call_kwargs["subject"].startswith("[DEMO]")
                # CC contains team emails
                assert "audit@example.com" in call_kwargs["cc"]
                assert "observer@example.com" in call_kwargs["cc"]
                # Reply-to reaches team
                assert call_kwargs["reply_to"] == "replies@janaawaz.in"

    asyncio.run(_run())


def test_human_review_gate_holds_dispatch():
    """Requirement 4: Reports flagged with needs_human_review=True must never be autonomously dispatched."""
    async def _run():
        test_id = str(uuid.uuid4())
        docket_no = f"JA-2026-{uuid.uuid4().hex[:5].upper()}"
        async with AsyncSessionLocal() as session:
            rep = Report(
                id=test_id,
                docket_no=docket_no,
                tracking_token=generate_tracking_token(),
                title="Ambiguous hazard report",
                description="Needs physical verification",
                category="streetlight",
                location="Tiruchirappalli",
                needs_human_review=True,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        with patch("agent.dispatch.send_dispatch_email") as mock_send:
            res = await draft_and_send_dispatch(test_id)
            assert res is None
            assert not mock_send.called

    asyncio.run(_run())


def test_api_track_endpoint_leaks_no_pii(client):
    """Requirement 7: /api/track/{token} returns status, countdown, dispatch info, and STRICTLY zero citizen PII."""
    tok = generate_tracking_token()
    test_id = str(uuid.uuid4())
    docket_no = f"JA-2026-{uuid.uuid4().hex[:5].upper()}"
    private_citizen_email = "citizen_secret_pii@example.com"

    async def setup_data():
        async with AsyncSessionLocal() as session:
            rep = Report(
                id=test_id,
                docket_no=docket_no,
                tracking_token=tok,
                citizen_id="citizen-uuid-999",
                citizen_email=private_citizen_email,
                title="Pavement water pipeline leak",
                description="Clean water bubbling from curb",
                category="water_leak",
                location="Main Market, Trichy",
                locality="Trichy",
                severity=SeverityEnum.high,
                status=StatusEnum.in_progress,
                sla_hours=48,
                created_at=datetime.utcnow() - timedelta(hours=4),
            )
            session.add(rep)

            disp = Dispatch(
                id=str(uuid.uuid4()),
                report_id=test_id,
                kind="initial",
                to_email="test-inbox@example.com",
                recipient_office="Executive Engineer (Water Supply)",
                subject="Notice: Pavement water pipeline leak",
                body="Full formal dispatch notice",
                sent=True,
                created_at=datetime.utcnow() - timedelta(hours=3),
            )
            session.add(disp)
            await session.commit()

    asyncio.run(setup_data())

    # Call the public tracking endpoint
    resp = client.get(f"/api/track/{tok}")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Verify expected public fields
    assert data["docket_no"] == docket_no
    assert data["tracking_token"] == tok
    assert data["status"] == "in_progress"
    assert data["severity"] == "high"
    assert "remaining" in data["sla_countdown"] or "h" in data["sla_countdown"]
    assert data["sla_remaining_hours"] > 0

    # Verify dispatch info
    assert data["dispatch_info"] is not None
    assert data["dispatch_info"]["provider_accepted"] is True
    # Verify wording is "sent", not "delivered or read"
    assert "sent" in data["dispatch_info"]["status_text"].lower()
    assert "delivered" not in data["dispatch_info"]["status_text"].lower()
    assert "read" not in data["dispatch_info"]["status_text"].lower()

    # STRICT PII CHECK: Ensure citizen email, citizen id, phone are completely absent
    assert "citizen_email" not in data
    assert "citizen_id" not in data
    assert "citizen_name" not in data
    assert "phone" not in data
    assert private_citizen_email not in resp.text
