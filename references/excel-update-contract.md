# Excel Update Contract

Read this reference before changing a peer comparison workbook.

## 1. Authorization and target

Require:

- Exact source workbook path.
- Target company, reporting period, and metrics.
- Authoritative source IDs and as-of dates.
- Intended output path or permission to create a sibling updated workbook.

Do not assume the example filename or Booking 2026Q1 applies to every request.

## 2. Pre-change inventory

Inspect and record:

- Workbook type and whether macros are present.
- Visible and hidden sheets.
- Target table coordinates and existing periods.
- Formulas and array formulas.
- Named ranges and structured tables.
- Chart objects, series formulas, category ranges, and chart caches where accessible.
- External links, queries, pivots, data validation, conditional formatting, merged cells, and protection.
- Units, currencies, scaling conventions, and blank/zero conventions.

If the selected library cannot preserve a material workbook feature, stop before saving and report the limitation.

## 3. Backup

Create a byte-for-byte backup before mutation. Never overwrite an existing backup. Record path, size, modified time, and SHA-256 hash. Keep generated backup and output artifacts separate from the canonical source.

## 4. Cell mapping

Create an explicit update map before writing:

| Sheet | Cell | Metric | Period | Unit | Before | After | Source ID | Cell type |
|---|---|---|---|---|---|---|---|---|

`Cell type` must identify input, formula, label, or chart-support cell. Formulas are read-only unless the user explicitly authorizes a formula change.

## 5. Write rules

- Write only mapped cells.
- Preserve number formats, styles, comments, hyperlinks, validation, and protection.
- Preserve blanks as blanks; do not convert missing values to zero.
- Do not silently rescale values between units.
- Do not replace formulas with calculated values.
- Do not delete sheets, rows, columns, names, tables, or charts.
- Preserve macros by using a macro-capable workflow when applicable.

## 6. Chart synchronization

For every affected chart, verify:

- Series formula and category range.
- Sheet name quoting and absolute references.
- New quarter inclusion and order.
- Title, legend, axis labels, units, and number format.
- No unintended blank or zero categories.
- Cached chart data is refreshed when supported; otherwise record the manual refresh requirement.

Do not claim a chart is synchronized merely because source cells changed.

## 7. Post-change validation

- Reopen the saved workbook.
- Compare sheet names, dimensions, formulas, named ranges, and chart counts with the pre-change inventory.
- Confirm all mapped values and no unauthorized cells changed.
- Confirm formulas remain formulas and do not contain new errors.
- Verify the workbook opens without a repair warning when the available tooling permits.
- Produce a modification report and hash for the updated file.

## 8. Delivery report

Report:

- Source, backup, and output paths.
- Backup and output hashes.
- Modified sheets and exact cells.
- Before/after values, units, periods, and source IDs.
- Formula, style, named-range, external-link, and hidden-sheet preservation.
- Chart series synchronization and cache/refresh status.
- Tooling limitations and remaining manual checks.
