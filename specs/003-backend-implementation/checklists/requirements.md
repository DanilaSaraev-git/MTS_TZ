# Specification Quality Checklist: Рабочий backend платформы ревью

**Purpose**: проверить полноту и качество новой реализационной спецификации до планирования

**Created**: 2026-09-05

**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] Спецификация описывает наблюдаемое поведение и ценность backend, а конкретный стек вынесен в `plan.md`.
- [x] Feature 003 отделён от архитектурного feature 002 и не выдаёт реализацию за продуктовую проверку.
- [x] Текст понятен backend-разработчику, web-интегратору и оператору.
- [x] Все обязательные разделы заполнены.

## Requirement Completeness

- [x] В спецификации нет маркеров `[NEEDS CLARIFICATION]`.
- [x] Все 50 Functional Requirements проверяемы и используют однозначные MUST/MUST NOT/MAY.
- [x] Все Success Criteria измеримы и не обещают неподтверждённый продуктовый эффект.
- [x] User stories имеют independent tests и acceptance scenarios.
- [x] Edge cases покрывают документы, модель, coverage, idempotency, concurrency, cancellation, restart и безопасность данных.
- [x] Arbitrary deterministic input не имитирует semantic review: он даёт zero-finding partial report и явный gap для каждого primary target fragment; expected fixture path выбирается trusted digest/config, не content marker.
- [x] Clean Compose smoke владеет versioned non-secret runtime config и exact expected-output resource; пустой root default и resource/config drift имеют отдельные проверки.
- [x] Requested-source snapshot, concurrent extraction claim/recovery и append-once prepared-source snapshot разделены по времени.
- [x] Immutable profile versions отделены от mutable CAS family-head pointer; default system profile определён как deployment-scoped release seed.
- [x] Privacy rule различает purpose-built document/report/dialogue content responses и content-free errors/metadata/queue/logs/metrics/diagnostics.
- [x] In Scope и Out of Scope явно разделены.
- [x] Зависимости от feature 002, canonical contracts и feature 001 PoC названы.

## Feature Readiness

- [x] Основной synthetic E2E не требует внешней или платной модели.
- [x] Optional local model не является release gate и не запускает автоматическую загрузку weights.
- [x] Web и MTS/client materials явно исключены из implementation diff.
- [x] Immutable report, canonical bytes/ETag и mutable finding state разделены.
- [x] Durable history, outbox, duplicate delivery и restart входят в Definition of Done.
- [x] Configured namespace не представлен как authentication или authorization.
- [x] `runtime-config.v1` policy, typed operator deployment settings, exact idempotent seed и application/Procrastinate schema readiness описаны без скрытого control-plane API.
- [x] Egress gate ограничен application/Compose boundary: default internal network, explicit optional-model allowlist и отсутствие неподтверждённой OS-wide firewall претензии.
- [x] Canonicalizer pinned как `rfc8785==0.1.4`; обязательны официальные RFC 8785 Appendix B и cyberphone vectors.
- [x] Artifact crash windows включают stale staging, promoted-unreferenced orphan, file fsync и parent-directory fsync.
- [x] Publisher/collector race закрыта общим transaction-scoped advisory fence и конкурентным integration test, а не только grace period.
- [x] Внутренние extraction/model availability states имеют полное отображение в закрытые canonical HTTP enums и boundary tests.
- [x] Legacy unavailable context представим без выдуманного SHA/parser и проверяется реальным feature-001 fixture.
- [x] Orval/typecheck использует отдельный exact-pinned backend harness и не зависит от защищённого `apps/web/`.
- [x] Release gate физически собирает и тестирует public packages из source export без каталога `MTS/`.
- [x] Regression сохраняет старые snapshot/report bytes и ETag после появления новых config versions.
- [x] Все buildable outcomes могут быть разложены в TDD-oriented tasks.
- [x] `contracts/test-matrix.md` содержит явные FR/SC → Txxx mappings, а не только umbrella release task.

## Notes

- Проверка подтверждает готовность требований к техническому планированию, а не качество AI-замечаний или результаты пилота.
- `AGENTS.md` — единственный нормативный источник project instructions; pointer constitution и любые незамерженные альтернативы не меняют эти правила.
- Конкретные версии библиотек, таблицы, ports, composition roots и правила contract-conformance определяются в `plan.md`, `research.md`, `data-model.md` и `contracts/`; canonical public API при этом остаётся только в root `contracts/review-platform/v1`.
- Canonical HTTP v1 остаётся входным baseline; complete additive v1.0.2 delta, examples/tests/tag, FastAPI export и Orval compatibility оформляются отдельным contract task/PR до зависимой реализации.
