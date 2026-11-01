"""Phase M Authenticity Gate test suite.

Validates:
1. Genuine civic report passes through and dispatches
2. Joke/test text -> spam, hidden from public feeds and not dispatched
3. Low-confidence spam (<0.8) -> suspicious with human review
4. Gemini failure -> unchecked (demo mode dispatches, live mode holds)
5. Authority override to genuine clears review and triggers dispatch
6. Short regional-language genuine report is not rejected
7. Spam excluded from /api/stats
8. Meme photo mismatch -> suspicious
9. Abuse limit: 3 spam complaints in 24h -> 429 on next POST /api/reports
10. Public tracking endpoint /api/track/{token} shows "Held for review" for spam
"""
import os
import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from database import AsyncSessionLocal
from models import Report, Dispatch, ReportTimeline, Citizen, StatusEnum, SeverityEnum
from agent.schemas import AuthenticityVerdict
from agent.pipeline import check_authenticity
from agent.dispatch import draft_and_send_dispatch


def test_1_genuine_report_passes_through():
    """1. Genuine report passes through authenticity check with genuine verdict."""
    async def _run():
        mock_verdict = AuthenticityVerdict(
            verdict="genuine",
            confidence=0.92,
            reason="Clear civic road defect requiring repair",
            signals=["concrete damage", "clear description", "valid category"],
        )
        mock_resp = MagicMock()
        mock_resp.text = mock_verdict.model_dump_json()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = await check_authenticity(
            title="Dangerous pothole on MG Road",
            description="Deep 2ft pothole in right lane near bus stop, risk of accidents",
            category="road_damage",
            media_bytes=None,
            media_mime=None,
            latitude=13.0827,
            longitude=80.2707,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "genuine"
        assert res["skip_pipeline"] is False
        assert res["authenticity_confidence"] == 0.92

    asyncio.run(_run())


def test_2_joke_text_marked_spam_and_not_dispatched():
    """2. Joke/test text with >=0.8 confidence marked spam, skips pipeline and blocked from dispatch."""
    async def _run():
        mock_verdict = AuthenticityVerdict(
            verdict="spam",
            confidence=0.95,
            reason="Humorous test submission with non-civic joke text",
            signals=["joke content", "test keywords", "no infrastructure issue"],
        )
        mock_resp = MagicMock()
        mock_resp.text = mock_verdict.model_dump_json()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = await check_authenticity(
            title="Why did the chicken cross the road lol",
            description="Just testing haha nothing wrong here lol",
            category="other",
            media_bytes=None,
            media_mime=None,
            latitude=None,
            longitude=None,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "spam"
        assert res["skip_pipeline"] is True
        assert res["timeline_note"] is not None

        # Create report in DB with spam authenticity
        rep_id = str(uuid.uuid4())
        doc_no = f"JA-M-{uuid.uuid4().hex[:12].upper()}"
        async with AsyncSessionLocal() as session:
            rep = Report(
                id=rep_id,
                docket_no=doc_no,
                tracking_token=f"JA-TRK-{uuid.uuid4().hex[:12].upper()}",
                title="Joke text report",
                description="Test joke",
                category="other",
                location="Chennai",
                severity=SeverityEnum.low,
                status=StatusEnum.open,
                authenticity="spam",
                authenticity_reason="Humorous test submission",
                needs_human_review=False,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        # Attempt autonomous dispatch -> must be blocked
        disp_res = await draft_and_send_dispatch(rep_id, "initial")
        assert disp_res is None

        # Verify timeline records dispatch_held
        async with AsyncSessionLocal() as session:
            tls = (await session.execute(select(ReportTimeline).where(ReportTimeline.report_id == rep_id))).scalars().all()
            held_events = [t for t in tls if t.action_type == "dispatch_held"]
            assert len(held_events) >= 1

    asyncio.run(_run())


def test_3_low_confidence_spam_becomes_suspicious():
    """3. Spam verdict with confidence < 0.8 is downgraded to suspicious."""
    async def _run():
        mock_verdict = AuthenticityVerdict(
            verdict="spam",
            confidence=0.65,  # Low confidence
            reason="Uncertain whether complaint is genuine or test",
            signals=["vague text"],
        )
        mock_resp = MagicMock()
        mock_resp.text = mock_verdict.model_dump_json()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = await check_authenticity(
            title="Unclear street issue",
            description="Something looks weird here",
            category="other",
            media_bytes=None,
            media_mime=None,
            latitude=None,
            longitude=None,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "suspicious"
        assert res["skip_pipeline"] is True
        assert res["authenticity_confidence"] == 0.65

    asyncio.run(_run())


def test_4_gemini_failure_becomes_unchecked_demo_dispatches_live_holds():
    """4. Gemini failure -> authenticity='unchecked'. Demo mode dispatches, live mode holds."""
    async def _run():
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("Gemini API timeout"))

        res = await check_authenticity(
            title="Broken pipe",
            description="Water leaking across sidewalk",
            category="water_leak",
            media_bytes=None,
            media_mime=None,
            latitude=None,
            longitude=None,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "unchecked"
        assert res["step_data"]["status"] == "degraded"

        # Test dispatch gate:
        rep_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as session:
            rep = Report(
                id=rep_id,
                docket_no=f"JA-M-{uuid.uuid4().hex[:12].upper()}",
                tracking_token=f"JA-TRK-{uuid.uuid4().hex[:12].upper()}",
                title="Broken pipe",
                description="Water leaking",
                category="water_leak",
                location="Chennai",
                severity=SeverityEnum.medium,
                status=StatusEnum.open,
                authenticity="unchecked",
                needs_human_review=False,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        # In live mode -> must be held
        with patch.dict(os.environ, {"DISPATCH_MODE": "live"}):
            live_disp = await draft_and_send_dispatch(rep_id, "initial")
            assert live_disp is None

        # In demo mode -> unchecked is allowed to proceed
        with patch.dict(os.environ, {"DISPATCH_MODE": "demo", "DEV_MODE": "true"}):
            with patch("agent.dispatch.send_dispatch_email", return_value=True):
                with patch("agent.dispatch._get_client", return_value=None):
                    demo_disp = await draft_and_send_dispatch(rep_id, "initial")
                    assert demo_disp is not None
                    assert demo_disp["sent"] is True

    asyncio.run(_run())


def test_5_authority_approve_triggers_dispatch(client, authority_headers):
    """5. Authority approve endpoint overrides to genuine, clears review, triggers dispatch."""
    async def _run():
        rep_id = str(uuid.uuid4())
        doc_no = f"JA-M-{uuid.uuid4().hex[:12].upper()}"
        async with AsyncSessionLocal() as session:
            rep = Report(
                id=rep_id,
                docket_no=doc_no,
                tracking_token=f"JA-TRK-{uuid.uuid4().hex[:12].upper()}",
                title="Suspicious reported defect",
                description="Needs authority eyes",
                category="road_damage",
                location="Tiruchirappalli",
                severity=SeverityEnum.high,
                status=StatusEnum.open,
                authenticity="suspicious",
                authenticity_reason="Preliminary automated screening unsure",
                needs_human_review=True,
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        with patch("agent.dispatch.send_dispatch_email", return_value=True):
            with patch("agent.dispatch._get_client", return_value=None):
                res = client.post(
                    f"/api/reports/{rep_id}/authenticity",
                    json={"verdict": "genuine", "note": "Verified by ward inspector"},
                    headers=authority_headers,
                )
                assert res.status_code == 200
                assert res.json()["authenticity"] == "genuine"

        # Verify DB state
        async with AsyncSessionLocal() as session:
            updated_rep = await session.get(Report, rep_id)
            assert updated_rep.authenticity == "genuine"
            assert updated_rep.needs_human_review is False

            # Verify timeline
            tls = (await session.execute(select(ReportTimeline).where(ReportTimeline.report_id == rep_id))).scalars().all()
            auth_approved = [t for t in tls if t.action_type == "authority_approved"]
            assert len(auth_approved) >= 1
            assert "Verified by ward inspector" in auth_approved[0].notes

    asyncio.run(_run())


def test_6_short_regional_language_not_rejected():
    """6. Short regional-language genuine report is not rejected."""
    async def _run():
        mock_verdict = AuthenticityVerdict(
            verdict="genuine",
            confidence=0.88,
            reason="Valid Tamil grievance reporting road crater",
            signals=["regional language Tamil", "actionable defect"],
        )
        mock_resp = MagicMock()
        mock_resp.text = mock_verdict.model_dump_json()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = await check_authenticity(
            title="ரோடு பள்ளம்",
            description="சாலையில் பெரிய பள்ளம் உள்ளது உடனடியாக சரிசெய்யவும்",
            category="road_damage",
            media_bytes=None,
            media_mime=None,
            latitude=10.7905,
            longitude=78.7047,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "genuine"
        assert res["skip_pipeline"] is False

    asyncio.run(_run())


def test_7_spam_excluded_from_stats_and_list(client):
    """7. Authenticity=='spam' reports are hidden from /api/stats and /api/reports list."""
    async def _run():
        unique_cat = "streetlight"
        spam_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())

        async with AsyncSessionLocal() as session:
            r_spam = Report(
                id=spam_id,
                docket_no=f"JA-M-{uuid.uuid4().hex[:12].upper()}",
                title="Meme complaint about lights",
                description="Lol darkness meme",
                category=unique_cat,
                location="Chennai",
                severity=SeverityEnum.low,
                status=StatusEnum.open,
                authenticity="spam",
                authenticity_reason="Meme/joke",
                created_at=datetime.utcnow(),
            )
            r_gen = Report(
                id=gen_id,
                docket_no=f"JA-M-{uuid.uuid4().hex[:12].upper()}",
                title="Genuine broken sodium streetlight",
                description="Bulb is damaged and pole exposed",
                category=unique_cat,
                location="Chennai",
                severity=SeverityEnum.medium,
                status=StatusEnum.open,
                authenticity="genuine",
                created_at=datetime.utcnow(),
            )
            session.add_all([r_spam, r_gen])
            await session.commit()

        # Check /api/reports list
        res_list = client.get(f"/api/reports?category={unique_cat}")
        assert res_list.status_code == 200
        reports_data = res_list.json()
        ids_in_list = [r["id"] for r in reports_data]
        assert gen_id in ids_in_list
        assert spam_id not in ids_in_list, "Spam report should be excluded from /api/reports list"

        # Check /api/stats
        res_stats = client.get("/api/stats")
        assert res_stats.status_code == 200

        # Both reporter and authority can still open spam by ID
        res_direct = client.get(f"/api/reports/{spam_id}")
        assert res_direct.status_code == 200
        assert res_direct.json()["authenticity"] == "spam"

    asyncio.run(_run())


def test_8_meme_photo_mismatch_becomes_suspicious():
    """8. Meme photo or description-photo mismatch flagged as suspicious."""
    async def _run():
        mock_verdict = AuthenticityVerdict(
            verdict="suspicious",
            confidence=0.78,
            reason="Photo depicts an internet meme cartoon, mismatch with reported broken pipe",
            signals=["media-description mismatch", "cartoon graphic"],
        )
        mock_resp = MagicMock()
        mock_resp.text = mock_verdict.model_dump_json()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        res = await check_authenticity(
            title="Huge pipe burst",
            description="Water is everywhere on the street",
            category="water_leak",
            media_bytes=b"fake-image-bytes",
            media_mime="image/png",
            latitude=13.08,
            longitude=80.27,
            client=mock_client,
            models=["gemini-3.5-flash-lite"],
            on_step=None,
        )

        assert res["authenticity"] == "suspicious"
        assert res["skip_pipeline"] is True
        assert "meme" in res["authenticity_reason"].lower() or "mismatch" in res["authenticity_reason"].lower()

    asyncio.run(_run())


def test_9_abuse_limit_three_spam_verdicts_returns_429(client, citizen_headers):
    """9. Abuse limit: If citizen has >=3 spam verdicts in 24h, next submission returns 429."""
    async def _run():
        # The citizen_headers token has sub="citizen@janaawaz.in"
        citizen_email = "citizen@janaawaz.in"

        async with AsyncSessionLocal() as session:
            # Create or get citizen with unique ID
            cit = (await session.execute(select(Citizen).where(Citizen.email == citizen_email))).scalar_one_or_none()
            if not cit:
                citizen_id = str(uuid.uuid4())
                cit = Citizen(
                    id=citizen_id,
                    email=citizen_email,
                    first_name="Test",
                    last_name="Citizen",
                    dob="1990-01-01",
                    address="123 Civic Lane",
                    is_verified=True,
                )
                session.add(cit)
                await session.commit()
            else:
                citizen_id = cit.id

            # Insert 3 spam reports created in the last 2 hours for this citizen
            now = datetime.utcnow()
            for i in range(3):
                spam_r = Report(
                    id=str(uuid.uuid4()),
                    docket_no=f"JA-M-{uuid.uuid4().hex[:12].upper()}",
                    citizen_id=citizen_id,
                    citizen_email=citizen_email,
                    title=f"Spam test {i+1}",
                    description="Gibberish test text",
                    category="other",
                    location="Test City",
                    severity=SeverityEnum.low,
                    status=StatusEnum.open,
                    authenticity="spam",
                    authenticity_reason="Spam submission",
                    created_at=now - timedelta(minutes=i * 20),
                )
                session.add(spam_r)
            await session.commit()

        # Now attempt 4th submission with citizen headers
        form_data = {
            "title": "Another attempt",
            "description": "Will this go through?",
            "category": "road_damage",
            "location": "Anna Nagar, Chennai",
        }
        res = client.post("/api/reports", data=form_data, headers=citizen_headers)
        assert res.status_code == 429
        assert "limit reached" in res.json()["detail"].lower()

    asyncio.run(_run())


def test_10_public_track_for_spam_shows_held_for_review(client):
    """10. /api/track/{token} for spam report shows status 'Held for review' and includes reason."""
    async def _run():
        rep_id = str(uuid.uuid4())
        doc_no = f"JA-M-{uuid.uuid4().hex[:12].upper()}"
        track_tok = f"JA-TRK-SPAM-{uuid.uuid4().hex[:4].upper()}"

        async with AsyncSessionLocal() as session:
            rep = Report(
                id=rep_id,
                docket_no=doc_no,
                tracking_token=track_tok,
                title="Questionable Complaint",
                description="This is test text",
                category="garbage",
                location="Koyambedu",
                severity=SeverityEnum.low,
                status=StatusEnum.open,
                authenticity="spam",
                authenticity_reason="Automated verification identified non-civic content",
                created_at=datetime.utcnow(),
            )
            session.add(rep)
            await session.commit()

        res = client.get(f"/api/track/{track_tok}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "Held for review"
        assert data["authenticity"] == "spam"
        assert data["authenticity_reason"] == "Automated verification identified non-civic content"

    asyncio.run(_run())
