# Evaluation Report — `receipt` on `gpt-5-mini_re-minimal`

_Generated: 2026-07-05T06:49:06+00:00_

## Headline

| Metric | Value |
|---|---|
| Documents evaluated | 5 |
| Extractor errors    | 0 |
| **Micro F1**        | **0.7945** |
| **Macro F1**        | **0.9667** |
| Doc exact-match rate| 20.00% |
| Mean latency        | 5553 ms |
| Mean cost / doc     | $0.011845 |
| Total cost          | $0.0592 |
| Wall time           | 27.77 s |

## Per-field performance

| Field | Type | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| `currency` | exact | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[]` | number | 5 | 1.000 | 1.000 | 1.000 |
| `merchant` | text | 5 | 1.000 | 1.000 | 1.000 |
| `total` | money | 5 | 1.000 | 1.000 | 1.000 |
| `transaction_date` | date | 5 | 1.000 | 1.000 | 1.000 |
| `merchant_address.line1` | text | 5 | 0.800 | 0.800 | 0.800 |
| `merchant_address.city` | text | 0 | 0.000 | 0.000 | 0.000 |
| `merchant_address.country` | exact | 0 | 0.000 | 0.000 | 0.000 |
| `merchant_address.line2` | text | 0 | 0.000 | 0.000 | 0.000 |
| `merchant_address.postal_code` | exact | 0 | 0.000 | 0.000 | 0.000 |
| `merchant_address.region` | text | 0 | 0.000 | 0.000 | 0.000 |
