# Quickstart: параллельный старт web и backend/skills

Цель — начать с одного проверенного contract baseline и получить ранний tracer bullet без ожидания второй стороны. Команды scaffold ниже выполняются только после отдельного поручения начать реализацию.

## 1. Получить общую точку

После публикации этой feature-ветки:

```bash
git fetch origin --tags
git show review-platform-contract-v1.0.1 --stat
```

Коллега создаёт web-ветку:

```bash
git switch -c codex/web-review-v1 review-platform-contract-v1.0.1
```

Автор продукта в своей рабочей копии создаёт backend/skills-ветку:

```bash
git switch -c codex/backend-review-v1 review-platform-contract-v1.0.1
```

Если нужен UI из существующего прототипа, его коммит переносится в web-ветку после создания от contract tag; прототип не становится источником DTO.

## 2. Проверить baseline до работы

```bash
jq -e . contracts/review-platform/v1/schemas/*.json
jq -e . contracts/review-platform/v1/examples/skill/*.json
jq -e . contracts/review-platform/v1/examples/http/*.json
ruby -e 'require "yaml"; YAML.load_file("contracts/review-platform/v1/openapi.yaml", aliases: true)'
```

Полная проверка дополнительно валидирует OpenAPI, локальные `$ref`, каждый skill example по Draft 2020-12, HTTP examples по component schemas и semantic invariants. Команда CI должна стать единой (`make contracts` либо эквивалент) в setup slice.

## 3. Web lane — коллега

Рабочая область: только `apps/web/`, кроме отдельного contract PR.

1. Создать Vite React TypeScript app на зафиксированных Node/npm версиях.
2. Настроить Orval на `contracts/review-platform/v1/openapi.yaml` с fetch client, TanStack Query hooks и MSW output.
3. Собрать shell маршрутов: bootstrap/workspace, upload/new run, run progress, report, finding dialogue. Login/account/role UI не создаётся.
4. Реализовать tracer bullet исключительно против MSW examples.
5. Обработать состояния `queued|preparing|reviewing|validating|completed|failed|cancelled`, partial coverage, `409`, retryable dialogue error и `can_send_message/blocked_reason`.
6. Не создавать ручные копии server DTO и не читать skill/PоC JSON напрямую.

Минимальный web gate:

```bash
npm ci
npm run generate:api
npm run typecheck
npm test
npm run test:e2e:mock
```

## 4. Backend + skills lane — автор продукта

Рабочая область: `apps/api/`, `apps/worker/`, `apps/cli/`, `packages/`, `skills/`, `deploy/`, кроме отдельного contract PR.

1. Создать uv workspace и composition roots, не импортируя FastAPI/SQLAlchemy в `review-core`.
2. Реализовать OpenAPI skeleton с deterministic fixture: bootstrap → upload → create/poll run → immutable report → finding states → one dialogue turn → decision.
3. Подключить PoC adapter и все пять skill JSON schemas; сначала deterministic fake model.
4. Добавить PostgreSQL models/migrations с namespace constraints, POSIX ArtifactStore, outbox, dispatcher и Procrastinate worker.
5. Добавить OpenAI-compatible ModelGateway и trusted-network deployment configuration только после зелёного fixture tracer bullet. Auth runtime не добавляется.
6. Не передавать web локальный skill ID, provider secret, internal work units или raw model response.

Минимальный backend gate:

```bash
uv sync --locked
uv run pytest tests/contract tests/unit
uv run pytest tests/integration tests/security
uv run review-cli contract-smoke contracts/review-platform/v1/examples/skill
```

## 5. Ранний стык

Backend запускает fixture mode с теми же IDs/examples, которые использует MSW. Web меняет только base URL, а не client и не DTO:

```text
mock:  browser -> MSW generated handlers
real:  browser -> /api/v1 -> FastAPI -> fixture application adapter
```

Обязательный smoke-flow:

```text
bootstrap
  -> upload synthetic-spec.md
  -> create run with Idempotency-Key
  -> poll completed
  -> read immutable report + finding-states
  -> create one dialogue turn with expected_revision
  -> poll assistant response
  -> put HumanDecision
  -> re-read report and assert identical body/ETag
```

Затем fixture application adapter заменяется настоящим Review Engine. HTTP-контракт и web код не меняются.

## 6. Как менять контракт

1. Открыть отдельную ветку и PR в `codex/002-target-review-platform`.
2. Обновить OpenAPI/JSON Schema, все затронутые examples и `CHANGELOG.md`.
3. Указать: compatible additive change или breaking change; breaking change не может оставаться v1.
4. Дождаться contract CI и совместного review.
5. После merge обе реализационные ветки подтягивают один commit; generated client обновляется только из canonical OpenAPI.

Подробный порядок PR и merge — [docs/architecture/parallel-development.md](../../docs/architecture/parallel-development.md).

## 7. Что не считать готовностью продукта

Зелёные contract/E2E тесты подтверждают только техническую согласованность. Полезность замечаний, выигрыш от диалога, время аналитика, переносимость между компаниями и качество на модели заказчика проверяются отдельными экспериментами с заранее согласованными порогами.
