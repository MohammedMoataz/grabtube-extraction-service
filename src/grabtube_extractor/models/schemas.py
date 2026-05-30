"""Pydantic request/response models — the wire contract (extraction-service.md).

Field names use the contract's camelCase exactly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .domain import (
    Job,
    MediaItem,
    Playlist,
    QualityOption,
)


# --- /resolve ---------------------------------------------------------------------
class ResolveRequest(BaseModel):
    url: str


class QualityOut(BaseModel):
    id: str
    label: str
    heightPx: int
    container: str = "mp4"


class MediaItemOut(BaseModel):
    id: str
    title: str
    author: str
    thumbnailUrl: str
    durationSeconds: int
    audioAvailable: bool
    qualities: list[QualityOut]


class PlaylistOut(BaseModel):
    id: str
    title: str
    count: int
    items: list[MediaItemOut]


class ResolveVideoResponse(BaseModel):
    kind: Literal["video"] = "video"
    item: MediaItemOut


class ResolvePlaylistResponse(BaseModel):
    kind: Literal["playlist"] = "playlist"
    playlist: PlaylistOut


# --- /jobs ------------------------------------------------------------------------
class CreateJobRequest(BaseModel):
    source: Literal["video", "playlist"]
    id: str
    format: Literal["mp4", "mp3"]
    qualityId: str | None = None


class CreateJobResponse(BaseModel):
    jobId: str
    status: str


class JobItemOut(BaseModel):
    itemId: str
    title: str
    status: str
    progress: int


class JobStatusResponse(BaseModel):
    jobId: str
    status: str
    overallProgress: int
    resultKind: str | None = None
    resultUrl: str | None = None
    error: dict | None = None
    items: list[JobItemOut]


class CancelResponse(BaseModel):
    jobId: str
    status: str


# --- mappers ----------------------------------------------------------------------
def quality_out(q: QualityOption) -> QualityOut:
    return QualityOut(id=q.id, label=q.label, heightPx=q.height_px, container=q.container)


def media_item_out(m: MediaItem) -> MediaItemOut:
    return MediaItemOut(
        id=m.id,
        title=m.title,
        author=m.author,
        thumbnailUrl=m.thumbnail_url,
        durationSeconds=m.duration_seconds,
        audioAvailable=m.audio_available,
        qualities=[quality_out(q) for q in m.qualities],
    )


def playlist_out(p: Playlist) -> PlaylistOut:
    return PlaylistOut(
        id=p.id,
        title=p.title,
        count=p.count,
        items=[media_item_out(i) for i in p.items],
    )


def job_status_out(job: Job) -> JobStatusResponse:
    error = None
    if job.error_code is not None:
        error = {"code": job.error_code.value, "message": job.error_message or ""}
    result_url = None
    if job.result is not None:
        result_url = f"/jobs/{job.job_id}/file"
    return JobStatusResponse(
        jobId=job.job_id,
        status=job.status.value,
        overallProgress=job.overall_progress,
        resultKind=job.result_kind.value if job.result_kind else None,
        resultUrl=result_url,
        error=error,
        items=[
            JobItemOut(itemId=i.item_id, title=i.title, status=i.status.value, progress=i.progress)
            for i in job.items
        ],
    )
