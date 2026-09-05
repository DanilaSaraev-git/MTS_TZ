# Feature 003 implementation rules and contract conformance

Это не самостоятельный и не альтернативный публичный API. Единственный canonical HTTP/skill contract находится в `contracts/review-platform/v1`; документы ниже только фиксируют однозначную реализационную семантику и тестовые проверки для feature 003, не копируя публичные схемы feature 002.

| Boundary | Normative artifact |
| --- | --- |
| Web/client ↔ backend | root [OpenAPI v1](../../../contracts/review-platform/v1/openapi.yaml) + [additive clarifications](http-v1-clarifications.md) |
| API/worker/CLI ↔ application | [runtime semantics](runtime-semantics.md) |
| Exact bytes, digests, quotes and coverage | [canonicalization](canonicalization.md) |
| Feature 001 PoC ↔ target model | [PoC v1 mapping](poc-v1-mapping.md) + typed [PoC import view schema](poc-import-view.v1.schema.json) |
| Operator config ↔ runtime | [runtime configuration schema](runtime-config.v1.schema.json) + semantic cross-field validation |
| Trusted deterministic smoke config ↔ fixture executor | [expected-output template schema](trusted-fixture-expected-output.v1.schema.json), selected only by the exact runtime-config digest binding |
| Durable queue handoff | [attempt-specific job envelope schema](job-envelope.v1.schema.json), enforced by T004/T005 before producers are implemented |
| Requirement/operation ↔ automated evidence | [test matrix](test-matrix.md) |

Canonical external schema sources remain:

- `contracts/review-platform/v1/openapi.yaml` for HTTP;
- `contracts/review-platform/v1/schemas/*.json` for review/dialogue/manifest;
- `contracts/review-platform/v1/model-adapter.md` for the model port;
- `contracts/review-platform/v1/deployment-boundary.md` for configured single-workspace no-auth semantics.

Implementation MUST NOT create a parallel HTTP DTO or edit `specs/002-target-review-platform/`. T002 first records a failing additive-v1.0.2 conformance test; only T003 then updates root contracts/examples/changelog in one isolated contract commit before dependent route code.

Before any outbox producer exists, T004/T005 require every queue envelope to identify one exact attempt through its kind-specific payload. `execute_review` carries `review_run_id + review_execution_id`; `generate_dialogue_turn` carries `dialogue_id + dialogue_turn_id + generation_attempt_id`. A stale or duplicate delivery may inspect that exact attempt and exit idempotently, but MUST NOT select a newer pending attempt implicitly.

`read-poc-v1` has no persistence side effect on either legacy input or backend stores. Success is exactly one schema-valid `poc-import-view.v1`; an invalid finding/anchor fails the whole mapping, while unrepresentable legacy human state becomes default target `unreviewed` plus a typed diagnostic and is never attributed to configured actor.

Feature 003 fixes the remaining implementation choices as follows:

- report publication eagerly creates exactly one FindingState and one Dialogue for every finding;
- deterministic expected findings are selected only by a trusted runtime-config binding over exact input/profile/skill/parser digests; uploaded marker text is never a selector;
- the default deterministic result for any unbound document is partial, contains no findings, places every primary target fragment in an explicit gap and declares that semantic analysis was not performed;
- a partially extracted primary with usable fragments adds source-level `{code: source_partial, fragment_id: null, reason: primary_source_partial}` while still partitioning every known primary fragment; zero usable primary fragments fail without a report;
- mandatory Compose runs API/worker without external egress; an optional provider uses a separately enabled route restricted to the exact configured endpoint.
