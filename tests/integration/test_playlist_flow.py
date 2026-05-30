"""End-to-end playlist job → single ZIP, partial-failure tolerant (US4, SC-005)."""

import io
import zipfile

from tests.conftest import poll_until_finished


async def test_playlist_zip_contains_successful_items_only(client):
    create = await client.post(
        "/jobs", json={"source": "playlist", "id": "PL123", "format": "mp4", "qualityId": "137"}
    )
    job_id = create.json()["jobId"]
    final = await poll_until_finished(client, job_id)
    assert final["status"] == "completed"

    dl = await client.get(f"/jobs/{job_id}/file")
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    names = zf.namelist()
    # 2 of 3 items succeed (failitem fails); ZIP holds one file per success.
    assert len(names) == 2
    assert all(n.endswith(".mp4") for n in names)
