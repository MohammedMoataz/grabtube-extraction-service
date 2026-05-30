<!--
Sync Impact Report
==================
Version change: (template/inherited) → 1.0.0
Bump rationale: Initial ratification for the standalone GrabTube Extraction Service — a backend
project distinct from the static website (which has its own "Static-First" constitution).

Principles:
  - I. Contract-First & Backward Compatibility
  - II. Stateless & Transient (No Content Retention)
  - III. Reliability & Graceful Degradation
  - IV. Security & Abuse Resistance (No Secrets in Clients, No DRM Circumvention)
  - V. Observability
  - VI. Test Discipline
Added sections: Operational & Compliance Constraints; Development Workflow & Quality Gates
Removed sections: none
Templates: plan-template.md "Constitution Check" is generic → resolves against this file; OK.
Follow-up: RATIFICATION_DATE set to first adoption (today).
-->

# GrabTube Extraction Service Constitution

## Core Principles

### I. Contract-First & Backward Compatibility

The service's HTTP interface is defined by a published contract
(`specs/001-extraction-service/contracts/extraction-service.md`). The contract is the source of
truth that the GrabTube front-end depends on.

- Changes MUST keep existing consumers working: additive/compatible changes only within a major
  version; breaking changes REQUIRE a new versioned interface and a migration path.
- Request/response shapes, status semantics, and error codes MUST match the contract; deviations
  are defects.

**Rationale**: A separate front-end is built against this contract. Honoring it is what lets the two
projects evolve independently without breaking users.

### II. Stateless & Transient (No Content Retention)

The service holds no long-term state about users or content.

- Produced files are **transient**: retained only long enough to be retrieved, then removed within a
  defined retention window. The service is NOT a media library.
- No personal data is collected or stored; submitted links and job state are ephemeral.
- The service does not host, archive, or redistribute copyrighted content.

**Rationale**: Minimizes legal exposure, storage cost, and privacy risk; keeps the service a pure
processing pipeline.

### III. Reliability & Graceful Degradation

Failures and load MUST degrade gracefully, never hang or crash the host.

- Every external operation (resolution, conversion, packaging, transfer) MUST have a timeout.
- Resource usage MUST be bounded per job and overall (concurrency limits, per-request limits) so
  large playlists or spikes degrade rather than exhaust the host.
- Batch (playlist) work MUST tolerate per-item failure and report partial success.

**Rationale**: A downloader hits flaky upstreams and unbounded inputs; bounded, fault-tolerant
behavior is the difference between a usable service and an outage.

### IV. Security & Abuse Resistance (No Secrets in Clients, No DRM Circumvention)

- The service MUST be callable by a browser client **without any client-embedded secret**, with CORS
  scoped to the configured site origin(s).
- The service MUST validate all input and enforce **rate limiting / abuse protection**, returning a
  clear rate-limit response when exceeded.
- The service MUST NOT attempt to bypass DRM or other technical protection measures.
- Any operator secrets (proxies, cookies, credentials) live only server-side, never in responses or
  client-reachable surfaces.

**Rationale**: The client is a public static site that cannot keep secrets; abuse protection and
input validation are the only gate. Refusing DRM circumvention keeps the project lawful.

### V. Observability

The service MUST be operable and debuggable in production.

- Structured logs for requests, jobs, and failures (no sensitive data); a health/readiness signal;
  and basic metrics (job counts, durations, failure rates, queue depth).
- Errors returned to clients carry a stable code; internal detail stays in logs, not responses.

**Rationale**: A processing service with external dependencies fails in varied ways; observability
makes those failures diagnosable without leaking detail to clients.

### VI. Test Discipline

Behavior MUST be protected by automated tests, and the contract MUST be enforced by tests.

- **Contract tests** verify every endpoint/response shape and error code against the published
  contract (Principle I).
- Core flows (resolve, single MP4, MP3 + metadata, playlist ZIP, cancel, error paths) MUST have
  automated coverage; bug fixes add regression tests.
- Tests MUST be deterministic and runnable locally and in CI with a single documented command;
  upstream access is mocked/faked so tests don't depend on live external sources.

**Rationale**: Tests are the executable record of the contract and behavior, and the safety net for
keeping the front-end working.

## Operational & Compliance Constraints

- **Configuration over secrets-in-code**: All deployment configuration (allowed origins, rate
  limits, retention window, concurrency caps, proxy/cookie settings) is provided via environment/
  config, never hardcoded.
- **Transport security**: All client-facing traffic MUST be over HTTPS.
- **Upstream maintenance**: The underlying extraction capability changes as sources change; keeping
  it current is an ongoing, expected maintenance responsibility.
- **Legal posture**: The service surfaces no claim of rights over content; operators and users are
  responsible for lawful use and platform-terms compliance. No copyrighted content is retained.

## Development Workflow & Quality Gates

- **Spec-driven**: Work follows the Spec Kit flow — spec → (clarify) → plan → tasks → (analyze) →
  implement. See `SPECKIT-GUIDE.md`.
- **Definition of Done**: (1) meets all six principles; (2) contract tests + core-flow tests pass in
  CI; (3) reviewed for contract compatibility and resource-bound/security behavior.
- **CI gates (must block)**: lint/format, unit tests, contract tests, integration tests for core
  flows. Performance/load checks where applicable.
- **Complexity justification**: Any principle deviation (extra statefulness, unbounded operation,
  relaxed CORS) MUST be recorded in the plan's Complexity Tracking with the rejected simpler option.

## Governance

This constitution supersedes other practices for this service. Where a habit or document conflicts
with it, this constitution wins.

- **Amendments** are proposed via pull request that updates this file, states rationale, and bumps
  the version. Approval from a maintainer is required before merge.
- **Versioning policy** (semantic): **MAJOR** — remove/redefine a principle; **MINOR** — add a
  principle/section or materially expand guidance; **PATCH** — clarifications and wording.
- **Compliance review**: every PR review verifies adherence to the Core Principles and Quality
  Gates. `/speckit-analyze` treats any conflict with a NON-NEGOTIABLE or MUST statement as CRITICAL.
- **Runtime guidance**: use `SPECKIT-GUIDE.md` for the day-to-day workflow; it MUST stay consistent
  with this constitution.

**Version**: 1.0.0 | **Ratified**: 2026-05-30 | **Last Amended**: 2026-05-30
