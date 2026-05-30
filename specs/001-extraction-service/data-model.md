# Phase 1 Data Model: Backend Extraction Service

**Date**: 2026-05-30 | **Feature**: `001-extraction-service`

All entities are **in-memory or on local disk** (single-instance, no database). This document defines
the internal domain model and how it maps to the wire shapes in `contracts/extraction-service.md`.
Field names below use the contract's casing where they cross the wire.

---

## Enumerations

- **LinkKind**: `video` | `playlist` | `invalid`
- **Format**: `mp4` | `mp3`
- **JobStatus**: `queued` | `running` | `completed` | `failed` | `canceled`
- **ItemStatus**: `pending` | `running` | `done` | `failed`
- **ResultKind**: `file` | `zip`
- **ErrorCode** (stable, user-safe): `invalid_url` | `unavailable` | `live_unsupported` |
  `drm_protected` | `no_formats` | `quality_required` | `timeout` | `rate_limited` |
  `result_expired` | `not_found` | `internal`

---

## Entities

### QualityOption
One selectable MP4 variant for a video.

| Field | Type | Rules |
|-------|------|-------|
| id | string | yt-dlp format id; non-empty |
| label | string | e.g. `1080p`, `720p` |
| heightPx | int | **MUST be ≤ 1080** (SC-004); options above 1080p are excluded entirely |
| container | string | `mp4` |

### MediaItem
A single resolvable video.

| Field | Type | Rules |
|-------|------|-------|
| id | string | video id; unique within a playlist |
| title | string | required |
| author | string | channel/author; may be empty if source omits |
| thumbnailUrl | string (URL) | required when source provides; used as MP3 cover source |
| durationSeconds | int | ≥ 0 |
| audioAvailable | bool | whether an MP3 can be produced (FR-004) |
| qualities | QualityOption[] | all ≤ 1080p; empty for playlist-listing items |

**Validation**: a MediaItem with neither qualities nor `audioAvailable` → `no_formats` error.

### Playlist
An ordered collection of MediaItems.

| Field | Type | Rules |
|-------|------|-------|
| id | string | playlist id |
| title | string | required |
| count | int | total item count; **no fixed cap** (FR-009) |
| items | MediaItem[] | ordered; listing items carry empty `qualities` |

### Job
A unit of async work. **In-memory**, keyed by `jobId`.

| Field | Type | Rules |
|-------|------|-------|
| jobId | string | server-generated, unique |
| source | LinkKind | `video` or `playlist` |
| format | Format | `mp4` requires `qualityId`; `mp3` MUST omit it (FR-006/FR-007) |
| qualityId | string \| null | required iff `format == mp4` |
| status | JobStatus | lifecycle below |
| overallProgress | int | 0–100 |
| resultKind | ResultKind \| null | set on completion (`file` single, `zip` playlist) |
| resultRef | ResultArtifact \| null | internal pointer to the produced artifact |
| error | ErrorResponse \| null | set when `status == failed` |
| items | JobItem[] | one per playlist item; single video → 0 or 1 entry |
| createdAt / completedAt | timestamp | drives 30-min retention sweep |
| cancelToken | internal | cooperative cancellation signal |

**State transitions**:
```
queued ──(pool slot acquired)──▶ running ──(all items resolved)──▶ completed
  │                                  │
  │                                  ├──(fatal error)──▶ failed
  └──(cancel)──▶ canceled ◀──(cancel)─┘
```
- A **failed individual item** keeps the job `running`; the job still reaches `completed` with partial
  results (FR-010). The job is `failed` only on a job-level fatal error (e.g., invalid source, all
  items failed, global resource limit hit).
- `canceled` is reachable from `queued` or `running`; processing stops within 10 s (SC-006).

### JobItem
Per-item state for playlist (and single-video) jobs.

| Field | Type | Rules |
|-------|------|-------|
| itemId | string | source video id |
| title | string | for progress UI |
| status | ItemStatus | `pending → running → done \| failed` |
| progress | int | 0–100 |
| artifactPath | string \| null | per-item produced file (pre-ZIP) |

### ResultArtifact
The produced output on local disk; transient.

| Field | Type | Rules |
|-------|------|-------|
| path | string | local temp path |
| kind | ResultKind | `file` or `zip` |
| contentType | string | `video/mp4` \| `audio/mpeg` \| `application/zip` |
| filename | string | for `Content-Disposition` |
| expiresAt | timestamp | `completedAt + 30 min`; sweeper deletes at/after this (SC-008) |

**Lifecycle**: created on completion → downloadable until `expiresAt` → deleted by sweeper (or earlier
on explicit cleanup / client disconnect). Fetch after deletion → `result_expired`.

### ErrorResponse
Returned for any non-2xx (matches contract `{ "error": { "code", "message" } }`).

| Field | Type | Rules |
|-------|------|-------|
| code | ErrorCode | stable, machine-readable |
| message | string | user-safe; no internal detail (Constitution V) |

---

## Wire mapping (contract alignment)

| Contract endpoint | Domain entities | Notes |
|-------------------|-----------------|-------|
| `POST /resolve` → video | MediaItem (+ QualityOption[]) | `kind: "video"`, qualities ≤1080p |
| `POST /resolve` → playlist | Playlist (+ MediaItem[]) | `kind: "playlist"`, listing items have empty qualities |
| `POST /jobs` | Job (create) → `{ jobId, status: "queued" }` (202) | mp4 requires `qualityId` |
| `GET /jobs/{id}` | Job + JobItem[] | `overallProgress`, `resultKind`, `resultUrl`, `items[]` |
| `GET /jobs/{id}/file` | ResultArtifact | stream with `Content-Type` + `Content-Disposition` |
| `POST /jobs/{id}/cancel` | Job (→ canceled) | `{ jobId, status: "canceled" }` |
| any error | ErrorResponse | code → HTTP status: invalid_url=400, unavailable/not_found=404, live_unsupported=422, rate_limited=429, result_expired=410, timeout=504, internal=500 |

## Error code → HTTP status map

| ErrorCode | HTTP | Trigger |
|-----------|------|---------|
| invalid_url | 400 | unrecognized / unsupported link |
| quality_required | 400 | mp4 job without `qualityId` |
| unavailable | 404 | private/deleted/region-blocked |
| not_found | 404 | unknown jobId |
| result_expired | 410 | artifact already swept |
| live_unsupported | 422 | live/upcoming stream |
| drm_protected | 422 | DRM-protected (no circumvention attempted) |
| no_formats | 422 | no MP4 and no audio available |
| rate_limited | 429 | per-IP limit exceeded |
| timeout | 504 | resolve/processing exceeded limit |
| internal | 500 | unexpected failure (detail logged, not returned) |
