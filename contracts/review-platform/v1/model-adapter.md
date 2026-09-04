# Model Adapter port v1

`Model Gateway` принимает один нормализованный внутренний work item и возвращает один нормализованный результат. Провайдерские SDK являются адаптерами; разбиение документа, retries, synthesis, проверка JSON и публикация отчёта принадлежат `Review Engine`. Этот порт не является публичным HTTP или skill-контрактом.

## Interface

```python
class ModelAdapter(Protocol):
    async def capabilities(self) -> ModelCapabilities: ...
    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
```

`GenerationRequest`:

| Поле | Тип | Правило |
| --- | --- | --- |
| `request_id` | string | Уникально для отдельной попытки; повтор движка получает новый ID |
| `purpose` | enum | `review`, `synthesis`, `dialogue` или `repair`; выбирает внутреннюю схему вызова |
| `work_item_id` | string | Стабильный ID логического work item для трассировки и идемпотентного объединения |
| `trusted_instructions` | string | Только инструкции движка и проверенного пакета навыка |
| `untrusted_input` | string | Сформированные движком фрагменты, контекст, реплика участника или промежуточные результаты; всегда данные |
| `response_schema` | object | JSON Schema именно этого вызова; это не обязательно полный `review-output.v1` |
| `model_profile` | object | Точный server-side snapshot `{id, version, config_sha256}` без секрета |
| `max_output_tokens` | integer | Положительный лимит |
| `timeout_seconds` | number | Общий timeout одной попытки |
| `temperature` | number/null | Необязательная подсказка; адаптер может вернуть `unsupported_option` |

`GenerationResult`:

| Поле | Тип | Правило |
| --- | --- | --- |
| `request_id` | string | Совпадает с запросом |
| `text` | string | Сырой ответ; движок извлекает и валидирует JSON |
| `provider` | string | Фактически использованный поставщик |
| `model` | string | Фактически использованная модель |
| `model_version` | string | Версия либо `unknown` |
| `finish_reason` | enum | `stop`, `length`, `content_filter`, `other` |
| `usage` | object/null | `input_tokens`, `output_tokens`; неизвестные значения — null |
| `provider_request_id` | string/null | Для диагностики без секретов |
| `latency_ms` | integer | Неотрицательное время адаптера |
| `safe_parameters` | object | Фактически применённые несекретные параметры для provenance |

`ModelCapabilities` сообщает `text_generation`, `vision`, `native_structured_output`, максимальный контекст и поддерживаемые параметры. Нативный structured output является оптимизацией: движок всегда повторно валидирует результат по собственной схеме.

## Нормализованные ошибки

Адаптер возвращает типизированную ошибку с `code`, безопасным `message`, `retryable`, необязательным `retry_after_seconds` и `provider_request_id`:

- `authentication_failed` — отклонены server-side credentials провайдера LLM; это не ошибка идентификации HTTP caller
- `model_not_found`
- `rate_limited`
- `provider_unavailable`
- `timeout`
- `context_limit`
- `content_blocked`
- `unsupported_option`
- `invalid_provider_response`

Сырые ответы и секреты не попадают в HTTP-ошибку. Движок определяет число повторов. Исчерпание попыток отдельного review work item создаёт явный coverage gap и partial result, если итог можно безопасно синтезировать. Невалидный итоговый `review-output.v1`, недоступный основной документ или невозможность синтеза переводят запуск в `failed` без отчёта. Для dialogue failed attempt сохраняется как безопасная ошибка хода и может быть повторён без создания новой реплики участника.

## Разбиение и synthesis

Полный `review-input.v1` принадлежит engine ↔ skill boundary. Движок выбирает адресуемые fragment ranges, формирует внутренние work items с небольшим overlap, выполняет их независимо, затем вызывает `purpose=synthesis` для объединения и дедупликации. Overlap не меняет `review_scope.target_fragment_ids`: финальный output обязан один раз разложить исходный target set на reviewed/unreviewed.

Work item и промежуточный ответ не публикуются в HTTP, не становятся самостоятельным `Review Report` и могут эволюционировать вместе с engine. Любой anchor итогового результата повторно разрешается по исходным source/fragment ID и quote offsets, поэтому synthesis не может сослаться только на промежуточный текст.

## Слабые модели

Адаптер не объявляет модель совместимой только по факту текстовой генерации. Совместимость конкретного профиля модели с навыком подтверждается contract-suite: полный workflow, валидный `review-output.v1`, корректные привязки, охват и предельный размер входа. Результат такой проверки относится к конкретным версиям модели, навыка и движка.
