# Data model: schema_version 1

Экспериментальный контракт PoC, не постоянный публичный контракт продукта. Точное описание отчёта поставляется в [report-format](../../implementation/poc/review-data-spec/references/report-format.md), машинные ограничения — в ресурсах пакета.

| Сущность | Поля и связи | Инвариант |
| --- | --- | --- |
| Source | id, role=document/context, name, original_path, status, snapshot, sha256, parser, diagnostics | Ровно один доступный document; исходные байты сохранены. Необязательный контекст может быть unavailable с причиной |
| Fragment | id, source_id, kind=text/table_row, text, location (page либо line_start/line_end; table/row/bbox для таблицы), cells | Уникальный адрес в запуске; cells сохраняют null и переносы |
| Bundle | schema_version, run_id, sources, fragments | Нормализованное производное представление; source_id существует |
| Profile | schema_version, name, version, role, goal, checks, context_files | Пути контекста относительно profile.json; базовый профиль без клиента |
| Manifest | schema_version, run_id, created_at, skill_version, runtime, parser, profile_mode, sources, artifacts, prepare_seconds | artifacts: относительный путь → SHA-256; все пути в пределах запуска |
| Settings | schema_version, parser, text/table settings, normalization | Зафиксированы вместе с хешем |
| Report | schema_version, run_id, generation, summary, coverage, findings, limitations | Связан с подготовленным запуском; JSON Schema + семантический валидатор привязок |
| Coverage | reviewed_fragment_ids, unreviewed [{fragment_id, reason}] | Точное непересекающееся разбиение всех фрагментов; недоступные источники/пустые страницы добавляет валидатор |
| Finding | id, kind, title, problem, reason, question, priority, priority_reason, status, human_review, anchors, scope | Есть основание в ТЗ. kind=missing использует непустой scope; другие виды требуют anchors. Все основания входят в reviewed |
| Anchor | source_id, fragment_id, quote | quote непустая и входит в указанный фрагмент после NFC+whitespace; идентификаторы не исправляются |
| HumanReview | null либо reviewer, decision_reason | Для статуса кроме unreviewed обязателен человек и причина; приоритет независим |
| Generation | mode=agent/demo_fixture, agent, model, model_version | Неизвестные значения записываются unknown; технический fixture не называется агентным анализом |

Статусы замечания: unreviewed → confirmed / rejected / needs_context по решению человека. Валидатор не подтверждает личность reviewer или правоту вывода.

Состояния запуска: отсутствует → prepared (атомарно создаётся папка) → report.json → validated → report.md. При невалидном отчёте render завершает работу с ошибкой, а не оформляет результат как прошедший проверку. Изменение отчёта требует новой валидации; validation.json фиксирует хеш именно проверенного отчёта.

Недоступность контекста или неполный охват — валидный, но partial отчёт. Нарушение контракта или целостности — invalid. Эти состояния не смешиваются. Manifest не является подписью и не защищает от намеренной совместной подмены манифеста и файлов.
