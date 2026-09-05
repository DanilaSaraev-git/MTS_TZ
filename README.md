# AI Analytics Review

База знаний для продукта предварительного ревью технических заданий на потоки и витрины данных. Название рабочее. MTS рассматриваем как первого клиента, а применимость к другим компаниям проверяем в ходе продуктового анализа.

Состояние на 2026-09-05: собраны исходные материалы, рабочие гипотезы и порядок их проверки. Реализован технический PoC переносимого навыка ревью и проведён настроечный агентный прогон на известном примере MTS. Backend 003 завершён и принят из e0dd57e; инженерная feature 004 реализована и проверена только на synthetic fake provider. Конкретная модель и реальный endpoint не выбраны и не проверялись. Экспертная оценка, независимый контроль, отдельные проблемные интервью и измерение продуктового эффекта ещё не проводились.

## Общая база

| Документ | Для чего читать |
| --- | --- |
| [Рамка продукта](knowledge/product.md) | Пользователь, проблема, предполагаемая ценность и границы обобщения |
| [Методика анализа](knowledge/methodology.md) | Конспект презентации с привязкой к слайдам и правила применения |
| [Гипотезы](knowledge/hypotheses-v2.md) | Основной реестр: одна гипотеза проблемы, пять групп решения, коммерческая гипотеза, поля SMART, вопросов и подтверждения |
| [План проверки](knowledge/discovery-plan.md) | Интервью, сбор свидетельств, оценка качества и переход к реализации |
| [Таймлайн и workflow](knowledge/roadmap.md) | Этапы развития продукта и правила изменения маршрута через продуктовые гипотезы |
| [Автопроверки требований и workflows](knowledge/requirements-workflow-evidence.md) | Существующие подходы перед разработкой, первичные источники и границы автоматизации |
| [Принятые решения](knowledge/decisions.md) | Зафиксированные направления и ещё открытые решения |
| [Источники](knowledge/sources.md) | Происхождение материалов и пределы доказательств |
| [Целевая архитектура](architecture/target-product.md) | Единый продукт для трёх стадий, выбранный стек, границы модулей и инварианты |
| [Параллельная разработка](architecture/parallel-development.md) | GitHub-flow, владение web/backend/skills, contract PR и порядок интеграции |
| [Контракты review-platform v1](contracts/review-platform/v1/README.md) | OpenAPI, skill/dialogue JSON Schema, trusted deployment boundary, model adapter и synthetic examples |
| [Инженерная LLM-интеграция — feature 004](specs/004-llm-review-integration/plan.md) | Адаптер, исполнение, хранение попыток, ошибки, backend/CLI и совместимость; [требования](specs/004-llm-review-integration/spec.md), [задачи](specs/004-llm-review-integration/tasks.md), [бэклог](specs/004-llm-review-integration/backlog.md) |
| [Настройка runtime](docs/operations/configuration.md) | Offline default, явное подключение внешней модели, mounted-file secrets и операторские проверки |
| [Смоделированное интервью с аналитиком](knowledge/simulated-interview-analyst.md) | Вымышленный диалог для репетиции интервью по вопросам гипотез 1.1, 2.1, 3.1, 4.1 — не свидетельство, не использовать как подтверждение |
| [Структура предварительной презентации](PRESENTATION_OUTLINE.md) | Каркас выступления: подход, схема решения, прогресс, результаты, риски и команда; раздел результатов заполняется после тестирования PoC |
| [DRAFT: продуктовая презентация для MTS](output/presentations/AI-analytics-review-platform-MTS-DRAFT.pptx) | Промежуточная версия: платформенный подход для разных команд, два режима review, позиционирование и три этапа реализации — PoC, самостоятельный движок, сервис с фронтендом; красно-белая стилистика без логотипа |
| [Описание решения](SOLUTION_DESCRIPTION.md) | Сводное текстовое описание для внешнего читателя: аннотация, проблематика, постановка задачи, техническое решение, результаты, планы и команда; производный документ по текущей базе |

## Реализация и эксперименты

Папка `implementation/` содержит [план PoC ревью ТЗ](implementation/poc/PLAN.md) и [переносимый навык](implementation/poc/review-data-spec/SKILL.md) с локальным CLI. Спецификация, дизайн, контракт и проверка: [Spec Kit feature](specs/001-review-data-spec-poc/spec.md). Обсуждавшийся MVP переименован в proof of concept по [D-10](knowledge/decisions.md); реализация зафиксирована в [D-17](knowledge/decisions.md).

Целевой продукт спроектирован через [Spec Kit feature 002](specs/002-target-review-platform/spec.md). Зафиксированы первый срез «ревью + диалог», React web, Python backend/core, self-hosted single-workspace deployment без авторизации и машинные контракты для параллельной работы — [D-18 и D-19](knowledge/decisions.md). Его `tasks.md` — общая карта работы, не отчёт о текущем исполнении. На 2026-09-05 backend 003 завершён; окончательный commit, исторический рабочий снимок и результаты сверки описаны в [research feature 004](specs/004-llm-review-integration/research.md).

Для самой реализации backend создан [Spec Kit feature 003](specs/003-backend-implementation/spec.md): отдельные [план](specs/003-backend-implementation/plan.md), [реализационные правила и матрица contract-conformance](specs/003-backend-implementation/contracts/README.md), [quickstart](specs/003-backend-implementation/quickstart.md), [активный MVP task ledger](specs/003-backend-implementation/tasks.md) и [отложенный production-hardening backlog](specs/003-backend-implementation/deferred-production-hardening.md). Это не второй публичный API: единственным canonical contract остаётся `contracts/review-platform/v1`. Обязательный release gate работает без внешней модели на deterministic adapter; бесплатная локальная OpenAI-compatible модель, если она уже доступна, проверяется только как необязательный adapter. Web и клиентские материалы MTS в feature 003 не входят — [D-20](knowledge/decisions.md).

[Feature 004](specs/004-llm-review-integration/spec.md) реализует инженерное подключение модели поверх окончательного 003: один review step на полном допустимом входе, максимум один автоповтор временного отказа, deadlines 300/60s, без model concurrency limiter и очереди — [D-21](knowledge/decisions.md). Review, dialogue, same-turn retry, immutable report, попытки, restart reconciliation, mounted-file secrets, direct CLI и opt-in Compose проверены synthetic gate. [Чанкинг](specs/004-llm-review-integration/backlog.md) отложен. Предметный harness проектируется в другой задаче; модель/провайдер не выбраны, реальный endpoint не проверен.

PoC фиксирует одну экспериментальную конфигурацию. Общий маршрут развития описан в [таймлайне и workflow](knowledge/roadmap.md): инженерные работы и продуктовые проверки имеют раздельные статусы; состав следующих срезов может меняться по мере уточнения гипотез. Клиентские материалы, включая результаты экспериментов MTS, сохраняются в `MTS/`.

## Первый клиент

[Каталог MTS](MTS/README.md) содержит постановку кейса, тестовые документы, первоначальные наблюдения и вопросы кейсодателю. Клиентские требования развиваются там; общая база содержит продуктовые обобщения и ссылки на свидетельства.

- [Оригинал транскрибации Q&A](MTS/sources/meeting-qa-received-2026-09-03.original.txt): копия без исправлений, получена 2026-09-03; дата встречи неизвестна.
- [Портреты пользователя и покупателя](MTS/user-and-buyer.md): выводы по MTS, карта участников решения и пробелы для следующего интервью.
- [Уточнённый список моделей MTS](MTS/model-candidates.md): сообщение заказчика сохранено отдельно от предположений о model ID; конкретная модель/провайдер ещё не выбраны.
- [Контекст-пак MTS, версия 2](CONTEXT_PACK_MTS.md): черновик по всем восьми разделам, обновлённый по базе знаний; требования, свидетельства и непроверенные гипотезы разделены.
- [Исходная версия контекст-пака, S-07](MTS/sources/context-pack-mts-7753099.original.md): сохранённые без изменений наброски из репозитория.

## Репозиторий

Рабочая папка привязана к [DanilaSaraev-git/MTS_TZ](https://github.com/DanilaSaraev-git/MTS_TZ), приватному репозиторию; `origin` указывает на него, `main` отслеживает `origin/main`. История сохранена. Исходная точка импорта — коммит `77530996790b6b1ad7b5e58b52ac9ff9605b287c` от 2026-09-03.

По новому поручению пользователя [CONTEXT_PACK_MTS.md](CONTEXT_PACK_MTS.md) обновлён до версии 2 и остаётся в корне; исходная версия S-07 сохранена в `MTS/sources/` — [D-08](knowledge/decisions.md). Остальные материалы кейса находятся в `MTS/`; общие гипотезы и методика — в `knowledge/`. Название репозитория не меняет направление продукта для нескольких компаний.

## Инструкции агентам

[AGENTS.md](AGENTS.md) содержит правила работы. `CLAUDE.md -> AGENTS.md` использует те же инструкции без отдельной копии. Используем имена файлов в верхнем регистре.

В проект подключён GitHub Spec Kit 1.0.4 для Codex: [навыки](.agents/skills/) вызываются через `$speckit-specify`, `$speckit-clarify`, `$speckit-plan` и другие имена `$speckit-*`; [служебные файлы](.specify/) содержат шаблоны и скрипты. [Указатель принципов Spec Kit](.specify/memory/constitution.md) отсылает к `AGENTS.md`. Установка инструмента не означает начала реализации продукта.

Следующие направления: провести экспертную оценку PoC на новом контрольном документе по [плану проверки](knowledge/discovery-plan.md), уточнять гипотезы и поддерживать [таймлайн](knowledge/roadmap.md). Сравнение Docling и pdfplumber остаётся отдельной технической проверкой; текущий PoC использует pdfplumber по поручению пользователя.
