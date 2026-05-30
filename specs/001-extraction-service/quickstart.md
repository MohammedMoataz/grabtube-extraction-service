# Quickstart: Backend Extraction Service

**Date**: 2026-05-30 | **Feature**: `001-extraction-service`

How to run, configure, and test the service locally and in a container. This reflects the agreed
stack (Python 3.12 + FastAPI, yt-dlp library + ffmpeg subprocess + mutagen, in-process job manager,
single Docker image). Paths are the planned layout from `plan.md`.

---

## Prerequisites

- Python 3.12
- ffmpeg on `PATH` (for local dev; the Docker image bundles it)
- yt-dlp (installed as a Python dependency)

## Configuration (environment variables)

All tunables are env-only (Constitution: configuration over secrets-in-code).

| Variable | Default | Purpose |
|----------|---------|---------|
| `GT_CORS_ORIGINS` | (empty → deny) | Comma-separated allow-list of explicit origins (FR-014) |
| `GT_MAX_CONCURRENCY` | `4` | Global concurrent-conversion pool size (FR-020) |
| `GT_RATE_JOBS_PER_MIN` | `10` | Per-IP job-creation limit (FR-015) |
| `GT_RATE_RESOLVE_PER_MIN` | `30` | Per-IP resolve limit (FR-015) |
| `GT_RETENTION_MINUTES` | `30` | Result lifetime after completion (FR-017 / SC-008) |
| `GT_RESOLVE_TIMEOUT_S` | `30` | Resolve timeout (SC-001 budget) |
| `GT_JOB_TIMEOUT_S` | `1800` | Per-job processing timeout |
| `GT_TMP_DIR` | system temp | Where transient artifacts are written |
| `GT_PORT` | `8080` | Listen port |
| `GT_PROXY_URL` / `GT_COOKIES_FILE` | (unset) | Optional operator egress config (server-side only) |

Copy `.env.example` and adjust. **HTTPS is terminated by your reverse proxy**, which also sets
`X-Forwarded-For` for per-IP limiting.

## Run locally

```bash
pip install -e .            # or: pip install -r requirements.txt
export GT_CORS_ORIGINS="http://localhost:5173"   # your front-end origin
uvicorn grabtube_extractor.main:app --port 8080 --reload
```

`GET /health` should return readiness. Point the GrabTube front-end's `PUBLIC_DOWNLOADER_API` at
`http://localhost:8080`.

## Run with Docker

```bash
docker build -t grabtube-extractor .
docker run --rm -p 8080:8080 \
  -e GT_CORS_ORIGINS="https://grabtube.example" \
  -e GT_MAX_CONCURRENCY=4 \
  grabtube-extractor
```

## Smoke-test the core flows

```bash
# 1) Resolve a video
curl -sX POST localhost:8080/resolve \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO"}'

# 2) Create an MP4 job (qualityId required for mp4)
curl -sX POST localhost:8080/jobs \
  -H 'Content-Type: application/json' \
  -d '{"source":"video","id":"VIDEO","format":"mp4","qualityId":"137"}'
# → { "jobId": "...", "status": "queued" }

# 3) Poll until completed
curl -s localhost:8080/jobs/JOB_ID

# 4) Download the result
curl -s -OJ localhost:8080/jobs/JOB_ID/file

# 5) Create an MP3 job (no qualityId) and confirm embedded tags
curl -sX POST localhost:8080/jobs -H 'Content-Type: application/json' \
  -d '{"source":"video","id":"VIDEO","format":"mp3"}'

# 6) Cancel a long playlist job
curl -sX POST localhost:8080/jobs/JOB_ID/cancel
```

## Run the tests

A single documented command (Constitution VI). Tests fake yt-dlp + ffmpeg — no live upstream needed.

```bash
pytest                      # contract + integration + unit
pytest tests/contract       # just the contract suite vs extraction-service.md
```

What the suites prove:
- **Contract**: every endpoint shape + error code matches `contracts/extraction-service.md`.
- **Integration**: resolve (video/playlist), MP4 job, MP3 + embedded metadata, playlist → single ZIP,
  partial-failure (one item fails, rest complete), cancel, and each error path.
- **Unit**: 1080p cap (0 violations), error-code mapping, MP3 tag read-back, retention sweeper,
  concurrency-pool backpressure.

## Acceptance checkpoints (map to Success Criteria)

| Check | Criterion |
|-------|-----------|
| Resolve returns metadata + formats < 5 s | SC-001 |
| Returned/produced video never > 1080p | SC-004 |
| MP3 carries correct title/author/cover | SC-003 |
| Playlist → one ZIP, failed items reported | SC-005 |
| Cancel halts processing < 10 s | SC-006 |
| Results gone ≤ 30 min after completion | SC-008 |
| Front-end works unmodified against the API | SC-010 |
