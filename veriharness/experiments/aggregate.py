from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from veriharness.experiments.stats import bootstrap_ci, mean

CONTEXT_BLOAT_FAILURE_CODES = {
    "constraint_forgotten",
    "required_field_missing",
    "distractor_adopted",
    "json_field_mismatch",
    "expected_substring_missing",
    "forbidden_substring_present",
}

RESULT_COLUMNS = [
    "experiment_id",
    "task_id",
    "benchmark",
    "variant",
    "model_client",
    "model_name",
    "model_provider",
    "model_parameter_count",
    "model_active_parameter_count",
    "model_parameter_count_label",
    "seed",
    "trace_length",
    "constraint_position",
    "noise_type",
    "provenance_label",
    "success",
    "accepted_by_agent",
    "accepted_by_gate",
    "premature_stop",
    "wrong_claim_accepted",
    "constraint_violation",
    "tokens_in",
    "tokens_out",
    "num_leaf_calls",
    "num_retries",
    "wall_time_sec",
    "failure_reasons",
    "run_path",
]

POLICY_TEST_PAIRS = [
    ("H0", "H3"),
    ("H3", "generic-retry"),
    ("generic-retry", "natural-retry"),
    ("generic-retry", "retain+generic"),
    ("natural-retry", "targeted+untyped"),
    ("targeted+untyped", "typed+no-retain"),
    ("typed+no-retain", "H4"),
    ("retain+generic", "H4"),
    ("generic-retry", "H4"),
    ("H3", "H4"),
]


def read_results(run_dir: Path) -> List[Dict[str, Any]]:
    path = Path(run_dir) / "results.jsonl"
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _rate(rows: List[Dict[str, Any]], field: str) -> float:
    return mean(1.0 if row.get(field) else 0.0 for row in rows)


def _failure_rate(rows: List[Dict[str, Any]], codes: set[str]) -> float:
    return mean(1.0 if codes.intersection(row.get("failure_reasons", [])) else 0.0 for row in rows)


def aggregate_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)

    variants = {}
    for variant, group in sorted(by_variant.items()):
        successes = [1.0 if row.get("success") else 0.0 for row in group]
        ci = bootstrap_ci(successes)
        tokens = sum(float(row.get("tokens_in", 0)) + float(row.get("tokens_out", 0)) for row in group)
        success_count = sum(successes)
        variants[variant] = {
            "n": len(group),
            "success_rate": _rate(group, "success"),
            "success_rate_ci": list(ci),
            "accepted_by_agent_rate": _rate(group, "accepted_by_agent"),
            "accepted_by_gate_rate": _rate(group, "accepted_by_gate"),
            "context_bloat_proxy_rate": _failure_rate(group, CONTEXT_BLOAT_FAILURE_CODES),
            "self_biased_acceptance_rate": _rate(group, "premature_stop"),
            "constraint_violation_rate": _rate(group, "constraint_violation"),
            "premature_stop_rate": _rate(group, "premature_stop"),
            "wrong_claim_acceptance_rate": _rate(group, "wrong_claim_accepted"),
            "tokens_per_success": tokens / success_count if success_count else 0.0,
            "retries_per_success": sum(float(row.get("num_retries", 0)) for row in group) / success_count
            if success_count
            else 0.0,
        }

    context_rows = [row for row in rows if row.get("benchmark") == "context_trace"]
    provenance_rows = [row for row in rows if row.get("benchmark") == "provenance_bias"]
    return {
        "n_rows": len(rows),
        "by_variant": variants,
        "context_overload_slope": context_overload_slope(context_rows),
        "self_evaluation_bias_gap": self_evaluation_bias_gap(provenance_rows),
        "per_seed_results": per_seed_results(rows),
        "paired_policy_tests": paired_policy_tests(rows),
        "failure_modes_by_benchmark": failure_modes_by_benchmark(rows),
        "paired_deltas_by_benchmark": paired_deltas_by_benchmark(rows),
        "failure_taxonomy": failure_taxonomy(rows),
    }


def context_overload_slope(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)
    slopes = {}
    for variant, group in by_variant.items():
        lengths = sorted({int(row["trace_length"]) for row in group if row.get("trace_length") is not None})
        if len(lengths) < 2:
            slopes[variant] = 0.0
            continue
        min_rate = _rate([row for row in group if int(row["trace_length"]) == lengths[0]], "success")
        max_rate = _rate([row for row in group if int(row["trace_length"]) == lengths[-1]], "success")
        slopes[variant] = min_rate - max_rate
    return slopes


def self_evaluation_bias_gap(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[row["variant"]].append(row)
    gaps = {}
    for variant, group in by_variant.items():
        own = [row for row in group if row.get("provenance_label") == "own_previous_answer"]
        external = [row for row in group if row.get("provenance_label") != "own_previous_answer"]
        gaps[variant] = _rate(own, "wrong_claim_accepted") - _rate(external, "wrong_claim_accepted")
    return gaps


def failure_taxonomy(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for reason in row.get("failure_reasons", []):
            counter[reason] += 1
    return dict(counter)


def per_seed_results(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row.get("seed", 0))][str(row.get("variant", ""))].append(row)

    summary: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for seed, by_variant in sorted(grouped.items(), key=lambda item: item[0]):
        summary[seed] = {}
        for variant, group in sorted(by_variant.items()):
            successes = sum(1 for row in group if row.get("success"))
            summary[seed][variant] = {
                "n": len(group),
                "success_count": successes,
                "success_rate": successes / len(group) if group else 0.0,
                "num_leaf_calls": sum(int(row.get("num_leaf_calls") or 0) for row in group),
                "num_retries": sum(int(row.get("num_retries") or 0) for row in group),
                "premature_stop_count": sum(1 for row in group if row.get("premature_stop")),
            }
    return summary


def paired_policy_tests(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    materialized = list(rows)
    variants = {str(row.get("variant", "")) for row in materialized}
    by_key = {
        _instance_variant_key(row): row
        for row in materialized
        if row.get("variant") and row.get("task_id") and row.get("benchmark") is not None
    }
    instances = sorted({_instance_key(row) for row in materialized if row.get("task_id") and row.get("variant")})
    result: Dict[str, Dict[str, Any]] = {}
    for baseline, treatment in POLICY_TEST_PAIRS:
        if baseline not in variants or treatment not in variants:
            continue
        treatment_only = baseline_only = same_pass = same_fail = 0
        deltas: List[float] = []
        for instance in instances:
            baseline_row = by_key.get((*instance, baseline))
            treatment_row = by_key.get((*instance, treatment))
            if not baseline_row or not treatment_row:
                continue
            baseline_success = bool(baseline_row.get("success"))
            treatment_success = bool(treatment_row.get("success"))
            deltas.append((1.0 if treatment_success else 0.0) - (1.0 if baseline_success else 0.0))
            if treatment_success and not baseline_success:
                treatment_only += 1
            elif baseline_success and not treatment_success:
                baseline_only += 1
            elif treatment_success and baseline_success:
                same_pass += 1
            else:
                same_fail += 1
        if not deltas:
            continue
        ci = bootstrap_ci(deltas)
        result[f"{treatment}_vs_{baseline}"] = {
            "baseline": baseline,
            "treatment": treatment,
            "n_pairs": len(deltas),
            "baseline_success": same_pass + baseline_only,
            "treatment_success": same_pass + treatment_only,
            "treatment_only": treatment_only,
            "baseline_only": baseline_only,
            "same_pass": same_pass,
            "same_fail": same_fail,
            "delta_success_rate": mean(deltas),
            "delta_success_rate_ci": list(ci),
            "mcnemar_exact_p": mcnemar_exact_p(baseline_only, treatment_only),
        }
    return result


def mcnemar_exact_p(baseline_only: int, treatment_only: int) -> float:
    discordant = baseline_only + treatment_only
    if discordant == 0:
        return 1.0
    tail = min(baseline_only, treatment_only)
    probability = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2 ** discordant)
    return min(1.0, 2.0 * probability)


def failure_modes_by_benchmark(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row.get("benchmark", ""))][str(row.get("variant", ""))].append(row)

    summary: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for benchmark, by_variant in sorted(grouped.items()):
        summary[benchmark] = {}
        for variant, group in sorted(by_variant.items()):
            summary[benchmark][variant] = {
                "n": len(group),
                "success_rate": _rate(group, "success"),
                "context_bloat_proxy_rate": _failure_rate(group, CONTEXT_BLOAT_FAILURE_CODES),
                "self_biased_acceptance_rate": _rate(group, "premature_stop"),
                "wrong_claim_acceptance_rate": _rate(group, "wrong_claim_accepted"),
                "accepted_by_agent_rate": _rate(group, "accepted_by_agent"),
                "accepted_by_gate_rate": _rate(group, "accepted_by_gate"),
                "failure_taxonomy": failure_taxonomy(group),
            }
    return summary


def paired_deltas_by_benchmark(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, int]]]:
    materialized = list(rows)
    benchmarks = sorted({str(row.get("benchmark", "")) for row in materialized})
    variants = sorted({str(row.get("variant", "")) for row in materialized})
    pairs = POLICY_TEST_PAIRS
    result: Dict[str, Dict[str, Dict[str, int]]] = {}
    by_key = {
        _instance_variant_key(row): row
        for row in materialized
    }
    for benchmark in benchmarks:
        instances = sorted({
            _instance_key(row)
            for row in materialized
            if str(row.get("benchmark", "")) == benchmark and row.get("task_id")
        })
        result[benchmark] = {}
        for baseline, treatment in pairs:
            if baseline not in variants or treatment not in variants:
                continue
            treatment_only = baseline_only = same_pass = same_fail = 0
            for instance in instances:
                baseline_row = by_key.get((*instance, baseline))
                treatment_row = by_key.get((*instance, treatment))
                if not baseline_row or not treatment_row:
                    continue
                baseline_success = bool(baseline_row.get("success"))
                treatment_success = bool(treatment_row.get("success"))
                if treatment_success and not baseline_success:
                    treatment_only += 1
                elif baseline_success and not treatment_success:
                    baseline_only += 1
                elif treatment_success and baseline_success:
                    same_pass += 1
                else:
                    same_fail += 1
            result[benchmark][f"{treatment}_vs_{baseline}"] = {
                "treatment_only": treatment_only,
                "baseline_only": baseline_only,
                "same_pass": same_pass,
                "same_fail": same_fail,
            }
    return result


def _instance_key(row: Dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("benchmark", "")),
        str(row.get("task_id", "")),
        str(row.get("seed", 0)),
    )


def _instance_variant_key(row: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (*_instance_key(row), str(row.get("variant", "")))


def write_aggregate(run_dir: Path, tables_dir: Path = Path("artifacts/tables")) -> Dict[str, Any]:
    rows = read_results(run_dir)
    aggregate = aggregate_rows(rows)
    run_dir = Path(run_dir)
    aggregate["prompt_token_overhead"] = prompt_token_overhead(run_dir)
    run_dir.joinpath("aggregate.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_leaderboard(run_dir, aggregate)
    write_failure_modes_csv(run_dir / "failure_modes_by_benchmark.csv", aggregate)
    write_per_seed_csv(run_dir / "per_seed_results.csv", aggregate)
    write_paired_tests_csv(run_dir / "paired_policy_tests.csv", aggregate)
    write_prompt_token_overhead_csv(run_dir / "prompt_token_overhead.csv", aggregate)
    tables_dir.mkdir(parents=True, exist_ok=True)
    write_metrics_csv(tables_dir / "metrics.csv", aggregate)
    write_failure_modes_csv(tables_dir / "failure_modes_by_benchmark.csv", aggregate)
    write_markdown_table(tables_dir / "context_trace_table.md", aggregate.get("context_overload_slope", {}), "ContextTrace")
    write_markdown_table(tables_dir / "provenance_bias_table.md", aggregate.get("self_evaluation_bias_gap", {}), "ProvenanceBias")
    write_markdown_table(tables_dir / "mini_workflow_table.md", aggregate.get("by_variant", {}), "MiniWorkflow")
    return aggregate


def prompt_token_overhead(run_dir: Path) -> Dict[str, Any]:
    leaves_dir = Path(run_dir) / "artifacts" / "leaves"
    by_variant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    if not leaves_dir.exists():
        return {"by_variant": {}, "comparisons": {}}
    for transcript in leaves_dir.rglob("transcript.txt"):
        try:
            relative = transcript.relative_to(leaves_dir)
        except ValueError:
            continue
        parts = relative.parts
        if not parts:
            continue
        variant = parts[0]
        attempt = next((part for part in parts if part.startswith("attempt_")), "attempt_0")
        try:
            attempt_index = int(attempt.split("_", 1)[1])
        except Exception:
            attempt_index = 0
        tokens = len(transcript.read_text(encoding="utf-8", errors="replace").split())
        by_variant[variant].append({"tokens": tokens, "attempt": attempt_index})

    summary: Dict[str, Dict[str, Any]] = {}
    for variant, items in sorted(by_variant.items()):
        retry_items = [item for item in items if int(item["attempt"]) > 0]
        summary[variant] = {
            "leaf_count": len(items),
            "retry_leaf_count": len(retry_items),
            "avg_prompt_tokens": mean(float(item["tokens"]) for item in items),
            "avg_retry_prompt_tokens": mean(float(item["tokens"]) for item in retry_items),
            "total_prompt_tokens": sum(int(item["tokens"]) for item in items),
        }

    comparisons: Dict[str, Dict[str, float]] = {}
    for baseline, treatment in POLICY_TEST_PAIRS:
        if baseline not in summary or treatment not in summary:
            continue
        comparisons[f"{treatment}_vs_{baseline}"] = {
            "avg_prompt_token_delta": summary[treatment]["avg_prompt_tokens"] - summary[baseline]["avg_prompt_tokens"],
            "avg_retry_prompt_token_delta": summary[treatment]["avg_retry_prompt_tokens"]
            - summary[baseline]["avg_retry_prompt_tokens"],
            "total_prompt_token_delta": summary[treatment]["total_prompt_tokens"] - summary[baseline]["total_prompt_tokens"],
        }
    return {"by_variant": summary, "comparisons": comparisons}


def write_leaderboard(run_dir: Path, aggregate: Dict[str, Any]) -> None:
    path = run_dir / "leaderboard.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["variant", "n", "success_rate", "premature_stop_rate"])
        writer.writeheader()
        for variant, metrics in aggregate.get("by_variant", {}).items():
            writer.writerow({
                "variant": variant,
                "n": metrics["n"],
                "success_rate": metrics["success_rate"],
                "premature_stop_rate": metrics["premature_stop_rate"],
            })


def write_metrics_csv(path: Path, aggregate: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "metric", "value"])
        for variant, metrics in aggregate.get("by_variant", {}).items():
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    writer.writerow([variant, key, value])


def write_per_seed_csv(path: Path, aggregate: Dict[str, Any]) -> None:
    fieldnames = [
        "seed",
        "variant",
        "n",
        "success_count",
        "success_rate",
        "num_leaf_calls",
        "num_retries",
        "premature_stop_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for seed, by_variant in aggregate.get("per_seed_results", {}).items():
            for variant, metrics in by_variant.items():
                writer.writerow({"seed": seed, "variant": variant, **metrics})


def write_paired_tests_csv(path: Path, aggregate: Dict[str, Any]) -> None:
    fieldnames = [
        "comparison",
        "baseline",
        "treatment",
        "n_pairs",
        "baseline_success",
        "treatment_success",
        "treatment_only",
        "baseline_only",
        "same_pass",
        "same_fail",
        "delta_success_rate",
        "ci_low",
        "ci_high",
        "mcnemar_exact_p",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for comparison, metrics in aggregate.get("paired_policy_tests", {}).items():
            ci = metrics.get("delta_success_rate_ci", [0.0, 0.0])
            writer.writerow({
                "comparison": comparison,
                "baseline": metrics.get("baseline"),
                "treatment": metrics.get("treatment"),
                "n_pairs": metrics.get("n_pairs"),
                "baseline_success": metrics.get("baseline_success"),
                "treatment_success": metrics.get("treatment_success"),
                "treatment_only": metrics.get("treatment_only"),
                "baseline_only": metrics.get("baseline_only"),
                "same_pass": metrics.get("same_pass"),
                "same_fail": metrics.get("same_fail"),
                "delta_success_rate": metrics.get("delta_success_rate"),
                "ci_low": ci[0] if len(ci) > 0 else 0.0,
                "ci_high": ci[1] if len(ci) > 1 else 0.0,
                "mcnemar_exact_p": metrics.get("mcnemar_exact_p"),
            })


def write_prompt_token_overhead_csv(path: Path, aggregate: Dict[str, Any]) -> None:
    overhead = aggregate.get("prompt_token_overhead", {})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "name", "metric", "value"])
        for variant, metrics in overhead.get("by_variant", {}).items():
            for metric, value in metrics.items():
                writer.writerow(["variant", variant, metric, value])
        for comparison, metrics in overhead.get("comparisons", {}).items():
            for metric, value in metrics.items():
                writer.writerow(["comparison", comparison, metric, value])


def write_failure_modes_csv(path: Path, aggregate: Dict[str, Any]) -> None:
    fieldnames = [
        "benchmark",
        "variant",
        "n",
        "success_rate",
        "context_bloat_proxy_rate",
        "self_biased_acceptance_rate",
        "wrong_claim_acceptance_rate",
        "accepted_by_agent_rate",
        "accepted_by_gate_rate",
        "failure_taxonomy",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for benchmark, by_variant in aggregate.get("failure_modes_by_benchmark", {}).items():
            for variant, metrics in by_variant.items():
                row = {"benchmark": benchmark, "variant": variant}
                for key in fieldnames:
                    if key in {"benchmark", "variant"}:
                        continue
                    value = metrics.get(key)
                    row[key] = json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
                writer.writerow(row)


def write_markdown_table(path: Path, data: Dict[str, Any], title: str) -> None:
    lines = [f"# {title}", "", "| key | value |", "|---|---|"]
    for key, value in sorted(data.items()):
        lines.append(f"| {key} | {json.dumps(value, sort_keys=True)} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
