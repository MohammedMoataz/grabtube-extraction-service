"""End-to-end MP4 job: create -> poll -> download (US2)."""

from tests.conftest import poll_until_finished


async def test_mp4_create_poll_download(client):
    create = await client.post(
        "/jobs", json={"source": "video", "id": "abc123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]
    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"

    dl = await client.get(f"/jobs/{job_id}/file")
    assert dl.status_code == 200
    assert dl.content.startswith(b"\x00\x00\x00\x18ftyp")  # the fake MP4 bytes
