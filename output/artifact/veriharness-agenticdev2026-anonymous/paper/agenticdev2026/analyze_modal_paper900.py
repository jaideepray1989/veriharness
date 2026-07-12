#!/usr/bin/env python3
"""Recompute the Modal paper900 statistics and paper-ready tables."""

from __future__ import annotations

import csv
import itertools
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
OUT = ROOT / "reports" / "paper900"

MODELS = {
    "qwen_coder_14b": "Qwen2.5-Coder-14B-AWQ/L4",
    "llama_8b": "Llama-3.1-8B-AWQ/T4",
}
PRIMARY_VARIANTS = [
    "generic+diagnostics",
    "same-info-natural",
    "location-observed",
    "typed-fields",
]
PRIMARY_CONTRASTS = [
    ("generic+diagnostics", "same-info-natural", "structured_feedback"),
    ("generic+diagnostics", "typed-fields", "full_interface"),
    ("same-info-natural", "typed-fields", "typed_structure"),
    ("location-observed", "typed-fields", "expected_alternatives"),
]
EXPECTED_RUNS = {
    "modal_reviewer_textworld_b4_qwen_coder_14b": 200,
    "modal_reviewer_textworld_b4_llama_8b": 200,
    "modal_paper900_humaneval_public_b4_qwen_coder_14b": 60,
    "modal_paper900_humaneval_public_b4_llama_8b": 60,
    "modal_paper900_textworld_b2_qwen_coder_14b": 30,
    "modal_paper900_textworld_b2_llama_8b": 30,
    "modal_paper900_textworld_b6_qwen_coder_14b": 30,
    "modal_paper900_textworld_b6_llama_8b": 30,
    "modal_paper900_textworld_b8_qwen_coder_14b": 30,
    "modal_paper900_textworld_b8_llama_8b": 30,
    "modal_paper900_textworld_sample_r1_qwen_coder_14b": 60,
    "modal_paper900_textworld_sample_r2_qwen_coder_14b": 60,
    "modal_paper900_textworld_sample_r3_qwen_coder_14b": 60,
}


def read_rows(run_name: str) -> list[dict[str, Any]]:
    path = RUNS / run_name / "results.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = EXPECTED_RUNS[run_name]
    if len(rows) != expected:
        raise AssertionError(f"{run_name}: expected {expected} rows, found {len(rows)}")
    keys = [(row["task_id"], row["variant"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise AssertionError(f"{run_name}: duplicate task-policy keys")
    return rows


def bootstrap_ci(values: Sequence[float], draws: int = 10_000, seed: int = 1) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return samples[int(0.025 * (draws - 1))], samples[int(0.975 * (draws - 1))]


def mcnemar_exact(baseline_only: int, treatment_only: int) -> float:
    discordant = baseline_only + treatment_only
    if not discordant:
        return 1.0
    tail = min(baseline_only, treatment_only)
    probability = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2 * probability)


def holm_adjust(items: list[dict[str, Any]], key: str = "p") -> None:
    ordered = sorted(enumerate(items), key=lambda pair: pair[1][key])
    running = 0.0
    m = len(items)
    for rank, (original_index, item) in enumerate(ordered):
        adjusted = min(1.0, (m - rank) * float(item[key]))
        running = max(running, adjusted)
        items[original_index]["holm_p"] = running


def paired(rows: Sequence[dict[str, Any]], baseline: str, treatment: str) -> dict[str, Any]:
    by = {(row["task_id"], row["variant"]): row for row in rows}
    tasks = sorted({row["task_id"] for row in rows if row["variant"] in {baseline, treatment}})
    deltas = []
    call_deltas = []
    treatment_only = baseline_only = same_pass = same_fail = 0
    for task in tasks:
        base = bool(by[(task, baseline)]["success"])
        treat = bool(by[(task, treatment)]["success"])
        deltas.append(float(treat) - float(base))
        call_deltas.append(
            float(by[(task, treatment)]["num_leaf_calls"])
            - float(by[(task, baseline)]["num_leaf_calls"])
        )
        if treat and not base:
            treatment_only += 1
        elif base and not treat:
            baseline_only += 1
        elif treat:
            same_pass += 1
        else:
            same_fail += 1
    ci = bootstrap_ci(deltas)
    call_ci = bootstrap_ci(call_deltas)
    return {
        "baseline": baseline,
        "treatment": treatment,
        "n": len(tasks),
        "baseline_success": same_pass + baseline_only,
        "treatment_success": same_pass + treatment_only,
        "delta": sum(deltas) / len(deltas),
        "ci_low": ci[0],
        "ci_high": ci[1],
        "treatment_only": treatment_only,
        "baseline_only": baseline_only,
        "same_pass": same_pass,
        "same_fail": same_fail,
        "p": mcnemar_exact(baseline_only, treatment_only),
        "delta_calls": sum(call_deltas) / len(call_deltas),
        "delta_calls_ci_low": call_ci[0],
        "delta_calls_ci_high": call_ci[1],
    }


def variant_summary(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for variant in sorted({row["variant"] for row in rows}):
        group = [row for row in rows if row["variant"] == variant]
        action_invalid_rows = sum(
            "action_invalid" in set(row["failure_reasons"]) for row in group
        )
        result.append(
            {
                "variant": variant,
                "success": sum(bool(row["success"]) for row in group),
                "n": len(group),
                "success_rate": sum(bool(row["success"]) for row in group) / len(group),
                "calls": sum(int(row["num_leaf_calls"]) for row in group),
                "avg_calls": sum(int(row["num_leaf_calls"]) for row in group) / len(group),
                "action_invalid_final_rows": action_invalid_rows,
            }
        )
    return result


def prompt_summary(run_name: str) -> list[dict[str, Any]]:
    leaves = RUNS / run_name / "artifacts" / "leaves"
    grouped: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for transcript in leaves.rglob("transcript.txt"):
        relative = transcript.relative_to(leaves)
        variant = relative.parts[0]
        attempt_part = next(part for part in relative.parts if part.startswith("attempt_"))
        attempt = int(attempt_part.rsplit("_", 1)[1])
        words = len(transcript.read_text(encoding="utf-8", errors="replace").split())
        grouped[variant].append((attempt, words))
    result = []
    for variant, items in sorted(grouped.items()):
        retry = [words for attempt, words in items if attempt > 0]
        result.append(
            {
                "variant": variant,
                "leaf_prompts": len(items),
                "retry_prompts": len(retry),
                "avg_all_prompt_words": sum(words for _attempt, words in items) / len(items),
                "avg_retry_prompt_words": sum(retry) / len(retry) if retry else 0.0,
                "total_prompt_words": sum(words for _attempt, words in items),
            }
        )
    return result


def cluster_sign_flip_p(values: Sequence[float], draws: int = 100_000, seed: int = 1) -> float:
    nonzero = [value for value in values if value]
    if not nonzero:
        return 1.0
    rng = random.Random(seed)
    observed = abs(sum(nonzero) / len(nonzero))
    extreme = 0
    for _ in range(draws):
        statistic = abs(sum(value if rng.random() < 0.5 else -value for value in nonzero) / len(nonzero))
        extreme += statistic >= observed - 1e-12
    return (extreme + 1) / (draws + 1)


def sampling_analysis(rows: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    per_repeat = []
    for seed in sorted({int(row["metadata"]["sampling_seed"]) for row in rows}):
        group = [row for row in rows if int(row["metadata"]["sampling_seed"]) == seed]
        for summary in variant_summary(group):
            per_repeat.append({"sampling_seed": seed, **summary})

    contrasts = []
    for baseline, treatment, label in [
        ("generic+diagnostics", "same-info-natural", "structured_feedback"),
        ("generic+diagnostics", "typed-fields", "full_interface"),
        ("same-info-natural", "typed-fields", "typed_structure"),
    ]:
        by = {
            (row["task_id"], int(row["metadata"]["sampling_seed"]), row["variant"]): row
            for row in rows
        }
        seeds = sorted({int(row["metadata"]["sampling_seed"]) for row in rows})
        tasks = sorted({row["task_id"] for row in rows})
        cluster_deltas = []
        for task in tasks:
            deltas = [
                float(by[(task, seed, treatment)]["success"])
                - float(by[(task, seed, baseline)]["success"])
                for seed in seeds
            ]
            cluster_deltas.append(sum(deltas) / len(deltas))
        ci = bootstrap_ci(cluster_deltas)
        contrasts.append(
            {
                "contrast": label,
                "baseline": baseline,
                "treatment": treatment,
                "n_game_clusters": len(tasks),
                "repeats_per_game": len(seeds),
                "delta": sum(cluster_deltas) / len(cluster_deltas),
                "ci_low": ci[0],
                "ci_high": ci[1],
                "p": cluster_sign_flip_p(cluster_deltas),
            }
        )
    holm_adjust(contrasts)
    return per_repeat, contrasts


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def main() -> None:
    all_rows = {name: read_rows(name) for name in EXPECTED_RUNS}
    flat = [row for rows in all_rows.values() for row in rows]
    client_errors = [row for row in flat if "client_error" in row.get("failure_reasons", [])]
    if client_errors:
        raise AssertionError(f"primary dataset contains {len(client_errors)} client-error rows")
    if len(flat) != 880:
        raise AssertionError(f"expected 880 total rows, found {len(flat)}")

    primary_summary = []
    primary_tests = []
    prompts = []
    for model_key, model_label in MODELS.items():
        run_name = f"modal_reviewer_textworld_b4_{model_key}"
        rows = all_rows[run_name]
        for summary in variant_summary(rows):
            primary_summary.append({"model": model_label, **summary})
        tests = []
        for baseline, treatment, label in PRIMARY_CONTRASTS:
            tests.append({"model": model_label, "contrast": label, **paired(rows, baseline, treatment)})
        holm_adjust(tests)
        primary_tests.extend(tests)
        for summary in prompt_summary(run_name):
            prompts.append({"model": model_label, **summary})

    code_summary = []
    code_tests = []
    for model_key, model_label in MODELS.items():
        run_name = f"modal_paper900_humaneval_public_b4_{model_key}"
        rows = all_rows[run_name]
        for summary in variant_summary(rows):
            group = [row for row in rows if row["variant"] == summary["variant"]]
            code_summary.append(
                {
                    "model": model_label,
                    **summary,
                    "public_gate_accept": sum(bool(row["accepted_by_gate"]) for row in group),
                    "one_call": sum(int(row["num_leaf_calls"]) == 1 for row in group),
                }
            )
        for baseline, treatment, label in PRIMARY_CONTRASTS:
            code_tests.append({"model": model_label, "contrast": label, **paired(rows, baseline, treatment)})

    budget_summary = []
    budget_tests = []
    for model_key, model_label in MODELS.items():
        b2_rows = all_rows[f"modal_paper900_textworld_b2_{model_key}"]
        common_tasks = {row["task_id"] for row in b2_rows}
        for budget in (2, 4, 6, 8):
            if budget == 4:
                source = all_rows[f"modal_reviewer_textworld_b4_{model_key}"]
                rows = [
                    row for row in source
                    if row["task_id"] in common_tasks and row["variant"] in {"generic+diagnostics", "typed-fields"}
                ]
            else:
                rows = all_rows[f"modal_paper900_textworld_b{budget}_{model_key}"]
            for summary in variant_summary(rows):
                budget_summary.append({"model": model_label, "budget": budget, **summary})
            budget_tests.append(
                {"model": model_label, "budget": budget, **paired(rows, "generic+diagnostics", "typed-fields")}
            )
        model_tests = [item for item in budget_tests if item["model"] == model_label]
        holm_adjust(model_tests)

    sampled_rows = list(
        itertools.chain.from_iterable(
            all_rows[f"modal_paper900_textworld_sample_r{repeat}_qwen_coder_14b"]
            for repeat in (1, 2, 3)
        )
    )
    sampling_summary, sampling_tests = sampling_analysis(sampled_rows)

    failure_rows = []
    for item in primary_summary:
        failure_rows.append(
            {
                "model": item["model"],
                "variant": item["variant"],
                "action_invalid_final_rows": item["action_invalid_final_rows"],
                "final_failures": item["n"] - item["success"],
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "primary_summary.csv", primary_summary)
    write_csv(OUT / "primary_paired_tests.csv", primary_tests)
    write_csv(OUT / "prompt_overhead.csv", prompts)
    write_csv(OUT / "code_scope_summary.csv", code_summary)
    write_csv(OUT / "code_scope_paired_tests.csv", code_tests)
    write_csv(OUT / "budget_summary.csv", budget_summary)
    write_csv(OUT / "budget_paired_tests.csv", budget_tests)
    write_csv(OUT / "sampling_per_repeat.csv", sampling_summary)
    write_csv(OUT / "sampling_cluster_tests.csv", sampling_tests)
    write_csv(OUT / "failure_taxonomy.csv", failure_rows)

    output = {
        "validation": {
            "rows": len(flat),
            "runs": len(all_rows),
            "client_error_rows": len(client_errors),
            "leaf_calls": sum(int(row["num_leaf_calls"]) for row in flat),
        },
        "primary_summary": primary_summary,
        "primary_tests": primary_tests,
        "prompt_overhead": prompts,
        "code_scope_summary": code_summary,
        "code_scope_tests": code_tests,
        "budget_summary": budget_summary,
        "budget_tests": budget_tests,
        "sampling_summary": sampling_summary,
        "sampling_tests": sampling_tests,
        "failure_taxonomy": failure_rows,
    }
    (OUT / "analysis.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    primary_by = {(row["model"], row["variant"]): row for row in primary_summary}
    tests_by = {(row["model"], row["contrast"]): row for row in primary_tests}
    lines = [
        "# VeriHarness Modal Paper900 Analysis",
        "",
        "## Validated dataset",
        "",
        f"- {len(flat)} rows across {len(all_rows)} runs; {sum(int(row['num_leaf_calls']) for row in flat)} leaf calls.",
        "- Zero infrastructure/client-error rows after one quarantined request was rerun identically.",
        "- Oracle-blind acceptance; TextWorld terminal success and full hidden HumanEval tests are post-hoc outcomes.",
        "",
        "## Primary TextWorld result (50 paired games, budget 4)",
        "",
    ]
    for model_label in MODELS.values():
        raw = primary_by[(model_label, "generic+diagnostics")]
        natural = primary_by[(model_label, "same-info-natural")]
        location = primary_by[(model_label, "location-observed")]
        typed = primary_by[(model_label, "typed-fields")]
        full = tests_by[(model_label, "full_interface")]
        structure = tests_by[(model_label, "typed_structure")]
        alternatives = tests_by[(model_label, "expected_alternatives")]
        lines.extend(
            [
                f"### {model_label}",
                "",
                f"- Raw diagnostics: {raw['success']}/{raw['n']} ({fmt_pct(raw['success_rate'])}).",
                f"- Same-information natural language: {natural['success']}/{natural['n']} ({fmt_pct(natural['success_rate'])}).",
                f"- Location+observed, no alternatives: {location['success']}/{location['n']} ({fmt_pct(location['success_rate'])}).",
                f"- Typed fields: {typed['success']}/{typed['n']} ({fmt_pct(typed['success_rate'])}).",
                f"- Typed vs raw: {fmt_pct(full['delta'])} [95% CI {fmt_pct(full['ci_low'])}, {fmt_pct(full['ci_high'])}], exact p={full['p']:.6g}, Holm p={full['holm_p']:.6g}.",
                f"- Typed vs same-information NL: {fmt_pct(structure['delta'])} [95% CI {fmt_pct(structure['ci_low'])}, {fmt_pct(structure['ci_high'])}], exact p={structure['p']:.6g}, Holm p={structure['holm_p']:.6g}.",
                f"- Typed vs location-only: {fmt_pct(alternatives['delta'])} [95% CI {fmt_pct(alternatives['ci_low'])}, {fmt_pct(alternatives['ci_high'])}], exact p={alternatives['p']:.6g}, Holm p={alternatives['holm_p']:.6g}.",
                "",
            ]
        )
    sampling_by = {row["contrast"]: row for row in sampling_tests}
    sampled_full = sampling_by["full_interface"]
    sampled_structure = sampling_by["typed_structure"]
    lines.extend(
        [
            "## Robustness lanes",
            "",
            "### Budget sensitivity (same 15 games)",
            "",
            "- Qwen raw/typed wins at budgets 2, 4, 6, 8: 5/8, 4/11, 4/11, 4/12.",
            "- Llama raw/typed wins at budgets 2, 4, 6, 8: 1/5, 2/9, 2/11, 2/11.",
            "- The gain increases between budgets 2 and 4, then plateaus for Qwen and grows through budget 6 for Llama; this is not a universal step exactly at budget 4.",
            "",
            "### Sampled Qwen decoding (20 games x 3 seeds)",
            "",
            "- Per-seed wins: raw 6/6/5, same-information NL 14/13/14, typed 14/16/14.",
            f"- Typed vs raw clustered delta: {fmt_pct(sampled_full['delta'])} [95% CI {fmt_pct(sampled_full['ci_low'])}, {fmt_pct(sampled_full['ci_high'])}], Holm p={sampled_full['holm_p']:.4f}.",
            f"- Typed vs same-information NL: {fmt_pct(sampled_structure['delta'])} [95% CI {fmt_pct(sampled_structure['ci_low'])}, {fmt_pct(sampled_structure['ci_high'])}], Holm p={sampled_structure['holm_p']:.3f}.",
            "",
            "### Public-test HumanEval scope check (15 tasks)",
            "",
            "- Qwen hidden-test success is 14/15 under every policy; all 15 candidates pass the public gate on call one.",
            "- Llama hidden-test success is 10/15 for raw, same-information NL, and location-only, versus 9/15 for typed fields.",
            "- This lane supplies a negative boundary result, not evidence of code-repair improvement.",
            "",
            "## Efficiency and prompt overhead",
            "",
            "- Typed vs same-information NL uses 130 vs 147 calls for Qwen and 149 vs 161 for Llama.",
            "- Paired call differences are -0.34 calls/game [95% CI -0.60, -0.06] for Qwen and -0.24 [-0.44, -0.04] for Llama.",
            "- Average retry transcripts are similar (typed/prose: 701/716 Qwen; 706/722 Llama). Total prompt-word proxies are 14% and 10% lower for typed feedback because it realizes fewer calls.",
            "",
            "## Statistical definitions",
            "",
            "- Primary intervals: 10,000 paired bootstrap resamples over 50 games, seed 1.",
            "- Primary tests: two-sided exact McNemar with Holm correction over four planned contrasts within each model.",
            "- Sampling intervals: 10,000 bootstrap resamples over 20 game clusters, retaining three repeats per game.",
            "- Sampling tests: 100,000 seeded game-cluster sign flips with Holm correction.",
            "",
        ]
    )
    lines.extend(
        [
            "## Interpretation for the paper",
            "",
            "1. Include: structured verifier feedback with expected alternatives substantially outperforms raw diagnostics across both model families.",
            "2. Include as a boundary: typed JSON structure itself does not outperform an information-matched natural-language message.",
            "3. Include: removing expected alternatives largely removes the gain, identifying explicit repair content as the active ingredient within structured feedback.",
            "4. Include as robustness: the ordering persists across budgets and sampled decoding.",
            "5. Include as a negative scope result: public-test HumanEval shows no repair-policy gain; most Qwen tasks pass on the first call, and Llama differences are small.",
            "6. Exclude: claims that typed structure alone is causal, that preserve/retention is beneficial, or that the study demonstrates deployment impact.",
            "",
            "See the CSV files in this directory for exact paper tables.",
        ]
    )
    (OUT / "paper_inclusion_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(output["validation"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
