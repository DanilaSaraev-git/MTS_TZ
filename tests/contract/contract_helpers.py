from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_no_duplicates(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(), object_pairs_hook=_pairs)


def materialize_defaults(schema: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict):
        result = dict(value)
        for key, child in schema.get("properties", {}).items():
            if key not in result and "default" in child:
                result[key] = copy.deepcopy(child["default"])
            if key in result:
                result[key] = materialize_defaults(child, result[key])
        if not result and "default" in schema:
            return materialize_defaults(schema, copy.deepcopy(schema["default"]))
        return result
    return value


def validate_schema(schema: dict[str, Any], value: Any) -> None:
    from jsonschema import Draft202012Validator, FormatChecker

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError("; ".join(error.message for error in errors))


def validate_runtime_config(schema: dict[str, Any], value: Any) -> None:
    validate_schema(schema, value)
    leases = value["leases"]
    for name, lease in leases.items():
        if lease["heartbeat_seconds"] * 3 > lease["lease_seconds"]:
            raise ValueError(f"{name} heartbeat must fit at least three times in lease")
    shortest_lease = min(item["lease_seconds"] for item in leases.values())
    if value["recovery"]["scan_interval_seconds"] > shortest_lease:
        raise ValueError("recovery scan interval exceeds shortest lease")
    retries = value["retries"]
    if retries["initial_backoff_seconds"] > retries["max_backoff_seconds"]:
        raise ValueError("initial retry backoff exceeds maximum")
    optional = value["model_gateway"]["optional_openai_compatible"]
    if optional["auto_download"]:
        raise ValueError("automatic model downloads are forbidden")
    if optional["enabled"]:
        from urllib.parse import urlsplit

        endpoint = optional["endpoint"]
        parsed = urlsplit(endpoint or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("enabled optional endpoint must be absolute HTTP(S)")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("optional endpoint must not contain userinfo, query, or fragment")
    bindings = value["deterministic_gateway"]["trusted_fixture_bindings"]
    binding_ids = [binding["binding_id"] for binding in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("trusted fixture binding_id values must be unique")
    selector_keys = (
        "primary_document_sha256",
        "review_profile_semantic_digest",
        "skill_package_sha256",
        "parser_settings_digest",
        "engine_version",
    )
    selectors = [tuple(binding[key] for key in selector_keys) for binding in bindings]
    if len(selectors) != len(set(selectors)):
        raise ValueError("trusted fixture selector tuples must be unique")
