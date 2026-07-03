PY ?= python3
RUN_PY := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo $(PY); fi)

.PHONY: install test lint typecheck smoke run-context-trace run-provenance-bias run-mini-workflow check-coreai run-coreai-ablation aggregate plots

install:
	$(PY) -m venv .venv
	. .venv/bin/activate && python -m pip install --upgrade pip
	. .venv/bin/activate && python -m pip install -e .

test:
	$(RUN_PY) -m pytest tests

lint:
	$(RUN_PY) -m ruff check .

typecheck:
	$(RUN_PY) -m veriharness.devtools_typecheck

smoke:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_smoke.yaml --backend local

run-context-trace:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_context_trace.yaml --backend local

run-provenance-bias:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_provenance_bias.yaml --backend local

run-mini-workflow:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_mini_workflow.yaml --backend local

check-coreai:
	$(RUN_PY) -m veriharness.cli.main check-coreai

run-coreai-ablation:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_coreai_ablation.yaml --backend local

run-coreai-freeform-ablation:
	$(RUN_PY) -m veriharness.cli.main run --config configs/experiment_coreai_freeform_ablation.yaml --backend local

aggregate:
	$(RUN_PY) -m veriharness.cli.main aggregate --run-dir runs/latest

plots:
	$(RUN_PY) -m veriharness.cli.main plot --run-dir runs/latest
