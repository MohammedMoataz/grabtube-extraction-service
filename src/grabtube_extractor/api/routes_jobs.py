"""Job endpoints: create, poll, download, cancel (US2–US5)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse

from ..models.domain import ErrorCode, Format, JobStatus, LinkKind
from ..errors import ServiceError
from ..middleware.rate_limit import make_dependency
from ..models.schemas import (
    CancelResponse,
    CreateJobRequest,
    CreateJobResponse,
    job_status_out,
)

router = APIRouter()


@router.post("/jobs", status_code=202)
async def create_job(req: CreateJobRequest, request: Request, _rl=Depends(make_dependency("jobs"))):
    manager = request.app.state.job_manager
    source = LinkKind.playlist if req.source == "playlist" else LinkKind.video
    fmt = Format.mp4 if req.format == "mp4" else Format.mp3
    job = manager.create_job(source, req.id, fmt, req.qualityId)
    return JSONResponse(
        CreateJobResponse(jobId=job.job_id, status=job.status.value).model_dump(),
        status_code=202,
    )


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    manager = request.app.state.job_manager
    job = manager.get(job_id)
    return JSONResponse(job_status_out(job).model_dump())


@router.get("/jobs/{job_id}/file")
async def download(job_id: str, request: Request):
    manager = request.app.state.job_manager
    job = manager.get(job_id)
    if job.status is not JobStatus.completed or job.result is None:
        # Completed-then-swept results read as expired; otherwise the result isn't ready.
        if job.completed_at is not None and job.result is None:
            raise ServiceError(ErrorCode.result_expired)
        raise ServiceError(ErrorCode.not_found, "Result is not ready.")

    result = job.result
    if not Path(result.path).exists():
        raise ServiceError(ErrorCode.result_expired)

    return FileResponse(
        path=result.path,
        media_type=result.content_type,
        filename=result.filename,
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, request: Request):
    manager = request.app.state.job_manager
    job = manager.cancel(job_id)
    # If the job already finished, report its real terminal state; otherwise it's been
    # signaled to cancel and the worker will transition cooperatively.
    if job.status in (JobStatus.completed, JobStatus.failed):
        status = job.status.value
    else:
        status = "canceled"
    return JSONResponse(CancelResponse(jobId=job.job_id, status=status).model_dump())
