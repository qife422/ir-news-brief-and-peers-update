# IR Professional Methodology

Read this reference for news selection, materiality scoring, interpretation, and IR actions.

## 1. Time and scope

Record one report time zone and convert source timestamps consistently. Use configurable windows rather than assuming every request is a 24-hour daily brief.

Suggested defaults when the user does not specify them:

- Current: previous 24 hours.
- Recent context: previous 7 calendar days.
- Structural context: older than 7 days, included only when needed to explain a current event.

Never place recent or structural context in the current-news count. If the source timestamp cannot be established, mark `timestamp_status: missing` and do not describe the item as latest.

## 2. Candidate selection

Select an item only when at least one concrete transmission path exists:

- Demand: travel intent, affordability, consumer confidence, destination mix.
- Supply: flight capacity, hotel inventory, visas, border policy, distribution access.
- Economics: take rate, pricing, marketing efficiency, customer service cost, FX, payment cost.
- Competition: search entry, loyalty, direct booking, inventory, M&A, regulation.
- Valuation: earnings expectations, risk premium, peer rerating, guidance credibility.

Generic AI or macro headlines without a travel, OTA, or valuation path belong outside the core brief.

## 3. Materiality score

Score each selected item from 1 to 5 on five dimensions:

| Dimension | Weight | Question |
|---|---:|---|
| Business impact | 35% | Could this affect demand, supply, revenue, margin, cash flow, or strategic position? |
| Trip.com relevance | 25% | Is the connection direct, company-specific, or clearly applicable to close peers? |
| Timeliness | 15% | Is the information inside the requested window and newly decision-useful? |
| Evidence confidence | 15% | Is it supported by primary or independently corroborated reliable sources? |
| IR actionability | 10% | Does it change monitoring, messaging, Q&A preparation, or investor outreach? |

Calculate:

```text
materiality_score = round(sum(score_i * weight_i) / 5 * 100)
```

Classification:

- High: 75-100.
- Medium: 50-74.
- Low: below 50.

Do not raise materiality merely because a headline is negative or popular. Keep `direction` separate: positive, negative, mixed, neutral, or uncertain.

## 4. Required analysis block

For each important item, keep these fields distinct:

1. **Confirmed fact:** what the source states.
2. **Transmission path:** the causal chain into travel, OTA, hotel, airline, or valuation outcomes.
3. **Company exposure:** which Trip.com business, geography, customer segment, or peer is affected.
4. **Direction and horizon:** positive/negative/mixed/uncertain; immediate, 1-2 quarters, or structural.
5. **Alternative interpretation:** the strongest reasonable counterpoint or uncertainty.
6. **IR action:** act now, prepare Q&A, monitor, or background only.

Use conditional language for inference. Do not convert correlation, market commentary, or a competitor claim into a confirmed Trip.com outcome.

## 5. IR action levels

- `Act now`: likely to prompt investor questions or change same-day messaging.
- `Prepare Q&A`: material enough to prepare evidence and management-approved wording.
- `Monitor`: define the indicator, threshold, and next check date.
- `Background`: useful context but no immediate action.

Avoid a vague recommendation such as “continue monitoring” unless the brief names what to monitor and why.

## 6. Compliance boundaries

- Use public or user-authorized information only.
- Do not combine public data with confidential context in a way that reveals material non-public information.
- Do not imply management guidance, strategic intent, or certainty without an attributable source.
- Separate analyst inference from company statements visually and linguistically.
- Record paywalled or licensed sources without reproducing restricted full text.
- Treat social media and commentary as signals, not proof, unless corroborated.
- Label machine-generated summaries as summaries, not source quotations.

## 7. Executive summary standard

Use three to five conclusions, ordered by decision importance. Each conclusion should answer:

- What changed?
- Why does it matter to Trip.com or its valuation narrative?
- What should IR do next?

Avoid repeating the article list in shorter form.

## 8. Investor questions and feedback

Group signals by durable business topics and compare with a named prior report. Distinguish newly published facts, newly obtained evidence, changed company wording and a changed interpretation. A first run is a baseline, not a measured trend.

Candidate questions are generated preparation ideas. Only eligible, manually confirmed meeting records count as actual questions; simulations and duplicate records never inflate counts. Explain priority using business relevance, supported change and preparation timing, without claiming a calibrated probability of investor questions.
