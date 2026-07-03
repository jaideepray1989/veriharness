from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from veriharness.experiments.aggregate import (
    CONTEXT_BLOAT_FAILURE_CODES,
    aggregate_rows,
    read_results,
    write_aggregate,
)
from veriharness.experiments.stats import bootstrap_ci


BASELINE_NAME = "AutoResearch-style self-accept harness"


def compile_workshop_bundle(
    run_dirs: Iterable[Path],
    out_dir: Path,
    expected_rows: int = 0,
) -> Dict[str, Any]:
    """Compile workshop-oriented tables across model-matrix runs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    materialized_runs = [Path(run_dir) for run_dir in run_dirs]

    all_rows: List[Dict[str, Any]] = []
    model_rows: List[Dict[str, Any]] = []
    variant_rows: List[Dict[str, Any]] = []
    benchmark_rows: List[Dict[str, Any]] = []
    failure_rows: List[Dict[str, Any]] = []

    for run_dir in materialized_runs:
        rows = read_results(run_dir)
        if not rows:
            continue
        write_aggregate(run_dir)
        all_rows.extend(rows)
        model_rows.append(_model_summary(run_dir, rows, expected_rows))
        variant_rows.extend(_variant_summary(rows))
        benchmark_rows.extend(_benchmark_summary(rows))
        failure_rows.extend(_failure_taxonomy(rows))

    baseline_rows = _baseline_comparison(all_rows)
    example_rows = _failure_examples(materialized_runs)

    combined = aggregate_rows(all_rows)
    _write_json(out_dir / "combined_aggregate.json", combined)
    _write_csv(out_dir / "model_summary.csv", model_rows)
    _write_csv(out_dir / "variant_summary.csv", variant_rows)
    _write_csv(out_dir / "benchmark_summary.csv", benchmark_rows)
    _write_csv(out_dir / "baseline_comparison.csv", baseline_rows)
    _write_csv(out_dir / "failure_taxonomy.csv", failure_rows)
    _write_csv(out_dir / "failure_examples.csv", example_rows)

    (out_dir / "baseline_comparison.md").write_text(
        _baseline_markdown(baseline_rows), encoding="utf-8"
    )
    (out_dir / "failure_examples.md").write_text(
        _examples_markdown(example_rows), encoding="utf-8"
    )
    (out_dir / "workshop_results.md").write_text(
        _workshop_markdown(model_rows, variant_rows, baseline_rows, example_rows),
        encoding="utf-8",
    )

    return {
        "out_dir": str(out_dir),
        "models": len(model_rows),
        "rows": len(all_rows),
        "complete_models": sum(1 for row in model_rows if row["complete"]),
        "artifacts": [
            "workshop_results.md",
            "baseline_comparison.md",
            "failure_examples.md",
            "model_summary.csv",
            "variant_summary.csv",
            "benchmark_summary.csv",
            "baseline_comparison.csv",
            "failure_taxonomy.csv",
            "failure_examples.csv",
            "combined_aggregate.json",
        ],
    }


def _model_summary(run_dir: Path, rows: List[Dict[str, Any]], expected_rows: int) -> Dict[str, Any]:
    successes = [1.0 if row.get("success") else 0.0 for row in rows]
    ci_low, ci_high = bootstrap_ci(successes)
    success_count = int(sum(successes))
    leaf_calls = sum(int(row.get("num_leaf_calls") or 0) for row in rows)
    retries = sum(int(row.get("num_retries") or 0) for row in rows)
    wall_time = sum(float(row.get("wall_time_sec") or 0.0) for row in rows)
    first = rows[0]
    return {
        "run_dir": str(run_dir),
        "model_name": first.get("model_name", ""),
        "provider": first.get("model_provider", ""),
        "parameter_label": first.get("model_parameter_count_label", ""),
        "parameter_count": first.get("model_parameter_count", ""),
        "rows": len(rows),
        "expected_rows": expected_rows or len(rows),
        "complete": len(rows) == expected_rows if expected_rows else True,
        "success": success_count,
        "success_rate": success_count / len(rows) if rows else 0.0,
        "success_ci_low": ci_low,
        "success_ci_high": ci_high,
        "leaf_calls": leaf_calls,
        "retries": retries,
        "avg_leaf_calls": leaf_calls / len(rows) if rows else 0.0,
        "avg_retries": retries / len(rows) if rows else 0.0,
        "wall_time_sec": wall_time,
        "avg_wall_time_sec": wall_time / len(rows) if rows else 0.0,
    }


def _variant_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[str(row.get("variant", ""))].append(row)

    first = rows[0]
    output = []
    for variant, group in sorted(by_variant.items()):
        successes = [1.0 if row.get("success") else 0.0 for row in group]
        ci_low, ci_high = bootstrap_ci(successes)
        success_count = int(sum(successes))
        leaf_calls = sum(int(row.get("num_leaf_calls") or 0) for row in group)
        retries = sum(int(row.get("num_retries") or 0) for row in group)
        context_bloat = sum(
            1
            for row in group
            if CONTEXT_BLOAT_FAILURE_CODES.intersection(row.get("failure_reasons", []))
        )
        output.append({
            "model_name": first.get("model_name", ""),
            "parameter_label": first.get("model_parameter_count_label", ""),
            "variant": variant,
            "n": len(group),
            "success": success_count,
            "success_rate": success_count / len(group) if group else 0.0,
            "success_ci_low": ci_low,
            "success_ci_high": ci_high,
            "leaf_calls": leaf_calls,
            "avg_leaf_calls": leaf_calls / len(group) if group else 0.0,
            "retries": retries,
            "avg_retries": retries / len(group) if group else 0.0,
            "accepted_by_agent": sum(1 for row in group if row.get("accepted_by_agent")),
            "accepted_by_gate": sum(1 for row in group if row.get("accepted_by_gate")),
            "gate_without_self_accept": sum(
                1 for row in group if row.get("accepted_by_gate") and not row.get("accepted_by_agent")
            ),
            "self_accept_without_gate": sum(
                1 for row in group if row.get("accepted_by_agent") and not row.get("accepted_by_gate")
            ),
            "premature_stop": sum(1 for row in group if row.get("premature_stop")),
            "wrong_claim_accepted": sum(1 for row in group if row.get("wrong_claim_accepted")),
            "constraint_violation": sum(1 for row in group if row.get("constraint_violation")),
            "context_bloat_proxy": context_bloat,
            "avg_wall_time_sec": sum(float(row.get("wall_time_sec") or 0.0) for row in group)
            / len(group)
            if group
            else 0.0,
        })
    return output


def _benchmark_summary(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_key: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    first = rows[0]
    for row in rows:
        by_key[(str(row.get("benchmark", "")), str(row.get("variant", "")))].append(row)

    output = []
    for (benchmark, variant), group in sorted(by_key.items()):
        success_count = sum(1 for row in group if row.get("success"))
        failures = Counter(reason for row in group for reason in row.get("failure_reasons", []))
        output.append({
            "model_name": first.get("model_name", ""),
            "parameter_label": first.get("model_parameter_count_label", ""),
            "benchmark": benchmark,
            "variant": variant,
            "n": len(group),
            "success": success_count,
            "success_rate": success_count / len(group) if group else 0.0,
            "premature_stop": sum(1 for row in group if row.get("premature_stop")),
            "wrong_claim_accepted": sum(1 for row in group if row.get("wrong_claim_accepted")),
            "constraint_violation": sum(1 for row in group if row.get("constraint_violation")),
            "context_bloat_proxy": sum(
                1
                for row in group
                if CONTEXT_BLOAT_FAILURE_CODES.intersection(row.get("failure_reasons", []))
            ),
            "accepted_by_agent": sum(1 for row in group if row.get("accepted_by_agent")),
            "accepted_by_gate": sum(1 for row in group if row.get("accepted_by_gate")),
            "leaf_calls": sum(int(row.get("num_leaf_calls") or 0) for row in group),
            "retries": sum(int(row.get("num_retries") or 0) for row in group),
            "failure_taxonomy": json.dumps(dict(failures), sort_keys=True),
        })
    return output


def _failure_taxonomy(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    first = rows[0]
    grouped: Counter[tuple[str, str, str]] = Counter()
    for row in rows:
        for reason in row.get("failure_reasons", []):
            grouped[(str(row.get("benchmark", "")), str(row.get("variant", "")), reason)] += 1
    return [
        {
            "model_name": first.get("model_name", ""),
            "parameter_label": first.get("model_parameter_count_label", ""),
            "benchmark": benchmark,
            "variant": variant,
            "failure_reason": reason,
            "count": count,
        }
        for (benchmark, variant, reason), count in sorted(grouped.items())
    ]


def _baseline_comparison(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_model = sorted({str(row.get("model_name", "")) for row in rows})
    output = []
    for model in by_model:
        model_rows = [row for row in rows if row.get("model_name") == model]
        label = str(model_rows[0].get("model_parameter_count_label", "")) if model_rows else ""
        for treatment in ["H3", "H4"]:
            baseline = [row for row in model_rows if row.get("variant") == "H0"]
            treated = [row for row in model_rows if row.get("variant") == treatment]
            paired = _paired_counts(baseline, treated)
            base_success = sum(1 for row in baseline if row.get("success"))
            treatment_success = sum(1 for row in treated if row.get("success"))
            output.append({
                "baseline": BASELINE_NAME,
                "treatment": treatment,
                "model_name": model,
                "parameter_label": label,
                "baseline_n": len(baseline),
                "treatment_n": len(treated),
                "baseline_success": base_success,
                "treatment_success": treatment_success,
                "baseline_success_rate": base_success / len(baseline) if baseline else 0.0,
                "treatment_success_rate": treatment_success / len(treated) if treated else 0.0,
                "success_rate_delta": (
                    treatment_success / len(treated) - base_success / len(baseline)
                    if baseline and treated
                    else 0.0
                ),
                "treatment_only": paired["treatment_only"],
                "baseline_only": paired["baseline_only"],
                "same_pass": paired["same_pass"],
                "same_fail": paired["same_fail"],
                "baseline_premature": sum(1 for row in baseline if row.get("premature_stop")),
                "treatment_premature": sum(1 for row in treated if row.get("premature_stop")),
                "baseline_context_bloat": sum(
                    1
                    for row in baseline
                    if CONTEXT_BLOAT_FAILURE_CODES.intersection(row.get("failure_reasons", []))
                ),
                "treatment_context_bloat": sum(
                    1
                    for row in treated
                    if CONTEXT_BLOAT_FAILURE_CODES.intersection(row.get("failure_reasons", []))
                ),
                "baseline_wrong_claim": sum(
                    1 for row in baseline if row.get("wrong_claim_accepted")
                ),
                "treatment_wrong_claim": sum(
                    1 for row in treated if row.get("wrong_claim_accepted")
                ),
                "baseline_leaf_calls": sum(int(row.get("num_leaf_calls") or 0) for row in baseline),
                "treatment_leaf_calls": sum(int(row.get("num_leaf_calls") or 0) for row in treated),
            })
    return output


def _paired_counts(
    baseline: List[Dict[str, Any]],
    treatment: List[Dict[str, Any]],
) -> Dict[str, int]:
    by_key = {
        (str(row.get("benchmark", "")), str(row.get("task_id", ""))): row
        for row in baseline
    }
    counts = {"treatment_only": 0, "baseline_only": 0, "same_pass": 0, "same_fail": 0}
    for row in treatment:
        key = (str(row.get("benchmark", "")), str(row.get("task_id", "")))
        baseline_row = by_key.get(key)
        if not baseline_row:
            continue
        base_success = bool(baseline_row.get("success"))
        treatment_success = bool(row.get("success"))
        if treatment_success and not base_success:
            counts["treatment_only"] += 1
        elif base_success and not treatment_success:
            counts["baseline_only"] += 1
        elif treatment_success and base_success:
            counts["same_pass"] += 1
        else:
            counts["same_fail"] += 1
    return counts


def _failure_examples(run_dirs: List[Path]) -> List[Dict[str, Any]]:
    rows_with_dir = []
    for run_dir in run_dirs:
        for row in read_results(run_dir):
            rows_with_dir.append((run_dir, row))

    selectors: List[tuple[str, Callable[[Dict[str, Any]], bool]]] = [
        (
            "context_bloat_proxy",
            lambda row: bool(
                CONTEXT_BLOAT_FAILURE_CODES.intersection(row.get("failure_reasons", []))
            ),
        ),
        (
            "self_biased_acceptance",
            lambda row: bool(row.get("premature_stop") or (row.get("accepted_by_agent") and not row.get("success"))),
        ),
        (
            "gate_repair_success",
            lambda row: row.get("variant") == "H4"
            and bool(row.get("success"))
            and int(row.get("num_retries") or 0) > 0,
        ),
        (
            "missing_artifact_or_evidence",
            lambda row: bool(
                {"artifact_missing", "claim_without_evidence", "empty_answer"}.intersection(
                    row.get("failure_reasons", [])
                )
            ),
        ),
        (
            "gate_without_self_accept",
            lambda row: bool(row.get("accepted_by_gate") and not row.get("accepted_by_agent")),
        ),
    ]

    examples = []
    used: set[tuple[str, str, str, str]] = set()
    for category, selector in selectors:
        for run_dir, row in rows_with_dir:
            if not selector(row):
                continue
            key = (
                category,
                str(row.get("model_name", "")),
                str(row.get("task_id", "")),
                str(row.get("variant", "")),
            )
            if key in used:
                continue
            examples.append(_example_row(category, run_dir, row))
            used.add(key)
            break
    return examples


def _example_row(category: str, run_dir: Path, row: Dict[str, Any]) -> Dict[str, Any]:
    artifact_dir = run_dir / str(row.get("run_path", ""))
    leaf = _load_json(artifact_dir / "leaf_output.json")
    gate = _load_json(artifact_dir / "gate_results.json")
    answer = leaf.get("answer", "") if isinstance(leaf, dict) else ""
    gate_failures = gate.get("failure_reasons", []) if isinstance(gate, dict) else []
    return {
        "category": category,
        "model_name": row.get("model_name", ""),
        "variant": row.get("variant", ""),
        "benchmark": row.get("benchmark", ""),
        "task_id": row.get("task_id", ""),
        "success": row.get("success", False),
        "accepted_by_agent": row.get("accepted_by_agent", False),
        "accepted_by_gate": row.get("accepted_by_gate", False),
        "premature_stop": row.get("premature_stop", False),
        "num_leaf_calls": row.get("num_leaf_calls", 0),
        "num_retries": row.get("num_retries", 0),
        "failure_reasons": json.dumps(row.get("failure_reasons", []), sort_keys=True),
        "gate_failure_reasons": json.dumps(gate_failures, sort_keys=True),
        "answer_preview": _preview(str(answer)),
        "artifact_dir": str(artifact_dir),
        "context_pack": str(artifact_dir / "context_pack.md"),
        "leaf_output": str(artifact_dir / "leaf_output.json"),
        "gate_results": str(artifact_dir / "gate_results.json"),
    }


def _preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _workshop_markdown(
    model_rows: List[Dict[str, Any]],
    variant_rows: List[Dict[str, Any]],
    baseline_rows: List[Dict[str, Any]],
    example_rows: List[Dict[str, Any]],
) -> str:
    lines = [
        "# Workshop Results Bundle",
        "",
        "This bundle compiles model-matrix VeriHarness runs into submission-ready tables.",
        "",
        "## Model Summary",
        "",
        "| Model | Params | Rows | Complete | Solve, 95% bootstrap CI | Leaf calls | Retries | Avg sec/row |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in model_rows:
        lines.append(
            "| {model} | {params} | {rows}/{expected} | {complete} | {solve}/{rows} "
            "({rate}, CI {lo}-{hi}) | {calls} | {retries} | {secs} |".format(
                model=row["model_name"],
                params=row["parameter_label"],
                rows=row["rows"],
                expected=row["expected_rows"],
                complete=str(row["complete"]).lower(),
                solve=row["success"],
                rate=_pct(row["success_rate"]),
                lo=_pct(row["success_ci_low"]),
                hi=_pct(row["success_ci_high"]),
                calls=row["leaf_calls"],
                retries=row["retries"],
                secs=f"{row['avg_wall_time_sec']:.1f}",
            )
        )

    lines.extend([
        "",
        "## Variant Summary",
        "",
        "| Model | Variant | Solve, 95% bootstrap CI | Avg calls | Retries | Gate no self-accept | Premature | Context bloat | Wrong claim |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in variant_rows:
        lines.append(
            "| {model} | {variant} | {solve}/{n} ({rate}, CI {lo}-{hi}) | {avg_calls} | "
            "{retries} | {gate_no_self} | {premature} | {context} | {wrong} |".format(
                model=row["model_name"],
                variant=row["variant"],
                solve=row["success"],
                n=row["n"],
                rate=_pct(row["success_rate"]),
                lo=_pct(row["success_ci_low"]),
                hi=_pct(row["success_ci_high"]),
                avg_calls=f"{row['avg_leaf_calls']:.2f}",
                retries=row["retries"],
                gate_no_self=row["gate_without_self_accept"],
                premature=row["premature_stop"],
                context=row["context_bloat_proxy"],
                wrong=row["wrong_claim_accepted"],
            )
        )

    lines.extend([
        "",
        "## Baseline Takeaway",
        "",
        _baseline_takeaway(baseline_rows),
        "",
        "## Example Taxonomy",
        "",
    ])
    for row in example_rows:
        lines.extend([
            f"- `{row['category']}`: `{row['model_name']}` `{row['variant']}` "
            f"`{row['benchmark']}` `{row['task_id']}`; "
            f"success={str(row['success']).lower()}, retries={row['num_retries']}, "
            f"reasons={row['failure_reasons']}.",
            f"  Artifact: `{row['artifact_dir']}`",
        ])

    lines.extend([
        "",
        "## Files",
        "",
        "- `model_summary.csv`",
        "- `variant_summary.csv`",
        "- `benchmark_summary.csv`",
        "- `baseline_comparison.csv`",
        "- `baseline_comparison.md`",
        "- `failure_examples.csv`",
        "- `failure_examples.md`",
        "- `combined_aggregate.json`",
        "",
    ])
    return "\n".join(lines)


def _baseline_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# Baseline Comparison",
        "",
        f"Baseline: `{BASELINE_NAME}`. Operationally this is H0: full trace in context, no independent acceptance gate, and leaf self-assessment controls done.",
        "",
        "| Axis | Baseline | VeriHarness H4 |",
        "|---|---|---|",
        "| Leaf action | LLM-generated structured output | LLM-generated structured output |",
        "| Acceptance | Leaf/model self-accepts | External gates accept/reject |",
        "| Context | Full accumulated trace | State/context pack |",
        "| Repair | No gate-conditioned repair | Failure-conditioned repair from gate feedback |",
        "| Traceability | Prompts and outputs | Prompts, outputs, gates, events, and retries |",
        "",
        "## Paired Results",
        "",
        "| Model | Treatment | Baseline solve | Treatment solve | Delta | Treatment-only | Baseline-only | Premature baseline->treatment | Leaf calls baseline->treatment |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {treatment} | {base}/{base_n} ({base_rate}) | "
            "{treated}/{treated_n} ({treated_rate}) | {delta} | {treatment_only} | "
            "{baseline_only} | {base_pre}->{treated_pre} | {base_calls}->{treated_calls} |".format(
                model=row["model_name"],
                treatment=row["treatment"],
                base=row["baseline_success"],
                base_n=row["baseline_n"],
                base_rate=_pct(row["baseline_success_rate"]),
                treated=row["treatment_success"],
                treated_n=row["treatment_n"],
                treated_rate=_pct(row["treatment_success_rate"]),
                delta=_signed_pct(row["success_rate_delta"]),
                treatment_only=row["treatment_only"],
                baseline_only=row["baseline_only"],
                base_pre=row["baseline_premature"],
                treated_pre=row["treatment_premature"],
                base_calls=row["baseline_leaf_calls"],
                treated_calls=row["treatment_leaf_calls"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _examples_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = ["# Failure And Repair Examples", ""]
    for row in rows:
        lines.extend([
            f"## {row['category']}",
            "",
            f"- Model: `{row['model_name']}`",
            f"- Variant: `{row['variant']}`",
            f"- Benchmark/task: `{row['benchmark']}` / `{row['task_id']}`",
            f"- Success: `{str(row['success']).lower()}`",
            f"- Accepted by agent/gate: `{row['accepted_by_agent']}` / `{row['accepted_by_gate']}`",
            f"- Retries: `{row['num_retries']}`",
            f"- Failure reasons: `{row['failure_reasons']}`",
            f"- Gate reasons: `{row['gate_failure_reasons']}`",
            f"- Answer preview: `{row['answer_preview']}`",
            f"- Artifact dir: `{row['artifact_dir']}`",
            "",
        ])
    return "\n".join(lines)


def _baseline_takeaway(rows: List[Dict[str, Any]]) -> str:
    h4 = [row for row in rows if row["treatment"] == "H4"]
    if not h4:
        return "No H4 baseline comparison rows were available."
    base_success = sum(int(row["baseline_success"]) for row in h4)
    base_n = sum(int(row["baseline_n"]) for row in h4)
    treatment_success = sum(int(row["treatment_success"]) for row in h4)
    treatment_n = sum(int(row["treatment_n"]) for row in h4)
    base_premature = sum(int(row["baseline_premature"]) for row in h4)
    treatment_premature = sum(int(row["treatment_premature"]) for row in h4)
    return (
        f"Against {BASELINE_NAME}, H4 solves {treatment_success}/{treatment_n} "
        f"({_pct(treatment_success / treatment_n if treatment_n else 0.0)}) versus "
        f"{base_success}/{base_n} ({_pct(base_success / base_n if base_n else 0.0)}), "
        f"while premature acceptance changes from {base_premature} to {treatment_premature}."
    )


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.1f} pp"

