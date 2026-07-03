from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .harness import AutoResearchHarness, HarnessConfig
from .llm import make_provider
from .models import load_plans, select_plans, slugify

DEFAULT_PLANS_FILE = Path("plans/optimization.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the autoresearch harness.")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="run one or more research plans")
    run.add_argument("--plans-file", type=Path, default=DEFAULT_PLANS_FILE)
    run.add_argument("--plan-id", action="append", default=[], help="plan id to run; repeatable")
    run.add_argument("--limit", type=int, default=0, help="limit number of selected plans")
    run.add_argument("--provider", choices=["codex", "mock"], default="codex")
    run.add_argument("--model", default=None, help="optional model name for provider=codex")
    run.add_argument("--timeout", type=int, default=900, help="per-LLM-call timeout in seconds")
    run.add_argument("--out", type=Path, default=Path("runs"))
    run.add_argument("--label", default="optimization")
    run.add_argument("--max-tasks", type=int, default=4)
    run.add_argument("--concurrency", type=int, default=2)
    run.add_argument("--synthesis-context-chars", type=int, default=18000)

    subparsers.add_parser("list-samples", help="list sample plan ids")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    if command == "list-samples":
        plans = load_plans(DEFAULT_PLANS_FILE)
        for plan in plans:
            print(f"{plan.plan_id}\t{plan.title}")
        return 0

    if command != "run":
        parser.error(f"unknown command: {command}")

    plans = load_plans(args.plans_file)
    plans = select_plans(plans, args.plan_id, args.limit)
    if not plans:
        raise SystemExit("no plans selected")

    provider = make_provider(args.provider, model=args.model, timeout_seconds=args.timeout)
    config = HarnessConfig(
        output_dir=args.out,
        max_tasks=args.max_tasks,
        concurrency=max(1, args.concurrency),
        synthesis_context_chars=args.synthesis_context_chars,
    )
    harness = AutoResearchHarness(provider, config)
    store = harness.run(plans, label=args.label)
    print(f"Run complete: {store.root}")
    for plan in plans:
        print(f"- {plan.plan_id}: {store.root / slugify(plan.plan_id) / 'report.md'}")
    return 0
