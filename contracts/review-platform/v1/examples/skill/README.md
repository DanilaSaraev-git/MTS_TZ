# Skill contract examples

| Operation | Input | Output |
| --- | --- | --- |
| `review` | `review-input.json` | `review-output.json` |
| `finding_dialogue` | `finding-dialogue-input.json` | `finding-dialogue-output.json` |
| package discovery | `skill-manifest.json` | — |

Примеры синтетические. JSON Schema проверяет форму; engine semantic validator дополнительно проверяет source/fragment membership, quote offsets, exact target coverage и запрет `clarify`, если `current_turn.follow_up_allowed=false`.
