# GrabTube Extraction Service

The **backend extraction service** behind the [GrabTube](https://github.com/MohammedMoataz/youtube-downloader)
static front-end. A self-hosted HTTP service that resolves YouTube video/playlist links, extracts
and converts media (MP4 up to 1080p, MP3 with embedded metadata), packages playlists into a single
ZIP, and streams the results back — exposing the contract the front-end already depends on.

> This is a **separate project** from the static website. The website is static-only (no backend);
> this service is the backend it calls. They evolve independently against a shared HTTP contract.

## Status

Spec-driven (GitHub Spec Kit). Current phase: **specification complete** →
[`specs/001-extraction-service/spec.md`](specs/001-extraction-service/spec.md).

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

1. `/speckit-clarify` — confirm assumptions (retention window, concurrency caps, allowed origins).
2. `/speckit-plan` — choose the stack (e.g., yt-dlp + ffmpeg + an HTTP layer) and design.
3. `/speckit-tasks` → `/speckit-implement`.

The technology choices intentionally live in the **plan** phase, not the spec.
