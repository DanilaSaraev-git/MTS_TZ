# Changelog

## 2026-09-04 — v1 baseline

- Зафиксирован асинхронный HTTP-flow загрузки, запуска, polling, отчёта и решения человека.
- Отчёт сделан неизменяемым; `finding-states`, диалог и решение человека вынесены в отдельные ресурсы.
- Добавлен последовательный асинхронный диалог по finding: create, poll и retry failed generation; лимит задаёт versioned policy, а не web.
- Зафиксированы `review-input.v1`, `review-output.v1`, `finding-dialogue-input.v1`, `finding-dialogue-output.v1` и `review-skill.v1`.
- Добавлены `review_scope.target_fragment_ids`, structured source diagnostics и source-level coverage gaps для больших документов и недоступного контекста.
- Снимок запуска фиксирует точные версии/digests профиля, skill package, model profile, dialogue policy и engine.
- Решение человека отделено от вывода навыка; конкурентные обновления диалога и решения защищены `expected_revision`.
- Выбор поставщика LLM скрыт за версионированным профилем модели и внутренним портом backend; web больше не выбирает skill ID.
- Добавлены точные display locators и quote offsets, deployment boundary для одного настроенного actor/workspace и synthetic mock examples.
- HTTP bootstrap не моделирует identity/access-control runtime: `organization_id` сохранён только как namespace и будущий seam.
- Добавлен статический Swagger UI для просмотра канонического OpenAPI без генерации отдельной схемы.
