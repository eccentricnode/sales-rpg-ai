"""Modal vLLM server — OpenAI-compatible endpoint for Sales RPG.

Deploy:
    modal deploy scripts/modal_vllm_serve.py

After deploy, the endpoint will be:
    https://eccentricnode--sales-rpg-llm-serve.modal.run/v1/chat/completions

Stop (to avoid idle billing — though it autoscales to zero after 5 min idle):
    modal app stop sales-rpg-llm

Model: Qwen2.5-7B-Instruct (ungated, ~14GB, fits comfortably on A10G).
Cost: ~$1.10/hr while serving; scales to zero on idle. Cold start ~60s.
"""

import modal

MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.7.3",
        "huggingface_hub[hf_transfer]==0.26.2",
    )
    # outlines hard-imports pyairports.airports on package init.
    # Modal's pip mirror only has pyairports==0.0.1 which lacks the airports
    # module. Write a stub instead — Sales RPG never uses outlines' airport
    # validators, we just need the import not to crash on every request.
    .run_commands(
        "mkdir -p /usr/local/lib/python3.12/site-packages/pyairports && "
        "printf '' > /usr/local/lib/python3.12/site-packages/pyairports/__init__.py && "
        "printf 'AIRPORT_LIST = []\\n' > /usr/local/lib/python3.12/site-packages/pyairports/airports.py"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "CACHE_BUST": "v6"})
)

app = modal.App("sales-rpg-llm")

# Persistent volume so the model weights download once, not every cold start.
hf_cache_vol = modal.Volume.from_name("sales-rpg-hf-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("sales-rpg-vllm-cache", create_if_missing=True)


@app.function(
    image=vllm_image,
    gpu="A10G",
    scaledown_window=300,  # idle for 5 min → scale to zero
    timeout=60 * 20,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=8000, startup_timeout=300)
def serve():
    """Launch vLLM's OpenAI-compatible server inside the Modal container."""
    import subprocess

    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", "8000",
        "--max-model-len", "8192",
        "--gpu-memory-utilization", "0.85",
        "--disable-log-requests",
    ]
    subprocess.Popen(cmd)
