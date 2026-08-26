"""Unified LLM service: local llama.cpp OR OpenAI-compatible HTTP API.

Adapted from llama.cpp's GGUF inference interface via `llama-cpp-python`
(MIT): chat-template formatting and token streaming are preserved; the
OpenAI-compatible branch speaks the same wire format as DeepSeek/OpenAI.

Both branches expose one async generator:

    async for token in stream_chat(messages, mode=..., api_key=...): ...

If the local model is missing/unavailable the generator yields a friendly
error message instead of raising — the UI degrades gracefully.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx

from ..config import settings

log = logging.getLogger("counsel.llm")

_LOCAL_LOCK = asyncio.Lock()
_local_llm = None  # llama_cpp.Llama | None


class LLMAvailability:
    model_path_exists = False
    llama_cpp_installed = False


def availability() -> LLMAvailability:
    av = LLMAvailability()
    p = settings.model_path
    av.model_path_exists = bool(p) and Path(p).exists()
    try:
        import llama_cpp  # noqa: F401

        av.llama_cpp_installed = True
    except ImportError:
        pass
    return av


async def _get_local_llm():
    """Lazily load the GGUF model once. Returns None when unusable."""
    global _local_llm
    if _local_llm is not None:
        return _local_llm
    async with _LOCAL_LOCK:
        if _local_llm is not None:
            return _local_llm
        av = availability()
        if not av.llama_cpp_installed or not av.model_path_exists:
            return None
        log.info("loading local GGUF model: %s", settings.model_path)

        def _load():
            from llama_cpp import Llama

            return Llama(
                model_path=settings.model_path,
                n_ctx=settings.model_ctx_size,
                n_gpu_layers=settings.model_gpu_layers,
                verbose=False,
            )

        _local_llm = await asyncio.to_thread(_load)
        return _local_llm


_NO_MODEL_MSG = (
    "No local model is configured yet.\n\n"
    "To use Local mode:\n"
    "1. Download a GGUF model (e.g. Llama-3.2-3B-Instruct Q4_K_M).\n"
    "2. Set LOCAL_MODEL_PATH in your .env file to the full path of the .gguf file.\n"
    "3. Restart the backend — or switch to API mode in the top bar."
)


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
    """Remove accidental tool-call artifacts some small models emit."""
    return re.sub(r"<\|[^|]*\|>", "", text)


async def stream_local(
    messages: list[dict[str, str]], max_tokens: int = 1024
) -> AsyncIterator[str]:
    llm = await _get_local_llm()
    if llm is None:
        yield _NO_MODEL_MSG
        return
    # llama-cpp-python's create_chat_completion(stream=True) returns a plain
    # sync iterator. We start it in a worker thread and pump tokens back over
    # an asyncio queue so the event loop (and therefore the WebSocket) stays
    # fully responsive while GGUF inference runs.

    def _start_stream():  # noqa: ANN202
        return llm.create_chat_completion(
            messages=messages,  # type: ignore[arg-type]
            temperature=settings.model_temperature,
            max_tokens=max_tokens,
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
    if "stream" not in gen_ctx:
        yield "Local inference produced no output."
        return

    sync_stream = gen_ctx["stream"]
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def pump() -> None:
        try:
            for chunk in sync_stream:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                tok = delta.get("content") or ""
                if tok:
                    loop.call_soon_threadsafe(q.put_nowait, tok)
        except Exception as exc:  # pragma: no cover
            log.warning("stream ended with error: %s", exc)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)

    import threading

    threading.Thread(target=pump, daemon=True).start()
    emitted = 0
    while True:
        tok = await q.get()
        if tok is None:
            break
        emitted += len(tok)
        yield strip_md_artifacts(tok)


async def stream_api(
    messages: list[dict[str, str]],
    api_key: Optional[str],
    max_tokens: int = 2048,
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
    payload = {
        "model": settings.api_model,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")
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
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if tok:
                        yield tok
    except httpx.HTTPError as exc:
        log.warning("API request error: %s", exc)
        yield (
            "Could not reach the API endpoint. Check your internet connection "
            "and the API base URL in Settings."
        )


async def stream_chat(
    messages: list[dict[str, str]],
    mode: str = "api",
    api_key: Optional[str] = None,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """Single entry point used by chat, RAG answers, research writing, MDX."""
    if mode == "local":
        async for t in stream_local(messages, max_tokens=max_tokens):
            yield t
    else:
        async for t in stream_api(messages, api_key=api_key, max_tokens=max_tokens):
            yield t


async def complete(
    messages: list[dict[str, str]],
    mode: str = "api",
    api_key: Optional[str] = None,
    max_tokens: int = 1024,
) -> str:
    parts: list[str] = []
    async for t in stream_chat(messages, mode=mode, api_key=api_key, max_tokens=max_tokens):
        parts.append(t)
    return "".join(parts)


def system_prompt(jurisdiction: dict[str, str], mode: str) -> str:
    place = ", ".join(
        filter(None, [jurisdiction.get("city"), jurisdiction.get("province"), jurisdiction.get("country")])
    )
    privacy = {
        "local": "This session is LOCAL-ONLY: nothing leaves this machine.",
        "api": "This session uses an external API: remind the user not to paste privileged client data.",
    }.get(mode, "")
    return (
        "You are Counsel AI, a careful assistant for legal professionals. "
        "You draft clearly, cite precisely, never fabricate statutes or case law, "
        "and always recommend professional verification before filing. "
        + (f"The user practises in: {place}. Tailor references accordingly." if place else "")
        + (f" {privacy}" if privacy else "")
        + " Respond in clean Markdown. Never use emojis."
    )
