# Tasks: PoC ревью ТЗ

**Input**: [spec](spec.md), [plan](plan.md), [research](research.md), [data model](data-model.md), [CLI](contracts/cli.md).

Тесты прямо запрошены пользователем. Путь P ниже для чтения означает implementation/poc/review-data-spec; в задачах указаны полные пути от корня.

## Phase 1: Setup

- [X] T001 Создать пакет и фиксированные зависимости в implementation/poc/review-data-spec/pyproject.toml и uv.lock.
- [X] T002 Настроить исключения локальных артефактов в .gitignore, сохранив исходные исключения.

## Phase 2: Foundational

- [X] T003 Создать общие операции JSON/hash/проверки путей в implementation/poc/review-data-spec/scripts/review_data_spec/__init__.py.
- [X] T004 Создать контракт профиля и базовый профиль в implementation/poc/review-data-spec/scripts/review_data_spec/resources/.

## Phase 3: US1 — Подготовка (P1)

Цель: снимок с проверяемыми адресами. Независимая проверка: повторная подготовка текста/PDF, таблицы, пустые и повреждённые входы.

- [X] T005 [US1] Написать и запустить падающие тесты подготовки в implementation/poc/review-data-spec/tests/test_prepare.py.
- [X] T006 [US1] Реализовать ParserAdapter, PDF и UTF-8 адаптеры в implementation/poc/review-data-spec/scripts/review_data_spec/parsers.py.
- [X] T007 [US1] Реализовать prepare, снимки, хеши, диагностику и шаблон отчёта в implementation/poc/review-data-spec/scripts/review_data_spec/prepare.py; добиться прохождения T005.

## Phase 4: US2 — Адресное ревью (P1)

Цель: проверяемый отчёт, отсутствие требования и честный охват. Независимая проверка: позитивные/негативные отчёты и ручное чтение агентом.

- [X] T008 [US2] Написать падающие тесты цитат, scope, охвата, повреждения и пустого результата в implementation/poc/review-data-spec/tests/test_validation.py.
- [X] T009 [US2] Реализовать report.schema.json и validate в implementation/poc/review-data-spec/scripts/review_data_spec/validation.py.
- [X] T010 [US2] Реализовать render с полным списком и адресами в implementation/poc/review-data-spec/scripts/review_data_spec/render.py; добиться прохождения T008.
- [X] T011 [US2] Написать переносимые инструкции в implementation/poc/review-data-spec/SKILL.md и references/; проверить противоречие, отсутствие, корректный документ и инструкцию внутри ТЗ реальным агентом.

## Phase 5: US3 — Профиль и приоритеты (P2)

Цель: отдельный контекст клиента и ранжирование без потери замечаний. Независимая проверка: базовый/два независимых профиля, недоступный контекст, конфликт правил.

- [X] T012 [US3] Добавить проверки изоляции профилей, относительных путей и сортировки в implementation/poc/review-data-spec/tests/test_prepare.py и test_validation.py.
- [X] T013 [US3] Завершить обработку профилей/приоритетов в implementation/poc/review-data-spec/scripts/review_data_spec/prepare.py и render.py; сохранить черновой client-materials/experiments/poc-review-data-spec/profile.json.

## Phase 6: US4 — Перенос и демонстрация (P2)

Цель: установка и end-to-end. Независимая проверка: subprocess CLI вне репозитория и клиентский агентный отчёт.

- [X] T014 [US4] Написать падающие CLI-тесты в implementation/poc/review-data-spec/tests/test_cli.py.
- [X] T015 [US4] Реализовать prepare/validate/render/run-demo CLI и synthetic fixture в implementation/poc/review-data-spec/scripts/review_data_spec/cli.py, demo.py и scripts/review_data_spec.py.
- [X] T016 [US4] Установить отдельную копию навыка без базы разработчиков; проверить pytest и run-demo по specs/001-review-data-spec-poc/quickstart.md.
- [X] T017 [US4] Провести агентное ревью PDF, визуально сверить проблемные страницы, сохранить отчёт и протокол в client-materials/experiments/poc-review-data-spec/<run-id>/.

## Phase 7: Polish

- [X] T018 Обновить карту README.md, client-materials/README.md, implementation/poc/PLAN.md, product-knowledge/decisions.md, sources.md и roadmap.md по фактическому результату.
- [X] T019 Проверить markdown-ссылки, CLAUDE.md → AGENTS.md, git ignore, исходные хеши и весь контракт; записать результаты в specs/001-review-data-spec-poc/quickstart.md.

## Dependencies & Execution Order

T001–T004 → T005–T007 (US1) → T008–T011 (US2) → T012–T013 (US3) → T014–T017 (US4) → T018–T019. Тесты перед соответствующей реализацией. Встроенный requirements checklist проверяется до implement и далее не меняется.

Независимые чтения и тестовые процессы можно запускать параллельно: US1 — PDF и TXT fixtures; US2 — schema и цитаты; US3 — два профиля; US4 — копия и read-only сверка PDF. Это возможности исполнения после зависимостей, не отдельное поручение новым агентам.

## Implementation Strategy

Последовательно довести каждый сценарий до проверяемого результата. Минимальная первая контрольная точка — US1; пользователь поручил все четыре истории, поэтому после проверок продолжить до полного PoC. Продуктовые гипотезы и экспертную оценку не отмечать завершёнными вместо технических задач.
