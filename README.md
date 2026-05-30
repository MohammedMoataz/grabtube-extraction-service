# GrabTube Extraction Service

The **backend extraction service** behind the [GrabTube](https://github.com/MohammedMoataz/youtube-downloader)
static front-end. A self-hosted HTTP service that resolves YouTube video/playlist links, extracts
and converts media (MP4 up to 1080p, MP3 with embedded metadata), packages playlists into a single
ZIP, and streams the results back — exposing the contract the front-end already depends on.

> This is a **separate project** from the static website. The website is static-only (no backend);
> this service is the backend it calls. They evolve independently against a shared HTTP contract.

## Status

Spec-driven (GitHub Spec Kit). Current phase: **implemented & tested** — the service is built
(Python 3.12 + FastAPI), the full `pytest` suite (contract + integration + unit) is green, and the
Docker image builds. See [`specs/001-extraction-service/`](specs/001-extraction-service/) for the
spec, plan, and tasks, and [`quickstart.md`](specs/001-extraction-service/quickstart.md) to run it.

```bash
pip install -e ".[dev]" && pytest          # run the test suite
uvicorn grabtube_extractor.main:app        # run locally (set GT_CORS_ORIGINS)
docker build -t grabtube-extractor .       # build the deployable image
```

| Artifact | Path |
|----------|------|
| Constitution | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Spec | [`specs/001-extraction-service/spec.md`](specs/001-extraction-service/spec.md) |
| HTTP contract | [`specs/001-extraction-service/contracts/extraction-service.md`](specs/001-extraction-service/contracts/extraction-service.md) |
| Quality checklist | [`specs/001-extraction-service/checklists/requirements.md`](specs/001-extraction-service/checklists/requirements.md) |

## What it does (from the spec)

- **Resolve** a video/playlist link → metadata + available MP4 qualities (≤1080p) + audio availability.
- **Jobs**: produce MP4 (chosen quality) or MP3 (with embedded title/author/cover art); playlists →
  one ZIP, no item cap, per-item + overall progress, partial-failure tolerant, cancelable.
- **Deliver**: stream the finished file/ZIP with correct content type + filename.
- **Safe by design**: CORS for the site origin, **no client-embedded secret**, rate limiting/abuse
  protection, transient storage (no content retention), no DRM circumvention.

## Next steps (SDD flow)

1. ✅ `/speckit-clarify` — assumptions confirmed (single-instance/local-disk state, 30-min retention,
   concurrency pool of 4, per-IP rate limits, configurable CORS allow-list). See the spec's
   `## Clarifications` section.
2. `/speckit-plan` — choose the stack (e.g., yt-dlp + ffmpeg + an HTTP layer) and design.
3. `/speckit-tasks` → `/speckit-implement`.

The technology choices intentionally live in the **plan** phase, not the spec.
