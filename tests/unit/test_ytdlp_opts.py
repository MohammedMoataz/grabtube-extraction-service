"""yt-dlp option building for the real backend (the backend itself needs live sources)."""

from grabtube_extractor.models.domain import Format
from grabtube_extractor.services.ytdlp_backend import format_opts


def _keys(opts):
    return [p["key"] for p in opts["postprocessors"]]


def test_mp3_writes_and_embeds_the_thumbnail_as_cover_art():
    opts = format_opts(Format.mp3, None)
    assert opts["writethumbnail"] is True
    assert _keys(opts) == ["FFmpegThumbnailsConvertor", "FFmpegExtractAudio", "EmbedThumbnail"]
    assert opts["postprocessors"][0]["format"] == "jpg"


def test_mp4_keeps_quality_selection_and_skips_thumbnails():
    opts = format_opts(Format.mp4, "137")
    assert opts["format"] == "137+bestaudio/best"
    assert opts["writethumbnail"] is False
    assert _keys(opts) == ["FFmpegVideoRemuxer"]


def test_mp4_without_quality_caps_at_1080p():
    assert format_opts(Format.mp4, None)["format"] == "bestvideo[height<=1080]+bestaudio/best"
