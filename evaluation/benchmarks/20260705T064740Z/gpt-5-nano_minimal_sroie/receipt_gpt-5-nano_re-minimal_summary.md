# Evaluation Report — `receipt` on `gpt-5-nano_re-minimal`

_Generated: 2026-07-05T06:48:10+00:00_

## Headline

| Metric | Value |
|---|---|
| Documents evaluated | 5 |
| Extractor errors    | 0 |
| **Micro F1**        | **0.9355** |
| **Macro F1**        | **0.9815** |
| Doc exact-match rate| 20.00% |
| Mean latency        | 5366 ms |
| Mean cost / doc     | $0.011673 |
| Total cost          | $0.0584 |
| Wall time           | 26.84 s |

## Per-field performance

| Field | Type | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| `currency` | exact | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[]` | number | 5 | 1.000 | 1.000 | 1.000 |
| `merchant` | text | 5 | 1.000 | 1.000 | 1.000 |
| `total` | money | 5 | 1.000 | 1.000 | 1.000 |
| `transaction_date` | date | 5 | 1.000 | 1.000 | 1.000 |
| `merchant_address.line1` | text | 5 | 1.000 | 0.800 | 0.889 |
| `merchant_address.line2` | text | 0 | 0.000 | 0.000 | 0.000 |
| `subtotal` | money | 0 | 0.000 | 0.000 | 0.000 |
