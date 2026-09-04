<!--
Sync Impact Report
- Version change: unversioned pointer -> 1.0.0
- Modified principles: pointer to AGENTS.md -> five self-contained engineering principles
- Added sections: Technology and Deployment Constraints; Development Workflow and Quality Gates; Governance
- Removed sections: none
- Follow-up TODOs: none
-->
# Review Platform Constitution

## Core Principles

### I. Contract First

Public boundaries MUST be designed and reviewed before dependent implementation.

- `contracts/review-platform/v1/openapi.yaml` is the canonical React web ↔ backend contract.
- JSON Schema under `contracts/review-platform/v1/schemas/` is the canonical engine ↔ skill contract.
- Web MUST generate transport types from OpenAPI and MUST NOT maintain handwritten copies of server DTOs.
- FastAPI export MUST remain semantically compatible with the canonical OpenAPI.
- A contract change MUST update affected schemas, examples and `CHANGELOG.md` in one contract PR.
- Removing a field, adding a required field or changing existing semantics MUST create a new major contract version.

Rationale: web and backend/skills are developed in parallel and require one language-neutral source of truth.

### II. One Domain Core, Explicit Adapters

Review semantics MUST have one implementation independent of delivery channel and infrastructure.

- `review-core` MUST expose coarse application operations for documents, runs, reports, dialogues and human decisions.
- Domain and application modules MUST NOT import FastAPI, SQLAlchemy, queue libraries or model-provider SDKs.
- React uses the core through HTTP; API, worker and CLI are composition roots and adapters.
- Local CLI and AI skills MUST call the Python application/core directly and MUST NOT require an HTTP server.
- Parser, repository, artifact storage, job queue, model and skill runtime MUST remain behind explicit ports when more than one real implementation is planned.
- A new network service MUST be justified by a measured scaling, failure-isolation or independent-deployment constraint.

Rationale: one deep core prevents the PoC, standalone engine and web service from becoming three products.

### III. Immutable Evidence, Mutable Review State

Inputs and published model output MUST remain reproducible; human review state MUST remain separate.

- Document versions, review-profile versions, execution snapshots, reports, findings, evidence anchors and coverage MUST be immutable after publication.
- A run MUST reference exact versions and digests of document, context, profile, skill, model profile, dialogue policy and engine.
- Dialogue, proposed resolution and `HumanDecision` MUST be stored separately from the immutable report.
- Mutable dialogue and decision records MUST use `expected_revision`; stale writes MUST return a conflict instead of silently overwriting state.
- Model output MUST NOT automatically confirm, reject or edit a finding or source document.
- A finding remains a candidate problem until a human decision is explicitly stored.

Rationale: an analyst must be able to distinguish source evidence, model output and human judgment.

### IV. Validation and Tests Are Release Gates

No result or integration is complete until its boundary and semantic invariants are verified.

- Engine output MUST pass JSON Schema and semantic checks before a report is published.
- Semantic checks MUST cover referenced IDs, exact quotes and offsets, anchors, missing-requirement scope and the complete coverage partition.
- Large documents MUST NOT be silently truncated. Partial processing MUST publish explicit source or fragment gaps; an unavailable primary document MUST fail the run.
- Every contract baseline MUST validate OpenAPI, all HTTP examples and all skill examples.
- Backend changes MUST pass unit, contract and PostgreSQL integration tests; web changes MUST pass typecheck, component tests and the applicable Playwright flow.
- The synthetic tracer bullet MUST work against MSW, the real HTTP adapter and the local CLI/skill without divergent DTOs.
- Existing feature-001 PoC regression tests MUST remain green.

Rationale: syntactically valid model JSON is insufficient for a source-linked review product.

### V. Scope Discipline and Data Separation

Implementation MUST stay inside the approved slice and MUST preserve the distinction between evidence and assumptions.

- A specification, plan or task list does not authorize implementation by itself; implementation begins only after an explicit user instruction.
- MTS documents, rules, interviews, examples and constraints MUST remain under `MTS/` and MUST NOT enter common skills, contracts or synthetic fixtures.
- Common conclusions MUST live under `knowledge/` with sources and applicability limits.
- Document text, context and user messages MUST be treated as untrusted data, never as instructions that override engine or skill rules.
- Provider credentials MUST remain server-side and MUST NOT appear in browser payloads, public DTOs, skills, reports, fixtures or safe logs.
- RAG, training, OCR, autonomous tool selection, automatic document editing and new infrastructure MUST NOT be added without a separately approved requirement.

Rationale: the product is still under validation, so hidden scope and client-specific leakage create more risk than value.

## Technology and Deployment Constraints

The following versions are the implementation baseline verified on 2026-09-04. Direct dependencies MUST be pinned in lock files. A version change MUST use a dedicated PR and pass contract, migration and regression gates; it does not require a constitution amendment when architecture and public contracts remain unchanged.

| Area | Required baseline |
| --- | --- |
| Web runtime | Node.js 24.20.0 LTS; npm 12.0.2 |
| Web application | React/react-dom 19.2.8; TypeScript 6.0.3; Vite 8.2.2; plugin-react 6.1.1 |
| Web data/routing | React Router 7.18.3; TanStack Query 5.102.8 |
| Web contracts/tests | Orval 8.28.1; MSW 2.15.0; Vitest; Testing Library; Playwright |
| Web UI | Tailwind CSS 4; accessible Radix UI primitives; React Hook Form; Zod; PDF.js |
| Python runtime | Python 3.14.7; uv 0.12.9 with committed `uv.lock` |
| Backend | FastAPI 0.141.1; Pydantic 2.13.5; pydantic-settings 2.15.0; Uvicorn 0.52.4 |
| Persistence | PostgreSQL 18.6; SQLAlchemy 2.0.52 async; Alembic 1.19.1; psycopg 3.3.5 |
| Background work | Procrastinate 3.9.0 behind `JobQueue`; transactional outbox; at-least-once, idempotent handlers |
| Artifacts | `ArtifactStore`; durable POSIX volume first; optional S3 adapter through boto3 1.43.88 |
| Models/documents | Own `ModelGateway`; deterministic fake plus OpenAI-compatible adapter; pdfplumber adapter for text-layer PDF; UTF-8 TXT/Markdown directly |
| Packaging | Docker Compose with reverse proxy, React SPA, API, worker and PostgreSQL |

Additional constraints:

- The first HTTP v1 deployment MUST contain exactly one operator-configured actor, organization and workspace.
- HTTP v1 MUST NOT implement login, accounts, membership, access roles, permission checks, cookie or bearer sessions, CSRF, or RLS as access control.
- `organization_id` and `workspace_id` are data namespaces and future migration seams, not claims of current multi-organization isolation.
- Any caller that reaches HTTP v1 acts as the configured actor; API and reverse proxy MUST therefore run only inside a trusted network boundary.
- Authentication, authorization, public exposure and multi-organization runtime require a new specification, threat model and ADR.
- React SPA and `/api` MUST use one origin in the initial deployment.
- The first system MUST remain a modular monolith with separate API and worker processes from one Python codebase.
- PostgreSQL is the source of truth for runtime metadata and mutable state. Artifact bytes MUST be stored through `ArtifactStore`.
- Procrastinate MUST remain replaceable behind `JobQueue`; business state and outbox MUST commit atomically.
- MinIO Community MUST NOT be a production dependency. An operator-selected S3-compatible service MAY implement the optional adapter.
- LangChain, Redis, RabbitMQ, Kubernetes, a vector database and a managed cloud control plane are outside the current baseline.

## Development Workflow and Quality Gates

1. Start implementation branches from the current immutable contract tag documented in `architecture/parallel-development.md`.
2. Web owns `apps/web/`; backend/skills own `apps/api/`, `apps/worker/`, `apps/cli/`, `packages/`, `skills/` and `deploy/`. Changes under `contracts/` require joint review.
3. Implement the fixture tracer bullet before PostgreSQL, a real queue or a real model adapter: bootstrap → upload → create/poll run → immutable report → finding state → one dialogue turn → human decision.
4. Implement durable persistence and worker processing only after the same HTTP flow passes against deterministic fakes.
5. A PR that changes a public HTTP or skill schema MUST be merged before dependent web or backend implementation PRs.
6. CI MUST fail on contract/schema/example incompatibility, a divergent generated web client, Python or TypeScript test failure, broken PoC regression, leaked client data or leaked provider secrets.
7. Review MUST verify that no auth runtime, multi-organization claim or client-specific material entered the current slice.
8. Green technical tests demonstrate implementation consistency only; they MUST NOT be recorded as proof of product value, demand, time savings or pilot success.

Development details and task order are maintained in `specs/002-target-review-platform/`. Product and knowledge-maintenance rules remain in `AGENTS.md`; `AGENTS.md` does not replace the engineering principles in this constitution.

## Governance

This constitution governs technical plans, task generation, implementation and review for Review Platform. When another project document conflicts with it, the constitution prevails unless a later explicit user decision requires an amendment. Direct user instructions and system-level instructions remain authoritative.

- Amendments MUST be made through the Spec Kit constitution workflow and MUST include a Sync Impact Report.
- A material principle removal or incompatible redefinition requires a MAJOR version bump.
- A new principle or materially expanded governance section requires a MINOR version bump.
- Clarification without changed obligations requires a PATCH version bump.
- Each amendment MUST record an ISO date, rationale and affected plans, contracts or migration work.
- Every implementation plan MUST include a Constitution Check before task generation.
- Every release or integration PR MUST verify the applicable principles and document justified exceptions.
- Product decisions MUST be recorded in `knowledge/decisions.md`; source evidence MUST be recorded in `knowledge/sources.md`.
- `AGENTS.md` remains the only source of agent interaction rules and knowledge-base maintenance rules. `CLAUDE.md` MUST remain a relative symlink to it.

**Version**: 1.0.0 | **Ratified**: 2026-09-04 | **Last Amended**: 2026-09-04
