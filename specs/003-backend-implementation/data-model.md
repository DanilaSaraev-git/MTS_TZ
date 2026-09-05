# Data Model: backend feature 003

Статус: implementation-ready logical/relational contract. Имена таблиц предложены для SQLAlchemy/Alembic; публичные названия остаются в canonical HTTP v1. Все timestamps — UTC, все server resource IDs — UUID.

## Общие правила

- `Organization`, `Workspace` и `Actor` создаются/проверяются operator bootstrap, не public HTTP.
- Каждый workspace-owned primary/unique/foreign key включает `organization_id` и `workspace_id`, даже если внешний DTO показывает только resource UUID.
- Namespace constraints обеспечивают целостность/provenance, а не authentication/authorization.
- Immutable rows не обновляются и не удаляются runtime role после публикации. Mutable lifecycle/head/availability rows используют integer `revision` и compare-and-set (CAS).
- JSON input сначала читается duplicate-key-safe и проверяется schema/semantics; JSONB не считается canonical wire representation.
- Raw document bytes и canonical report bytes находятся в `ArtifactStore`; БД хранит opaque key, size и SHA-256.
- Любой digest канонического JSON хранится вместе с `codec_id`; feature 003 принимает только `jcs-rfc8785-0.1.4`.

## Deployment context

### `deployments`

| Column | Type / constraint |
| --- | --- |
| `id` | UUID PK, generated once for a logical installation and persisted across restarts |
| `release_version` | safe release identifier |
| `created_at` | immutable timestamp |

Configured `deployment_id` MUST match this row at startup/readiness. It is the exact owner namespace for system configuration; a process/container instance ID is not a deployment ID.

### `organizations`

| Column | Type / constraint |
| --- | --- |
| `id` | UUID PK |
| `slug` | non-empty unique label |
| `display_name` | non-empty |
| `created_at` | immutable timestamp |

В первом deployment существует ровно одна configured row. Приложение сверяет config с row at startup/readiness.

### `workspaces`

| Column | Type / constraint |
| --- | --- |
| `organization_id` | FK organizations, part of PK/unique namespace |
| `id` | UUID, unique with organization |
| `name` | non-empty |
| `created_at` | immutable timestamp |

### `actors`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `id` | namespace identity and composite FK |
| `display_name` | attribution label |
| `created_at` | immutable |

Actor не содержит credentials/account/role. Каждый HTTP caller атрибутируется этой configured row.

## Artifact metadata

### `artifacts`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `id` | composite identity |
| `kind` | `document_original|report_canonical|derived_parser_raw` |
| `store_key` | opaque relative/provider key, unique; filename/path запрещён |
| `size_bytes` | positive |
| `sha256` | 64 lowercase hex |
| `media_type` | safe media type |
| `canonical_codec_id` | nullable; required and equal to `jcs-rfc8785-0.1.4` for `report_canonical`, null for raw bytes |
| `created_at` | immutable |

Staging keys не регистрируются в таблице. Только atomically promoted object может быть referenced. Unreferenced promoted object — orphan, недоступный API и пригодный для collector после grace period. Отдельная intent-row не нужна: publisher и collector обязаны использовать один transaction-scoped PostgreSQL advisory fencing lock, детерминированный exact `(organization_id, workspace_id, store_key, sha256)`. Publisher получает lock до promotion и удерживает через DB reference commit; collector под тем же lock повторно проверяет отсутствие row/reference и удаляет object до release. Hash collision у advisory-key допустим только как лишняя сериализация, но не как потеря safety.

## Documents and extraction

### `document_versions`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `id` | composite identity |
| `artifact_id` | namespace FK artifacts(kind=document_original), unique per version |
| `filename` | sanitized display name; не storage key/path |
| `media_type` | `application/pdf|text/markdown|text/plain` |
| `size_bytes`, `sha256` | equal referenced artifact |
| `created_by`, `created_at` | configured actor provenance |

`document_versions` is immutable immediately after upload. The upload transaction also creates exactly one feature-003 `document_extractions` row in `pending` with the current release parser/settings. Public `extraction_state` is a projection of that separate lifecycle row; it is not a field that mutates the document.

### `document_extractions`

| Column | Type / constraint |
| --- | --- |
| namespace + `id` | extraction identity |
| `document_id` | namespace FK immutable document version |
| `parser_name`, `parser_version`, `settings_digest`, `settings_codec_id` | exact extraction identity; codec is `jcs-rfc8785-0.1.4` |
| `state` | `pending|extracting|completed|partial|failed` |
| `attempt_count` | non-negative, bounded by runtime config |
| `checkpoint` | `pending|bytes_verified|parsed|fragments_persisted`; last committed restart point |
| `checkpoint_artifact_id`, `checkpoint_digest`, `checkpoint_codec_id` | nullable derived-parser artifact/canonical digest/codec; required for a durable `parsed` checkpoint |
| `lease_token`, `lease_owner`, `lease_expires_at`, `heartbeat_at` | all null when not actively owned; token is unguessable UUID |
| `error_code`, `safe_error_message` | terminal failure only; no raw content/path |
| `revision` | CAS version |
| `created_at`, `started_at`, `finished_at` | lifecycle timestamps |

Feature 003 enforces unique `(organization_id, workspace_id, document_id)`; parser/settings columns make the selected extraction reproducible rather than caller-selectable. Claim/takeover is one CAS: a worker may claim `pending`, or reclaim `extracting` only when `lease_expires_at < now`, replacing the token, incrementing `attempt_count`/`revision`, and resuming from the last verified checkpoint. Every heartbeat/checkpoint/terminal write predicates on the current `lease_token` and expected `revision`; a stale owner cannot publish. Terminal extraction outcome, fragment set and diagnostics are immutable.

State transitions:

```text
pending -> extracting -> completed
                     -> partial
                     -> failed
extracting --expired lease/CAS takeover--> extracting
```

Reprocessing with different parser/settings is a future feature (or requires a newly uploaded document version); feature 003 never mutates document bytes, extraction identity or a terminal extraction. Exhausted recovery attempts transition to `failed` with a normalized code.

### `fragments`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `document_id`, `extraction_id`, `id` | composite identity |
| `ordinal` | positive, unique per extraction |
| `kind` | `text|table_row` |
| `text` | exact normalized fragment text used by validators/model input |
| `content_sha256` | digest of normalized text + locator |
| `location_json` | tagged PDF/Text locator validated at write |
| `created_at` | extraction timestamp |

Text locator: 1-based `line_start/line_end`, 0-based half-open `char_start/char_end`. PDF locator: 1-based page; normalized `[left,top,right,bottom]` rects in `0..1`; optional 1-based table/row; parser raw artifact may support diagnostics but is not public.

Fragment identity is deterministic inside immutable document extraction: UUIDv5 over document UUID, extraction parser/settings digest, ordinal, content digest and locator digest. Same extraction retry produces same IDs; a uniqueness constraint prevents duplicate retry publication.

### `source_diagnostics`

| Column | Type / constraint |
| --- | --- |
| namespace + `id` | identity |
| `document_id`, `extraction_id` | namespace FKs |
| `ordinal` | stable order per extraction |
| `code` | stable snake_case machine code |
| `safe_message` | no content/path/secret |
| `location_json` | nullable safe page/range reference |

`completed` requires at least one fragment and no loss diagnostic. `partial` requires at least one fragment plus a loss diagnostic. `failed` requires zero usable fragments or fatal diagnostic. Fragment/diagnostic rows and the terminal extraction transition commit together, or are verified by `checkpoint_digest` before a recovery worker reuses them.

## Versioned configuration

### `review_profile_families`

| Column | Type / constraint |
| --- | --- |
| `row_id` | internal UUID PK used by version/head FKs |
| `id` | public logical profile UUID, globally unique inside this deployment database |
| `scope` | `system|workspace` |
| `deployment_id` | required FK deployments for `system`, null for `workspace` |
| `organization_id`, `workspace_id` | both required for `workspace`, both null for `system` |
| `created_at` | immutable |

CHECK constraints require exactly one owner representation: `(scope=system, deployment_id set, organization/workspace null)` or `(scope=workspace, deployment_id null, organization/workspace set)`. The global public-ID uniqueness plus owner indexes prevent ambiguity in the effective system+workspace list. A configured system profile is therefore installation-scoped, not represented by a magic workspace, null wildcard, or process-local constant.

### `review_profile_versions`

| Column | Type / constraint |
| --- | --- |
| `family_row_id`, `version` | composite PK/FK, SemVer |
| `name`, `role`, `goal` | semantic fields |
| `checks_json` | non-empty ordered unique strings |
| `semantic_digest`, `semantic_codec_id` | canonical SHA-256 plus `jcs-rfc8785-0.1.4`, unique within family |
| `supersedes_version` | null only at `1.0.0`; exact prior version otherwise |
| `created_by`, `created_at` | system release or configured actor |

Version rows are append-only and never carry mutable head state.

### `review_profile_heads`

| Column | Type / constraint |
| --- | --- |
| `family_row_id` | PK/FK family |
| `head_version` | FK exact immutable version in the same family |
| `revision` | CAS version |
| `updated_at` | mutable timestamp |

Public `ReviewProfile.id` maps to family `id`. Without `supersedes`, POST creates a workspace family/version/head at `1.0.0` in one transaction. With the current workspace head, it appends the next patch version and CAS-updates only `review_profile_heads`. Missing/foreign reference is `404`; visible system reference is `400 invalid_supersedes`; stale head and unchanged content are distinct `409` conflicts.

### `model_profile_versions`

| Column | Type / constraint |
| --- | --- |
| `id`, `version` | operator/system stable key + SemVer |
| `name`, `description` | safe public metadata |
| `adapter_kind` | `deterministic|openai_compatible` internal |
| `capabilities_json` | supported capabilities |
| `config_digest`, `config_codec_id` | safe canonical digest plus `jcs-rfc8785-0.1.4`, no secret |
| `secret_ref` | server-side reference, never DTO/snapshot text |
| `created_at` | immutable |

### `model_profile_availability`

| Column | Type / constraint |
| --- | --- |
| `deployment_id`, `model_profile_id`, `model_profile_version` | PK and exact version FK |
| `state` | `available|unavailable|degraded|unknown` |
| `reason_code` | nullable safe machine code |
| `checked_at`, `expires_at` | bounded health observation |
| `revision` | CAS version |

Availability is a mutable deployment-local health projection evaluated at read/use time; it is not part of the immutable model profile version or run evidence. At least the deterministic profile is seeded, and its projection is available without egress.

### Canonical HTTP state projections

Internal lifecycle vocabulary never leaks into the root OpenAPI enums:

| Internal state | Canonical HTTP field/value |
| --- | --- |
| `document_extractions.pending|extracting` | `Document.extraction_state=pending` |
| `document_extractions.completed|partial|failed` | same-named `Document.extraction_state` terminal value |
| fresh `model_profile_availability.available` | `ModelProfile.availability=available` |
| `unavailable|degraded|unknown`, missing row, or expired observation | `ModelProfile.availability=unavailable` |

DTO construction validates the resulting value against canonical HTTP schemas. `reason_code`, freshness and internal state remain server-side diagnostics/config-health inputs; they cannot add an enum member. A missing/degraded deterministic seed additionally fails readiness because bootstrap invariants require it to be available.

### `skill_versions`

`(skill_id, version)` plus `package_sha256`, manifest contract versions, capability list and artifact/package reference. Immutable and organization-neutral.

### `dialogue_policy_versions`

`(id, version)`, JCS digest plus `codec_id`, positive integer or null `max_member_turns`, additive flags and created metadata. Run snapshots exact version/digest.

## Review run

### `review_runs`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `id` | composite identity |
| `primary_document_id` | namespace FK |
| `state` | `queued|preparing|reviewing|validating|completed|failed|cancelled` |
| `progress_percent`, `progress_message_code` | 0..100 + safe localized key/message |
| `execution_snapshot_id` | namespace FK, immutable |
| `created_by`, `created_at`, `started_at`, `finished_at` | audit |
| `cancel_requested_at` | nullable, set once |
| `error_code`, `safe_error_message`, `retryable` | only terminal failed/cancelled as applicable |
| `revision` | CAS for state/cancel/publication |

Allowed transitions:

```text
queued -> preparing -> reviewing -> validating -> completed
queued|preparing|reviewing|validating -> failed
queued|preparing|reviewing|validating -> cancelled
```

Terminal rows never transition. `completed` requires exactly one published report; failed/cancelled require none. Final publication uses `WHERE state='validating' AND cancel_requested_at IS NULL AND revision=:expected` and separately predicates on the current review-execution lease token/revision.

### `review_run_sources`

| Column | Type / constraint |
| --- | --- |
| run namespace + `run_id`, `source_id` | identity; source_id stable skill-facing string |
| `document_id` | namespace FK immutable version |
| `requested_extraction_id` | exact extraction FK resolved at create-run time |
| `role` | exactly one `document`, zero or more `context` |
| `ordinal` | request order |
| `created_at` | immutable request timestamp |

All requested source rows are inserted with the run and are immutable. Preparation never edits the requested document/role/order.

### `review_run_source_preparations`

| Column | Type / constraint |
| --- | --- |
| run namespace + `run_id`, `source_id` | PK/FK requested source; at most one outcome |
| `extraction_id` | exact terminal extraction FK; MUST equal requested source extraction |
| `status` | `available|partial|unavailable` snapshot |
| `fragment_ids_json` | exact ordered extraction fragment IDs used |
| `diagnostics_json` | exact safe source diagnostics snapshot |
| `outcome_digest`, `codec_id` | JCS digest plus `jcs-rfc8785-0.1.4` |
| `prepared_at` | immutable timestamp |

Preparation outcome is set once with `INSERT`; retry may accept an existing row only after recomputing the same `outcome_digest`. A different result is a deterministic conflict and fails the run rather than replacing evidence. The primary target set equals the primary preparation's known `fragment_ids_json`; context never enters target coverage. A partial primary with usable fragments is allowed but forces source-level `code=source_partial, reason=primary_source_partial` in the report in addition to the exact partition of every known target fragment. A primary with no usable fragment fails the run.

### `execution_snapshots`

Immutable row containing exact refs/digests for profile family/version, skill/version/package, model profile/version/config, dialogue policy/version, engine version, locale, parser/settings and safe execution options. It records `codec_id=jcs-rfc8785-0.1.4` for its canonical digest. If and only if a trusted deterministic fixture binding matches, the snapshot also records its operator-configured binding ID/digest plus expected-output resource ID/SHA. The resource is a closed ordinal/quote-occurrence template; dynamic run/source/fragment IDs and offsets are resolved only after exact selector matching and are revalidated as `review-output.v1`. Provider credential and mutable model availability are absent.

### `review_run_executions`

| Column | Type / constraint |
| --- | --- |
| namespace + `id`, `run_id` | execution identity and unique run FK; exactly one per run in feature 003 |
| `state` | `ready|running|waiting_retry|completed|failed|cancelled` |
| `checkpoint` | `queued|sources_prepared|input_built|work_items_complete|output_validated|report_staged|published` |
| `checkpoint_payload_json`, `checkpoint_digest`, `codec_id` | IDs/digests only; no document/model text; JCS codec fixed to `jcs-rfc8785-0.1.4` |
| `attempt_count`, `next_attempt_at` | bounded recovery state |
| `lease_token`, `lease_owner`, `lease_expires_at`, `heartbeat_at` | current worker ownership; null when not running |
| `revision` | CAS version |
| `last_safe_error_code`, `created_at`, `updated_at`, `finished_at` | safe lifecycle metadata |

Run creation inserts this execution row and its execution-specific outbox row in the same transaction. An execution job names this exact `id`; `attempt_count` counts bounded claims/recoveries of that execution, not new review runs. Claim or expired-lease takeover is a CAS that installs a fresh token and increments attempt/revision. Every side-effecting checkpoint and terminal transition predicates on that token and expected revision. Checkpoints are committed only after their referenced durable rows/artifacts are verified, so redelivery resumes at the last checkpoint instead of requiring run state `queued`. A stale worker cannot advance or publish. Exhausted attempts transition execution and non-terminal run to normalized `failed` without a report; a new review requires a new run.

### `review_work_items` and `model_attempts`

Internal durable engine records. Work item has stable UUID, execution/run/source fragment subset, purpose `review|synthesis|repair`, state, attempt count and gap outcome. Model attempt has unique request ID, provider request ID, safe error/result metadata, latency/usage and artifact reference only when policy permits. Work-item terminal output is committed before the enclosing execution checkpoint advances; deterministic IDs make replay idempotent. Raw prompts/responses are not logged or public; storage of raw provider response is disabled by default.

## Idempotency and job handoff

### `idempotency_records`

| Column | Type / constraint |
| --- | --- |
| `organization_id`, `workspace_id`, `operation`, `key` | unique identity |
| `request_digest` | SHA-256 of JCS validated DTO |
| `request_codec_id` | `jcs-rfc8785-0.1.4` |
| `resource_kind`, `resource_id` | original result |
| `created_at`, `expires_at` | minimum create-run/turn window 24h |

Same digest returns current representation of same resource. Different digest conflicts. Record and business resource are one transaction.

### `job_outbox`

| Column | Type / constraint |
| --- | --- |
| namespace + `id` | job UUID |
| `kind` | `execute_review|generate_dialogue_turn` |
| `payload_version` | starts at 1 |
| `payload_json` | attempt-specific IDs/versions only, validated by `job-envelope.v1.schema.json` |
| `business_key` | unique exact execution key: review execution ID or generation attempt ID |
| `state` | `pending|claimed|published|failed` |
| `next_attempt_at`, `claimed_at`, `published_at`, `failed_at` | dispatcher lifecycle |
| `claim_token`, `claimed_by`, `lease_expires_at` | nullable lease; set together only in `claimed` |
| `attempts`, `max_attempts`, `last_safe_error_code` | bounded retry state copied from validated runtime policy |
| `trace_id`, `requested_by` | observability/attribution |

Business execution/attempt and outbox row commit together. A dispatcher claims only due `pending` or expired `claimed` rows with one CAS, replacing `claim_token`; publish/failure writes require the same token. Transient failure clears the claim and computes bounded exponential-backoff `next_attempt_at`. Because queue enqueue and marking `published` cannot be atomic, an uncertain enqueue is retried and duplicate queue delivery is legal. On exhausted/permanent delivery failure the dispatcher atomically marks the outbox `failed` and, iff the referenced execution/attempt is still active, transitions its review run or dialogue generation attempt/turn to normalized `job_dispatch_exhausted`; no business work stays invisibly queued. A failed review requires a new run; explicit dialogue retry creates a new generation attempt/outbox rather than resurrecting a terminal row.

### Queue job state

Procrastinate owns physical queue records and its schema/migrations are managed separately from Alembic business migrations. Application execution IDs, leases and checkpoints—not Procrastinate job status—are the authority for idempotent replay and operator recovery. Queue handlers validate the envelope and claim the named business execution/attempt before any work; a delivery for a different or terminal attempt exits idempotently. Heartbeat, leases, backoff and recovery bounds come from validated `runtime-config.v1.schema.json`, not HTTP DTOs.

## Immutable published report

### `review_reports`

| Column | Type / constraint |
| --- | --- |
| namespace + `id` | UUID |
| `run_id` | unique namespace FK; run must become completed in same transaction |
| `artifact_id` | unique FK canonical bytes |
| `canonical_sha256` | equals artifact SHA |
| `etag` | quoted sha256, unique representation validator |
| `codec_id` | exactly `jcs-rfc8785-0.1.4` |
| `created_at` | immutable |

Runtime GET streams exact artifact bytes. JSONB projections may exist for querying but cannot generate wire bytes.

### `findings`

Namespace + report ID + finding UUID; positive unique ordinal; kind/title/problem/reason/question; priority level/rationale. Append-only. No Human Decision fields.

### `evidence_anchors`

Finding FK, ordinal, run source/document/fragment namespace FKs, exact quote, 0-based half-open `quote_start/quote_end` in fragment text, display locator snapshot. Non-missing finding requires at least one. Validator requires primary document basis across anchors/scopes.

### `finding_scopes`

Finding + primary fragment FK. `missing` requires at least one scope and zero anchors; other kinds may contain scope but require anchors. Scope fragments must be reviewed.

### `coverage_reviewed` and `coverage_gaps`

For every known primary target fragment exactly one row exists in reviewed or a fragment-level gap. Gap fields: source, nullable fragment, canonical-v1 code and safe reason. Source-level gaps use `fragment_id=NULL` and never replace partition rows for known primary targets. They are required for unavailable/partial context and, when primary extraction is partial but has usable fragments, exactly one primary source gap with `code=source_partial, reason=primary_source_partial` is required. In deterministic no-model mode, every known primary target fragment is a fragment-level gap with `code=other, reason=semantic_analysis_not_performed`; no target may be placed in reviewed coverage merely because parsing/orchestration ran.

Report `complete` iff there are no fragment or source gaps. `partial` iff at least one valid gap exists. Thus partial primary extraction and arbitrary-document deterministic no-model execution always publish a `partial` report. Constraints/validator reject overlap, unknown IDs, context target, duplicate membership and status mismatch.

### `report_source_provenance`

Ordered requested sources with role, document ID/name/SHA, status and diagnostics; plus `model_execution` safe metadata and full execution snapshot ref. All requested sources appear exactly once.

## Mutable finding review

### `finding_states`

One row per finding created with report publication:

- `decision_status=unreviewed`, `decision_revision=0`;
- actor/reason/resolution/decided_at null;
- `dialogue_id` references the one-to-one dialogue created eagerly in the same report-publication transaction.

CAS update increments decision revision. Non-unreviewed requires actor/reason/time; reset clears these fields and increments revision. Optionally append-only audit events mirror each accepted change; current projection remains source for HTTP.

### `finding_dialogues`

One per finding, created eagerly with `finding_states` during report publication. Stores exact policy snapshot ref, `revision`, computed state inputs and timestamps. `can_send_message`/`blocked_reason` are projections, not mutable truth; reading a dialogue never creates state.

### `dialogue_turns`

One immutable member message payload with ordinal/configured actor, plus lifecycle state `queued|generating|completed|failed`, created/finished timestamps, nullable published response/error and `active_generation_attempt_id`. A partial unique index over dialogue where state in active set permits only one active turn. Creating a turn also creates its first `generation_attempts` row, points `active_generation_attempt_id` at it and inserts outbox in the same transaction. Lifecycle changes use dialogue/turn CAS; member content and identity never change.

### `generation_attempts`

One or more per turn. Each contains stable `id`, attempt ordinal, state `ready|generating|waiting_retry|completed|failed|discarded`, request ID, safe provider metadata/error, assistant response only for the single published successful attempt, timestamps and usage. It also persists checkpoint `queued|input_built|provider_completed|response_validated|published`, checkpoint digest/codec, bounded `recovery_count`/next retry time, and `lease_token|lease_owner|lease_expires_at|heartbeat_at|revision` with the same CAS rules as review execution. A queue envelope names the exact generation attempt. Expired active work is reclaimed/resumed from the last verified checkpoint; stale owners cannot publish. Retry CAS-transitions the same failed turn back to `queued`, adds a new attempt, switches `active_generation_attempt_id`, and never duplicates the member message.

Decision while a turn is active immediately makes dialogue projection blocked. Existing attempt may finish for audit, but does not reopen dialogue or modify decision.

## Canonicalization and validation invariants

- Report artifact is JCS UTF-8 without BOM/newline; `canonical_sha256` hashes exact bytes; ETag is quoted digest.
- Profile/idempotency/config digests use same JCS implementation after validation; raw document SHA uses exact bytes.
- Duplicate JSON keys and non-finite numbers are invalid before storage.
- RFC 8785/I-JSON domain checks occur before the pinned canonicalizer; unsupported integers, invalid Unicode and values not round-trippable under the codec are rejected rather than silently changed.
- Quote `[start,end)` must equal fragment substring exactly; normalization is only an explicit adapter step, never hidden validator repair.
- Every finding has primary-document basis. Context-only evidence is invalid.
- All report graph references belong to run snapshot and configured namespace.
- `completed` implies exactly one immutable report and all initial finding states; `failed|cancelled` implies no report.
- Dialogue/decision writes cannot update any report/finding/anchor/coverage row or artifact.

## PoC v1 virtual/import identity

Adapter namespace UUID is a fixed implementation constant. IDs are UUIDv5 of `legacy_run_digest + entity_kind + legacy_id`. Same validated legacy directory maps identically on repeat. Mapping table and loss rules are normative in [contracts/poc-v1-mapping.md](contracts/poc-v1-mapping.md).

Legacy `original_path` is discarded. Representable `unreviewed` state becomes the default target FindingState. A non-unreviewed legacy human value is never attributed to the configured actor: the target FindingState stays `unreviewed` and the read-only import view carries `legacy_human_state_unrepresentable`. No adapter operation writes inside the legacy run directory.

## Retention and deletion

Feature 003 does not expose delete/retention API. Operational cleanup covers both abandoned staging objects and promoted-but-unreferenced objects after the configured grace period. Promoted-object deletion requires the shared advisory fencing lock; collector rechecks inside the owning transaction that no artifact metadata/reference points at the exact namespace/store key/digest, deletes while the lock is held, and skips deletion on lock/DB uncertainty. Publisher takes the same lock before promotion and holds it through reference commit, closing the check/delete/publication race. Referenced artifacts are never collector targets. Retention, legal hold, end-user deletion and backup lifecycle require a later product/operations decision; current code must not claim either guaranteed indefinite retention or production deletion compliance.
