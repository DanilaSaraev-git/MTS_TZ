# CLI contract v1

Запуск: `review-data-spec <command>` после установки пакета либо `python /path/to/review-data-spec/scripts/review_data_spec.py <command>` с установленными зависимостями. Пути с пробелами заключаются в кавычки. Локальное чтение, без сети/SDK модели.

## prepare

`prepare INPUT --output-root DIR [--run-id ID] [--profile FILE] [--context FILE ...]`

INPUT: PDF с текстом, UTF-8 MD/TXT. Каждый --context добавляет файл; пути CLI относительно cwd, context_files профиля относительно самого профиля. По умолчанию базовый профиль и pdfplumber. ID: буква/цифра в начале, далее буквы/цифры/точка/дефис/подчёркивание, до 80 символов; по умолчанию UTC-время + случайный суффикс. Существующий ID отклоняется.

Создаёт DIR/ID: manifest.json, bundle.json, profile.json, settings.json, report.template.json, sources/ и raw/. Оригиналы копируются побайтово; хеши и версии фиксируются. Шаблон отчёта имеет пустые findings, весь охват unreviewed; это не готовое ревью. stdout — JSON с run_dir, run_id и diagnostics.

Повреждённый/пустой основной документ — ошибка без опубликованной папки запуска. Недоступный или неподдерживаемый контекст — unavailable + причина. Частично пустой PDF — предупреждение и partial coverage.

## validate

`validate RUN_DIR [--report FILE]`

По умолчанию RUN_DIR/report.json. Проверяет JSON Schema, run-id, целостность снимка, ссылки, нормализованные цитаты, отсутствие дубликатов ID, разбиение coverage, наличие оснований в ТЗ и независимость human_review. Пишет RUN_DIR/validation.json с valid, errors, coverage_status и report_sha256; stdout — тот же JSON. При invalid exit 2. Корректный partial отчёт exit 0 с явным coverage_status=partial. Совпадение цитаты не означает подтверждение вывода.

## render

`render RUN_DIR [--report FILE] [--output FILE]`

Сначала повторная validate актуального отчёта. По умолчанию RUN_DIR/report.md. При invalid выход 2, отчёт не создаётся. Markdown: сводка, происхождение/профиль/модель, охват, источники и диагностика, весь список high/medium/low, причины/вопросы/статусы, ссылки на снимки с координатами, ограничения. Внешний output разрешён с корректными относительными ссылками; перезапись входов/подготовленных артефактов запрещена. Существующий собственный report.md допускает повторный render.

## run-demo

`run-demo --output-root DIR [--run-id ID]`

Создаёт синтетический документ, prepare, фиксированный report.json (mode=demo_fixture), validate, render. Не принимает клиентский PDF и не вызывает модель. stdout: run_dir и путь report.md. Идемпотентность по содержимому входа/привязкам, а не по run-id; повторный ID отклоняется. Реальный сценарий: prepare → агент читает SKILL.md и bundle → пишет report.json → validate/render.

## Errors

Успех exit 0. Ошибки использования, входа, формата или целостности exit 2, диагностика JSON (argparse usage — обычный stderr). Неожиданные ошибки разработки не скрываются под успешным результатом. Исходники не изменяются; подготовленные снимки не перезаписываются.
