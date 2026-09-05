# Conformance and test matrix

Every row is release evidence, not a claim of product quality. Exact task IDs are assigned in `tasks.md`.

| Concern | Requirements / criteria | Minimum automated evidence | Task evidence |
| --- | --- | --- | --- |
| Canonical contracts | FR-001, FR-006, SC-001 | complete v1.0.2 delta including list cursor `400`, upload `404`, profile `409`; duplicate-key-safe lint/ref/examples; every existing `400/404/409`; FastAPI export plus exact-pinned isolated `tools/contracts/orval/` generation/typecheck compatibility without `apps/web/` | T002–T005, T025–T028, T057, T115, T117 |
| Backend delivery topology | FR-002, SC-014 | manifests and import/build smoke cover API, worker, direct CLI, shared core, runtime adapters, migrations, deployment and tests; protected-path guard proves no web implementation or `apps/web/` change | T001, T006–T010, T019–T024, T035–T037, T075–T095, T114, T118 |
| Application boundary and clean seed | FR-001, FR-003, FR-040, SC-002, SC-011 | every operationId maps to a coarse use case including bootstrap/download; `runtime-config.v1` policy and typed operator deployment-settings validation; packaged synthetic policy/resource ID/SHA/schema/selectors; exact idempotent org/workspace/actor + deployment system profile/model/policy/skill seed; config/resource drift makes readiness unhealthy | T004–T005, T011, T019–T020, T025, T030–T032, T077–T078, T088–T091, T115 |
| No-auth namespace | FR-004–FR-005, FR-035, SC-008 | no security schemes/401/403; every route foreign workspace/resource `404`; DB cross-namespace FK rejection | T013, T023, T025–T028, T057, T069–T070, T112, T115, T118 |
| Upload, formats and budgets | FR-007–FR-012 | MD/TXT/PDF; zero/whitespace/BOM; type mismatch; byte/page/fragment/context/work budgets; empty page; scanned/encrypted/corrupt; split table; caller mutation; two distinct DocumentVersions for same bytes; stable bytes/hash/ETag; internal extraction `pending|extracting` projects to HTTP `pending` and terminal states one-to-one | T012, T025, T030–T031, T039, T044–T045, T067, T074, T111, T115 |
| Two-phase extraction | FR-008, FR-010, FR-016, FR-038, SC-004, SC-007 | requested snapshot before enqueue; single-writer extraction claim; concurrent wait/reload; crash/lease recovery; append-once prepared-source snapshot; no duplicate fragments/diagnostics | T014, T032, T039, T043, T045, T069, T071, T085, T091, T115 |
| Profiles and immutable snapshots | FR-013–FR-016, SC-005 | deployment-scoped immutable system seed; separate family-head CAS; new/stale/system/foreign/unchanged/concurrent cases; digest stability; publish report, add new config versions, then read identical old snapshot/report bytes/ETag | T015–T016, T031–T032, T053, T070, T073, T075–T080, T115 |
| Canonical JSON | FR-015, FR-026, SC-005 | exact `rfc8785==0.1.4`; official RFC 8785 Appendix B and cyberphone reference vectors; duplicate keys/non-finite rejection; stable UTC timestamp form and strong ETag | T015, T018, T027, T034, T053, T073, T111, T115 |
| Run lifecycle and cancel | FR-017–FR-019 | transition table; cancel each checkpoint; duplicate cancel; deterministic cancel-vs-publication race | T014, T026, T043, T050, T072, T087, T091, T115 |
| Offline deterministic engine | FR-020–FR-021, SC-002, SC-004 | exact document/profile/skill/parser/engine + expected-resource ID/SHA binding and closed ordinal/quote template gives expected finding; missing/drifted resource fails readiness; marker-like arbitrary text cannot select it; arbitrary input yields zero-finding partial, empty reviewed set and `CoverageGap(code=other, reason=semantic_analysis_not_performed)` for every known target; application spy permits declared internal services and sees zero external/unknown attempts; full dialogue history remains untrusted | T004–T005, T011, T020, T029, T033, T038, T041–T043, T049–T053, T089–T091, T113, T115 |
| Report validation | FR-022–FR-027, SC-003–SC-005 | exact reviewed-or-gap partition; partial primary adds `CoverageGap(code=source_partial, fragment_id=null, reason=primary_source_partial)`; invalid IDs/quotes/offsets/locators/scope; stored canonical bytes/ETag immutable | T015, T027, T034, T040, T048, T053, T058, T066, T073, T080, T087, T115 |
| Dialogue and decision | FR-028–FR-033, SC-005–SC-006 | one active turn; full-history prompt separation; same-key replay precedes current-state conflict; retry attempts; policy blocks; stale decision; model cannot mutate decision/report | T054–T066, T070–T073, T081, T085, T091, T115 |
| Durable idempotency/outbox/queue | FR-034–FR-039, SC-006–SC-007 | PostgreSQL same-key race creates one resource/outbox; different digest conflicts; rollback and duplicate delivery; locked-image `uv run --frozen procrastinate --app=<app> schema --apply` then matching `healthchecks`; complete Alembic config/env; clean/current/stale schema and readiness; stalled recovery | T056, T068–T073, T075–T091, T115 |
| POSIX artifacts | FR-037, FR-039, SC-007 | staging file + parent-directory fsync; hash/size; crash before/after promotion; stale staging and promoted-unreferenced cleanup after grace; shared advisory fence closes concurrent collector-vs-publication race; referenced artifact never collected | T067, T073–T074, T080, T087, T091, T111, T115 |
| CLI and PoC | FR-040–FR-043, SC-010 | cross-channel semantic fixture; synthetic PoC golden mapping; real legacy unavailable-context source maps with null SHA/parser and zero fragments while available/partial requires verified metadata; ambiguous quote/location negatives; legacy hashes and unchanged suite | T092–T101, T115, T118 |
| Model adapters | FR-044–FR-045, SC-012 | deterministic conformance; fake OpenAI server errors/timeouts/capabilities; exact optional endpoint allowlist; internal availability matrix maps only fresh `available` to HTTP `available`, all other/missing/expired states to `unavailable`; existing local endpoint smoke/skip | T025, T031, T042, T049, T102–T109, T113, T115 |
| Deployment and content safety | FR-046–FR-049, SC-008–SC-011 | clean Compose internal service network + loopback/trusted proxy bind; application egress deny and explicit optional-model opt-in; local docs; purpose-built content responses and manifest-allowlisted neutral fixtures allowed, but Problem/metadata/queue/log/metric/diagnostic/package/image scans reject non-allowlisted runtime/client content, secrets and paths | T003, T009–T010, T013, T023, T037, T088–T091, T110–T114, T116–T119 |
| Full release | FR-043, FR-050, SC-013–SC-014 | locked install; unit/contract/integration/migration/security/E2E; exact FR/SC evidence; diff guards for `apps/web/`, `MTS/`, feature 001/002; temporary source archive physically excludes `MTS/` and still passes locked package build plus public unit/contract suites | T009–T010, T100, T110–T120 |

## Mandatory synthetic fixtures

- `synthetic-spec.md`: neutral data-flow requirement with three primary fragments; expected finding is enabled only by its exact raw-byte SHA-256 and version in a trusted fixture manifest/config, never by document markers.
- `synthetic-arbitrary.md`: supported content absent from the trusted digest allowlist; expected result is zero findings, partial coverage and one `semantic_analysis_not_performed` gap per primary fragment.
- `synthetic-rules.md`: neutral rule used only as supporting context.
- `synthetic-spec.pdf`: text-layer equivalent plus a small table.
- generated zero-byte, whitespace-only, BOM, empty-page, partial, image-only, encrypted, corrupt, oversize and split-table inputs inside temporary test directories.
- caller-mutation and same-byte/different-name upload cases created in temporary directories.
- `synthetic-duplicate-quote.md`: repeated phrase for occurrence offsets.
- `synthetic-injection.md`: inert prompts and canary secrets treated only as data.
- fresh feature 001 `run-demo` output for PoC mapping; no MTS copy.

The entire public suite and package build MUST pass in a checkout where `MTS/` is absent. Private corpus smoke, if used, is opt-in through an explicit external path and must not print or persist client content.

## E2E proof sequence

```text
bootstrap
  -> verify exact seed and current application/Procrastinate schemas
  -> upload synthetic primary/context
  -> create run (and idempotent replay)
  -> poll completed
  -> save exact report bytes + ETag
  -> read finding states
  -> create one dialogue turn (and blocked concurrent attempt)
  -> poll completed response
  -> put Human Decision (and stale conflict)
  -> re-read identical report bytes + ETag
  -> create newer profile/model/skill/policy versions
  -> re-read identical old snapshot/report bytes + ETag
  -> restart API/worker/PostgreSQL
  -> re-read document/run/report/dialogue/decision
  -> redaction and no-egress assertions
```

The suite also runs an arbitrary non-allowlisted document and proves the per-fragment partial gaps, races two workers on one pending extraction, races two same-key callers in PostgreSQL, and exercises clean/current/stale Procrastinate schemas. Duplicate review and dialogue jobs are injected after restart; logical resource counts and IDs must remain unchanged.
