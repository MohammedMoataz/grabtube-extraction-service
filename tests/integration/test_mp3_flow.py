"""End-to-end MP3 job with embedded metadata read back from the downloaded file (US3, SC-003)."""

import io

from mutagen.id3 import ID3

from tests.conftest import poll_until_finished


async def test_mp3_download_has_embedded_metadata(client):
    create = await client.post("/jobs", json={"source": "video", "id": "abc123", "format": "mp3"})
    job_id = create.json()["jobId"]
    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"

    dl = await client.get(f"/jobs/{job_id}/file")
    assert dl.status_code == 200

    tags = ID3(io.BytesIO(dl.content))
    assert tags["TIT2"].text[0] == "Example Video"
    assert tags["TPE1"].text[0] == "Channel Name"
    assert tags.getall("APIC"), "cover art (APIC) should be embedded"
