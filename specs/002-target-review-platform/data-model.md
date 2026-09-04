# Data Model: целевая платформа ревью

Статус: design baseline. Имена относятся к доменной модели; конкретные имена таблиц могут отличаться, но инварианты и связи обязаны сохраниться.

## Границы и общие правила

- `Organization` — настроенный namespace deployment; первый срез содержит ровно одну organization и не заявляет межорганизационную изоляцию.
- `Workspace` — единственная настроенная область хранения и работы внутри organization.
- UUID генерируются сервером. Время хранится в UTC и отдаётся как RFC 3339.
- Неизменяемые сущности не обновляются «на месте»: документ, версия профиля, снимок исполнения, отчёт, замечание, anchor и завершённые реплики append-only.
- Изменяемые сущности имеют integer `revision` и обновляются только при совпадении `expected_revision`.
- Межтабличные ссылки workspace-owned сущностей включают `organization_id` и `workspace_id`, чтобы FK не мог связать разные namespace. Это целостность данных, не авторизация.

## Deployment context

### Organization

| Поле | Правило |
| --- | --- |
| `id` | UUID, primary key |
| `slug` | operator-managed label |
| `display_name` | человекочитаемое имя |
| `created_at` | immutable |

### Workspace

| Поле | Правило |
| --- | --- |
| `id` | UUID |
| `organization_id` | обязательная FK в Organization |
| `name` | имя настроенного workspace |
| `created_at` | immutable |

### Actor

`Actor` — настроенная operator'ом подпись `{id, display_name}`. Она записывается в provenance документов, запусков, реплик и решений, но не связана с login или account и не подтверждает личность HTTP caller. Любой caller, достигший API, действует как этот actor. Organization, Workspace и Actor задаются deployment configuration вне HTTP v1.

## Документы и подготовка

### DocumentVersion

Одна неизменяемая загруженная версия. HTTP v1 называет ресурс `Document`, но его ID всегда адресует именно версию, а не изменяемый «последний файл».

| Поле | Правило |
| --- | --- |
| `id`, `organization_id`, `workspace_id` | составной namespace принадлежности |
| `filename`, `media_type`, `size_bytes` | metadata оригинала |
| `sha256` | checksum оригинальных байтов |
| `artifact_key` | непрозрачный внутренний ключ ArtifactStore |
| `extraction_state` | `pending|completed|partial|failed` |
| `created_by`, `created_at` | provenance |

Одинаковый SHA не обязан дедуплицироваться логически. Если байты переиспользуются физически, принадлежность всё равно определяется записью DocumentVersion, не ключом объекта.

### Fragment

Адресуемый неизменяемый фрагмент извлечённого содержания.

| Поле | Правило |
| --- | --- |
| `id` | стабильный внутри DocumentVersion |
| `document_version_id` | обязательная принадлежность |
| `ordinal` | уникален в версии |
| `kind` | `text|table_row` |
| `normalized_text` | данные, никогда не управляющие инструкции |
| `location` | tagged union PDF/text locator |
| `content_sha256` | защищает адресацию при воспроизведении |

PDF locator использует 1-based page и один или несколько normalized rectangles `[left, top, right, bottom]` в координатах 0..1 от левого верхнего угла. Text locator использует 1-based lines и 0-based half-open character offsets в нормализованном тексте источника.

### SourceDiagnostic

Структурированная диагностика `{code, message}`. `code` стабилен для UI/tests; `message` безопасен и не содержит секретов. Источник имеет `available|partial|unavailable`. Основной источник обязан быть `available|partial` с хотя бы одним фрагментом; полностью unavailable primary source завершает run ошибкой. Optional context может быть unavailable и отражается в report gap.

## Версионируемые конфигурации

### ReviewProfile и ReviewProfileVersion

`ReviewProfile` — стабильная логическая идентичность и scope `system|workspace`. `ReviewProfileVersion` immutable, имеет SemVer, role, goal, checks, canonical digest и created metadata. Run ссылается на точную версию.

### ModelProfile и ModelProfileVersion

`ModelProfile` — именованный безопасный alias в workspace/system scope. `ModelProfileVersion` immutable и содержит разрешённые capabilities, ссылку на server-side provider config и `config_sha256`. Секреты хранятся в secret provider и не входят в строку, snapshot или DTO.

### ReviewSkillVersion

Идентифицируется `skill_id + SemVer + package_sha256`. Manifest объявляет операции `review` и `finding_dialogue`, их contract versions, instructions/references и требования к engine/model capabilities. Пакет не содержит сетевых hooks, секретов или organization-specific data.

### FindingDialoguePolicyVersion

Immutable policy, выбранная сервером для run: ID, version, digest, `max_member_turns: positive integer|null` и прочие будущие additive flags. `null` снимает только численный лимит; состояние всё равно может блокировать следующий ход.

## Запуск проверки

### ReviewRun

| Поле | Правило |
| --- | --- |
| `id`, `organization_id`, `workspace_id` | identity и configured namespace |
| `primary_document_version_id` | ровно один основной документ |
| `state` | state machine ниже |
| `progress_percent`, `progress_message` | безопасная projection для polling |
| `execution_snapshot_id` | immutable snapshot |
| `created_by`, `created_at`, `started_at`, `finished_at` | audit |
| `cancel_requested_at` | просьба об отмене, не гарантия мгновенной остановки |
| `error_code`, `safe_error_message`, `retryable` | только для failed/cancelled |

Допустимые переходы:

```text
queued -> preparing -> reviewing -> validating -> completed
queued|preparing|reviewing|validating -> failed
queued|preparing|reviewing|validating -> cancelled, если worker подтвердил отмену
```

Терминальные состояния не меняются. `report_id` появляется только при completed после schema + semantic validation.

### ReviewRunSource

Снимок порядка и роли sources: `primary|context`, DocumentVersion, source ID для skill contract, extraction status и diagnostics. Primary ровно один. `review_scope.target_fragment_ids` по умолчанию равен всем фрагментам primary source; context fragments — supporting и не входят в coverage partition.

### ExecutionSnapshot

Immutable value object:

- profile `{id, version, digest}`;
- skill `{id, version, package_sha256}`;
- model profile `{id, version, config_sha256}`;
- dialogue policy `{id, version, digest}`;
- `engine_version`;
- locale и безопасные execution options.

Snapshot не содержит provider credentials. Фактически использованная provider/model version и usage добавляются в provenance результата.

### IdempotencyRecord

Ключ: `(organization_id, workspace_id, operation, idempotency_key)`. Хранит request body digest, resource ID, status и expiry. Повтор с тем же digest возвращает тот же ресурс; с другим — conflict. Минимальное окно create-review в HTTP v1 — 24 часа.

## Неизменяемый результат

### ReviewReport

Один на completed ReviewRun. Содержит summary, Coverage, limitations и Provenance. Report сериализуется канонически; решения и dialogue не входят. После публикации тело и ETag не меняются.

### Finding

Append-only дочерняя сущность ReviewReport: ordinal, kind, title, problem, reason, question, Priority, anchors и scope. `missing` может не иметь anchor, но обязан иметь непустую проверенную scope; прочие kinds имеют хотя бы один anchor.

### EvidenceAnchor

Связывает Finding с source/document/fragment, точной quote, half-open quote offsets внутри fragment и display locator. Семантический validator подтверждает соответствие quote/offsets и принадлежность run snapshot.

### Coverage и CoverageGap

Coverage без пересечений раскладывает **ровно** `review_scope.target_fragment_ids` на reviewed и unreviewed. Gap может быть:

- fragment-level: `source_id + fragment_id + code + reason`;
- source-level: `source_id + fragment_id=null + code + reason` для partial/unavailable context либо source-wide failure.

`status=complete` только при отсутствии gaps. Неуспешный внутренний work unit после retries создаёт явные fragment gaps и partial report; невалидный итоговый output создаёт failed run без report.

### Provenance

Содержит execution snapshot refs/digests, фактические provider/model/model version, безопасные параметры/usage и все запрошенные sources со status, checksum если известен и diagnostics. Секреты и raw provider response запрещены.

## Изменяемое рассмотрение

### FindingState и HumanDecision

`FindingState` — projection одного Finding: текущий `HumanDecision` и `DialogueSummary`. До первого решения decision имеет `status=unreviewed`, `revision=0`, остальные поля null.

Для `confirmed|rejected|needs_context` обязательны actor, reason и decided_at; resolution необязателен и всегда подтверждается человеком. Сброс в `unreviewed` очищает actor/reason/resolution/decided_at и увеличивает revision.

### FindingDialogue

Ровно один на Finding. Хранит immutable policy snapshot, current revision и ordered turns. Вычисляемые поля HTTP:

- `can_send_message=true` только при отсутствии active turn, незаписанном terminal human decision, поддержке skill/model и разрешении policy;
- иначе `blocked_reason` — `generation_in_progress|turn_limit_reached|human_decision_recorded|dialogue_not_supported|model_unavailable`.

### DialogueTurn и GenerationAttempt

Один DialogueTurn содержит immutable `member_message` (историческое имя поля контракта), настроенного actor, ordinal, created time и state `queued|generating|completed|failed`. Завершённый ответ содержит action `clarify|propose_resolution|escalate`, content, optional ProposedResolution, anchors и provenance.

Повтор HTTP с тем же Idempotency-Key не создаёт второй turn. Retry failed turn не создаёт второе member message: он добавляет `GenerationAttempt`, а опубликованным становится один успешный assistant response. Частичный unique constraint запрещает более одного active turn (`queued|generating`) на dialogue.

## Outbox и jobs

### JobOutbox

| Поле | Правило |
| --- | --- |
| `id`, `organization_id`, `workspace_id` | UUID и configured namespace |
| `kind` | `execute_review|generate_dialogue_turn` |
| `payload_version`, `payload_json` | versioned trusted envelope |
| `idempotency_key` | unique для логической работы |
| `available_at`, `published_at`, `attempts` | dispatcher state |
| `trace_id`, `requested_by` | observability/audit |

Business state и outbox row коммитятся одной SQL transaction. Handler проверяет terminal business state перед side effect и остаётся идемпотентным при повторной доставке.

## Ограничения целостности

- Deployment config создаёт одну Organization, один Workspace и одного Actor; public HTTP не создаёт и не переключает их.
- Composite FK включает `organization_id` и `workspace_id`; запрос к ID вне configured workspace возвращает обычный `404` как namespace mismatch.
- Unique `(organization_id, report_id, ordinal)` для findings, один report на run, один dialogue/state на finding.
- Published report/finding/anchor/coverage rows запрещено UPDATE/DELETE runtime-процессам.
- Секреты хранятся вне public/business schemas. Логи содержат IDs, codes, durations и trace IDs, но не document/message/provider-secret content.

## Retention и удаление

Retention, legal hold, пользовательское удаление и backup RPO/RTO не определены свидетельствами пилота. Первый срез не обещает lifecycle API. До production эти правила должны получить отдельное решение; нельзя реализовать hard delete или бессрочное хранение как скрытое допущение.
