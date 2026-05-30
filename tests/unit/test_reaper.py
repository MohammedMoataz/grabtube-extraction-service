"""Retention sweeper deletes expired results (FR-017, SC-008)."""

from pathlib import Path

from grabtube_extractor.models.domain import (
    Format,
    Job,
    JobStatus,
    LinkKind,
    ResultArtifact,
    ResultKind,
)
from grabtube_extractor.observability import Metrics
from grabtube_extractor.services.job_manager import JobManager
from grabtube_extractor.services.reaper import Reaper
from grabtube_extractor.services.resolver import Resolver
from tests.conftest import make_settings
from tests.fakes.fake_backend import FakeBackend


def _manager_with_completed_job(tmp_path, expires_at: float):
    settings = make_settings(tmp_path)
    backend = FakeBackend()
    manager = JobManager(settings, backend, Metrics(), Resolver(backend))
    f = Path(settings.work_dir) / "result.mp4"
    f.write_bytes(b"data")
    job = Job(
        job_id="job_1",
        source=LinkKind.video,
        format=Format.mp4,
        quality_id="137",
        status=JobStatus.completed,
    )
    job.result = ResultArtifact(
        path=str(f), kind=ResultKind.file, content_type="video/mp4", filename="result.mp4", expires_at=expires_at
    )
    job.result_kind = ResultKind.file
    manager.jobs[job.job_id] = job
    return manager, job, f


def test_sweep_deletes_expired(tmp_path):
    manager, job, f = _manager_with_completed_job(tmp_path, expires_at=100.0)
    removed = Reaper(manager).sweep_once(now=101.0)
    assert removed == 1
    assert not f.exists()
    assert job.result is None
    assert job.result_kind is None


def test_sweep_keeps_unexpired(tmp_path):
    manager, job, f = _manager_with_completed_job(tmp_path, expires_at=200.0)
    removed = Reaper(manager).sweep_once(now=100.0)
    assert removed == 0
    assert f.exists()
    assert job.result is not None
