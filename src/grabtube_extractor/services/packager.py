"""Package multiple produced files into a single ZIP (FR-009)."""

from __future__ import annotations

import zipfile
from pathlib import Path


def build_zip(dest_zip: str | Path, files: list[tuple[str, str | Path]]) -> Path:
    """Write ``files`` (list of (arcname, path)) into ``dest_zip``. Returns the path."""
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        used: set[str] = set()
        for arcname, src in files:
            name = _unique(arcname, used)
            zf.write(src, arcname=name)
    return dest_zip


def _unique(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem, dot, ext = name.rpartition(".")
    i = 2
    while True:
        candidate = f"{stem} ({i}).{ext}" if dot else f"{name} ({i})"
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1
