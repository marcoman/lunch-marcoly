"""
agent_core.py — domain logic for 23-agent-tools (no HTTP here).

Teaching focus: AgentControl **Library tools** attached to a completion
variation; the app runs a model-driven tool loop and records
``track_tool_call`` for Monitoring.

  1. Data          Personas (Claude → Anthropic; Llama → Ollama 3.2:3b; Gwen → Ollama 1b)
  2. LaunchDarkly  completion_config (tools attached on the variation)
  3. Providers     Anthropic (cloud) or Ollama (local offline path)
  4. Generation    tool loop: analyze each ticker → compare → final briefing

LaunchDarkly: AgentControl · Library tools · track_tool_call
https://launchdarkly.com/docs/home/agentcontrol/tools
https://launchdarkly.com/docs/sdk/ai/python
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import ldclient
from ldai import AICompletionConfigDefault, LDAIClient, LDMessage, ModelConfig, ProviderConfig
from ldai.providers.types import LDAIMetrics
from ldai.tracker import TokenUsage
from ldclient import Context
from ldclient.config import Config

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
BASELINE_MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"

CANNED_STORIES = (
    "No ticker stories loaded yet. Ask the user to click Get Stories."
)

# LaunchDarkly: ai-config key=equity-briefing-tools name="Equity briefing tools" mode=completion
# Tools: analyze-ticker-stories · compare-ticker-analyses
# https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tools

DEFAULT_CONFIG_KEY = "equity-briefing-tools"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
# Tool-capable local default (1b is too weak for reliable tool loops).
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
TOOL_ANALYZE = "analyze-ticker-stories"
TOOL_COMPARE = "compare-ticker-analyses"
MAX_TOOL_STEPS = 6
# Extra system guidance for small local models (Ollama personas).
OLLAMA_TOOL_SUFFIX = (
    "Local-model rules (Ollama):\n"
    "- You MUST call tools before writing any briefing.\n"
    "- One tool call per turn when possible: analyze ticker 1, then analyze ticker 2, "
    "then compare-ticker-analyses.\n"
    "- Never call compare in the same turn as analyze.\n"
    "- Pass the exact analyze JSON as analysis_a / analysis_b — do not invent fields.\n"
    "- Do not skip compare-ticker-analyses after two analyzes."
)

POSITIVE_WORDS = frozenset(
    {
        "surge",
        "soar",
        "gain",
        "gains",
        "rise",
        "rises",
        "jump",
        "jumps",
        "beat",
        "beats",
        "record",
        "growth",
        "upgrade",
        "bullish",
        "profit",
        "profits",
        "strong",
        "rally",
    }
)
NEGATIVE_WORDS = frozenset(
    {
        "fall",
        "falls",
        "drop",
        "drops",
        "plunge",
        "cut",
        "cuts",
        "miss",
        "misses",
        "loss",
        "losses",
        "downgrade",
        "bearish",
        "weak",
        "lawsuit",
        "probe",
        "decline",
        "risk",
        "risks",
    }
)


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    # Local runtime preference only — not an LD targeting attribute.
    # "anthropic" (Analyst Claude) or "ollama" (Analyst Llama / Gwen).
    profile: str
    # Optional pinned model (Ollama tag). None → env / default for that persona.
    model: str | None = None
    anonymous: bool = False


# UI identities + in-app provider/model choice (not LaunchDarkly name targeting).
PERSONAS: tuple[Persona, ...] = (
    Persona("analyst-claude", "Analyst Claude", "anthropic"),
    Persona("analyst-llama", "Analyst Llama", "ollama", model="llama3.2:3b"),
    # Smaller sibling — expect more skips; Ollama guardrails still apply.
    Persona("analyst-gwen", "Analyst Gwen", "ollama", model="llama3.2:1b"),
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


_ld_client = None
_ai_client: LDAIClient | None = None


def persona_by_id(persona_id: str) -> Persona | None:
    for persona in PERSONAS:
        if persona.id == persona_id:
            return persona
    return None


def config_key() -> str:
    return os.environ.get("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).strip() or DEFAULT_CONFIG_KEY


def default_anthropic_model() -> str:
    return (
        os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).strip()
        or DEFAULT_ANTHROPIC_MODEL
    )


def default_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


def persona_runtime(persona: Persona) -> str:
    """Preferred LLM runtime for this UI persona (local app choice)."""
    profile = (persona.profile or "").strip().lower()
    if profile in {"ollama", "local", "gwen", "llama"}:
        return "ollama"
    return "anthropic"


def persona_model_name(persona: Persona, ld_model: str) -> tuple[str, str]:
    """
    Resolve (provider, model) for this persona.

    LaunchDarkly supplies the Anthropic model on the variation; Ollama personas
    use the pinned Persona.model (or OLLAMA_MODEL / default).
    """
    if persona_runtime(persona) == "ollama":
        pinned = (persona.model or "").strip()
        return "ollama", pinned or default_ollama_model()
    model = ld_model if ld_model.startswith("claude") else default_anthropic_model()
    return "anthropic", model


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


from yahoo_news import format_story_source


def stories_as_prompt_text(ticker_results: list[dict[str, Any]] | None) -> str:
    """Plain-text headlines for {{ stories }} (avoids Mustache HTML-escaping of JSON quotes)."""
    if not ticker_results:
        return CANNED_STORIES
    lines: list[str] = []
    for block in ticker_results:
        ticker = str(block.get("ticker") or "?").strip().upper() or "?"
        name = str(block.get("name") or ticker).strip()
        lines.append(f"{ticker} ({name})")
        stories = block.get("stories") or []
        if not stories:
            lines.append("  - (no stories available)")
            if block.get("error"):
                lines.append(f"  - note: {block['error']}")
        else:
            for i, story in enumerate(stories, start=1):
                if not isinstance(story, dict):
                    continue
                title = str(story.get("title") or "").strip() or "(untitled)"
                source = format_story_source(story) or "unknown"
                lines.append(f"  {i}. {title} — {source}")
        lines.append("")
    return "\n".join(lines).strip()


def prompt_display_sections(stories_text: str) -> list[dict[str, str]]:
    """UI-friendly sections for the User Prompt panel (heading / body / code)."""
    return [
        {
            "kind": "heading",
            "text": "Task",
        },
        {
            "kind": "body",
            "text": "Write an equity briefing for these tickers using the required tools.",
        },
        {
            "kind": "heading",
            "text": "Stories",
        },
        {
            "kind": "code",
            "text": stories_text,
        },
        {
            "kind": "heading",
            "text": "Reminder",
        },
        {
            "kind": "body",
            "text": (
                "Call analyze-ticker-stories once per ticker (pass that ticker's headlines), "
                "then compare-ticker-analyses, then write the briefing from tool results only."
            ),
        },
    ]


def init_launchdarkly() -> None:
    """Initialize server SDK + AI client once at process start."""
    global _ld_client, _ai_client
    if _ai_client is not None:
        return
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            f"LD_SDK_KEY is required. Export a server-side SDK key for the "
            f"environment that targets {DEFAULT_CONFIG_KEY}."
        )
    ldclient.set_config(Config(sdk_key))
    _ld_client = ldclient.get()
    if not _ld_client.is_initialized():
        raise RuntimeError(
            "LaunchDarkly client failed to initialize. Check LD_SDK_KEY and network."
        )
    _ai_client = LDAIClient(_ld_client)


def ai_client() -> LDAIClient:
    if _ai_client is None:
        init_launchdarkly()
    assert _ai_client is not None
    return _ai_client


def build_context(persona: Persona) -> Context:
    builder = Context.builder(persona.id).name(persona.name)
    if persona.anonymous:
        builder = builder.anonymous(True)
    return builder.build()


def baseline_completion_default() -> AICompletionConfigDefault:
    return AICompletionConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_anthropic_model()),
        provider=ProviderConfig(name="anthropic"),
        messages=[
            LDMessage(role="system", content=baseline_system_prompt()),
            LDMessage(role="user", content=baseline_user_template()),
        ],
    )


def evaluate_completion(persona: Persona, stories_text: str):
    """LaunchDarkly: completion_config — model, messages, and attached tools."""
    return ai_client().completion_config(
        config_key(),
        build_context(persona),
        baseline_completion_default(),
        {"stories": stories_text},
    )


def _empty_metrics() -> Metrics:
    return Metrics()


def _messages_as_dicts(config) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for msg in config.messages or []:
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None)
        if role and content is not None:
            out.append({"role": str(role), "content": str(content)})
    return out


def _user_message_text(messages: list[dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content") or ""
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
                    "(baseline shape with Library tools; used if config key is missing)."
                ),
                "enabled": True,
                "model": default_anthropic_model(),
                "provider": "anthropic",
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


def _ld_tools_to_anthropic(config) -> list[dict[str, Any]]:
    """Convert config.tools (LDTool map) to Anthropic tools= shape."""
    tools_map = getattr(config, "tools", None) or {}
    out: list[dict[str, Any]] = []
    for key, tool in tools_map.items():
        name = getattr(tool, "name", None) or key
        description = getattr(tool, "description", None) or ""
        parameters = getattr(tool, "parameters", None) or {
            "type": "object",
            "properties": {},
        }
        out.append(
            {
                "name": str(name),
                "description": str(description),
                "input_schema": parameters,
            }
        )
    return out


def _ld_tools_to_openai(config) -> list[dict[str, Any]]:
    """Convert config.tools to OpenAI/Ollama Chat Completions tools= shape."""
    tools_map = getattr(config, "tools", None) or {}
    out: list[dict[str, Any]] = []
    for key, tool in tools_map.items():
        name = getattr(tool, "name", None) or key
        description = getattr(tool, "description", None) or ""
        parameters = getattr(tool, "parameters", None) or {
            "type": "object",
            "properties": {},
        }
        out.append(
            {
                "type": "function",
                "function": {
                    "name": str(name),
                    "description": str(description),
                    "parameters": parameters,
                },
            }
        )
    return out


def _dispatch_tool(name: str, raw_input: dict[str, Any]) -> dict[str, Any]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool: {name}"}
    return handler(raw_input)


def _looks_like_analyze_result(obj: Any) -> bool:
    """True when obj resembles handle_analyze_ticker_stories output."""
    if not isinstance(obj, dict):
        return False
    return "ticker" in obj and ("tone_score" in obj or "claims" in obj)


def _normalize_compare_args(
    raw_input: dict[str, Any],
    analyze_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """
    Prefer real analyze tool results over model-invented compare args.

    Small local models often call compare in parallel with inventing analysis_a/b.
    Returns (args, rewritten).
    """
    a = raw_input.get("analysis_a") if isinstance(raw_input.get("analysis_a"), dict) else {}
    b = raw_input.get("analysis_b") if isinstance(raw_input.get("analysis_b"), dict) else {}
    if _looks_like_analyze_result(a) and _looks_like_analyze_result(b):
        return {"analysis_a": a, "analysis_b": b}, False
    if len(analyze_results) >= 2:
        return {
            "analysis_a": analyze_results[-2],
            "analysis_b": analyze_results[-1],
        }, True
    return {"analysis_a": a, "analysis_b": b}, False


def _ollama_tool_name(call: dict[str, Any]) -> str:
    fn = call.get("function") if isinstance(call, dict) else None
    if not isinstance(fn, dict):
        return ""
    return str(fn.get("name") or "")


def _sort_ollama_tool_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run analyzes before compare within the same model turn."""

    def sort_key(call: dict[str, Any]) -> int:
        name = _ollama_tool_name(call)
        if name == TOOL_ANALYZE:
            return 0
        if name == TOOL_COMPARE:
            return 1
        return 2

    return sorted(calls, key=sort_key)


def _sentiment_score(text: str) -> int:
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    score = 0
    for tok in tokens:
        if tok in POSITIVE_WORDS:
            score += 1
        elif tok in NEGATIVE_WORDS:
            score -= 1
    return score


def handle_analyze_ticker_stories(args: dict[str, Any]) -> dict[str, Any]:
    """Deterministic single-ticker analysis grounded in headline titles."""
    ticker = str(args.get("ticker") or "").strip().upper() or "?"
    raw_stories = args.get("stories") or []
    claims: list[dict[str, str]] = []
    score = 0
    for item in raw_stories:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        tone = _sentiment_score(title)
        score += tone
        if tone > 0:
            claim = f"Positive headline signal for {ticker}: {title}"
        elif tone < 0:
            claim = f"Negative headline signal for {ticker}: {title}"
        else:
            claim = f"Neutral headline for {ticker}: {title}"
        claims.append({"claim": claim, "evidence_title": title})
    if not claims:
        summary = f"No usable headlines provided for {ticker}."
    elif score > 0:
        summary = f"{ticker}: net positive headline tone ({len(claims)} stories)."
    elif score < 0:
        summary = f"{ticker}: net negative headline tone ({len(claims)} stories)."
    else:
        summary = f"{ticker}: mixed/neutral headline tone ({len(claims)} stories)."
    return {
        "ticker": ticker,
        "claims": claims,
        "summary": summary,
        "tone_score": score,
    }


def handle_compare_ticker_analyses(args: dict[str, Any]) -> dict[str, Any]:
    """Compare two analyze-ticker-stories results; optional preferred ticker."""
    a = args.get("analysis_a") if isinstance(args.get("analysis_a"), dict) else {}
    b = args.get("analysis_b") if isinstance(args.get("analysis_b"), dict) else {}
    ta = str(a.get("ticker") or "A").upper()
    tb = str(b.get("ticker") or "B").upper()
    sa = int(a.get("tone_score") or 0)
    sb = int(b.get("tone_score") or 0)

    def stance(score: int) -> str:
        if score > 0:
            return "constructive"
        if score < 0:
            return "cautious"
        return "neutral"

    evidence_a = [c.get("evidence_title") for c in (a.get("claims") or []) if isinstance(c, dict)]
    evidence_b = [c.get("evidence_title") for c in (b.get("claims") or []) if isinstance(c, dict)]
    evidence_a = [e for e in evidence_a if e]
    evidence_b = [e for e in evidence_b if e]

    preferred = None
    if sa > sb:
        preferred = ta
    elif sb > sa:
        preferred = tb

    rationale_parts = [
        f"{ta} tone_score={sa} ({stance(sa)}); {tb} tone_score={sb} ({stance(sb)})."
    ]
    if preferred:
        rationale_parts.append(
            f"{preferred} is the better option on headline tone alone."
        )
    else:
        rationale_parts.append("No clear preferred ticker on headline tone.")

    return {
        "ticker1": {
            "ticker": ta,
            "recommendation": stance(sa),
            "evidence": evidence_a,
        },
        "ticker2": {
            "ticker": tb,
            "recommendation": stance(sb),
            "evidence": evidence_b,
        },
        "preferred_ticker": preferred,
        "rationale": " ".join(rationale_parts),
    }


TOOL_HANDLERS = {
    TOOL_ANALYZE: handle_analyze_ticker_stories,
    TOOL_COMPARE: handle_compare_ticker_analyses,
}


def _ollama_metrics(data: dict[str, Any]) -> LDAIMetrics:
    prompt = int(data.get("prompt_eval_count") or 0)
    completion = int(data.get("eval_count") or 0)
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=prompt + completion,
            input=prompt,
            output=completion,
        ),
    )


def _ollama_chat(
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Non-streaming Ollama /api/chat with tools (OpenAI-compatible shape)."""
    import urllib.error
    import urllib.request

    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama request failed ({host}, model={model}): HTTP {exc.code} {detail}. "
            f"Is Ollama running, and does `ollama list` include {model}?"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama request failed ({host}, model={model}): {exc}. "
            "Is the Ollama daemon running?"
        ) from exc


def _anthropic_metrics(response: Any) -> LDAIMetrics:
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
    return LDAIMetrics(
        success=True,
        tokens=TokenUsage(
            total=input_tokens + output_tokens,
            input=input_tokens,
            output=output_tokens,
        ),
    )


def _anthropic_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "") or ""))
    return "".join(parts)


def _chunk_yield(text: str, metrics: Metrics, started: float) -> Iterator[dict[str, Any]]:
    if not text:
        metrics.finish_reason = "stop"
        return
    metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
    size = 24
    for i in range(0, len(text), size):
        yield {"type": "token", "text": text[i : i + size]}
    metrics.finish_reason = "stop"


def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None,
) -> Iterator[dict[str, Any]]:
    """Evaluate config, run Anthropic tool loop, stream final briefing tokens."""
    stories_text = stories_as_prompt_text(ticker_results)
    started = time.perf_counter()
    metrics = _empty_metrics()
    input_sections = prompt_display_sections(stories_text)

    try:
        config = evaluate_completion(persona, stories_text)
    except Exception as exc:  # noqa: BLE001
        baseline_msgs = [
            {"role": "system", "content": baseline_system_prompt()},
            {"role": "user", "content": baseline_user_template()},
        ]
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": stories_text,
            "inputSections": input_sections,
            "provider": "anthropic",
            "model": default_anthropic_model() + " (code baseline)",
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
                provider="anthropic",
                model=default_anthropic_model() + " (code baseline)",
                messages=baseline_msgs,
                served_meta=None,
                enabled=False,
            ),
        }
        yield {
            "type": "status",
            "message": f"LaunchDarkly evaluation failed ({exc}); using code baseline.",
        }
        yield {
            "type": "error",
            "message": "Tool loop requires a live AgentControl config. "
            f"Provision with rest/create-tools.sh && rest/create-config.sh. ({exc})",
        }
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    if not config.enabled:
        baseline_msgs = [
            {"role": "system", "content": baseline_system_prompt()},
            {"role": "user", "content": baseline_user_template()},
        ]
        yield {
            "type": "meta",
            "persona": asdict(persona),
            "input": stories_text,
            "inputSections": input_sections,
            "provider": "anthropic",
            "model": default_anthropic_model() + " (code baseline)",
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
                provider="anthropic",
                model=default_anthropic_model() + " (code baseline)",
                messages=baseline_msgs,
                served_meta=None,
                enabled=False,
            ),
        }
        yield {
            "type": "status",
            "message": f"AgentControl config '{config_key()}' is off; tools path disabled.",
        }
        yield {
            "type": "error",
            "message": "Enable the AgentControl config and attach Library tools to generate.",
        }
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    ld_model = (
        config.model.name if config.model and config.model.name else default_anthropic_model()
    )
    provider, model_name = persona_model_name(persona, ld_model)

    messages = _messages_as_dicts(config)
    anthropic_tools = _ld_tools_to_anthropic(config)
    openai_tools = _ld_tools_to_openai(config)
    tool_names = [t["name"] for t in anthropic_tools]
    tracker = config.create_tracker()

    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": _user_message_text(messages) or stories_text,
        "inputSections": input_sections,
        "provider": provider,
        "model": model_name,
        "mode": "launchdarkly",
        "configKey": config_key(),
        "fallback": False,
        "stories": ticker_results or [],
        "tools": tool_names,
        "tracked": True,
        "ldTransaction": build_ld_transaction(
            persona=persona,
            stories_text=stories_text,
            config_key_value=config_key(),
            fallback=False,
            mode="launchdarkly",
            provider=provider,
            model=model_name,
            messages=messages,
            served_meta=None,
            enabled=True,
        ),
    }

    if not tool_names:
        yield {
            "type": "status",
            "message": "No tools attached on this variation. Run rest/attach-tools.sh.",
        }

    system = ""
    chat: list[dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "system":
            system = (system + "\n\n" if system else "") + msg["content"]
        else:
            chat.append({"role": msg["role"], "content": msg["content"]})

    final_text = ""
    tool_call_index = 0
    try:
        if provider == "ollama":
            ollama_messages: list[dict[str, Any]] = []
            # LaunchDarkly system messages + local-model suffix for reliable tool use.
            ollama_system = (
                f"{system}\n\n{OLLAMA_TOOL_SUFFIX}".strip() if system else OLLAMA_TOOL_SUFFIX
            )
            if ollama_system:
                ollama_messages.append({"role": "system", "content": ollama_system})
            ollama_messages.extend(chat)

            analyze_results: list[dict[str, Any]] = []
            called_tools: list[str] = []
            nudged_for_tools = False

            for step in range(MAX_TOOL_STEPS):
                data = tracker.track_metrics_of(
                    _ollama_metrics,
                    lambda msgs=ollama_messages: _ollama_chat(
                        model_name, msgs, openai_tools
                    ),
                )
                metrics.prompt_tokens = (metrics.prompt_tokens or 0) + int(
                    data.get("prompt_eval_count") or 0
                )
                metrics.completion_tokens = (metrics.completion_tokens or 0) + int(
                    data.get("eval_count") or 0
                )
                metrics.total_tokens = (metrics.prompt_tokens or 0) + (
                    metrics.completion_tokens or 0
                )
                message = data.get("message") or {}
                tool_calls = message.get("tool_calls") or []
                content = str(message.get("content") or "")
                if not tool_calls:
                    # Small models sometimes skip tools entirely — nudge once.
                    if (
                        not nudged_for_tools
                        and tool_names
                        and not analyze_results
                        and step < MAX_TOOL_STEPS - 1
                    ):
                        nudged_for_tools = True
                        yield {
                            "type": "status",
                            "message": (
                                f"{persona.name} skipped tools on the first turn — nudging once "
                                "to run analyze → analyze → compare."
                            ),
                        }
                        ollama_messages.append(message)
                        ollama_messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Stop writing the briefing. Call tools now: "
                                    f"{TOOL_ANALYZE} once per ticker, then "
                                    f"{TOOL_COMPARE} with the exact analyze JSON results, "
                                    "then write the briefing."
                                ),
                            }
                        )
                        continue

                    final_text = content
                    break

                ollama_messages.append(message)
                for call in _sort_ollama_tool_calls(
                    [c for c in tool_calls if isinstance(c, dict)]
                ):
                    fn = call.get("function") if isinstance(call, dict) else None
                    if not isinstance(fn, dict):
                        continue
                    name = str(fn.get("name") or "")
                    raw_input = fn.get("arguments")
                    if isinstance(raw_input, str):
                        try:
                            raw_input = json.loads(raw_input)
                        except json.JSONDecodeError:
                            raw_input = {}
                    if not isinstance(raw_input, dict):
                        raw_input = {}

                    if name == TOOL_COMPARE:
                        raw_input, rewritten = _normalize_compare_args(
                            raw_input, analyze_results
                        )
                        if rewritten:
                            yield {
                                "type": "status",
                                "message": (
                                    "Rewrote compare args from prior analyze results "
                                    "(local model invented or parallel-called compare)."
                                ),
                            }

                    result = _dispatch_tool(name, raw_input)
                    tracker.track_tool_call(name)
                    called_tools.append(name)
                    if name == TOOL_ANALYZE and _looks_like_analyze_result(result):
                        analyze_results.append(result)
                    tool_call_index += 1
                    yield {
                        "type": "tool",
                        "name": name,
                        "args": raw_input,
                        "result": result,
                        "callIndex": tool_call_index,
                        "round": step + 1,
                    }
                    ollama_messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(result),
                        }
                    )
            else:
                yield {
                    "type": "status",
                    "message": f"Hit MAX_TOOL_STEPS={MAX_TOOL_STEPS}; using last model text if any.",
                }
                final_text = final_text or "(No final text after tool loop.)"

            # Guardrail: if the local model analyzed twice but never compared, run compare once.
            if (
                TOOL_COMPARE not in called_tools
                and len(analyze_results) >= 2
                and tool_names
            ):
                yield {
                    "type": "status",
                    "message": (
                        f"{persona.name} skipped compare-ticker-analyses — running it from prior "
                        "analyze results, then asking for a final briefing."
                    ),
                }
                compare_args = {
                    "analysis_a": analyze_results[-2],
                    "analysis_b": analyze_results[-1],
                }
                result = _dispatch_tool(TOOL_COMPARE, compare_args)
                tracker.track_tool_call(TOOL_COMPARE)
                tool_call_index += 1
                yield {
                    "type": "tool",
                    "name": TOOL_COMPARE,
                    "args": compare_args,
                    "result": result,
                    "callIndex": tool_call_index,
                    "round": "guardrail",
                }
                ollama_messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"{TOOL_COMPARE} returned:\n{json.dumps(result)}\n\n"
                            "Write the short equity briefing now using ONLY the tool "
                            "results (analyze + compare). Cite evidence titles."
                        ),
                    }
                )
                try:
                    data = tracker.track_metrics_of(
                        _ollama_metrics,
                        lambda: _ollama_chat(model_name, ollama_messages, []),
                    )
                    metrics.prompt_tokens = (metrics.prompt_tokens or 0) + int(
                        data.get("prompt_eval_count") or 0
                    )
                    metrics.completion_tokens = (metrics.completion_tokens or 0) + int(
                        data.get("eval_count") or 0
                    )
                    metrics.total_tokens = (metrics.prompt_tokens or 0) + (
                        metrics.completion_tokens or 0
                    )
                    brief = str((data.get("message") or {}).get("content") or "")
                    if brief:
                        final_text = brief
                except Exception as exc:  # noqa: BLE001 — keep prior text
                    yield {
                        "type": "status",
                        "message": f"Post-compare briefing call failed: {exc}",
                    }
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                yield {
                    "type": "error",
                    "message": (
                        "ANTHROPIC_API_KEY is required for Analyst Claude. "
                        "Switch to Analyst Llama or Analyst Gwen for local Ollama, "
                        "or export your Claude key."
                    ),
                }
                metrics.finish_reason = "error"
                metrics.latency_ms = int((time.perf_counter() - started) * 1000)
                yield {"type": "metrics", "metrics": metrics.to_dict()}
                yield {"type": "done"}
                return

            try:
                import anthropic
            except ImportError:
                yield {
                    "type": "error",
                    "message": "Package 'anthropic' is required. pip install -r requirements.txt",
                }
                metrics.finish_reason = "error"
                metrics.latency_ms = int((time.perf_counter() - started) * 1000)
                yield {"type": "metrics", "metrics": metrics.to_dict()}
                yield {"type": "done"}
                return

            client = anthropic.Anthropic(api_key=api_key)
            for step in range(MAX_TOOL_STEPS):
                def _call():
                    kwargs: dict[str, Any] = {
                        "model": model_name,
                        "max_tokens": 1024,
                        "messages": chat,
                    }
                    if system:
                        kwargs["system"] = system
                    if anthropic_tools:
                        kwargs["tools"] = anthropic_tools
                    return client.messages.create(**kwargs)

                response = tracker.track_metrics_of(_anthropic_metrics, _call)
                stop = getattr(response, "stop_reason", None)
                usage = getattr(response, "usage", None)
                if usage:
                    metrics.prompt_tokens = (metrics.prompt_tokens or 0) + int(
                        getattr(usage, "input_tokens", 0) or 0
                    )
                    metrics.completion_tokens = (metrics.completion_tokens or 0) + int(
                        getattr(usage, "output_tokens", 0) or 0
                    )
                    metrics.total_tokens = (metrics.prompt_tokens or 0) + (
                        metrics.completion_tokens or 0
                    )

                if stop != "tool_use":
                    final_text = _anthropic_text(response)
                    break

                assistant_content = []
                tool_results = []
                for block in response.content:
                    btype = getattr(block, "type", None)
                    if btype == "text":
                        assistant_content.append(
                            {"type": "text", "text": getattr(block, "text", "") or ""}
                        )
                    elif btype == "tool_use":
                        name = str(getattr(block, "name", "") or "")
                        tool_id = str(getattr(block, "id", "") or "")
                        raw_input = getattr(block, "input", None) or {}
                        if not isinstance(raw_input, dict):
                            raw_input = {}
                        result = _dispatch_tool(name, raw_input)
                        tracker.track_tool_call(name)
                        tool_call_index += 1
                        yield {
                            "type": "tool",
                            "name": name,
                            "args": raw_input,
                            "result": result,
                            "callIndex": tool_call_index,
                            "round": step + 1,
                        }
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tool_id,
                                "name": name,
                                "input": raw_input,
                            }
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": json.dumps(result),
                            }
                        )
                chat.append({"role": "assistant", "content": assistant_content})
                chat.append({"role": "user", "content": tool_results})
            else:
                yield {
                    "type": "status",
                    "message": f"Hit MAX_TOOL_STEPS={MAX_TOOL_STEPS}; using last model text if any.",
                }
                final_text = final_text or "(No final text after tool loop.)"
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    yield from _chunk_yield(final_text, metrics, started)
    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {"type": "done"}
