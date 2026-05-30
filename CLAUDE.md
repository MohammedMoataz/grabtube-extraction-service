# GrabTube Extraction Service — Agent Context

Self-hosted backend behind the static GrabTube front-end. Resolves YouTube links and runs async jobs
to produce MP4 / MP3 / playlist-ZIP, streamed back over an HTTP contract the front-end depends on.

## Governance & workflow

- Spec-driven (GitHub Spec Kit): spec → clarify → plan → tasks → implement.
- Constitution: `.specify/memory/constitution.md` (Contract-First, Stateless/Transient, Reliability,
  Security/Abuse-Resistance, Observability, Test Discipline). The constitution wins on conflict.

## Active feature

<!-- SPECKIT START -->
**001-extraction-service** — Backend Extraction Service
- Plan: `specs/001-extraction-service/plan.md`
- Spec: `specs/001-extraction-service/spec.md`
- Contract (authoritative): `specs/001-extraction-service/contracts/extraction-service.md`
- Research: `specs/001-extraction-service/research.md`
- Data model: `specs/001-extraction-service/data-model.md`
- Quickstart: `specs/001-extraction-service/quickstart.md`
<!-- SPECKIT END -->

## Stack (agreed)

- **Python 3.12 + FastAPI** (Uvicorn).
- **yt-dlp** as a library (resolve / format-selection / progress hooks); **ffmpeg** as a subprocess
  (transcode/mux); **mutagen** for MP3 metadata + cover art.
- **In-process async job manager** + bounded worker pool (global semaphore, default 4); in-memory job
  registry; results on a local temp dir; background sweeper enforces **30-min** retention.
- Per-IP rate limiting; configurable CORS allow-list (deny by default).
- Packaged as a **single Docker image** (Python + yt-dlp + ffmpeg), env-var configured.
- Tests: **pytest + httpx**, yt-dlp/ffmpeg faked; single `pytest` command (contract + integration + unit).

## Key constraints

- Hard 1080p cap on returned/produced video (0 violations).
- No DRM circumvention; no client-embedded secret; all client traffic over HTTPS.
- Single-instance, no external store/broker (per clarifications).
- Must not break the published HTTP contract.
