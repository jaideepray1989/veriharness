from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from veriharness.experiments.aggregate import read_results

MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c6360f8ffff3f0005fe02fea73581e20000000049454e44ae426082"
)


def _write_placeholder(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MINIMAL_PNG)


def write_plots(run_dir: Path, figures_dir: Path = Path("artifacts/figures")) -> List[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    rows = read_results(run_dir)
    outputs = [
        figures_dir / "context_overload_success_vs_trace_length.png",
        figures_dir / "self_eval_bias_gap.png",
        figures_dir / "tokens_per_success.png",
        figures_dir / "premature_stop_rate.png",
    ]
    try:
        import matplotlib  # type: ignore

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        for path in outputs:
            _write_placeholder(path)
        return outputs

    _plot_context(rows, outputs[0], plt)
    _plot_bias(rows, outputs[1], plt)
    _plot_tokens(rows, outputs[2], plt)
    _plot_premature(rows, outputs[3], plt)
    return outputs


def _group_rate(rows: List[Dict[str, Any]], field: str) -> float:
    return sum(1 for row in rows if row.get(field)) / len(rows) if rows else 0.0


def _plot_context(rows: List[Dict[str, Any]], path: Path, plt: Any) -> None:
    data = [row for row in rows if row.get("benchmark") == "context_trace"]
    variants = sorted({row["variant"] for row in data})
    lengths = sorted({int(row["trace_length"]) for row in data if row.get("trace_length") is not None})
    plt.figure()
    for variant in variants:
        ys = [_group_rate([row for row in data if row["variant"] == variant and int(row["trace_length"]) == length], "success") for length in lengths]
        plt.plot(lengths, ys, marker="o", label=variant)
    plt.xlabel("trace length")
    plt.ylabel("success rate")
    if variants:
        plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _plot_bias(rows: List[Dict[str, Any]], path: Path, plt: Any) -> None:
    data = [row for row in rows if row.get("benchmark") == "provenance_bias"]
    labels = sorted({row["provenance_label"] for row in data if row.get("provenance_label")})
    variants = sorted({row["variant"] for row in data})
    plt.figure()
    for variant in variants:
        ys = [_group_rate([row for row in data if row["variant"] == variant and row.get("provenance_label") == label], "wrong_claim_accepted") for label in labels]
        plt.plot(labels, ys, marker="o", label=variant)
    plt.xticks(rotation=20)
    plt.ylabel("wrong claim acceptance rate")
    if variants:
        plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _plot_tokens(rows: List[Dict[str, Any]], path: Path, plt: Any) -> None:
    variants = sorted({row["variant"] for row in rows})
    values = []
    for variant in variants:
        group = [row for row in rows if row["variant"] == variant]
        tokens = sum(row.get("tokens_in", 0) + row.get("tokens_out", 0) for row in group)
        successes = sum(1 for row in group if row.get("success"))
        values.append(tokens / successes if successes else 0)
    plt.figure()
    plt.bar(variants, values)
    plt.ylabel("tokens per successful task")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _plot_premature(rows: List[Dict[str, Any]], path: Path, plt: Any) -> None:
    variants = sorted({row["variant"] for row in rows})
    values = [_group_rate([row for row in rows if row["variant"] == variant], "premature_stop") for variant in variants]
    plt.figure()
    plt.bar(variants, values)
    plt.ylabel("premature stop rate")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
