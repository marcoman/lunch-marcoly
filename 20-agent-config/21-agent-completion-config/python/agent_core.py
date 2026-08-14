"""
agent_core.py — domain logic for 21-agent-completion-config (no HTTP here).

=============================================================================
HOW TO READ THIS FILE
=============================================================================

Same product flow as 01-reference-agent, but at generate time LaunchDarkly
AgentControl supplies **model**, **system** message, and **user** message.

  1. Data          Personas (UI labels + LD context key/name)
  2. LaunchDarkly  Init server SDK + AI SDK; completion_config evaluation
  3. Providers     Route by served provider/model (Ollama Custom, Bedrock, …)
  4. Generation    generate_stream() — evaluate config, then stream LLM tokens

LaunchDarkly insertion point (read this first):
  generate_stream() → LDAIClient.completion_config(...)
  Docs: https://launchdarkly.com/docs/sdk/ai/python
  Keywords: AgentControl · completion config · AI SDK · message variables

Variables: the config user message includes {{ stories }}; we pass
{"stories": <formatted headlines>} so LaunchDarkly substitutes at evaluate time.
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
from ldai.tracker import TokenUsage
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient

from yahoo_news import format_stories_for_prompt

# ---------------------------------------------------------------------------
# 1. Data — demo personas (also become the LD evaluation context)
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
# Single source of truth with REST provisioning prompts.
BASELINE_MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"

CANNED_STORIES = (
    "No ticker stories loaded yet. Ask the user to click Get Stories."
)

# LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
# https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion

DEFAULT_CONFIG_KEY = "equity-briefing-completion"
DEFAULT_BEDROCK_REGION = "us-east-1"
DEFAULT_AWS_PROFILE = "Administrator"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"


@dataclass(frozen=True)
class Persona:
    """Selectable demo identity — also the LaunchDarkly user context."""

    id: str
    name: str
    profile: str
    anonymous: bool = False


PERSONAS: tuple[Persona, ...] = (
    Persona("conservative-charlie", "Conservative Charlie", "conservative"),
    Persona("neutral-nancy", "Neutral Nancy", "neutral"),
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
    # No name targeting — anonymous context falls through to baseline-analyst.
    Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", anonymous=True),
)


@dataclass
class Metrics:
    """Timing / usage fields for the Metrics panel."""

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
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read baseline message file {path}: {exc}") from exc


def baseline_system_prompt() -> str:
    """In-code baseline system prompt (same text as rest/messages/baseline-system.txt)."""
    return _read_message_file("baseline-system.txt").strip()


def baseline_user_template() -> str:
    """User prompt template with {{ stories }} (rest/messages/baseline-user.txt)."""
    return _read_message_file("baseline-user.txt").strip()


def render_baseline_user(stories_text: str) -> str:
    """Fill {{ stories }} locally when using the code baseline fallback."""
    template = baseline_user_template()
    return (
        template.replace("{{ stories }}", stories_text).replace("{{stories}}", stories_text)
    )


def baseline_messages(stories_text: str) -> list[dict[str, str]]:
    """Chat messages for the in-code baseline-analyst fallback."""
    return [
        {"role": "system", "content": baseline_system_prompt()},
        {"role": "user", "content": render_baseline_user(stories_text)},
    ]


def baseline_completion_default() -> AICompletionConfigDefault:
    """SDK default when the config key is missing / unreachable.

    Also documents the intended offline shape. When the config exists but is
    **turned off**, LaunchDarkly still returns the disabled variation
    (`enabled=false`) — see generate_stream() for the app-level fallback.
    https://launchdarkly.com/docs/sdk/ai/python
    """
    return AICompletionConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_ollama_model()),
        provider=ProviderConfig(name="Custom"),
        messages=[
            LDMessage(role="system", content=baseline_system_prompt()),
            LDMessage(role="user", content=baseline_user_template()),
        ],
    )


# ---------------------------------------------------------------------------
# 2. LaunchDarkly — server SDK + AI SDK (AgentControl)
# ---------------------------------------------------------------------------

_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


def init_launchdarkly() -> None:
    """Initialize the shared LaunchDarkly clients once at process start.

    LaunchDarkly: server-side SDK + AI SDK for AgentControl completion configs.
    https://launchdarkly.com/docs/sdk/ai/python
    """
    global _ld_client, _ai_client
    if _ai_client is not None:
        return

    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            "environment that targets equity-briefing-completion."
        )

    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    deadline = time.time() + 5.0
    while time.time() < deadline and not _ld_client.is_initialized():
        time.sleep(0.05)
    if not _ld_client.is_initialized():
        raise RuntimeError(
            "LaunchDarkly client failed to initialize within 5s. "
            "Check LD_SDK_KEY and network access to LaunchDarkly."
        )
    _ai_client = LDAIClient(_ld_client)


def ai_client() -> LDAIClient:
    if _ai_client is None:
        init_launchdarkly()
    assert _ai_client is not None
    return _ai_client


def build_context(persona: Persona) -> Context:
    """Build the LD evaluation context for this persona.

    Named personas: user key + name (name targeting matches Charlie/Nancy/Toby).
    Anonymous Amelia: fixed key, anonymous=True — not indexed as a known user;
    name rules do not match → fallthrough (baseline-analyst).
    https://launchdarkly.com/docs/sdk/features/anonymous
    """
    builder = Context.builder(persona.id).name(persona.name)
    if persona.anonymous:
        builder = builder.anonymous(True)
    return builder.build()


def evaluate_completion(
    persona: Persona,
    stories_text: str,
):
    """Fetch model + messages from AgentControl (completion mode).

    LaunchDarkly capability: completion_config evaluation with message variables.
    https://launchdarkly.com/docs/sdk/features/agentcontrol-config

    Default value is the in-code **baseline-analyst** shape (used if the config
    key is missing). When the config is turned **off**, LD returns enabled=false
    and generate_stream() applies the same baseline locally.
    """
    return ai_client().completion_config(
        config_key(),
        build_context(persona),
        baseline_completion_default(),
        {"stories": stories_text},
    )


def evaluation_meta(persona: Persona) -> dict[str, Any]:
    """Metadata for the served variation (public SDK: variation_detail).

    The typed AICompletionConfig exposes model/messages/provider/enabled, but not
    variationKey. That lives on the raw evaluation's ``_ldMeta`` (and in the
    metrics tracker). variation_detail also returns the match reason.
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    client = _ld_client
    if client is None:
        init_launchdarkly()
        client = _ld_client
    assert client is not None

    detail = client.variation_detail(
        config_key(),
        build_context(persona),
        baseline_completion_default().to_dict(),
    )
    value = detail.value if isinstance(detail.value, dict) else {}
    meta = value.get("_ldMeta") or {}
    return {
        "variationKey": meta.get("variationKey"),
        "version": meta.get("version"),
        "versionKey": meta.get("versionKey"),
        "mode": meta.get("mode"),
        "modelKey": meta.get("modelKey"),
        "modelVersion": meta.get("modelVersion"),
        "enabledMeta": meta.get("enabled"),
        "variationIndex": detail.variation_index,
        "reason": detail.reason,
    }


def log_served_variation(persona: Persona, meta: dict[str, Any] | None) -> None:
    """One-line server log: which AgentControl variation we received."""
    if not meta:
        print(f"[generate] {persona.name}: variation=(unknown)", flush=True)
        return
    key = meta.get("variationKey") or "(none)"
    reason = meta.get("reason") or {}
    reason_kind = reason.get("kind") if isinstance(reason, dict) else reason
    print(
        f"[generate] {persona.name}: variation={key!r} reason={reason_kind!r}",
        flush=True,
    )


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
                    "(baseline-analyst shape; used if config key is missing)."
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


def messages_as_dicts(config) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in config.messages or []:
        out.append({"role": msg.role, "content": msg.content})
    return out


def user_message_text(messages: list[dict[str, str]]) -> str:
    for msg in messages:
        if msg.get("role") == "user":
            return msg.get("content") or ""
    return ""


def system_message_text(messages: list[dict[str, str]]) -> str:
    for msg in messages:
        if msg.get("role") == "system":
            return msg.get("content") or ""
    return ""


def system_prompt_preview(messages: list[dict[str, str]], max_chars: int = 40) -> str:
    """Short preview for server logs (first line, capped)."""
    text = system_message_text(messages).strip()
    if not text:
        return "(none)"
    first_line = text.splitlines()[0].strip()
    if len(first_line) > max_chars:
        return first_line[: max_chars - 1] + "…"
    return first_line


def log_system_prompt_source(source: str, messages: list[dict[str, str]], persona: Persona) -> None:
    """Log that we have a system prompt (from LD or code baseline) without dumping it.

    Prefer the server terminal over the UI Status panel — the full prompt is long.
    """
    preview = system_prompt_preview(messages)
    print(
        f"[generate] {persona.name}: system prompt from {source}: {preview!r}",
        flush=True,
    )


def resolve_runtime(config) -> tuple[str, str]:
    """Map served provider/model to a local caller (ollama | bedrock).

    Custom / Ollama models from rest/create-model-config.sh use provider Custom
    and model id llama3.2:3b → call local Ollama.
    """
    model = (config.model.name if config.model else "") or ""
    provider_name = (config.provider.name if config.provider else "") or ""
    pl = provider_name.strip().lower()

    if pl in {"custom", "ollama"} or ":" in model:
        return "ollama", model
    if pl == "bedrock" or model.startswith(("us.", "amazon.", "anthropic.", "meta.")):
        return "bedrock", model
    if not model:
        raise RuntimeError(
            "AgentControl variation has no model name. "
            "Check modelConfigKey on the served variation in LaunchDarkly."
        )
    # Unknown provider: try Ollama with the model id (classroom default).
    return "ollama", model


# ---------------------------------------------------------------------------
# 3. Generation
# ---------------------------------------------------------------------------

def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, object]]:
    """Evaluate AgentControl, then stream tokens from the served model.

    Event contract matches 01-reference-agent (meta / token / error / metrics / done).

    When the AgentControl config is **disabled** (or returns enabled=false),
    fall back to the in-code baseline-analyst prompts + local Ollama model —
    same text as rest/messages/baseline-*.txt.
    """
    stories_text = format_stories(ticker_results)
    started = time.perf_counter()
    metrics = Metrics()
    tracker = None
    using_fallback = False

    try:
        # LaunchDarkly: evaluate completion config (model + messages).
        config = evaluate_completion(persona, stories_text)
        served_meta = evaluation_meta(persona)
    except Exception as exc:  # noqa: BLE001
        # Network / init failure — still try the code baseline so demos work.
        using_fallback = True
        config = None
        served_meta = None
        fallback_reason = f"LaunchDarkly evaluation failed ({exc}); using code baseline."
    else:
        fallback_reason = None
        if not config.enabled:
            # Config turned off in LD → disabled variation, not the SDK default.
            using_fallback = True
            fallback_reason = (
                f"AgentControl config '{config_key()}' is off / enabled=false; "
                "using code baseline-analyst."
            )

    if using_fallback:
        messages = baseline_messages(stories_text)
        provider, model = "ollama", default_ollama_model()
        mode = "baseline-fallback"
        print(
            f"[generate] {persona.name}: variation='code-baseline' reason='FALLBACK'",
            flush=True,
        )
        log_system_prompt_source("code baseline (AgentControl off)", messages, persona)
        prompt_preview = user_message_text(messages) or stories_text
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": prompt_preview,
            "provider": provider,
            "model": f"{model} (code baseline)",
            "mode": mode,
            "configKey": config_key(),
            "fallback": True,
            "stories": ticker_results or [],
            "ldTransaction": build_ld_transaction(
                persona=persona,
                stories_text=stories_text,
                config_key_value=config_key(),
                fallback=True,
                mode=mode,
                provider=provider,
                model=f"{model} (code baseline)",
                messages=messages,
                served_meta=served_meta,
                enabled=False if config is None else bool(config.enabled),
            ),
        }
        if fallback_reason:
            # Informational — not a hard failure; generation continues.
            yield {"type": "status", "message": fallback_reason}
        try:
            yield from _generate_ollama(model, messages, started, metrics)
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": str(exc)}
            metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    assert config is not None
    try:
        provider, model = resolve_runtime(config)
        messages = messages_as_dicts(config)
        if not messages:
            raise RuntimeError("Served variation has no messages.")
        tracker = config.create_tracker()
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
        yield {"type": "done"}
        return

    log_served_variation(persona, served_meta)
    log_system_prompt_source(f"LaunchDarkly ({config_key()})", messages, persona)
    prompt_preview = user_message_text(messages) or stories_text
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": prompt_preview,
        "provider": provider,
        "model": model,
        "mode": "launchdarkly",
        "configKey": config_key(),
        "variationKey": (served_meta or {}).get("variationKey"),
        "fallback": False,
        "stories": ticker_results or [],
        "ldTransaction": build_ld_transaction(
            persona=persona,
            stories_text=stories_text,
            config_key_value=config_key(),
            fallback=False,
            mode="launchdarkly",
            provider=provider,
            model=model,
            messages=messages,
            served_meta=served_meta,
            enabled=bool(config.enabled),
        ),
    }

    try:
        if provider == "ollama":
            yield from _generate_ollama(model, messages, started, metrics)
        elif provider == "bedrock":
            yield from _generate_bedrock(model, messages, started, metrics)
        else:
            raise RuntimeError(f"Unsupported runtime provider '{provider}'.")
        if tracker is not None:
            tracker.track_success()
            if metrics.latency_ms is None:
                metrics.latency_ms = int((time.perf_counter() - started) * 1000)
            tracker.track_duration(metrics.latency_ms or 0)
            if metrics.ttft_ms is not None:
                tracker.track_time_to_first_token(metrics.ttft_ms)
            if metrics.total_tokens or metrics.prompt_tokens or metrics.completion_tokens:
                tracker.track_tokens(
                    TokenUsage(
                        total=metrics.total_tokens or 0,
                        input=metrics.prompt_tokens or 0,
                        output=metrics.completion_tokens or 0,
                    )
                )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"
        if tracker is not None:
            try:
                tracker.track_error()
            except Exception:  # noqa: BLE001
                pass

    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {"type": "done"}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fill_token_estimates(messages: list[dict[str, str]], completion: str, metrics: Metrics) -> None:
    prompt = "".join(m.get("content") or "" for m in messages)
    metrics.prompt_tokens = estimate_tokens(prompt)
    metrics.completion_tokens = estimate_tokens(completion)
    metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)


# ---------------------------------------------------------------------------
# 4. Providers — call whatever model AgentControl named
# ---------------------------------------------------------------------------

def _generate_ollama(
    model: str,
    messages: list[dict[str, str]],
    started: float,
    metrics: Metrics,
) -> Iterator[dict[str, object]]:
    text_parts: list[str] = []
    first = True
    for chunk in _ollama_stream(model, messages):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        text_parts.append(chunk)
        yield {"type": "token", "text": chunk}
    metrics.finish_reason = "stop"
    _fill_token_estimates(messages, "".join(text_parts), metrics)


def _ollama_stream(model: str, messages: list[dict[str, str]]) -> Iterator[str]:
    """Stream from local Ollama using messages from AgentControl."""
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    url = f"{host}/api/chat"
    payload = {"model": model, "stream": True, "messages": messages}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(str(data["error"]))
                message = data.get("message") or {}
                content = message.get("content") or ""
                if content:
                    yield content
                if data.get("done"):
                    break
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama request failed ({host}, model={model}): {exc}. "
            "Is Ollama running, and does the AgentControl model id match `ollama list`?"
        ) from exc


def _generate_bedrock(
    model: str,
    messages: list[dict[str, str]],
    started: float,
    metrics: Metrics,
) -> Iterator[dict[str, object]]:
    text_parts: list[str] = []
    first = True
    for chunk in _bedrock_stream(model, messages, metrics):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        text_parts.append(chunk)
        yield {"type": "token", "text": chunk}
    if not metrics.finish_reason:
        metrics.finish_reason = "stop"
    if metrics.prompt_tokens is None or metrics.completion_tokens is None:
        _fill_token_estimates(messages, "".join(text_parts), metrics)


def _resolve_aws_region() -> str:
    return (
        os.environ.get("AWS_REGION", "").strip()
        or os.environ.get("AWS_DEFAULT_REGION", "").strip()
        or DEFAULT_BEDROCK_REGION
    )


def _resolve_aws_profile() -> str:
    return os.environ.get("AWS_PROFILE", "").strip() or DEFAULT_AWS_PROFILE


def _bedrock_runtime_client(region: str):
    import boto3

    profile = _resolve_aws_profile()
    cleared: dict[str, str] = {}
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
    ):
        if key in os.environ:
            cleared[key] = os.environ.pop(key)
    previous = os.environ.get("AWS_PROFILE")
    os.environ["AWS_PROFILE"] = profile
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client("bedrock-runtime")
    finally:
        os.environ.update(cleared)
        if previous is None:
            os.environ.pop("AWS_PROFILE", None)
        else:
            os.environ["AWS_PROFILE"] = previous


def _map_bedrock_stop_reason(stop_reason: str | None) -> str:
    if not stop_reason:
        return "stop"
    return {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "content_filtered": "content_filtered",
        "guardrail_intervened": "content_filtered",
        "tool_use": "tool_use",
    }.get(stop_reason, stop_reason)


def _bedrock_stream(
    model: str,
    messages: list[dict[str, str]],
    metrics: Metrics,
) -> Iterator[str]:
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for Bedrock models. "
            "pip install -r requirements.txt from the repository root."
        ) from exc

    region = _resolve_aws_region()
    profile = _resolve_aws_profile()
    try:
        client = _bedrock_runtime_client(region)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not create Bedrock client (profile={profile}, region={region}): {exc}"
        ) from exc

    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    user_parts = [m["content"] for m in messages if m.get("role") == "user"]
    request: dict[str, Any] = {
        "modelId": model,
        "messages": [
            {"role": "user", "content": [{"text": "\n\n".join(user_parts) or ""}]}
        ],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.5},
    }
    if system_parts:
        request["system"] = [{"text": "\n\n".join(system_parts)}]

    try:
        response = client.converse_stream(**request)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            f"Bedrock ConverseStream failed (profile={profile}, region={region}, model={model}): {exc}"
        ) from exc

    stream = response.get("stream")
    if stream is None:
        raise RuntimeError("Bedrock response did not include a stream.")

    for event in stream:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta") or {}
            text = delta.get("text") or ""
            if text:
                yield text
        elif "metadata" in event:
            usage = event["metadata"].get("usage") or {}
            if "inputTokens" in usage:
                metrics.prompt_tokens = int(usage["inputTokens"])
            if "outputTokens" in usage:
                metrics.completion_tokens = int(usage["outputTokens"])
            if "totalTokens" in usage:
                metrics.total_tokens = int(usage["totalTokens"])
            elif metrics.prompt_tokens is not None and metrics.completion_tokens is not None:
                metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens
        elif "messageStop" in event:
            metrics.finish_reason = _map_bedrock_stop_reason(
                event["messageStop"].get("stopReason")
            )
