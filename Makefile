.PHONY: contracts

contracts:
	npm ci --ignore-scripts --prefix tools/contracts/orval
	python3 tools/contracts/validate_contracts.py
	uvx --with jsonschema==4.25.1 --from pytest==9.0.2 pytest -q tests/contract
