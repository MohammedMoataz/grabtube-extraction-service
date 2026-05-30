"""Per-item production: drive the backend, then embed MP3 metadata when needed."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from ..models.domain import Format, MediaItem
from .backend import ExtractionBackend
from .metadata import embed_mp3_metadata

_SAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(title: str, ext: str) -> str:
    base = _SAFE.sub("_", title or "download").strip().rstrip(".") or "download"
    return f"{base[:120]}.{ext}"


async def produce_item(
    backend: ExtractionBackend,
    item: MediaItem,
    fmt: Format,
    quality_id: str | None,
    dest: Path,
    on_progress: Callable[[int], None],
    is_canceled: Callable[[], bool],
) -> Path:
    path = await backend.produce(
        video_id=item.id,
        fmt=fmt,
        quality_id=quality_id,
        dest=dest,
        on_progress=on_progress,
        is_canceled=is_canceled,
    )
    if fmt is Format.mp3:
        embed_mp3_metadata(
            path,
            title=item.title or None,
            artist=item.author or None,
            cover_bytes=item.thumbnail_bytes,
        )
    return path
