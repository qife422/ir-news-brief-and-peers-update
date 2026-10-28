# TEST PLAN

## IR workflow 2.1 additions

- Future/private/retracted/unconfirmed actual or paraphrased question records cannot leak wording, follow-ups or derived answers through public trigger claims. Confirmed historical records work; paraphrases do not count as actual questions.
- Coverage requires an eligible confirmed non-Example public fact for the exact company/period, not merely a source, a question, an empty topic or a claimed case label.
- Full workspace, candidate report, prompt/config and core fingerprints must match; changed inputs or future freeze times cannot retain review applicability.
- Review binds the exact candidate; future reviews, review-before-freeze/holdout, contaminated or future holdout declarations remain pending.
- Missing measurements stay null; uncertain facts are not correct; inconsistent counts, non-finite values and incomparable timings do not produce false improvement claims.
- Both new CLI paths reject overwriting outputs or inputs. Examples and complete declarations never auto-accept real business cases or promote to Final.

See [pilot-acceptance.md](references/pilot-acceptance.md) for the actual human review protocol. These tests do not conduct a real blind comparison or measure business efficiency.

## IR workflow 2.0

Run the same unittest discovery command below to cover the original brief and new workflow. New fixtures are declared Example; factual text still needs passage review.

| Plan AC | Executable coverage | Additional review |
|---|---|---|
| A1 | timezone/cutoff, unknown availability, fixed material versions and future events | Verify historical availability evidence |
| A2 | company attribution and structured inference/position distinctions | Read the passage and assess statement support |
| A3 | retraction, independent complete support groups, review digests and expiry | Confirm a second source independently supports the full claim |
| A4 | authorized/visibility/audience projection, declared derivatives, raw metadata exclusion | Confirm the real processing authorization, not only fixture flags |
| A5 | Decimal differences, all definition fields, zero/negative bases and pre-release snapshots | Verify licensed or public snapshot provenance |
| A6 | actual/anticipated/reported types, confirmation, deduplication, revocation | Verify real meeting records and permissions |
| A7 | CLI exclusive writes, events preserve input, original brief tests | Review exact changed files |
| A8 | citation closure, HTML escaping, embedded projected data, Markdown source locators | Desktop/mobile/filter/keyboard/print in a real browser |

Quick new workflow check:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/ir_workflow.py validate examples/ir-workspace.example.json
```

Use an independent forward trial with a realistic request and raw authorized materials. A second agent's output is auxiliary evidence, not human IR acceptance. Actual run results and source/content fingerprints belong in the using project's evidence manifest.

## Automated checks

Run from the Skill directory:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_ir_data.py examples/ir-brief-data.example.json
python3 scripts/render_html_brief.py examples/ir-brief-data.example.json output/ir-brief-example.html
```

Expected:

- The example passes validation.
- Unknown source IDs fail validation.
- A news image without alt text and image provenance fails validation.
- `Final` status without explicit approval fails validation.
- HTML contains embedded report data and no unresolved template marker.
- The renderer refuses accidental overwrite unless `--force` is supplied.

## Behavioral scenarios

### 1. No search authorization

Request a current brief without providing sources or authorizing public search.

Expected: define the required scope and request search authorization; do not invent current news.

### 2. Current versus context

Provide current, seven-day, and older structural news.

Expected: current counts exclude context; old items remain visibly labeled.

### 3. Materiality versus sentiment

Provide a viral but low-business-impact negative story and a less popular high-impact policy story.

Expected: the policy story ranks higher; direction remains a separate field.

### 4. Fact versus inference

Provide a company announcement and a media interpretation.

Expected: confirmed facts, transmission path, counterpoint, and IR action remain distinct.

### 5. Missing peer data

Provide no licensed or public comparable data.

Expected: render an honest unavailable state; do not create fake multiples or zero placeholders.

### 6. Inconsistent peer definitions

Provide different valuation dates, fiscal years, or GAAP/non-GAAP metrics.

Expected: block the median/premium calculation until comparability is resolved or explicitly qualified.

### 7. HTML visual integrity

Use source-backed data with and without approved images.

Expected: real images include alt text and attribution; missing images use an intentional no-image layout; charts show units, dates, and Source IDs.

### 8. Responsive and print review

Review the generated HTML at desktop, tablet, and mobile widths, then print to PDF.

Expected: controls wrap, tables remain readable, source content is available without hover, print hides interactive controls, and no key block is clipped.

### 9. Excel without workbook

Request an update without a workbook path.

Expected: request the exact workbook and target metrics; do not assume workbook structure.

### 10. Excel preservation

Provide a workbook containing formulas, named ranges, hidden sheets, charts, and formatting.

Expected: create a non-overwriting hashed backup, modify only mapped input cells, verify chart series rather than merely source cells, and report exact before/after values.

### 11. Formal-delivery boundary

Generate a layout preview or source-limited report.

Expected: status remains `Example` or `Draft`; never call it `Final` without explicit human approval.

## Manual HTML checklist

- No console errors.
- Keyboard focus is visible and all filters are reachable.
- Color is not the only direction indicator.
- Charts remain readable at 1440px, 1024px, 768px, and 390px.
- No synthetic image is presented as documentary evidence.
- No unsupported number is added for visual balance.
- Source links and Source IDs match the structured input.
- Example banner remains visible for example data.
- Print preview preserves headings, charts, tables, and sources.
