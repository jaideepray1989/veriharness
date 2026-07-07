from __future__ import annotations

from typing import Iterable, List

from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.benchmarks.external_benchmarks import (
    generate_ds1000_tasks,
    generate_mlagentbench_tasks,
    generate_swebench_tasks,
)
from veriharness.benchmarks.humaneval import generate_humaneval_tasks
from veriharness.benchmarks.mini_workflow import generate_mini_workflow_tasks
from veriharness.benchmarks.provenance_bias import generate_provenance_bias_tasks
from veriharness.benchmarks.public_nlp import (
    generate_arc_easy_tasks,
    generate_glue_mrpc_tasks,
    generate_glue_rte_tasks,
    generate_glue_sst2_tasks,
    generate_sciq_tasks,
    generate_trec_qc_tasks,
)
from veriharness.benchmarks.reading_comprehension import generate_boolq_tasks, generate_squad_tasks
from veriharness.core.types import BenchmarkConfig, TaskSpec


def generate_benchmark_tasks(config: BenchmarkConfig) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for seed in config.seeds:
        tasks.extend(generate_named_tasks(config.name, config.n_tasks, seed, config.trace_lengths))
    return tasks


def generate_named_tasks(
    benchmark: str,
    n_tasks: int,
    seed: int,
    trace_lengths: Iterable[int] = (4, 8),
) -> List[TaskSpec]:
    if benchmark in {"context_trace", "context-trace"}:
        return generate_context_trace_tasks(n_tasks=n_tasks, trace_lengths=trace_lengths, seed=seed)
    if benchmark in {"provenance_bias", "provenance-bias"}:
        return generate_provenance_bias_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"mini_workflow", "mini-workflow"}:
        return generate_mini_workflow_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"humaneval", "human-eval"}:
        return generate_humaneval_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"swebench_lite", "swebench-lite", "swe-bench-lite"}:
        return generate_swebench_tasks("swebench_lite", n_tasks=n_tasks, seed=seed)
    if benchmark in {"swebench_verified", "swebench-verified", "swe-bench-verified"}:
        return generate_swebench_tasks("swebench_verified", n_tasks=n_tasks, seed=seed)
    if benchmark in {"ds1000", "ds-1000"}:
        return generate_ds1000_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"mlagentbench", "ml-agent-bench", "mlagent-bench"}:
        return generate_mlagentbench_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"boolq", "bool-q"}:
        return generate_boolq_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"squad", "squad-v1", "squad_v1"}:
        return generate_squad_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark == "sciq":
        return generate_sciq_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"arc_easy", "arc-easy", "arc"}:
        return generate_arc_easy_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"glue_sst2", "glue-sst2", "sst2"}:
        return generate_glue_sst2_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"glue_rte", "glue-rte", "rte"}:
        return generate_glue_rte_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"glue_mrpc", "glue-mrpc", "mrpc"}:
        return generate_glue_mrpc_tasks(n_tasks=n_tasks, seed=seed)
    if benchmark in {"trec_qc", "trec-qc", "trec"}:
        return generate_trec_qc_tasks(n_tasks=n_tasks, seed=seed)
    raise ValueError(f"unknown benchmark: {benchmark}")
