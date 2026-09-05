# Параллельная разработка web и backend

Дата: 2026-09-04. Статус: рабочий GitHub workflow по [HTTP и skill-контрактам v1](../../contracts/review-platform/v1/README.md). Контур первой версии не содержит авторизации: один доверенный deployment обслуживает одно настроенное рабочее пространство.

## Владение изменениями

| Контур | Основной владелец | Каталоги | Вход для работы | Результат |
| --- | --- | --- | --- | --- |
| Web | Коллега | `apps/web/` | `openapi.yaml`, сгенерированный client, MSW и примеры | UI загрузки, запуска, отчёта, диалога и решения |
| Backend и engine | Автор продукта | `apps/api/`, `apps/worker/`, `packages/review-core/` | OpenAPI, skill JSON Schema | HTTP-адаптер, состояние запуска, диалог, валидация, хранение и worker |
| Skills и CLI | Автор продукта | `skills/`, `apps/cli/` | `skill-manifest`, review/dialogue input-output | Версионируемые пакеты навыков, локальный adapter и contract tests |
| Общие контракты | Совместное ревью | `contracts/review-platform/` | Изменение через отдельный PR | Версионированный интерфейс и совместимые примеры |

Каталоги `apps/`, `packages/` и `skills/` — целевая структура; создавать их нужно вместе с первой реализационной задачей. Реализованный PoC остаётся в `implementation/poc/` и подключается через адаптер.

## Общая точка старта

На GitHub публикуются ветка `codex/002-target-review-platform` и аннотированный тег `review-platform-contract-v1.0.1`. Тег указывает на проверенный no-auth baseline, включая зарезервированную папку `apps/web/` и согласованные Spec Kit-артефакты. Обе реализационные ветки создаются от этого тега:

```bash
git fetch origin --tags
git switch -c codex/web-review-v1 review-platform-contract-v1.0.1
git switch -c codex/backend-review-v1 review-platform-contract-v1.0.1
```

Вторую команду выполняет автор backend в своей рабочей копии, а не поверх web-ветки. Существующий `codex/web-review-ui-mockup` остаётся визуальным прототипом; нужные UI-коммиты переносятся в новую web-ветку отдельно, после чего UI подключается к сгенерированному клиенту.

На время первого вертикального среза v1 считается замороженным. Если выявлено необходимое изменение, оно сначала вносится отдельным PR в `codex/002-target-review-platform` с обновлением OpenAPI, JSON Schema, примеров и changelog; затем обе ветки подтягивают один и тот же контрактный коммит. Изменять DTO независимо в web- и backend-ветках нельзя.

Web не ждёт работающий backend: Orval генерирует fetch/TanStack Query client, а MSW отвечает примерами из `contracts/review-platform/v1/examples/http/`. Backend не ждёт UI: HTTP-адаптер проверяется запросами из тех же примеров и JSON Schema навыка. Каноническим design-first источником остаётся `openapi.yaml`; экспортированная FastAPI-схема сравнивается с ним в CI.

## Первый интеграционный срез

```text
GET  /v1/bootstrap
POST /v1/workspaces/{workspaceId}/documents
GET  /v1/workspaces/{workspaceId}/profiles
GET  /v1/workspaces/{workspaceId}/model-profiles
POST /v1/workspaces/{workspaceId}/review-runs
GET  /v1/workspaces/{workspaceId}/review-runs/{runId}
GET  /v1/workspaces/{workspaceId}/review-runs/{runId}/report
GET  /v1/workspaces/{workspaceId}/review-runs/{runId}/finding-states
GET  /v1/workspaces/{workspaceId}/review-runs/{runId}/findings/{findingId}/dialogue
POST /v1/workspaces/{workspaceId}/review-runs/{runId}/findings/{findingId}/dialogue/turns
PUT  /v1/workspaces/{workspaceId}/review-runs/{runId}/findings/{findingId}/decision
```

Web должен корректно показать `queued`, промежуточное состояние, `completed`, `failed`, partial-отчёт, конфликт revision и ход диалога в работе. Backend может сначала использовать фиксированный результат навыка, но обязан пройти тот же state machine и вернуть данные по OpenAPI. Затем fixture заменяется реальным `Review Engine` без изменения web.

## GitHub-flow по шагам

1. **Контракт.** Изменение сначала обсуждается как PR в интеграционную ветку. В PR обязательно приложить совместимые примеры и отметить breaking/non-breaking.
2. **Синхронизация.** После merge контрактного PR оба разработчика одинаково обновляют свою ветку из `codex/002-target-review-platform`. Новый контрактный тег ставится только на проверенный baseline.
3. **Параллельная работа.** Коллега реализует web против MSW. Автор продукта реализует core, skill, API и worker против contract tests. Каждая ветка регулярно проходит собственные тесты без второй части.
4. **Ранний стык.** Как только backend отдаёт fixture через HTTP, web запускает тот же smoke-flow без смены client или DTO. Расхождение считается ошибкой реализации, а не поводом незаметно поменять локальный тип.
5. **Integration PR.** Сначала вливается контракт, затем backend, затем web. Последний PR запускает общий Playwright smoke-flow с настоящим API, worker и PostgreSQL.
6. **Merge в `main`.** Только после зелёных contract, unit, integration и end-to-end проверок. Продуктовые гипотезы этим не подтверждаются: результаты пилота фиксируются отдельно.

Для небольших независимых изменений разрешены обычные PR прямо в соответствующую реализационную ветку. Любая правка публичного HTTP или skill JSON должна пройти через контрактный PR, даже если её обнаружил только один разработчик.

## Правила интеграции

1. Контрактный PR объединяется раньше зависимых реализаций.
2. Web генерирует типы, API client, query hooks и MSW handlers из зафиксированного `openapi.yaml`; ручные копии DTO не считаются источником истины.
3. Backend валидирует границы HTTP и skill runtime; внутренняя модель может отличаться от DTO.
4. Каждая сторона держит один smoke-сценарий: получить bootstrap → загрузить документ → создать запуск → дождаться `completed` → открыть неизменяемый отчёт → провести один ход диалога → сохранить решение.
5. Изменение контракта считается обратно совместимым только если старый consumer и старые примеры продолжают работать.
6. Клиентские материалы не копируются в web fixtures или общие contract tests. Для них используются синтетические данные.
7. В PR не коммитятся generated client-файлы, если команда не зафиксировала обратное; CI всегда заново генерирует их и проверяет отсутствие diff. Lock-файлы, напротив, коммитятся.
8. Pull request не смешивает изменение контракта и крупную реализацию. Допустимо добавить минимальный failing contract test, который объясняет изменение.

## Definition of Done для объединения

- OpenAPI проходит проверку структуры, а все JSON-примеры разбираются и соответствуют своим схемам.
- Export FastAPI семантически совместим с каноническим OpenAPI; Orval generation и TypeScript typecheck проходят без ручных правок.
- Web выполняет smoke-сценарий против mock и реального backend без ветвления по источнику данных.
- Backend принимает повторный `Idempotency-Key`, не создавая второй запуск.
- Невалидный `review-output.v1` переводит запуск в `failed` и не публикует отчёт.
- Решение или ход диалога с устаревшим `expected_revision` возвращает `409 Conflict`; одновременно генерируется не более одного хода замечания.
- Решения и диалог не изменяют байты или ETag опубликованного отчёта.
- Запрос с идентификатором, не принадлежащим настроенному рабочему пространству, получает обычный `404`; это проверка целостности namespace, а не авторизация.
- В web нет экранов логина, управления аккаунтами и ролями; deployment не выставляется в недоверенную публичную сеть.
- Логи и ответы не содержат содержимое секретов LLM-провайдера.
- Старый PoC остаётся воспроизводимым; сохранённые клиентские прогоны ведутся в продуктовом репозитории.
