# Report format v1

Use report.template.json as the complete top-level shape. Machine constraints live in scripts/review_data_spec/resources/report.schema.json.

A finding has id F-001…, kind ambiguity/contradiction/missing/inconsistency/other, title, problem, reason, question, priority high/medium/low, priority_reason, status, human_review, anchors, scope. For a present fragment, anchors contain exact short quotes plus source_id and fragment_id. The normalized quote must occur within that exact fragment. For a missing requirement, anchors is empty and scope lists the reviewed primary-document fragments that establish the search area. Other finding kinds need anchors. Each finding needs a primary-document basis even if context also supports it.

All anchor and scope fragment IDs must appear under coverage.reviewed_fragment_ids. Every other bundle fragment occurs once in coverage.unreviewed with a concrete reason. Unknown/omitted IDs and overlap are invalid.

Initial agent output uses status=unreviewed and human_review=null. Later confirmed/rejected/needs_context requires `{reviewer, decision_reason}`; this records a supplied human decision and is not identity authentication. Priority remains the agent's explained assessment.

Generation mode is agent for semantic review and demo_fixture only for built-in deterministic examples. Record agent/model/version when reliably known, otherwise literal unknown. Summary may report zero findings; still give full coverage and limitations. Never call successful schema/citation validation expert confirmation.
