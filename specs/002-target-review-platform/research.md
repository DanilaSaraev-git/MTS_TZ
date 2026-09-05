# Research: стек целевой платформы

Дата проверки: 2026-09-04. Решения ниже относятся к техническому baseline первого целевого среза. Они не являются свидетельством продуктовой ценности или ограничениями конкретного пилота.

## Матрица версий

| Компонент | Baseline | Политика |
| --- | --- | --- |
| Node.js | 24.20.0 LTS | фиксируется `.nvmrc`/CI image; обновления внутри LTS после тестов |
| npm | 12.0.2 | `package-lock.json`, установка через `npm ci` |
| React / react-dom | 19.2.8 | точная версия в lock-файле |
| Vite / plugin-react | 8.2.2 / 6.1.1 | точная версия; только сборка и dev server |
| TypeScript | 6.0.3 | не переходить на 7 до стабилизации compiler API/tooling |
| React Router | 7.18.3 | data routing без server rendering в первом срезе |
| TanStack Query | 5.102.8 | единственный слой server state в web |
| Orval | 8.28.1 | генерация fetch client, query hooks и MSW из OpenAPI |
| MSW | 2.15.0 | mock API для независимой разработки web |
| Python | 3.14.7 | фиксируется `.python-version` и container image |
| uv | 0.12.9 | `uv.lock`, установка через `uv sync --locked`; сам uv pin exact |
| FastAPI | 0.141.1 | HTTP adapter и OpenAPI export |
| Pydantic / settings | 2.13.5 / 2.15.0 | только boundary/config schemas, не общая доменная модель |
| SQLAlchemy / Alembic / psycopg | 2.0.52 / 1.19.1 / 3.3.5 | async application I/O, версионированные миграции |
| Uvicorn | 0.52.4 | ASGI runtime |
| PostgreSQL | 18.6 | major 18, всегда текущий поддерживаемый minor |
| Procrastinate | 3.9.0 | за собственным `JobQueue`; миграции очереди отдельно |
| boto3 | 1.43.88 | только S3 adapter, не доменный API |

Docker-образы фиксируются по версии и digest. Прямые зависимости обновляются ежемесячным PR, security fixes — сразу. Major/minor update обязан пройти миграционный тест, OpenAPI diff, повторную генерацию web client и integration suite.

## R-01. Web: React SPA + TypeScript + Vite

**Decision**: браузерный продукт — React SPA. Vite обслуживает локальную разработку и production build, но не содержит backend. React SPA и `/api` публикуются с одного origin через reverse proxy.

**Rationale**: у продукта отдельные Python API и worker, поэтому server-side React framework дублировал бы backend boundary. SPA достаточно для рабочего интерфейса: загрузка, polling, отчёт, диалог и решения. React выбран пользователем; Vite даёт минимальную сборочную поверхность.

**Supporting libraries**: React Router для маршрутов, TanStack Query для server state, React Hook Form + Zod для локального form state/валидации, Tailwind CSS 4 и доступные headless primitives для UI, PDF.js для отображения PDF и anchors. Redux не добавляется до появления отдельного сложного client-only state.

**Alternatives**:

- Angular пригоден, но его дополнительный framework surface не даёт преимущества команде из двух человек на границе OpenAPI.
- Next.js имеет смысл для отдельного публичного SEO/marketing сайта либо если появится доказанная потребность в SSR; рабочее приложение от этого не зависит.

**Primary sources**: [Node releases](https://nodejs.org/en/about/previous-releases), [React versions](https://react.dev/versions), [Vite releases](https://vite.dev/releases), [TypeScript 7 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/).

## R-02. Backend: Python + FastAPI, общее ядро без HTTP-зависимости

**Decision**: API, worker и CLI являются composition roots вокруг `review-core`. Core содержит предметные типы, use cases и порты и не импортирует FastAPI, SQLAlchemy, Procrastinate или SDK модели. Локальный skill/CLI вызывает application interface напрямую; web — только HTTP adapter.

**Rationale**: PoC уже на Python и использует локальные scripts. Pydantic/FastAPI дают строгую проверку публичных границ, но внутренняя модель остаётся независимой от transport DTO. uv управляет воспроизводимым Python workspace.

**Primary sources**: [Python 3.14.7](https://www.python.org/downloads/release/python-3147/), [uv project locking](https://docs.astral.sh/uv/concepts/projects/sync/), [uv versioning policy](https://docs.astral.sh/uv/reference/policies/versioning/), [FastAPI releases](https://fastapi.tiangolo.com/release-notes/), [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).

## R-03. Контракты: design-first OpenAPI и JSON Schema

**Decision**: `contracts/review-platform/v1/openapi.yaml` — канонический web ↔ backend контракт. Orval генерирует TypeScript client/query hooks/MSW. Backend реализует его Pydantic DTO и экспортирует собственный OpenAPI; CI проверяет семантическое соответствие. Engine ↔ skill использует независимые JSON Schema для операций review и finding dialogue.

**Rationale**: обе стороны могут работать с одного коммита без работающей второй стороны. Общая библиотека Python/TypeScript DTO не нужна и создала бы неявную связанность языков. HTTP, review и dialogue версии изменяются независимо.

**Rules**: RFC 9457 `application/problem+json`, UTC RFC 3339 timestamps, UUID resource IDs, cursor pagination, `Idempotency-Key` на создающих асинхронную работу POST, optimistic concurrency через `expected_revision`. Polling — baseline; SSE/WebSocket не входят в v1.

**Primary sources**: [FastAPI client generation](https://fastapi.tiangolo.com/advanced/generate-clients/), [Orval](https://orval.dev/docs/), [Orval MSW](https://orval.dev/docs/guides/msw/), [MSW](https://mswjs.io/docs/).

## R-04. Данные и namespace: PostgreSQL

**Decision**: PostgreSQL является источником истины для метаданных, состояний, диалогов, решений и outbox. Deployment configuration определяет одну organization и один workspace. Принадлежащие workspace записи хранят их ID, а ограничения и внешние ключи не позволяют связать ресурсы разных namespace. В первом срезе это целостность и provenance, а не механизм доступа.

**Rationale**: явный namespace предотвращает случайное смешивание данных и оставляет миграционный шов для будущей multi-organization версии. RLS, membership и role checks не добавляются, потому что текущий deployment не проверяет личность caller и обслуживает только один доверенный workspace.

**Primary source**: [PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/).

## R-05. Фоновые задания: Procrastinate за портом и transactional outbox

**Decision**: HTTP transaction пишет доменное изменение и `job_outbox` атомарно. Dispatcher публикует outbox в Procrastinate. Delivery — at least once; handler идемпотентен по `job_id`/business key. Worker ведёт heartbeat и восстанавливает stalled jobs. Procrastinate schema мигрируется отдельно от бизнес-схемы.

Минимальный envelope:

```json
{
  "job_id": "uuid",
  "organization_id": "uuid",
  "kind": "execute_review|generate_dialogue_turn",
  "payload_version": 1,
  "payload": {},
  "requested_by": "configured-actor-uuid",
  "idempotency_key": "string",
  "trace_id": "string"
}
```

**Rationale**: PostgreSQL-native queue сохраняет компактный self-hosted deploy без Redis/RabbitMQ. Прямой атомарный enqueue из SQLAlchemy async/psycopg 3 не предполагается; outbox устраняет dual-write. Риск поддержки Procrastinate изолирован собственным `JobQueue`, поэтому возможна замена без изменения use cases.

**Alternatives**: Celery + Redis/RabbitMQ зрелее, но добавляет отдельный обязательный сервис. Перейти на него можно после измеренной нагрузки или требования инфраструктуры заказчика.

**Primary sources**: [Procrastinate releases](https://github.com/procrastinate-org/procrastinate/releases), [external transactions](https://procrastinate.readthedocs.io/en/main/howto/production/external_connection.html), [stalled jobs](https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html), [Celery brokers](https://docs.celeryq.dev/en/main/getting-started/backends-and-brokers/).

## R-06. Артефакты: локальный volume сначала, S3 adapter без bundled MinIO

**Decision**: приложение знает только `ArtifactStore`. Первый single-node self-hosted compose использует durable POSIX volume с атомарной записью и проверкой SHA-256. Для нескольких узлов и возможной будущей SaaS-версии может быть реализован S3 adapter; ключи включают organization/workspace ID, а принадлежность и checksum хранятся в PostgreSQL. Browser получает контент через backend текущего trusted deployment.

**Rationale**: это даёт конкретную минимальную поставку без привязки к одному объектному серверу. Community-репозиторий MinIO архивирован и больше не поддерживается, поэтому он не входит в production baseline.

**Primary source**: [архивированный MinIO Community repository](https://github.com/minio/minio).

## R-07. Граница доступа: без auth в первом срезе

**Decision**: HTTP v1 не содержит login, accounts, membership, roles, permission checks, cookie session, bearer token или CSRF. Operator настраивает одного actor, organization и workspace; любой caller, достигший API, действует как этот actor. Поэтому reverse proxy/API размещаются только в доверенной сети и не рекламируются как безопасные для публичного доступа.

**Rationale**: пользователь явно исключил авторизацию из текущей реализации. Поля actor и organization/workspace сохраняют атрибуцию и namespace, но не создают ложной security-семантики. Любая будущая authentication/multi-organization версия требует отдельной спецификации, threat model и ADR.

**Contract**: [deployment-boundary.md](../../contracts/review-platform/v1/deployment-boundary.md).

## R-08. Модели и документы

**Decision**: собственный `ModelGateway`, без LangChain в core. Первая реальная реализация — OpenAI-compatible HTTP adapter плюс deterministic fake. `GenerationRequest` разделяет trusted instructions и untrusted input и задаёт purpose `review|synthesis|dialogue|repair`. Parser port сохраняет текущий pdfplumber adapter для PDF с текстовым слоем; UTF-8 TXT/Markdown обрабатываются напрямую.

**Rationale**: provider SDK и стратегия chunk/synthesis являются деталями engine. Docling, OCR и vision добавляются только после отдельной технической проверки; текущий выбор pdfplumber не является сравнительным выводом.

## R-09. Проверки

**Decision**: pytest/pytest-asyncio для core/API/worker, integration tests с PostgreSQL, Vitest + Testing Library для web, Playwright для настоящего E2E, MSW для web contract mode. JSON Schema examples и OpenAPI lint/ref checks выполняются в каждом PR. Boundary suite проверяет configured-workspace namespace, prompt-injection handling и отсутствие секретов/клиентских материалов в fixtures/logs; access-control suite отсутствует, поскольку access control не реализуется.

**Rationale**: контрактные тесты создают независимую точку готовности для двух веток; один синтетический tracer bullet проходит mock, real backend и local skill/CLI.

## Нерешённые эксплуатационные параметры

Не установлены размеры production-нагрузки, SLO, retention, backup/restore RPO/RTO, S3 конкретного заказчика, список разрешённых LLM и требования к оркестрации после Docker Compose. Authentication, authorization и multi-organization режим намеренно не проектируются в этом срезе. Эти параметры требуют отдельного решения и не должны маскироваться произвольными числами. Технические лимиты HTTP v1 являются release defaults и настраиваются сервером.
