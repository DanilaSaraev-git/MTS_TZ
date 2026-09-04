# Swagger UI

Страница [index.html](index.html) визуализирует канонический
[openapi.yaml](../openapi.yaml) без копирования или генерации схемы.

Из корня репозитория запустите статический сервер:

```bash
python3 -m http.server 8080
```

После этого откройте:

<http://localhost:8080/contracts/review-platform/v1/swagger/>

Swagger UI загружается с CDN в зафиксированной версии `5.32.11`; для первого
открытия нужен доступ к интернету. Внешний Swagger Validator отключён. Кнопка
Try it out начнёт выполнять запросы только когда страница и backend доступны
через один origin с `/api`, как задано в `openapi.yaml`.
