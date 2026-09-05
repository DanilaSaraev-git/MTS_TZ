# Read-only mapping from feature 001 PoC v1

The adapter reads a legacy run directory as untrusted immutable input. It is a direct CLI/application capability only; no new public HTTP import endpoint is added in feature 003.

## Preconditions

1. Resolve requested run directory without traversal; all manifest snapshot paths must remain under it.
2. Parse JSON with duplicate-key and non-finite-number rejection.
3. Run existing feature 001 manifest/artifact/source hash checks and report schema/semantic validator. Hashes are required only for source snapshots that exist: a legacy `unavailable` context has no snapshot/SHA/parser and must be validated as that explicit absence rather than assigned fabricated metadata.
4. Capture hashes of every legacy file before mapping; adapter MUST perform no write inside directory and hashes MUST remain equal afterward.
5. Validate the complete mapped graph before exposing or writing output. Any invalid finding or anchor fails the whole mapping; the adapter MUST NOT drop only the bad item or return a partially filtered view.
6. A successful result MUST validate against [`poc-import-view.v1.schema.json`](poc-import-view.v1.schema.json). A lossy but still structurally valid source/human-state conversion uses `mapping_status=partial` plus typed diagnostics; an invalid finding/anchor produces a safe failure and no view/output file.

## Typed result boundary

`poc-import-view.v1` is the only successful application/CLI result. It contains deterministic adapter/run/report IDs, source and fragment projections, target coverage, mapped findings/anchors, default finding states and safe diagnostics. The schema is closed (`additionalProperties=false`) at every object boundary so an implementation cannot silently add `original_path`, configured actor or legacy inline human fields.

The reader builds the candidate view in memory, validates every reference and the complete schema, and only then may atomically write the requested output outside the legacy run directory. Validation failure removes any staging output and returns a non-zero/safe typed error; there is no usable partial object on failure.

Semantic validation additionally requires exactly one primary source with a non-empty target set, source/document/fragment membership for every reference, the exact primary reviewed-or-gap partition, one default FindingState per finding, unique IDs/ordinals and the finding/anchor rules below. JSON Schema validation alone is not sufficient.

## Identity

A fixed adapter UUID namespace plus validated legacy run digest creates deterministic UUIDv5:

```text
uuid5(namespace, "<run_digest>:<entity_kind>:<legacy_id>")
```

Entity kinds are distinct (`document`, `fragment`, `run`, `report`, `finding`) to avoid collision. FindingState is keyed one-to-one by mapped finding ID. Re-reading identical artifacts produces the same target IDs and no duplicate read projection.

## Mapping table

| PoC v1 | Target view | Rule |
| --- | --- | --- |
| manifest `run_id` + artifact digests | ReviewRun / snapshot identity | deterministic UUID; provenance records adapter/version and legacy digest |
| source `id`, role, snapshot, sha256, status | DocumentVersion + RunSource view | for `available|partial`, validate/read exact snapshot bytes and require SHA/parser; for legacy `unavailable` context, require no snapshot, map `sha256=null`, `parser=null`, zero fragments and a typed gap/diagnostic without inventing bytes; feature 003 `read-poc-v1` does not import/copy into ArtifactStore and never exposes `original_path` |
| source parser/version/settings/raw artifact | extraction provenance/diagnostic | preserve safe names/digests; raw path remains internal and relative |
| bundle fragment `id`, text, kind, location | Fragment | deterministic UUID; preserve ordinal/text; normalize locator only when dimensions/ranges prove it |
| profile name/version/role/goal/checks | immutable profile snapshot | digest canonical semantic fields; context file paths do not become public storage paths |
| report generation | ModelExecution provenance | map `demo_fixture` to deterministic legacy provider; unknown agent/model stays explicit `unknown`, never invented |
| report coverage | target Coverage | target set contains only fragments whose source role is `document`; context fragments become supporting provenance, not target partition |
| finding `F-n`, kind/text/priority | Finding | deterministic UUID, ordinal from stable legacy order, priority_reason→rationale |
| anchor source/fragment/quote | EvidenceAnchor | source/fragment remap; offset only after provable occurrence rule below |
| missing scope | Finding scope | primary reviewed fragment only; no fabricated anchor |
| finding status/human_review | separate FindingState + diagnostic | every mapped state is target `unreviewed` revision 0; see human state rule |
| limitations and source diagnostics | report limitations/provenance gaps | preserve safe text only after path/secret redaction |

## Quote occurrence

Legacy validator compares NFC + collapsed whitespace. Adapter builds the same normalized fragment/quote view and finds occurrences:

- exactly one occurrence: derive its half-open offsets in target normalized fragment;
- more than one: use a precise legacy locator/row occurrence only if it resolves deterministically; otherwise fail the complete mapping with `legacy_quote_ambiguous` rather than selecting first;
- none: fail the complete mapping with `legacy_quote_not_found`.

If normalization prevents a reversible mapping to original raw characters, target fragment text is the explicitly normalized adapter representation and its parser/adapter digest records this fact.

## PDF locations

PoC page number remains 1-based. Absolute bbox converts to normalized rectangles only when page width/height are present and positive. A bbox representing a whole table MUST NOT be claimed as row-level precision. If an anchor cannot obtain a target-valid precise location because dimensions or row occurrence are ambiguous, the complete mapping fails with `legacy_location_imprecise`; it never fabricates a rectangle, drops the anchor or emits a filtered report. A source diagnostic not referenced by any finding may remain a safe partial-mapping diagnostic.

## Coverage conversion

PoC coverage accounts for every prepared fragment, including context. Target coverage partitions only primary document fragments:

- primary reviewed → target reviewed;
- primary unreviewed → target fragment gap preserving safe reason/code;
- primary source partial with at least one known fragment → source-level `{code: source_partial, fragment_id: null, reason: primary_source_partial}` plus exact reviewed-or-gap partition of every known primary fragment;
- primary with zero usable fragments → mapping failure and no view;
- context unread/unavailable → source-level context gap; projected source has `sha256=null`, `parser=null` and no fragments because feature 001 stores no snapshot metadata for that state;
- context reviewed → supporting provenance only.

The adapter recomputes target complete/partial; it does not copy PoC validation status blindly.

## Human state

- `unreviewed` + null human review becomes default FindingState with `decision_status=unreviewed`, `decision_revision=0` and null actor/reason/resolution/time.
- Legacy non-`unreviewed` state also becomes that same default target FindingState and adds a finding-scoped `legacy_human_state_unrepresentable` diagnostic. Legacy status/review text is not copied into the immutable report or decision projection.
- No current or future configured actor is inferred. Supporting a real decision import requires a separately audited mapping policy in a future feature.

## All-or-nothing finding graph

The following conditions fail the complete mapping and produce no `poc-import-view.v1`: unknown/foreign source or fragment, duplicate finding identity/ordinal, invalid missing/scope rule, context-only primary basis, quote not found or ambiguous, invalid offsets, unprovable required locator, or any target schema/semantic violation. An unavailable context is the one source projection allowed to carry null SHA/parser and zero fragments; available/partial sources require real verified snapshot metadata. Source availability and unrepresentable human state are the only lossy conditions described here that may yield a schema-valid partial view with diagnostics.

## Forbidden data

Drop/redact absolute `original_path`, run-directory path and any secret from successful views, failures and logs. General release tests use a fresh synthetic PoC generated by existing demo command. client run directories are optional private smoke inputs only, never copied to common fixtures, output evidence, images, wheels or logs; private smoke validates and discards its view in memory.
