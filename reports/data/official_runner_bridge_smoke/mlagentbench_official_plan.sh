#!/usr/bin/env bash
set -euo pipefail

.venv/bin/python -u -m MLAgentBench.prepare_task amp-parkinsons-disease-progression-prediction .venv/bin/python

mkdir -p reports/data/official_runner_bridge_smoke/mlagentbench_logs/amp-parkinsons-disease-progression-prediction
.venv/bin/python -u -m MLAgentBench.runner --python .venv/bin/python --task amp-parkinsons-disease-progression-prediction --device 0 --log-dir reports/data/official_runner_bridge_smoke/mlagentbench_logs/amp-parkinsons-disease-progression-prediction --work-dir reports/data/official_runner_bridge_smoke/mlagentbench_workspace/amp-parkinsons-disease-progression-prediction --agent_type Agent > reports/data/official_runner_bridge_smoke/mlagentbench_logs/amp-parkinsons-disease-progression-prediction/log 2>&1

mkdir -p reports/data/official_runner_bridge_smoke/mlagentbench_eval
.venv/bin/python -m MLAgentBench.eval --log-folder reports/data/official_runner_bridge_smoke/mlagentbench_logs/amp-parkinsons-disease-progression-prediction --task amp-parkinsons-disease-progression-prediction --output-file reports/data/official_runner_bridge_smoke/mlagentbench_eval/amp-parkinsons-disease-progression-prediction.json
