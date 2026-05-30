"""FastAPI app factory.

The extraction ``backend`` is injectable so tests can substitute a deterministic fake; in
production it defaults to the yt-dlp + ffmpeg backend.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import routes_health, routes_jobs, routes_resolve
from .config import Settings, load_settings
from .errors import ServiceError, service_error_handler, unhandled_error_handler
from .middleware.cors import add_cors
from .middleware.rate_limit import RateLimiter
from .observability import Metrics, configure_logging
from .services.backend import ExtractionBackend
from .services.job_manager import JobManager
from .services.reaper import Reaper
from .services.resolver import Resolver


def create_app(settings: Settings | None = None, backend: ExtractionBackend | None = None) -> FastAPI:
    configure_logging()
    settings = settings or load_settings()

    if backend is None:
        from .services.ytdlp_backend import YtDlpBackend

        backend = YtDlpBackend(settings)

    metrics = Metrics()
    resolver = Resolver(backend)
    job_manager = JobManager(settings, backend, metrics, resolver)
    reaper = Reaper(job_manager)
    rate_limiter = RateLimiter(
        {"resolve": settings.rate_resolve_per_min, "jobs": settings.rate_jobs_per_min}
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        reaper.cleanup_orphans()
        reaper.start()
        try:
            yield
        finally:
            await reaper.stop()
            await job_manager.shutdown()

    app = FastAPI(title="GrabTube Extraction Service", version="0.1.0", lifespan=lifespan)

    app.state.settings = settings
    app.state.backend = backend
    app.state.metrics = metrics
    app.state.resolver = resolver
    app.state.job_manager = job_manager
    app.state.reaper = reaper
    app.state.rate_limiter = rate_limiter

    add_cors(app, settings.cors_origins)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(routes_health.router)
    app.include_router(routes_resolve.router)
    app.include_router(routes_jobs.router)
    return app


# Module-level app for `uvicorn grabtube_extractor.main:app`.
app = create_app()
