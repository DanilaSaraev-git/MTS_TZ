.PHONY: lint contracts test-unit test-integration test-migration test-security test-e2e release-check-local release-check

UV := uv run --frozen

lint:
	$(UV) ruff check packages apps/api apps/worker apps/cli tests tools
	$(UV) mypy

contracts:
	npm ci --ignore-scripts --prefix tools/contracts/orval
	python3 tools/contracts/validate_contracts.py
	uvx --with jsonschema==4.25.1 --from pytest==9.0.2 pytest -q tests/contract

test-unit:
	$(UV) pytest -q packages/review-core/tests packages/review-runtime/tests apps/cli/tests

test-integration:
	$(UV) pytest -q tests/integration

test-migration:
	$(UV) pytest -q tests/migration

test-security:
	$(UV) pytest -q tests/security

test-e2e:
	$(UV) pytest -q tests/e2e

release-check-local: lint contracts test-unit test-security
	python3 tools/contracts/check_protected_paths.py

release-check: release-check-local test-integration test-migration test-e2e
