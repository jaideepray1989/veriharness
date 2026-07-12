#!/usr/bin/env python3
"""Build and anonymity-scan the AgenticDev paper900 artifact."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "artifact"
STAGE = OUT / "veriharness-agenticdev2026-anonymous"
ZIP = OUT / "veriharness-agenticdev2026-anonymous.zip"

RUNS = [
    "modal_reviewer_textworld_b4_qwen_coder_14b",
    "modal_reviewer_textworld_b4_llama_8b",
    "modal_paper900_humaneval_public_b4_qwen_coder_14b",
    "modal_paper900_humaneval_public_b4_llama_8b",
    "modal_paper900_textworld_b2_qwen_coder_14b",
    "modal_paper900_textworld_b2_llama_8b",
    "modal_paper900_textworld_b6_qwen_coder_14b",
    "modal_paper900_textworld_b6_llama_8b",
    "modal_paper900_textworld_b8_qwen_coder_14b",
    "modal_paper900_textworld_b8_llama_8b",
    "modal_paper900_textworld_sample_r1_qwen_coder_14b",
    "modal_paper900_textworld_sample_r2_qwen_coder_14b",
    "modal_paper900_textworld_sample_r3_qwen_coder_14b",
]

TEXT_SUFFIXES = {
    ".cfg", ".csv", ".json", ".jsonl", ".md", ".py", ".tex", ".txt",
    ".sh", ".yaml", ".yml",
}
REPLACEMENTS = {
    "jaideepray1989": "anonymous-workspace",
    "/Users/jaray/Documents/autoresearch": "<REPOSITORY_ROOT>",
    "/Users/jaray": "<HOME>",
    "jaray": "anonymous-user",
}


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".DS_Store"),
    )


def sanitize_text_files(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for old, new in REPLACEMENTS.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def main() -> None:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    shutil.copy2(ROOT / "paper" / "agenticdev2026" / "ARTIFACT_README.md", STAGE / "README.md")
    copy_tree(ROOT / "paper" / "agenticdev2026", STAGE / "paper" / "agenticdev2026")
    copy_tree(ROOT / "reports" / "paper900", STAGE / "reports" / "paper900")

    snapshot = STAGE / "source_snapshot"
    copy_tree(ROOT / "veriharness", snapshot / "veriharness")
    copy_tree(ROOT / "tests", snapshot / "tests")
    copy_tree(ROOT / "scripts", snapshot / "scripts")
    for name in ("pyproject.toml", "setup.py", "README.md", "AGENTS.md"):
        source = ROOT / name
        if source.exists():
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    for run_name in RUNS:
        copy_tree(ROOT / "runs" / run_name, STAGE / "runs" / run_name)
    backup = STAGE / "runs" / "modal_paper900_textworld_sample_r2_qwen_coder_14b" / "results.before_transient_rerun.jsonl"
    if backup.exists():
        backup.unlink()

    data_root = STAGE / "data" / "benchmarks"
    humaneval = ROOT / "data" / "benchmarks" / "humaneval" / "HumanEval.jsonl.gz"
    (data_root / "humaneval").mkdir(parents=True, exist_ok=True)
    shutil.copy2(humaneval, data_root / "humaneval" / humaneval.name)
    for seed in range(20_261_051, 20_261_101):
        for folder, suffix in (("games", ".z8"), ("metadata", ".json")):
            source = ROOT / "data" / "benchmarks" / "textworld" / folder / f"textworld-{seed}{suffix}"
            destination = data_root / "textworld" / folder / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    sanitize_text_files(STAGE)
    forbidden = [value for value in ("jaideepray1989", "/Users/jaray", "jaray")]
    leaks = []
    for path in STAGE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(value.lower() in text.lower() for value in forbidden):
            leaks.append(str(path.relative_to(STAGE)))
    if leaks:
        raise RuntimeError(f"identity strings remain in: {leaks[:20]}")

    manifest = {
        "rows": sum(
            len((STAGE / "runs" / run / "results.jsonl").read_text(encoding="utf-8").splitlines())
            for run in RUNS
        ),
        "runs": RUNS,
    }
    (STAGE / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT))
    digest = hashlib.sha256(ZIP.read_bytes()).hexdigest()
    (OUT / "veriharness-agenticdev2026-anonymous.sha256").write_text(
        f"{digest}  {ZIP.name}\n", encoding="ascii"
    )
    print(json.dumps({"rows": manifest["rows"], "zip": str(ZIP), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
