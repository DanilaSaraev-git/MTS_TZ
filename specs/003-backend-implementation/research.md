# Research: реализационные решения backend feature 003

Дата: 2026-09-05. Этот документ уточняет реализацию уже принятого направления D-18/D-19 и ADR-0001. Он не подтверждает продуктовые гипотезы и не меняет архитектурный feature 002. Единственный нормативный источник project instructions — `AGENTS.md`; `.specify/memory/constitution.md` допустим только как указатель на него, а незамерженная альтернативная constitution non-normative и не может менять scope или gates.

## R-01. Baseline и contract preflight

**Decision**: machine baseline реализации — tag `review-platform-contract-v1.0.1`. Перед кодом выпускается additive clarification `v1.0.2` в root `contracts/review-platform/v1/`: `info.version=1.0.2`; `400` invalid-cursor responses для `listDocuments`/`listReviewRuns`; `404` для `uploadDocument`; `409` для stale/unchanged profile supersedes; полный набор уже существующих `400/404/409` branches в conformance evidence; точные descriptions extraction/profile/strong ETag; локальные Swagger assets. Root README/CHANGELOG, affected examples/tests и tag `review-platform-contract-v1.0.2` обновляются вместе; FastAPI export, старые examples и isolated backend-owned `tools/contracts/orval/` generation/typecheck с exact Node/npm/TypeScript/Orval pins подтверждают additive compatibility без зависимости от `apps/web/`. Артефакты `specs/002-target-review-platform/` не редактируются.

**Rationale**: web уже может работать от v1.0.1, а найденные дыры не требуют breaking payload change. Отдельный первый task сохраняет contract-first порядок и не смешивает target design с progress tracking.

**Alternatives considered**:

- молча реализовать дополнительные ответы — отклонено: backend export разойдётся с design-first source;
- переписать feature 002 — отклонено пользователем: нужен новый implementation feature;
- открыть `/v2` — не требуется для additive response/descriptions.

## R-02. Обязательный no-model режим

**Decision**: shipped deterministic adapter выполняет две стратегии через обычный `ModelGateway` port:

1. для versioned canonical synthetic fixture сверяет exact raw-byte SHA-256, profile/skill/parser/engine selector digests и expected-output resource ID/SHA с trusted release config, валидирует закрытый `trusted-fixture-expected-output.v1` template и строит стабильный schema-valid response, разрешая только primary fragment ordinals, exact quote occurrences и текущие dynamic IDs/offsets;
2. для любого другого поддерживаемого документа возвращает zero-finding partial response: `reviewed_fragment_ids=[]`, каждый известный primary target fragment находится в `unreviewed`/HTTP gap с `code=other` и stable reason `semantic_analysis_not_performed`, а limitation равен `deterministic_mode_no_semantic_analysis`.

Обе стратегии проходят реальные extraction, review input assembly, orchestration, skill/output validation, canonical publication и persistence. HTTP route не выбирает готовый report fixture.

Root `runtime-config.v1` default намеренно содержит пустой binding list и всегда выбирает честный no-semantic path. Versioned Compose smoke config отдельно и явно содержит одну нейтральную binding и read-only packaged expected-output resource; bootstrap/readiness проверяет все её SHA/schema/selectors и падает при drift. **Rationale**: backend должен быть воспроизводимо рабочим без credentials, но не должен выдумывать смысловой анализ. Digest allowlist принадлежит trusted release config; пользователь не может включить expected-finding path, просто повторив marker-like текст.

**Alternatives considered**:

- hard-coded HTTP fixture — не проверяет engine boundary и persistence;
- content markers либо случайные heuristics по произвольному тексту — дают недоверенному документу управляющее значение или ложное впечатление полезности;
- обязательная внешняя LLM — ломает offline, deterministic tests и требование пользователя.

## R-03. Core и runtime

**Decision**: `review-core` содержит domain/application/ports и pure validators; `review-runtime` содержит все I/O adapters. API/worker/CLI — только composition/transport. `ReviewApplication` является coarse boundary, `ReviewEngine` — глубоким orchestration module. Boundary покрывает каждый backend-owned operationId, включая `get_bootstrap` и exact-byte `download_document`, а также list/upload/get documents, list/create profiles, list model profiles, create/list/get/cancel reviews, get report/finding states/dialogue, create/retry/execute dialogue turn, put decision, execute review и read PoC. HTTP routes не читают config, repositories или ArtifactStore в обход application use case.

**Rationale**: один core нужен HTTP и local channel, а выбранные adapters имеют реальные альтернативы: fake/PostgreSQL, memory/POSIX/S3, deterministic/OpenAI-compatible, inline/Procrastinate.

**Alternatives considered**:

- FastAPI service напрямую над SQLAlchemy — связывает domain с transport/storage и расходится с CLI;
- microservices — нет измеренного независимого deployment need;
- framework-wide mediator/event bus — добавляет surface без текущей пользы.

## R-04. Upload и extraction lifecycle

**Decision**: upload синхронно проверяет multipart, supported media type, non-zero/max bytes, пишет immutable bytes через staging/hash/promote и создаёт immutable `DocumentVersion` плюс отдельную lifecycle-row `document_extractions(state=pending)`. Публичный `Document.extraction_state` является projection этой строки: внутренние `pending|extracting` отображаются в canonical `pending`, terminal `completed|partial|failed` — одноимённо; DTO boundary не выдаёт внутренний enum. Сама версия документа не мутирует. Extraction не выполняется в upload request. Create run фиксирует immutable requested-source identity/order/role и config snapshot, но не выдумывает terminal status/fragments. В `preparing` первый worker получает single-writer claim по `(document_id, parser_name, parser_version, settings_digest)`; конкурентный worker ждёт или перечитывает terminal result. Claim имеет heartbeat/lease, stale claim после crash безопасно перехватывается, а unique identities не допускают duplicate fragments/diagnostics. После terminal extraction run одним append-once шагом фиксирует prepared-source status, exact fragment IDs и diagnostics до `reviewing`.

`completed` означает все ожидаемые units извлечены; `partial` — есть минимум один fragment и diagnostics; `failed` — нет безопасно используемого content. Partial primary с usable fragments добавляет source-level HTTP gap `code=source_partial`, `fragment_id=null`, `reason=primary_source_partial` и сохраняет exact partition всех известных target fragments; primary с zero usable fragments завершает run без report. Empty/image-only/encrypted PDF без OCR получает stable diagnostic.

Zero-byte и media-type mismatch отклоняются на boundary; byte limit проверяется streaming до полного сохранения. Leading UTF-8 BOM остаётся в raw bytes, но снимается с extracted text как versioned parser normalization. Whitespace-only primary не имеет usable fragments. Empty PDF pages и split tables сохраняют per-page boundaries/diagnostics без недоказанного merge. Caller mutation после ответа не влияет на stored bytes/hash; две загрузки одинаковых bytes создают разные DocumentVersion IDs/provenance, даже если storage когда-либо дедуплицирует blob. Context-count/cursor invalid input даёт `400`; page/fragment/work budgets дают failed primary либо явные source/fragment gaps, но не silent truncation.

**Rationale**: upload остаётся быстрым, bytes сразу воспроизводимы, parser failure относится к отдельному наблюдаемому lifecycle.

**Alternatives considered**:

- synchronous extraction — связывает request timeout с PDF и затрудняет recovery;
- отдельный extraction job сразу после upload — добавляет состояние/гонки до появления run без доказанной потребности;
- извлекать заново каждый run — нарушает reproducibility и расходует ресурсы.

## R-05. Profile family/version semantics

**Decision**:

- `POST` без `supersedes` создаёт workspace family UUID и immutable `1.0.0`;
- `supersedes` обязан ссылаться на текущую последнюю workspace version той же configured workspace family; server сохраняет family ID и увеличивает patch;
- missing либо foreign-workspace reference скрывается обычным `404`; видимый immutable system profile даёт `400 invalid_supersedes`; non-head/stale ref даёт `409 profile_version_conflict`; identical canonical semantic digest даёт `409 profile_content_unchanged`;
- `name`, `role`, `goal`, ordered `checks` образуют semantic digest; server metadata не входит;
- system profiles immutable и seed/versioned через release data, не public POST.
- default system profile deployment-scoped: его release identity/version/digest не принадлежит workspace, но он видим единственному configured workspace;
- immutable `review_profile_versions` не содержат изменяемый `is_head`; отдельный mutable family-head pointer обновляется CAS одновременно со вставкой следующей version, поэтому old version bytes/digest никогда не переписываются.

**Rationale**: request не содержит desired SemVer/change class, поэтому автоматический patch — единственная детерминированная backward-compatible политика. Major/minor требуют будущей отдельной operation/contract.

**Alternatives considered**:

- новый UUID/1.0.0 при каждом POST — `supersedes` не создаёт usable version chain;
- клиент задаёт SemVer — поля нет в v1 и возникает race;
- автоматически решать major/minor по содержимому — недостоверно.

## R-06. Canonical JSON, digest и ETag

**Decision**: [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) (JCS), UTF-8, no BOM, no trailing newline применяется к validated JSON-compatible values через exact pin [`rfc8785==0.1.4`](https://pypi.org/project/rfc8785/0.1.4/). Duplicate JSON keys, NaN/Infinity и non-finite provider numbers отклоняются до canonicalization. Strong report ETag — quoted lowercase SHA-256 hex canonical response bytes: `"<64-hex>"`.

Тот же canonicalizer используется для profile semantic digest, execution/config digests и idempotency request digest после DTO validation. Multipart document hash считается по raw bytes. Timestamp values до JCS нормализуются в UTC RFC 3339 как `YYYY-MM-DDTHH:mm:ss.ffffffZ`: суффикс только `Z`, ровно шесть fractional digits, без offset-вариантов. Conformance suite MUST прогонять официальные RFC 8785 Appendix B vectors и полный [`cyberphone/json-canonicalization`](https://github.com/cyberphone/json-canonicalization) reference vector corpus; локальные golden vectors дополняют, но не заменяют их.

**Rationale**: один алгоритм устраняет drift key order/whitespace и позволяет сохранить exact bytes как release artifact.

**Alternatives considered**:

- обычный `json.dumps(sort_keys=True)` — не является межреализационным стандартом и имеет edge cases numbers/Unicode;
- digest relational rows on each read — body может измениться после mapper refactor;
- weak ETag — не соответствует immutable exact representation.

## R-07. Report publication

**Decision**: engine строит target report value, выполняет schema/semantic validation, JCS serialization и SHA-256 до publication. Canonical bytes записываются в staged artifact и atomically promoted. Одна DB transaction создаёт report graph/metadata, ссылку на artifact, initial finding states и переводит run `validating→completed` условно на отсутствии cancellation. Runtime никогда не пересериализует report для GET: отдаёт сохранённые bytes и ETag. Regression обязательно создаёт новые profile/model/skill/policy versions после публикации и доказывает, что старый report, provenance snapshot, canonical bytes и ETag остаются прежними.

**Rationale**: стабильность не зависит от текущей ORM/Pydantic версии; `completed` невозможно наблюдать без report.

**Alternatives considered**:

- хранить только JSONB и сериализовать на GET — ETag/bytes нестабильны;
- только artifact без relational graph — dialogue/finding integrity и audit сложнее;
- publish state до artifact — создаёт broken completed run.

## R-08. Cooperative cancellation

**Decision**: cancel endpoint атомарно устанавливает `cancel_requested_at` только для non-terminal run. Worker проверяет cancellation: перед extraction; между sources; между work items; перед каждым model call/retry; перед synthesis; перед validation; перед artifact promotion; и в final compare-and-set publication transaction.

Race outcome бинарен: publication wins → completed/report и cancel conflict; cancellation wins → cancelled/no report и publication rejected. Повтор cancel до acknowledgement возвращает текущее run без нового side effect.

**Rationale**: provider call нельзя безопасно прервать в каждой точке, но bounded checkpoints и final CAS дают строгий publish invariant.

**Alternatives considered**:

- kill task/process — может оставить неизвестный provider/transaction state;
- только boolean polling раз в run — report может выйти после cancel;
- удалить report post-factum — нарушает append-only.

## R-09. Persistence и namespace integrity

**Decision**: PostgreSQL хранит все сущности из `data-model.md`. Каждая workspace-owned key/FK включает `organization_id, workspace_id`; configured context фильтруется в repository query, а missing/foreign resource становится `NotFound`. RLS не используется как access control. Immutable semantic/version rows защищены repository API и DB triggers/permissions в production role; lifecycle projection, extraction claim и отдельный profile family-head pointer являются явно mutable rows и обновляются только допустимым transition/CAS predicate.

**Rationale**: application check недостаточен против ошибочной cross-link записи. Composite constraints дают provenance integrity без заявления об authentication.

**Alternatives considered**:

- только UUID FK — возможны cross-workspace graph bugs;
- RLS/memberships — запрещённый D-19 auth scope;
- document database — слабее выражает constraints/races первого среза.

## R-10. Outbox и at-least-once worker

**Decision**: creation of run/turn/retry, durable idempotency reservation, exact review-execution/generation-attempt identity and `job_outbox` atomically commit. Unique `(namespace, operation, key)` reservation проверяется до mutable-state conflicts: concurrent same-key/same-body callers получают один resource/outbox и current representation, different digest получает `409`; losing transaction перечитывает winner. Envelope discriminated by kind names the exact `review_execution_id` or `generation_attempt_id`, so a late delivery can never execute a newer retry.

Dispatcher claims only due/expired rows through `claim_token + lease_expires_at` CAS, publishes an ID-only envelope to Procrastinate and marks publication with the same token. Transient/uncertain publish returns the row to bounded backoff; duplicate publish/delivery is legal. Exhaustion atomically marks the outbox and still-active referenced run/turn failed with a normalized code. Review and dialogue handlers separately claim application execution leases, heartbeat and persist verified checkpoints; after crash they resume the exact non-terminal attempt even when its business state has advanced beyond `queued`. A stale owner cannot checkpoint or publish.

Procrastinate schema не считается побочным эффектом worker startup. Clean installation явно выполняет locked-image [`uv run --frozen procrastinate --app=<app> schema --apply`](https://procrastinate.readthedocs.io/en/stable/quickstart.html), затем matching `... healthchecks`; readiness сверяет ожидаемую schema/version/current migration state. Empty database, current schema и stale/incompatible schema имеют отдельные integration cases, причём stale schema остаётся unhealthy до явного [apply/migration](https://procrastinate.readthedocs.io/en/stable/howto/production/migrations.html).

**Rationale**: SQLAlchemy business transaction и Procrastinate transaction не образуют distributed atomic commit; outbox closes the loss window.

**Alternatives considered**:

- enqueue after commit — crash loses job;
- enqueue before commit — worker sees absent state;
- direct in-process background task — lost on restart;
- Redis/RabbitMQ — лишний обязательный service без измеренной нагрузки.

## R-11. ArtifactStore

**Decision**: mandatory POSIX adapter uses keys derived from configured organization/workspace plus opaque UUID, never user filename/path. Writes use a same-filesystem temp file, streaming SHA/size verification and staging-file `fsync`. Publisher then opens a DB transaction, takes a transaction-scoped PostgreSQL advisory fence derived from exact namespace/store key/digest before atomic rename, performs the rename and parent-directory `fsync`, writes the DB reference and releases the fence only on commit. Collector after configured grace period handles stale staging and promoted-but-unreferenced objects left by crash; for a promoted object it takes the same fence, repeats the non-reference check inside the transaction, deletes before release and skips on DB/lock uncertainty. A concurrent collector therefore cannot delete between publisher check and reference commit. Provider-neutral port и conformance suite фиксируют требования к будущему S3-compatible adapter, но сам adapter и его SDK в feature 003 не входят.

**Rationale**: single-node baseline не требует object-server dependency; port сохраняет future portability.

**Alternatives considered**:

- blobs in PostgreSQL — увеличивают DB/backup surface;
- raw filesystem path in domain/API — leaks deployment and enables traversal;
- bundled MinIO — не нужен и не является принятым production baseline.

## R-12. PoC v1 read mapping

**Decision**: adapter сначала запускает legacy validation и hash checks, затем строит закрытый `poc-import-view.v1` целиком в памяти. Target IDs детерминированы UUIDv5 от `(legacy run digest, entity kind, legacy id)`; legacy bytes/directories не записываются и не копируются в ArtifactStore. `original_path` dropped. Context fragments доступны как evidence, но target coverage формируется только из primary document fragments. Только полностью schema/semantic-valid view может быть atomically written за пределами legacy directory.

Legacy quote offsets находятся после PoC NFC + whitespace-collapse normalization: единственное occurrence преобразуется; несколько occurrences требуют deterministic locator disambiguation, иначе вся mapping завершается typed failure без output. Непредставимый обязательный PDF locator, invalid finding/anchor или любое нарушение target graph также fail whole mapping — отдельный finding не отбрасывается. Safe source-availability loss может дать `mapping_status=partial`. Legacy `unreviewed` становится FindingState revision 0; любой non-unreviewed human state также остаётся target `unreviewed`, добавляет `legacy_human_state_unrepresentable` diagnostic и никогда не приписывается configured actor.

**Rationale**: mapping должен быть повторяемым и честным о потере точности; legacy schema не меняется.

**Alternatives considered**:

- случайные target UUID — повторный import дублирует ресурсы;
- in-place upgrade — разрушает experiment provenance;
- брать first quote occurrence — создаёт неверный anchor;
- включить context в coverage — меняет target v1 semantics.

## R-13. Optional local/OpenAI-compatible model

**Decision**: один OpenAI-compatible HTTP adapter реализует port; server-side profile задаёт base URL, model name, timeout, capabilities и secret reference. Внутренняя availability projection сохраняет `available|unavailable|degraded|unknown`, но canonical HTTP mapping равен `available → available`, а `unavailable|degraded|unknown|missing|expired → unavailable`; reason/freshness остаются server-side. На implementation host сначала выполняется read-only discovery уже установленного Ollama/совместимого endpoint. Модель не устанавливается и weights не скачиваются автоматически. Optional smoke включается явной environment configuration и skip при отсутствии ресурса.

**Rationale**: это позволяет использовать бесплатную локальную модель, если она действительно доступна, без превращения machine-specific download в release dependency.

**Alternatives considered**:

- bundle one model/runtime — большие weights, лицензия и hardware assumptions;
- provider-specific SDK in core — ломает port;
- declare any text model compatible — contract validity не гарантирует capability.

## R-14. Prompt boundary, logs и outbound policy

**Decision**: `GenerationRequest` строится из двух физически отдельных полей. `trusted_instructions` получает только versioned engine/skill content; document, context, current member message, полная prior dialogue history и intermediate outputs находятся только в `untrusted_input`. Queue/logs никогда не содержат эти тексты. Structured logs use IDs, state, codes, counts/durations and provider request ID; central redaction filters headers/secrets/path/content canaries. Canonical document download, report evidence quotes и dialogue content являются purpose-built responses и не подпадают под запрет content; Problem Details, metadata-only DTO, queue payload, logs, metrics и diagnostics подпадают.

Deterministic test installs application-level egress spy that allows declared internal PostgreSQL/queue service destinations and fails every external/unknown destination attempt. Default Compose uses an internal service network and loopback/configured trusted proxy bind; optional model egress появляется только через отдельную operator opt-in network/config и exact endpoint allowlist. Real adapter may connect only to that base URL; no telemetry/fallback endpoint. Это не OS-wide firewall claim: защита host/network perimeter остаётся обязанностью operator. API exposes safe RFC 9457 detail, while protected diagnostic sink still filters credentials.

**Rationale**: загруженный документ по AGENTS является data, а не instruction; offline claim must be testable.

**Alternatives considered**:

- prompt string concatenation — делает injection boundary непроверяемой;
- log prompts for debugging — нарушает data handling;
- transparent provider fallback — создаёт незаявленный egress.

## R-15. Local API documentation

**Decision**: production API docs use assets packaged in `apps/api/src/review_api/static/docs/` (or FastAPI-rendered equivalent pinned in image). No HTML imports runtime JS/CSS from CDN. Canonical `/api/v1/openapi.json`/YAML remains generated/served from the same schema; CI validates it against root design-first file.

**Rationale**: self-hosted offline deployment должен документировать API без внешнего supply-chain/runtime dependency.

**Alternatives considered**:

- current unpkg-based static page — breaks offline and adds runtime dependency;
- disable docs entirely — ухудшает operator/integration verification;
- duplicate handwritten API pages — drift from canonical schema.

## R-16. Test topology

**Decision**: TDD order per task. Unit/contract tests run without Docker; integration/migration run against disposable PostgreSQL 18; E2E starts clean Compose and performs actual API/worker flow. Synthetic fixtures are generated/committed without MTS/client data; trusted expected findings select only by committed digest/config, never by content markers. `.gitattributes` excludes `/MTS` from source exports and `.dockerignore` excludes it from image contexts; release gate builds packages and runs public unit/contract suites inside a temporary exported checkout after asserting the directory is absent. Private corpus smoke is opt-in by explicit path outside repo, emits no content and is never release gate.

Required evidence covers official RFC/cyberphone canonicalization vectors; BOM/empty/page/table-split and all byte/page/fragment/context/work budgets; caller mutation and distinct same-byte uploads; two-worker extraction claim/crash recovery; staging and promoted-orphan/DB crash windows plus concurrent collector-vs-publication fencing; durable idempotency races; duplicate delivery; stale revision; cancel-vs-publish; old report after config-version evolution; full dialogue-history prompt separation; Procrastinate clean/current/stale schema; invalid model output; path traversal; purpose-built content responses and redacted unexpected exceptions.

**Rationale**: one happy-path suite cannot prove asynchronous/durable invariants; deterministic model makes exhaustive failures reproducible.

**Alternatives considered**:

- mock-only tests — do not prove constraints/restart;
- real-LLM E2E as gate — nondeterministic and credential-bound;
- MTS fixtures in shared suite — violates client separation and contaminates independent evaluation.

## R-17. Runtime configuration and exact bootstrap seed

**Decision**: repository ships and validates the complete, secret-free runtime policy against `contracts/runtime-config.v1.schema.json` before composition starts: retry, timeout, lease/recovery and budget values, model-gateway policy, canonical codec and trusted fixture digest bindings. Separate typed operator deployment settings validate the exact organization/workspace/actor IDs and labels, artifact root, trusted proxy bind and exact refs for the deployment-scoped system review profile, deterministic model profile, dialogue policy and skill package. Database connection values and provider credentials are supplied only through environment/secret references; neither secrets nor operational connection values are copied into public DTO or execution snapshot text.

Application bootstrap is one idempotent transaction after application and Procrastinate schemas are current. It inserts the configured organization/workspace/actor and exact immutable profile/model/policy/skill versions when absent. If an existing identity has different immutable content/version/digest, startup does not mutate it and readiness is unhealthy with a safe drift code. Repeated bootstrap is a no-op with identical IDs/digests.

**Rationale**: “seed a default” is insufficient for a clean reproducible deployment; exact configured identities and package digests make bootstrap, snapshots and restart checks deterministic without inventing a multi-tenant control plane.

**Alternatives considered**:

- implicit hard-coded rows in API startup — hides drift and races multiple processes;
- mutable upsert over version rows — destroys old snapshot reproducibility;
- public bootstrap administration endpoints — expands the accepted no-auth contract.

## Unresolved production decisions

Retention/delete/legal hold, backup/restore RPO/RTO, numerical SLO/capacity, HA/Kubernetes, approved pilot LLM, client-specific S3 and security controls outside the trusted boundary remain unresolved. Feature 003 must expose these as operator documentation gaps, not choose silent indefinite promises. Они не блокируют локальный single-node technical release defined by this feature.
