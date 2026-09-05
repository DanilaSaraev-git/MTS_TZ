# Quickstart: проверка готового backend

Этот guide описывает команды, которые implementation feature 003 обязан сделать рабочими. Он проверяет backend без web и без обязательной внешней модели.

## 1. Prerequisites

- Git checkout feature 003 implementation branch.
- Python 3.14.7 and uv 0.12.9 для local suites.
- Docker Engine/Compose для PostgreSQL, worker и restart E2E.
- Свободный localhost port из `deploy/compose/env.example`.
- Никакие LLM credentials для обязательного flow не нужны.

Проверить, что checkout не содержит незаявленных изменений в защищённых lanes:

```bash
git diff --exit-code review-platform-contract-v1.0.1 -- apps/web MTS implementation/poc specs/001-review-data-spec-poc specs/002-target-review-platform
test "$(readlink CLAUDE.md)" = "AGENTS.md"
```

Contract preflight намеренно может менять только root `contracts/review-platform/v1/`; он проверяется отдельным allowlist/diff task.

## 2. Locked setup and contract gate

```bash
uv sync --locked
make contracts
uv run pytest \
  tests/contract \
  packages/review-core/tests \
  packages/review-runtime/tests \
  apps/cli/tests
```

Expected:

- OpenAPI and all JSON Schemas/examples valid;
- FastAPI export compatible with root v1.0.2;
- no auth schemes, `401` or `403`;
- attempt-specific job envelope and typed PoC import-view schemas valid;
- packaged synthetic runtime config and trusted expected-output template validate with matching resource ID/SHA and exact selector digests; root schema default remains unbound;
- official RFC 8785/JCS vectors pass;
- runtime-policy schema rejects invalid defaults/cross-field lease, retry, budget and trusted-fixture settings; operator settings reject incomplete namespace, seed references, storage and queue configuration;
- deterministic unit/contract flow makes zero network calls.

## 3. Start durable backend

Copy only non-secret example configuration and set deployment-local values. Do not commit the resulting environment file. The shipped example selects `/app/config/runtime-config.synthetic.v1.json`; Compose mounts `deploy/compose/config/` read-only, including `trusted-fixture-output.synthetic.v1.json`. Choosing the unbound root default instead is supported, but then every arbitrary document—including the synthetic one—correctly follows the zero-finding partial path.

```bash
cp deploy/compose/env.example deploy/compose/.env
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml up -d postgres
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml build api worker proxy
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml run --rm worker \
  uv run --frozen review-config-check
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml run --rm api \
  uv run --frozen alembic -c packages/review-runtime/alembic.ini upgrade head
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml run --rm worker \
  uv run --frozen procrastinate --app=review_worker.procrastinate_app schema --apply
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml run --rm worker \
  uv run --frozen procrastinate --app=review_worker.procrastinate_app healthchecks
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml up -d api worker proxy
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml ps
```

Expected health boundary:

- liveness succeeds when process event loop is alive;
- readiness succeeds only when runtime config matches the complete idempotent seed (organization/workspace/actor, system review profile, deterministic model profile, dialogue policy and trusted skill digest), Alembic and Procrastinate schemas are current, `healthchecks` succeeds, and PostgreSQL/artifact store/queue are usable;
- Swagger/API docs open with host internet disabled.

The config check and one-off schema commands run inside the same locked release images and inherit the same Compose environment as API/worker. Config check verifies exact expected-resource bytes/schema and document/profile/skill/parser/engine selectors without printing content. Compose health dependencies must wait for PostgreSQL before schema commands run; host-local Python or an implicitly loaded `.env` is not part of this path.

## 4. Canonical offline smoke

```bash
uv run review-cli api-smoke \
  --base-url http://127.0.0.1:8080/api \
  --primary tests/fixtures/synthetic-review/synthetic-spec.md \
  --context tests/fixtures/synthetic-review/synthetic-rules.md \
  --model-profile deterministic-v1 \
  --assert-offline \
  --evidence-dir .local/evidence/backend-smoke
```

The command performs:

```text
bootstrap
  -> upload primary/context
  -> create run + same-key replay + changed-body conflict
  -> poll legal monotonic states to completed (fast transient states need not all be observed)
  -> capture canonical report bytes and strong ETag
  -> read finding states and eagerly created dialogues
  -> create one dialogue turn + concurrent blocked attempt
  -> poll completed assistant response
  -> write Human Decision + stale revision conflict
  -> re-read byte-identical report and ETag
```

Expected provenance names deterministic adapter, binding ID and expected-output resource digest explicitly. The expected synthetic finding is enabled only because the exact committed document/profile/skill/parser/engine selectors and packaged resource SHA are present in the selected trusted configuration; marker-like text in uploaded data never enables fixture behavior.

Running the same flow with any other document, including one that copies the marker text, yields a valid **partial** report with zero findings, `deterministic_mode_no_semantic_analysis`, and one fragment-level gap for every primary target fragment. A partially extracted primary additionally has one source-level gap `{code: source_partial, fragment_id: null, reason: primary_source_partial}` while every known primary fragment remains exactly once in the reviewed-or-gap partition. A primary with zero usable fragments fails and publishes no report. These invariants are exercised directly by:

```bash
uv run pytest \
  packages/review-runtime/tests/test_document_parsers.py \
  packages/review-core/tests/test_review_validation.py \
  packages/review-core/tests/test_review_engine.py
```

The mandatory Compose profile places API and worker on an internal no-egress network. `--assert-offline` verifies the server-side socket/network boundary, not merely the CLI process; optional model egress is enabled only by the separate explicit profile and exact configured endpoint.

## 5. Restart and duplicate-delivery proof

```bash
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml restart postgres api worker
uv run review-cli verify-evidence \
  --base-url http://127.0.0.1:8080/api \
  --evidence-dir .local/evidence/backend-smoke
uv run pytest tests/e2e/test_restart_persistence.py tests/e2e/test_duplicate_delivery.py
```

Expected:

- document bytes, IDs, run, report bytes/ETag, dialogue order and decision revision equal captured evidence;
- injected duplicate attempt-specific jobs do not create a second report, member message, response or decision;
- stale extraction/execution/outbox leases and stage-kill windows recover without duplicate resources;
- `test_restart_persistence.py` installs newer profile/model/skill/policy versions through its operator/repository fixture and proves old snapshots/reports remain readable;
- outbox backlog drains, Procrastinate `healthchecks` succeeds and readiness returns healthy.

## 6. Direct CLI / skill channel

Run the same semantic fixture without HTTP:

```bash
uv run review-cli review \
  --primary tests/fixtures/synthetic-review/synthetic-spec.md \
  --context tests/fixtures/synthetic-review/synthetic-rules.md \
  --profile base-data-spec \
  --model-profile deterministic-v1 \
  --output .local/evidence/direct-review
uv run review-cli contract-smoke contracts/review-platform/v1/examples/skill
uv run pytest tests/contract/test_channel_semantics.py
```

HTTP and direct results may have different resource UUID/timestamps but must satisfy the same finding/coverage/provenance semantics and deterministic expected content.

## 7. PoC compatibility

Create only a fresh synthetic legacy run and read it through the adapter:

```bash
uv run --project implementation/poc/review-data-spec --frozen --extra test \
  pytest implementation/poc/review-data-spec/tests
uv run --project implementation/poc/review-data-spec --frozen \
  review-data-spec run-demo \
  --output-root .local/poc-v1 \
  --run-id synthetic-compat
uv run review-cli read-poc-v1 .local/poc-v1/synthetic-compat \
  --output .local/evidence/poc-mapping
uv run pytest tests/contract/test_poc_v1_adapter.py
```

Expected: all 12 legacy tests pass; source run hashes before/after are equal; output validates against `contracts/poc-import-view.v1.schema.json`; mapping uses target primary-only coverage and contains no absolute path. Any invalid finding, anchor, quote or location fails the whole mapping and leaves no view/output. A legacy non-`unreviewed` state becomes target `unreviewed` revision 0 plus `legacy_human_state_unrepresentable`; it is never attributed to configured actor.

The adapter suite additionally creates a feature-001 run with a genuinely missing context path. Its successful partial view must carry that source as `status=unavailable`, `sha256=null`, `parser=null`, no fragments and a typed context gap; it must never invent a snapshot digest.

Private MTS artifacts are never required. Any optional private smoke uses a path outside common fixtures and emits no content.

## 8. Full mandatory release gate

```bash
make lint
make contracts
make test-unit
make test-integration
make test-migration
make test-security
make test-e2e
make release-check
```

`make release-check` is an owned Make target. It must rebuild from locked dependencies, scan fixtures/wheels/images/captured safe logs, verify protected path diffs, start a clean isolated Compose project, apply and health-check both business and Procrastinate schemas, run smoke/restart/duplicate-delivery/lease/stage-kill tests, verify default network-level egress denial, and shut down without deleting data outside its isolated test volumes. It also creates a temporary `git archive` source export governed by `.gitattributes`, asserts that `MTS/` is absent, and runs the locked package build plus public unit/contract suites there; a package or runtime import of client files therefore fails the release gate.

## 9. Optional existing local model

This section is opt-in and not a release gate. Do not install a runtime or download weights automatically.

Read-only discovery for a common local endpoint:

```bash
curl --fail --silent --max-time 2 http://127.0.0.1:11434/api/tags
```

If a compatible endpoint/model already exists, configure a server-side OpenAI-compatible profile in the untracked environment and run:

```bash
uv run pytest -m local_model tests/e2e/test_optional_local_model.py
uv run review-cli model-smoke --profile local-opt-in --fixture tests/fixtures/synthetic-review/synthetic-spec.md
```

Expected outcomes:

- available compatible model: response passes the same schema/semantic validators and safe provenance is recorded;
- absent/incompatible/resource-limited model: test reports a safe skip/reason; mandatory deterministic suites remain green;
- a successful smoke proves technical contract compatibility only, not review quality or pilot readiness.

## 10. Safe shutdown

```bash
docker compose --env-file deploy/compose/.env -f deploy/compose/compose.yaml down
```

Default shutdown preserves named durable volumes. Destructive volume removal is never part of normal quickstart or release verification.
