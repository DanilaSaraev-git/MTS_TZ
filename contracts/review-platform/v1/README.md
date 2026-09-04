# Review Platform contracts v1

Статус: проверяемый baseline `v1.0.0` для параллельной реализации web, backend и навыков. Контракты описывают выбранные интерфейсы первого целевого среза, но не подтверждают продуктовую ценность.

## Web ↔ Backend

[openapi.yaml](openapi.yaml) — design-first источник истины для HTTP v1. [Swagger UI](swagger/README.md) даёт визуальную интерактивную документацию поверх этого же файла без копирования схемы. Web работает только с ресурсами HTTP и не читает файлы PoC или `review-output.v1` напрямую. [deployment-boundary.md](deployment-boundary.md) фиксирует границу доверенного deployment: один настроенный actor, одна organization и один workspace.

Основной frontend-flow:

1. `GET /v1/bootstrap` — получить настроенного actor, workspace и публичные лимиты.
2. `POST /v1/workspaces/{workspaceId}/documents` — загрузить основной документ или контекст.
3. `GET /profiles` и `GET /model-profiles` — выбрать точные версии настроек проверки.
4. `POST /review-runs` с `Idempotency-Key` — создать фоновый запуск.
5. `GET /review-runs/{runId}` — polling до терминального состояния.
6. `GET /review-runs/{runId}/report` — получить валидный неизменяемый отчёт.
7. `GET /review-runs/{runId}/finding-states` — наложить изменяемые решения и состояние диалога.
8. `GET /findings/{findingId}/dialogue` и `POST /dialogue/turns` — провести один асинхронный ход; следующий ход доступен только при `can_send_message=true`.
9. `PUT /findings/{findingId}/decision` — сохранить решение человека с optimistic concurrency.

Отчёт не содержит `HumanDecision` и не меняет тело/ETag после диалога. Ответ навыка может вернуть `Proposed Resolution`, но его принятие всегда является отдельным human action.

Примеры для mock и smoke-тестов находятся в [examples/http](examples/http/).

## Engine ↔ Review Skill

- [review-input.schema.json](schemas/review-input.schema.json) — неизменяемый снимок источников, фрагментов и профиля, передаваемый навыку.
- [review-output.schema.json](schemas/review-output.schema.json) — только смысловой результат навыка. Модель не устанавливает решение человека и не публикует HTTP-отчёт.
- [finding-dialogue-input.schema.json](schemas/finding-dialogue-input.schema.json) и [finding-dialogue-output.schema.json](schemas/finding-dialogue-output.schema.json) — один пользовательский ход по неизменяемому замечанию и только ответ навыка.
- [skill-manifest.schema.json](schemas/skill-manifest.schema.json) — декларативный пакет навыка с операциями `review` и `finding_dialogue`, без исполняемого сетевого кода.
- [model-adapter.md](model-adapter.md) — внутренний порт сменяемых LLM.

Проверка JSON Schema не заменяет семантическую валидацию. Движок дополнительно проверяет существование source/fragment ID, вхождение цитаты и offsets, точное разбиение `review_scope.target_fragment_ids`, правила `missing`, принадлежность истории конкретному finding и отсутствие инструкций из входных материалов в управляющем контексте.

`review_scope.target_fragment_ids` содержит объект проверки. По умолчанию это все фрагменты основного документа; fragments контекста являются supporting material. Большие документы движок делит на внутренние work units, но work units не входят ни в HTTP, ни в итоговый skill output.

Недоступный основной документ завершает run ошибкой. Optional context со статусом `partial|unavailable` и исчерпанный work item отражаются source/fragment gaps и дают partial report; никакой источник не исчезает из provenance молча.

Примеры находятся в [examples/skill](examples/skill/). Они синтетические и не содержат материалы MTS.

## Версионирование

- HTTP использует путь `/v1`. Добавление необязательного поля или нового endpoint допустимо в v1 и отмечается minor/patch baseline tag; удаление, новое обязательное поле и изменение смысла требуют `/v2`.
- Skill-контракты имеют строковые версии `review-input.v1`, `review-output.v1`, `finding-dialogue-input.v1` и `finding-dialogue-output.v1`. Они меняются независимо от HTTP.
- Manifest имеет версию `review-skill.v1`; версия самого навыка задаётся SemVer.
- Сохранённые артефакты PoC с `schema_version: 1` не меняются. Их читает отдельный адаптер.

Любое изменение baseline обновляет схемы, OpenAPI, примеры и [CHANGELOG.md](CHANGELOG.md) в одном коммите.

## Integration gate

- OpenAPI lint и локальные `$ref` проходят; backend export не содержит несовместимого diff.
- Orval заново генерирует client/query hooks/MSW без ручной правки generated DTO.
- Все пять skill examples проходят Draft 2020-12 schemas и semantic invariants.
- HTTP examples проходят соответствующие component schemas.
- Общий synthetic tracer bullet выполняется через MSW, real HTTP и local skill/CLI.
- Configured-workspace namespace mismatch, stale revision, duplicate idempotency и immutable-report cases являются обязательными негативными тестами.

GitHub-порядок, владельцы каталогов и merge sequence описаны в [parallel-development.md](../../../architecture/parallel-development.md).
