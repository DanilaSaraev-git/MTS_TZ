# Quickstart и проверка PoC

Запуск из корня репозитория. Python 3.11+ и uv. Установка скачивает зависимости; последующие CLI-команды работают локально. Агент и модель предоставляются твоей средой.

```bash
cd implementation/poc/review-data-spec
uv sync --frozen --extra test
uv run --frozen pytest
uv run --frozen review-data-spec run-demo --output-root .local-runs
```

Открой report.md по пути из stdout. generation.mode=demo_fixture означает заранее заданный синтетический результат, а не анализ моделью.

## Реальное ревью

```bash
uv run --frozen review-data-spec prepare /absolute/path/spec.pdf --output-root /absolute/path/runs --context /absolute/path/context.md
```

Прочитай [SKILL.md](../../implementation/poc/review-data-spec/SKILL.md) в среде агента. Агент читает профиль, manifest, bundle и при необходимости оригинал; создаёт report.json по report.template.json и [формату](../../implementation/poc/review-data-spec/references/report-format.md), указывая фактический охват и модель либо unknown.

```bash
uv run --frozen review-data-spec validate /absolute/path/runs/RUN_ID
uv run --frozen review-data-spec render /absolute/path/runs/RUN_ID
```

Коды и параметры: [контракт CLI](contracts/cli.md). Invalid даёт exit 2; partial может быть технически валидным, но не полным ревью. Исходное ТЗ остаётся неизменным.

## Проверка на клиентском примере

Из корня репозитория, после установки:

```bash
implementation/poc/review-data-spec/.venv/bin/review-data-spec prepare 'MTS/Тестовые данные.pdf' --profile MTS/experiments/poc-review-data-spec/profile.json --output-root MTS/experiments/poc-review-data-spec
```

Профиль явно подключает три заданных материала. Смысловой отчёт и протокол сохраняются в папке запуска; клиентские данные не нужны для run-demo/pytest. Результаты и пределы проверки: [протоколы MTS](../../MTS/experiments/poc-review-data-spec/README.md).

## Перенос

Скопируй всю папку review-data-spec (без .venv, .local-runs, кэшей) в каталог навыков своей агентной среды либо открой SKILL.md явно. В копии повтори uv sync --frozen --extra test и run-demo. Альтернатива без uv: `python -m venv .venv`, затем `.venv/bin/python -m pip install .` и `.venv/bin/review-data-spec --help`; точное транзитивное окружение обеспечивает uv.lock.

Проверяемые исходы: новое имя запуска; сохранённый документ и хеш; цитаты и номера страниц/строк; все замечания после сортировки; invalid для ложной цитаты; partial для непрочитанного фрагмента. Автотесты используют синтетические данные.

## Экспертная оценка после технической проверки

Для каждого замечания человек фиксирует confirmed/rejected/needs_context, причину, полезность, дубль и пропущенные проблемы; отдельно время чтения и исправления. Полезность и полнота без такой разметки неизвестны. Размер выборки и численные пороги не согласованы.

## Фактически проверено 2026-09-04

- `uv sync --frozen --extra test` и 12 тестов прошли на macOS с Python 3.13.0; пакет требует Python 3.11+, другие ОС и версии не проверялись.
- Чистая копия папки навыка установилась отдельно и выполнила pytest и run-demo вне репозитория.
- Поведенческий агентный сценарий прошёл на синтетике с противоречием, отсутствующим правилом, корректной частью и инструкцией внутри ТЗ как данными; структура и цитаты получили `complete`.
- Прогон `mts-test-data-20260904-agent` подготовил 141 фрагмент из PDF и трёх материалов контекста, сохранил хеши и прошёл validate/render; оригинальные 9 страниц визуально сверены.
- Навык прошёл штатный `skill-creator/quick_validate.py`. Экспертная и независимая проверка не проводилась.
