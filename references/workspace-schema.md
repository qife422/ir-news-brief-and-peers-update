# IR workspace schema 1.0

Read this reference when constructing an investor-question radar, earnings preparation, or meeting-memory workspace. The executable contract is `scripts/ir_workflow.py`; start with `examples/ir-workspace.example.json`. This local standard-library script validates, computes, filters and projects supplied records. It does not research sources, generate new wording, call a model, or decide whether a passage semantically supports a claim. IR personnel review those judgments.

## Root and metadata

The root is an object with `metadata` and arrays `sources`, `excerpts`, `claims`, `topics`, `questions`, `answers`, `feedback`, `financials`, `meetings`, `events`. Missing arrays mean empty arrays; use the complete root shape for maintained workspaces. Every array record requires a stable, unique, nonempty string `id`, unique within that collection. References use those IDs, not report-local source numbers. Preserve IDs and historical inputs across runs.

Required metadata:

| Field | Value |
|---|---|
| `schema_version` | String `1.0` |
| `id` | Stable workspace ID |
| `subject_company` | Subject company name |
| `status` | `Example`, `Draft`, `Reviewed`, or `Final` |
| `as_of` | ISO timestamp with explicit offset, e.g. `2026-03-01T00:00:00Z` |
| `timezone` | IANA name, e.g. `UTC` or `America/Los_Angeles` |
| `audience` | `public` or `internal` |
| `allowed_visibility` | Nonempty list drawn from `public`, `internal`, `licensed` |

`label` and other user metadata are optional and are not copied into reports. Generated reports remain `Draft`, or `Example` for Example input; input-level Reviewed/Final does not automatically approve generated answers or reports. Example figures and events are demonstrations, not actual company or investor records.

## Permissions and time

Sources, topics, questions, answers and meetings require an explicit permission tuple: `authorized` boolean, `visibility`, and nonempty `audiences` list. A record is usable only when authorized, its visibility is in metadata's allowed scope, and the target audience is in its audiences. Public output additionally requires visibility `public`; licensed and internal materials are excluded from public projections. Authorization describes the supplied processing/output permission, not a legal conclusion made by the script.

Claims, financial rows and nested analysis/actions/gaps/answer statements may optionally declare the same complete permission tuple to narrow their scope. Nested content otherwise inherits the parent scope; claims and financial rows always also require eligible source evidence. If any tuple field is present, all three must be explicit. Declared restricted dependencies suppress the derived text even if its own node is public. Declare every dependency: the script cannot discover an undeclared internal inference hidden in free text.

All time fields use offset-aware timestamps. `published_at` identifies publication; `available_at` is the earliest proven availability of that version; `version_at` identifies its content version; `retrieved_at` records collection and can be after a historical report cutoff. Publication/version cannot be after first availability, and retrieval cannot precede the content version. Preserve the evidence supporting availability rather than backdating a newly fetched page.

For date-only releases, retain `published_date_raw`, `time_precision`, `time_note` and use a documented conservative timestamp boundary. These optional string fields, plus `fingerprint_scope`, appear in the source ledger. They distinguish the original date from a normalized availability boundary and necessary-excerpt hashes from whole-document hashes. A missing/null publication, availability or version timestamp creates a warning; the source is excluded and reported as a gap. Retrieval time remains required.

## Sources, excerpts and claims

| Record | Required fields beyond `id` |
|---|---|
| `source` | `company`, `title`, `kind`, `url`, `version`, `published_at`, `available_at`, `version_at`, `retrieved_at`, 64-hex `content_sha256`, permission tuple, `status` |
| `excerpt` | `source_id`, `locator`, `text` |
| `claim` | `company`, `text`, `period`, `definition`, nonempty `excerpt_ids`, `status` |

Source `status` is `active`, `retracted`, or `superseded`; inactive records also require `invalidated_at`. Prefer events for subsequent state changes, preserving the original record. Optional `material_id` groups versions of one material; absent it, the source ID is the material ID. At a cutoff only the latest proven available version per material is current. A newer withdrawn version does not silently reactivate old wording. Optional `independence_key` identifies an independently originating source, not a syndicated copy.

Excerpt `locator` must locate the passage in the original material, such as a table row or paragraph. Optional excerpt `content_sha256` must equal SHA-256 of its exact UTF-8 `text`; it is checked. Source fingerprints are required ledger assertions whose scope must be established during intake: the script cannot verify a whole document it does not hold.

Claim `status` is `confirmed` or `pending`. Confirmed means the input maintainer has checked support; structural validation is not semantic confirmation. Optional `valid_from` and `valid_until` constrain applicability. Every supporting source must identify the same company as the claim. Macro/industry claims therefore use their own explicit company/entity label, not the subject company's name.

Default support is one complete group containing all `excerpt_ids`. Optional `support_groups` is a nonempty list of nonempty ID lists covering exactly those excerpts: each group is an explicit human assertion that its passages completely support the same claim. Multiple groups require explicit, non-overlapping source `independence_key` values. A surviving complete independent group can preserve the fact after another group is withdrawn, but does not renew an answer's old review.

## Topics, questions and answers

Topic required fields are `title` and permission tuple. `claim_ids` is a reference array, possibly empty; `base_priority` defaults to 0 and is a number from 0 to 5. `analysis`, `actions`, and `gaps` are arrays. Analysis nodes require `id`, `text`, `type` (`analysis` or `hypothesis`), and nonempty `claim_ids`. Dependency-bearing actions/gaps use `{id,text,claim_ids}`. Plain action/gap strings are permitted only as preparation instructions or missing-information descriptions under the topic's declared scope; factual or numeric assertions belong in cited records.

Question required fields are `topic_id`, `text`, `origin`, and permission tuple. `origin` is `anticipated`, `actual`, or `paraphrase`; prewritten questions do not become actual questions by changing their display label. `trigger_claim_ids` references the supporting claims and is required/nonempty for anticipated questions. `follow_ups` is an optional string array under the question's scope.

Answer required fields are `question_id`, string `version`, permission tuple, and nonempty `statements`. Each statement requires `text`, nonempty `claim_ids`, and `kind` (default `fact`). A `fact` or `company_position` statement also requires `company` matching every supporting claim; peer claims cannot support a subject-company fact. `analysis` permits interpretation with disclosed dependencies. Explicit statement IDs are recommended; otherwise the output uses answer ID plus its statement position. Optional answer `valid_from`/`valid_until` bound applicability.

`review` may be absent or `{status:"pending"}`. An active reviewed entry requires `{status:"reviewed",reviewer,at,scope,digest}`; `scope` is a nonempty string describing what the human checked. Optional `valid_until` limits review duration. `digest` must be obtained from `answer_review_digest(answer,data,as_of=review_time)` after the human has reviewed the exact answer and evidence. It binds answer and question versions/content/scope permissions, claim definitions, passages, source versions/fingerprints and source states. A source withdrawal, changed answer/question/definition, unsupported dependency, expired applicability, future review time or mismatched digest produces `NeedsReview`; independent surviving evidence does not automatically restore `Reviewed`.

## Meetings and feedback

Meeting required fields are `title`, `at`, and permission tuple; `question_ids` is an optional reference array. Meeting-memory reports select meetings at/before the cutoff, with permitted reusable questions/answers. Future meeting planning can reuse these outputs; the current model does not ingest future meeting outcomes.

Feedback required fields are `question_id`, `meeting_id`, `kind`, `excerpt_id`, and `confirmation`. Its kind is `actual`, `anticipated`, or `paraphrase`. Confirmation is `{status:"pending"}` or `{status:"confirmed"|"revoked",reviewer,at}`. Confirmation cannot precede the meeting. Counts require feedback kind actual, question origin actual, a confirmed record at the cutoff, an eligible original excerpt and eligible meeting/question scopes.

Natural deduplication key is meeting ID plus question text normalized for whitespace and case. Re-imported copies count once; the latest confirmation state controls the whole key, with revocation winning an equal-time conflict. Revocation cancels actual-question counts and corresponding priority contributions. Future events do not affect historical cutoffs. Preserving prior confirmation events is necessary to reconstruct a later-revoked record's earlier confirmed state.

## Financial rows and calculations

Required fields are `kind`, `value`, nonempty `excerpt_ids`, and all definition fields: `company`, `metric`, `period`, `currency`, `unit`, `accounting_basis`, `share_basis`, `definition_id`. Each definition is a nonempty string. Use explicit `not_applicable` values where appropriate, rather than omitting fields. `kind` is actual with `released_at`, or consensus with `snapshot_at`. Prefer decimal strings; NaN/infinity are rejected. Every financial row is backed by matching-company passages.

Pairs must match all definition fields exactly. Revenue/bookings, currencies, GAAP/adjusted, fiscal periods and share/ADS bases are not normalized implicitly. A valid consensus snapshot is strictly before actual release, with source availability and version no later than the snapshot. Retrieval can be later if historical availability is proven. The latest compatible pre-release snapshot is selected; mismatched candidates retain their values and `consensus_definition` but receive `incomparable` and null calculations.

Calculations use Decimal with precision 40: difference = actual minus consensus; for a positive consensus, percentage difference = difference / consensus × 100. Zero consensus gives `zero_base`, negative consensus gives `negative_base`; both preserve absolute difference but have null percentage difference. Missing and post-release/unproven snapshots give `missing_consensus` or `late_consensus`. There is no automatic beat/miss judgment, FX conversion, averaging, or estimate filling.

## Events and append-only history

Every event requires `id`, `at`, `type`, `target_id`, `reviewer`. Allowed types:

| Type | Target and additional fields |
|---|---|
| `source_retract` / `source_supersede` | Source ID; no additional required fields |
| `feedback_confirm` / `feedback_revoke` | Feedback ID; event cannot precede the meeting |
| `answer_review` | Answer ID plus `version`, `scope`, `digest`; optional `valid_until` |

Example withdrawal event (demonstration only):

```json
{"id":"example.event.retract","at":"2026-03-01T00:00:00Z","type":"source_retract","target_id":"example.source.company","reviewer":"Example IR reviewer"}
```

The event command appends a validated event into a new workspace file without replacing original source/feedback/answer records. Answer-review events additionally check that version and digest match the answer/evidence at the event time. Reports apply events at/before the cutoff in temporal order. Neither event append nor snapshot advances the report cutoff; choose an explicit later `--as-of` when appropriate. Snapshots add `snapshot_parent_sha256` and `snapshot_created_at` to a deep copy. Full snapshots remain workspace inputs and must not be embedded or published as public report data.

## API, CLI and output contract

```python
errors, warnings = validate_workspace(data)
report = build_report(data, previous=None, mode="radar", audience=None, as_of=None)
digest = answer_review_digest(answer, data, as_of=None)
new_workspace = append_event(data, event)
snapshot = snapshot_workspace(data)
```

```bash
python3 scripts/ir_workflow.py validate WORKSPACE.json
python3 scripts/ir_workflow.py report WORKSPACE.json OUTPUT.json --mode radar --audience public
python3 scripts/ir_workflow.py report WORKSPACE.json OUTPUT.json --mode earnings --as-of 2026-03-01T00:00:00Z --previous PREVIOUS.json
python3 scripts/ir_workflow.py report WORKSPACE.json OUTPUT.json --mode meeting
python3 scripts/ir_workflow.py snapshot WORKSPACE.json SNAPSHOT.json
python3 scripts/ir_workflow.py event WORKSPACE.json EVENT.json NEXT_WORKSPACE.json
```

Output directories for the core CLI above must exist. `render_workflow.py WORKSPACE.json OUTPUT.html --mode radar` (or `OUTPUT.md`) creates missing parent directories. Both commands use exclusive file creation: an existing output, including the workspace path itself, is rejected; there is no force flag. Invalid workspaces/events fail before creating output. CLI returns 0 for success, 1 for validation/runtime failure; argument errors use argparse's status 2. Validation diagnostics name field paths, not raw document text. API validation returns error/warning lists; builders raise ValueError on invalid input.

The five-dimension materiality assessment in `professional-methodology.md` remains a human judgment. Record its component scores and reasoning as a dependency-bearing topic analysis, then explicitly choose `base_priority` (0–5); the workflow score is not the original materiality score or an investor-question probability. Put confirmed preparation owners/deadlines in `actions`, unresolved ones in `gaps`. Public coverage boundaries belong in topic text/gaps, not arbitrary metadata (which is intentionally not exported).

Report root keys are `metadata`, `topics`, `sources`, `earnings`, `meeting_brief`, `data_gaps`. Topics share `id`, `title`, `change`, `facts`, `analysis`, `questions`, `answers`, `actions`, `gaps`, `priority`, `actual_question_count`. Facts have supported citations or an unavailable/pending state; unsupported text is withheld. Answers have Draft/Reviewed/NeedsReview status. Earnings holds `comparisons` and `gaps`; meeting_brief holds `meetings`. Only eligible source ledger fields and cited excerpts are projected; the input workspace and arbitrary metadata are never embedded.

Previous reports must share schema, output audience and subject company and must not be later than the new cutoff. Changes distinguish initial baseline, new topic, changed, unchanged; compare fact wording/definitions/evidence and visible question/answer state. Preparation priority combines the declared base, confirmed actual-question count (capped contribution 3), and a one-point evidence-change contribution (total cap 10). It is an explainable preparation ranking, not a probability or causal stock-price estimate.
