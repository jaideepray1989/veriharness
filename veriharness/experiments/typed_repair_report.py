from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from veriharness.experiments.aggregate import paired_policy_tests, read_results

VARIANTS = ["generic+diagnostics", "typed-fields", "typed-repair+retain"]
COMPARISONS = [
    "typed-fields_vs_generic+diagnostics",
    "typed-repair+retain_vs_typed-fields",
    "typed-repair+retain_vs_generic+diagnostics",
]


def compile_typed_repair_evidence(
    run_dirs: Iterable[Path],
    out_path: Path,
    *,
    expected_rows_per_model: int = 1_992,
) -> Dict[str, Any]:
    materialized = [Path(run_dir) for run_dir in run_dirs]
    rows_by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for run_dir in materialized:
        rows = read_results(run_dir)
        if not rows:
            continue
        model = str(rows[0].get("model_name") or rows[0].get("model_client") or run_dir.name)
        rows_by_model[model].extend(rows)

    lines = ["# Cross-Benchmark Typed Repair Evidence", "", "## Completion", ""]
    lines.extend(["| Model | Rows | Expected | Complete |", "|---|---:|---:|---|"])
    for model, rows in sorted(rows_by_model.items()):
        lines.append(f"| {model} | {len(rows)} | {expected_rows_per_model} | {len(rows) == expected_rows_per_model} |")

    lines.extend(["", "## Success By Benchmark", ""])
    lines.extend(["| Model | Benchmark | Diagnostics | Typed fields | Full typed repair |", "|---|---|---:|---:|---:|"])
    for model, rows in sorted(rows_by_model.items()):
        grouped = _benchmark_variant_groups(rows)
        for benchmark in sorted(grouped):
            cells = [_success_cell(grouped[benchmark].get(variant, [])) for variant in VARIANTS]
            lines.append(f"| {model} | {benchmark} | {cells[0]} | {cells[1]} | {cells[2]} |")

    lines.extend(["", "## Paired Tests", ""])
    lines.extend(["| Model | Benchmark | Comparison | Delta | 95% paired CI | McNemar p |", "|---|---|---|---:|---:|---:|"])
    for model, rows in sorted(rows_by_model.items()):
        for benchmark, benchmark_rows in sorted(_benchmark_rows(rows).items()):
            tests = paired_policy_tests(benchmark_rows)
            for comparison in COMPARISONS:
                metrics = tests.get(comparison)
                if not metrics:
                    continue
                ci = metrics["delta_success_rate_ci"]
                lines.append(
                    f"| {model} | {benchmark} | {comparison} | "
                    f"{metrics['delta_success_rate'] * 100:+.1f} pp | "
                    f"{ci[0] * 100:+.1f} to {ci[1] * 100:+.1f} pp | {metrics['mcnemar_exact_p']:.3g} |"
                )

    lines.extend(
        [
            "",
            "HumanEval and DS-1000 official tests are post-hoc scores in this primary protocol. "
            "TextWorld and held-out MiniWorkflow provide online non-oracle repair feedback.",
            "",
        ]
    )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "out_path": str(out_path),
        "models": len(rows_by_model),
        "rows": sum(len(rows) for rows in rows_by_model.values()),
        "complete_models": sum(len(rows) == expected_rows_per_model for rows in rows_by_model.values()),
    }


def _benchmark_variant_groups(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row.get("benchmark", ""))][str(row.get("variant", ""))].append(row)
    return grouped


def _benchmark_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("benchmark", ""))].append(row)
    return grouped


def _success_cell(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "--"
    return f"{sum(bool(row.get('success')) for row in rows)}/{len(rows)}"
