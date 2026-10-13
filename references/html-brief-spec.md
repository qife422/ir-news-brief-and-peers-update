# HTML IR Brief Specification

Read this reference when producing HTML, charts, image-led news cards, responsive layouts, or print/PDF output.

## 1. Design read

Treat the deliverable as a trust-first financial intelligence page for IR professionals, not a marketing landing page and not a decorative dashboard.

- Design variance: 4/10.
- Motion intensity: 2/10.
- Visual density: 7/10.
- Theme: one restrained light theme unless the user requests otherwise.
- Typography: highly legible sans-serif; tabular or monospace numerals.
- Accent: one restrained brand-compatible blue; reserve green, red, and amber for actual semantic direction or status.

The page should feel like an analyst workspace that can also be printed for management.

## 2. Information architecture

Use this order unless the user specifies another decision flow:

1. Compact report header with status, as-of time, coverage, freshness, filters, and print action.
2. Three to five executive conclusions.
3. Lead stories with real source-authorized images when available.
4. Impact/urgency matrix and market pulse.
5. Peer valuation and operating comparison.
6. Macro, technology/AI, and OTA/travel news views.
7. IR action queue and data gaps.
8. Source ledger and prompt/scope disclosure.

Do not make users scroll through methodology before seeing conclusions.

## 3. Visualization mapping

Choose the smallest chart that answers the question:

| Question | Preferred visual |
|---|---|
| What needs attention now? | Impact versus urgency scatter |
| How did a market indicator move? | Sparkline plus current value and change |
| Which peer trades at a premium? | Horizontal dot plot with peer median |
| How do growth and margin compare? | Two-axis scatter with company labels |
| How did indexed prices perform? | Indexed line chart from a common base date |
| Actual versus consensus? | Grouped bars or compact variance columns |
| Which news is positive or negative? | Labeled direction field plus grouped counts, not color alone |

Avoid radar charts, 3D charts, oversized gauges, decorative progress bars, and charts that repeat a two-row table.

## 4. News cards and images

Each lead card should contain:

- Image only when it is a real, licensed or source-authorized asset.
- Functional alt text and image-source attribution.
- Title, source, published time, category, region, and related company.
- Confirmed-fact summary.
- Transmission path.
- Direction, horizon, materiality score, and IR action.
- Source IDs and manual-review status.

Do not generate or use synthetic images depicting a real news event, company property, executive, aircraft, or hotel as if they were documentary evidence. When no valid image exists, use a clean text-and-data layout without a fake placeholder image.

## 5. Interaction

Useful interactions include:

- Filter by category, company, region, materiality, and review status.
- Expand a news item to see evidence and counterpoints.
- Hover or focus a chart point for value, date, unit, and source ID.
- Switch between summary, news, peers, and sources.
- Print or save as PDF from the same HTML document.

Filters must work locally on the supplied report data and must not silently trigger external requests.

## 6. Accessibility and semantics

- Use semantic headings, landmarks, tables, buttons, labels, and links.
- Support keyboard access and visible focus states.
- Meet WCAG AA contrast for body text and controls.
- Do not encode direction or materiality by color alone; pair color with text or symbols.
- Provide useful alt text for factual images and empty alt text for purely decorative assets.
- Respect reduced-motion preferences. Default motion should be limited to hover, focus, and disclosure transitions.
- Provide a skip link and readable table overflow on narrow screens.

## 7. Responsive behavior

- Desktop: multi-column summary, charts, and lead-story layout.
- Below 1024px: charts and story panels reduce to two columns where possible.
- Below 768px: strict single column; tables scroll horizontally; controls wrap without truncating labels.
- Never require hover to access source or value details.

## 8. Print and PDF

Use print CSS to:

- Hide filters, interactive-only controls, and navigation.
- Expand disclosure content required for review.
- Preserve source IDs and URLs where practical.
- Avoid splitting a lead story, chart, or source record across pages when possible.
- Repeat table headers.
- Use a white background and print-safe semantic colors.

The PDF is a rendered view of the validated HTML, not a separately maintained document.

## 9. Required states

- Loading: skeletons shaped like the actual layout if data is loaded asynchronously.
- Empty: explain which authorized input or dataset is missing.
- Partial: show available sections and a visible data-gap notice.
- Stale: show the stale as-of date and exclude invalid current comparisons.
- Error: state what failed without hiding the rest of the report.
- Example: show a persistent banner that values are demonstration-only.

## 10. Output integrity

The HTML must be self-contained by default and must not require a CDN to display its core content or charts. Remote images may load only when the structured input explicitly supplies approved URLs. Escape all external text before inserting it into HTML.
