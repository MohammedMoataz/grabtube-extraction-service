"""Quality filtering: never return >1080p (SC-004, 0 violations)."""

from grabtube_extractor.services.backend import RawFormat, RawVideo
from grabtube_extractor.services.resolver import _qualities_from_raw


def test_excludes_above_1080_and_sorts_desc():
    video = RawVideo(
        id="x",
        title="t",
        formats=[
            RawFormat(id="a", height=2160, ext="mp4", vcodec="vp9"),
            RawFormat(id="b", height=1440, ext="mp4", vcodec="vp9"),
            RawFormat(id="c", height=1080, ext="mp4", vcodec="avc1"),
            RawFormat(id="d", height=720, ext="mp4", vcodec="avc1"),
        ],
    )
    qualities = _qualities_from_raw(video)
    heights = [q.height_px for q in qualities]
    assert heights == [1080, 720]
    assert all(h <= 1080 for h in heights)  # zero violations


def test_drops_non_mp4_and_audio_only():
    video = RawVideo(
        id="x",
        title="t",
        formats=[
            RawFormat(id="webm", height=1080, ext="webm", vcodec="vp9"),
            RawFormat(id="audio", height=0, ext="mp4", vcodec="none"),
            RawFormat(id="ok", height=480, ext="mp4", vcodec="avc1"),
        ],
    )
    assert [q.height_px for q in _qualities_from_raw(video)] == [480]
