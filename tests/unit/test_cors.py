"""Configurable CORS allow-list (FR-014)."""

import httpx
import pytest

from grabtube_extractor.main import create_app
from tests.conftest import make_settings
from tests.fakes.fake_backend import FakeBackend


@pytest.fixture
def cors_app(tmp_path):
    settings = make_settings(tmp_path, cors_origins=["https://allowed.example"])
    return create_app(settings=settings, backend=FakeBackend())


async def test_listed_origin_is_granted(cors_app):
    transport = httpx.ASGITransport(app=cors_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/resolve",
            json={"url": "https://youtube.com/watch?v=abc"},
            headers={"Origin": "https://allowed.example"},
        )
    assert r.headers.get("access-control-allow-origin") == "https://allowed.example"


async def test_unlisted_origin_is_not_granted(cors_app):
    transport = httpx.ASGITransport(app=cors_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post(
            "/resolve",
            json={"url": "https://youtube.com/watch?v=abc"},
            headers={"Origin": "https://evil.example"},
        )
    assert "access-control-allow-origin" not in r.headers
