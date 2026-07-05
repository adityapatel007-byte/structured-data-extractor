# Multi-model benchmark

_Generated: 2026-07-05T06:50:39+00:00_

10 receipts (5 SROIE + 5 CORD), synthetic text derived from public ground truth.
All runs use the same prompts, schemas, and post-processing — the only variable is the model.

| Model | Effort | Micro F1 | Macro F1 | Doc-exact | Latency (ms) | Cost / doc | Total cost |
|---|---|---:|---:|---:|---:|---:|---:|
| `gpt-5-nano` | minimal | 0.896 | 0.885 | 40% | 5098 | $0.01163 | $0.1164 |
| `gpt-5-mini` | minimal | 0.864 | 0.927 | 40% | 6115 | $0.01269 | $0.1269 |
| `gpt-5` | minimal | 0.884 | 0.939 | 30% | 5377 | $0.01182 | $0.1183 |

_Field-level breakdowns live in each combo's per-run report under `evaluation/reports/`._