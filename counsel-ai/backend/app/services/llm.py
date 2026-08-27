"""Unified LLM service: local llama.cpp OR OpenAI-compatible HTTP API.

Upgrades over the MVP:

* **GPU offload detection** — probes for CUDA / Metal / ROCm and reports the
  backend in ``/api/health``; ``LOCAL_GPU_LAYERS=-1`` (default) lets
  llama.cpp auto-offload when a backend exists.
* **Model license gate** — ``check_model_license()`` classifies the loaded
  GGUF against a curated registry and warns (or blocks, per policy) when a
  non-commercially-licensed model is configured.
* **Prompt batching** — logical batch size forwarded to llama.cpp.
* Same single async entry point as the MVP: ``stream_chat(messages, mode,
  api_key)`` — chat, RAG answers, research writing and MDX all share it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx

from ..config import settings
from ..database import record_audit
from ..utils.logging_setup import new_correlation_id
from ..utils.metrics import inc, observe, timed

log = logging.getLogger("counsel.llm")

_LOCAL_LOCK = asyncio.Lock()
_local_llm = None


# ------------------------------------------------------------ availability


@dataclass
class LLMAvailability:
    model_path_exists: bool = False
    llama_cpp_installed: bool = False
    gpu_backend: str = "cpu"
    license: dict[str, Any] = field(default_factory=dict)
    blocked_by_license: bool = False


def detect_gpu_backend() -> str:
    """Best-effort accelerator probe without importing heavy libs."""
    import ctypes.util

    if platform.system() == "Darwin":
        return "metal"
    if ctypes.util.find_library("cudart") or ctypes.util.find_library("nvidia-ml") \
            or Path("/usr/lib/x86_64-linux-gnu/libcuda.so").exists():
        return "cuda"
    if ctypes.util.find_library("hipblas"):
        return "rocm"
    return "cpu"


def _auto_gpu_layers(backend: str) -> int:
    if settings.model_gpu_layers >= 0:
        return settings.model_gpu_layers
    return 999 if backend != "cpu" else 0  # llama.cpp clamps to its own max


def availability() -> LLMAvailability:
    av = LLMAvailability()
    p = settings.model_path
    av.model_path_exists = bool(p) and Path(p).exists()
    try:
        import llama_cpp  # noqa: F401

        av.llama_cpp_installed = True
    except ImportError:
        pass
    av.gpu_backend = detect_gpu_backend()
    if av.model_path_exists:
        lic = check_model_license(Path(p).name)
        av.license = lic
        av.blocked_by_license = not lic["commercial_ok"] and settings.enforce_commercial_models
    return av


# ------------------------------------------------------------ model licenses
# Curated GGUF registry. Patterns match file names commonly distributed on
# Hugging Face. `commercial_ok=False` marks research-only / NC checkpoints so
# the product can warn (or hard-block) before they reach client work.

MODEL_LICENSE_REGISTRY: tuple[dict[str, Any], ...] = (
    {"pattern": r"deepseek", "license": "DeepSeek Model License (commercial use permitted)", "commercial_ok": True},
    {"pattern": r"mistral|mixtral|ministral", "license": "Apache-2.0 (Mistral)", "commercial_ok": True},
    {"pattern": r"gemma", "license": "Gemma Terms of Use (commercial use permitted)", "commercial_ok": True},
    {"pattern": r"qwen", "license": "Tongyi Qianwen LICENSE (commercial use permitted <100M MAU)", "commercial_ok": True},
    {"pattern": r"phi-", "license": "MIT (Microsoft Phi)", "commercial_ok": True},
    {"pattern": r"llama-?3|llama3|^meta-llama", "license": "Llama 3 Community License (commercial use permitted)", "commercial_ok": True},
    {"pattern": r"llama-?2|llama2", "license": "Llama 2 Community License (commercial use permitted)", "commercial_ok": True},
    {"pattern": r"falcon", "license": "TII Falcon License (commercial use permitted)", "commercial_ok": True},
    # research-only examples that must NOT ship commercially:
    {"pattern": r"research|non-?commercial|-nc\b|galactica", "license": "RESEARCH/NON-COMMERCIAL ONLY", "commercial_ok": False},
)


def check_model_license(model_filename: str) -> dict[str, Any]:
    name = model_filename.lower()
    for entry in MODEL_LICENSE_REGISTRY:
        if re.search(entry["pattern"], name):
            return {
                "model": model_filename,
                "license": entry["license"],
                "commercial_ok": entry["commercial_ok"],
            }
    return {
        "model": model_filename,
        "license": "Unknown — verify with the model publisher before commercial use",
        "commercial_ok": False,
    }


# ------------------------------------------------------------------ loading


async def _get_local_llm():
    global _local_llm
    if _local_llm is not None:
        return _local_llm
    async with _LOCAL_LOCK:
        if _local_llm is not None:
            return _local_llm
        av = availability()
        if not av.llama_cpp_installed or not av.model_path_exists or av.blocked_by_license:
            return None
        log.info("loading local GGUF model: %s (gpu=%s)", settings.model_path, av.gpu_backend)

        def _load():
            from llama_cpp import Llama

            return Llama(
                model_path=settings.model_path,
                n_ctx=settings.model_ctx_size,
                n_gpu_layers=_auto_gpu_layers(av.gpu_backend),
                n_batch=settings.model_batch_size,
                verbose=False,
            )

        with timed("llm.load_seconds"):
            _local_llm = await asyncio.to_thread(_load)
        return _local_llm


_NO_MODEL_MSGS = {
    "missing": (
        "No local model is configured yet.\n\nTo use Local mode:\n"
        "1. Download a commercial-license GGUF model (e.g. Llama-3.2-3B-Instruct Q4_K_M).\n"
        "2. Set LOCAL_MODEL_PATH in your .env to the full path of the .gguf file.\n"
        "3. Restart the backend — or switch to API mode in the top bar."
    ),
    "license": (
        "The configured local model carries a research-only license and this "
        "deployment blocks non-commercial models (COUNSEL_ENFORCE_COMMERCIAL_MODELS). "
        "Ask your administrator to switch to a commercially licensed model such as "
        "Llama 3, Mistral, Gemma or DeepSeek distills."
    ),
}


def _friendly_api_error(status: int, body: str) -> str:
    if status in (401, 403):
        return (
            "The API provider rejected the key. Open Settings and check that "
            "your API key is valid for the selected provider."
        )
    if status == 429:
        return "The API provider is rate-limiting requests. Please wait a moment and retry."
    if status >= 500:
        return "The API provider had a temporary problem. Please retry shortly."
    detail = body[:200].replace("\n", " ")
    return f"The API request failed ({status}). {detail}"


def strip_md_artifacts(text: str) -> str:
    return re.sub(r"<\|[^|]*\|>", "", text)


# -------------------------------------------------------------- local branch


async def stream_local(messages: list[dict[str, str]], max_tokens: int = 1024) -> AsyncIterator[str]:
    av = availability()
    if av.blocked_by_license:
        yield _NO_MODEL_MSGS["license"]
        return
    llm = await _get_local_llm()
    if llm is None:
        yield _NO_MODEL_MSGS["missing"]
        return

    def _start_stream():
        return llm.create_chat_completion(
            messages=messages,  # type: ignore[arg-type]
            temperature=settings.model_temperature,
            max_tokens=max_tokens,
            n_batch=settings.model_batch_size,
            stream=True,
        )

    gen_ctx: dict = {}

    def runner() -> None:
        try:
            gen_ctx["stream"] = _start_stream()
        except Exception as exc:  # pragma: no cover
            gen_ctx["error"] = exc

    await asyncio.to_thread(runner)
    if "error" in gen_ctx:
        log.exception("local inference failed")
        yield "Local inference failed to start. Check the backend logs and your model file."
        return

    sync_stream = gen_ctx["stream"]
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def pump() -> None:
        try:
            for chunk in sync_stream:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                tok = delta.get("content") or ""
                usage = chunk.get("usage") or {}
                if usage.get("completion_tokens"):
                    observe("llm.tokens", float(usage["completion_tokens"]),
                            {"mode": "local"})
                if tok:
                    loop.call_soon_threadsafe(q.put_nowait, tok)
        except Exception as exc:  # pragma: no cover
            log.warning("stream ended with error: %s", exc)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=pump, daemon=True).start()
    while True:
        tok = await q.get()
        if tok is None:
            break
        inc("llm.tokens_generated", labels={"mode": "local"})
        yield strip_md_artifacts(tok)


# ---------------------------------------------------------------- api branch


async def stream_api(
    messages: list[dict[str, str]],
    api_key: Optional[str],
    max_tokens: int = 2048,
    user_id: str | None = None,
) -> AsyncIterator[str]:
    key = api_key or settings.api_key_fallback
    if not key:
        yield (
            "No API key configured. Add your DeepSeek/OpenAI-compatible key in "
            "Settings (it is stored only in this machine's OS keychain), or use "
            "Local mode."
        )
        return

    url = settings.api_base_url.rstrip("/") + "/chat/completions"
    cid = new_correlation_id()
    payload = {
        "model": settings.api_model,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    tokens_out = 0
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.api_timeout_seconds)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
                    record_audit(user_id, "llm.api_error", url,
                                 {"status": resp.status_code}, correlation_id=cid)
                    inc("llm.errors", labels={"provider": "api"})
                    yield _friendly_api_error(resp.status_code, body)
                    return
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        tok = chunk["choices"][0]["delta"].get("content")
                        usage = chunk.get("usage") or {}
                        if usage.get("completion_tokens"):
                            observe("llm.tokens", float(usage["completion_tokens"]), {"mode": "api"})
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if tok:
                        tokens_out += len(tok)
                        yield tok
        # external transmission happened — audit it (no content, no keys)
        record_audit(
            user_id, "llm.api_call",
            target=settings.api_base_url,
            detail={"model": settings.api_model, "messages_chars": sum(len(m["content"]) for m in messages),
                    "approx_tokens_out": tokens_out // 4},
            correlation_id=cid,
        )
        inc("llm.requests", labels={"mode": "api"})
    except httpx.HTTPError as exc:
        log.warning("API request error: %s", exc)
        inc("llm.errors", labels={"provider": "api"})
        yield (
            "Could not reach the API endpoint. Check your internet connection "
            "and the API base URL in Settings."
        )


# ---------------------------------------------------------------- public API


async def stream_chat(
    messages: list[dict[str, str]],
    mode: str = "api",
    api_key: Optional[str] = None,
    max_tokens: int = 2048,
    user_id: str | None = None,
) -> AsyncIterator[str]:
    """Single entry point used by chat, RAG answers, research writing, MDX."""
    start = time.perf_counter()
    if mode == "local":
        iterator = stream_local(messages, max_tokens=max_tokens)
    else:
        iterator = stream_api(messages, api_key=api_key, max_tokens=max_tokens, user_id=user_id)
    async for t in iterator:
        yield t
    observe("llm.latency_seconds", time.perf_counter() - start, {"mode": mode})


async def complete(
    messages: list[dict[str, str]],
    mode: str = "api",
    api_key: Optional[str] = None,
    max_tokens: int = 1024,
    user_id: str | None = None,
) -> str:
    parts: list[str] = []
    async for t in stream_chat(messages, mode=mode, api_key=api_key,
                               max_tokens=max_tokens, user_id=user_id):
        parts.append(t)
    return "".join(parts)


def system_prompt(jurisdiction: dict[str, str], mode: str, skill_blocks: list[str] | None = None) -> str:
    place = ", ".join(
        filter(None, [jurisdiction.get("city"), jurisdiction.get("province"),
                      jurisdiction.get("country")])
    )
    privacy = {
        "local": "This session is LOCAL-ONLY: nothing leaves this machine.",
        "api": ("This session uses an external API: remind the user not to paste "
                "privileged client data."),
    }.get(mode, "")
    skill_text = ""
    if skill_blocks:
        skill_text = "\n\nActive skills you MUST follow:\n" + "\n\n".join(
            f"- {b}" for b in skill_blocks
        )
    return (
        "You are Counsel AI, a careful assistant for legal professionals. "
        "You draft clearly, cite precisely, never fabricate statutes or case law, "
        "and always recommend professional verification before filing. "
        + (f"The user practises in: {place}. Tailor references accordingly." if place else "")
        + (f" {privacy}" if privacy else "")
        + skill_text
        + " Respond in clean Markdown. Never use emojis."
    )
