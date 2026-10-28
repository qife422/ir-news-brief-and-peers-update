# Business pilot acceptance

Use `scripts/assess_pilot.py` to expose coverage gaps and prepare human reviews of
three cases: `peer_update`, `earnings_preparation`, and `meeting`. It reads the
existing workspace schema and calls `ir_workflow.build_report` with a public
audience before assessing coverage. It never generates questions, opens actual
question holdouts, verifies disclosure permission, or accepts an IR deliverable.

The three real business cases are still pending. Adding this interface, filling
an Example, or passing automated checks does not complete them. The prior public
single-quarter trial is not evidence of the planned four subject-company quarters
and two quarters per core peer. A company/period is covered only when the public
projection contains an eligible, non-Example, confirmed fact with citations.
Documents, topics without facts, and internal/licensed facts do not count. Even a
covered period is not a claim that its complete financial or business content has
been reviewed. Input maintainers must identify examples accurately; changing a
label cannot establish authenticity.

## Candidate identity and actual-question holdout

Prepare the permitted pre-cutoff workspace separately from actual questions,
subsequent meeting outcomes and post-release materials. Do not place holdout text
in workspace arrays, free metadata, prompts, or the author's context. Schema
filtering cannot undo an author seeing the raw future material. Use a fresh
author who receives only the allowed pre-cutoff material when making a blind
comparison; mark an exposed run contaminated.

Freeze the authored candidate before opening held-out questions. The freeze binds
canonical full workspace JSON, the public candidate report, the full supplied
generation object (`prompt` and `config`), and current `ir_workflow.py` bytes.
Canonical JSON ignores formatting/key ordering, but not record values or array
ordering. Only hash actual supplied configuration; do not invent model settings.
The combined `candidate_sha256` identifies that candidate. It is neither a signed
audit receipt nor proof that generation began blind. Input/source availability
evidence and generation-before-holdout procedure still require human review.

Keep any initial pre-generation input freeze and the actual-question holdout
fingerprint with the pilot's existing local review record. The tool's candidate
freeze is an additional content identity, not a replacement for that earlier
input freeze. An evaluator opens holdout only after candidate freeze, then records
`contaminated`, the actual `opened_at`, and matching `frozen_candidate_sha256`.
An earlier opening, future opening, absent declaration or changed binding cannot
support a blind comparison. `declared_uncontaminated` is only a structured declaration, never a
machine-certified blind pass. Preserve candidate-to-actual-theme matches and
exclusion reasons in the review sheet; duplicate question wording must not inflate
coverage. Do not edit a candidate after seeing scores and retain its old review.

For a cutoff regression, add a later version at an old URL and a post-release
consensus snapshot in a separate test copy. Both must be excluded at the historical
cutoff, including dependent wording. They must never enter the author bundle.
Do not backdate `available_at` to make freshly obtained materials appear historic.

## API and local CLI

```python
from assess_pilot import assess_pilot, freeze_candidate

frozen = freeze_candidate(workspace, generation)
result = assess_pilot(workspace, plan, freeze=frozen)
```

`generation` is `{"prompt":"the actual supplied prompt","config":{}}` with a
nonempty prompt and the actual supplied JSON configuration. `plan.generation`
must be identical for comparison with a freeze. Example plan:
[pilot-assessment.example.json](../examples/pilot-assessment.example.json).

```bash
python3 scripts/assess_pilot.py freeze WORKSPACE.json GENERATION.json FROZEN.json
python3 scripts/assess_pilot.py assess WORKSPACE.json PLAN.json ASSESSMENT.json --freeze FROZEN.json
```

Output parents must exist; output uses exclusive creation, including when its path
equals an input path. Invalid inputs fail before creating output. Exit status is
0 for a written assessment (which can still be pending), 1 for invalid input or
unavailable output, and 2 for argument errors. Diagnostics never print supplied
source text. Stale freezes are reportable gaps, not fatal errors.

`assess_pilot(workspace, plan, freeze=None)` returns `coverage` rows
`{company,period,status,claim_ids,source_ids}`, plus three `cases` rows even if
some are omitted from the plan. `freeze_status` is `missing`, `mismatch`, or
`matched`; `freeze_changes` names changed binding fields without raw content.

Plan shape (unknown fields below remain null until measured/confirmed):

```json
{
  "generation": {"prompt": "Actual pre-cutoff author request", "config": {}},
  "required_coverage": [{"company": "Trip.com Group", "periods": ["2025Q4"]}],
  "cases": [{
    "case_type": "peer_update",
    "data_kind": null,
    "permission_ref": null,
    "human_review": null,
    "metrics": {
      "preparation_time": null,
      "factual_accuracy": null,
      "question_value": null,
      "feedback_reuse": null
    },
    "holdout": {"contaminated": null, "opened_at": null, "frozen_candidate_sha256": null}
  }]
}
```

Use `data_kind` `public_real`, `authorized_real`, or `Example`. Real classification
and `permission_ref` are human assertions, not permissions granted by a JSON flag.
The reference should identify the actual permitted inputs, processing environment,
and output audience. Confidential/paid inputs require their actual permission;
never place such contents in this public repository or a public search query.
Human review is `{reviewer,at,scope,candidate_sha256}` using a real named reviewer,
offset-aware timestamp, actual review scope and the matching frozen candidate
identity. The review time must be at/after that freeze and cannot be in the future.
For the complete comparison record it must also be at/after the actual holdout
opening; a preceding review leaves the `review_before_holdout` blocker.
An old review does not carry forward after a candidate changes and is frozen again;
missing/mismatched bindings remain pending with a generic review blocker. A future
freeze time is itself a mismatch. A model name is not a human reviewer. Do not
invent reviewers, timing or authorization references to fill the form.

## Four baseline metrics

Each metric can be null. To calculate it, provide the fields below and a nonempty
`evidence_ref` locating the actual timing/count review. The module checks finite
nonnegative minutes, integer counts and arithmetic consistency, not whether the
underlying review is true. Missing values or evidence reference yield null.

| Metric key | Recorded fields | Derived output |
|---|---|---|
| `preparation_time` | `manual_minutes`, `assisted_minutes`, `comparable_scope` | Minutes saved and reduction fraction only for comparable scope; zero manual baseline has no percentage |
| `factual_accuracy` | `checked`, `supported`, `contradicted`, `unsupported`, `uncertain` | supported / checked; all four outcome counts must sum to checked |
| `question_value` | `reviewed`, `accepted`, `accepted_after_edit`, `rejected` | (accepted + accepted_after_edit) / reviewed |
| `feedback_reuse` | `eligible_items`, `used_items` | used_items / eligible_items; used cannot exceed eligible |

Review atomic statements with exact locators and severity. Uncertain is not correct.
Use the same materials, scope and output quality when comparing preparation time;
acknowledge practice/order effects rather than promising a measured efficiency gain.
Question adoption is not predictive coverage. Actual-question coverage needs a
separate human theme-matching review after freeze, with the eligible-theme
denominator and exclusion reasons fixed independently of candidate performance.
Feedback reuse means records or follow-ups actually used in a later preparation,
not merely copied files or Example feedback. Preserve those item IDs and evidence
in the referenced review sheet.

For example, a measured factual review may use
`{"evidence_ref":"local-review#facts","checked":4,"supported":3,"contradicted":0,"unsupported":0,"uncertain":1}`.
These numbers illustrate shape only; do not copy them into a real baseline.

Case status priority is `pending_inputs` (missing real inputs/permission or
Example), then `pending_freeze`, then `pending_business_review` (missing human,
metrics or holdout record). All complete declarations produce only
`review_record_complete`, a structural result. Every assessment remains `Draft`
with `business_acceptance: pending_human_acceptance`. This does not change answer
review events, promote Reviewed to Final, accept a business pilot, or authorize
formal disclosure or publication.
