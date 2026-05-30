"""Deterministic in-memory extraction backend for tests (no live upstream, no ffmpeg).

URL conventions used by the suite:
- contains "list=" / "playlist"  -> a 3-item playlist (middle item id "failitem" fails)
- contains "invalid"             -> invalid_url
- contains "unavailable"/"private" -> unavailable
- contains "live"                -> live_unsupported
- contains "drm"                 -> drm_protected
- contains "noformats"           -> a video with no formats and no audio
- otherwise                      -> a normal video with 1440p (excluded), 1080p, 720p + audio
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

from grabtube_extractor.models.domain import ErrorCode, Format
from grabtube_extractor.errors import ServiceError
from grabtube_extractor.services.backend import RawFormat, RawPlaylist, RawResolve, RawVideo

# Minimal fixture payloads (not real media; tests check headers/bytes/tags, not playback).
TINY_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomFAKEMP4DATA"
TINY_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 64  # a plausible MPEG audio frame header + padding
TINY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 16 + b"\xff\xd9"


def _normal_video(video_id: str = "abc123") -> RawVideo:
    return RawVideo(
        id=video_id,
        title="Example Video",
        author="Channel Name",
        thumbnail_url="https://img.example/hq.jpg",
        duration_seconds=372,
        has_audio=True,
        formats=[
            RawFormat(id="271", height=1440, ext="mp4", vcodec="vp9"),  # excluded (>1080p)
            RawFormat(id="137", height=1080, ext="mp4", vcodec="avc1"),
            RawFormat(id="136", height=720, ext="mp4", vcodec="avc1"),
        ],
        thumbnail_bytes=TINY_JPEG,
    )


class FakeBackend:
    def __init__(self, *, block: bool = False):
        self.block = block
        self.release = asyncio.Event()
        self.active = 0
        self.max_active = 0
        self.produced_ids: list[str] = []

    async def resolve(self, url: str) -> RawResolve:
        u = url.lower()
        if "invalid" in u:
            raise ServiceError(ErrorCode.invalid_url)
        if "unavailable" in u or "private" in u:
            raise ServiceError(ErrorCode.unavailable)
        if "live" in u:
            raise ServiceError(ErrorCode.live_unsupported)
        if "drm" in u:
            raise ServiceError(ErrorCode.drm_protected)
        if "noformats" in u:
            v = _normal_video("noform")
            v.formats = []
            v.has_audio = False
            return RawResolve(kind="video", video=v)
        if "list=" in u or "playlist" in u:
            items = [
                _normal_video("vid1"),
                _normal_video("failitem"),
                _normal_video("vid3"),
            ]
            for it in items:
                it.title = f"Item {it.id}"
            return RawResolve(
                kind="playlist",
                playlist=RawPlaylist(id="PL123", title="My Playlist", items=items),
            )
        return RawResolve(kind="video", video=_normal_video())

    async def produce(
        self,
        *,
        video_id: str,
        fmt: Format,
        quality_id: str | None,
        dest: Path,
        on_progress: Callable[[int], None],
        is_canceled: Callable[[], bool],
    ) -> Path:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            on_progress(10)
            if self.block:
                for _ in range(2000):
                    if is_canceled():
                        raise ServiceError(ErrorCode.timeout, "Canceled.")
                    if self.release.is_set():
                        break
                    await asyncio.sleep(0.005)
            if video_id == "failitem":
                raise ServiceError(ErrorCode.unavailable, "Item could not be processed.")

            ext = "mp4" if fmt is Format.mp4 else "mp3"
            out = dest.with_suffix(f".{ext}")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(TINY_MP4 if fmt is Format.mp4 else TINY_MP3)
            self.produced_ids.append(video_id)
            on_progress(100)
            return out
        finally:
            self.active -= 1
