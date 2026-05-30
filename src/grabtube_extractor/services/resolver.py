"""Resolve service: classify a link and shape raw backend data into domain entities.

Applies the hard 1080p cap (SC-004) and audio-availability detection (FR-004).
"""

from __future__ import annotations

from ..models.domain import (
    ErrorCode,
    LinkKind,
    MediaItem,
    Playlist,
    QualityOption,
)
from ..errors import ServiceError
from .backend import ExtractionBackend, RawVideo

MAX_HEIGHT = 1080


def _qualities_from_raw(video: RawVideo) -> list[QualityOption]:
    """MP4 formats with height <= 1080, de-duplicated by height, highest first."""
    by_height: dict[int, QualityOption] = {}
    for f in video.formats:
        if f.ext != "mp4" or f.vcodec == "none":
            continue
        if f.height > MAX_HEIGHT or f.height <= 0:
            continue
        # Keep the first format id seen per height.
        by_height.setdefault(f.height, QualityOption(id=f.id, label=f"{f.height}p", height_px=f.height))
    return [by_height[h] for h in sorted(by_height, reverse=True)]


def _to_media_item(video: RawVideo) -> MediaItem:
    return MediaItem(
        id=video.id,
        title=video.title,
        author=video.author,
        thumbnail_url=video.thumbnail_url,
        duration_seconds=video.duration_seconds,
        audio_available=video.has_audio,
        qualities=_qualities_from_raw(video),
        thumbnail_bytes=video.thumbnail_bytes,
    )


class Resolver:
    def __init__(self, backend: ExtractionBackend):
        self.backend = backend

    async def resolve(self, url: str) -> tuple[LinkKind, MediaItem | None, Playlist | None]:
        if not url or not isinstance(url, str):
            raise ServiceError(ErrorCode.invalid_url)

        raw = await self.backend.resolve(url)

        if raw.kind == "playlist" and raw.playlist is not None:
            items = [_to_media_item(v) for v in raw.playlist.items]
            playlist = Playlist(
                id=raw.playlist.id,
                title=raw.playlist.title,
                count=len(items),
                items=items,
            )
            return LinkKind.playlist, None, playlist

        if raw.kind == "video" and raw.video is not None:
            item = _to_media_item(raw.video)
            if not item.qualities and not item.audio_available:
                raise ServiceError(ErrorCode.no_formats)
            return LinkKind.video, item, None

        raise ServiceError(ErrorCode.invalid_url)
