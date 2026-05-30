"""End-to-end resolve for video and playlist (US1)."""


async def test_resolve_video_end_to_end(client):
    r = await client.post("/resolve", json={"url": "https://www.youtube.com/watch?v=abc123"})
    item = r.json()["item"]
    assert item["title"] == "Example Video"
    assert item["durationSeconds"] == 372
    # 1440p excluded; 1080p + 720p kept, highest first.
    assert [q["heightPx"] for q in item["qualities"]] == [1080, 720]


async def test_resolve_playlist_end_to_end(client):
    r = await client.post("/resolve", json={"url": "https://www.youtube.com/playlist?list=PL123"})
    pl = r.json()["playlist"]
    assert pl["title"] == "My Playlist"
    assert pl["count"] == 3
