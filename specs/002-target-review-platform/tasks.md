# Tasks: целевая платформа предварительного ревью ТЗ

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts](contracts/README.md)

**Execution status**: not started. Этот файл готовит параллельную реализацию, но выполнение начинается только после отдельного поручения пользователя.

**Format**: `[ID] [P?] [Story?] [Owner] Description`. `[P]` означает отсутствие файловой/незавершённой зависимости; `WEB`, `BE` и `SHARED` задают владельца.

## Phase 1 — Reproducible setup

- [ ] T001 [P] [WEB] Создать Vite React TypeScript package в `apps/web/`, зафиксировать Node/npm и exact direct dependencies в `apps/web/package.json` и `package-lock.json`
- [ ] T002 [P] [BE] Создать корневой uv workspace и Python packages из plan в `pyproject.toml`, `apps/{api,worker,cli}/` и `packages/{review-core,review-runtime}/`, зафиксировать `.python-version` и `uv.lock`
- [ ] T003 [P] [SHARED] Добавить единый contract validator для OpenAPI, JSON Schema, examples и semantic invariants в `tools/contracts/` и команду `make contracts` в `Makefile`
- [ ] T004 [P] [SHARED] Добавить CI jobs для `make contracts`, web generation/typecheck/tests и Python lint/tests в `.github/workflows/ci.yml`
- [ ] T005 [SHARED] Зафиксировать CODEOWNERS для `apps/web/`, Python/skills и совместного `contracts/` в `.github/CODEOWNERS`

**Checkpoint**: обе ветки устанавливаются воспроизводимо; contract CI работает без product code.

## Phase 2 — Shared foundations

- [ ] T006 [P] [WEB] Настроить Orval fetch/TanStack Query/MSW generation из `contracts/review-platform/v1/openapi.yaml` в `apps/web/orval.config.ts` и `apps/web/src/api/generated/`
- [ ] T007 [P] [WEB] Создать test shell и MSW server, загружающий canonical HTTP fixtures, в `apps/web/src/test/` и `apps/web/src/mocks/`
- [ ] T008 [P] [BE] Описать domain entities/value objects/state transitions без transport imports в `packages/review-core/src/review_core/domain/`
- [ ] T009 [P] [BE] Описать coarse application interfaces и ports (`ReviewApplication`, repositories, `ArtifactStore`, `JobQueue`, `ModelGateway`, parser, skill runtime) в `packages/review-core/src/review_core/application/` и `ports/`
- [ ] T010 [P] [BE] Создать FastAPI composition root, RFC 9457 mapper и DTO boundary в `apps/api/src/review_api/`
- [ ] T011 [P] [BE] Создать SQLAlchemy metadata/Alembic layout и configured deployment context helper в `packages/review-runtime/src/review_runtime/postgres/`
- [ ] T012 [P] [BE] Создать deterministic fake adapters для repository/artifact/job/model/skill в `packages/review-runtime/src/review_runtime/fakes/`
- [ ] T013 [P] [SHARED] Зафиксировать один synthetic tracer-bullet dataset без клиентских материалов в `tests/fixtures/synthetic-review/`
- [ ] T014 [BE] Добавить contract tests, сравнивающие Pydantic/FastAPI export с canonical OpenAPI, в `tests/contract/test_openapi_compatibility.py`
- [ ] T015 [WEB] Добавить generation guard, запрещающий ручной diff generated client после `npm run generate:api`, в `apps/web/package.json` и CI

**Checkpoint**: web компилируется против MSW; API skeleton и fake application проходят OpenAPI contract; стороны продолжают независимо.

## Phase 3 — User Story 1: проверяемое ревью в web (P1)

**Independent Test**: synthetic document проходит bootstrap → upload → create/poll run → immutable report; partial и failed states отображаются корректно.

### Tests first

- [ ] T016 [P] [US1] [WEB] Написать failing mock E2E основного пути и failed/partial вариантов в `apps/web/e2e/review-flow.spec.ts`
- [ ] T017 [P] [US1] [BE] Написать failing HTTP contract tests upload/run/report/idempotency/cancel в `tests/contract/test_review_http.py`
- [ ] T018 [P] [US1] [BE] Написать failing core tests для state machine, exact target coverage, missing anchors и invalid output в `packages/review-core/tests/test_review_execution.py`

### Backend/core

- [ ] T019 [US1] [BE] Реализовать immutable document intake и PDF/TXT/Markdown parser adapters в `packages/review-runtime/src/review_runtime/documents/`
- [ ] T020 [US1] [BE] Реализовать create/cancel/execute/get run use cases с execution snapshot и idempotency в `packages/review-core/src/review_core/application/reviews.py`
- [ ] T021 [US1] [BE] Реализовать review skill schema boundary и semantic validator в `packages/review-core/src/review_core/review/validation.py`
- [ ] T022 [US1] [BE] Реализовать внутреннее partition/work-unit/synthesis выполнение без утечки work units в HTTP в `packages/review-core/src/review_core/review/engine.py`
- [ ] T023 [US1] [BE] Реализовать bootstrap/documents/profiles/model-profiles/review-runs/report endpoints по OpenAPI в `apps/api/src/review_api/routes/`

### Web

- [ ] T024 [P] [US1] [WEB] Реализовать app/bootstrap/workspace shell без login UI и error boundary в `apps/web/src/app/`
- [ ] T025 [P] [US1] [WEB] Реализовать upload + profile/model selection + create-run форму в `apps/web/src/features/new-review/`
- [ ] T026 [P] [US1] [WEB] Реализовать polling и состояния run/cancel/error в `apps/web/src/features/review-run/`
- [ ] T027 [US1] [WEB] Реализовать immutable report, priority/coverage/limitations и PDF/text anchor navigation в `apps/web/src/features/review-report/`
- [ ] T028 [US1] [SHARED] Запустить один US1 E2E против MSW и fixture FastAPI без условных DTO/веток в web

**Checkpoint**: US1 самостоятельно демонстрирует ревью; реальная модель и durable infrastructure ещё не обязательны.

## Phase 4 — User Story 2: диалог и решение человека (P1)

**Independent Test**: из fixture report аналитик выполняет один асинхронный turn, получает предложение, сохраняет HumanDecision; report body/ETag не меняется.

### Tests first

- [ ] T029 [P] [US2] [WEB] Написать failing MSW/component tests для open/generating/failed/blocked dialogue и stale decision в `apps/web/src/features/finding-dialogue/*.test.tsx`
- [ ] T030 [P] [US2] [BE] Написать failing core concurrency tests для one-active-turn, policy, retry и human-only decision в `packages/review-core/tests/test_finding_dialogue.py`
- [ ] T031 [P] [US2] [BE] Написать failing HTTP tests dialogue/finding-states/decision/idempotency/revision/immutable ETag в `tests/contract/test_dialogue_http.py`

### Backend/core

- [ ] T032 [US2] [BE] Реализовать FindingState/HumanDecision use cases и optimistic concurrency в `packages/review-core/src/review_core/application/findings.py`
- [ ] T033 [US2] [BE] Реализовать dialogue state machine, effective policy и retry generation attempt в `packages/review-core/src/review_core/application/dialogue.py`
- [ ] T034 [US2] [BE] Реализовать dialogue skill schemas/semantic validation и deterministic response adapter в `packages/review-runtime/src/review_runtime/skills/`
- [ ] T035 [US2] [BE] Реализовать finding-states/dialogue/turn/retry/decision endpoints по OpenAPI в `apps/api/src/review_api/routes/findings.py`

### Web

- [ ] T036 [P] [US2] [WEB] Реализовать overlay FindingState поверх immutable report без мутации report cache в `apps/web/src/features/review-report/finding-state.ts`
- [ ] T037 [US2] [WEB] Реализовать dialogue panel, one-turn composer, polling, retry и blocked reasons в `apps/web/src/features/finding-dialogue/`
- [ ] T038 [US2] [WEB] Реализовать confirm/reject/needs-context/reset decision UI с expected revision и конфликтом в `apps/web/src/features/finding-decision/`
- [ ] T039 [US2] [SHARED] Прогнать US2 E2E с real fixture API и доказать идентичный report ETag до/после turn и decision

**Checkpoint**: оба P1-сценария работают через mock и реальный fixture backend.

## Phase 5 — User Story 3: local skill и CLI (P2)

- [ ] T040 [P] [US3] [BE] Написать failing compatibility tests неизменённых feature-001 artifacts в `tests/contract/test_poc_v1_adapter.py`
- [ ] T041 [P] [US3] [BE] Создать целевой declarative skill package с review/dialogue operations в `skills/review-data-spec/`
- [ ] T042 [US3] [BE] Реализовать PoC `schema_version: 1` read adapter без in-place migration в `packages/review-runtime/src/review_runtime/poc_adapter/`
- [ ] T043 [US3] [BE] Реализовать CLI composition root, напрямую вызывающий ReviewApplication без HTTP, в `apps/cli/src/review_cli/`
- [ ] T044 [US3] [BE] Добавить cross-channel contract suite для CLI/skill и fixture HTTP на одном synthetic dataset в `tests/contract/test_channel_semantics.py`

**Checkpoint**: локальный agent/CLI и service сохраняют одну семантику, а старый PoC воспроизводим.

## Phase 6 — User Story 4: durable history в configured workspace (P2)

- [ ] T045 [P] [US4] [BE] Написать failing persistence, immutable-row и configured-workspace namespace tests в `tests/integration/test_review_history.py`
- [ ] T046 [P] [US4] [WEB] Написать failing history/reopen UI tests в `apps/web/src/features/review-history/review-history.test.tsx`
- [ ] T047 [US4] [BE] Реализовать PostgreSQL schema, composite namespace FKs и immutable constraints без RLS/access-control semantics в `packages/review-runtime/migrations/`
- [ ] T048 [US4] [BE] Реализовать provider configured organization/workspace/actor и обычный `404` для namespace mismatch в `packages/review-runtime/src/review_runtime/config/context.py`
- [ ] T049 [US4] [BE] Реализовать cursor lists для documents/runs и durable report/dialogue/decision repositories в `packages/review-runtime/src/review_runtime/postgres/repositories/`
- [ ] T050 [US4] [WEB] Реализовать history и восстановление отчёта/dialogue/decision по bootstrap workspace в `apps/web/src/features/review-history/`

**Checkpoint**: restart/history и namespace consistency проходят на PostgreSQL, не только на fakes.

## Phase 7 — User Story 5: self-hosted поставка (P2)

- [ ] T051 [P] [US5] [BE] Реализовать POSIX ArtifactStore с staging/hash/atomic promote и tests в `packages/review-runtime/src/review_runtime/artifacts/posix.py`
- [ ] T052 [P] [US5] [BE] Реализовать transactional outbox, dispatcher, Procrastinate adapter, heartbeat/stalled recovery и idempotent handlers в `apps/worker/` и migrations
- [ ] T053 [P] [US5] [BE] Реализовать OpenAI-compatible ModelGateway и deterministic provider contract suite в `packages/review-runtime/src/review_runtime/models/`
- [ ] T054 [P] [US5] [BE] Реализовать загрузку operator configuration для одного organization/workspace/actor и проверку запрета auth endpoints/schemes по `deployment-boundary.md` в `apps/api/src/review_api/config.py`
- [ ] T055 [P] [US5] [BE] Добавить optional S3 ArtifactStore и organization/workspace namespace-key tests без production MinIO dependency в `packages/review-runtime/src/review_runtime/artifacts/s3.py`
- [ ] T056 [US5] [BE] Собрать same-origin Docker Compose (proxy, SPA, API, worker, PostgreSQL), health/readiness и persistent volumes в `deploy/compose/`
- [ ] T057 [US5] [SHARED] Прогнать clean-deploy в trusted network, restart persistence, real API Playwright, namespace mismatch, secret scan и outbound-connection allowlist tests в `tests/e2e/` и `tests/security/`

## Phase 8 — Release hardening

- [ ] T058 [P] [SHARED] Документировать operator bootstrap, migrations, queue recovery, явно нерешённые backup/restore policy и model configuration в `docs/operations/`
- [ ] T059 [P] [SHARED] Добавить dependency/image vulnerability scan и проверку отсутствия customer data в public fixtures в CI
- [ ] T060 [SHARED] Выполнить `quickstart.md`, все contract/unit/integration/security/E2E suites и сохранить release evidence без объявления продуктовых гипотез подтверждёнными
- [ ] T061 [SHARED] Зафиксировать следующий контрактный tag и объединить contract → backend → web в порядке из `architecture/parallel-development.md`

## Dependencies and parallel lanes

```text
T001 WEB ──> T006-T007-T015 ──> T016,T024-T027 ──> T029,T036-T038 ──> T046,T050

T002 BE  ──> T008-T012,T014 ──> T017-T023 ───────> T030-T035 ───────> T040-T055

T003-T005 + T013 are shared setup
US1 integration T028 requires web US1 + backend fixture US1
US2 integration T039 requires T028 + web/backend US2
US5 final T057 requires persistence/namespace T047-T049 and deploy T051-T056
```

Коллега может выполнять web lane сразу после T001/T006/T007, пока backend выполняет T002/T008–T014. Первое обязательное совместное ожидание — T028. Любая неожиданная правка OpenAPI/skill schema выполняется отдельным contract PR раньше зависимой реализации.

## Definition of Done

- Все canonical contracts, examples и generated clients синхронны; breaking change не спрятан в v1.
- Mock и real backend используют один web client и один набор DTO.
- Невалидный model/skill output не публикуется; partial всегда содержит gaps.
- Одновременно активен не более чем один turn на finding; модель не меняет HumanDecision.
- Report body/ETag неизменен после dialogue/decision.
- Bootstrap возвращает одного configured actor/workspace; ID вне namespace получает обычный `404`, а OpenAPI не содержит auth schemes или `401/403`.
- Self-hosted restart сохраняет synthetic flow; секреты и customer data отсутствуют в public DTO, fixtures и logs.
- Feature 001 PoC остаётся воспроизводимым.
