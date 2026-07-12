#!/usr/bin/env python3
"""Run one model lane of the 880-row paper matrix against Modal vLLM."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

from run_paper900 import campaign as local_campaign
from run_paper900 import expected_rows
from run_reviewer_extension import RUNS, run_one

MODAL_WORKSPACE = os.environ.get("VERIHARNESS_MODAL_WORKSPACE", "anonymous-workspace")
ENDPOINTS = {
    "qwen_coder_14b": f"https://{MODAL_WORKSPACE}--qwen.modal.run/v1/chat/completions",
    "llama_8b": f"https://{MODAL_WORKSPACE}--llama.modal.run/v1/chat/completions",
}
MODEL_NAMES = {"qwen_coder_14b": "qwen2.5-coder:14b", "llama_8b": "llama3.1:8b"}
GPU_NAMES = {"qwen_coder_14b": "L4", "llama_8b": "T4"}
TIME_BUDGET_SECONDS = 3 * 60 * 60


def modal_campaign(model_key: str) -> list[Dict[str, Any]]:
    marker = model_key
    items = []
    for source in local_campaign():
        if marker not in source["experiment_id"]:
            continue
        raw = json.loads(json.dumps(source))
        raw["experiment_id"] = f"modal_{raw['experiment_id']}"
        raw["model"].update(
            {
                "client": "local",
                "provider": "modal-vllm",
                "model_name": MODEL_NAMES[model_key],
                "endpoint": ENDPOINTS[model_key],
                "quantization": "AWQ-INT4",
                "timeout_seconds": 180,
            }
        )
        raw["metadata"].update(
            {
                "execution_backend": "modal-vllm",
                "modal_gpu": GPU_NAMES[model_key],
                "modal_app": "veriharness-paper900",
                "modal_time_budget_seconds": TIME_BUDGET_SECONDS,
                "checkpoint_policy": "persist every result row and raw leaf response",
            }
        )
        items.append(raw)
    return items


def write_state(model_key: str, items: list[Dict[str, Any]], started: float, status: str) -> None:
    blocks = []
    completed = total = 0
    for raw in items:
        path = RUNS / raw["experiment_id"] / "results.jsonl"
        rows = sum(1 for _ in path.open()) if path.exists() else 0
        expected = expected_rows(raw)
        completed += min(rows, expected)
        total += expected
        blocks.append({"experiment_id": raw["experiment_id"], "rows": rows, "expected": expected})
    payload = {
        "model_key": model_key,
        "gpu": GPU_NAMES[model_key],
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "time_budget_seconds": TIME_BUDGET_SECONDS,
        "rows": completed,
        "expected_rows": total,
        "blocks": blocks,
    }
    (RUNS / f"modal_paper900_{model_key}_state.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-key", choices=sorted(ENDPOINTS), required=True)
    args = parser.parse_args()
    items = modal_campaign(args.model_key)
    started = time.monotonic()
    write_state(args.model_key, items, started, "running")
    for index, raw in enumerate(items, start=1):
        if time.monotonic() - started >= TIME_BUDGET_SECONDS:
            write_state(args.model_key, items, started, "time_budget_exhausted")
            return
        print(f"[{index}/{len(items)}] {raw['experiment_id']}", flush=True)
        run_one(raw)
        write_state(args.model_key, items, started, "running")
    write_state(args.model_key, items, started, "complete")


if __name__ == "__main__":
    main()
