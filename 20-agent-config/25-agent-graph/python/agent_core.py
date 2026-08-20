"""
agent_core.py — domain logic for 25-agent-graph (no HTTP here).

=============================================================================
HOW TO READ THIS FILE
=============================================================================

Equity briefing UI with LaunchDarkly **Agent Graphs**:

  1. Data          Charlie / Amelia / Toby + humor easter egg
  2. LaunchDarkly  agent_graph + agent_config (mode=agent instructions)
  3. Providers     Local Ollama per node (LD does not call the model)
  4. Generation    assess → specialist → (optional scorers) → finalize

LaunchDarkly insertion point (read this first):
  generate_stream() → LDAIClient.agent_graph(...) then agent_config(...) per node
  Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
  Keywords: AgentControl · Agent graphs · Agents · Library tools · track_tool_call

Scorers (questions gap/ground, joke corny) are app-invoked for Trace — scores appear
in the tool *name* (e.g. score-question-gap:0.82); they do not change specialist text.

Why manual walk (not create_agent_graph):
  Automatic orchestration needs LangGraph / OpenAI Agents. Classroom Trace needs
  a visible assess → specialist → finalize path with Ollama — so we evaluate the
  graph + each node via the AI SDK, then invoke Ollama ourselves and record
  handoffs on AIGraphTracker.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import ldclient
from ldai import AIAgentConfigDefault, LDAIClient, ModelConfig, ProviderConfig
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient

from yahoo_news import format_stories_for_prompt

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"

CANNED_STORIES = "No ticker stories loaded yet. Ask the user to click Get Stories."

DEFAULT_GRAPH_KEY = "equity-briefing-graph"
DEFAULT_NODE_ASSESS = "equity-briefing-graph-assess"
DEFAULT_NODE_REPORT = "equity-briefing-graph-report"
DEFAULT_NODE_QUESTIONS = "equity-briefing-graph-questions"
DEFAULT_NODE_GOOD = "equity-briefing-graph-good"
DEFAULT_NODE_JOKE = "equity-briefing-graph-joke"
DEFAULT_NODE_FINALIZE = "equity-briefing-graph-finalize"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
# Joke path: higher temperature for more variety (not "never repeat").
DEFAULT_JOKE_TEMPERATURE = 0.95
DEFAULT_CORNY_HIGH = 0.80
DEFAULT_CORNY_LOW = 0.20

TOOL_QUESTION_GAP = "score-question-gap"
TOOL_JOKE_CORNY = "score-joke-corny"

# Soft angle hints — nudge variety without banning prior jokes.
JOKE_ANGLE_HINTS: tuple[str, ...] = (
    "bulls vs bears",
    "earnings season nerves",
    "index funds vs stock picking",
    "coffee and candlesticks",
    "diversification as a lifestyle",
    "the eternally loading chart",
    "hot takes cooling overnight",
    "FOMO meeting patience",
)

VALID_SPECIALISTS = frozenset({"report", "questions", "good", "joke"})
ACTIONS_NEEDING_STORIES = frozenset({"report", "questions", "good"})

# Humor easter egg — app code only (not an LLM message).
HUMOR_LEVEL: dict[str, int] = {
    "conservative-charlie": 25,
    "anonymous-amelia": 50,
    "thoughtless-toby": 90,
}


@dataclass(frozen=True)
class Persona:
    """Selectable demo identity — also the LaunchDarkly user context."""

    id: str
    name: str
    profile: str
    anonymous: bool = False


PERSONAS: tuple[Persona, ...] = (
    Persona("conservative-charlie", "Conservative Charlie", "conservative"),
    Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", anonymous=True),
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
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


def graph_key() -> str:
    return os.environ.get("LD_GRAPH_KEY", DEFAULT_GRAPH_KEY).strip() or DEFAULT_GRAPH_KEY


def node_key(role: str) -> str:
    defaults = {
        "assess": DEFAULT_NODE_ASSESS,
        "report": DEFAULT_NODE_REPORT,
        "questions": DEFAULT_NODE_QUESTIONS,
        "good": DEFAULT_NODE_GOOD,
        "joke": DEFAULT_NODE_JOKE,
        "finalize": DEFAULT_NODE_FINALIZE,
    }
    env_map = {
        "assess": "LD_NODE_ASSESS",
        "report": "LD_NODE_REPORT",
        "questions": "LD_NODE_QUESTIONS",
        "good": "LD_NODE_GOOD",
        "joke": "LD_NODE_JOKE",
        "finalize": "LD_NODE_FINALIZE",
    }
    env_name = env_map.get(role, "")
    if env_name:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return raw
    return defaults[role]


def default_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL


def joke_temperature() -> float:
    raw = os.environ.get("JOKE_TEMPERATURE", "").strip()
    if not raw:
        return DEFAULT_JOKE_TEMPERATURE
    try:
        return max(0.0, min(1.5, float(raw)))
    except ValueError:
        return DEFAULT_JOKE_TEMPERATURE


def corny_high_threshold() -> float:
    raw = os.environ.get("JOKE_CORNY_HIGH", "").strip()
    if not raw:
        return DEFAULT_CORNY_HIGH
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_CORNY_HIGH


def corny_low_threshold() -> float:
    raw = os.environ.get("JOKE_CORNY_LOW", "").strip()
    if not raw:
        return DEFAULT_CORNY_LOW
    try:
        return float(raw)
    except ValueError:
        return DEFAULT_CORNY_LOW


def humor_level_for(persona: Persona) -> int:
    return HUMOR_LEVEL.get(persona.id, 50)


def format_stories(ticker_results: list[dict[str, Any]] | None) -> str:
    if not ticker_results:
        return CANNED_STORIES
    return format_stories_for_prompt(ticker_results)


def load_questions_list() -> str:
    path = MESSAGES_DIR / "questions.txt"
    try:
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            lines.append(s)
        return "\n".join(f"- {q}" for q in lines)
    except OSError as exc:
        raise RuntimeError(f"Could not read questions list {path}: {exc}") from exc


def _read_message_file(name: str) -> str:
    path = MESSAGES_DIR / name
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Could not read message file {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# LaunchDarkly
# ---------------------------------------------------------------------------

_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


def init_launchdarkly() -> None:
    global _ld_client, _ai_client
    if _ai_client is not None:
        return

    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            "environment that targets equity-briefing-graph."
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


def build_context(persona: Persona, action: str) -> Context:
    """Build LD context. Anonymous Amelia: anonymous=True (fallthrough targeting)."""
    builder = Context.builder(persona.id).name(persona.name)
    if persona.anonymous:
        builder = builder.anonymous(True)
    builder = builder.set("action", action).set("profile", persona.profile)
    return builder.build()


def agent_default(instructions_file: str) -> AIAgentConfigDefault:
    return AIAgentConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_ollama_model(), parameters={"temperature": 0}),
        provider=ProviderConfig(name="Custom"),
        instructions=_read_message_file(instructions_file),
    )


def DEFAULT_INSTRUCTIONS_FILE(role: str) -> str:
    return {
        "assess": "assess-instructions.txt",
        "report": "report-baseline-instructions.txt",
        "questions": "questions-instructions.txt",
        "good": "good-instructions.txt",
        "joke": "joke-instructions.txt",
        "finalize": "finalize-instructions.txt",
    }[role]


def evaluate_agent(role: str, context: Context, variables: dict[str, Any] | None = None):
    """Evaluate one agent-mode node. LaunchDarkly: agent_config + instructions."""
    return ai_client().agent_config(
        node_key(role),
        context,
        agent_default(DEFAULT_INSTRUCTIONS_FILE(role)),
        variables or {},
    )


def resolve_runtime(config) -> tuple[str, str]:
    model = (config.model.name if config.model else "") or ""
    provider_name = (config.provider.name if config.provider else "") or ""
    pl = provider_name.strip().lower()
    if pl in {"custom", "ollama"} or ":" in model:
        return "ollama", model or default_ollama_model()
    if not model:
        return "ollama", default_ollama_model()
    return "ollama", model


def clip(text: str, max_len: int = 55) -> str:
    s = re.sub(r"\s+", " ", (text or "")).strip()
    if len(s) <= max_len:
        return s
    return s[: max(0, max_len - 1)] + "…"


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    match = re.search(r"\{[\s\S]*\}", (raw or "").strip())
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, n))


def extract_questions_from_draft(draft: str) -> list[str]:
    """Pull candidate questions from specialist text (for scoring only)."""
    out: list[str] = []
    for line in (draft or "").splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^[-*•]+\s*", "", s)
        s = re.sub(r"^\d+[.)]\s*", "", s)
        if "?" not in s:
            continue
        if len(s) < 12:
            continue
        out.append(s)
        if len(out) >= 5:
            break
    return out


def score_question_gap(question: str, headlines: str, model: str) -> dict[str, float]:
    """App-side scorer: gap + ground in [0,1]. Does not change specialist output.

    LaunchDarkly: Library tool key score-question-gap (attached for Monitoring).
    https://launchdarkly.com/docs/home/agentcontrol/tools
    """
    user = (
        "Score this follow-up question against the headlines.\n"
        "Return JSON only: "
        '{"gap":0.0,"ground":0.0}\n'
        "- gap: how poorly the headlines answer it (1.0 = large information gap).\n"
        "- ground: how well the question fits this headline domain (1.0 = on-topic).\n"
        "Use decimals in [0,1].\n\n"
        f"QUESTION:\n{question}\n\n"
        f"HEADLINES:\n{headlines}\n"
    )
    raw = _ollama_complete(
        model,
        [
            {
                "role": "system",
                "content": "You are a strict scoring tool. Output JSON only.",
            },
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )
    data = _parse_json_object(raw) or {}
    return {
        "gap": _clamp01(data.get("gap"), 0.5),
        "ground": _clamp01(data.get("ground"), 0.5),
    }


def score_joke_corny(joke: str, model: str) -> float:
    """App-side easter-egg scorer: corniness in [0,1]."""
    user = (
        "Score how corny this joke is.\n"
        'Return JSON only: {"corny":0.0}\n'
        "0.0 = dry/subtle; 1.0 = very corny dad-joke energy. Decimal in [0,1].\n\n"
        f"JOKE:\n{joke}\n"
    )
    raw = _ollama_complete(
        model,
        [
            {
                "role": "system",
                "content": "You are a whimsical scoring tool. Output JSON only.",
            },
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )
    data = _parse_json_object(raw) or {}
    return _clamp01(data.get("corny"), 0.5)


def format_tool_name_with_score(base: str, score: float) -> str:
    """Trace display: score lives in the tool name (teaching visibility)."""
    return f"{base}:{score:.2f}"


def parse_assess_json(raw: str, action_hint: str) -> tuple[str, str]:
    """Return (specialist, reason). Invalid/unknown → report."""
    specialist = action_hint if action_hint in VALID_SPECIALISTS else "report"
    reason = "fallback"
    text = (raw or "").strip()
    # Prefer a JSON object if the model wrapped it in prose/fences.
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            data = json.loads(match.group(0))
            cand = str(data.get("specialist") or "").strip().lower()
            if cand in VALID_SPECIALISTS:
                specialist = cand
            reason = str(data.get("reason") or reason).strip() or reason
            return specialist, reason
        except json.JSONDecodeError:
            pass
    if action_hint in VALID_SPECIALISTS:
        return action_hint, "assess parse failed; used UI action hint"
    return "report", "assess parse failed; fall through to report"


def _ollama_complete(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
) -> str:
    """Non-streaming completion (assess / buffer specialist)."""
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama request failed ({exc}). Is Ollama running, and does "
            f"`ollama list` include {model}?"
        ) from exc
    message = body.get("message") or {}
    return str(message.get("content") or "")


def _ollama_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.0,
) -> Iterator[str]:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message") or {}
                text = msg.get("content") or ""
                if text:
                    yield text
                if chunk.get("done"):
                    break
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama stream failed ({exc}). Is Ollama running, and does "
            f"`ollama list` include {model}?"
        ) from exc


def _messages_for_node(instructions: str, user_content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": instructions or "You are a helpful assistant."},
        {"role": "user", "content": user_content},
    ]


def generate_stream(
    persona: Persona,
    action: str,
    ticker_results: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Run assess → specialist → finalize.

    SSE event types:
      run, status, info, assess, specialist, finalize, token, metrics, error, done
    """
    action = (action or "report").strip().lower()
    if action not in VALID_SPECIALISTS:
        action = "report"

    stories_text = format_stories(ticker_results)
    has_real_stories = bool(ticker_results) and stories_text != CANNED_STORIES

    if action in ACTIONS_NEEDING_STORIES and not has_real_stories:
        yield {
            "type": "error",
            "message": "Load stories first (Get Stories), then try this action again.",
        }
        yield {"type": "done"}
        return

    started = time.time()
    metrics = Metrics()
    context = build_context(persona, action)

    # --- Graph evaluate (topology + tracker) ---------------------------------
    # LaunchDarkly: agent_graph — see docs link in module prelude.
    try:
        graph = ai_client().agent_graph(graph_key(), context)
    except Exception as exc:  # noqa: BLE001 — surface to UI
        yield {"type": "error", "message": f"LaunchDarkly agent_graph failed: {exc}"}
        yield {"type": "done"}
        return

    graph_tracker = graph.create_tracker()
    graph_enabled = bool(getattr(graph, "enabled", False))

    yield {
        "type": "run",
        "action": action,
        "personaId": persona.id,
        "personaName": persona.name,
        "graphKey": graph_key(),
        "graphEnabled": graph_enabled,
    }
    yield {
        "type": "status",
        "message": (
            f"Graph {graph_key()} "
            + ("enabled" if graph_enabled else "disabled/missing — using node configs + local walk")
        ),
    }

    path: list[str] = [node_key("assess")]

    # --- Humor easter egg (joke path only) -----------------------------------
    if action == "joke":
        level = humor_level_for(persona)
        line = f"Setting humor level to {level}%"
        yield {"type": "info", "message": line, "kind": "humor"}

    # --- Step 1: assess ------------------------------------------------------
    yield {"type": "status", "message": "assess — choosing specialist…"}
    try:
        assess_cfg = evaluate_agent(
            "assess",
            context,
            {
                "action": action,
                "stories": stories_text if has_real_stories else "(none)",
            },
        )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"assess agent_config failed: {exc}"}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    _, assess_model = resolve_runtime(assess_cfg)
    assess_user = (
        f"UI action hint: {action}\n"
        f"Headlines present: {'yes' if has_real_stories else 'no'}\n\n"
        f"HEADLINES:\n{stories_text if has_real_stories else '(none)'}\n\n"
        "Return JSON only."
    )
    try:
        assess_raw = _ollama_complete(
            assess_model,
            _messages_for_node(assess_cfg.instructions or "", assess_user),
        )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    specialist, reason = parse_assess_json(assess_raw, action)
    # Prefer UI action when valid (teaching: button intent wins if assess drifts).
    if action in VALID_SPECIALISTS and specialist != action:
        reason = f"{reason} (UI hint={action}; using hint)"
        specialist = action

    specialist_key = node_key(specialist)
    path.append(specialist_key)
    graph_tracker.track_handoff_success(node_key("assess"), specialist_key)

    yield {
        "type": "assess",
        "specialist": specialist,
        "reason": reason,
        "clip": clip(f"{specialist}: {reason}"),
        "model": assess_model,
        "configKey": node_key("assess"),
    }
    yield {
        "type": "route",
        "specialist": specialist,
        "reason": reason,
        "message": f"Selected specialist: {specialist}",
    }

    # --- Step 2: specialist --------------------------------------------------
    yield {"type": "status", "message": f"{specialist} — running specialist…"}
    variables: dict[str, Any] = {
        "action": action,
        "stories": stories_text if has_real_stories else "(none)",
        "specialist": specialist,
    }
    if specialist == "questions":
        variables["questions"] = load_questions_list()

    try:
        # report uses persona targeting on the same key; other nodes are single-variation.
        spec_cfg = evaluate_agent(specialist, context, variables)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"{specialist} agent_config failed: {exc}"}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    _, spec_model = resolve_runtime(spec_cfg)
    variation_key = str(getattr(spec_cfg, "variation_key", "") or "")

    if specialist == "questions":
        spec_user = (
            f"CANDIDATE QUESTIONS:\n{variables['questions']}\n\n"
            f"HEADLINES:\n{stories_text}\n\n"
            "Return the top 2–3 gap-priority questions with a short why each."
        )
        spec_temperature = 0.0
    elif specialist == "good":
        spec_user = (
            f"HEADLINES:\n{stories_text}\n\n"
            "Produce ## Good and ## Bad sections now (both required)."
        )
        spec_temperature = 0.0
    elif specialist == "joke":
        tickers = []
        for row in ticker_results or []:
            t = (row.get("ticker") or "").strip()
            if t:
                tickers.append(t)
        # Tickers / headlines are optional upside — joke works with none.
        extras: list[str] = []
        if tickers:
            extras.append(f"Optional tickers (use lightly if you want): {', '.join(tickers)}")
        if has_real_stories:
            extras.append(
                "Optional headlines (use lightly if you want):\n"
                + clip(stories_text, 400)
            )
        angle = random.choice(JOKE_ANGLE_HINTS)
        extras.append(
            f"Variety nudge (optional inspiration, not a script): lean toward “{angle}” "
            "or another fresh angle — prefer a different setup than the most common one."
        )
        bonus = ("\n\n" + "\n\n".join(extras)) if extras else ""
        spec_user = (
            "Tell a short market/investing joke now. "
            "Aim for variety across runs. Do not require tickers or headlines."
            f"{bonus}"
        )
        spec_temperature = joke_temperature()
        yield {
            "type": "info",
            "message": f"Joke sampling temperature={spec_temperature:.2f}; angle hint “{angle}”",
            "kind": "joke-variety",
        }
    else:
        spec_user = (
            f"HEADLINES:\n{stories_text}\n\n"
            f"Produce the {specialist} output now."
        )
        spec_temperature = 0.0

    try:
        specialist_draft = _ollama_complete(
            spec_model,
            _messages_for_node(spec_cfg.instructions or "", spec_user),
            temperature=spec_temperature,
        )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    yield {
        "type": "specialist",
        "specialist": specialist,
        "clip": clip(specialist_draft),
        "model": spec_model,
        "configKey": specialist_key,
        "variationKey": variation_key,
    }

    # --- Optional scorers (Trace visibility; outcomes unchanged) --------------
    # LaunchDarkly: Library tools + track_tool_call
    # https://launchdarkly.com/docs/home/agentcontrol/tools
    try:
        node_tracker = spec_cfg.create_tracker()
    except Exception:  # noqa: BLE001
        node_tracker = None

    if specialist == "questions":
        yield {"type": "status", "message": "Scoring questions (gap / ground)…"}
        questions = extract_questions_from_draft(specialist_draft)
        if not questions:
            yield {
                "type": "info",
                "message": "No questions parsed for scoring — Trace skips tool scores.",
                "kind": "tool",
            }
        call_index = 0
        for q in questions:
            scores = score_question_gap(q, stories_text, spec_model or default_ollama_model())
            gap = scores["gap"]
            ground = scores["ground"]
            # Score in the tool *name* so Trace teaches values along the way.
            gap_name = format_tool_name_with_score(TOOL_QUESTION_GAP, gap)
            ground_name = format_tool_name_with_score("score-question-ground", ground)
            call_index += 1
            if node_tracker is not None:
                try:
                    node_tracker.track_tool_call(TOOL_QUESTION_GAP)
                except Exception:  # noqa: BLE001
                    pass
            yield {
                "type": "tool",
                "name": gap_name,
                "toolKey": TOOL_QUESTION_GAP,
                "score": gap,
                "scores": {"gap": gap, "ground": ground},
                "args": {"question": q},
                "result": {"gap": gap, "ground": ground},
                "callIndex": call_index,
                "clip": clip(q, 40),
            }
            call_index += 1
            yield {
                "type": "tool",
                "name": ground_name,
                "toolKey": "score-question-ground",
                "score": ground,
                "args": {"question": q},
                "result": {"ground": ground},
                "callIndex": call_index,
                "clip": clip(q, 40),
            }

    elif specialist == "joke":
        yield {"type": "status", "message": "Scoring joke corniness…"}
        corny = score_joke_corny(specialist_draft, spec_model or default_ollama_model())
        corny_name = format_tool_name_with_score(TOOL_JOKE_CORNY, corny)
        if node_tracker is not None:
            try:
                node_tracker.track_tool_call(TOOL_JOKE_CORNY)
            except Exception:  # noqa: BLE001
                pass
        yield {
            "type": "tool",
            "name": corny_name,
            "toolKey": TOOL_JOKE_CORNY,
            "score": corny,
            "args": {"joke": clip(specialist_draft, 120)},
            "result": {"corny": corny},
            "callIndex": 1,
            "clip": clip(specialist_draft, 40),
        }
        high = corny_high_threshold()
        low = corny_low_threshold()
        level = humor_level_for(persona)
        if corny >= high:
            tip = (
                f"Corny {corny:.2f} ≥ {high:.2f} — recommend lowering humor setting "
                f"(currently {level}%)."
            )
            # Once only: info → Trace + status panel (do not also yield status).
            yield {"type": "info", "message": tip, "kind": "humor-tip"}
        elif corny <= low:
            tip = (
                f"Corny {corny:.2f} ≤ {low:.2f} — recommend raising humor setting "
                f"(currently {level}%)."
            )
            yield {"type": "info", "message": tip, "kind": "humor-tip"}

    finalize_key = node_key("finalize")
    path.append(finalize_key)
    graph_tracker.track_handoff_success(specialist_key, finalize_key)

    # --- Step 3: finalize (stream to Response) -------------------------------
    yield {"type": "status", "message": "finalize — polishing…"}
    try:
        fin_cfg = evaluate_agent(
            "finalize",
            context,
            {
                "action": action,
                "specialist": specialist,
                "draft": specialist_draft,
                "stories": stories_text if has_real_stories else "(none)",
            },
        )
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"finalize agent_config failed: {exc}"}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    _, fin_model = resolve_runtime(fin_cfg)
    fin_user = (
        f"Original action: {action}\n"
        f"Specialist: {specialist}\n\n"
        f"SPECIALIST DRAFT:\n{specialist_draft}\n\n"
        "Return the final polished text only."
    )

    yield {
        "type": "model",
        "provider": "ollama",
        "model": fin_model,
        "configKey": finalize_key,
        "phase": "finalize",
    }

    final_parts: list[str] = []
    first_token_at: float | None = None
    try:
        for chunk in _ollama_stream(
            fin_model,
            _messages_for_node(fin_cfg.instructions or "", fin_user),
        ):
            if first_token_at is None:
                first_token_at = time.time()
                metrics.ttft_ms = int((first_token_at - started) * 1000)
            final_parts.append(chunk)
            yield {"type": "token", "text": chunk}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        graph_tracker.track_invocation_failure()
        yield {"type": "done"}
        return

    final_text = "".join(final_parts)
    metrics.latency_ms = int((time.time() - started) * 1000)
    metrics.finish_reason = "stop"

    yield {
        "type": "finalize",
        "clip": clip(final_text),
        "model": fin_model,
        "configKey": finalize_key,
    }

    graph_tracker.track_path(path)
    graph_tracker.track_duration(metrics.latency_ms or 0)
    graph_tracker.track_invocation_success()

    # Per-node success trackers (best-effort)
    try:
        assess_cfg.create_tracker().track_success()
        if node_tracker is not None:
            node_tracker.track_success()
        else:
            spec_cfg.create_tracker().track_success()
        fin_cfg.create_tracker().track_success()
    except Exception:  # noqa: BLE001
        pass

    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {
        "type": "done",
        "path": path,
        "specialist": specialist,
        "action": action,
    }
