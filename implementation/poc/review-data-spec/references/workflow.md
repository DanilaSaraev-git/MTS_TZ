# Operational reference

Install with `uv sync --frozen`; add `--extra test` for pytest. The skill is self-contained and works outside this repository. `run-demo` is a deterministic fixture and contains no LLM call.

pdfplumber is the default adapter. It reads machine-generated PDF text and heuristically locates tables. Empty extracted text, missing tables, cell nulls, line breaks, and reading order are extraction diagnostics; inspect the original when they affect a finding. OCR is outside v1. Addresses are expected to remain stable only for identical source bytes, order, parser version, and settings.

Profile context paths are relative to profile.json. CLI --context paths are relative to the invocation directory. Unavailable context is recorded and makes coverage partial; an unreadable primary document stops prepare. A conflict between sources becomes an uncertainty with both references. The primary document remains the authority for what it currently says, not necessarily for the intended business rule.

For a recorded experiment, preserve the run directory, agent-authored report.json, validation.json, report.md and protocol. The protocol distinguishes technical validation from expert usefulness, notes whether the document influenced tuning, and leaves unknown measurements unknown.
