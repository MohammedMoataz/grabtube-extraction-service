"""Per-IP rate limiting (FR-015)."""

import httpx
import pytest

from grabtube_extractor.main import create_app
from grabtube_extractor.middleware.rate_limit import RateLimiter
from grabtube_extractor.errors import ServiceError
from tests.conftest import make_settings
from tests.fakes.fake_backend import FakeBackend


def test_limiter_blocks_after_limit_with_retry_after():
    clock = {"t": 0.0}
    rl = RateLimiter({"jobs": 2}, clock=lambda: clock["t"])
    rl.check("1.1.1.1", "jobs")
    rl.check("1.1.1.1", "jobs")
    with pytest.raises(ServiceError) as exc:
        rl.check("1.1.1.1", "jobs")
    assert exc.value.code.value == "rate_limited"
    assert exc.value.retry_after is not None


def test_limiter_is_per_ip():
    rl = RateLimiter({"jobs": 1})
    rl.check("1.1.1.1", "jobs")
    rl.check("2.2.2.2", "jobs")  # different IP, fresh budget — no raise


async def test_resolve_returns_429_when_limited(tmp_path):
    settings = make_settings(tmp_path, rate_resolve_per_min=1)
    app = create_app(settings=settings, backend=FakeBackend())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        first = await c.post("/resolve", json={"url": "https://youtube.com/watch?v=abc"})
        assert first.status_code == 200
        second = await c.post("/resolve", json={"url": "https://youtube.com/watch?v=abc"})
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "rate_limited"
        assert "retry-after" in {k.lower() for k in second.headers}
