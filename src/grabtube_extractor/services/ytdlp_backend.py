"""Real extraction backend: yt-dlp (library) + ffmpeg (subprocess) + thumbnail fetch.

This is the production implementation. It is intentionally not exercised by the test
suite (which injects a fake) so tests stay deterministic and offline; correctness here is
covered by manual/CI smoke tests against live sources.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from ..config import Settings
from ..models.domain import ErrorCode, Format
from ..errors import ServiceError
from .backend import ExtractionBackend, ProgressCb, RawFormat, RawPlaylist, RawResolve, RawVideo

logger = logging.getLogger("grabtube")

MAX_HEIGHT = 1080


def format_opts(fmt: Format, quality_id: str | None) -> dict:
    """yt-dlp format + post-processing options for one item.

    MP3 writes the source thumbnail, converts it to JPEG and embeds it as cover art
    (FR-008); the later mutagen tagging step keeps that APIC frame.
    """
    if fmt is Format.mp4:
        return {
            "format": f"{quality_id}+bestaudio/best" if quality_id else f"bestvideo[height<={MAX_HEIGHT}]+bestaudio/best",
            "merge_output_format": "mp4",
            "writethumbnail": False,
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
        }
    return {
        "format": "bestaudio/best",
        "merge_output_format": None,
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "EmbedThumbnail"},
        ],
    }


class YtDlpBackend(ExtractionBackend):
    def __init__(self, settings: Settings):
        self.settings = settings

    # --- helpers -----------------------------------------------------------------
    def _ydl_opts(self, extra: dict | None = None) -> dict:
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
            "skip_download": True,
        }
        if self.settings.proxy_url:
            opts["proxy"] = self.settings.proxy_url
        if self.settings.cookies_file:
            opts["cookiefile"] = self.settings.cookies_file
        if extra:
            opts.update(extra)
        return opts

    @staticmethod
    def _classify_error(exc: Exception) -> ServiceError:
        msg = str(exc).lower()
        if "private" in msg or "unavailable" in msg or "removed" in msg or "deleted" in msg:
            return ServiceError(ErrorCode.unavailable)
        if "live" in msg or "premiere" in msg or "upcoming" in msg:
            return ServiceError(ErrorCode.live_unsupported)
        if "drm" in msg or "protected" in msg:
            return ServiceError(ErrorCode.drm_protected)
        if "unsupported url" in msg or "is not a valid url" in msg:
            return ServiceError(ErrorCode.invalid_url)
        return ServiceError(ErrorCode.unavailable)

    def _to_raw_video(self, info: dict) -> RawVideo:
        formats = []
        for f in info.get("formats", []):
            height = f.get("height") or 0
            if f.get("ext") == "mp4" and f.get("vcodec") not in (None, "none") and height:
                formats.append(RawFormat(id=str(f.get("format_id")), height=int(height), ext="mp4", vcodec=f.get("vcodec")))
        has_audio = any(f.get("acodec") not in (None, "none") for f in info.get("formats", []))
        if info.get("is_live"):
            raise ServiceError(ErrorCode.live_unsupported)
        return RawVideo(
            id=str(info.get("id")),
            title=info.get("title") or "",
            author=info.get("uploader") or info.get("channel") or "",
            thumbnail_url=info.get("thumbnail") or "",
            duration_seconds=int(info.get("duration") or 0),
            has_audio=has_audio,
            formats=formats,
        )

    # --- interface ---------------------------------------------------------------
    async def resolve(self, url: str) -> RawResolve:
        import yt_dlp  # imported lazily so the package imports without the binary present

        def _extract() -> dict:
            with yt_dlp.YoutubeDL(self._ydl_opts({"extract_flat": "in_playlist"})) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await asyncio.to_thread(_extract)
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped to a user-safe error
            logger.warning("resolve failed: %s", exc)
            raise self._classify_error(exc) from exc

        if not info:
            raise ServiceError(ErrorCode.invalid_url)

        if info.get("_type") == "playlist" or "entries" in info:
            items = []
            for entry in info.get("entries", []) or []:
                if not entry:
                    continue
                items.append(
                    RawVideo(
                        id=str(entry.get("id")),
                        title=entry.get("title") or "",
                        author=entry.get("uploader") or "",
                        thumbnail_url=entry.get("thumbnail") or "",
                        duration_seconds=int(entry.get("duration") or 0),
                    )
                )
            return RawResolve(
                kind="playlist",
                playlist=RawPlaylist(id=str(info.get("id")), title=info.get("title") or "", items=items),
            )

        return RawResolve(kind="video", video=self._to_raw_video(info))

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
        import yt_dlp

        url = f"https://www.youtube.com/watch?v={video_id}"
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _hook(d: dict) -> None:
            if is_canceled():
                raise ServiceError(ErrorCode.timeout, "Canceled.")
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if total:
                    on_progress(min(99, int(done * 100 / total)))
            elif d.get("status") == "finished":
                on_progress(99)

        opts = self._ydl_opts(
            {
                "skip_download": False,
                "noplaylist": True,
                "outtmpl": str(dest.with_suffix(".%(ext)s")),
                "progress_hooks": [_hook],
                **format_opts(fmt, quality_id),
            }
        )

        def _download() -> None:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

        try:
            await asyncio.wait_for(asyncio.to_thread(_download), timeout=self.settings.job_timeout_s)
        except asyncio.TimeoutError as exc:
            raise ServiceError(ErrorCode.timeout) from exc
        except ServiceError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("produce failed for %s: %s", video_id, exc)
            raise self._classify_error(exc) from exc

        # yt-dlp writes <dest>.<ext>; normalise to the expected dest path.
        produced = self._find_output(dest, fmt)
        on_progress(100)
        return produced

    @staticmethod
    def _find_output(dest: Path, fmt: Format) -> Path:
        ext = "mp4" if fmt is Format.mp4 else "mp3"
        candidate = dest.with_suffix(f".{ext}")
        if candidate.exists():
            return candidate
        # Fall back to whatever sibling was produced.
        for sibling in dest.parent.glob(dest.stem + ".*"):
            return sibling
        raise ServiceError(ErrorCode.internal, "Conversion produced no output.")
