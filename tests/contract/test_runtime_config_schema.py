from __future__ import annotations

from pathlib import Path

import pytest

from contract_helpers import load_json_no_duplicates, materialize_defaults, validate_runtime_config


ROOT = Path(__file__).parents[2]
SCHEMA = load_json_no_duplicates(ROOT / "specs/003-backend-implementation/contracts/runtime-config.v1.schema.json")


def test_root_default_materializes_to_valid_unbound_policy() -> None:
    value = materialize_defaults(SCHEMA, {})
    validate_runtime_config(SCHEMA, value)
    assert value["deterministic_gateway"]["trusted_fixture_bindings"] == []
    assert value["model_gateway"]["optional_openai_compatible"]["auto_download"] is False


def test_cross_field_lease_invariant() -> None:
    value = materialize_defaults(SCHEMA, {})
    value["leases"]["extraction"] = {"lease_seconds": 20, "heartbeat_seconds": 10}
    with pytest.raises(ValueError, match="heartbeat"):
        validate_runtime_config(SCHEMA, value)
