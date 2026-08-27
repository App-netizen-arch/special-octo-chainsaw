"""APScheduler wiring: daily legal update monitoring + manual trigger.

The scheduler runs in-process (single-conductor deployment). Jobs are
idempotent and safe to re-run; the DB-level content hash deduplicates.
"""

from __future__ import annotations

import asyncio
import logging

from ..config import settings

log = logging.getLogger("counsel.scheduler")

_scheduler = None


def start_scheduler() -> None:
    """Start the background scheduler when updates are enabled."""
    global _scheduler
    if not settings.updates_enabled or _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.warning("APScheduler not installed — legal update monitoring disabled.")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    async def _daily_refresh() -> None:
        from .legal_updates import refresh_updates

        try:
            await refresh_updates()
        except Exception:  # noqa: BLE001 — scheduled jobs must never crash boot
            log.exception("scheduled update refresh failed")

    def _run_daily() -> None:
        asyncio.get_event_loop().create_task(_daily_refresh())

    _scheduler.add_job(
        _run_daily,
        CronTrigger(hour=settings.updates_hour_utc, minute=15),
        id="legal_updates_daily",
        replace_existing=True,
    )
    # light housekeeping: purge expired research cache rows daily
    def _purge_cache() -> None:
        import time

        from ..database import session_scope
        from ..models.db import ResearchCache

        with session_scope() as s:
            n = (
                s.query(ResearchCache)
                .filter(ResearchCache.expires_at < time.time())
                .delete()
            )
        if n:
            log.info("purged %d expired research cache rows", int(n))

    _scheduler.add_job(_purge_cache, CronTrigger(hour=4, minute=5),
                       id="cache_purge", replace_existing=True)
    _scheduler.start()
    log.info("scheduler started (updates at %02d:15 UTC)", settings.updates_hour_utc)


def shutdown_scheduler() -> None:
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


async def trigger_update_check_now() -> dict[str, int]:
    """Manual 'Check for updates now' button."""
    from .legal_updates import refresh_updates

    return await refresh_updates(force=True)
