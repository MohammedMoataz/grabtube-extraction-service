# Implementation Plan: Backend Extraction Service

**Branch**: `main` (feature dir `001-extraction-service`) | **Date**: 2026-05-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-extraction-service/spec.md`

## Summary

A self-hosted, single-instance HTTP service that resolves YouTube video/playlist links into metadata
+ available MP4 qualities (≤1080p) and audio availability, then runs asynchronous jobs to produce a
playable MP4 (chosen quality), an MP3 with embedded metadata, or a single ZIP for a whole playlist —
streaming the result back to the static GrabTube front-end. It implements the already-published HTTP
contract (`contracts/extraction-service.md`) without breaking it.

**Technical approach**: A FastAPI application drives **yt-dlp as a Python library** (resolve, format
selection, progress hooks) and invokes **ffmpeg as a subprocess** for transcode/mux, with **mutagen**
embedding MP3 tags + cover art. Jobs run through an **in-process async job manager** backed by an
in-memory registry and a **bounded worker pool** (global semaphore, default 4 — FR-020); blocking
yt-dlp/ffmpeg work runs in an executor so the event loop stays responsive for resolve/poll. Results
land in a local-disk temp directory; a **background sweeper** enforces the 30-minute retention window
(FR-017). Cross-cutting middleware provides a **configurable CORS allow-list** (FR-014) and **per-IP
rate limiting** (FR-015). The whole thing ships as one **Docker image** bundling Python + yt-dlp +
ffmpeg, configured entirely via environment variables.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI (HTTP + streaming + OpenAPI), Uvicorn (ASGI server), yt-dlp
(extraction/format-selection as a library), ffmpeg (external binary, subprocess) for transcode/mux,
mutagen (MP3/ID3 tag + cover-art embedding), slowapi or an equivalent per-IP limiter for rate
limiting, pydantic v2 (request/response models matching the contract)

**Storage**: Local-disk temp directory for transient result artifacts (MP4/MP3/ZIP); in-memory job
registry. No database, no external broker, no shared store (single-instance clarification).

**Testing**: pytest + httpx (ASGI transport) for contract + integration tests; yt-dlp and ffmpeg are
faked/mocked so tests are deterministic and need no live upstream access (Constitution VI).

**Target Platform**: Linux container (Docker), self-hosted behind HTTPS-terminating reverse proxy.

**Project Type**: Single backend web service.

**Performance Goals**: Resolve returns within 5 s under normal conditions (SC-001); ≥95% of valid
single-video jobs succeed (SC-002); cancellation halts processing within 10 s (SC-006); service stays
responsive to resolve/poll under load and never exhausts the host (SC-009).

**Constraints**: Hard 1080p cap on returned/produced video (SC-004); MP3 metadata correctness (SC-003);
30-minute result retention then deletion (SC-008); global concurrency pool default 4 with excess
queued (FR-020); per-IP rate limits (~10 job creations/min, ~30 resolves/min, polling unthrottled —
FR-015); no DRM circumvention (FR-018); no client-embedded secret (FR-014); all client traffic over
HTTPS (Constitution: Transport security).

**Scale/Scope**: Single instance, vertical scaling. 5 endpoints (resolve, create job, poll, download,
cancel). No fixed playlist item cap; backpressure via the bounded pool and per-IP limits.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | How the plan complies | Status |
|---|-----------|------------------------|--------|
| I | Contract-First & Backward Compatibility | Pydantic models + routes are generated to match `contracts/extraction-service.md` exactly; contract tests assert every endpoint/shape/error code. No breaking changes. | ✅ PASS |
| II | Stateless & Transient (No Content Retention) | In-memory job registry; results on local temp disk; background sweeper deletes ≤30 min after completion; no accounts, no personal data, no content library. | ✅ PASS |
| III | Reliability & Graceful Degradation | Every external op (resolve, ffmpeg, transfer) has a timeout; bounded worker pool + per-request limits; playlist jobs tolerate per-item failure (partial success); client-disconnect cleanup. | ✅ PASS |
| IV | Security & Abuse Resistance | No client secret; configurable CORS allow-list (deny by default); per-IP rate limiting → 429; input validation; operator secrets (cookies/proxy) server-side only; no DRM circumvention. | ✅ PASS |
| V | Observability | Structured request/job/failure logs (no sensitive data); `/health` readiness; metrics: job counts, durations, failure rates, queue depth. Client errors carry stable code; detail stays in logs. | ✅ PASS |
| VI | Test Discipline | Contract tests for all 5 endpoints + error codes; core-flow integration tests (resolve, MP4, MP3+meta, playlist ZIP, cancel, error paths); yt-dlp/ffmpeg faked for determinism; single `pytest` command. | ✅ PASS |

**Operational & Compliance**: All tunables (CORS origins, rate limits, retention, pool size, proxy/
cookies, port) via env vars — never hardcoded. HTTPS terminated at the reverse proxy. No content
retained; no rights claimed.

**Gate result**: PASS — no violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-extraction-service/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── extraction-service.md   # Authoritative HTTP contract (pre-existing)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/
└── grabtube_extractor/
    ├── main.py                 # FastAPI app factory, middleware wiring, lifespan (sweeper start/stop)
    ├── config.py               # Env-var settings (CORS origins, pool size, rate limits, retention, timeouts, port, proxy/cookies)
    ├── api/
    │   ├── routes_resolve.py    # POST /resolve
    │   ├── routes_jobs.py       # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/file, POST /jobs/{id}/cancel
    │   └── routes_health.py     # GET /health
    ├── models/
    │   ├── schemas.py           # Pydantic request/response models (match contract)
    │   └── domain.py            # Internal entities: Job, JobItem, MediaItem, QualityOption, ResultArtifact, enums
    ├── services/
    │   ├── resolver.py          # yt-dlp library: classify link, extract metadata, filter qualities ≤1080p
    │   ├── extractor.py         # Per-item production: yt-dlp download + ffmpeg transcode/mux
    │   ├── metadata.py          # mutagen: embed title/author/cover art + extra fields into MP3
    │   ├── packager.py          # Build single ZIP for playlist results
    │   ├── job_manager.py       # In-memory registry, async queue, bounded pool (semaphore), cancellation, progress
    │   └── reaper.py            # Background sweeper: enforce 30-min retention, cleanup on disconnect/expiry
    ├── middleware/
    │   ├── cors.py              # Configurable allow-list CORS
    │   └── rate_limit.py        # Per-IP limiter → 429
    ├── errors.py               # Stable error codes → user-safe messages; exception→HTTP mapping
    └── observability.py        # Structured logging + metrics (counts, durations, failure rates, queue depth)

tests/
├── contract/                   # Assert each endpoint/shape/error code vs extraction-service.md
├── integration/                # Core flows: resolve, MP4, MP3+meta, playlist ZIP, cancel, error paths
├── unit/                       # quality filtering, error mapping, metadata embedding, sweeper, pool limits
└── fakes/                      # Fake yt-dlp + ffmpeg (deterministic, no live upstream)

Dockerfile                      # Python 3.12 + yt-dlp + ffmpeg, env-var configured
pyproject.toml                  # Deps + pytest config; single documented test command
.env.example                    # Documented configuration surface
```

**Structure Decision**: Single backend web service (the spec's project type). One Python package
`src/grabtube_extractor` with a thin API layer over a service layer; the job manager is the heart of
the async model. Tests split into contract / integration / unit per Constitution VI, with a `fakes/`
package so no test touches a live upstream.

## Complexity Tracking

> No constitution violations — section intentionally empty.
