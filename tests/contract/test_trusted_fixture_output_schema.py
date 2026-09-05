from __future__ import annotations

from pathlib import Path

import pytest

from contract_helpers import load_json_no_duplicates, validate_schema


ROOT = Path(__file__).parents[2]
SCHEMA = load_json_no_duplicates(ROOT / "specs/003-backend-implementation/contracts/trusted-fixture-expected-output.v1.schema.json")


def test_closed_literal_template_accepts_exact_selectors() -> None:
    value = {
        "schema_version": "trusted-fixture-expected-output.v1",
        "resource_id": "synthetic-v1",
        "summary": "Synthetic expected review.",
        "findings": [{
            "local_id": "F-001",
            "kind": "ambiguity",
            "title": "Undefined retry boundary",
            "problem": "The retry rule has no terminal boundary.",
            "reason": "Implementations may diverge.",
            "question": "What is the maximum number of attempts?",
            "priority": {"level": "medium", "rationale": "Affects deterministic execution."},
            "anchors": [{"primary_fragment_ordinal": 1, "quote": "retry", "occurrence": 1}],
            "scope_primary_fragment_ordinals": [1],
        }],
        "reviewed_primary_fragment_ordinals": [1],
        "unreviewed_primary_fragments": [],
        "limitations": [],
    }
    validate_schema(SCHEMA, value)


@pytest.mark.parametrize("ordinal", [0, -1])
def test_invalid_ordinal_is_rejected(ordinal: int) -> None:
    with pytest.raises(ValueError):
        validate_schema(SCHEMA, {
            "schema_version": "trusted-fixture-expected-output.v1",
            "resource_id": "literal-${HOME}",
            "summary": "Literal placeholder-like text.",
            "findings": [],
            "reviewed_primary_fragment_ordinals": [ordinal],
            "unreviewed_primary_fragments": [],
            "limitations": [],
        })
