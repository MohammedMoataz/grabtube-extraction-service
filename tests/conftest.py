"""Shared fixtures: a fake-backed app and an httpx ASGI client.

The app's state (settings, job manager, resolver, rate limiter) is wired in ``create_app``,
so tests don't need to run the ASGI lifespan. The background reaper is exercised separately
in its own unit test, so it's intentionally not started here.
"""

from __future__ import annotations

import httpx
import pytest

from grabtube_extractor.config import Settings
from grabtube_extractor.main import create_app

from .fakes.fake_backend import FakeBackend


def make_settings(tmp_path, **overrides) -> Settings:
    base = dict(
        cors_origins=["https://grabtube.example"],
        max_concurrency=4,
        rate_jobs_per_min=1000,
        rate_resolve_per_min=1000,
        retention_minutes=30,
        resolve_timeout_s=30,
        job_timeout_s=60,
        tmp_dir=str(tmp_path),
        port=8080,
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings, backend):
    return create_app(settings=settings, backend=backend)


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def blocking_backend() -> FakeBackend:
    """A backend whose produce() blocks until released or canceled."""
    return FakeBackend(block=True)


@pytest.fixture
async def blocking_client(settings, blocking_backend):
    """Client whose jobs block in produce(); request ``blocking_backend`` too to control it."""
    app = create_app(settings=settings, backend=blocking_backend)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def poll_until_finished(client, job_id, timeout=5.0):
    """Poll GET /jobs/{id} until a terminal state; return the final JSON body."""
    import asyncio
    import time

    data = {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(f"/jobs/{job_id}")
        data = resp.json()
        if data.get("status") in ("completed", "failed", "canceled"):
            return data
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s: {data}")
