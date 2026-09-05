# Review Application and runtime semantics

This is the internal implementation contract shared by API, worker and direct CLI. Python names are illustrative but stable coarse capabilities are required; framework DTO/repository objects MUST NOT cross this boundary.

## Application capabilities

```python
class ReviewApplication(Protocol):
    async def get_bootstrap(self, query: GetBootstrap) -> BootstrapView: ...
    async def upload_document(self, command: UploadDocument) -> DocumentView: ...
    async def list_documents(self, query: ListDocuments) -> DocumentPage: ...
    async def get_document(self, query: GetDocument) -> DocumentView: ...
    async def download_document(self, query: DownloadDocument) -> ImmutableRepresentation: ...
    async def create_profile(self, command: CreateProfile) -> ReviewProfileView: ...
    async def list_profiles(self, query: ListProfiles) -> list[ReviewProfileView]: ...
    async def list_model_profiles(self, query: ListModelProfiles) -> list[ModelProfileView]: ...
    async def create_review(self, command: CreateReview) -> ReviewRunView: ...
    async def cancel_review(self, command: CancelReview) -> ReviewRunView: ...
    async def execute_review(self, command: ExecuteReview) -> None: ...
    async def get_review(self, query: GetReview) -> ReviewRunView: ...
    async def list_reviews(self, query: ListReviews) -> ReviewRunPage: ...
    async def get_report(self, query: GetReport) -> ImmutableRepresentation: ...
    async def list_finding_states(self, query: ListFindingStates) -> FindingStateList: ...
    async def get_dialogue(self, query: GetDialogue) -> FindingDialogueView: ...
    async def create_dialogue_turn(self, command: CreateDialogueTurn) -> FindingDialogueView: ...
    async def retry_dialogue_turn(self, command: RetryDialogueTurn) -> FindingDialogueView: ...
    async def execute_dialogue_turn(self, command: ExecuteDialogueTurn) -> None: ...
    async def put_decision(self, command: PutDecision) -> HumanDecisionView: ...
    async def read_poc_v1(self, command: ReadPocV1) -> PocImportView: ...
```

Commands contain configured namespace/actor, typed IDs, validated values, idempotency key and trace ID. They do not contain FastAPI Request, Pydantic boundary model, SQLAlchemy Session or provider SDK objects.

Health, readiness, queue-schema checks and recovery controls belong to a separate operator-only `OperationalApplication` composition boundary. They are not `ReviewApplication` capabilities, are not mounted below canonical public HTTP v1, and cannot add paths to its OpenAPI document. Readiness verifies configured deployment/organization/workspace/actor, PostgreSQL business migrations, separately owned Procrastinate schema version, artifact-store writability, and required deterministic resources without making an external model call.

## Ports

- `UnitOfWork`: typed repositories plus commit/rollback; owns transaction.
- `ArtifactStore`: stage, hash/verify, atomic promote, open immutable, delete verified staging/orphan. Feature 003 ships the durable POSIX adapter only; S3 is deferred behind this unchanged port.
- `DocumentParser`: capabilities and deterministic extraction result.
- `SkillRegistry` / `SkillExecutor`: resolve exact package and validate operation boundary.
- `TrustedFixtureRegistry`: resolve only operator-packaged expected-output resources by ID, verify exact bytes/SHA and validate the closed feature schema; caller paths/content never reach it.
- `ModelGateway`: capabilities/generate using root model-adapter contract.
- `JobOutboxRepository` and `JobQueue`: durable handoff; queue implementation is replaceable.
- `Clock`, `IdGenerator`, `Canonicalizer`, `SecretProvider`, `SafeLogger`: explicit deterministic/system seams.

Runtime policy is loaded once from a duplicate-key-safe document validated against `runtime-config.v1.schema.json`, then semantically validated for cross-field lease/heartbeat/backoff/budget invariants. The schema's complete root `default` is the testable release policy; any operator overlay is materialized to the same complete shape before validation and canonical digesting. Its numeric budgets are release safety bounds, not claimed SLOs or pilot capacity. The resulting canonical config digest and codec ID are included in execution evidence. Environment variables may resolve secret references and the one explicitly enabled model endpoint but MUST NOT silently bypass the validated bounds; network policy denies every other egress destination.

The root schema default deliberately has `trusted_fixture_bindings=[]`, so an unspecified installation never fabricates a semantic result. The documented Compose smoke explicitly selects the versioned, non-secret `deploy/compose/config/runtime-config.synthetic.v1.json` and mounts its referenced `trusted-fixture-output.synthetic.v1.json` read-only. Bootstrap/readiness verifies the complete config, resource ID, exact expected-output SHA, schema, fixture/profile/skill/parser selector digests and engine version. Missing/drifted assets make readiness unhealthy. The expected-output template identifies primary fragment ordinals and exact quote occurrences; only after all binding selectors match may the engine resolve current run/source/fragment IDs and quote offsets. It performs no other placeholder substitution and validates the resulting `review-output.v1` semantically before publication.

Repository interfaces are internal to application services; adapters cannot bypass use-case invariants by being called from HTTP routes.

## Fixture tracer versus real engine

### Slice 2 fixture application

An in-memory adapter implements repositories/artifacts/outbox and a deterministic scheduler. It exercises real application commands, state machines, canonicalizer and HTTP DTO mapping. It may use a fixture review executor but MUST expose provenance `deterministic-fixture` and MUST NOT be described as semantic analysis. Fixture behavior is selected by test composition/configuration, never by text embedded in an uploaded document.

### Slice 3 real engine

The fixture executor is replaced behind `ReviewEngine` with real source extraction, review-input creation, skill resolution, work partition, ModelGateway calls, synthesis and semantic validation. HTTP routes/DTO remain unchanged. Contract test parameterization runs the same structural cases against both compositions during migration; final release default uses real engine plus deterministic gateway.

The release deterministic gateway has two explicit outcomes:

- ordinary input performs no semantic inference: every known primary target fragment gets `CoverageGap(code=other, reason=semantic_analysis_not_performed)`, no target is marked reviewed, findings are empty, and the report is `partial`;
- a synthetic expected result is allowed only when an operator-controlled `trusted_fixture_bindings` entry matches the exact primary document SHA-256, profile semantic digest, skill package digest, parser settings digest, engine version and expected-output digest/resource. The closed template is validated against `trusted-fixture-expected-output.v1`, its primary ordinals/quote occurrences are resolved against verified prepared input, and the resulting dynamic IDs/offsets still pass full `review-output.v1` validation. The matched binding/resource ID and digests are snapshotted as provenance. Document text, filename, metadata, magic marker, or caller input can never enable this path.

## Review execution algorithm

1. Validate the discriminated envelope and load the exact run plus `review_execution_id`. A terminal attempt or delivery for a superseded ID exits idempotently; a non-terminal execution is claimable even when the run is already `preparing|reviewing|validating`.
2. CAS-claim `ready|waiting_retry`, or reclaim `running` only after lease expiry, installing a new lease token. In the same guarded start transition move a `queued` run to `preparing`; an already advanced non-terminal run is accepted only when consistent with the persisted checkpoint. Resume from the last committed checkpoint; every heartbeat/checkpoint/state write predicates on token + revision.
3. Check cancellation. For each immutable requested source, load its create-run-time `requested_extraction_id` and verify parser/settings against the execution snapshot, then `ensure_extracted` through its own CAS lease. A stale extraction lease is reclaimed; deterministic fragment IDs and checkpoint digests make replay safe.
4. Insert each `review_run_source_preparations` outcome exactly once. An existing outcome is reusable only when its canonical digest matches. Primary with no usable fragment fails. Partial primary with usable fragments continues but requires source-level `CoverageGap(code=source_partial, fragment_id=null, reason=primary_source_partial)`; this gap does not replace coverage rows for known fragments.
5. Commit checkpoint `sources_prepared`, resolve exact profile/skill/model/policy/config and verify every immutable digest. Mutable model availability is checked separately and never rewrites the snapshot.
6. Build and persist the digest/IDs for `review-input.v1`; primary preparation fragment IDs are the complete known target set and context is supporting. Commit `input_built`, then CAS the run to `reviewing` if it has not already advanced.
7. Materialize deterministic work items without changing the target set. For each incomplete item: renew lease, check cancel, call the gateway with separated trusted/untrusted fields and a configured timeout, parse/validate output, then commit either the terminal result or explicit gap. Retry/backoff is bounded by runtime config.
8. After every work item is terminal, commit `work_items_complete`; synthesize/deduplicate one `review-output.v1`. Ordinary no-model deterministic execution emits no findings and one `CoverageGap(code=other, reason=semantic_analysis_not_performed)` for every target fragment, therefore `partial`. A trusted fixture result is used only through the exact configured digest binding described above.
9. CAS the run to `validating` if it has not already advanced, then schema + semantic validate exact coverage, source/fragment/quote/locator/scope/provenance invariants. Commit `output_validated`, canonicalize with `jcs-rfc8785-0.1.4`, stage exact report bytes and commit `report_staged` with artifact key/digest only after store verification.
10. Renew/check the lease immediately before publication, then open the final database transaction. Inside it, predicate on execution token/revision plus run cancellation/revision and acquire the shared transaction-scoped PostgreSQL advisory fence for the exact namespace/store key/digest. While holding that fence, revalidate the staged file, atomically promote it, fsync the parent directory, reference the exact promoted key/digest, insert the immutable report graph, eager dialogues and initial finding states, mark run/execution completed and commit `published`; commit releases the fence. A failed transaction releases the fence and leaves only a collector-eligible unreferenced object.
11. On crash/redelivery, recovery validates durable rows/artifacts named by the checkpoint and resumes the first incomplete step. Exhausted execution attempts fail the non-terminal run without a report. Safe work gaps may yield partial; invalid final output, impossible synthesis or inconsistent checkpoint fails without publication.

Extraction, review and dialogue leases are application records; Procrastinate heartbeats alone do not satisfy recovery. A recovery scan operates only on expired leases, uses database time, and emits normalized audit/log codes for reclaim, exhaustion and stale-owner rejection. The concrete durations, attempt limits, timeouts and scan/backoff intervals are the validated values from `runtime-config.v1.schema.json`.

## Cancellation contract

Cancellation checks occur before steps 3, 4, every step-7 attempt, 8, 9, artifact promotion and the step-10 transaction. A provider call already in flight is best-effort cancelled; its returned data is discarded after cancellation wins. Cancellation also invalidates/clears the active execution lease by CAS so a stale worker cannot commit another checkpoint.

The final CAS has exactly two valid race outcomes:

- report publication commits first: run is `completed`; cancel observes terminal and returns conflict;
- cancellation commits first: run is `cancelled`; publication predicate fails; no report reference exists.

## Dialogue execution algorithm

0. Every finding already has one eagerly created dialogue from report publication; `get_dialogue` is read-only and never creates it.
1. The create command locks/CASes dialogue revision, recomputes `can_send_message`, validates idempotency and inserts one active turn, its first `GenerationAttempt`, and attempt-specific outbox in one transaction.
2. Worker validates the envelope and loads the exact `dialogue_id`, `turn_id` and `generation_attempt_id`. A terminal/superseded/foreign delivery exits idempotently.
3. CAS-claim the named attempt or reclaim it only after lease expiry, installing a fresh token. Resume from its verified checkpoint; all heartbeat/checkpoint/publication writes require token + revision.
4. Load immutable finding/report/policy/snapshot; build `finding-dialogue-input.v1`, persist its safe digest/IDs and commit `input_built`. Member/history/document values remain untrusted.
5. Call gateway with the configured timeout. Persist safe provider outcome, commit `provider_completed`, then schema + semantic validate response and anchors and commit `response_validated`. Redelivery does not repeat a completed checkpoint.
6. Publish at most one assistant response and mark attempt/turn completed, or mark them with a normalized safe failed error. The final write requires the current lease and the active-attempt identity.
7. Recompute dialogue projection. Existing Human Decision always keeps it blocked; a response may remain audit-visible but never reopens dialogue or changes the decision.
8. Retry of a failed turn CAS-transitions that turn back to `queued`, appends a new `GenerationAttempt`, selects it as the active attempt and inserts its own outbox entry; it never inserts a second member message. The new envelope names only that new attempt.

Expired dialogue attempts are reclaimed and resumed by checkpoint. Exhausted attempts become terminal `failed` and cannot leave the turn in `queued|generating`. Any late completion from an older attempt loses the active-attempt/lease CAS and is discarded.

Decision write uses its own expected decision revision. It may race with generation; accepted decision does not delete/audit-hide the active attempt and can never be overwritten by it.

## Typed domain errors

Application errors map centrally:

| Domain category | HTTP |
| --- | --- |
| validation / invalid transition request | `400` unless state race below |
| configured namespace/resource absent | `404` |
| idempotency payload mismatch | `409` |
| stale revision / active turn / stale profile head / terminal cancel | `409` |
| report not published for run | `409` |
| upload size limit | `413` |
| unexpected internal/provider details | safe `500` or async failed state; never raw exception |

CLI maps the same categories to documented non-zero exit codes and safe stderr without changing domain semantics.

## Job handoff

Only two business job kinds exist in feature 003: `execute_review` and `generate_dialogue_turn`. The envelope MUST validate against `job-envelope.v1.schema.json` and includes only common IDs/version/trace/actor plus one discriminated attempt-specific payload:

- review: immutable `review_run_id` + `review_execution_id`;
- dialogue: immutable `dialogue_id` + `dialogue_turn_id` + `generation_attempt_id`.

The outbox `business_key` is derived from the discriminant and exact execution/attempt ID. A payload with mismatched kind, namespace, parent IDs or current active execution is rejected safely before a lease is claimed. It never contains message/document text, provider data or secrets.

The dispatcher uses tokenized expiring claims, bounded exponential backoff and terminal failure rules from `runtime-config.v1.schema.json`. An uncertain publish is retried because handlers are idempotent. Exhaustion marks both the outbox and still-active referenced business work terminal, so queue delivery failure cannot create a permanently invisible `queued` run/turn.

Procrastinate schema ownership is operationally separate from application Alembic migrations. Install/upgrade runs the locked image command `uv run --frozen procrastinate --app=<dotted.app> schema --apply`; readiness runs the matching locked `... healthchecks` in addition to application migration checks. Application recovery never mutates Procrastinate tables directly.

## POSIX artifact durability and cleanup

The mandatory adapter writes a unique staging file on the same filesystem, streams size/SHA verification, `fsync`s the file, atomically renames to a content-addressed opaque key, then `fsync`s the parent directory before the key may be referenced by a committed database row. Database rollback can therefore leave only an unreferenced promoted object, never a referenced partial object.

The collector handles both stale staging files and promoted-but-unreferenced objects older than configured grace periods. Publisher and promoted-object collector share a transaction-scoped PostgreSQL advisory fencing lock derived deterministically from exact namespace/store key/digest. Publisher acquires it before promotion and keeps it through the database reference commit. Collector acquires the same lock, rechecks exact references inside that transaction, deletes before releasing the lock, and skips deletion on lock or database uncertainty. Thus a collector cannot pass a non-reference check and delete after a concurrent publisher commits. Advisory-key collisions may serialize unrelated objects but cannot weaken safety. S3 lifecycle/consistency semantics are explicitly outside feature 003.
