
from __future__ import annotations
import os

# Backend selector: "ollama" | "vllm" | "stub"
BACKEND = os.getenv("ARC_LLM_BACKEND", "stub").lower()
_TEMPERATURE = float(os.getenv("ARC_LLM_TEMPERATURE", "0.2"))
_MAX_TOKENS  = int(os.getenv("ARC_LLM_MAX_TOKENS", "64"))

def _stub_llm(prompt: str) -> str:
    # Kaggle-safe deterministic fallback
    return "mirror vertical"

def _ollama_llm(prompt: str) -> str:
    import requests
    url   = os.getenv("ARC_OLLAMA_URL", "http://localhost:11434/api/generate")
    model = os.getenv("ARC_OLLAMA_MODEL", "llama3.1:8b")
    resp = requests.post(url, json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": _TEMPERATURE, "num_predict": _MAX_TOKENS}
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()

def _vllm_llm(prompt: str) -> str:
    import requests
    url   = os.getenv("ARC_VLLM_URL", "http://localhost:8000")
    model = os.getenv("ARC_VLLM_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
    resp = requests.post(f"{url.rstrip('/')}/generate", json={
        "model": model, "prompt": prompt,
        "temperature": _TEMPERATURE, "max_tokens": _MAX_TOKENS
    }, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("text") or data.get("generated_text") or "").strip()

def llm_rule(prompt: str) -> str:
    # Auto-stub inside Kaggle environments
    if os.getenv("KAGGLE_KERNEL_RUN_TYPE") or os.getenv("KAGGLE_WORKING_DIR"):
        return _stub_llm(prompt)
    try:
        if BACKEND == "ollama":
            return _ollama_llm(prompt)
        if BACKEND == "vllm":
            return _vllm_llm(prompt)
    except Exception:
        # If local server is unavailable, fall back to stub
        return _stub_llm(prompt)
    return _stub_llm(prompt)
