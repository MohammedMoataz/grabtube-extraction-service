"""Contract tests for the MP3 job (US3) — no qualityId, audio/mpeg result."""

from tests.conftest import poll_until_finished


async def test_mp3_job_omits_quality_and_returns_audio(client):
    create = await client.post("/jobs", json={"source": "video", "id": "abc123", "format": "mp3"})
    assert create.status_code == 202
    job_id = create.json()["jobId"]

    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"
    assert final["resultKind"] == "file"

    dl = await client.get(f"/jobs/{job_id}/file")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "audio/mpeg"
    assert ".mp3" in dl.headers["content-disposition"]
