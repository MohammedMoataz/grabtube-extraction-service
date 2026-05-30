"""Internal domain model (in-memory / on-disk) per data-model.md.

These are the service's own types. Wire shapes live in ``schemas.py``; the mapping
between the two is handled in the API layer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum


class LinkKind(str, Enum):
    video = "video"
    playlist = "playlist"
    invalid = "invalid"


class Format(str, Enum):
    mp4 = "mp4"
    mp3 = "mp3"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


class ItemStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class ResultKind(str, Enum):
    file = "file"
    zip = "zip"


class ErrorCode(str, Enum):
    invalid_url = "invalid_url"
    unavailable = "unavailable"
    live_unsupported = "live_unsupported"
    drm_protected = "drm_protected"
    no_formats = "no_formats"
    quality_required = "quality_required"
    timeout = "timeout"
    rate_limited = "rate_limited"
    result_expired = "result_expired"
    not_found = "not_found"
    internal = "internal"


@dataclass
class QualityOption:
    id: str
    label: str
    height_px: int
    container: str = "mp4"


@dataclass
class MediaItem:
    id: str
    title: str
    author: str = ""
    thumbnail_url: str = ""
    duration_seconds: int = 0
    audio_available: bool = False
    qualities: list[QualityOption] = field(default_factory=list)
    # Internal-only: raw thumbnail bytes for MP3 cover-art embedding (never serialized).
    thumbnail_bytes: bytes | None = None


@dataclass
class Playlist:
    id: str
    title: str
    count: int
    items: list[MediaItem] = field(default_factory=list)


@dataclass
class ResultArtifact:
    path: str
    kind: ResultKind
    content_type: str
    filename: str
    expires_at: float  # epoch seconds; sweeper deletes at/after this


@dataclass
class JobItem:
    item_id: str
    title: str
    status: ItemStatus = ItemStatus.pending
    progress: int = 0
    artifact_path: str | None = None


@dataclass
class Job:
    job_id: str
    source: LinkKind
    format: Format
    quality_id: str | None
    status: JobStatus = JobStatus.queued
    overall_progress: int = 0
    result_kind: ResultKind | None = None
    result: ResultArtifact | None = None
    error_code: ErrorCode | None = None
    error_message: str | None = None
    items: list[JobItem] = field(default_factory=list)
    created_at: float = 0.0
    completed_at: float | None = None
    # Cooperative cancellation signal, checked between items and before each conversion.
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def is_canceled(self) -> bool:
        return self.cancel_event.is_set()
