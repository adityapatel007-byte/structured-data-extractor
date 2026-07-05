# Evaluation Report — `receipt` on `gpt-5-mini_re-minimal`

_Generated: 2026-07-05T06:49:41+00:00_

## Headline

| Metric | Value |
|---|---|
| Documents evaluated | 5 |
| Extractor errors    | 0 |
| **Micro F1**        | **0.9333** |
| **Macro F1**        | **0.8880** |
| Doc exact-match rate| 60.00% |
| Mean latency        | 6677 ms |
| Mean cost / doc     | $0.013542 |
| Total cost          | $0.0677 |
| Wall time           | 33.39 s |

## Per-field performance

| Field | Type | Support | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| `currency` | exact | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[0].description` | text | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[0].quantity` | number | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[]` | number | 5 | 1.000 | 1.000 | 1.000 |
| `merchant` | text | 5 | 1.000 | 1.000 | 1.000 |
| `subtotal` | money | 5 | 1.000 | 1.000 | 1.000 |
| `tax` | money | 5 | 1.000 | 1.000 | 1.000 |
| `total` | money | 5 | 1.000 | 1.000 | 1.000 |
| `line_items[0].total` | money | 5 | 1.000 | 0.800 | 0.889 |
| `line_items[0].unit_price` | money | 5 | 0.750 | 0.600 | 0.667 |
| `line_items[1].description` | text | 4 | 1.000 | 1.000 | 1.000 |
| `line_items[1].quantity` | number | 4 | 1.000 | 1.000 | 1.000 |
| `line_items[1].total` | money | 4 | 1.000 | 0.750 | 0.857 |
| `line_items[1].unit_price` | money | 4 | 0.667 | 0.500 | 0.571 |
| `line_items[2].description` | text | 1 | 1.000 | 1.000 | 1.000 |
| `line_items[2].quantity` | number | 1 | 1.000 | 1.000 | 1.000 |
| `line_items[2].total` | money | 1 | 1.000 | 1.000 | 1.000 |
| `line_items[2].unit_price` | money | 1 | 0.000 | 0.000 | 0.000 |
