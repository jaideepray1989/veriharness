"""Modal-hosted vLLM endpoints for the reduced VeriHarness paper sweep."""

from __future__ import annotations

import subprocess

import modal

APP_NAME = "veriharness-paper900"
PORT = 8000
FOUR_HOURS = 4 * 60 * 60
TEN_MINUTES = 10 * 60

QWEN_MODEL = "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
LLAMA_MODEL = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"

app = modal.App(APP_NAME)
hf_cache = modal.Volume.from_name("veriharness-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("veriharness-vllm-cache", create_if_missing=True)

image = (
    modal.Image.from_registry("vllm/vllm-openai:v0.8.5.post1", add_python="3.12")
    .entrypoint([])
    .env(
        {
            "HF_HOME": "/root/.cache/huggingface",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VLLM_CACHE_ROOT": "/root/.cache/vllm",
        }
    )
)

volumes = {
    "/root/.cache/huggingface": hf_cache,
    "/root/.cache/vllm": vllm_cache,
}


def _serve(model: str, served_name: str) -> None:
    command = [
        "vllm",
        "serve",
        model,
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
        "--served-model-name",
        served_name,
        "--dtype",
        "half",
        "--quantization",
        "awq",
        "--max-model-len",
        "8192",
        "--max-num-seqs",
        "16",
        "--gpu-memory-utilization",
        "0.90",
        "--enforce-eager",
        "--generation-config",
        "vllm",
    ]
    subprocess.Popen(command)


@app.function(
    image=image,
    gpu="L4",
    volumes=volumes,
    timeout=FOUR_HOURS,
    startup_timeout=20 * 60,
    scaledown_window=TEN_MINUTES,
    max_containers=1,
)
@modal.web_server(PORT, startup_timeout=20 * 60, label="qwen")
def qwen_server() -> None:
    _serve(QWEN_MODEL, "qwen2.5-coder:14b")


@app.function(
    image=image,
    gpu="T4",
    volumes=volumes,
    timeout=FOUR_HOURS,
    startup_timeout=20 * 60,
    scaledown_window=TEN_MINUTES,
    max_containers=1,
)
@modal.web_server(PORT, startup_timeout=20 * 60, label="llama")
def llama_server() -> None:
    _serve(LLAMA_MODEL, "llama3.1:8b")
