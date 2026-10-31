"""SLA Watchdog Autonomous Agent for Jan Aawaz.

Periodically inspects open and in-progress dockets against SLA deadlines,
triggers tiered administrative escalations (Dept Head -> Commissioner -> Overdue),
and executes idempotent background dispatch drafting.
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, and_

from database import AsyncSessionLocal
from models import Report, StatusEnum
from agent.dispatch import draft_and_send_dispatch

logger = logging.getLogger("janaawaz.agent.watchdog")

_WATCHDOG_TASK: Optional[asyncio.Task] = None


def get_sla_time_scale() -> float:
    """Read time scale factor from environment (default 1.0; e.g. 60 = 1 min represents 1 hour)."""
    try:
        return float(os.getenv("SLA_TIME_SCALE", "1.0"))
    except ValueError:
        return 1.0


def _get_scale_for_report(report: Report, global_scale: float) -> float:
    """Return applicable SLA time scale for an individual report.
    
    Applies only if report.demo_accel is True or report was created after SLA_SCALE_FROM.
    Otherwise evaluates at 1.0x (real time).
    """
    if getattr(report, "demo_accel", False):
        return global_scale

    scale_from_raw = os.getenv("SLA_SCALE_FROM")
    if scale_from_raw and report.created_at:
        try:
            scale_from_dt = datetime.fromisoformat(scale_from_raw.replace("Z", "+00:00"))
            rpt_dt = report.created_at
            if scale_from_dt.tzinfo is not None and rpt_dt.tzinfo is None:
                rpt_dt = rpt_dt.replace(tzinfo=scale_from_dt.tzinfo)
            elif scale_from_dt.tzinfo is None and rpt_dt.tzinfo is not None:
                scale_from_dt = scale_from_dt.replace(tzinfo=rpt_dt.tzinfo)
            if rpt_dt >= scale_from_dt:
                return global_scale
        except Exception as e:
            logger.warning(f"Failed parsing SLA_SCALE_FROM ({scale_from_raw}): {e}")

    return 1.0


async def run_watchdog_check() -> Dict[str, Any]:
    """Inspect all active reports and apply idempotent tiered SLA escalations."""
    now = datetime.utcnow()
    scale = get_sla_time_scale()
    max_dispatches = int(os.getenv("WATCHDOG_MAX_DISPATCH_PER_RUN", "3"))
    dispatches_sent = 0

    checked_count = 0
    escalated_items: List[Dict[str, Any]] = []

    try:
        async with AsyncSessionLocal() as session:
            stmt = select(Report).where(
                Report.status.in_([StatusEnum.open, StatusEnum.in_progress])
            )
            res = await session.execute(stmt)
            active_reports = res.scalars().all()
            checked_count = len(active_reports)

            for report in active_reports:
                report_scale = _get_scale_for_report(report, scale)
                sla_hrs = float(report.sla_hours or 72)
                # Apply time scale compression
                scaled_sla_hrs = sla_hrs / max(0.0001, report_scale)
                effective_deadline = report.created_at + timedelta(hours=scaled_sla_hrs)

                if now > effective_deadline:
                    # Calculate how overdue
                    elapsed_secs = (now - report.created_at).total_seconds()
                    sla_secs = max(1.0, (effective_deadline - report.created_at).total_seconds())
                    overdue_ratio = elapsed_secs / sla_secs

                    # Tiered escalation criteria:
                    # Ratio >= 1.0 -> Level 1 (Dept Head Reminder)
                    # Ratio >= 1.4 -> Level 2 (Commissioner Escalation)
                    # Ratio >= 1.8 -> Level 3 (Public Overdue Flag)
                    current_level = report.escalation_level or 0
                    target_level = current_level
                    if overdue_ratio >= 1.8:
                        target_level = max(target_level, 3)
                    elif overdue_ratio >= 1.4:
                        target_level = max(target_level, 2)
                    elif overdue_ratio >= 1.0:
                        target_level = max(target_level, 1)

                    # Escalate one step at a time to maintain clean audit trail
                    if target_level > current_level:
                        if dispatches_sent >= max_dispatches:
                            logger.info(f"SLA watchdog reached max dispatch cap ({max_dispatches}) for this cycle.")
                            break

                        next_level = current_level + 1
                        report.escalation_level = next_level

                        if next_level >= 3:
                            report.is_overdue = True

                        report.updated_at = now
                        await session.commit()

                        # Draft and send escalation dispatch asynchronously
                        await draft_and_send_dispatch(
                            report_id=report.id,
                            kind="escalation",
                            escalation_level=next_level,
                        )
                        dispatches_sent += 1

                        escalated_items.append({
                            "report_id": report.id,
                            "title": report.title,
                            "escalation_level": next_level,
                            "is_overdue": report.is_overdue,
                            "overdue_ratio": round(overdue_ratio, 2),
                        })

    except Exception as e:
        logger.error(f"SLA watchdog run check error: {e}", exc_info=True)

    return {
        "timestamp": now.isoformat(),
        "sla_time_scale": scale,
        "checked": checked_count,
        "escalated_count": len(escalated_items),
        "escalated": escalated_items,
    }


async def watchdog_worker_loop():
    """Background polling loop for the SLA watchdog."""
    interval = int(os.getenv("WATCHDOG_INTERVAL_SEC", "60"))
    logger.info(f"SLA Watchdog worker started (Interval: {interval}s, Scale: {get_sla_time_scale()}x).")

    while True:
        try:
            await asyncio.sleep(interval)
            res = await run_watchdog_check()
            if res.get("escalated_count", 0) > 0:
                logger.info(f"SLA Watchdog escalated {res['escalated_count']} docket(s).")
        except asyncio.CancelledError:
            logger.info("SLA Watchdog background task cancelled.")
            break
        except Exception as e:
            logger.error(f"SLA Watchdog loop error: {e}")
            await asyncio.sleep(10)


def is_watchdog_running() -> bool:
    """Return True if the background watchdog task is active and running."""
    global _WATCHDOG_TASK
    return bool(_WATCHDOG_TASK and not _WATCHDOG_TASK.done())


def start_watchdog_background_task() -> asyncio.Task:
    """Start the watchdog background worker loop."""
    global _WATCHDOG_TASK
    if _WATCHDOG_TASK is None or _WATCHDOG_TASK.done():
        _WATCHDOG_TASK = asyncio.create_task(watchdog_worker_loop())
    return _WATCHDOG_TASK


def stop_watchdog_background_task():
    """Stop the watchdog background worker loop."""
    global _WATCHDOG_TASK
    if _WATCHDOG_TASK and not _WATCHDOG_TASK.done():
        _WATCHDOG_TASK.cancel()
