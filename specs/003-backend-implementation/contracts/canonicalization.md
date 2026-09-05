# Canonical artifacts and semantic validation

## Canonical JSON codec `jcs-rfc8785-0.1.4`

- The only feature-003 implementation is pinned exactly as `rfc8785==0.1.4`; neither a compatible range nor a handwritten partial encoder is accepted for release evidence.
- Input is a fully schema/semantics-validated I-JSON-compatible value. The boundary rejects duplicate object keys, NaN, positive/negative Infinity, invalid UTF-8/Unicode scalar values, and integers/numbers outside the domain that the application can round-trip without semantic change under RFC 8785/IEEE-754 serialization.
- Serialize per RFC 8785 JSON Canonicalization Scheme as UTF-8, including UTF-16 code-unit property ordering and ECMAScript-compatible number serialization implemented by the pinned codec.
- No BOM, indentation or trailing newline.
- UTC timestamps are normalized to the canonical RFC 3339 form chosen by boundary DTO before JCS.
- Arrays preserve semantic order; object member order is canonicalized.
- Codec identifier `jcs-rfc8785-0.1.4` is stored with every exact representation/digest. An unknown/different ID is not silently decoded or recomputed.

Release tests MUST pass every applicable RFC 8785 Appendix serialization vector and the vendored, provenance-recorded `cyberphone/json-canonicalization` canonicalizer corpus, including UTF-16 ordering, escaped/control/Unicode strings, IEEE-754 edge numbers and invalid I-JSON negatives. Tests also assert that upgrading the package or codec ID is an explicit migration/contract decision and that stored historical bytes/digests are read, not regenerated.

Uses:

| Value | Digest input |
| --- | --- |
| Review report | exact canonical public response value |
| Profile semantic digest | `{name, role, goal, checks}` only |
| Idempotency request | validated operation DTO, excluding headers/trace/server defaults not in semantic request |
| Execution/config snapshot | documented safe snapshot without secrets |
| Raw document | not JCS; exact uploaded bytes |

Strong ETag for document/report is quoted lowercase SHA-256 hex of exact returned bytes: `"0123…cdef"`. Report GET returns stored bytes; it MUST NOT reconstruct them from JSONB/ORM rows. Document bytes are raw and therefore have no JSON codec ID; report/profile/idempotency/config/snapshot records persist the codec ID beside the digest.

## Text and quote coordinates

Target fragments store the exact normalized `text` used by output validation. Anchor `quote_start` is 0-based inclusive and `quote_end` 0-based exclusive in Python/Unicode code points of that text. Required invariant:

```text
fragment.text[quote_start:quote_end] == quote
```

The validator does not search for or repair a wrong quote. Parser/adapters may normalize source text only before fragment publication, with parser/settings digest recorded. A repeated quote is unambiguous because offsets select the occurrence.

PoC v1 mapping is the only compatibility normalization path: NFC plus whitespace collapse first, then unique occurrence or explicit diagnostic as described in `poc-v1-mapping.md`.

## Location validation

- Text: line numbers 1-based; chars 0-based half-open; start ≤ end and range resolves within immutable normalized source.
- PDF: page 1-based within page count; every rectangle has four finite values in `0..1`, left < right and top < bottom; optional table/row are positive.
- A table-row anchor must use the row locator/bbox when parser provides it; whole-table bbox cannot be mislabeled as precise row evidence.
- If precise legacy coordinates cannot be proven, adapter emits diagnostic/partial behavior rather than fabricating a rectangle.

## Exact coverage

Let `T` be `review_scope.target_fragment_ids` from the primary source, `R` reviewed IDs and `Gf` fragment IDs of primary fragment-level gaps.

```text
R ∩ Gf = ∅
R ∪ Gf = T
R ⊆ T
Gf ⊆ T
```

All arrays are duplicate-free. Context fragments are never members of `T`. A source-level gap has `fragment_id=null` and does not participate in—or replace any member of—the primary partition.

Allowed source-level cases in feature 003 are:

- `code=source_partial|source_unavailable` with the corresponding stable context reason for a requested context source;
- exactly one `code=source_partial, reason=primary_source_partial` when primary extraction produced usable fragments plus a loss diagnostic.

For partial primary extraction, `T` is every known usable primary fragment and the equations above still hold for all of them. The source-level `primary_source_partial` gap additionally records that unknown/unextractable source content exists; the report MUST be `partial`. Primary extraction with no usable fragment fails the run and cannot publish a report.

For ordinary deterministic no-model execution, `R` is empty and `Gf=T`; every fragment-level gap is `code=other, reason=semantic_analysis_not_performed`, findings are empty, and the report MUST be `partial`. Running parsing, orchestration or validation is not semantic review and cannot put a fragment in `R`. A synthetic expected result is permitted only by an exact operator-controlled trusted fixture binding over document/configuration digests; uploaded marker text, filename or metadata is never a selector.

`coverage.status=complete` iff there are no fragment-level or source-level gaps. `partial` requires at least one legitimate gap. A fully partitioned known primary target set plus any source-level gap remains partial.

## Finding validation

- Finding IDs/ordinals unique within report.
- `missing`: zero anchors and at least one reviewed primary scope fragment.
- Other kinds: at least one anchor; scopes optional.
- Every anchor/source/fragment belongs to run snapshot and configured namespace.
- Anchor fragment and every scope fragment are reviewed, not a gap.
- Across anchors/scopes every finding has at least one primary-document basis; context-only finding invalid.
- Quote/offset/location resolve exactly; no unknown ID, fabricated quote or foreign document.
- Priority has level and non-empty rationale.
- Model/skill output cannot contain Human Decision fields; extra properties rejected.

## Publication invariant

Only schema-valid and semantically valid value is canonicalized with the pinned codec. Artifact promotion and DB publication are staged so that:

- a caller cannot observe partial report bytes;
- `completed` always has exactly one report and exact artifact;
- `failed|cancelled` never has a report;
- dialogue/decision/retry never writes report artifact or graph;
- repeated reads before/after restart are byte-identical and use same ETag.

Publication verifies that the report row, artifact metadata and canonical bytes all agree on SHA-256 and `codec_id=jcs-rfc8785-0.1.4`. A codec mismatch is a normalized internal integrity error, never an instruction to regenerate historical bytes.

POSIX publisher obtains the shared transaction-scoped advisory artifact fence before promotion and holds it through the report/reference commit. Orphan collector obtains the same exact namespace/store-key/digest fence, rechecks non-reference under lock and deletes before release, so collection cannot race a valid publication.
