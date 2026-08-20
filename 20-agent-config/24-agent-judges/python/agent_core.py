"""
agent_core.py — 24-agent-judges domain logic (no HTTP here).

=============================================================================
HOW TO READ THIS FILE
=============================================================================

Same equity-briefing product as 21, plus a **runtime judge gate**:

  1. Data          Toby + Charlie personas
  2. LaunchDarkly  completion_config + create_judge / evaluate
  3. Providers     Ollama for drafts; judges via OpenAI-compatible Ollama
  4. Generation    draft → both judges → optional one Charlie rewrite
                   → re-score rewrite (display only; no second rewrite)

LaunchDarkly insertion (read first):
  generate_stream() → completion_config(...) then create_judge(...).evaluate(...)
  (again on the rewrite when the draft gate fails)
  Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
  Keywords: Judges · custom judges · create_judge · evaluate · runtime gate

Ollama note: the Python AI SDK's create_judge runner uses the OpenAI provider
package. Point OPENAI_BASE_URL at Ollama's /v1 API (see ensure_ollama_openai_env).
"""

from __future__ import annotations

import asyncio
import json
import os
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

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"

CANNED_STORIES = "No ticker stories loaded yet. Ask the user to click Get Stories."

DEFAULT_CONFIG_KEY = "equity-briefing-judged"
DEFAULT_JUDGE_FIDELITY_KEY = "equity-briefing-source-fidelity"
DEFAULT_JUDGE_DISCIPLINE_KEY = "equity-briefing-recommendation-discipline"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_PASS_THRESHOLD = 0.65


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    profile: str


PERSONAS: tuple[Persona, ...] = (
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
    Persona("conservative-charlie", "Conservative Charlie", "conservative"),
)

CHARLIE = PERSONAS[1]
TOBY = PERSONAS[0]


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


def judge_fidelity_key() -> str:
    return (
        os.environ.get("LD_JUDGE_FIDELITY_KEY", DEFAULT_JUDGE_FIDELITY_KEY).strip()
        or DEFAULT_JUDGE_FIDELITY_KEY
    )


def judge_discipline_key() -> str:
    return (
        os.environ.get("LD_JUDGE_DISCIPLINE_KEY", DEFAULT_JUDGE_DISCIPLINE_KEY).strip()
        or DEFAULT_JUDGE_DISCIPLINE_KEY
    )


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
    path = MESSAGES_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read message file {path}: {exc}") from exc


def ensure_ollama_openai_env() -> None:
    """Point the OpenAI client (used by create_judge) at local Ollama /v1.

    LaunchDarkly AI SDK judges run through openai/langchain runners — not Custom.
    Ollama's OpenAI-compatible API lets classroom demos stay fully local.
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    os.environ.setdefault("OPENAI_BASE_URL", f"{host}/v1")
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "ollama"))


# ---------------------------------------------------------------------------
# LaunchDarkly
# ---------------------------------------------------------------------------

_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


def init_launchdarkly() -> None:
    global _ld_client, _ai_client
    if _ai_client is not None:
        return

    ensure_ollama_openai_env()

    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            "environment that targets equity-briefing-judged."
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
    return Context.builder(persona.id).name(persona.name).build()


def skeptic_completion_default() -> AICompletionConfigDefault:
    return AICompletionConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_ollama_model()),
        provider=ProviderConfig(name="Custom"),
        messages=[
            LDMessage(role="system", content=_read_message_file("skeptic-system.txt").strip()),
            LDMessage(role="user", content=_read_message_file("skeptic-user.txt").strip()),
        ],
    )


def judge_default(system_file: str, metric_key: str) -> AIJudgeConfigDefault:
    # temperature=0: pin sampling so local Ollama judges bounce less run-to-run.
    return AIJudgeConfigDefault(
        enabled=True,
        model=ModelConfig(
            name=default_ollama_model(),
            parameters={"temperature": 0},
        ),
        provider=ProviderConfig(name="Custom"),
        evaluation_metric_key=metric_key,
        messages=[
            LDMessage(role="system", content=_read_message_file(system_file).strip()),
        ],
    )


def _default_metric_for_judge_key(key: str) -> str:
    """SDK default metric when the judge config is missing — must use $ld:ai:judge: prefix."""
    if "fidelity" in key:
        return "$ld:ai:judge:source-fidelity"
    if "discipline" in key:
        return "$ld:ai:judge:recommendation-discipline"
    suffix = key.replace("equity-briefing-", "") or "custom"
    return f"$ld:ai:judge:{suffix}"


def evaluate_completion(persona: Persona, stories_text: str):
    return ai_client().completion_config(
        config_key(),
        build_context(persona),
        skeptic_completion_default(),
        {"stories": stories_text},
    )


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


def resolve_runtime(config) -> tuple[str, str]:
    model = (config.model.name if config.model else "") or ""
    provider_name = (config.provider.name if config.provider else "") or ""
    pl = provider_name.strip().lower()
    if pl in {"custom", "ollama"} or ":" in model:
        return "ollama", model
    if not model:
        raise RuntimeError("AgentControl variation has no model name.")
    return "ollama", model


def judge_input_text(stories_text: str, tickers: list[str] | None = None) -> str:
    ticker_line = ""
    if tickers:
        ticker_line = f"Tickers: {', '.join(tickers)}\n\n"
    return (
        f"{ticker_line}"
        f"Task: Write a short equity briefing comparing the tickers using only "
        f"the headlines below.\n\nHEADLINES:\n{stories_text}"
    )


def extract_tickers(ticker_results: list[dict[str, Any]] | None) -> list[str]:
    if not ticker_results:
        return []
    out: list[str] = []
    for row in ticker_results:
        t = (row.get("ticker") or "").strip()
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Judges
# ---------------------------------------------------------------------------

def _run_one_judge(key: str, persona: Persona, input_text: str, output_text: str) -> dict[str, Any]:
    """Evaluate one judge (async). Prefer run_judges() so both share one event loop."""
    return asyncio.run(_eval_one_judge(key, persona, input_text, output_text))


async def _eval_one_judge(
    key: str, persona: Persona, input_text: str, output_text: str
) -> dict[str, Any]:
    # LaunchDarkly: create_judge + evaluate — runtime gate (not Monitoring-only).
    # https://launchdarkly.com/docs/sdk/ai/python
    metric = _default_metric_for_judge_key(key)
    default = judge_default(
        "judge-source-fidelity-system.txt"
        if "fidelity" in key
        else "judge-recommendation-discipline-system.txt",
        metric,
    )
    judge = ai_client().create_judge(
        key,
        build_context(persona),
        default,
        default_ai_provider="openai",
    )
    if judge is None:
        return {
            "key": key,
            "success": False,
            "error": "create_judge returned None (disabled or unsupported provider)",
            "score": None,
            "reasoning": None,
            "model": default_ollama_model(),
            "passed": False,
        }
    # Prefer the model from the evaluated judge variation (usually llama3.2:3b).
    model_name = default_ollama_model()
    try:
        cfg_model = getattr(getattr(judge, "_ai_config", None), "model", None)
        if cfg_model is not None and getattr(cfg_model, "name", None):
            model_name = cfg_model.name
    except Exception:
        pass
    result = await judge.evaluate(input_text, output_text, sampling_rate=1.0)
    score = result.score
    passed = score is not None and float(score) >= pass_threshold()
    return {
        "key": key,
        "success": bool(result.success),
        "error": result.error_message,
        "score": score,
        "reasoning": result.reasoning,
        "metricKey": result.metric_key,
        "sampled": result.sampled,
        "model": model_name,
        "passed": passed,
    }


def run_judges(persona: Persona, input_text: str, draft: str) -> list[dict[str, Any]]:
    """Run both judges in one asyncio.run so httpx clients close before the loop dies.

    Two separate asyncio.run() calls left orphaned AsyncClient.aclose() tasks and
    printed 'Event loop is closed' after a successful generate.
    """

    async def _both() -> list[dict[str, Any]]:
        return [
            await _eval_one_judge(judge_fidelity_key(), persona, input_text, draft),
            await _eval_one_judge(judge_discipline_key(), persona, input_text, draft),
        ]

    return asyncio.run(_both())


def judges_passed(results: list[dict[str, Any]]) -> bool:
    return all(bool(r.get("passed")) for r in results)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, object]]:
    """Draft → decorate → judge → optional one Charlie rewrite.

    SSE event types (in addition to 01/21):
      section — UI heading for draft / scores / rewrite
      judges  — score payload for both judges
    """
    stories_text = format_stories(ticker_results)
    tickers = extract_tickers(ticker_results)
    started = time.perf_counter()
    metrics = Metrics()
    threshold = pass_threshold()

    try:
        config = evaluate_completion(persona, stories_text)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"LaunchDarkly completion_config failed: {exc}"}
        yield {"type": "done"}
        return

    if not config.enabled:
        yield {
            "type": "error",
            "message": (
                f"AgentControl config '{config_key()}' is off / enabled=false. "
                "Run rest/create-config.sh and update targeting."
            ),
        }
        yield {"type": "done"}
        return

    try:
        provider, model = resolve_runtime(config)
        messages = messages_as_dicts(config)
        if not messages:
            raise RuntimeError("Served variation has no messages.")
        tracker = config.create_tracker()
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        yield {"type": "done"}
        return

    prompt_preview = user_message_text(messages) or stories_text
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": prompt_preview,
        "provider": provider,
        "model": model,
        "mode": "launchdarkly",
        "configKey": config_key(),
        "judgeKeys": [judge_fidelity_key(), judge_discipline_key()],
        "passThreshold": threshold,
        "stories": ticker_results or [],
    }

    yield {
        "type": "section",
        "title": f"Draft ({persona.name})",
        "kind": "draft",
    }

    draft_parts: list[str] = []
    try:
        for event in _generate_ollama(model, messages, started, metrics):
            if event.get("type") == "token":
                draft_parts.append(str(event.get("text") or ""))
            yield event
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
        if tracker is not None:
            try:
                tracker.track_error()
            except Exception:  # noqa: BLE001
                pass
        metrics.finish_reason = "error"
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    draft = "".join(draft_parts).strip()
    yield {"type": "status", "message": "Running judges (Source Fidelity + Recommendation Discipline)…"}

    j_input = judge_input_text(stories_text, tickers)
    try:
        judge_results = run_judges(persona, j_input, draft)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Judge evaluation failed: {exc}"}
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    passed = judges_passed(judge_results)
    yield {
        "type": "section",
        "title": "Judge scores",
        "kind": "judges",
    }
    yield {
        "type": "judges",
        "passed": passed,
        "threshold": threshold,
        "results": judge_results,
    }

    if passed:
        yield {
            "type": "status",
            "message": f"Both judges ≥ {threshold:.2f} — no rewrite.",
        }
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    # One rewrite max — Conservative Charlie (stronger local model).
    yield {
        "type": "status",
        "message": "Gate failed — rewriting once with Conservative Charlie…",
    }
    yield {
        "type": "section",
        "title": "Rewrite (Conservative Charlie)",
        "kind": "rewrite",
    }

    rewrite_metrics = Metrics()
    rewrite_started = time.perf_counter()
    rewrite_parts: list[str] = []
    try:
        charlie_config = evaluate_completion(CHARLIE, stories_text)
        if not charlie_config.enabled:
            raise RuntimeError("Charlie variation enabled=false; check targeting.")
        c_provider, c_model = resolve_runtime(charlie_config)
        c_messages = messages_as_dicts(charlie_config)
        c_tracker = charlie_config.create_tracker()
        yield {
            "type": "status",
            "message": f"Falling back to a different model ({c_model}).",
        }
        yield {
            "type": "rewrite_meta",
            "persona": asdict(CHARLIE),
            "provider": c_provider,
            "model": c_model,
        }
        for event in _generate_ollama(c_model, c_messages, rewrite_started, rewrite_metrics):
            if event.get("type") == "token":
                rewrite_parts.append(str(event.get("text") or ""))
            yield event
        if c_tracker is not None:
            c_tracker.track_success()
            rewrite_metrics.latency_ms = int((time.perf_counter() - rewrite_started) * 1000)
            c_tracker.track_duration(rewrite_metrics.latency_ms or 0)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Charlie rewrite failed: {exc}"}
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    rewrite = "".join(rewrite_parts).strip()
    yield {
        "type": "status",
        "message": "Re-scoring rewrite (Source Fidelity + Recommendation Discipline)…",
    }
    try:
        rewrite_judge_results = run_judges(CHARLIE, j_input, rewrite)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"Rewrite judge evaluation failed: {exc}"}
        metrics.latency_ms = int((time.perf_counter() - started) * 1000)
        yield {"type": "metrics", "metrics": metrics.to_dict()}
        yield {"type": "done"}
        return

    rewrite_passed = judges_passed(rewrite_judge_results)
    yield {
        "type": "section",
        "title": "Rewrite judge scores",
        "kind": "judges",
    }
    yield {
        "type": "judges",
        "phase": "rewrite",
        "passed": rewrite_passed,
        "threshold": threshold,
        "results": rewrite_judge_results,
    }

    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    if rewrite_passed:
        yield {
            "type": "status",
            "message": "Rewrite complete — both judges passed (one rewrite max).",
        }
    else:
        yield {
            "type": "status",
            "message": (
                "Rewrite complete — judges still below threshold "
                "(one rewrite max; no further rewrite)."
            ),
        }
    yield {"type": "done"}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _fill_token_estimates(messages: list[dict[str, str]], completion: str, metrics: Metrics) -> None:
    prompt = "".join(m.get("content") or "" for m in messages)
    metrics.prompt_tokens = estimate_tokens(prompt)
    metrics.completion_tokens = estimate_tokens(completion)
    metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)


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
        with urllib.request.urlopen(req, timeout=180) as resp:
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
            "Is Ollama running, and does the model id match `ollama list`?"
        ) from exc
