# Оценка реализации продукта как приложения Confluence и обзор аналогов

**Дата проверки:** 2026-09-04  
**Статус:** исследовательская оценка по официальной документации Atlassian; прототип не собирался, клиентская среда и требования ИБ не подтверждены  
**Применимость:** техническая часть подробно относится к Confluence Cloud. Для Confluence Data Center нужна отдельная оценка и другая технология расширения. Обзор аналогов не является исчерпывающим реестром Marketplace.

## Краткий ответ

Да, продукт технически можно сделать приложением для Confluence Cloud. Для нового приложения разумная основа — **Forge**, а не Connect. Оно сможет получать сохранённый текст страницы, вложения, комментарии и версии, запускать анализ вручную или по событию, показывать статус рядом с заголовком и возвращать замечания в собственном окне или в виде inline-комментариев.

Это не означает, что продукт нужно уже сейчас переводить в Confluence. В текущем кейсе MTS интеграция с Confluence не подтверждена как обязательная, исходные примеры представлены PDF-файлами, а тип инсталляции клиента — Cloud или Data Center — неизвестен. Поэтому Confluence пока лучше считать **каналом поставки и UX-адаптером**, сохраняя ядро проверки независимым от платформы.

## Факты платформы

Ниже перечислены подтверждённые возможности платформы. Продуктовые выводы и предложения вынесены в отдельные разделы.

### 1. Варианты реализации

| Вариант | Подтверждённый статус | Что даёт продукту |
|---|---|---|
| **Forge с размещением у Atlassian** | Forge — облачная платформа Atlassian для приложений; вычисления, хранение, права и UI-модули управляются платформой ([Forge platform](https://developer.atlassian.com/platform/forge/introduction/the-forge-platform/)). | Наиболее нативный вариант для Confluence Cloud. Подходит для UI, доступа к REST API, хранения результатов и фоновых заданий. |
| **Forge LLMs API** | Forge-приложение может вызывать размещённые Atlassian языковые модели без выхода данных за пределы платформы; добавление LLM к существующему приложению требует major upgrade и одобрения администратора ([overview](https://developer.atlassian.com/platform/forge/runtime-reference/forge-llms-api/), [API reference](https://developer.atlassian.com/platform/forge/runtime-reference/forge-llms-api-reference/)). Сейчас поддерживаются только текстовые входы и выходы ([models](https://developer.atlassian.com/platform/forge/runtime-reference/forge-llms-models/)). | Потенциально самый простой путь к AI-анализу страниц с маркировкой `Runs on Atlassian`. Не решает сам по себе извлечение текста из PDF, OCR и проверку качества модели на русских ТЗ. |
| **Forge + Forge Remote** | Forge может вызывать собственный внешний backend и получать контекст для вызовов Atlassian API ([Forge Remote](https://developer.atlassian.com/platform/forge/remote/), [Remote essentials](https://developer.atlassian.com/platform/forge/remote/essentials/)). Внешние домены нужно явно декларировать в разрешениях ([permissions](https://developer.atlassian.com/platform/forge/manifest-reference/permissions/)). | Нужен, если используются собственная модель, Python/OCR, сложный PDF-парсер, RAG или корпоративный inference endpoint. Передача содержимого наружу добавляет требования ИБ, privacy и data residency. |
| **Rovo Agent поверх Forge** | Forge поддерживает Rovo agents и actions. Агент доступен из Rovo Chat, AI toolbar редактора Confluence, Automation и некоторых программных UI-точек ([Rovo agent module](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-agent/), [Rovo modules](https://developer.atlassian.com/platform/forge/manifest-reference/modules/rovo-index/)). | Удобен как диалоговый слой для уточняющих вопросов и разбора замечаний. Не обязателен для основного сценария «запустить проверку и получить структурированный отчёт». |
| **Atlassian Connect** | Новые Connect-приложения больше нельзя публиковать; Atlassian направляет новую расширяемость в Forge ([Connect descriptor notice](https://developer.atlassian.com/cloud/confluence/connect-app-descriptor/)). Для новых Marketplace-приложений Jira/Confluence с 17 сентября 2025 года требуется Forge, а окончание поддержки Connect объявлено на 31 января 2027 года ([timeline](https://www.atlassian.com/blog/development/getting-ready-for-connect-end-of-support)). | Для нового продукта нецелесообразен. Наличие старых Connect-аналогов на Marketplace не делает Connect подходящим архитектурным выбором. |
| **Плагин для Confluence Data Center** | Data Center использует отдельную серверную модель приложений и отдельный plugin SDK ([Data Center developer docs](https://developer.atlassian.com/server/confluence/), [plugin guide](https://developer.atlassian.com/server/confluence/confluence-plugin-guide/)). | Forge/Rovo-реализация для Cloud не устанавливается в Data Center. Если у клиента on-prem/Data Center, потребуется отдельная архитектура и отдельная оценка поставки. |

### 2. Доступ к данным Confluence

| Объект | Возможность и требуемый доступ | Значение для продукта |
|---|---|---|
| **Страницы** | Confluence REST API v2 позволяет получить страницу по ID и запросить тело в поддерживаемом формате; доступ ограничивается правами пользователя/приложения и OAuth scope, например `read:page:confluence` ([Pages API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/)). API также различает состояния содержимого и версии. | Можно проверять опубликованную или сохранённую версию страницы и привязывать результат к `pageId` и номеру версии. |
| **Черновики и редактор** | API страницы поддерживает работу со статусами содержимого, но каталог Forge UI-модулей не описывает универсального hook, который перехватывает каждое изменение произвольной страницы в редакторе ([Pages API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/), [Confluence modules](https://developer.atlassian.com/platform/forge/manifest-reference/modules/index-confluence/)). Macro — отдельный вставляемый блок, а context menu действует по выделенному тексту на странице. | Доступ к сохранённому draft возможен в рамках API и прав, но «подчёркивание замечаний во время набора» нельзя считать подтверждённой возможностью. |
| **Вложения** | Можно перечислить вложения страницы и получить metadata, media type, размер, download link и версию; бинарное содержимое скачивается отдельным endpoint ([Attachments v2](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-attachment/), [download endpoint](https://developer.atlassian.com/cloud/confluence/rest/v1/api-group-content---attachments/)). Scope — `read:attachment:confluence`. | PDF технически доступен приложению. Текст, таблицы и сканы придётся извлекать собственным кодом или внешним сервисом. |
| **Комментарии** | API позволяет читать page footer и inline comments, а также создавать их. Для inline comment передаются свойства выделения, включая текст и индекс совпадения; есть состояние разрешения комментария ([Comments API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comment/)). Scopes — `read:comment:confluence` и, для записи, `write:comment:confluence`. | Замечание можно вернуть к конкретному фрагменту и оставить решение человеку. Устойчивость якоря после правок и неоднозначность одинаковых фрагментов требуют проверки. |
| **История** | REST API v2 отдаёт список и детали версий страниц, комментариев и вложений; для страницы доступны номер версии, автор, дата, сообщение и тело в запрошенном формате ([Versions API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-version/)). | Можно повторно проверять только новую версию и сравнивать её с предыдущей. Семантический diff и перенос статуса замечаний должен реализовать сам продукт. |
| **Ограничение доступа** | API возвращает только то, что разрешено пользователю/приложению; администратор организации может блокировать доступ приложения к выбранным Confluence spaces ([app access rules](https://support.atlassian.com/security-and-access-policies/docs/block-app-access/), [developer guide](https://developer.atlassian.com/cloud/confluence/data-security-policy-developer-guide/)). | Нельзя предполагать доступ ко всей базе. Интерфейс должен корректно показывать частичную недоступность, а индексацию лучше начинать с явно выбранных страниц/пространств. |

Изменение страницы через API также возможно, но Atlassian предупреждает о согласовании текущего тела с существующим draft при update ([Pages API](https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-page/)). Для первого сценария безопаснее создавать отчёт или комментарии, а не автоматически переписывать исходный документ.

### 3. UI-точки и события

Forge предоставляет следующие подходящие точки интерфейса ([каталог Confluence modules](https://developer.atlassian.com/platform/forge/manifest-reference/modules/index-confluence/)):

- **Content action** — пункт в меню `…` страницы или блога, который открывает modal. Это нативная точка для команды «Проверить документ» ([module reference](https://developer.atlassian.com/platform/forge/manifest-reference/modules/confluence-content-action/)).
- **Content byline item** — строка под заголовком страницы с динамическими title/icon/tooltip. Подходит для состояния «не проверено / проверяется / есть замечания / проверено» ([module reference](https://developer.atlassian.com/platform/forge/manifest-reference/modules/confluence-content-byline-item/)).
- **Context menu** — действие после выделения текста на опубликованной странице. Подходит для проверки одного фрагмента ([tutorial](https://developer.atlassian.com/platform/forge/create-confluence-contextmenu-module/)).
- **Global page или space page** — отдельный экран приложения со сводкой проверок, фильтрами и историей.
- **Macro** — вставляемый через редактор динамический блок. Это самостоятельный блок контента, а не общий перехватчик всего редактора ([macro reference](https://developer.atlassian.com/platform/forge/manifest-reference/modules/macro/)).
- **Inline comments** — нативный канал результата через REST API; он не является Forge UI-модулем, но появляется на самой странице.

Forge-события включают создание и обновление страниц, lifecycle live docs, создание/обновление комментариев и вложений. Для live docs есть события инициализации, начала редактирования, snapshot и публикации ([Confluence events](https://developer.atlassian.com/platform/forge/events-reference/confluence/)). Событие несёт контекст, после чего приложение может запросить актуальное содержимое через REST API.

Обычный UI-вызов Forge ограничен по времени, поэтому длительный AI-анализ следует ставить в очередь. Async Events API предназначен в том числе для AI и допускает длительные consumer-вызовы; актуальные лимиты приведены в документации ([Async Events API](https://developer.atlassian.com/platform/forge/runtime-reference/async-events-api/), [invocation limits](https://developer.atlassian.com/platform/forge/limits-invocation/)). Для Forge LLM также действуют отдельные лимиты запросов, токенов и inference ([LLM limits](https://developer.atlassian.com/platform/forge/limits-llm/)).

### 4. AI, безопасность и размещение данных

- **Нативный AI.** Forge LLMs выполняет LLM-вызовы внутри платформы Atlassian и сохраняет право на `Runs on Atlassian`; запросы проходят такую же модерацию, как AI-функции Atlassian и Rovo ([Forge LLMs](https://developer.atlassian.com/platform/forge/runtime-reference/forge-llms-api/)). Использование LLM явно показывается администратору при установке.
- **Rovo зависит от политики клиента.** Доступ к Atlassian AI/Rovo управляется администратором организации; сервис недоступен в Atlassian Government Cloud ([Atlassian Intelligence/Rovo administration](https://support.atlassian.com/organization-administration/docs/what-is-atlassian-intelligence/)). Поэтому критический сценарий приложения не стоит делать зависимым только от Rovo UI.
- **Atlassian-hosted-only для Rovo.** Enterprise-клиенты могут запросить режим Atlassian-hosted LLMs only. Он ограничивает выход данных за границу Atlassian Cloud, но не обещает выполнение в конкретном data residency realm ([Atlassian-hosted LLMs](https://support.atlassian.com/organization-administration/docs/atlassian-hosted-llms/)). Это свойство Rovo, а не произвольного внешнего backend.
- **Внешняя модель.** При Forge Remote домены egress декларируются в manifest. Если пользовательский контент уходит во внешний сервис, приложение обычно не соответствует критериям `Runs on Atlassian`, кроме ограниченных разрешённых категорий egress ([Runs on Atlassian](https://developer.atlassian.com/platform/forge/runs-on-atlassian/)). Это не запрещает приложение, но меняет его security/privacy-профиль.
- **Data residency.** Hosted storage Forge поддерживает pinning и migration вместе с Atlassian app; remote можно сделать `PINNED`, если развернуть endpoints по поддерживаемым регионам. В списке поддерживаемых locations есть, например, EU, Germany, UK, US и ряд других регионов, но нет России. Atlassian отдельно указывает, что compute стремится выполняться в регионе данных, но иногда может выполняться вне него ([Forge data residency](https://developer.atlassian.com/platform/forge/data-residency/)).
- **Модель ответственности.** Разработчик отвечает за минимальные scopes, проверку разрешений, валидацию ввода и безопасное применение `asUser()`/`asApp()` ([shared responsibility](https://developer.atlassian.com/platform/forge/shared-responsibility-model/)). Для Rovo actions Atlassian отдельно требует защищаться от prompt injection и утечки данных ([Marketplace security requirements](https://developer.atlassian.com/platform/marketplace/security-requirements/)).

Следствие именно для MTS нельзя считать установленным фактом: если требуется российский контур, on-prem или полный запрет передачи документа в облачный AI, стандартная Forge Cloud-архитектура может не пройти ИБ. Это нужно подтвердить с клиентом до технического выбора.

### 5. Публикация и монетизация

- Для пилота Forge-приложение можно установить в собственный site или распространять через install link; администратор сайта подтверждает установку. После включения licensing или подачи этой версии в Marketplace install-link sharing для неё больше недоступен, поэтому Atlassian рекомендует отдельную unlicensed-копию для тестирования ([distribution](https://developer.atlassian.com/platform/forge/distribute-your-apps/)).
- Публичное приложение требует Marketplace listing и проверки Atlassian. Нужны документация, privacy policy, terms, support, обоснование scopes, раскрытие внешних сервисов и ответы в Privacy & Security tab; применяются security checks и проверка партнёра ([listing](https://developer.atlassian.com/platform/marketplace/creating-a-marketplace-listing/), [approval guidelines](https://developer.atlassian.com/platform/marketplace/app-approval-guidelines/), [security workflow](https://developer.atlassian.com/platform/marketplace/app-approval-security-workflow/)).
- Платное Forge-приложение для Confluence публикуется с `app.licensing.enabled` и, если Atlassian не дал исключение, использует Paid via Atlassian ([pricing and billing](https://developer.atlassian.com/platform/marketplace/pricing-payment-and-billing/), [Marketplace Partner Agreement](https://www.atlassian.com/licensing/marketplace/partneragreement)). Стандартная Cloud-лицензия рассчитывается по размеру всего Confluence site, а не по числу активных аналитиков.
- User-based billing для Forge находится в EAP и пока не поддерживает публикацию приложения в Marketplace ([user-based billing](https://developer.atlassian.com/platform/forge/adopt-user-based-billing/)). На него нельзя опирать текущую бизнес-модель.
- Для pure Forge apps действует льготная revenue share: 100% gross revenue до первых $1 млн lifetime Forge revenue партнёра; после порога — 84% до 30 сентября 2026 года и 83% с 1 октября 2026 года ([pricing and billing](https://developer.atlassian.com/platform/marketplace/pricing-payment-and-billing/)). Forge Remote может оставаться pure Forge, если приложение не содержит Connect/OAuth-модулей и соответствует остальным критериям.
- Вычисления, хранилище, логи и Forge LLM тарифицируются разработчику по правилам Forge; для Forge LLM нет бесплатного allowance ([Forge platform pricing](https://developer.atlassian.com/platform/forge/forge-platform-pricing/), [Forge LLM pricing](https://developer.atlassian.com/platform/forge/runtime-reference/forge-llms-api-pricing/)). У Rovo agents запросы расходуют пул Rovo credits клиента ([Forge platform pricing](https://developer.atlassian.com/platform/forge/forge-platform-pricing/)).

Текущие тарифы, revenue share и статусы EAP могут измениться; перед коммерческим запуском их нужно перепроверить.

## Существующие решения и граница новизны

Публично описанные решения подтверждают, что сама категория «AI проверяет требования до разработки» уже существует. На дату проверки не найден зрелый Confluence-продукт, который публично заявляет весь наш предполагаемый контур: длинное ТЗ на поток или витрину данных, клиентский профиль и контекст, адресное замечание с причиной и вопросом, приоритет, подтверждение человеком и измерение полезности. Это результат кабинетного поиска, а не доказательство отсутствия такого решения на рынке.

| Решение | Подтверждённая возможность | Отличие от текущей продуктовой гипотезы |
|---|---|---|
| [Atlassian Rovo: Product requirements expert](https://www.atlassian.com/software/rovo/use-cases/agent-product-requirements-expert) | Встроенный агент находит контекст в Confluence и Jira, читает страницу по URL, создаёт страницы или комментарии и предлагает сценарий `Review my PRD`. Rovo-агента также можно запускать из Automation ([пример Atlassian](https://www.atlassian.com/software/rovo/guides/admin-guide/rovo-walkthrough)). | Главный заменитель универсального «AI reviewer for Confluence». Публичное описание не обещает специализированные проверки потоков и витрин, устойчивый контракт замечания и наш протокол оценки качества. |
| [CN2](https://marketplace.atlassian.com/apps/1236194/cn2) | AI Requirements Copilot для Confluence Cloud и Jira Cloud; заявлены автоматизация сбора требований, impact analysis и создание документации. | Концептуально близкий Confluence-аналог, но публичная карточка не раскрывает формат адресных замечаний, качество на длинных таблицах и data-engineering специализацию. |
| [Requirement Yogi](https://marketplace.atlassian.com/apps/1212523/requirement-yogi-requirements-management-for-confluence?hosting=cloud&tab=overview) | Управление требованиями в Confluence: типы и validation rules, traceability matrices, baselines, варианты требований и интеграция с Jira. | Сильный конкурент за структуру и governance; смысловой AI-анализ неоднозначностей и логики в карточке не заявлен. |
| [Scroll Content Quality](https://marketplace.atlassian.com/apps/1224799/scroll-content-quality-for-confluence?hosting=cloud&tab=overview) | Настраиваемый linting текста, структуры, ссылок, изображений и макросов, severity и отчёты на уровне страницы и пространства. | UX проверки близок, но предмет — стиль, структура и качество контента, а не достаточность технических требований для реализации. |
| [Spexsure](https://marketplace.atlassian.com/apps/2129757973/spexsure) | Jira Cloud app проверяет PRD по инженерным категориям, маркирует gaps по severity, оставляет принятие или отклонение человеку и формирует backlog; принимает PDF, DOCX, Markdown и текст. | Самый близкий по ценности, но не Confluence-native и публично не заявляет клиентский профиль для потоков и витрин данных. |
| [Story Analyser](https://marketplace.atlassian.com/apps/1219686/story-analyser-for-jira) и [EthicGuard](https://marketplace.atlassian.com/apps/914032111/ethicguard-ai-acceptance-criteria-review-gate) | Проверяют Jira stories и acceptance criteria на качество, неоднозначность, пропуски или противоречия; EthicGuard добавляет readiness gate. | Подтверждают наличие категории, но работают с Jira work items, а не с полным техническим документом в Confluence. |

Нативный Rovo делает слабой позицию «ещё один AI-помощник для Confluence»: в платных Cloud-планах уже доступны AI-функции, агенты, организационный контекст и Automation ([возможности Rovo в Confluence](https://support.atlassian.com/confluence-cloud/docs/atlassian-intelligence-features-in-confluence-cloud/)). Клиент также может собрать кастомного агента без отдельного продукта.

Предполагаемое свободное окно уже: **quality gate для спецификаций потоков и витрин данных, встроенный в Confluence**. Возможная дифференциация — проверки схем, полей и `NULLABLE`, фильтрации, временных правил, Kafka/HDFS, обновления и расчётной логики; версионированный профиль компании; ссылки на конкретное правило; human-in-the-loop; история принятых и отклонённых замечаний; измерение пропусков, шума и времени разбора. Наличие окна не подтверждает спрос или готовность платить.

## Выводы для продукта

Это синтез источников применительно к текущей продуктовой рамке, а не принятое решение.

### Предпочтительная схема для Cloud-гипотезы

```text
Content action «Проверить документ»
    → получить сохранённое тело страницы и page version
    → поставить анализ в async queue
    → Forge LLMs либо внешний движок через Forge Remote
    → сохранить структурированный результат и статус
    → показать отчёт в modal / space page
    → после подтверждения человеком создать inline comments
```

В этой схеме:

- **ручной запуск** лучше подходит для первого эксперимента, чем автоматический анализ каждого изменения: он проще для пользователя, не создаёт лишние комментарии и лучше контролирует стоимость;
- **byline status** делает состояние проверки видимым без изменения текста документа;
- **inline comments** соответствуют принципу адресуемого замечания и оставляют решение человеку, но их стоит включать после подтверждения результатов в отчёте;
- **автоматический запуск** можно добавить позже по `page updated`, snapshot/publish live doc, метке или настройке пространства, с debounce и фиксацией проверенной версии;
- **Rovo Agent** полезен как опциональный разговорный слой: объяснить замечание, задать уточняющие вопросы, повторить проверку фрагмента. Ядро анализа и сохранённый результат не должны зависеть только от доступности Rovo;
- **автоматическое редактирование исходной страницы** для первой версии не рекомендуется: оно конфликтует с ролью человека как принимающего решение и несёт риск работы с параллельным draft.

### Граница архитектуры

Проверяющий движок целесообразно отделить от Confluence adapter:

```text
Confluence adapter: доступ, события, UI, комментарии
                    ↓
Независимое ядро: профиль проверки → findings → вопросы → evidence
                    ↑
Другие входы: PDF, DOCX, локальный skill, будущие интеграции
```

Такой шов сохраняет переносимость между компаниями и форматами документов. Для Cloud-приложения можно выбрать Forge LLMs, а для клиента с собственным inference — Remote, не меняя контракт результата.

## Гипотезы и открытые вопросы

| Вопрос | Почему блокирует решение | Как проверить |
|---|---|---|
| У MTS и других целевых клиентов Confluence Cloud или Data Center? | Forge-путь применим только к Cloud. | Уточнить тип и редакцию инсталляции у владельца среды. |
| ТЗ действительно живут как страницы, вложения или ссылки на внешние хранилища? | От этого зависит UX, парсинг и полнота анализа. | Разобрать 5–10 реальных рабочих документов и их путь публикации. |
| Разрешит ли ИБ установку Forge app и обработку содержимого LLM? | Возможны запрет egress, требование on-prem или регион, которого нет у Forge. | Согласовать data-flow diagram и список scopes с ИБ клиента. |
| Достаточно ли качества Forge LLMs для русских ТЗ, таблиц и текущего профиля проверки? | Нативное размещение полезно только при приемлемом качестве. | Сравнить на одном размеченном наборе Forge LLMs и текущий baseline по точности находок и ложным срабатываниям. |
| Какой результат предпочтительнее: modal/отчёт, inline comments или оба? | Комментарии нативны, но могут создавать шум и затрагивать рабочий процесс авторов. | Протестировать кликабельный сценарий с аналитиками и авторами ТЗ. |
| Насколько устойчив inline-якорь после редактирования и при повторяющемся тексте? | Потерянная адресация разрушает ключевую ценность продукта. | PoC с повторяющимися фрагментами и последующими правками страницы. |
| Приемлема ли цена за весь Confluence site, если продуктом пользуется малая группа аналитиков? | Стандартная Marketplace-лицензия может ухудшить unit economics. | Получить размеры типичных sites и willingness-to-pay; отдельно оценить private/enterprise contract. |
| Нужна ли автоматическая проверка при публикации? | Она повышает частоту использования, но расход, шум и риск дублей тоже растут. | Сначала измерить частоту ручных запусков и долю принятых замечаний. |

## Минимальный технический эксперимент

Не строить полноценный плагин, а проверить критические неизвестные в частной Forge-установке:

1. Добавить один `contentAction` на опубликованной тестовой странице.
2. Получить её тело и номер версии с правами текущего пользователя.
3. Поставить задачу в async queue и вернуть три заранее определённых или модельных замечания.
4. Показать их в modal; одно подтверждённое замечание записать как inline comment.
5. Повторить на draft, странице с одинаковыми фразами, PDF-вложении и в пространстве, закрытом app access rule.
6. Зафиксировать время до результата, полноту извлечения ADF/PDF, стабильность адресации, требуемые scopes и фактический data flow.

**Критерий продолжения гипотезы:** приложение читает разрешённый документ без обхода ACL, выдаёт структурированный результат для конкретной версии и надёжно привязывает подтверждённое замечание к фрагменту, не меняя исходную страницу. Качество самих замечаний оценивается отдельно по продуктовой методике.

## Рекомендация на текущем этапе

**Не менять принятую форму PoC на Confluence-приложение до подтверждения среды и рабочего процесса клиента.** Зафиксировать Forge-интеграцию как перспективную гипотезу канала поставки для Confluence Cloud.

Если Cloud и нативные комментарии подтвердятся как значимые, первым выбором выглядит Forge-приложение с ручным `contentAction`, async-анализом, byline-статусом и подтверждаемыми inline comments. Forge LLMs стоит проверить первым ради более простого security-профиля; Forge Remote оставить как альтернативу для собственного движка и сложного разбора PDF. Connect для новой разработки исключить, а Data Center оценивать отдельно.
