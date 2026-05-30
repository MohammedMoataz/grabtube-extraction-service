"""MP3 metadata embedding via mutagen (FR-008, SC-003)."""

from mutagen.id3 import ID3

from grabtube_extractor.services.metadata import embed_mp3_metadata
from tests.fakes.fake_backend import TINY_JPEG, TINY_MP3


def test_embeds_all_fields(tmp_path):
    p = tmp_path / "song.mp3"
    p.write_bytes(TINY_MP3)
    embed_mp3_metadata(
        p, title="My Song", artist="Some Artist", cover_bytes=TINY_JPEG, album="Album", year="2026"
    )
    tags = ID3(str(p))
    assert tags["TIT2"].text[0] == "My Song"
    assert tags["TPE1"].text[0] == "Some Artist"
    assert tags["TALB"].text[0] == "Album"
    assert str(tags["TDRC"].text[0]) == "2026"
    assert tags.getall("APIC")


def test_missing_fields_are_omitted_without_failing(tmp_path):
    p = tmp_path / "song.mp3"
    p.write_bytes(TINY_MP3)
    # Only a title; no artist/cover — must not raise.
    embed_mp3_metadata(p, title="Only Title")
    tags = ID3(str(p))
    assert tags["TIT2"].text[0] == "Only Title"
    assert not tags.getall("TPE1")
    assert not tags.getall("APIC")
