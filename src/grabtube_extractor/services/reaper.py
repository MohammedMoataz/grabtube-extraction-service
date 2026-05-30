"""Background sweeper enforcing the 30-minute retention window (FR-017, SC-008).

- Deletes result artifacts at/after their ``expires_at``.
- On startup, removes orphaned job directories from a previous run.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path
from typing import Callable

from .job_manager import JobManager

logger = logging.getLogger("grabtube")


class Reaper:
    def __init__(self, manager: JobManager, interval_s: int = 60, clock: Callable[[], float] = time.time):
        self.manager = manager
        self.interval_s = interval_s
        self.clock = clock
        self._task: asyncio.Task | None = None

    def sweep_once(self, now: float | None = None) -> int:
        """Delete expired results. Returns the number of artifacts removed."""
        now = self.clock() if now is None else now
        removed = 0
        for job in self.manager.jobs.values():
            result = job.result
            if result is None:
                continue
            if now >= result.expires_at:
                if self._delete(result.path):
                    removed += 1
                job.result = None
                job.result_kind = None
        return removed

    def cleanup_orphans(self) -> None:
        """Remove job working directories with no live job (e.g. after a restart)."""
        work_dir = Path(self.manager.settings.work_dir)
        if not work_dir.exists():
            return
        live = set(self.manager.jobs.keys())
        for child in work_dir.glob("job_*"):
            if child.is_dir() and child.name not in live:
                shutil.rmtree(child, ignore_errors=True)

    async def run_forever(self) -> None:
        self.cleanup_orphans()
        try:
            while True:
                await asyncio.sleep(self.interval_s)
                try:
                    self.sweep_once()
                except Exception:  # noqa: BLE001
                    logger.exception("reaper sweep failed")
        except asyncio.CancelledError:
            return

    def start(self) -> None:
        self._task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    @staticmethod
    def _delete(path: str) -> bool:
        p = Path(path)
        try:
            if p.exists():
                p.unlink()
                return True
        except OSError:
            logger.warning("could not delete %s", path)
        return False
