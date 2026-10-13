# Data Governance and Peer Definitions

Read this reference when collecting sources, presenting market or financial data, calculating peer comparisons, or resolving missing/conflicting values.

## 1. Source hierarchy

Use the strongest available source for each claim:

1. Company IR sites, earnings releases, SEC or exchange filings, regulator and government releases.
2. Licensed market-data and consensus platforms, subject to the user's access rights.
3. Reuters, Bloomberg, FT, WSJ, CNBC, and other reputable financial media.
4. Established industry publications and attributable company announcements.
5. Commentary, social media, and WeChat articles as lower-confidence signals requiring manual review.

A secondary article quoting a primary document should link the primary document when available.

## 2. Source ledger

Assign stable IDs such as `S001`. Each source record should include:

- Source ID and source name.
- Source type: primary, filing, licensed, media, industry, commentary, or example.
- Title or dataset name.
- Published timestamp and time zone, or an explicit missing-timestamp state.
- URL or licensed-source note.
- Access timestamp.
- Reliability: high, medium, or low, with a short rationale when not obvious.
- Whether manual review is required.
- Claims or metrics supported.

Every news item references one or more source IDs. Every financial row references the source ID and as-of date used for that row.

## 3. Freshness and conflicts

- Record report `as_of` separately from source `published_at` and data `as_of`.
- Do not mix market prices from different dates in one peer comparison.
- When two reliable sources conflict, show both values, definitions, and timestamps. Do not silently choose the more convenient one.
- Mark stale inputs and exclude them from current comparisons unless the user accepts the limitation.
- Preserve the raw supplied value and store normalized values separately when conversion is required.

## 4. Metric dictionary

### Market capitalization

Price timestamp multiplied by the matching diluted or basic share count, depending on the stated convention. Record share class and ADS ratio. Do not combine a current price with an old share count without disclosure.

### Enterprise value

Use a stated convention, normally market capitalization plus debt, preferred stock, and non-controlling interests, less cash and cash equivalents. Record lease treatment and other adjustments when material.

### P/E

Price divided by EPS for the same share/ADS basis and period. Label actual versus consensus and GAAP versus adjusted. `25E`, `26E`, and `27E` are not sufficient without fiscal-year definitions and an as-of date.

### EV/EBITDA

Enterprise value divided by EBITDA for a matching period and definition. Label reported, adjusted, or consensus EBITDA and state lease treatment if it changes comparability.

### EPS growth CAGR

```text
CAGR = (ending EPS / starting EPS)^(1 / years) - 1
```

Do not calculate across negative or sign-changing EPS without explaining that CAGR is not meaningful.

### PEG

State the selected P/E period and EPS growth definition. Do not calculate PEG when the growth rate is zero, negative, sign-changing, or not comparable.

### Revenue growth and EBITDA margin

State reported currency, constant-currency treatment, gross versus net revenue convention, and adjusted versus reported EBITDA. OTA companies may not recognize bookings as revenue; do not compare gross bookings directly with revenue.

### Market performance

For indexed performance, set all securities to 100 at the same market close and disclose local currency versus common-currency treatment. Address non-overlapping trading days explicitly.

## 5. Quarterly earnings comparison

Recommended columns:

| Metric | Prior period | Actual | YoY | Consensus | Beat/Miss | Guidance | Unit | Definition | Source ID |
|---|---:|---:|---:|---:|---:|---:|---|---|---|

Do not label a result as a beat or miss unless the consensus source, snapshot time, and comparable metric definition are known.

## 6. Peer comparison controls

Before calculating a peer median or premium/discount, verify:

- Same valuation date or documented close-date alignment.
- Same fiscal-year basis.
- Same currency treatment where currency matters.
- Same share/ADS and diluted-share basis.
- Same GAAP or adjusted convention.
- Same enterprise-value and lease convention.
- No `N/A` value is converted to zero.

Premium/discount calculation:

```text
premium_discount = company_multiple / peer_median - 1
```

Show the peer set and whether the subject company is excluded from the median.

## 7. Missing data

Use `null` in structured data and `N/A` in human-facing output. Never use zero as a missing-data placeholder. State whether a gap is caused by unavailable access, non-comparable definitions, stale data, or pending manual input.

## 8. Persistent workflow evidence

For radar, earnings and meeting work, use stable workspace source/excerpt IDs rather than reusing a report-local S001 for different documents. Map IDs when exporting the old brief format. Record material identity, content/version time, access scope and source status. A historical replay needs proof that the exact material version was available by the cutoff.

Retraction or supersession propagates to dependent statements and answer reviews. Independent support means a complete independent source group supports the same claim, not that multiple sites repeat one announcement. Preserve input history and invalidate evidence after relevant changes.

Authorize processing and output separately. Filter before analysis and project only safe supported content. Do not embed a raw workspace into a public HTML file or leak excluded content through metadata, source summaries, attachments, error strings or private-derived text. Schema permissions do not create a company's processing authorization or a commercial-data licence.
