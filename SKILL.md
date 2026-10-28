---
name: ir-news-brief-and-peers-update
description: Prepare source-backed Trip.com Group IR briefs, investor-question radars, earnings Q&A and variance analysis, and manually confirmed meeting feedback. Use for travel and OTA market intelligence, peer updates, earnings preparation, or investor-meeting preparation with traceable evidence and financial definitions.
metadata:
  version: "2.1.0"
---

# IR新闻简报与同业数据更新

Produce decision-useful Trip.com Group IR intelligence, not a news dump. Default to a structured HTML brief with charts, source drill-down, and print CSS. Generate PDF from the same HTML source when requested so the web and PDF versions stay consistent.

Never fabricate news, market data, consensus estimates, valuation multiples, financial results, images, or citations.

## Route the request

Choose one or combine only when the user asks:

- **HTML intelligence brief:** the default for daily or periodic news plus data visualization.
- **PDF brief:** render from the validated HTML brief; do not maintain a separate hard-coded PDF narrative.
- **Markdown brief:** use when the user wants a reviewable draft or cannot use HTML.
- **Peer-data view:** compare valuation, growth, margins, market performance, or quarterly results.
- **Excel update:** modify a supplied workbook under a cell-level change contract.
- **Investor-question radar:** maintain topics, evidence, changes, candidate questions and answer preparation across report snapshots.
- **Earnings preparation:** prepare evidence-backed Q&A and calculate actual-versus-consensus differences only from comparable authorized snapshots.
- **Meeting preparation and feedback:** use manually confirmed meeting records for a meeting brief, follow-ups and actual-question counts.
- **Pilot coverage and business review:** expose missing company/period evidence and prepare measured human acceptance without treating tests or Example runs as business completion.

Read only the references needed for the selected route:

- For news selection and IR interpretation, read [references/professional-methodology.md](references/professional-methodology.md).
- For sources, financial definitions, peer data, and data freshness, read [references/data-governance.md](references/data-governance.md).
- For HTML, charts, images, interaction, accessibility, or PDF export, read [references/html-brief-spec.md](references/html-brief-spec.md).
- For workbook changes, read [references/excel-update-contract.md](references/excel-update-contract.md).
- For radar and persistent evidence, read [references/investor-question-radar.md](references/investor-question-radar.md).
- For earnings Q&A and numerical comparisons, read [references/earnings-prep.md](references/earnings-prep.md).
- For meeting records and confirmation, read [references/meeting-feedback.md](references/meeting-feedback.md).
- For the new workspace fields and executable commands, read [references/workspace-schema.md](references/workspace-schema.md).
- For multi-quarter coverage, frozen candidates, actual-question holdouts and the three real business cases, read [references/pilot-acceptance.md](references/pilot-acceptance.md).

## Required intake

Before research or mutation, resolve:

- Deliverable: news, radar, earnings, meeting, peers, Excel, or combined; HTML/PDF/Markdown as needed.
- As-of time, coverage window, time zone, regions, companies, and language.
- Allowed source scope: supplied materials, public search, licensed sources, or a combination.
- Whether public search is authorized for this request or by a standing scope already stated by the user.
- Whether peer data is public, licensed, or manually supplied.
- For Excel: exact workbook path, target company/quarter, target metrics, and authoritative source.
- For workflow reports: exact workspace path, subject company, report audience, cutoff, permitted processing scope and previous snapshot when comparing changes.

Do not repeatedly ask for facts that can be discovered safely from the supplied files or an already-authorized search scope. Do not search with confidential information or configure API keys without explicit permission.

## Persistent IR workflow

Use the new workspace separately from the old news JSON; both interfaces remain supported. Start with [examples/ir-workspace.example.json](examples/ir-workspace.example.json) only for Example runs. Populate real workspaces from authorized material with exact excerpts/locators and dates. A reference ID alone does not establish that a sentence is true: check the cited passage and keep inference distinct from company statements.

```bash
python3 scripts/ir_workflow.py validate path/to/workspace.json
python3 scripts/ir_workflow.py report path/to/workspace.json path/to/report.json --mode radar
python3 scripts/render_workflow.py path/to/workspace.json path/to/report.html --mode radar
python3 scripts/render_workflow.py path/to/workspace.json path/to/report.md --mode earnings
python3 scripts/ir_workflow.py snapshot path/to/workspace.json path/to/snapshot.json
python3 scripts/ir_workflow.py event path/to/workspace.json path/to/event.json path/to/updated-workspace.json
```

Use `--previous` for an earlier projected report, `--as-of` for an explicit timezone-aware cutoff, and `--audience` for public/internal projection. New outputs reject overwrite. Keep snapshots and revised workspaces in the user's project, not in the Skill source. Never silently replace the user's input file.

The workflow excludes unavailable material versions and unauthorized audiences before selecting claims, topics, questions or answers. It propagates source invalidation and binds answer review to content and evidence. Public HTML embeds only the projected report, never the raw workspace. Do not put internal evidence, its derived wording or private meeting records in public searches, outputs or diagnostic messages.

Actual and paraphrased questions require a permitted original record, source locator and human confirmation available by the report cutoff before their wording or derived answers can be shown. Public trigger claims cannot substitute for that origin evidence. Predicted questions and second-hand comments remain separate, duplicate records do not increase actual counts, and revocation removes their effect. A reviewed answer is not automatically Final; formal delivery still requires explicit acceptance.

For business pilots, use `assess_pilot.py` with the actual workspace and a local plan to distinguish eligible public coverage, frozen candidate identity and incomplete human review. Preserve unknown baseline metrics as null. A candidate hash does not prove that its author never saw held-out actual questions; keep those inputs outside the author bundle and record contamination honestly. Do not mark the three real cases complete merely because coverage or automated checks pass.

Scripts validate dependencies and calculate differences. Codex reads evidence and authors the topic analysis, questions and drafts; the scripts do not autonomously research, generate investment judgments or assess disclosure legality. Real consensus access and confidential meeting processing require the actual permitted inputs and environment, not only a schema flag.

## Evidence-first workflow

1. Lock the as-of time and scope.
2. Gather candidate items from authorized sources. Prefer primary sources.
3. Normalize timestamps, company names, regions, currencies, periods, units, and source IDs.
4. Deduplicate syndicated or repeated coverage. Keep the strongest source and record supporting sources.
5. Separate confirmed facts, source-backed interpretation, IR implications, and unresolved gaps.
6. Score materiality using the professional methodology. Do not treat sentiment as materiality.
7. Build the source ledger before final rendering.
8. Validate structured data, then render HTML. Export PDF from that HTML only when requested.
9. Run a final evidence, freshness, display, and missing-data review.

## Default HTML workflow

Use the reusable standalone renderer when structured data is available:

```bash
python3 scripts/validate_ir_data.py path/to/report.json
python3 scripts/render_html_brief.py path/to/report.json path/to/report.html
```

The renderer refuses to overwrite an existing output unless `--force` is explicitly supplied. Start from [examples/ir-brief-data.example.json](examples/ir-brief-data.example.json); all values in that file are labeled as examples and are not formal IR data.

The HTML must make the following visible without opening source code:

- Report status, as-of time, coverage window, time zone, and data freshness.
- Three to five executive conclusions.
- High-impact news with real images only when licensed or source-authorized.
- Impact/urgency view, market pulse, peer comparison, and detailed news cards.
- Source IDs, source reliability, access time, and manual-review flags.
- Data gaps, stale inputs, conflicting sources, and unavailable metrics.
- Prompt/scope summary.

If chart-ready data is unavailable, render an honest empty state. Do not invent values to fill a visual.

## Peer-data requirements

Peer views must show an `as_of` date and keep comparable definitions together. At minimum identify:

- Company, security/ticker, listing, currency, fiscal-year basis, and share/ADS basis.
- Actual versus consensus versus company guidance.
- GAAP versus non-GAAP or adjusted metrics.
- Market-price timestamp and FX timestamp where relevant.
- Source ID for every market or financial data row.

Calculate premium/discount to a peer median only after validating comparable periods and definitions. Never average `N/A` as zero.

If reliable data is unavailable, state:

```text
数据不足 / 需要 Bloomberg、FactSet、Capital IQ、Visible Alpha、公司披露或手动输入数据。
```

## Excel requirements

Only modify a workbook supplied by the user or identified by an exact path. Before editing:

- Inventory sheets, hidden sheets, formulas, named ranges, external links, charts, data validation, merged cells, and target regions.
- Create a non-overwriting backup.
- Record the pre-change target cells and chart references.

Change only authorized input cells. Do not overwrite formulas, delete sheets, break named ranges, or silently change units and periods. After editing, report the backup path, exact cells, before/after values, source IDs, formula preservation, chart synchronization, and remaining manual checks.

## Delivery status

Label every output as one of:

- `Example`: mock values used only to demonstrate layout.
- `Draft`: source-backed but still requires named manual checks.
- `Reviewed`: required checks were completed and recorded.
- `Final`: use only when the user or designated reviewer explicitly accepts it as the formal deliverable.

A Skill test, layout preview, or source-limited analysis is never `Final` by default.

## Final quality gates

- Every news item has a source ID and timestamp or an explicit missing-timestamp flag.
- Every financial data row has a source ID, as-of date, unit, currency where relevant, and metric definition.
- Old items are separated from the current window.
- Facts and analyst inference are visually distinct.
- Trip.com and peer implications are specific and include a transmission path.
- Unsupported numbers remain unavailable, not estimated silently.
- HTML works at desktop and mobile widths, supports keyboard navigation, and has print CSS.
- Images have provenance and alt text; missing images do not produce decorative placeholders.
- Loading, empty, stale, partial, and error states are represented when relevant.
- The source ledger, data gaps, and prompt/scope summary are included.
- Excel changes are backed up, bounded, and reported at cell level.

## Protected boundaries

- Do not modify unrelated projects or `美股项目（1）`.
- Do not expose credentials, cookies, licensed raw exports, or confidential user data.
- Do not publish, email, upload, or externally share a brief unless the user explicitly requests that action.
- Do not treat market commentary as company guidance or confirmed management intent.
