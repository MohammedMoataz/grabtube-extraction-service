"""Contract tests for the MP4 job lifecycle (US2)."""

from tests.conftest import poll_until_finished


async def test_create_mp4_job_returns_202_queued(client):
    r = await client.post("/jobs", json={"source": "video", "id": "abc123", "format": "mp4", "qualityId": "137"})
    assert r.status_code == 202
    body = r.json()
    assert body["jobId"]
    assert body["status"] == "queued"


async def test_mp4_job_completes_and_downloads(client):
    create = await client.post(
        "/jobs", json={"source": "video", "id": "abc123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]

    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"
    assert final["overallProgress"] == 100
    assert final["resultKind"] == "file"
    assert final["resultUrl"] == f"/jobs/{job_id}/file"

    dl = await client.get(f"/jobs/{job_id}/file")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "video/mp4"
    assert "attachment" in dl.headers["content-disposition"]
    assert ".mp4" in dl.headers["content-disposition"]
    assert dl.content  # bytes streamed


async def test_mp4_without_quality_is_rejected(client):
    r = await client.post("/jobs", json={"source": "video", "id": "abc123", "format": "mp4"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "quality_required"
