# Evaluation Report — `filing` on `gpt-5-nano_re-minimal`

_Generated: 2026-07-05T07:39:15+00:00_

## Headline

| Metric | Value |
|---|---|
| Documents evaluated | 5 |
| Extractor errors    | 0 |
| **Micro F1**        | **0.5600** |
| **Macro F1**        | **0.5685** |
| Doc exact-match rate| 0.00% |
| Mean latency        | 6085 ms |
| Mean cost / doc     | $0.060523 |
| Total cost          | $0.3026 |
| Wall time           | 30.53 s |

## Per-field performance

| Field | Type | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| `cover.cik` | text | 5 | 1.000 | 1.000 | 1.000 |
| `cover.fiscal_year_end` | date | 5 | 1.000 | 1.000 | 1.000 |
| `cover.ticker` | text | 5 | 1.000 | 1.000 | 1.000 |
| `financials.currency` | exact | 5 | 1.000 | 1.000 | 1.000 |
| `financials.fiscal_year` | number | 5 | 1.000 | 1.000 | 1.000 |
| `cover.company_name` | text | 5 | 0.800 | 0.800 | 0.800 |
| `top_risk_factors[]` | number | 5 | 0.800 | 0.800 | 0.800 |
| `cover.form_type` | text | 5 | 0.600 | 0.600 | 0.600 |
| `financials.total_assets` | number | 5 | 1.000 | 0.400 | 0.571 |
| `financials.operating_cash_flow` | number | 5 | 0.667 | 0.400 | 0.500 |
| `cover.filing_date` | date | 5 | 1.000 | 0.200 | 0.333 |
| `financials.eps_basic` | number | 5 | 1.000 | 0.200 | 0.333 |
| `financials.eps_diluted` | number | 5 | 1.000 | 0.200 | 0.333 |
| `financials.net_income` | number | 5 | 0.333 | 0.200 | 0.250 |
| `financials.revenue` | number | 5 | 0.333 | 0.200 | 0.250 |
| `financials.total_equity` | number | 5 | 0.000 | 0.000 | 0.000 |
| `financials.cash_and_equivalents` | number | 4 | 0.500 | 0.250 | 0.333 |
| `financials.cost_of_revenue` | number | 3 | 0.333 | 0.333 | 0.333 |
| `financials.total_debt` | number | 3 | 0.000 | 0.000 | 0.000 |
| `financials.operating_income` | number | 2 | 0.500 | 0.500 | 0.500 |
| `financials.gross_profit` | number | 1 | 1.000 | 1.000 | 1.000 |
| `cover.exchange` | text | 0 | 0.000 | 0.000 | 0.000 |
| `cover.state_of_incorporation` | text | 0 | 0.000 | 0.000 | 0.000 |
| `financials.free_cash_flow` | number | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[0].summary` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[0].theme` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[1].summary` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[1].theme` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[2].summary` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[2].theme` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[3].summary` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[3].theme` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[4].summary` | text | 0 | 0.000 | 0.000 | 0.000 |
| `top_risk_factors[4].theme` | text | 0 | 0.000 | 0.000 | 0.000 |
