# Tasks: Backend Extraction Service

**Feature**: `001-extraction-service` | **Date**: 2026-05-30
**Inputs**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md), [research.md](./research.md), [contracts/extraction-service.md](./contracts/extraction-service.md), [quickstart.md](./quickstart.md)

Tests are **included** — Constitution VI mandates contract tests + core-flow coverage with faked
upstreams. Package root: `src/grabtube_extractor/`. Single test command: `pytest`.

---

## Phase 1: Setup

- [x] T001 Create project skeleton: `pyproject.toml` (Python 3.12, deps: fastapi, uvicorn[standard], yt-dlp, mutagen, slowapi, pydantic, pytest, httpx), package dir `src/grabtube_extractor/`, and `tests/` with `contract/`, `integration/`, `unit/`, `fakes/` subdirs
- [x] T002 [P] Add `.env.example` documenting all env vars from quickstart.md (`GT_CORS_ORIGINS`, `GT_MAX_CONCURRENCY`, `GT_RATE_JOBS_PER_MIN`, `GT_RATE_RESOLVE_PER_MIN`, `GT_RETENTION_MINUTES`, `GT_RESOLVE_TIMEOUT_S`, `GT_JOB_TIMEOUT_S`, `GT_TMP_DIR`, `GT_PORT`, `GT_PROXY_URL`, `GT_COOKIES_FILE`)
- [x] T003 [P] Configure pytest in `pyproject.toml` (testpaths, asyncio mode) and add `tests/conftest.py` with an httpx ASGI client fixture and an app factory fixture
- [x] T004 [P] Add `.gitignore` entries for `__pycache__`, `*.egg-info`, `.pytest_cache`, local temp dirs

## Phase 2: Foundational (blocking prerequisites)

- [x] T005 Implement `src/grabtube_extractor/config.py`: a pydantic-settings `Settings` reading all env vars (defaults from quickstart.md), including parsing `GT_CORS_ORIGINS` into a list
- [x] T006 [P] Implement `src/grabtube_extractor/models/domain.py`: enums (`LinkKind`, `Format`, `JobStatus`, `ItemStatus`, `ResultKind`, `ErrorCode`) and dataclasses (`QualityOption`, `MediaItem`, `Playlist`, `Job`, `JobItem`, `ResultArtifact`) per data-model.md
- [x] T007 [P] Implement `src/grabtube_extractor/models/schemas.py`: pydantic request/response models matching the wire shapes in contracts/extraction-service.md (ResolveRequest, video/playlist responses, CreateJobRequest, JobStatusResponse, ErrorResponse)
- [x] T008 [P] Implement `src/grabtube_extractor/errors.py`: `ServiceError(code, message)` exception, the `ErrorCode → HTTP status` map from data-model.md, and a FastAPI exception handler emitting `{ "error": { "code", "message" } }`
- [x] T009 [P] Implement `src/grabtube_extractor/observability.py`: structured JSON logging setup + simple in-memory metrics (job counts, durations, failure rates, queue depth)
- [x] T010 Implement `src/grabtube_extractor/main.py`: FastAPI app factory wiring config, exception handlers, middleware placeholders, routers, and a lifespan that starts/stops the reaper
- [x] T011 [P] Implement `src/grabtube_extractor/api/routes_health.py`: `GET /health` readiness endpoint
- [x] T012 [P] Build deterministic fakes in `tests/fakes/`: a fake yt-dlp (canned metadata/formats incl. >1080p entries to prove filtering; playlist enumeration; a deliberately-failing item) and a fake ffmpeg + tiny valid MP4/MP3/ZIP fixtures
- [x] T013 Implement `src/grabtube_extractor/services/job_manager.py`: in-memory registry, `asyncio.Queue` + global `Semaphore` (size = `GT_MAX_CONCURRENCY`), job lifecycle (`queued→running→completed/failed/canceled`), per-item progress, cancel token, runs blocking work in an executor

**Checkpoint**: app boots, `/health` returns OK, config + models + error mapping + job manager skeleton exist.

## Phase 3: User Story 1 — Resolve a link (P1) 🎯 MVP

**Goal**: Client submits a video/playlist link → metadata + MP4 qualities (≤1080p) + audio availability.
**Independent test**: `POST /resolve` with a video link returns title/author/thumbnail/duration/`audioAvailable` + qualities all ≤1080p; a playlist link returns title/count/ordered items.

- [x] T014 [P] [US1] Contract test `tests/contract/test_resolve.py`: video + playlist happy paths and error codes (400 invalid, 404 unavailable, 422 live, 429) match the contract
- [x] T015 [P] [US1] Unit test `tests/unit/test_quality_filter.py`: formats >1080p are excluded (0 violations, SC-004)
- [x] T016 [US1] Implement `src/grabtube_extractor/services/resolver.py`: classify link (video/playlist/invalid), extract metadata via fake/real yt-dlp, filter qualities to mp4 ≤1080p, detect audio availability, map upstream failures to `ServiceError`s
- [x] T017 [US1] Implement `src/grabtube_extractor/api/routes_resolve.py`: `POST /resolve` returning the video/playlist response shapes; apply resolve timeout (`GT_RESOLVE_TIMEOUT_S`)
- [x] T018 [US1] Integration test `tests/integration/test_resolve_flow.py`: end-to-end resolve for video + playlist via httpx client

**Checkpoint**: `/resolve` fully working and tested independently.

## Phase 4: User Story 2 — Single video MP4 (P1) 🎯 MVP

**Goal**: Create an MP4 job at a chosen quality, poll progress, download a playable MP4.
**Independent test**: create MP4 job → poll to completed → fetch streams `video/mp4` with a filename; mp4 without `qualityId` → 400.

- [x] T019 [P] [US2] Contract test `tests/contract/test_jobs_mp4.py`: `POST /jobs` (202 `{jobId,status:queued}`), `GET /jobs/{id}` transitions, `GET /jobs/{id}/file` headers; mp4 without `qualityId` → 400 `quality_required`
- [x] T020 [US2] Implement `src/grabtube_extractor/services/extractor.py`: per-item production — yt-dlp download at selected `qualityId` + ffmpeg subprocess transcode/mux to MP4, with per-op timeout and progress callback into the job
- [x] T021 [US2] Implement job-creation + polling in `src/grabtube_extractor/api/routes_jobs.py`: `POST /jobs` (validate mp4 requires `qualityId`), `GET /jobs/{id}` status with `overallProgress`/`resultKind`/`resultUrl`
- [x] T022 [US2] Implement result download `GET /jobs/{id}/file` (streamed `FileResponse`, `Content-Type` + `Content-Disposition`), wiring the `ResultArtifact` produced by the job
- [x] T023 [US2] Integration test `tests/integration/test_mp4_flow.py`: create → poll → download a playable MP4 (faked) end-to-end

**Checkpoint**: MVP complete — resolve + single MP4 download work end-to-end.

## Phase 5: User Story 3 — MP3 with embedded metadata (P2)

**Goal**: Create an MP3 job; output carries title/author/cover art + extra fields when present.
**Independent test**: MP3 job (no `qualityId`) → downloaded MP3 has correct ID3 title/author/cover read back.

- [x] T024 [P] [US3] Contract test `tests/contract/test_jobs_mp3.py`: mp3 job omits `qualityId`; result is `audio/mpeg`
- [x] T025 [P] [US3] Unit test `tests/unit/test_metadata.py`: mutagen embeds title/author/cover; missing fields omitted without failure (FR-008); read-back verifies tags (SC-003)
- [x] T026 [US3] Implement `src/grabtube_extractor/services/metadata.py`: mutagen ID3 embedding (TIT2/TPE1/APIC + optional album/year) from MediaItem, tolerant of missing fields
- [x] T027 [US3] Extend `extractor.py` for the mp3 path (audio extract + ffmpeg to MP3 + metadata embed); ensure `POST /jobs` accepts mp3 without `qualityId`
- [x] T028 [US3] Integration test `tests/integration/test_mp3_flow.py`: create mp3 job → download → assert embedded metadata

**Checkpoint**: audio extraction with metadata works.

## Phase 6: User Story 4 — Playlist into a single ZIP (P3)

**Goal**: Process every playlist item (no cap) sequentially within the job → one ZIP; partial-failure tolerant.
**Independent test**: playlist job → per-item + overall progress → single ZIP with one file per successful item; a failing item is reported failed while others complete.

- [x] T029 [P] [US4] Contract test `tests/contract/test_jobs_playlist.py`: playlist job → `resultKind:"zip"`, `items[]` with per-item status incl. a `failed` item that doesn't stop completion
- [x] T030 [US4] Implement `src/grabtube_extractor/services/packager.py`: build a single ZIP (stdlib `zipfile`) from successful per-item artifacts
- [x] T031 [US4] Extend `job_manager.py` for playlist jobs: sequential per-item processing, per-item status/progress, continue past item failures (partial success, FR-010), overall progress aggregation
- [x] T032 [US4] Integration test `tests/integration/test_playlist_flow.py`: playlist with one deliberately-failing item → ZIP of the rest, failed item reported (SC-005)

**Checkpoint**: playlist ZIP with partial-failure tolerance works.

## Phase 7: User Story 5 — Cancel an in-progress job (P3)

**Goal**: Cancel a running job; processing stops within 10s and status reflects cancellation.
**Independent test**: start a playlist job → cancel → status `canceled`, processing halts (SC-006).

- [x] T033 [P] [US5] Contract test `tests/contract/test_jobs_cancel.py`: `POST /jobs/{id}/cancel` → `{jobId,status:"canceled"}`; subsequent poll shows canceled
- [x] T034 [US5] Implement `POST /jobs/{id}/cancel` in `routes_jobs.py` + cancel-token honoring in `job_manager.py`/`extractor.py` (check between items and before each ffmpeg spawn; terminate child process on cancel)
- [x] T035 [US5] Integration test `tests/integration/test_cancel_flow.py`: cancellation halts processing within the bound and reports canceled

**Checkpoint**: all five user stories complete and independently tested.

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T036 [P] Implement `src/grabtube_extractor/middleware/cors.py`: configurable allow-list CORS (deny non-listed origins, FR-014); unit test in `tests/unit/test_cors.py`
- [x] T037 [P] Implement `src/grabtube_extractor/middleware/rate_limit.py`: per-IP limiter (jobs ~10/min, resolve ~30/min, polling unthrottled) → 429 with `Retry-After` and contract error JSON; unit test in `tests/unit/test_rate_limit.py`
- [x] T038 [P] Implement `src/grabtube_extractor/services/reaper.py`: background sweeper deleting artifacts ≥`GT_RETENTION_MINUTES` after completion + startup orphan cleanup + client-disconnect cleanup; unit test `tests/unit/test_reaper.py` (SC-008)
- [x] T039 [P] Unit test `tests/unit/test_concurrency_pool.py`: jobs beyond the pool wait in `queued`; pool never exceeds `GT_MAX_CONCURRENCY` (FR-020/SC-009)
- [x] T040 [P] Add timeouts + graceful degradation assertions: resolve/job timeouts return `timeout` error; integration test `tests/integration/test_error_paths.py` covers each error code (SC-007)
- [x] T041 Write the `Dockerfile`: slim Python 3.12 base, install ffmpeg + pinned yt-dlp, non-root user, expose `GT_PORT`, run uvicorn; add `.dockerignore`
- [x] T042 [P] Update `README.md` run/test/deploy instructions to match the implemented service and `quickstart.md`
- [x] T043 Full-suite green-check: run `pytest` and confirm contract + integration + unit pass deterministically (no live upstream)

---

## Dependencies & execution order

- **Setup (T001–T004)** → **Foundational (T005–T013)** block everything.
- **US1 (T014–T018)** and **US2 (T019–T023)** are the P1 MVP; US2 depends on US1's resolver + job manager.
- **US3 (T024–T028)** builds on the extractor/job path; **US4 (T029–T032)** builds on single-item + job manager; **US5 (T033–T035)** builds on running jobs.
- **Polish (T036–T043)** after stories; T041/T043 (Docker + full suite) last.

## Parallel opportunities

- Setup: T002, T003, T004 in parallel.
- Foundational: T006, T007, T008, T009, T011, T012 in parallel (after T005); T010/T013 after.
- Within each story, the `[P]` contract/unit tests run in parallel before the implementation tasks.
- Polish: T036, T037, T038, T039, T040, T042 in parallel; then T041, T043.

## Independent test criteria (per story)

| Story | Independently verifiable when… |
|-------|--------------------------------|
| US1 | `/resolve` returns correct shapes for video + playlist; qualities ≤1080p |
| US2 | MP4 job create→poll→download yields a playable MP4; mp4 w/o quality → 400 |
| US3 | MP3 download carries correct embedded title/author/cover |
| US4 | Playlist → single ZIP; failed item reported, others complete |
| US5 | Cancel halts processing <10s; status `canceled` |

## Suggested MVP scope

**US1 + US2** (Phases 1–4): resolve + single-video MP4 download — the minimum that makes the
front-end's core flow work. US3 (MP3), US4 (playlist ZIP), US5 (cancel) layer on incrementally.

**Total tasks**: 43 (Setup 4, Foundational 9, US1 5, US2 5, US3 5, US4 4, US5 3, Polish 8).
