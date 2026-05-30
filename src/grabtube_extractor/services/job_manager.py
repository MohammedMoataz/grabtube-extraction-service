"""In-memory async job manager with a bounded worker pool (FR-011, FR-020).

- A global ``asyncio.Semaphore`` (size = max_concurrency) is the backpressure mechanism:
  while a job waits for a slot it stays ``queued``.
- Playlist items are processed sequentially within a job; per-item failures are tolerated
  (partial success, FR-010).
- Cancellation is cooperative: checked between items and passed into the backend.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable

from ..config import Settings
from ..models.domain import (
    ErrorCode,
    Format,
    ItemStatus,
    Job,
    JobItem,
    JobStatus,
    LinkKind,
    ResultArtifact,
    ResultKind,
)
from ..errors import ServiceError
from ..observability import Metrics
from . import extractor, packager
from .backend import ExtractionBackend
from .resolver import Resolver

logger = logging.getLogger("grabtube")

_CONTENT_TYPE = {Format.mp4: "video/mp4", Format.mp3: "audio/mpeg"}
_EXT = {Format.mp4: "mp4", Format.mp3: "mp3"}


def _video_url(media_id: str) -> str:
    return f"https://www.youtube.com/watch?v={media_id}"


def _playlist_url(media_id: str) -> str:
    return f"https://www.youtube.com/playlist?list={media_id}"


class JobManager:
    def __init__(
        self,
        settings: Settings,
        backend: ExtractionBackend,
        metrics: Metrics,
        resolver: Resolver,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self.backend = backend
        self.metrics = metrics
        self.resolver = resolver
        self.clock = clock
        self.jobs: dict[str, Job] = {}
        self.semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._counter = 0
        self._tasks: set[asyncio.Task] = set()

    # --- public API --------------------------------------------------------------
    def create_job(self, source: LinkKind, media_id: str, fmt: Format, quality_id: str | None) -> Job:
        if fmt is Format.mp4 and source is LinkKind.video and not quality_id:
            raise ServiceError(ErrorCode.quality_required)
        if fmt is Format.mp3:
            quality_id = None

        self._counter += 1
        job = Job(
            job_id=f"job_{self._counter}",
            source=source,
            format=fmt,
            quality_id=quality_id,
            created_at=self.clock(),
        )
        self.jobs[job.job_id] = job
        self.metrics.jobs_created += 1

        task = asyncio.create_task(self._run(job, media_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    def get(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise ServiceError(ErrorCode.not_found)
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status in (JobStatus.queued, JobStatus.running):
            job.cancel_event.set()
        return job

    @property
    def queue_depth(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status is JobStatus.queued)

    async def shutdown(self) -> None:
        for t in list(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    # --- execution ---------------------------------------------------------------
    async def _run(self, job: Job, media_id: str) -> None:
        try:
            if job.is_canceled:
                return self._finalize_cancel(job)
            async with self.semaphore:
                if job.is_canceled:
                    return self._finalize_cancel(job)
                job.status = JobStatus.running
                await self._process(job, media_id)
        except ServiceError as exc:
            self._finalize_failure(job, exc.code, exc.message)
        except asyncio.CancelledError:
            self._finalize_cancel(job)
            raise
        except Exception:  # noqa: BLE001
            logger.exception("job %s crashed", job.job_id)
            self._finalize_failure(job, ErrorCode.internal, "Something went wrong.")

    async def _process(self, job: Job, media_id: str) -> None:
        url = _video_url(media_id) if job.source is LinkKind.video else _playlist_url(media_id)
        _, item, playlist = await self.resolver.resolve(url)
        items = [item] if item is not None else (playlist.items if playlist else [])
        if not items:
            raise ServiceError(ErrorCode.unavailable)

        job.items = [JobItem(item_id=i.id, title=i.title) for i in items]
        job_dir = Path(self.settings.work_dir) / job.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        n = len(items)
        produced: list[tuple[str, Path]] = []

        for idx, media in enumerate(items):
            if job.is_canceled:
                return self._finalize_cancel(job)
            ji = job.items[idx]
            ji.status = ItemStatus.running

            def on_progress(p: int, _idx: int = idx, _ji: JobItem = ji) -> None:
                _ji.progress = p
                job.overall_progress = int(((_idx * 100) + p) / n)

            quality = job.quality_id if job.source is LinkKind.video else None
            dest = job_dir / media.id
            try:
                path = await extractor.produce_item(
                    self.backend, media, job.format, quality, dest, on_progress, lambda: job.is_canceled
                )
                ji.status = ItemStatus.done
                ji.progress = 100
                ji.artifact_path = str(path)
                produced.append((extractor.safe_filename(media.title, _EXT[job.format]), path))
            except ServiceError as exc:
                ji.status = ItemStatus.failed
                ji.progress = 0
                logger.warning("job %s item %s failed: %s", job.job_id, media.id, exc.code.value)

        if job.is_canceled:
            return self._finalize_cancel(job)
        if not produced:
            raise ServiceError(ErrorCode.unavailable, "No items could be processed.")

        self._finalize_success(job, produced, job_dir)

    # --- finalizers --------------------------------------------------------------
    def _finalize_success(self, job: Job, produced: list[tuple[str, Path]], job_dir: Path) -> None:
        now = self.clock()
        expires = now + self.settings.retention_seconds
        if job.source is LinkKind.playlist:
            zip_path = job_dir / "result.zip"
            packager.build_zip(zip_path, [(name, p) for name, p in produced])
            title = extractor.safe_filename(f"playlist_{job.job_id}", "zip")
            job.result = ResultArtifact(
                path=str(zip_path), kind=ResultKind.zip, content_type="application/zip",
                filename=title, expires_at=expires,
            )
            job.result_kind = ResultKind.zip
        else:
            name, path = produced[0]
            job.result = ResultArtifact(
                path=str(path), kind=ResultKind.file, content_type=_CONTENT_TYPE[job.format],
                filename=name, expires_at=expires,
            )
            job.result_kind = ResultKind.file

        job.status = JobStatus.completed
        job.overall_progress = 100
        job.completed_at = now
        self.metrics.jobs_completed += 1
        self.metrics.record_duration(now - job.created_at)

    def _finalize_failure(self, job: Job, code: ErrorCode, message: str) -> None:
        job.status = JobStatus.failed
        job.error_code = code
        job.error_message = message
        job.completed_at = self.clock()
        self.metrics.jobs_failed += 1

    def _finalize_cancel(self, job: Job) -> None:
        job.status = JobStatus.canceled
        job.completed_at = self.clock()
        self.metrics.jobs_canceled += 1
        self._cleanup_partial(job)

    def _cleanup_partial(self, job: Job) -> None:
        for ji in job.items:
            if ji.artifact_path:
                try:
                    Path(ji.artifact_path).unlink(missing_ok=True)
                except OSError:
                    pass
