import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from agent.watchdog import run_watchdog_check, get_sla_time_scale


def test_watchdog_time_scale():
    """Watchdog time scale helper must parse float values and default to 1.0."""
    with patch.dict("os.environ", {"SLA_TIME_SCALE": "3600"}):
        assert get_sla_time_scale() == 3600.0

    with patch.dict("os.environ", {"SLA_TIME_SCALE": "invalid"}):
        assert get_sla_time_scale() == 1.0

    with patch.dict("os.environ", {}, clear=True):
        assert get_sla_time_scale() == 1.0


def test_watchdog_run_idempotency():
    """Running watchdog check multiple times back-to-back must be idempotent."""
    async def _test():
        # Mock draft_and_send_dispatch to avoid network SMTP/Gemini calls in unit tests
        with patch("agent.watchdog.draft_and_send_dispatch", new_callable=AsyncMock) as mock_dispatch:
            # First pass
            res1 = await run_watchdog_check()
            assert "checked" in res1
            assert "escalated_count" in res1

            # Immediate second pass without time progression
            res2 = await run_watchdog_check()
            assert "checked" in res2
            # After an immediate re-run, no tickets should double-escalate
            assert res2["escalated_count"] == 0

    asyncio.run(_test())
