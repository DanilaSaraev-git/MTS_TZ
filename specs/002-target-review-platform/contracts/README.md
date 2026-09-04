# Feature 002 contract map

Машинные контракты вынесены в корневой версионируемый каталог, чтобы web и backend/skills могли создавать ветки от одного baseline и не копировать DTO.

| Boundary | Canonical artifact |
| --- | --- |
| React web ↔ backend | [OpenAPI v1](../../../contracts/review-platform/v1/openapi.yaml) |
| Trusted single-workspace deployment | [deployment-boundary.md](../../../contracts/review-platform/v1/deployment-boundary.md) |
| Engine ↔ review skill | [review-input](../../../contracts/review-platform/v1/schemas/review-input.schema.json) / [review-output](../../../contracts/review-platform/v1/schemas/review-output.schema.json) |
| Engine ↔ dialogue skill | [dialogue input](../../../contracts/review-platform/v1/schemas/finding-dialogue-input.schema.json) / [dialogue output](../../../contracts/review-platform/v1/schemas/finding-dialogue-output.schema.json) |
| Skill package | [manifest](../../../contracts/review-platform/v1/schemas/skill-manifest.schema.json) |
| Review engine ↔ LLM adapter | [model-adapter.md](../../../contracts/review-platform/v1/model-adapter.md) |
| Mock/contract fixtures | [examples](../../../contracts/review-platform/v1/examples/) |

Root [README](../../../contracts/review-platform/v1/README.md) defines semantic validation, compatibility and integration gates. [CHANGELOG](../../../contracts/review-platform/v1/CHANGELOG.md) changes in the same commit as any contract artifact.
