# Feature Specification: Backend Extraction Service

**Feature Branch**: `001-extraction-service`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "Backend extraction service for the GrabTube YouTube downloader. A self-hosted HTTP service (yt-dlp + ffmpeg based) that the static front-end calls via a configurable public endpoint... implements the HTTP contract already defined in specs/001-extraction-service/contracts/extraction-service.md..."

## Overview

This service is the **download engine** behind the GrabTube website (feature `001`). The website is
a static front-end with no backend of its own; it delegates all retrieval and conversion to this
**separate, self-hosted service** over HTTP. This service resolves YouTube links into metadata and
available formats, performs the actual video/audio extraction and conversion, packages playlists,
and streams the finished files back. It exposes the interface already defined in
`specs/001-extraction-service/contracts/extraction-service.md` and must remain compatible with it.

> **Project boundary**: This is a backend service and is a **distinct project** from the static
> website. It is intentionally NOT governed by the website's "Static-First, No Backend" constitution
> and is expected to live in (or move to) its own repository with its own governance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve a link into metadata and formats (Priority: P1)

The calling client sends a YouTube video or playlist link and receives back the content's details
(title, author/channel, thumbnail, duration), the list of available MP4 video qualities (capped at
1080p), and whether audio is available — so the front-end can show a preview and let the visitor
choose a format.

**Why this priority**: Every download flow starts with resolution. Nothing else can happen without
it, and it is independently demonstrable.

**Independent Test**: Send a valid single-video link and confirm the response contains the title,
author, thumbnail, duration, an `audioAvailable` flag, and a list of MP4 qualities none of which
exceed 1080p. Send a playlist link and confirm a playlist title, item count, and ordered items.

**Acceptance Scenarios**:

1. **Given** a valid single-video link, **When** the client requests resolution, **Then** the
   service returns the video's metadata and its available MP4 qualities, all ≤ 1080p, plus whether
   audio can be produced.
2. **Given** a valid playlist link, **When** the client requests resolution, **Then** the service
   returns the playlist title, total item count, and the ordered list of contained videos.
3. **Given** a link whose source exposes qualities above 1080p, **When** resolved, **Then** those
   higher resolutions are excluded from the returned list.

---

### User Story 2 - Produce a single video download as MP4 (Priority: P1)

The client requests a download job for a single video at a chosen quality; the service produces a
playable MP4 and makes it available for retrieval.

**Why this priority**: Together with US1 this is the minimum viable service — it lets the front-end
deliver its core MVP (single-video MP4 download).

**Independent Test**: Create an MP4 job for a resolved video at a given quality, poll until it
completes, fetch the result, and confirm a playable MP4 at (about) the requested resolution with a
filename provided by the service.

**Acceptance Scenarios**:

1. **Given** a resolved video and a chosen quality, **When** the client creates an MP4 job, **Then**
   the service accepts it and returns a job identifier.
2. **Given** a running MP4 job, **When** the client polls its status, **Then** the service reports
   progress and, on completion, a way to fetch the finished file.
3. **Given** a completed MP4 job, **When** the client fetches the result, **Then** the service
   streams a playable MP4 with an appropriate content type and a download filename.
4. **Given** an MP4 job request without a chosen quality, **When** submitted, **Then** the service
   rejects it with a clear, user-safe error.

---

### User Story 3 - Produce an MP3 with embedded metadata (Priority: P2)

The client requests an audio job; the service produces an MP3 with the source's metadata embedded —
title, author/channel, cover artwork (thumbnail), and any available extra fields.

**Why this priority**: Audio extraction is a primary differentiator of the product, building on the
same job mechanism as US2.

**Independent Test**: Create an MP3 job for a resolved video, fetch the result, and confirm a
playable MP3 whose embedded metadata shows the correct title, author, and cover artwork.

**Acceptance Scenarios**:

1. **Given** a resolved video with audio available, **When** the client creates an MP3 job, **Then**
   the service produces an MP3 with title, author, and cover artwork embedded.
2. **Given** a source missing some metadata fields, **When** the MP3 is produced, **Then** available
   fields are embedded and missing ones are omitted without failing the job.
3. **Given** an MP3 job request, **When** submitted, **Then** no video quality selection is required.

---

### User Story 4 - Process a playlist into a single ZIP (Priority: P3)

The client requests a job for a playlist; the service processes every item (no fixed cap) in the
chosen format and packages the results into a single ZIP, reporting per-item and overall progress,
and continuing past individual item failures.

**Why this priority**: Playlist support is high-value but builds on single-item jobs and is the most
resource-intensive, so it follows the single-item capabilities.

**Independent Test**: Create a playlist job, poll and observe per-item plus overall progress, then
fetch a single ZIP containing one file per successfully processed item; confirm a deliberately
failing item is reported as failed while the rest complete.

**Acceptance Scenarios**:

1. **Given** a resolved playlist and a chosen format, **When** the client creates a job, **Then**
   the service processes all items with no fixed cap and reports per-item and overall progress.
2. **Given** a playlist job, **When** it completes, **Then** the result is a single ZIP containing
   the produced files.
3. **Given** one item in a playlist cannot be processed, **When** the job runs, **Then** that item
   is marked failed and the remaining items still complete (partial success).

---

### User Story 5 - Cancel an in-progress job (Priority: P3)

The client cancels a running job (e.g., a large playlist); the service stops processing promptly and
releases the associated resources.

**Why this priority**: Important for large playlists and resource hygiene, but only meaningful once
long-running jobs exist.

**Independent Test**: Start a playlist job, request cancellation, and confirm the job transitions to
canceled and stops consuming processing resources shortly after.

**Acceptance Scenarios**:

1. **Given** a running job, **When** the client cancels it, **Then** the service marks it canceled
   and stops further processing.
2. **Given** a canceled job, **When** the client polls it, **Then** the status reflects cancellation.

---

### Edge Cases

- **Invalid/unsupported link**: Not a recognizable YouTube video or playlist → user-safe validation
  error; no job created.
- **Unavailable content**: Private, deleted, region-blocked, or otherwise inaccessible → clear
  "unavailable" error explaining it cannot be retrieved.
- **Live or upcoming stream**: Link points to a live/scheduled stream → rejected as unsupported.
- **DRM-protected content**: Content that cannot be downloaded without circumventing protection →
  reported as unavailable; the service does not attempt circumvention.
- **No downloadable video formats**: A video exposes no MP4 formats → audio (MP3) is still offered
  if available; otherwise a clear "cannot be downloaded" error.
- **Slow source / timeout**: Resolution or processing exceeds limits → the job/request times out
  with a clear, retryable error rather than hanging indefinitely.
- **Very large playlist**: No fixed cap, but resource/time limits apply → progress is reported, and
  if a global resource limit is hit the job fails gracefully with explanation.
- **Partial playlist failure**: Some items fail → job completes with partial success; failures are
  reported per item.
- **Abusive request volume**: Excessive requests from a client → throttled with a clear rate-limit
  response.
- **Result fetched after expiry**: A transient result has already been cleaned up → clear "expired"
  error inviting the client to re-request.
- **Client disconnects mid-download**: The service handles interrupted transfers without leaking
  resources.
- **Duplicate job request**: Identical concurrent requests should not multiply work unnecessarily.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST accept a YouTube video or playlist link and classify it as video,
  playlist, or invalid, returning a clear error for invalid/unsupported links.
- **FR-002**: For a video link, the service MUST return metadata: title, author/channel, thumbnail,
  and duration.
- **FR-003**: The service MUST return the list of available MP4 video qualities for a video, **capped
  at 1080p**, and MUST exclude any resolution above 1080p.
- **FR-004**: The service MUST indicate whether audio (MP3) can be produced for a given video.
- **FR-005**: For a playlist link, the service MUST return the playlist title, total item count, and
  the ordered list of contained videos.
- **FR-006**: The service MUST create a download job for a single video as MP4 at a client-chosen
  quality, and MUST reject an MP4 request that lacks a quality selection.
- **FR-007**: The service MUST create a download job that produces an MP3 for a video, requiring no
  video-quality selection.
- **FR-008**: When producing an MP3, the service MUST embed available source metadata — at minimum
  title, author/channel, and cover artwork (thumbnail) — and additional fields (e.g., album, year)
  when available, omitting missing fields without failing.
- **FR-009**: The service MUST create a download job for a playlist that processes **every** item
  (no fixed cap) in the chosen format and packages the results into a **single ZIP**.
- **FR-010**: The service MUST continue processing a playlist when individual items fail, marking
  failed items and completing the remaining ones (partial success).
- **FR-011**: The service MUST expose an asynchronous job lifecycle: create a job, poll its status
  with **overall progress** and **per-item progress/status**, and obtain the finished result.
- **FR-012**: The service MUST allow a client to cancel an in-progress job, after which it stops
  processing and reflects a canceled status.
- **FR-013**: On completion, the service MUST stream the result (MP4, MP3, or playlist ZIP) with a
  content type appropriate to the format and a download filename.
- **FR-014**: The service MUST be callable from a browser-based client: it MUST permit cross-origin
  requests from the configured site origin and MUST NOT require any client-embedded secret.
- **FR-015**: The service MUST perform its own abuse protection, including request validation and
  rate limiting, returning a clear rate-limit error when limits are exceeded.
- **FR-016**: The service MUST return clear, user-safe error responses (a stable code plus a
  human-readable message) for: invalid links, unavailable/private/region-blocked/deleted content,
  live/upcoming streams, DRM-protected content, and timeouts.
- **FR-017**: The service MUST treat produced files as **transient**: results are retained only long
  enough to be retrieved and are removed afterward per a defined retention policy; the service does
  not maintain a library of downloaded content.
- **FR-018**: The service MUST NOT attempt to bypass DRM or other technical protection measures.
- **FR-019**: The service MUST remain compatible with the HTTP contract defined in
  `specs/001-extraction-service/contracts/extraction-service.md` (request/response shapes, status
  semantics, and endpoints), so the existing front-end works against it without changes.
- **FR-020**: The service MUST bound resource usage per job and overall (e.g., concurrency and
  per-request limits) so that large playlists or high load degrade gracefully rather than exhausting
  the host.

### Key Entities *(include if feature involves data)*

- **Link**: A submitted reference; classified as video, playlist, or invalid.
- **MediaItem**: A single resolvable video — title, author, thumbnail, duration, available MP4
  qualities (≤1080p), and audio availability.
- **QualityOption**: One selectable MP4 variant (resolution label + identifier).
- **Playlist**: An ordered collection of MediaItems with a title and total count.
- **Job**: A unit of work — its requested format/quality, status (queued, running, completed,
  failed, canceled), overall progress, and per-item statuses for batches.
- **ResultArtifact**: The produced output — a single media file or a playlist ZIP — transient, with
  a retention lifetime and a download filename.
- **ErrorResponse**: A stable error code plus a user-safe message returned for any failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For available content, a resolution request returns metadata and formats within 5
  seconds under normal conditions.
- **SC-002**: At least 95% of jobs for valid, available single videos complete successfully and
  yield a retrievable file.
- **SC-003**: 100% of produced MP3s contain the correct title, author, and cover artwork when the
  source provides those fields.
- **SC-004**: Returned MP4 quality lists never include a resolution above 1080p (0 violations).
- **SC-005**: A playlist job yields a single ZIP containing one file for every successfully
  processed item, and every failed item is individually reported.
- **SC-006**: A cancellation request stops further item processing within 10 seconds and the job
  reports a canceled status.
- **SC-007**: Every defined failure case (invalid, unavailable, live, DRM, timeout, rate-limited,
  expired result) returns a stable error code and a human-readable message — no opaque or empty
  failures.
- **SC-008**: Transient results are removed within the defined retention window in 100% of cases
  (no indefinite accumulation of downloaded content).
- **SC-009**: Under sustained load or a very large playlist, the service stays responsive to new
  resolution/status requests and never exhausts host resources to the point of crashing.
- **SC-010**: The service passes a compatibility check against every endpoint and response shape in
  the front-end contract, so the existing GrabTube front-end works against it unmodified.

## Assumptions

- **Separate project & governance**: This service is a standalone backend, not part of the static
  website project, and will have its own repository and constitution. Documented here so planning
  does not inherit the website's Static-First constraints.
- **Contract is authoritative**: The existing `extraction-service.md` contract defines the external
  interface; this spec describes the behavior behind it and must not break it.
- **YouTube only**: Only YouTube video and playlist links are in scope; other platforms are out of
  scope for this version.
- **Underlying extraction capability**: The service relies on a mature extraction/conversion
  capability for retrieval, format selection, transcoding, and metadata embedding. Keeping this
  current (as upstream sources change) is an ongoing operational responsibility.
- **Anti-bot / access**: The operator may need to supply network egress, and possibly cookies or
  proxying, so the service can access content reliably; specifics are an operational concern.
- **Transient retention default**: Results are deleted promptly after retrieval, and in any case
  within a short retention window (assumed on the order of tens of minutes) unless configured
  otherwise. No long-term storage of content.
- **Anonymous access, no accounts**: The service does not implement user accounts or authentication
  for end users; abuse protection is by rate limiting and validation, not login.
- **MP3 / MP4 only**: Audio is delivered as MP3 and video as MP4 in this version; other formats are
  out of scope.
- **Responsible use & legality**: Operating the service and using it is the operator's/user's
  responsibility under applicable law and platform terms; the service does not host or redistribute
  copyrighted content and does not circumvent DRM.
