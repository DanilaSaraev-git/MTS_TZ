# HTTP synthetic scenario

Все JSON используют один настроенный trusted actor, одну вымышленную организацию, один workspace и один tracer-bullet flow. Это canonical fixtures для backend contract tests и web MSW; они не содержат материалы MTS.

| Operation / state | Fixture |
| --- | --- |
| `getBootstrap` | `bootstrap.json` |
| `uploadDocument` / `getDocument` | `document.json` |
| `listReviewProfiles` | `profiles.json` |
| `listModelProfiles` | `model-profiles.json` |
| `createReviewRun` request | `create-review-run.json` |
| `ReviewRun` | `review-run.queued.json`, `review-run.completed.json`, `review-run.failed.json` |
| `getReviewReport` | `report.json`, `report.partial.json` |
| `listFindingStates` | `finding-states.json` |
| `createFindingDialogueTurn` request | `create-dialogue-turn.json` |
| `FindingDialogue` | `dialogue.generating.json`, `dialogue.open.json`, `dialogue.failed.json` |
| `retryFindingDialogueTurn` request | `retry-dialogue-turn.json` |
| `putFindingDecision` request/response | `put-decision.json`, `decision.json` |
| RFC 9457 error | `problem.json` |

MSW adapter должен выбирать fixture по operation/state, но типы и URL берёт только из generated OpenAPI client. Замена MSW на реальный backend меняет base transport, а не DTO или компоненты UI.
