"""Contract test for cancel (US5)."""

from tests.conftest import poll_until_finished


async def test_cancel_returns_canceled_and_poll_reflects_it(blocking_client, blocking_backend):
    create = await blocking_client.post(
        "/jobs", json={"source": "playlist", "id": "PL123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]

    cancel = await blocking_client.post(f"/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json() == {"jobId": job_id, "status": "canceled"}

    final = await poll_until_finished(blocking_client, job_id)
    assert final["status"] == "canceled"
