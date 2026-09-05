# Feature Specification: Рабочий backend платформы ревью

**Feature Branch**: `codex/003-backend-implementation`

**Created**: 2026-09-05

**Status**: Ready for implementation

**Input**: реализовать и протестировать полностью рабочий backend целевой Review Platform по baseline feature 002. Web разрабатывается отдельно. Обязательный результат не зависит от платной или внешней модели: воспроизводимый deterministic-режим проводит весь сценарий и честно отражает отсутствие смыслового LLM-анализа через partial coverage. Бесплатная локальная модель подключается только как необязательное расширение, если доступна без ключей и затрат.

Эта спецификация определяет новый реализационный feature. [Feature 002](../002-target-review-platform/spec.md), [целевая архитектура](../../architecture/target-product.md) и [HTTP/skill contracts v1](../../contracts/review-platform/v1/README.md) остаются входным продуктовым и контрактным baseline, а не журналом выполнения backend-задач. Техническая готовность backend не подтверждает полезность замечаний, экономию, спрос, переносимость между компаниями или результаты пилота.

## User Scenarios & Testing

### User Story 1 — Выполнить полный review-flow без внешней модели (Priority: P1)

Клиент публичного API загружает поддерживаемый документ, выбирает доступные профили, создаёт проверку, наблюдает её состояния и получает валидный неизменяемый отчёт. Чистая установка обязана выполнять этот путь без API-ключей и платных сервисов; deterministic composition соединяется только с объявленными internal Compose dependencies и не делает external egress attempts.

**Why this priority**: это минимальный рабочий backend и независимая точка интеграции для web. Без него остальные возможности не образуют проверяемый продуктовый сценарий.

**Independent Test**: в чистой установке пройти canonical synthetic flow `bootstrap → upload → create run → poll → report` через публичный API и получить отчёт, прошедший структурную и семантическую валидацию.

**Acceptance Scenarios**:

1. **Given** чистая установка, валидная `runtime-config.v1` policy и валидные operator deployment settings, **When** выполнены schema initialization и idempotent bootstrap, **Then** сохранены точные configured organization/workspace/actor, deployment-scoped system review profile, dialogue policy, deterministic model profile и skill version/package digest; повторный bootstrap подтверждает те же IDs/versions/digests либо делает readiness unhealthy при drift.
2. **Given** поддерживаемый synthetic fixture, exact document/profile/skill/parser/engine selectors которого разрешены versioned trusted fixture config и ссылаются на schema-valid packaged expected-output resource с совпадающим SHA-256, **When** клиент загружает его и запускает проверку, **Then** запуск проходит согласованные состояния и публикует неизменяемый отчёт с ожидаемыми замечаниями, охватом, ограничениями и происхождением; совпадение пользовательского текста с test-фразой само по себе этот режим не включает.
3. **Given** любой другой поддерживаемый документ в deterministic-режиме, **When** его digest отсутствует в trusted fixture config, **Then** backend публикует zero-finding partial report: каждый известный target fragment primary document представлен отдельным `CoverageGap(code=other, reason=semantic_analysis_not_performed)`, limitation явно называет отсутствие смыслового анализа, а reviewed set пуст.
4. **Given** повтор запроса с тем же ключом идемпотентности и тем же телом, **When** запрос приходит повторно, **Then** возвращается тот же ресурс; другой payload с тем же ключом получает конфликт и не создаёт второй ресурс.
5. **Given** документ содержит текст, похожий на команды агенту, **When** выполняется проверка, **Then** этот текст остаётся недоверенными данными и не меняет правила выполнения.
6. **Given** результат внутреннего анализа нарушает структуру, ссылки, цитаты или правила охвата, **When** завершается валидация, **Then** запуск получает безопасную ошибку, а отчёт не публикуется.
7. **Given** запрос содержит идентификатор вне настроенного workspace, **When** вызывается любая workspace-scoped операция, **Then** backend отвечает обычным `404`, не раскрывая access-control семантику.

---

### User Story 2 — Обсудить замечание и сохранить решение человека (Priority: P1)

Клиент открывает состояние замечания, отправляет один последовательный ход диалога, получает проверенный ответ и сохраняет отдельное решение человека. Ни диалог, ни решение не меняют опубликованный отчёт.

**Why this priority**: review и диалог выбраны как единый первый целевой срез; решение всегда должно оставаться за человеком.

**Independent Test**: из canonical synthetic report создать ход, дождаться ответа, сохранить решение и доказать, что тело и strong ETag отчёта остались прежними.

**Acceptance Scenarios**:

1. **Given** существующее замечание, **When** клиент открывает dialogue, **Then** история однозначно связана с run, report и finding и восстанавливается в исходном порядке.
2. **Given** `can_send_message=true`, **When** принят один ход, **Then** до его завершения второй ход не принимается, а клиент видит машинно различимую причину блокировки.
3. **Given** повтор того же хода с тем же ключом и телом, **When** запрос повторяется, **Then** второй turn не создаётся; другой payload с тем же ключом получает конфликт.
4. **Given** устаревшая ожидаемая ревизия диалога или решения, **When** приходит изменение, **Then** прежние данные не перезаписываются, а клиент получает конфликт версий.
5. **Given** backend предлагает объяснение или возможное решение, **When** ответ опубликован, **Then** он остаётся предложением системы и не изменяет Human Decision автоматически.
6. **Given** решение сохранено либо effective policy запрещает продолжение, **When** клиент читает dialogue, **Then** `can_send_message=false` и `blocked_reason` согласованы с фактическим состоянием.

---

### User Story 3 — Сохранить историю и пережить перезапуск (Priority: P1)

Оператор запускает API и worker в доверенном self-hosted контуре. Документы, состояния работ, отчёты, диалоги и решения сохраняются после штатного перезапуска; повторная доставка работы не создаёт дубли.

**Why this priority**: backend считается полностью рабочим только при долговечном хранении и восстановимом фоновом выполнении, а не как одноразовый in-memory mock.

**Independent Test**: выполнить synthetic flow, перезапустить API, worker и хранилище состояния, повторно доставить одно задание и убедиться, что история восстановлена, а опубликованные ресурсы и число логических работ не изменились.

**Acceptance Scenarios**:

1. **Given** принятая загрузка, **When** процесс прерывается до либо после atomic promotion, но до регистрации ресурса, **Then** staging либо promoted-but-unreferenced object не становится доступным документом и после grace period безопасно очищается; publisher и collector сериализованы общим fencing lock, поэтому referenced object не удаляется даже при конкурентной публикации.
2. **Given** созданный run или dialogue turn, **When** процесс перезапускается до публикации задания, **Then** сохранённая работа в итоге выполняется без потери бизнес-состояния.
3. **Given** одно задание доставлено несколько раз, **When** worker обрабатывает повторы, **Then** side effects выполняются логически один раз, а терминальный ресурс не дублируется.
4. **Given** активный run, **When** принята отмена, **Then** worker проверяет её между ограниченными этапами, прекращает дальнейшие внешние вызовы и никогда не публикует отчёт после подтверждённой отмены.
5. **Given** завершённые run, report, dialogue и decision, **When** все процессы штатно перезапущены, **Then** клиент читает те же ресурсы в том же workspace, а неизменяемые bytes и ETag совпадают.
6. **Given** потерявшая heartbeat работа, **When** оператор запускает восстановление, **Then** работа безопасно возвращается в обработку либо завершается диагностируемой ошибкой без скрытого зависания.

---

### User Story 4 — Использовать то же ядро через CLI и читать PoC (Priority: P2)

Оператор или AI-агент запускает проверку локально через CLI без HTTP и получает тот же доменный результат. Сохранённые артефакты feature 001 читаются отдельным адаптером без изменения исходных файлов.

**Why this priority**: это сохраняет переносимый канал PoC и доказывает, что смысловой процесс не привязан к FastAPI или браузеру.

**Independent Test**: выполнить один synthetic dataset через CLI и HTTP, проверить одинаковые обязательные понятия и семантические инварианты, затем прочитать сохранённый PoC v1 и доказать его побайтовую неизменность.

**Acceptance Scenarios**:

1. **Given** те же immutable inputs и execution snapshot, **When** workflow запущен через CLI, **Then** он использует те же правила подготовки, валидации, охвата и происхождения, что HTTP/worker flow.
2. **Given** сохранённый PoC с `schema_version: 1`, **When** его читает adapter, **Then** идентификаторы, привязки и статусы преобразуются в целевые понятия без in-place migration и без раскрытия локальных абсолютных путей.
3. **Given** portable skill package и общие fixtures, **When** выполняется проверка состава, **Then** в них нет документов, правил, путей или секретов конкретного клиента.

---

### User Story 5 — Необязательно подключить бесплатную локальную модель (Priority: P3)

Оператор может заменить deterministic-профиль на совместимую локальную модель, доступную без платного аккаунта и API-ключа. Отсутствие такой модели не делает backend неготовым.

**Why this priority**: реальная локальная генерация полезна для демонстрации, но её доступность, размер и качество зависят от машины и не должны блокировать воспроизводимую поставку.

**Independent Test**: если на машине уже доступен поддерживаемый локальный endpoint и подходящая модель, выполнить optional smoke через тот же model profile boundary; иначе test корректно помечается skipped с диагностикой, а все обязательные suites остаются зелёными.

**Acceptance Scenarios**:

1. **Given** локальный совместимый endpoint явно включён оператором, **When** профиль проходит capability check, **Then** review/dialogue используют его без изменения публичного или skill-контракта.
2. **Given** endpoint отсутствует, модель не установлена либо не укладывается в ресурсы машины, **When** запускаются обязательные проверки, **Then** они используют deterministic-профиль и не скачивают большие модели автоматически.
3. **Given** локальная модель вернула невалидный, слишком длинный или заблокированный ответ, **When** engine исчерпал допустимые попытки, **Then** применяются те же правила partial/failed и безопасной диагностики, что для любого другого provider.

### Edge Cases

- Zero-byte upload и неподдерживаемый либо не совпадающий с bytes media type отклоняются до resource-intensive work; whitespace-only TXT/MD, повреждённый/зашифрованный PDF и PDF без text layer сохраняют bytes, но primary завершается extraction failure без report, а optional context становится явным unavailable gap.
- Один leading UTF-8 BOM удаляется только из normalized extracted text с зафиксированным parser/settings digest; raw artifact остаётся побайтово исходным. Пустые PDF pages сохраняют адресуемые границы/diagnostic, а table, split между страницами, остаётся набором per-page row fragments и не объединяется без доказуемой continuity.
- Мутация caller-файла после завершения upload не меняет уже сохранённые bytes/hash. Две загрузки одинаковых bytes, включая разные filenames, создают две самостоятельные DocumentVersion с разными IDs/provenance; физическая дедупликация storage, если появится, не меняет эту публичную семантику.
- Один logical document состоит из нескольких секций либо один PDF содержит несколько логических ТЗ; v1 всё равно считает одной review-unit одну загруженную версию и явно сохраняет границы фрагментов.
- Недоступный или частично извлечённый context source; полностью недоступный primary source; conflicting context rules.
- Byte limit применяется до/во время streaming upload и даёт `413`; invalid cursor/context-count даёт `400`. Page/fragment/work-item budgets проверяются в `preparing/reviewing`: превышение для primary без usable target завершает run ошибкой, а частично обработанный primary или optional context даёт явные source/fragment gaps; ни один известный target fragment не исчезает из coverage молча.
- Page text и table rows дублируют содержание; одна quote встречается несколько раз; Unicode и whitespace отличаются; locator выходит за границы страницы или текста.
- Нулевое число findings при полном coverage; `missing` finding без цитаты; present-text finding без anchor; anchor только на context без primary-document основания.
- Повтор idempotency key после timeout; тот же key с другим payload; параллельная отмена и завершение; повторная отмена терминального run.
- Отмена принята перед model call, между work items, перед synthesis, во время validation или непосредственно перед atomic publication.
- Два run/worker одновременно требуют extraction одного pending document; ровно один claim владеет записью результата, второй ждёт либо перечитывает terminal result, а stale claim после crash восстанавливается без duplicate fragments/diagnostics.
- Два worker одновременно получают одну работу; процесс падает после side effect, но до acknowledgement; outbox опубликован повторно; heartbeat устарел; два caller одновременно резервируют одинаковый Idempotency-Key.
- Два caller одновременно создают dialogue turn, retry failed turn или обновляют Human Decision.
- Профиль supersedes несуществующую, системную, чужую, не последнюю либо уже superseded версию; canonical content новой версии совпадает с текущей.
- Конфигурация содержит неверный workspace/actor, недоступное хранилище, незапущенные миграции или нездоровую очередь.
- Документ, сообщение либо provider response содержит prompt injection, секрет, абсолютный путь или управляющие последовательности для логов.
- Необязательная локальная модель отсутствует, не отвечает, не поддерживает structured output, превышает контекст или требует непредусмотренной загрузки.

## Requirements

### Functional Requirements

#### Публичная граница и чистый запуск

- **FR-001**: backend MUST реализовать все backend-owned операции canonical HTTP v1 и skill contracts, перечисленные в feature 002, без несовместимых обязательных полей или скрытых альтернативных DTO.
- **FR-002**: реализация MUST включать API, worker, direct CLI, общее предметное ядро, runtime adapters, migration/deployment assets и tests; реализация web UI и изменение `apps/web/` MUST оставаться вне scope.
- **FR-003**: чистая установка MUST валидировать versioned `runtime-config.v1` policy и typed operator deployment settings, применить application и Procrastinate schemas и идемпотентно seed/check точные organization/workspace/actor, deployment-scoped immutable system review profile, dialogue policy version, deterministic model profile и skill version/package digest. Если выбрана trusted synthetic binding, startup/readiness MUST также проверить её exact document/profile/skill/parser/engine selectors, expected-output resource ID/SHA и закрытую schema; mismatch MUST делать readiness unhealthy, а не молча переписывать versioned rows.
- **FR-004**: HTTP v1 MUST NOT содержать login, accounts, membership, roles, permissions, cookie/bearer sessions, CSRF или access-control responses; deployment MUST явно ограничиваться доверенной сетью.
- **FR-005**: каждая workspace-scoped операция MUST проверять настроенный namespace; другой workspace либо связанный resource из другого namespace MUST возвращать обычный `404`.
- **FR-006**: ошибки boundary MUST использовать согласованный Problem Details payload; invalid input, conflict, unavailable report, payload limit и not found MUST быть машинно различимы и не раскрывать внутренние исключения.

#### Документы и подготовка

- **FR-007**: upload MUST сохранять неизменяемые оригинальные bytes, вычисленный SHA-256, безопасные metadata и actor provenance до возврата созданного Document; изменение caller-файла после upload не влияет на сохранённый artifact, а повторная загрузка тех же bytes создаёт отдельную логическую DocumentVersion.
- **FR-008**: успешный upload MUST возвращать `extraction_state=pending`; внутренние `document_extractions.pending|extracting` MUST проецироваться только в canonical HTTP `pending`, а terminal `completed|partial|failed` — одноимённо. Create run фиксирует requested source identities/order/roles отдельно от ещё неизвестного extraction outcome. Во время `preparing` extraction MUST иметь single-writer claim/CAS, идемпотентное crash recovery и одинаковые fragment identities/diagnostics для тех же bytes/parser/settings; после terminal extraction run атомарно фиксирует append-once prepared-source status, fragment IDs и diagnostics до `reviewing`.
- **FR-009**: обязательные parsers MUST поддерживать PDF с текстовым слоем, Markdown и UTF-8 TXT; raw UTF-8 BOM MUST сохраняться в artifact и сниматься только как versioned text normalization, empty pages/split tables MUST давать стабильные boundaries/diagnostics без недоказанного merge. OCR, DOCX, vision и внешние страницы MUST не включаться неявно.
- **FR-010**: extraction MUST сохранять адресуемые text/table fragments, source status и безопасные diagnostics; primary без единого usable fragment MUST завершать run ошибкой. Partial primary с usable fragments MUST давать source-level gap `code=source_partial`, `fragment_id=null`, `reason=primary_source_partial` плюс exact partition всех известных target fragments; partial/unavailable context MUST отражаться явным gap.
- **FR-011**: document bytes, evidence quotes, member messages и assistant content MAY присутствовать только в purpose-built canonical content/report/dialogue responses, где этого требует HTTP v1. Absolute paths, provider secrets и raw provider responses MUST отсутствовать во всех публичных DTO; document/message content дополнительно MUST отсутствовать в Problem Details, metadata-only DTO, queue payload, logs, metrics и безопасных diagnostics.
- **FR-012**: byte limit MUST применяться streaming и давать `413`; malformed cursor и context-count limit MUST давать `400`; page/fragment/work budgets MUST завершать unusable primary ошибкой либо давать явные source/fragment gaps при частичном usable результате. Ни один limit MUST не приводить к молчаливому усечению.

#### Профили и снимок исполнения

- **FR-013**: list profiles MUST возвращать immutable system и workspace versions, а run MUST ссылаться на точные version/digest каждого выбранного профиля. Default system profile MUST быть deployment-scoped release seed, видимым configured workspace, но не workspace-owned либо изменяемым через public POST.
- **FR-014**: создание workspace profile без `supersedes` MUST создавать новую family с server-assigned version `1.0.0`; валидный `supersedes` текущего mutable family-head pointer MUST создавать следующую immutable patch-version с тем же logical ID и CAS-обновлять отдельный head pointer, не меняя прежнюю version row. Missing либо foreign-workspace reference MUST выглядеть как обычный `404`; ссылка на видимый immutable system profile MUST давать `400 invalid_supersedes`; stale head MUST давать `409 profile_version_conflict`; совпадающий canonical content MUST давать `409 profile_content_unchanged`.
- **FR-015**: profile digest MUST вычисляться из одной канонической формы семантических полей; порядок object keys и незначимые различия сериализации MUST не менять digest.
- **FR-016**: create run MUST атомарно зафиксировать immutable config snapshot точных profile, skill, model, dialogue policy и engine versions/digests и requested-source snapshot до постановки работы в очередь; prepared-source snapshot с terminal statuses/fragments/diagnostics фиксируется отдельным append-once шагом после extraction и до `reviewing`.

#### Review lifecycle и результат

- **FR-017**: run MUST следовать состояниям `queued → preparing → reviewing → validating → completed` с допустимыми terminal `failed|cancelled`; terminal state MUST не изменяться.
- **FR-018**: worker MUST проверять запрос отмены до подготовки, между sources/work items, до каждого model invocation, до synthesis, до validation и непосредственно перед публикацией.
- **FR-019**: после атомарного принятия отмены backend MUST прекращать новые внешние вызовы; run MUST завершиться `cancelled`, а report MUST никогда не публиковаться.
- **FR-020**: deterministic mode MUST выполнять настоящие parsing, snapshot, orchestration и validation stages. Expected findings разрешены только при exact match document/profile/skill/parser/engine selectors с trusted release config и exact expected-output resource ID/SHA, валидным по `trusted-fixture-expected-output.v1`; template MAY разрешить только primary fragment ordinals, exact quote occurrences и текущие dynamic IDs/offsets, после чего итог повторно проходит `review-output.v1` validation. Для любого другого документа mode MUST публиковать zero-finding partial report, пустой reviewed set, limitation `deterministic_mode_no_semantic_analysis` и один `CoverageGap(code=other, reason=semantic_analysis_not_performed)` на каждый известный primary target fragment.
- **FR-021**: engine MUST отделять trusted versioned engine/skill instructions от document, context, текущего сообщения, всей предыдущей dialogue history и intermediate model text, рассматривая все последние значения только как untrusted input.
- **FR-022**: каждый published report MUST пройти JSON Schema и semantic validation: membership, quote occurrence/offsets, locator bounds, primary-document grounding, exact target coverage, missing/scope rules и duplicate detection.
- **FR-023**: coverage MUST ровно и без пересечений раскладывать каждый известный target fragment primary document на reviewed либо fragment-level gap; source-level `primary_source_partial`/context gaps дополняют, но не заменяют эту partition, а supporting context MUST не увеличивать target set.
- **FR-024**: exhausted optional context/work item MAY дать partial report только с явными gaps; unavailable primary, невозможный synthesis или invalid final output MUST дать failed run без report.
- **FR-025**: valid report с нулём findings MUST быть допустим как complete при доказанном semantic review либо как partial при полном fragment-level gap partition и явных limitations/provenance; arbitrary deterministic input использует только второй вариант.
- **FR-026**: published report MUST сериализоваться одной canonical JSON procedure и получать strong ETag из точных canonical bytes; повторное чтение и изменения dialogue/decision MUST не менять bytes или ETag.
- **FR-027**: report/finding/anchor/coverage/provenance MUST быть append-once; происхождение MUST называть execution snapshot, фактический adapter/model и все requested sources без секретов.

#### Dialogue и Human Decision

- **FR-028**: backend MUST хранить ровно один dialogue на finding и не более одного active `queued|generating` turn; `can_send_message` и `blocked_reason` MUST вычисляться сервером из состояния и immutable policy snapshot.
- **FR-029**: create dialogue turn MUST использовать Idempotency-Key и `expected_revision`; repeat same key/body MUST вернуть тот же turn, а changed body, stale revision или active turn MUST дать conflict.
- **FR-030**: retry failed turn MUST создавать новую generation attempt для исходного member message, а не второе пользовательское сообщение; опубликованным становится не более одного успешного assistant response.
- **FR-031**: skill/model response MAY объяснять, уточнять, предлагать resolution или escalation, но MUST NOT создавать или изменять Human Decision.
- **FR-032**: decision update MUST использовать `expected_revision`; non-`unreviewed` status MUST сохранять configured actor, reason, time и новую revision, а reset MUST очищать связанные human fields.
- **FR-033**: dialogue turns, generation attempts и decisions MUST восстанавливаться после restart в исходном порядке; report state MUST читаться отдельно.

#### Долговечность и фоновые задания

- **FR-034**: durable store MUST сохранять Organization, Workspace, Actor, DocumentVersion, Fragment, SourceDiagnostic, profile/model/skill/policy versions, ReviewRun, sources/snapshot, report graph, FindingState, Dialogue, Turn, GenerationAttempt, HumanDecision, IdempotencyRecord и JobOutbox.
- **FR-035**: все связи workspace-owned records MUST быть защищены namespace-aware integrity constraints; runtime MUST не создавать cross-workspace graph даже при прямой repository ошибке.
- **FR-036**: business state, durable IdempotencyRecord и outbox entry MUST фиксироваться одной transaction; конкурентные same-key/same-body requests MUST создать ровно один business resource/job и вернуть его обоим callers, different body MUST конфликтовать, delivery MUST быть at least once, а handlers MUST быть идемпотентны по business identity.
- **FR-037**: artifact upload MUST использовать same-filesystem staging, streaming size/hash verification, file fsync, atomic promotion и parent-directory fsync; rollback/crash MUST не оставлять referenced partial object. Publisher MUST до promotion получить общий transaction-scoped PostgreSQL advisory fencing lock, детерминированный exact namespace/store-key/digest, и удерживать его до commit DB reference; collector MUST брать тот же lock, повторно проверять отсутствие reference под lock и удалять object до release. При недоступной БД cleanup MUST пропускать deletion. После grace period collector MUST удалять stale staging и безопасно fenced promoted-but-unreferenced objects, никогда не удаляя referenced artifacts.
- **FR-038**: worker MUST поддерживать heartbeat, bounded retry/backoff, safe stalled-job recovery и нормализованные terminal errors; Procrastinate schema MUST инициализироваться штатной schema command, проверяться на ожидаемую version/current state и входить в readiness/healthchecks.
- **FR-039**: штатный restart API, worker и state/artifact stores MUST сохранять весь завершённый synthetic flow и позволять безопасно продолжить незавершённую outbox work; application/Procrastinate schema mismatch MUST останавливать readiness до явного migration/apply.

#### Direct channel, compatibility и model adapters

- **FR-040**: CLI MUST вызывать тот же application interface напрямую, без HTTP и без отдельной доменной модели; HTTP, worker и CLI MUST использовать общие use cases и validators.
- **FR-041**: PoC adapter MUST читать `schema_version: 1` как immutable input и применять явное преобразование source/fragment IDs, coverage, anchors, locators, diagnostics, provenance и human state без in-place rewrite.
- **FR-042**: feature 001 source, schemas, saved artifacts и regression tests MUST оставаться неизменными и проходить прежний test suite.
- **FR-043**: portable skill, common fixtures и release artifacts MUST быть organization-neutral и MUST не содержать client-materials/client materials, local absolute paths или secrets. Locked package build и public unit/contract suites MUST дополнительно проходить в generated source checkout/archive, где каталог `client-materials/` физически отсутствует, чтобы запрет включал runtime/import dependency, а не только content scan.
- **FR-044**: Model Gateway MUST иметь deterministic обязательный adapter и OpenAI-compatible optional adapter с одинаковой нормализацией capabilities, results, timeouts и errors. Внутренняя availability `available` MUST проецироваться в HTTP `available`, а `unavailable|degraded|unknown`, отсутствующая либо expired observation — только в canonical HTTP `unavailable`; внутренний reason не расширяет публичный enum.
- **FR-045**: optional local-model smoke MAY выполняться только для уже доступного либо явно разрешённого оператором endpoint; обязательный setup/tests MUST не покупать, не требовать ключи и не скачивать большие model weights автоматически.

#### Поставка, наблюдаемость и проверка

- **FR-046**: self-hosted package MUST запускать API, worker, state store, artifact volume и same-origin boundary воспроизводимой командой, по умолчанию держать service network internal и публиковать proxy только на loopback/configured trusted bind, а также предоставлять отдельные liveness/readiness checks, включая application migrations, Procrastinate schema/version и exact seed resolution.
- **FR-047**: API documentation MUST обслуживаться из локальных release assets или server-generated schema и MUST не зависеть от runtime CDN/внешнего JavaScript.
- **FR-048**: structured logs MUST содержать request/trace/job/resource IDs, state transitions, safe codes и durations, но не содержимое документов/сообщений, provider secrets или raw responses.
- **FR-049**: default Compose/runtime configuration MUST разрешать только объявленные internal service connections и не предоставлять external application egress; deterministic tests MUST доказывать 0 connection attempts к адресам вне internal allowlist. Optional model egress MAY включаться только отдельной operator opt-in конфигурацией для exact allowlisted endpoint; feature не заявляет и не реализует OS-wide firewall для host.
- **FR-050**: implementation MUST следовать test-first порядку и иметь автоматические contract, unit, integration, migration, security и end-to-end suites, включая все негативные сценарии этой спецификации.

### Key Entities

- **Configured Deployment Context**: единственные настроенные Organization, Workspace и Actor; namespace и provenance без identity/access-control утверждений.
- **Document Version / Fragment / Source Diagnostic**: неизменяемые bytes, адресуемое извлечённое содержимое и безопасное описание доступности.
- **Review Profile Family / Version**: логическая family и её server-versioned immutable настройки проверки.
- **Model Profile / Skill Version / Dialogue Policy Version**: разрешённые immutable execution dependencies без provider secrets.
- **Review Run / Run Source / Execution Snapshot**: lifecycle фоновой работы и точный снимок всех входов и версий.
- **Review Report / Finding / Evidence Anchor / Coverage Gap / Provenance**: append-once validated результат.
- **Finding State / Dialogue / Dialogue Turn / Generation Attempt / Human Decision**: отдельное mutable/versioned рассмотрение человеком.
- **Idempotency Record / Job Outbox**: защита create operations и durable handoff фоновой работы.
- **Artifact**: непрозрачно адресуемые immutable bytes за общим storage boundary.

## Scope and Boundaries

### In Scope

- Backend-owned HTTP v1 operations, asynchronous API/worker flow, direct CLI и portable skill runtime.
- Реальное извлечение PDF с текстовым слоем, Markdown и UTF-8 TXT; immutable artifacts, exact coverage и semantic validation.
- Полный deterministic synthetic flow без внешней модели и optional OpenAI-compatible/local model adapter.
- PostgreSQL-backed durable state, migrations, transactional outbox, Procrastinate worker, обязательный POSIX artifact storage и provider-neutral `ArtifactStore` port для будущих adapters.
- Review report, dialogue, Human Decision, history, idempotency, cancellation, concurrency и restart recovery.
- Self-hosted trusted-network Compose, local API docs, safe logs, health/readiness и автоматические suites.

### Out of Scope

- Любые изменения или реализация React web в `apps/web/`; web использует существующий canonical contract.
- Authentication, authorization, accounts, roles, multi-organization runtime, RLS как access control и публикация API в недоверенную сеть.
- OS-wide host firewall, perimeter/VPN/TLS provisioning и доказательство отсутствия egress у процессов вне поставляемой Compose/application boundary.
- Автоматическое редактирование ТЗ, новый документ по решениям, общий чат вне finding, RAG, обучение и библиотека прошлых ошибок.
- OCR, DOCX, vision, связанные внешние страницы, Confluence/Jira/почта/мессенджеры и автоматический сбор клиентского контекста.
- Обязательная облачная/платная LLM, автоматическая установка большой локальной модели и заявление о качестве конкретной модели.
- Производственные SLO, retention/delete, backup RPO/RTO, Kubernetes и конкретный S3 provider до отдельного решения.
- Экспертное подтверждение findings, продуктовый эффект, результаты пилота, коммерческий статус и переносимость между компаниями.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% backend-owned HTTP v1 operationIds имеют автоматический contract test и совместимую реализацию; generated backend OpenAPI не содержит breaking diff относительно canonical baseline.
- **SC-002**: canonical digest-allowlisted synthetic review и dialogue/decision flow проходит в чистой установке с versioned packaged runtime config + expected-output resource, без API-ключей и платных сервисов; startup проверяет exact resource/selectors, а network-deny spy допускает только declared internal service destinations и фиксирует 0 external/unknown destination attempts в deterministic composition.
- **SC-003**: 100% опубликованных reports проходят structural и semantic validation; в негативных fixtures ни один invalid result не публикуется.
- **SC-004**: во всех coverage tests каждый известный target fragment встречается ровно один раз в reviewed set либо fragment gap; partial primary дополнительно содержит source-level `code=source_partial`, `fragment_id=null`, `reason=primary_source_partial`, а arbitrary deterministic document имеет `code=other`, `reason=semantic_analysis_not_performed` для каждого target fragment.
- **SC-005**: повторное чтение report до и после dialogue/decision/restart и после добавления новых profile/model/skill/policy versions возвращает побайтово одинаковое canonical body, прежний execution snapshot и тот же strong ETag.
- **SC-006**: во всех in-memory и PostgreSQL race tests конкурентный same key/body создаёт ровно один resource/outbox и возвращает его обоим callers даже после изменения текущей projection; different body или stale revision получает conflict, и одновременно существует не более одного active turn на finding.
- **SC-007**: clean application + Procrastinate schema initialization, exact seed, full synthetic flow, штатный restart и duplicate job delivery завершаются без потери либо дублирования documents, runs, reports, turns и decisions; stale schema/version делает readiness unhealthy до migration.
- **SC-008**: 100% namespace-negative tests возвращают обычный `404`; опубликованная OpenAPI не содержит security schemes, `401` или `403` responses.
- **SC-009**: автоматический scan на release artifacts, metadata-only DTO, Problem Details, queue payload и captured safe logs находит 0 provider secrets, client-materials/client markers, local absolute paths и non-allowlisted runtime/client document/message content; committed neutral synthetic fixtures разрешены только по manifest allowlist. Отдельные contract tests подтверждают, что purpose-built document/report/dialogue responses возвращают только предусмотренные canonical content fields.
- **SC-010**: direct CLI и HTTP проходят один semantic conformance dataset, а неизменённый feature 001 PoC проходит прежний regression suite.
- **SC-011**: clean self-hosted package после штатных locked-image `uv run --frozen alembic ... upgrade head`, `uv run --frozen procrastinate --app=<app> schema --apply`, exact seed и matching `... healthchecks` предоставляет зелёные liveness/readiness и выполняет обязательный smoke после restart; API documentation открывается при отключённом интернете.
- **SC-012**: optional local-model test либо проходит через общий adapter contract, либо предсказуемо пропускается с безопасной причиной; его отсутствие не меняет результат обязательных suites.
- **SC-013**: все обязательные contract, unit, integration, migration, security и end-to-end tests завершаются успешно из locked dependency state; locked package build и public unit/contract subset отдельно проходят в source export без каталога `client-materials/`.
- **SC-014**: git diff feature не содержит изменений под `apps/web/`, `client-materials/`, `specs/001-*` или `specs/002-*`; shared root contract меняется только additive preflight v1.0.2.

## Assumptions

- Пользователь отдельным поручением разрешил реализацию backend; D-18/D-19 и feature 002 остаются действующим baseline.
- Первую поставку запускает один operator в доверенной сети с одной organization, одним workspace и одним actor; их значения задаются конфигурацией, а не HTTP.
- Deterministic adapter является техническим test/demo substitute, а не заменой смысловой модели и не свидетельством качества review.
- Canonical synthetic dataset идентифицируется только exact digest + versioned trusted fixture configuration; content markers не являются переключателем поведения. На любом другом документе deterministic mode обязан вернуть partial zero-finding result с per-fragment `CoverageGap(code=other, reason=semantic_analysis_not_performed)` вместо выдуманного анализа.
- Бесплатная локальная модель считается доступной только при наличии совместимого endpoint и достаточных ресурсов; автоматическое скачивание weights не предполагается.
- Неподтверждённые performance/SLO, document scale, retention и backup параметры не блокируют локальную реализацию, но фиксируются как нерешённые production decisions.
- Вся новая документация и fixtures являются общими и синтетическими; материалы client используются только как evidence при формулировке edge cases и не копируются.
- `AGENTS.md` остаётся единственным нормативным источником project instructions; `.specify/memory/constitution.md` может только указывать на него, а любая незамерженная альтернативная constitution non-normative и не расширяет scope.
- Реализация выполняется автономно по dependency-ordered tasks после отдельного старта implementation task; промежуточные product approvals не требуются, пока не меняются перечисленные scope и публичные contracts.
