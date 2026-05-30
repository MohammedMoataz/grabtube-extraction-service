"""End-to-end cancellation halts processing (US5, SC-006)."""

import time

from tests.conftest import poll_until_finished


async def test_cancel_halts_processing(blocking_client, blocking_backend):
    create = await blocking_client.post(
        "/jobs", json={"source": "playlist", "id": "PL123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]

    # Let the first item start, then cancel.
    await blocking_client.post(f"/jobs/{job_id}/cancel")

    start = time.monotonic()
    final = await poll_until_finished(blocking_client, job_id, timeout=10.0)
    assert final["status"] == "canceled"
    assert time.monotonic() - start < 10.0  # SC-006: stops well within the bound

    # Not all items were produced (processing stopped early).
    assert len(blocking_backend.produced_ids) < 3
