"""Bounded worker pool: excess jobs wait in 'queued'; pool never exceeds the cap (FR-020, SC-009)."""

import asyncio

from grabtube_extractor.models.domain import Format, JobStatus, LinkKind
from grabtube_extractor.observability import Metrics
from grabtube_extractor.services.job_manager import JobManager
from grabtube_extractor.services.resolver import Resolver
from tests.conftest import make_settings
from tests.fakes.fake_backend import FakeBackend


async def test_pool_caps_concurrency_and_queues_excess(tmp_path):
    settings = make_settings(tmp_path, max_concurrency=2)
    backend = FakeBackend(block=True)
    manager = JobManager(settings, backend, Metrics(), Resolver(backend))

    jobs = [manager.create_job(LinkKind.video, f"v{i}", Format.mp4, "137") for i in range(4)]

    # Let two jobs reach produce(); the other two should be parked on the semaphore.
    await asyncio.sleep(0.15)
    assert backend.active == 2
    assert backend.max_active <= 2
    assert sum(1 for j in jobs if j.status is JobStatus.queued) == 2
    assert manager.queue_depth == 2

    backend.release.set()  # let everything finish

    for j in jobs:
        for _ in range(300):
            if j.status in (JobStatus.completed, JobStatus.failed):
                break
            await asyncio.sleep(0.01)

    assert all(j.status is JobStatus.completed for j in jobs)
    assert backend.max_active <= 2  # never exceeded the cap over the whole run
    await manager.shutdown()
