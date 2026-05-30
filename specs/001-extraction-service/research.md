# Phase 0 Research: Backend Extraction Service

**Date**: 2026-05-30 | **Feature**: `001-extraction-service`

The tech stack was agreed with the stakeholder, so there are no open `NEEDS CLARIFICATION` items.
This document records each decision, its rationale, and the alternatives considered, plus the
specific best-practice patterns the implementation will follow.

---

## 1. Language & web framework — Python 3.12 + FastAPI

- **Decision**: Build the service in Python 3.12 on FastAPI (Uvicorn ASGI server).
- **Rationale**: yt-dlp is a native Python library, eliminating fragile CLI-output parsing and giving
  direct access to format dictionaries and download progress hooks. FastAPI provides async request
  handling (keeps resolve/poll responsive while conversions run), first-class `StreamingResponse` /
  `FileResponse` for delivering MP4/MP3/ZIP, and auto-generated OpenAPI to validate against the
  published contract.
- **Alternatives considered**:
  - *Node.js + TypeScript (Fastify)* — shares a language with the front-end but must shell out to the
    yt-dlp CLI and parse JSON; weaker metadata-embedding story. Rejected: more glue, less control.
  - *Go (Echo/net-http)* — excellent streaming and a single binary, but shells out to yt-dlp and has
    weaker MP3-tagging libraries. Rejected: more manual work for the metadata-embedding requirement.

## 2. Extraction & conversion — yt-dlp (library) + ffmpeg (subprocess) + mutagen

- **Decision**: Import yt-dlp as a library for resolve, format selection, and per-item progress;
  invoke ffmpeg as a subprocess for transcode/mux; embed MP3 tags + cover art via mutagen.
- **Rationale**: The library gives structured metadata and a `progress_hooks` callback for real
  per-item progress (needed for FR-011 overall + per-item progress). Driving ffmpeg directly (rather
  than via yt-dlp postprocessors) gives precise control over the MP4 container/quality and the MP3
  output, and lets us attach our own timeouts. mutagen writes ID3 frames (TIT2 title, TPE1 artist,
  APIC cover) and tolerates missing fields (FR-008).
- **Best practices**:
  - Use `YoutubeDL` with `quiet`, `noplaylist` toggling, and `extract_flat` for fast playlist
    enumeration; only do full extraction per item at job time.
  - Cap qualities by filtering formats to `vcodec != none`, `ext == mp4`/compatible, `height <= 1080`
    (SC-004, hard 0-violation requirement).
  - Run all blocking yt-dlp/ffmpeg work in an executor (see §3); never block the event loop.
  - Wrap ffmpeg in `asyncio.create_subprocess_exec` with a timeout; kill the process tree on
    cancel/timeout.
- **Alternatives considered**: yt-dlp CLI subprocess (brittle stdout parsing); yt-dlp built-in ffmpeg
  postprocessors (less progress granularity and output control). Rejected for control reasons.

## 3. Job execution & concurrency — in-process async manager + bounded pool

- **Decision**: An in-memory job registry plus an async job manager that admits work through a global
  `asyncio.Semaphore` (default 4, from FR-020). Blocking work runs in a thread/process executor;
  excess jobs wait in `queued`. Playlist items are processed **sequentially** within their own job, so
  one large playlist consumes a single pool slot rather than starving others.
- **Rationale**: Matches the clarified single-instance / no-external-store model. The semaphore is the
  primary backpressure mechanism (SC-009). Sequential per-item processing keeps per-job memory/disk
  bounded and makes per-item progress + partial-failure reporting (FR-010) straightforward.
- **Best practices**:
  - Model job state as an enum (`queued → running → completed | failed | canceled`) with an
    `asyncio.Event`/cancel token checked between items and before each ffmpeg spawn (SC-006: stop
    within 10 s).
  - On cancel/timeout, terminate the child process group and delete partial artifacts.
  - Track `queue depth` and expose it as a metric (Constitution V).
  - Bound per-request input (reject absurd inputs early) and apply per-op timeouts (Constitution III).
- **Alternatives considered**: Celery/RQ + Redis (adds an external broker — contradicts single-instance
  clarification); raw threads with no pool (no backpressure, harder cancellation). Both rejected.

## 4. Transient storage & retention — local temp dir + background sweeper

- **Decision**: Write artifacts to a configurable local temp directory keyed by `jobId`; a background
  asyncio sweeper deletes any artifact ≥30 minutes past completion and cleans up canceled/failed jobs
  and orphaned temp files on startup.
- **Rationale**: Satisfies FR-017 / SC-008 (30-min retention, 100% cleanup) without external storage.
  Startup cleanup prevents accumulation across restarts.
- **Best practices**: Stream downloads with `FileResponse`; never load whole files into memory;
  ZIP playlists with the stdlib `zipfile` written to disk (streamed on download). Clean up on client
  disconnect to avoid leaks (spec edge case).
- **Alternatives considered**: In-memory artifacts (won't hold large playlist ZIPs); object storage
  (external dependency, out of scope). Rejected.

## 5. CORS & rate limiting — configurable allow-list + per-IP limiter

- **Decision**: CORS via an explicit, env-configured allow-list (deny non-listed origins). Per-IP rate
  limiting (slowapi or equivalent in-memory limiter): ~10 job creations/min, ~30 resolves/min, polling
  effectively unthrottled; over-limit → HTTP 429 with the contract error JSON.
- **Rationale**: FR-014/FR-015 and Constitution IV. In-memory limiter is consistent with the
  single-instance model (no shared store needed).
- **Best practices**: Resolve client IP from the reverse-proxy `X-Forwarded-For` (operator-trusted);
  make all thresholds env-configurable; return `Retry-After` on 429.
- **Alternatives considered**: Global limit (one heavy client starves others); wildcard CORS (rejected
  by Principle IV).

## 6. Packaging & deployment — single Docker image

- **Decision**: One Docker image based on a slim Python 3.12 image with ffmpeg installed and yt-dlp
  pinned; the app reads all configuration from environment variables (CORS origins, pool size, rate
  limits, retention window, timeouts, port, optional proxy/cookies). HTTPS is terminated by an
  external reverse proxy.
- **Rationale**: Reproducible, self-hosted-friendly, pins the ffmpeg/yt-dlp versions the service was
  tested against (Constitution: upstream maintenance is explicit). Env-only config satisfies the
  "configuration over secrets-in-code" constraint.
- **Best practices**: Pin yt-dlp and ffmpeg versions but document the routine update step (upstream
  changes are expected). Run as a non-root user; expose `/health` for readiness.
- **Alternatives considered**: docker-compose (nice for dev — may add later, not required); bare
  process (unmanaged ffmpeg/yt-dlp host dependency). Rejected as the primary artifact.

## 7. Testing strategy — pytest + httpx, faked upstreams

- **Decision**: pytest with httpx ASGI transport. Contract tests assert each endpoint's request/
  response shape and error codes against `contracts/extraction-service.md`. Integration tests cover
  every core flow (resolve video/playlist, MP4, MP3+metadata, playlist ZIP, cancel, error paths).
  yt-dlp and ffmpeg are replaced by deterministic fakes so no test depends on live upstream.
- **Rationale**: Constitution VI mandates contract + core-flow coverage, determinism, and a single
  documented command. Faking upstream is the only way to keep CI deterministic.
- **Best practices**: Fakes emit canned metadata/formats and write tiny valid MP4/MP3/ZIP fixtures;
  a 1080p-cap test asserts 0 violations; an MP3 test reads back ID3 frames to confirm embedding.
- **Alternatives considered**: Hitting live YouTube (non-deterministic, rate-limited, flaky). Rejected.

---

## Resolved unknowns

All Technical Context items are concrete; no `NEEDS CLARIFICATION` remains. Operational specifics
(exact proxy/cookie setup, reverse-proxy choice, host sizing) are deployment-time concerns and are
exposed as configuration rather than pinned here.
