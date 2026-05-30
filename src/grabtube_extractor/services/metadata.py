"""MP3 metadata embedding via mutagen (FR-008, SC-003).

Embeds title, author/artist, cover art (APIC) and optional extra fields. Missing fields
are omitted without failing the job. Uses real mutagen so it works offline in tests.
"""

from __future__ import annotations

import logging
from pathlib import Path

from mutagen.id3 import ID3, APIC, TALB, TDRC, TIT2, TPE1
from mutagen.id3 import ID3NoHeaderError

logger = logging.getLogger("grabtube")


def embed_mp3_metadata(
    path: str | Path,
    *,
    title: str | None = None,
    artist: str | None = None,
    cover_bytes: bytes | None = None,
    cover_mime: str = "image/jpeg",
    album: str | None = None,
    year: str | None = None,
) -> None:
    path = str(path)
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    if title:
        tags.setall("TIT2", [TIT2(encoding=3, text=title)])
    if artist:
        tags.setall("TPE1", [TPE1(encoding=3, text=artist)])
    if album:
        tags.setall("TALB", [TALB(encoding=3, text=album)])
    if year:
        # TDRC is the ID3v2.4 recording-time frame (mutagen saves v2.4 by default).
        tags.setall("TDRC", [TDRC(encoding=3, text=str(year))])
    if cover_bytes:
        tags.setall(
            "APIC",
            [APIC(encoding=3, mime=cover_mime, type=3, desc="Cover", data=cover_bytes)],
        )

    tags.save(path)
