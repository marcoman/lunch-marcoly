"""
agent_core.py — domain logic for 26-flags-vs-agent-control (no HTTP here).

=============================================================================
HOW TO READ THIS FILE
=============================================================================

First variation only: **Original** (AgentControl). Separate flags and the JSON
flag are later variations. This file does not evaluate them.

  1. Data          Charlie and Toby (UI labels + LD context key/name)
  2. LaunchDarkly  completion_config for model + prompts, then one judge score
  3. Providers     Route by served provider/model (Ollama Custom, Bedrock, …)
  4. Generation    stream the draft, score it. On a fail, Original may run one tool.

LaunchDarkly insertion points (read these first):
  generate_stream() → LDAIClient.completion_config(...)
  then create_judge(...).evaluate(...) — score only
  Docs: https://launchdarkly.com/docs/sdk/ai/python
  Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
  Keywords: AgentControl · completion config · judges · create_judge · evaluate

The user message includes {{ stories }}; we pass {"stories": <headlines>}
so LaunchDarkly substitutes at evaluate time.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import ldclient
from ldai import (
    AICompletionConfigDefault,
    AIJudgeConfigDefault,
    LDAIClient,
    LDMessage,
    ModelConfig,
    ProviderConfig,
)
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

# LaunchDarkly: ai-config key=equity-briefing-flag-compare name="Equity briefing flag compare" mode=completion
# https://launchdarkly.com/docs/home/agentcontrol/quickstart
# Dedicated key so 21 keeps equity-briefing-completion.

DEFAULT_CONFIG_KEY = "equity-briefing-flag-compare"
# LaunchDarkly: ai-config key=equity-briefing-flag-compare-judge name="Equity briefing flag compare judge" mode=judge
# https://launchdarkly.com/docs/home/agentcontrol/judges
DEFAULT_JUDGE_KEY = "equity-briefing-flag-compare-judge"
DEFAULT_JUDGE_METRIC = "$ld:ai:judge:flag-compare"
DEFAULT_PASS_THRESHOLD = 0.65
# Library tool attached only to the AgentControl variation (reckless-hype).
# Feature flags cannot return this attachment.
REPAIR_TOOL_KEY = "reduce-briefing-uncertainty"
SOURCE_ORIGINAL = "original"
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


# Two personas: one name rule (Charlie) and a fallthrough (Toby).
PERSONAS: tuple[Persona, ...] = (
    Persona("conservative-charlie", "Conservative Charlie", "conservative"),
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
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


def demo_personas() -> tuple[Persona, ...]:
    """The screen shows Toby. Charlie's name rule stays on the config."""
    return tuple(p for p in PERSONAS if p.id == "thoughtless-toby")


def persona_by_id(persona_id: str) -> Persona | None:
    for persona in PERSONAS:
        if persona.id == persona_id:
            return persona
    return None


def config_key() -> str:
    return os.environ.get("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).strip() or DEFAULT_CONFIG_KEY


def judge_key() -> str:
    return os.environ.get("LD_JUDGE_KEY", DEFAULT_JUDGE_KEY).strip() or DEFAULT_JUDGE_KEY


def pass_threshold() -> float:
    raw = os.environ.get("JUDGE_PASS_THRESHOLD", "").strip()
    if not raw:
        return DEFAULT_PASS_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_PASS_THRESHOLD


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
    """In-code fallback system prompt (Charlie / concise-skeptic text)."""
    return _read_message_file("skeptic-system.txt").strip()


def baseline_user_template() -> str:
    """User prompt template with {{ stories }} (rest/messages/skeptic-user.txt)."""
    return _read_message_file("skeptic-user.txt").strip()


def render_baseline_user(stories_text: str) -> str:
    """Fill {{ stories }} locally when using the code baseline fallback."""
    template = baseline_user_template()
    return (
        template.replace("{{ stories }}", stories_text).replace("{{stories}}", stories_text)
    )


def baseline_messages(stories_text: str) -> list[dict[str, str]]:
    """Chat messages for the in-code concise-skeptic fallback."""
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


def ensure_ollama_openai_env() -> None:
    """Point the OpenAI client (used by create_judge) at local Ollama /v1.

    LaunchDarkly AI SDK judges run through an OpenAI-compatible runner.
    Ollama's /v1 API keeps the score local.
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    os.environ.setdefault("OPENAI_BASE_URL", f"{host}/v1")
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "ollama"))


def init_launchdarkly() -> None:
    """Initialize the shared LaunchDarkly clients once at process start.

    LaunchDarkly: server-side SDK + AI SDK for the completion config and the judge.
    https://launchdarkly.com/docs/sdk/ai/python
    """
    global _ld_client, _ai_client
    if _ai_client is not None:
        return

    ensure_ollama_openai_env()

    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            "environment that targets equity-briefing-flag-compare."
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

    Named personas: user key + name. The name rule matches Conservative Charlie.
    Thoughtless Toby is the fallthrough (reckless-hype).
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

    Default value is the in-code concise-skeptic shape (used if the config
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
    tools: list[str] | None = None,
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
                    "(concise-skeptic / Charlie shape; used if config key is missing)."
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
            "tools": tools or [],
            "appWork": [
                "Evaluated one completion config for the model, both messages, and any attached tools.",
                "LaunchDarkly substituted {{ stories }} before the app saw the user message.",
                "Called the model and provider named on that variation.",
                "Evaluated one judge config. On a fail, the app runs reduce-briefing-uncertainty if that tool is attached.",
                "Separate flags and the JSON flag do not return a tool, so a failed draft stays failed.",
            ],
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


def _collect_tokens(
    gen: Iterator[dict[str, object]], bucket: list[str]
) -> Iterator[dict[str, object]]:
    """Forward stream events and keep the draft text for the judge."""
    for event in gen:
        if event.get("type") == "token":
            bucket.append(str(event.get("text") or ""))
        yield event


def _rail_fields(messages: list[dict[str, str]]) -> dict[str, object]:
    """Fields the lab rail shows for the Original source."""
    return {
        "source": SOURCE_ORIGINAL,
        "systemPrompt": system_message_text(messages),
        "judgeOn": True,
        "judgeSurface": "judge-config",
        "evaluations": 1,
    }


def judge_default() -> AIJudgeConfigDefault:
    """SDK default if the judge config key is missing.

    temperature 0 keeps the local score steadier between runs.
    """
    return AIJudgeConfigDefault(
        enabled=True,
        model=ModelConfig(name="llama3.2:3b", parameters={"temperature": 0}),
        provider=ProviderConfig(name="Custom"),
        evaluation_metric_key=DEFAULT_JUDGE_METRIC,
        messages=[
            LDMessage(role="system", content=_read_message_file("judge-system.txt").strip()),
        ],
    )


def judge_input_text(stories_text: str) -> str:
    return (
        "Task: Write a short equity briefing comparing the tickers using only "
        f"the headlines below.\n\nHEADLINES:\n{stories_text}"
    )


async def _close_judge_client(judge) -> None:
    """Close the judge HTTP client while this event loop is still open.

    create_judge builds an async OpenAI client. If that client is only
    garbage-collected after asyncio.run() finishes, its destructor schedules
    aclose() on a dead loop and the server prints 'Event loop is closed'.
    """
    runner = judge.get_model_runner() if hasattr(judge, "get_model_runner") else None
    client = getattr(runner, "_client", None)
    close = getattr(client, "close", None)
    if close is None:
        return
    try:
        await close()
    except Exception:  # noqa: BLE001
        return


async def _eval_judge(persona: Persona, input_text: str, output_text: str) -> dict[str, Any]:
    """Score the draft. The result is display-only.

    LaunchDarkly: create_judge + evaluate — one judge, no rewrite.
    https://launchdarkly.com/docs/home/agentcontrol/judges
    Keywords: judges · create_judge · evaluate · online evaluations
    """
    default = judge_default()
    judge = ai_client().create_judge(
        judge_key(),
        build_context(persona),
        default,
        default_ai_provider="openai",
    )
    if judge is None:
        return {
            "success": False,
            "error": "create_judge returned None (disabled or unsupported provider)",
            "score": None,
            "reasoning": None,
            "passed": False,
        }
    try:
        result = await judge.evaluate(input_text, output_text, sampling_rate=1.0)
    finally:
        await _close_judge_client(judge)
    score = result.score
    threshold = pass_threshold()
    passed = score is not None and float(score) >= threshold
    return {
        "success": bool(result.success),
        "error": result.error_message,
        "score": score,
        "reasoning": result.reasoning,
        "metricKey": result.metric_key,
        "passed": passed,
        "threshold": threshold,
    }


def evaluating_event(surface: str, key: str) -> dict[str, str]:
    """One Trace line naming the LaunchDarkly resource about to be read."""
    return {"type": "eval", "surface": surface, "key": key}


def _score_events(
    persona: Persona,
    stories_text: str,
    draft: str,
    *,
    source: str = SOURCE_ORIGINAL,
    evaluations: int = 2,
) -> Iterator[dict[str, object]]:
    """Tell the Trace which judge is being evaluated, then score the draft."""
    yield evaluating_event("judge", judge_key())
    yield judge_event(
        persona,
        stories_text,
        draft,
        source=source,
        evaluations=evaluations,
    )


def judge_event(
    persona: Persona,
    stories_text: str,
    draft: str,
    *,
    source: str = SOURCE_ORIGINAL,
    evaluations: int = 2,
) -> dict[str, object]:
    """One judge evaluation. Score only; the draft is not rewritten."""
    threshold = pass_threshold()
    base: dict[str, object] = {
        "type": "judge",
        "source": source,
        "on": True,
        "judgeKey": judge_key(),
        "threshold": threshold,
        "evaluations": evaluations,
    }
    if not draft.strip():
        return {
            **base,
            "success": False,
            "passed": False,
            "score": None,
            "reasoning": None,
            "error": "No draft to score.",
        }
    try:
        scored = asyncio.run(
            _eval_judge(persona, judge_input_text(stories_text), draft)
        )
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "success": False,
            "passed": False,
            "score": None,
            "reasoning": None,
            "error": str(exc),
        }
    return {**base, **scored}


def attached_tool_names(config) -> list[str]:
    """Names served on the completion config. A flag evaluation has no equivalent.

    LaunchDarkly: Library tools on a completion variation.
    https://launchdarkly.com/docs/home/agentcontrol/tools
    """
    tools_map = getattr(config, "tools", None) or {}
    names: list[str] = []
    for key, tool in tools_map.items():
        names.append(str(getattr(tool, "name", None) or key))
    return names


def reduce_briefing_uncertainty(draft: str) -> str:
    """Handler for the Library tool reduce-briefing-uncertainty.

    The app calls this after a failed judge. The model does not choose to.
    Certainty language is softened, then a fixed hedge is appended.
    """
    text = draft or ""
    swaps = (
        (r"\b100\s*%", "low"),
        (r"\b9[5-9]\s*%", "limited"),
        (
            r"\b(?:buy hard|strong buy|all-in|moonshot|to the moon|can't lose|cannot lose|no-brainer)\b",
            "no firm trade",
        ),
        (r"\b(?:will soar|will double|can't miss|cannot miss)\b", "may not move"),
    )
    for pattern, repl in swaps:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    hedge = (
        "Uncertainty: these headlines do not support a firm recommendation. "
        "Confidence stays low, and missing information is left missing."
    )
    if "Uncertainty:" not in text:
        text = text.rstrip() + "\n\n" + hedge
    return text


def _repair_if_failed(
    config,
    tracker,
    draft: str,
    scored: dict[str, object],
) -> Iterator[dict[str, object]]:
    """Run the attached repair tool when the judge fails.

    Flag sources never reach this. They have no tool attachment to discover.
    """
    if scored.get("passed") is not False or scored.get("on") is False:
        return
    names = attached_tool_names(config)
    if REPAIR_TOOL_KEY not in names:
        yield {
            "type": "status",
            "message": (
                "Judge failed. This variation has no repair tool attached. "
                "Provision with rest/attach-repair-tool.sh."
            ),
        }
        return
    yield evaluating_event("tool", REPAIR_TOOL_KEY)
    repaired = reduce_briefing_uncertainty(draft)
    if tracker is not None:
        try:
            tracker.track_tool_call(REPAIR_TOOL_KEY)
        except Exception:  # noqa: BLE001
            pass
    yield {
        "type": "repair",
        "tool": REPAIR_TOOL_KEY,
        "repaired": repaired,
    }


# Feature flags — string, boolean, and JSON variations.
# https://launchdarkly.com/docs/sdk/features/flag-types
# Separate flags: one key per field. JSON flag: the same four fields in one body.
FLAG_MODEL_KEY = "configure-briefing-model"
FLAG_SYSTEM_KEY = "configure-briefing-system-prompt"
FLAG_USER_KEY = "configure-briefing-user-prompt"
FLAG_JUDGE_KEY = "enable-briefing-judge"
FLAG_JSON_KEY = "configure-briefing-json"
SOURCE_FLAGS = "flags"
SOURCE_JSON = "json"


def ld_client() -> LDClient:
    if _ld_client is None:
        init_launchdarkly()
    assert _ld_client is not None
    return _ld_client


def _fill_stories(template: str, stories_text: str) -> str:
    """Substitute headlines into a flag-served template.

    AgentControl does this inside completion_config. Flag values are plain
    strings, so the app replaces {{ stories }} itself.
    """
    return template.replace("{{ stories }}", stories_text).replace("{{stories}}", stories_text)


def _persona_prompts(persona: Persona) -> tuple[str, str, str]:
    """Code defaults when a flag is missing: Charlie cautious, Toby reckless."""
    if persona.id == "thoughtless-toby":
        return (
            "llama3.2:1b",
            _read_message_file("reckless-system.txt").strip(),
            _read_message_file("reckless-user.txt").strip(),
        )
    return (
        "llama3.2:3b",
        _read_message_file("skeptic-system.txt").strip(),
        _read_message_file("skeptic-user.txt").strip(),
    )


def _preview_value(value: Any, limit: int = 180) -> str:
    """Short drawer text for a flag value. Full prompts stay behind Show more in the UI."""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value or "")
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _detail_record(key: str, detail) -> dict[str, Any]:
    """What a feature-flag evaluation actually returns.

    LaunchDarkly: variation index and reason. A flag value is not a model,
    a message, or a provider — the app decides that after this record.
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    reason = detail.reason if isinstance(getattr(detail, "reason", None), dict) else {}
    return {
        "key": key,
        "variationIndex": detail.variation_index,
        "reason": reason,
        "reasonKind": reason.get("kind"),
        "valuePreview": _preview_value(detail.value),
    }


def _flag_detail(key: str, persona: Persona, default: Any):
    """Evaluate one feature flag for this persona.

    LaunchDarkly: variation_detail — value plus the reason (rule, fallthrough, error).
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    return ld_client().variation_detail(key, build_context(persona), default)


def _reason_error(detail) -> str | None:
    reason = getattr(detail, "reason", None) or {}
    if isinstance(reason, dict) and reason.get("kind") == "ERROR":
        return str(reason.get("errorKind") or "ERROR")
    return None


def _resolve_separate_flags(persona: Persona) -> Iterator[dict[str, object]]:
    """Four evaluations. Each flag repeats the Charlie name rule.

    Yields a Trace event before each read, then returns the resolved fields.
    """
    model_default, system_default, user_default = _persona_prompts(persona)
    pairs = (
        (FLAG_MODEL_KEY, model_default),
        (FLAG_SYSTEM_KEY, system_default),
        (FLAG_USER_KEY, user_default),
        (FLAG_JUDGE_KEY, True),
    )
    details = []
    records = []
    for key, default in pairs:
        yield evaluating_event("flag", key)
        detail = _flag_detail(key, persona, default)
        details.append(detail)
        records.append(_detail_record(key, detail))
    model_detail, system_detail, user_detail, judge_detail = details
    missing = [
        key
        for key, detail in (
            (FLAG_MODEL_KEY, model_detail),
            (FLAG_SYSTEM_KEY, system_detail),
            (FLAG_USER_KEY, user_detail),
            (FLAG_JUDGE_KEY, judge_detail),
        )
        if _reason_error(detail) == "FLAG_NOT_FOUND"
    ]
    return (
        str(model_detail.value or model_default),
        str(system_detail.value or system_default),
        str(user_detail.value or user_default),
        bool(judge_detail.value),
        missing,
        records,
    )


def _resolve_json_flag(persona: Persona) -> Iterator[dict[str, object]]:
    """One evaluation. The variation body holds model, both prompts, and judge."""
    model_default, system_default, user_default = _persona_prompts(persona)
    default_body = {
        "model": model_default,
        "systemPrompt": system_default,
        "userPrompt": user_default,
        "judge": True,
    }
    yield evaluating_event("flag", FLAG_JSON_KEY)
    detail = _flag_detail(FLAG_JSON_KEY, persona, default_body)
    missing = [FLAG_JSON_KEY] if _reason_error(detail) == "FLAG_NOT_FOUND" else []
    body = detail.value if isinstance(detail.value, dict) else default_body
    return (
        str(body.get("model") or model_default),
        str(body.get("systemPrompt") or system_default),
        str(body.get("userPrompt") or user_default),
        bool(body.get("judge", True)),
        missing,
        [_detail_record(FLAG_JSON_KEY, detail)],
    )


def _flag_app_work(source: str, judge_on: bool) -> list[str]:
    """Steps the app still owns after the flag evaluation returns."""
    if source == SOURCE_JSON:
        steps = [
            "Evaluated one JSON flag. The value is an object the app defined.",
            "Read model, systemPrompt, userPrompt, and judge out of that object.",
            "Substituted {{ stories }} in the user prompt.",
            "Built the message list and picked a provider from the model id.",
        ]
    else:
        steps = [
            "Evaluated four flags. Each one repeated the Charlie name rule.",
            "Substituted {{ stories }} in the user-prompt flag.",
            "Built the message list from two string flags and picked a provider from the model id.",
        ]
    if judge_on:
        steps.append(
            "The flag said to score. The score itself still comes from the AgentControl judge config."
        )
    else:
        steps.append("The flag said not to score, so the draft stays plain.")
    return steps


def _generate_from_resolved(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None,
    *,
    source: str,
    model: str,
    system_template: str,
    user_template: str,
    judge_on: bool,
    evaluations: int,
    judge_surface: str,
    missing: list[str],
    flag_evaluations: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, object]]:
    """Stream a draft from flag-served fields, then score only when judge_on."""
    stories_text = format_stories(ticker_results)
    started = time.perf_counter()
    metrics = Metrics()
    messages = [
        {"role": "system", "content": system_template.strip()},
        {"role": "user", "content": _fill_stories(user_template, stories_text)},
    ]
    provider = "bedrock" if model.startswith(("us.", "amazon.", "anthropic.", "meta.")) else "ollama"
    context = build_context(persona)
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": messages[1]["content"],
        "userTemplate": user_template.strip(),
        "provider": provider,
        "model": model,
        "mode": source,
        "configKey": FLAG_JSON_KEY if source == SOURCE_JSON else FLAG_MODEL_KEY,
        "fallback": bool(missing),
        "stories": ticker_results or [],
        "source": source,
        "systemPrompt": system_template.strip(),
        "judgeOn": judge_on,
        "judgeSurface": judge_surface if judge_on else "off",
        "evaluations": evaluations,
        "ldTransaction": {
            "sent": {
                "source": source,
                "context": context.to_dict(),
                "evaluations": evaluations,
            },
            "received": {
                "source": source,
                "model": model,
                "judgeOn": judge_on,
                "flagEvaluations": flag_evaluations or [],
                "appWork": _flag_app_work(source, judge_on),
                "messages": [
                    {"role": "system", "content": system_template.strip()},
                    {"role": "user", "content": user_template.strip()},
                ],
            },
        },
    }
    if missing:
        joined = ", ".join(missing)
        yield {
            "type": "status",
            "message": (
                f"Flag not found: {joined}. Using in-code defaults. "
                "Provision with rest/create-flags.sh."
            ),
        }

    draft_parts: list[str] = []
    try:
        stream = (
            _generate_bedrock(model, messages, started, metrics)
            if provider == "bedrock"
            else _generate_ollama(model, messages, started, metrics)
        )
        yield from _collect_tokens(stream, draft_parts)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"

    if judge_on:
        yield {"type": "status", "message": "Scoring the draft…"}
        yield from _score_events(
            persona,
            stories_text,
            "".join(draft_parts),
            source=source,
            evaluations=evaluations + 1,
        )
    else:
        yield {
            "type": "judge",
            "source": source,
            "on": False,
            "passed": None,
            "score": None,
            "evaluations": evaluations,
        }

    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {"type": "done"}


# ---------------------------------------------------------------------------
# 3. Generation
# ---------------------------------------------------------------------------

def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None = None,
    source: str = SOURCE_ORIGINAL,
) -> Iterator[dict[str, object]]:
    """Evaluate the completion config, stream the draft, then score it.

    Event contract: meta / token / judge / error / metrics / done.
    The judge reports pass or fail. It does not rewrite the draft.

    When the completion config is disabled, fall back to the in-code
    concise-skeptic prompts plus local Ollama, then still score.

    source "flags" evaluates four feature flags. source "json" evaluates one
    JSON flag. Both score only when the served judge field is true.
    """
    if source == SOURCE_FLAGS:
        model, system_text, user_text, judge_on, missing, flag_evaluations = (
            yield from _resolve_separate_flags(persona)
        )
        yield from _generate_from_resolved(
            persona,
            ticker_results,
            source=SOURCE_FLAGS,
            model=model,
            system_template=system_text,
            user_template=user_text,
            judge_on=judge_on,
            evaluations=4,
            judge_surface="boolean-flag",
            missing=missing,
            flag_evaluations=flag_evaluations,
        )
        return
    if source == SOURCE_JSON:
        model, system_text, user_text, judge_on, missing, flag_evaluations = (
            yield from _resolve_json_flag(persona)
        )
        yield from _generate_from_resolved(
            persona,
            ticker_results,
            source=SOURCE_JSON,
            model=model,
            system_template=system_text,
            user_template=user_text,
            judge_on=judge_on,
            evaluations=1,
            judge_surface="json-flag",
            missing=missing,
            flag_evaluations=flag_evaluations,
        )
        return

    stories_text = format_stories(ticker_results)
    started = time.perf_counter()
    metrics = Metrics()
    tracker = None
    using_fallback = False

    yield evaluating_event("agent config", config_key())
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
                "using code concise-skeptic."
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
            **_rail_fields(messages),
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
        draft_parts: list[str] = []
        try:
            yield from _collect_tokens(
                _generate_ollama(model, messages, started, metrics), draft_parts
            )
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "message": str(exc)}
            metrics.finish_reason = "error"
        yield {"type": "status", "message": "Scoring the draft…"}
        yield from _score_events(persona, stories_text, "".join(draft_parts))
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
            "source": SOURCE_ORIGINAL,
            "systemPrompt": "",
            "judgeOn": True,
            "judgeSurface": "judge-config",
            "evaluations": 1,
        }
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "status", "message": "Scoring the draft…"}
        yield from _score_events(persona, stories_text, "")
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
        **_rail_fields(messages),
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
                tools=attached_tool_names(config),
            ),
        }
    reason = (served_meta or {}).get("reason") or {}
    if isinstance(reason, dict) and reason.get("errorKind") == "FLAG_NOT_FOUND":
        yield {
            "type": "status",
            "message": (
                f"Completion config '{config_key()}' was not found. "
                "Using the in-code concise-skeptic default. "
                "Provision with rest/create-original.sh."
            ),
        }

    draft_parts: list[str] = []
    try:
        if provider == "ollama":
            yield from _collect_tokens(
                _generate_ollama(model, messages, started, metrics), draft_parts
            )
        elif provider == "bedrock":
            yield from _collect_tokens(
                _generate_bedrock(model, messages, started, metrics), draft_parts
            )
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

    yield {"type": "status", "message": "Scoring the draft…"}
    draft_text = "".join(draft_parts)
    scored: dict[str, object] | None = None
    for event in _score_events(persona, stories_text, draft_text):
        if event.get("type") == "judge":
            scored = event
        yield event
    if scored is not None:
        yield from _repair_if_failed(config, tracker, draft_text, scored)
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
