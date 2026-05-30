"""Contract tests for POST /resolve (US1) — shapes + error codes vs extraction-service.md."""

import pytest


async def test_resolve_video_shape(client):
    r = await client.post("/resolve", json={"url": "https://www.youtube.com/watch?v=abc123"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "video"
    item = body["item"]
    assert set(item) >= {"id", "title", "author", "thumbnailUrl", "durationSeconds", "audioAvailable", "qualities"}
    assert item["audioAvailable"] is True
    assert all(q["heightPx"] <= 1080 for q in item["qualities"])
    assert all(q["container"] == "mp4" for q in item["qualities"])


async def test_resolve_playlist_shape(client):
    r = await client.post("/resolve", json={"url": "https://www.youtube.com/playlist?list=PL123"})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "playlist"
    pl = body["playlist"]
    assert pl["count"] == len(pl["items"]) == 3
    assert [i["id"] for i in pl["items"]] == ["vid1", "failitem", "vid3"]


@pytest.mark.parametrize(
    "url,status,code",
    [
        ("https://youtube.com/invalid", 400, "invalid_url"),
        ("https://youtube.com/watch?v=unavailable", 404, "unavailable"),
        ("https://youtube.com/watch?v=live", 422, "live_unsupported"),
        ("https://youtube.com/watch?v=drm", 422, "drm_protected"),
    ],
)
async def test_resolve_error_codes(client, url, status, code):
    r = await client.post("/resolve", json={"url": url})
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    assert r.json()["error"]["message"]  # user-safe message present
