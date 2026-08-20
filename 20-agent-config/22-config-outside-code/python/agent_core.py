"""
agent_core.py — domain logic for 22-config-outside-code (no HTTP here).

Teaching focus: AgentControl completion config **outside code**, with
**track_metrics_of** + thumbs feedback as the headline (Monitoring tab).

  1. Data          Personas (Best Betty → Anthropic, Anonymous Amelia → Ollama)
  2. LaunchDarkly  completion_config evaluation
  3. Providers     Ollama (default) or Anthropic (Best Betty)
  4. Generation    track_metrics_of wraps the LLM call; resumption token for feedback

LaunchDarkly: AgentControl · completion config · AI metrics · feedback
https://launchdarkly.com/docs/sdk/ai/python
https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import ldclient
from ldai import AICompletionConfigDefault, LDAIClient, LDMessage, ModelConfig, ProviderConfig
from ldai.providers.types import LDAIMetrics
from ldai.tracker import FeedbackKind, TokenUsage
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient

from yahoo_news import format_stories_for_prompt

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
BASELINE_MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"

CANNED_STORIES = (
    "No ticker stories loaded yet. Ask the user to click Get Stories."
)

# LaunchDarkly: ai-config key=equity-briefing-tracked-completion name="Equity briefing tracked completion" mode=completion
# https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tracked-completion

DEFAULT_CONFIG_KEY = "equity-briefing-tracked-completion"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    profile: str
    anonymous: bool = False


# Best Betty → tracked-anthropic (Claude). Anonymous Amelia → tracked-ollama (fallthrough).
PERSONAS: tuple[Persona, ...] = (
    Persona("best-betty", "Best Betty", "best"),
    Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", anonymous=True),
)


@dataclass
class Metrics:
    latency_ms: int | None = None
    ttft_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def persona_by_id(persona_id: str) -> Persona | None:
    for persona in PERSONAS:
        if persona.id == persona_id:
            return persona
    return None


def config_key() -> str:
    return os.environ.get("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).strip() or DEFAULT_CONFIG_KEY


def format_stories(ticker_results: list[dict[str, Any]] | None) -> str:
    if not ticker_results:
        return CANNED_STORIES
    return format_stories_for_prompt(ticker_results)


def default_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


def _read_message_file(name: str) -> str:
    path = BASELINE_MESSAGES_DIR / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Could not read {path}: {exc}") from exc


def baseline_system_prompt() -> str:
    return _read_message_file("baseline-system.txt")


def baseline_user_template() -> str:
    return _read_message_file("baseline-user.txt")


def render_baseline_user(stories_text: str) -> str:
    template = baseline_user_template()
    return template.replace("{{ stories }}", stories_text).replace("{{stories}}", stories_text)


def baseline_messages(stories_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": baseline_system_prompt()},
        {"role": "user", "content": render_baseline_user(stories_text)},
    ]


def baseline_completion_default() -> AICompletionConfigDefault:
    return AICompletionConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_ollama_model()),
        provider=ProviderConfig(name="Custom"),
        messages=[
            LDMessage(role="system", content=baseline_system_prompt()),
            LDMessage(role="user", content=baseline_user_template()),
        ],
    )


_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


def init_launchdarkly() -> None:
    """LaunchDarkly: server-side SDK + AI SDK for AgentControl."""
    global _ld_client, _ai_client
    if _ai_client is not None:
        return
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            f"environment that targets {DEFAULT_CONFIG_KEY}."
        )
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        ok = _ld_client.wait_for_initialization(5)
        if not ok:
            raise RuntimeError("LaunchDarkly client failed to initialize.")
    _ai_client = LDAIClient(_ld_client)


def ai_client() -> LDAIClient:
    if _ai_client is None:
        init_launchdarkly()
    assert _ai_client is not None
    return _ai_client


def ld_client() -> LDClient:
    if _ld_client is None:
        init_launchdarkly()
    assert _ld_client is not None
    return _ld_client


def build_context(persona: Persona) -> Context:
    builder = Context.builder(persona.id).kind("user").name(persona.name)
    if persona.anonymous:
        builder = builder.anonymous(True)
    return builder.build()


def evaluate_completion(persona: Persona, stories_text: str):
    """LaunchDarkly: completion_config with {{ stories }} variables."""
    return ai_client().completion_config(
        config_key(),
        build_context(persona),
        baseline_completion_default(),
        {"stories": stories_text},
    )


def messages_as_dicts(config) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in config.messages or []:
        role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
        if role and content is not None:
            out.append({"role": str(role), "content": str(content)})
    return out


def user_message_text(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def build_ld_transaction(
    *,
    persona: Persona,
    stories_text: str,
    config_key_value: str,
    fallback: bool,
    mode: str,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    served_meta: dict[str, Any] | None,
    enabled: bool | None,
) -> dict[str, object]:
    """Payload for the UI 'LD details' overlay (last generate: sent + received)."""
    context = build_context(persona)
    reason = (served_meta or {}).get("reason")
    return {
        "sent": {
            "configKey": config_key_value,
            "context": context.to_dict(),
            "variables": {"stories": stories_text},
            "sdkDefault": {
                "description": (
                    "AICompletionConfigDefault passed to completion_config "
                    "(baseline-analyst shape; used if config key is missing). "
                    "Generation runs inside track_metrics_of for Monitoring."
                ),
                "enabled": True,
                "model": default_ollama_model(),
                "provider": "Custom",
                "messages": [
                    {"role": "system", "content": baseline_system_prompt()},
                    {"role": "user", "content": baseline_user_template()},
                ],
            },
        },
        "received": {
            "fallback": fallback,
            "mode": mode,
            "enabled": enabled,
            "configKey": config_key_value,
            "variationKey": (served_meta or {}).get("variationKey"),
            "variationIndex": (served_meta or {}).get("variationIndex"),
            "reason": reason,
            "version": (served_meta or {}).get("version"),
            "versionKey": (served_meta or {}).get("versionKey"),
            "ldMode": (served_meta or {}).get("mode"),
            "modelKey": (served_meta or {}).get("modelKey"),
            "modelVersion": (served_meta or {}).get("modelVersion"),
            "provider": provider,
            "model": model,
            "messages": messages,
        },
    }


def resolve_runtime(config) -> tuple[str, str]:
    """Map served provider/model → ollama | anthropic."""
    model = (config.model.name if config.model else "") or ""
    provider_name = (config.provider.name if config.provider else "") or ""
    pl = provider_name.strip().lower()

    if pl == "anthropic" or model.startswith("claude-"):
        return "anthropic", model or DEFAULT_ANTHROPIC_MODEL
    if pl in {"custom", "ollama"} or ":" in model:
        return "ollama", model or default_ollama_model()
    if not model:
        raise RuntimeError("AgentControl variation has no model name.")
    return "ollama", model


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _chunk_yield(text: str, metrics: Metrics, started: float) -> Iterator[dict[str, object]]:
    """Yield UI tokens from a completed string (metrics already tracked)."""
    if not text:
        metrics.finish_reason = "stop"
        return
    metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
    # Chunk for SSE feel without another network round-trip.
    size = 24
    for i in range(0, len(text), size):
        yield {"type": "token", "text": text[i : i + size]}
    metrics.finish_reason = "stop"


def _ollama_complete(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = {"model": model, "stream": False, "messages": messages}
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    message = body.get("message") or {}
    text = str(message.get("content") or "")
    return {"text": text, "raw": body}


def _ollama_metrics(result: dict[str, Any]) -> LDAIMetrics:
    text = str(result.get("text") or "")
    prompt_est = 0  # filled by caller via tokens if needed
    out = estimate_tokens(text)
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(total=prompt_est + out, input=prompt_est, output=out),
    )


def _anthropic_complete(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required for Anthropic variations "
            "(Best Betty → tracked-anthropic). Export your Claude API key."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Package 'anthropic' is required. pip install -r requirements.txt"
        ) from exc

    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    chat = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in {"user", "assistant"}
    ]
    client = anthropic.Anthropic(api_key=api_key)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 1024,
        "messages": chat or [{"role": "user", "content": "Summarize the stories."}],
    }
    if system_parts:
        kwargs["system"] = "\n\n".join(system_parts)
    msg = client.messages.create(**kwargs)
    text_parts = []
    for block in msg.content or []:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(str(block.get("text") or ""))
    usage = getattr(msg, "usage", None)
    return {
        "text": "".join(text_parts),
        "usage": usage,
        "raw": msg,
    }


def _anthropic_metrics(result: dict[str, Any]) -> LDAIMetrics:
    usage = result.get("usage")
    inp = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    out = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    if not usage:
        text = str(result.get("text") or "")
        out = estimate_tokens(text)
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(total=inp + out, input=inp, output=out),
    )


def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, object]]:
    """Evaluate AgentControl, run LLM inside track_metrics_of, stream tokens to UI."""
    stories_text = format_stories(ticker_results)
    started = time.perf_counter()
    metrics = Metrics()
    resumption_token: str | None = None

    try:
        config = evaluate_completion(persona, stories_text)
    except Exception as exc:  # noqa: BLE001
        messages = baseline_messages(stories_text)
        provider, model = "ollama", default_ollama_model()
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": user_message_text(messages) or stories_text,
            "provider": provider,
            "model": f"{model} (code baseline)",
            "mode": "baseline-fallback",
            "configKey": config_key(),
            "fallback": True,
            "stories": ticker_results or [],
            "ldTransaction": build_ld_transaction(
                persona=persona,
                stories_text=stories_text,
                config_key_value=config_key(),
                fallback=True,
                mode="baseline-fallback",
                provider=provider,
                model=f"{model} (code baseline)",
                messages=messages,
                served_meta=None,
                enabled=False,
            ),
        }
        yield {"type": "status", "message": f"LaunchDarkly evaluation failed ({exc}); using code baseline."}
        try:
            result = _ollama_complete(model, messages)
            _fill_from_result(result, messages, metrics)
            yield from _chunk_yield(str(result.get("text") or ""), metrics, started)
        except Exception as gen_exc:  # noqa: BLE001
            yield {"type": "error", "message": str(gen_exc)}
            metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done", "resumptionToken": None}
        return

    if not config.enabled:
        messages = baseline_messages(stories_text)
        provider, model = "ollama", default_ollama_model()
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": user_message_text(messages) or stories_text,
            "provider": provider,
            "model": f"{model} (code baseline)",
            "mode": "baseline-fallback",
            "configKey": config_key(),
            "fallback": True,
            "stories": ticker_results or [],
            "ldTransaction": build_ld_transaction(
                persona=persona,
                stories_text=stories_text,
                config_key_value=config_key(),
                fallback=True,
                mode="baseline-fallback",
                provider=provider,
                model=f"{model} (code baseline)",
                messages=messages,
                served_meta=None,
                enabled=False,
            ),
        }
        yield {
            "type": "status",
            "message": f"AgentControl config '{config_key()}' is off; using code baseline.",
        }
        try:
            result = _ollama_complete(model, messages)
            _fill_from_result(result, messages, metrics)
            yield from _chunk_yield(str(result.get("text") or ""), metrics, started)
        except Exception as gen_exc:  # noqa: BLE001
            yield {"type": "error", "message": str(gen_exc)}
            metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done", "resumptionToken": None}
        return

    try:
        provider, model = resolve_runtime(config)
        messages = messages_as_dicts(config)
        if not messages:
            raise RuntimeError("Served variation has no messages.")
        tracker = config.create_tracker()
        resumption_token = getattr(tracker, "resumption_token", None)
    except Exception as exc:  # noqa: BLE001
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": stories_text,
            "provider": "—",
            "model": "—",
            "mode": "launchdarkly",
            "configKey": config_key(),
            "stories": ticker_results or [],
        }
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done", "resumptionToken": None}
        return

    print(
        f"[generate] {persona.name}: provider={provider} model={model} config={config_key()}",
        flush=True,
    )
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": user_message_text(messages) or stories_text,
        "provider": provider,
        "model": model,
        "mode": "launchdarkly",
        "configKey": config_key(),
        "fallback": False,
        "stories": ticker_results or [],
        "tracked": True,
        "ldTransaction": build_ld_transaction(
            persona=persona,
            stories_text=stories_text,
            config_key_value=config_key(),
            fallback=False,
            mode="launchdarkly",
            provider=provider,
            model=model,
            messages=messages,
            served_meta=None,
            enabled=True,
        ),
    }

    try:
        # LaunchDarkly: track_metrics_of — duration, success/error, tokens → Monitoring
        if provider == "anthropic":
            result = tracker.track_metrics_of(
                _anthropic_metrics,
                lambda: _anthropic_complete(model, messages),
            )
        elif provider == "ollama":
            prompt = "".join(m.get("content") or "" for m in messages)

            def _extract(res: dict[str, Any]) -> LDAIMetrics:
                text = str(res.get("text") or "")
                inp = estimate_tokens(prompt)
                out = estimate_tokens(text)
                return LDAIMetrics(
                    success=True,
                    tokens=TokenUsage(total=inp + out, input=inp, output=out),
                )

            result = tracker.track_metrics_of(
                _extract,
                lambda: _ollama_complete(model, messages),
            )
        else:
            raise RuntimeError(f"Unsupported runtime provider '{provider}'.")

        _fill_from_result(result, messages, metrics)
        yield from _chunk_yield(str(result.get("text") or ""), metrics, started)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"

    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {"type": "done", "resumptionToken": resumption_token}


def _fill_from_result(
    result: dict[str, Any],
    messages: list[dict[str, str]],
    metrics: Metrics,
) -> None:
    text = str(result.get("text") or "")
    usage = result.get("usage")
    if usage is not None:
        metrics.prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        metrics.completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)
    else:
        prompt = "".join(m.get("content") or "" for m in messages)
        metrics.prompt_tokens = estimate_tokens(prompt)
        metrics.completion_tokens = estimate_tokens(text)
        metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)


def submit_feedback(
    *,
    persona: Persona,
    resumption_token: str,
    kind: str,
) -> dict[str, Any]:
    """Record thumbs feedback against the same runId (resumption token).

    LaunchDarkly: track_feedback · FeedbackKind
    https://launchdarkly.com/docs/sdk/ai/python
    """
    token = (resumption_token or "").strip()
    if not token:
        raise RuntimeError("resumptionToken is required.")
    kind_l = kind.strip().lower()
    if kind_l in {"positive", "up", "thumbsup", "+"}:
        fb = FeedbackKind.Positive
    elif kind_l in {"negative", "down", "thumbsdown", "-"}:
        fb = FeedbackKind.Negative
    else:
        raise RuntimeError("kind must be positive or negative.")

    ctx = build_context(persona)
    result = ai_client().create_tracker(token, ctx)
    if not result.is_success:
        raise RuntimeError(result.error or "Could not rebuild tracker from resumption token.")
    tracker = result.value
    tracker.track_feedback({"kind": fb})
    return {"ok": True, "kind": fb.value}
