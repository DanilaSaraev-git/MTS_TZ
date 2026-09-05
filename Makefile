.PHONY: contracts

contracts:
	npm ci --ignore-scripts --prefix tools/contracts/orval
	python3 tools/contracts/validate_contracts.py
