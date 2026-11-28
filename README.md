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
docker compose up --build                  # run for local front-end integration
```

## Front-end integration

CI (GitHub Actions) lints, runs the full test suite on Python 3.11/3.12, builds the image,
smoke-tests `/health` + CORS, and publishes the image to GHCR on `main`:

```bash
docker pull ghcr.io/mohammedmoataz/grabtube-extraction-service:latest
docker run -p 8080:8080 -e GT_CORS_ORIGINS="https://your-frontend.example" \
  ghcr.io/mohammedmoataz/grabtube-extraction-service:latest
```

Point the front-end's `PUBLIC_DOWNLOADER_API` at the service URL, and set `GT_CORS_ORIGINS`
to the front-end's exact origin(s). Serve the service over HTTPS (behind a TLS reverse proxy)
so the browser doesn't block mixed content.

| Artifact | Path |
|----------|------|
| Constitution | [`.specify/memory/constitution.md`](.specify/memory/constitution.md) |
| Spec | [`specs/001-extraction-service/spec.md`](specs/001-extraction-service/spec.md) |
| HTTP contract | [`specs/001-extraction-service/contracts/extraction-service.md`](specs/001-extraction-service/contracts/extraction-service.md) |
| Quality checklist | [`specs/001-extraction-service/checklists/requirements.md`](specs/001-extraction-service/checklists/requirements.md) |

## Share with friends (Cloudflare quick tunnel)

The GrabTube browser extension can point at this service from anywhere. To share your
running instance without a server or domain, start the optional quick tunnel:

```powershell
docker compose --profile quick up -d --build
docker compose logs -f cloudflared-quick     # wait for the trycloudflare.com banner, then Ctrl+C
```

Or filter the log (it can take a few seconds to appear; rerun until it does):

```powershell
docker compose logs cloudflared-quick | Select-String trycloudflare.com    # PowerShell
docker compose logs cloudflared-quick | grep trycloudflare.com             # bash/zsh
```

Take the **newest** `https://<random-words>.trycloudflare.com` line (ignore
`api.trycloudflare.com`) and send it to your friends; they paste it into the extension's
Settings. The address **changes every time the tunnel restarts**. Stop sharing (the service
keeps running) with `docker compose stop cloudflared-quick`.

No access key protects the service: anyone with the address can use it, within the per-IP
rate limits. Share the link privately. Downloads run from your connection. Rate limits key on
`CF-Connecting-IP` (`GT_CLIENT_IP_HEADER`), which Cloudflare sets and clients can't fake through
the tunnel. Compose publishes port 8080 on this machine only (`127.0.0.1`), so other devices
can't reach the service around the tunnel. If you open it to your network by changing that to
`"8080:8080"`, clear `GT_CLIENT_IP_HEADER`, or those devices can fake the header.

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
