"""Tests for the fine-tuning dataset prep script.

No network / no OpenAI calls — pure JSON transformation tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_smoke(tmp_path: Path, rows: list[dict]) -> Path:
    """Write a JSONL fixture in the same shape as evaluation/smoke_*_sample.jsonl."""
    p = tmp_path / "smoke.jsonl"
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


def _run_prep(input_path: Path, out_prefix: Path, doc_type: str = "receipt") -> subprocess.CompletedProcess:
    """Always pass absolute paths — the script handles both absolute and relative."""
    return subprocess.run(
        [sys.executable, "scripts/prep_ft_dataset.py",
         "--input", str(input_path),
         "--doc-type", doc_type,
         "--out", str(out_prefix),
         "--val-frac", "0.2",
         "--seed", "42"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def _valid_smoke_rows(n: int) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append({
            "id": f"synthetic_{i}",
            "source": "test",
            "text": f"MERCHANT {i}\nTOTAL USD {10 + i}.99\n",
            "ground_truth": {
                "merchant": f"MERCHANT {i}",
                "total": 10.0 + i + 0.99,
                "currency": "USD",
            },
        })
    return rows


# --- shape ------------------------------------------------------------

def test_prep_produces_openai_chat_format(tmp_path):
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(10))
    out = tmp_path / "ft" / "receipt"
    r = _run_prep(input_path, out)
    assert r.returncode == 0, r.stderr

    train_path = out.with_name(out.name + "_train.jsonl")
    val_path   = out.with_name(out.name + "_val.jsonl")
    assert train_path.exists()
    assert val_path.exists()

    with train_path.open() as f:
        first = json.loads(f.readline())
    assert "messages" in first
    roles = [m["role"] for m in first["messages"]]
    assert roles == ["system", "user", "assistant"]


def test_assistant_content_is_valid_envelope_json(tmp_path):
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(10))
    out = tmp_path / "ft" / "receipt"
    _run_prep(input_path, out)

    train_path = out.with_name(out.name + "_train.jsonl")
    with train_path.open() as f:
        for line in f:
            row = json.loads(line)
            asst = row["messages"][2]["content"]
            envelope = json.loads(asst)
            assert set(envelope.keys()) == {"data", "field_confidences", "warnings"}
            assert isinstance(envelope["data"], dict)
            assert isinstance(envelope["field_confidences"], list)
            assert isinstance(envelope["warnings"], list)


def test_system_prompt_is_the_production_prompt(tmp_path):
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(10))
    out = tmp_path / "ft" / "receipt"
    _run_prep(input_path, out)

    train_path = out.with_name(out.name + "_train.jsonl")
    with train_path.open() as f:
        first = json.loads(f.readline())
    sys_msg = first["messages"][0]["content"]
    # The receipt prompt starts with a specific opening line — verify we\'re
    # baking THAT into the fine-tune, not some ad-hoc other prompt.
    assert "receipts" in sys_msg.lower()
    assert "CRITICAL EXTRACTION RULES" in sys_msg


def test_user_message_matches_production_shape(tmp_path):
    """The user-message format has to match what DocumentExtractor sends at
    inference. If they diverge, the fine-tune won\'t transfer."""
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(10))
    out = tmp_path / "ft" / "receipt"
    _run_prep(input_path, out)

    train_path = out.with_name(out.name + "_train.jsonl")
    with train_path.open() as f:
        first = json.loads(f.readline())
    user_msg = first["messages"][1]["content"]
    assert "---BEGIN DOCUMENT TEXT---" in user_msg
    assert "---END DOCUMENT TEXT---" in user_msg


# --- split ------------------------------------------------------------

def test_split_80_20_and_deterministic(tmp_path):
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(10))
    out = tmp_path / "ft" / "receipt"
    _run_prep(input_path, out)

    n_train = sum(1 for _ in (out.with_name(out.name + "_train.jsonl")).open())
    n_val   = sum(1 for _ in (out.with_name(out.name + "_val.jsonl")).open())
    assert n_train + n_val == 10
    # 20% of 10 = 2 val rows, 8 train rows.
    assert n_val == 2
    assert n_train == 8


# --- error handling ---------------------------------------------------

def test_skips_rows_missing_text_without_crashing(tmp_path):
    rows = _valid_smoke_rows(9) + [{
        "id": "no_text", "source": "test",
        "ground_truth": {"merchant": "X", "total": 1.0, "currency": "USD"},
    }]
    input_path = _write_smoke(tmp_path, rows)
    out = tmp_path / "ft" / "receipt"
    r = _run_prep(input_path, out)
    assert r.returncode == 0
    assert "no_text" in r.stderr  # skipped-line warning printed to stderr


def test_exit_code_2_when_input_missing(tmp_path):
    r = _run_prep(tmp_path / "does_not_exist.jsonl", tmp_path / "ft" / "r")
    assert r.returncode == 2


def test_warns_below_openai_minimum(tmp_path):
    input_path = _write_smoke(tmp_path, _valid_smoke_rows(5))
    out = tmp_path / "ft" / "receipt"
    r = _run_prep(input_path, out)
    assert r.returncode == 0
    assert ">= 10" in r.stderr  # the explicit-minimum warning


def test_filing_doc_type_uses_filing_prompt(tmp_path):
    rows = [{
        "id": "syn_filing",
        "source": "test",
        "text": "Company FORM 10-K\nRevenue: $100M",
        "ground_truth": {
            "cover":       {"company_name": "Test Co"},
            "financials":  {"currency": "USD"},
            "top_risk_factors": [],
        },
    }] * 10
    input_path = _write_smoke(tmp_path, rows)
    out = tmp_path / "ft" / "filing"
    r = _run_prep(input_path, out, doc_type="filing")
    assert r.returncode == 0, r.stderr

    train_path = out.with_name(out.name + "_train.jsonl")
    with train_path.open() as f:
        first = json.loads(f.readline())
    assert "10-K" in first["messages"][0]["content"]
