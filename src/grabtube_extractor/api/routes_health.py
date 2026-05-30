"""Health/readiness + metrics signal (Constitution V)."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    metrics = request.app.state.metrics
    manager = request.app.state.job_manager
    metrics.queue_depth = manager.queue_depth
    return {"status": "ok", "metrics": metrics.snapshot()}
