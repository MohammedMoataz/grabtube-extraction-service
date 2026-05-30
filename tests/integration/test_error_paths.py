"""Every defined failure case returns a stable code + user-safe message (SC-007, FR-016/FR-018)."""

import pytest


@pytest.mark.parametrize(
    "url,status,code",
    [
        ("https://youtube.com/invalid", 400, "invalid_url"),
        ("https://youtube.com/watch?v=unavailable", 404, "unavailable"),
        ("https://youtube.com/watch?v=live", 422, "live_unsupported"),
        ("https://youtube.com/watch?v=drm", 422, "drm_protected"),  # FR-018: reported, not circumvented
        ("https://youtube.com/watch?v=noformats", 422, "no_formats"),
    ],
)
async def test_resolve_failure_codes(client, url, status, code):
    r = await client.post("/resolve", json={"url": url})
    assert r.status_code == status
    err = r.json()["error"]
    assert err["code"] == code
    assert isinstance(err["message"], str) and err["message"]


async def test_unknown_job_is_not_found(client):
    r = await client.get("/jobs/job_does_not_exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_download_before_ready_is_not_found(blocking_client):
    create = await blocking_client.post(
        "/jobs", json={"source": "video", "id": "abc123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]
    # Job is still running (blocked); result not ready.
    r = await blocking_client.get(f"/jobs/{job_id}/file")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
