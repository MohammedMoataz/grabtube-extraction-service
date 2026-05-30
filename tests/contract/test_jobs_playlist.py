"""Contract tests for playlist jobs (US4) — single ZIP, per-item status, partial failure."""

from tests.conftest import poll_until_finished


async def test_playlist_job_yields_zip_with_partial_failure(client):
    create = await client.post(
        "/jobs", json={"source": "playlist", "id": "PL123", "format": "mp4", "qualityId": "137"}
    )
    assert create.status_code == 202
    job_id = create.json()["jobId"]

    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"
    assert final["resultKind"] == "zip"

    by_id = {i["itemId"]: i for i in final["items"]}
    assert by_id["failitem"]["status"] == "failed"
    assert by_id["vid1"]["status"] == "done"
    assert by_id["vid3"]["status"] == "done"

    dl = await client.get(f"/jobs/{job_id}/file")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    assert ".zip" in dl.headers["content-disposition"]
