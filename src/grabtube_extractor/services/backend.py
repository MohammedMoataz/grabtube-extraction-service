"""Extraction backend abstraction.

The backend is the low-level capability (yt-dlp + ffmpeg) and is **injectable** so the
test suite can substitute a deterministic fake (Constitution VI: no live upstream in tests).
The service layer (resolver/extractor/job_manager) depends only on this interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from ..models.domain import Format


@dataclass
class RawFormat:
    id: str
    height: int
    ext: str
    vcodec: str  # "none" for audio-only


@dataclass
class RawVideo:
    id: str
    title: str
    author: str = ""
    thumbnail_url: str = ""
    duration_seconds: int = 0
    has_audio: bool = True
    formats: list[RawFormat] = field(default_factory=list)
    thumbnail_bytes: bytes | None = None


@dataclass
class RawPlaylist:
    id: str
    title: str
    items: list[RawVideo] = field(default_factory=list)


@dataclass
class RawResolve:
    kind: str  # "video" | "playlist"
    video: RawVideo | None = None
    playlist: RawPlaylist | None = None


# Progress callback: receives 0..100 for the current item.
ProgressCb = Callable[[int], None]


class ExtractionBackend(Protocol):
    async def resolve(self, url: str) -> RawResolve:
        """Resolve a URL into raw metadata + formats. Raise ServiceError on failure."""
        ...

    async def produce(
        self,
        *,
        video_id: str,
        fmt: Format,
        quality_id: str | None,
        dest: Path,
        on_progress: ProgressCb,
        is_canceled: Callable[[], bool],
    ) -> Path:
        """Produce the media file for ``video_id`` at ``dest``. Raise ServiceError on failure."""
        ...
