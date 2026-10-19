"""
agent_core.py — capstone walk: assess → specialist → judges → tools → finalize.

LaunchDarkly insertion (read first):
  generate_stream() → agent_graph + agent_config per node
  then judge_config on the specialist draft
  then track_tool_call for each checked tool
  thumbs use the specialist tracker's resumption token
Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
Docs: https://launchdarkly.com/docs/home/agentcontrol/tools
Keywords: AgentControl · agent graphs · Library tools · judges · feedback
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import ldclient
from ldai import (
    AIAgentConfigDefault,
    AIJudgeConfigDefault,
    JudgeResult,
    LDAIClient,
    LDMessage,
    ModelConfig,
    ProviderConfig,
)
from ldai.tracker import FeedbackKind
from ldclient import Context
from ldclient.client import LDClient
from ldclient.config import Config

from yahoo_news import format_stories_for_prompt

HERE = Path(__file__).resolve().parent
MESSAGES_DIR = HERE.parent / "rest" / "messages"

DEFAULT_GRAPH_KEY = "equity-briefing-capstone"
NODE_DEFAULTS = {
    "assess": "equity-briefing-capstone-assess",
    "report": "equity-briefing-capstone-report",
    "questions": "equity-briefing-capstone-questions",
    "good": "equity-briefing-capstone-good",
    "finalize": "equity-briefing-capstone-finalize",
}
TOOL_ORDER = ["pig-latin", "rot13", "joke-tagline"]
VALID_SPECIALISTS = {"report", "questions", "good"}
HUMOR_LEVEL = {
    "conservative-charlie": 25,
    "anonymous-amelia": 50,
    "thoughtless-toby": 90,
}
ENGLISH_WORDS = set(
    "the and for that this with from have are was were not but its has will can you your "
    "their they been into over after more than also about would could should which there "
    "these those them then when what where while stock stocks market shares price prices "
    "growth revenue earnings company companies investor investors today according said says".split()
)
JOKES = {
    "en": {
        "conservative-charlie": "The market can stay irrational longer than a footnote.",
        "anonymous-amelia": "Diversification is the joke that still pays rent.",
        "thoughtless-toby": "Buy high, sell higher, and call the difference research.",
    },
    "es": {
        "conservative-charlie": "El mercado puede seguir irracional más que una nota al pie.",
        "anonymous-amelia": "Diversificar es el chiste que igual paga el alquiler.",
        "thoughtless-toby": "Compra caro, vende más caro, y llama investigación a la diferencia.",
    },
}
INSTRUCTION_FILES = {
    "assess": "assess-instructions.txt",
    "report": "report-baseline-instructions.txt",
    "questions": "questions-instructions.txt",
    "good": "good-instructions.txt",
    "finalize": "finalize-instructions.txt",
}

_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    profile: str
    anonymous: bool


PERSONAS = [
    Persona("conservative-charlie", "Conservative Charlie", "conservative", False),
    Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", True),
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker", False),
]


def persona_by_id(persona_id: str) -> Persona | None:
    for persona in PERSONAS:
        if persona.id == persona_id:
            return persona
    return None


def graph_key() -> str:
    return os.environ.get("LD_GRAPH_KEY", "").strip() or DEFAULT_GRAPH_KEY


def node_key(role: str) -> str:
    env_name = {
        "assess": "LD_NODE_ASSESS",
        "report": "LD_NODE_REPORT",
        "questions": "LD_NODE_QUESTIONS",
        "good": "LD_NODE_GOOD",
        "finalize": "LD_NODE_FINALIZE",
    }.get(role, "")
    raw = os.environ.get(env_name, "").strip() if env_name else ""
    return raw or NODE_DEFAULTS[role]


def judge_key(which: str) -> str:
    if which == "fidelity":
        return os.environ.get("LD_JUDGE_FIDELITY_KEY", "").strip() or "equity-briefing-capstone-source-fidelity"
    return os.environ.get("LD_JUDGE_DISCIPLINE_KEY", "").strip() or "equity-briefing-capstone-recommendation-discipline"


def pass_threshold() -> float:
    raw = os.environ.get("JUDGE_PASS_THRESHOLD", "").strip()
    try:
        return float(raw) if raw else 0.65
    except ValueError:
        return 0.65


def default_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "").strip() or "llama3.2:3b"


def read_message_file(name: str) -> str:
    path = MESSAGES_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read message file {path}: {exc}") from exc


def clip(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max(0, max_len - 1)] + "…"


def init_launchdarkly() -> None:
    global _ld_client, _ai_client
    if _ai_client is not None:
        return
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key before starting the capstone."
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


def build_context(persona: Persona, action: str, locale: str) -> Context:
    """User context for graph, node, and judge evaluation. Locale selects Spanish variations."""
    builder = (
        Context.builder(persona.id)
        .name(persona.name)
        .set("action", action)
        .set("locale", "es" if locale == "es" else "en")
        .set("profile", persona.profile)
    )
    if persona.anonymous:
        builder = builder.anonymous(True)
    return builder.build()


def agent_default(instructions_file: str) -> AIAgentConfigDefault:
    return AIAgentConfigDefault(
        enabled=True,
        model=ModelConfig(name=default_ollama_model(), parameters={"temperature": 0}),
        provider=ProviderConfig(name="Custom"),
        instructions=read_message_file(instructions_file).strip(),
    )


def evaluate_agent(role: str, context: Context, variables: dict[str, Any] | None = None):
    """Evaluate one agent-mode node. LaunchDarkly: agent_config + instructions."""
    return ai_client().agent_config(
        node_key(role),
        context,
        agent_default(INSTRUCTION_FILES[role]),
        variables or {},
    )


def resolve_model(config) -> str:
    name = (config.model.name if getattr(config, "model", None) else "") or ""
    return name or default_ollama_model()


def config_summary(config, key: str) -> dict[str, Any]:
    """Summarize one served AgentControl config for the LD Details drawer."""
    meta = getattr(config, "_ld_meta", None) or {}
    if not isinstance(meta, dict):
        meta = {
            "variationKey": getattr(meta, "variation_key", None) or getattr(config, "variation_key", None),
            "version": getattr(meta, "version", None) or getattr(config, "version", None),
            "modelKey": getattr(meta, "model_key", None),
        }
    provider = getattr(getattr(config, "provider", None), "name", None)
    return {
        "key": key,
        "enabled": bool(getattr(config, "enabled", False)),
        "variationKey": meta.get("variationKey") or getattr(config, "variation_key", None),
        "version": meta.get("version") if meta.get("version") is not None else getattr(config, "version", None),
        "modelKey": meta.get("modelKey"),
        "provider": provider,
        "model": resolve_model(config),
    }


def build_ld_transaction(
    *,
    persona: Persona,
    action: str,
    locale: str,
    stories_text: str,
    tools: list[str],
    graph: Any,
    specialist: str,
    assess_cfg: Any,
    spec_cfg: Any,
    fin_cfg: Any,
    judges: list[dict[str, Any]],
    transformed: str,
) -> dict[str, Any]:
    graph_config = graph.get_config() if graph is not None and hasattr(graph, "get_config") else None
    meta = getattr(graph_config, "_ld_meta", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    return {
        "sent": {
            "graphKey": graph_key(),
            "context": build_context(persona, action, locale).to_dict(),
            "variables": {
                "action": action,
                "locale": locale,
                "stories": stories_text,
                "selectedTools": tools,
            },
            "requestedPath": [node_key("assess"), node_key(specialist), node_key("finalize")],
            "sdkDefault": {
                "enabled": True,
                "provider": "Custom",
                "model": default_ollama_model(),
                "description": "Capstone graph fallback: assess → specialist → finalize.",
            },
        },
        "received": {
            "graph": {
                "key": graph_key(),
                "enabled": bool(getattr(graph, "enabled", False)),
                "variationKey": meta.get("variationKey") or getattr(graph_config, "variation_key", None),
                "version": meta.get("version", getattr(graph_config, "version", None)),
            },
            "route": specialist,
            "path": [node_key("assess"), node_key(specialist), node_key("finalize")],
            "nodes": [
                config_summary(assess_cfg, node_key("assess")),
                config_summary(spec_cfg, node_key(specialist)),
                config_summary(fin_cfg, node_key("finalize")),
            ],
            "tools": tools,
            "judges": judges,
            "transformedDraft": transformed,
        },
    }


def ollama_complete(model: str, messages: list[dict[str, str]]) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    body = json.dumps(
        {"model": model, "messages": messages, "stream": False, "options": {"temperature": 0}}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{host}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama request failed (HTTP {exc.code} {detail}).") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed ({exc.reason}). Is Ollama running with {model}?") from exc
    return str(((payload.get("message") or {}).get("content")) or "")


def parse_assess(raw: str, action_hint: str) -> tuple[str, str]:
    match = re.search(r"\{[\s\S]*\}", raw or "")
    if match:
        try:
            data = json.loads(match.group(0))
            cand = str((data or {}).get("specialist") or "").strip().lower()
            reason = str((data or {}).get("reason") or "assess").strip() or "assess"
            if cand in VALID_SPECIALISTS:
                return cand, reason
        except json.JSONDecodeError:
            pass
    if action_hint in VALID_SPECIALISTS:
        return action_hint, "assess parse failed; used the action"
    return "report", "assess parse failed; fall through to report"


def outgoing_targets(graph: Any, source_key: str) -> list[str]:
    if graph is None or not getattr(graph, "enabled", False):
        return []
    get_node = getattr(graph, "get_node", None)
    if not callable(get_node):
        return []
    node = get_node(source_key)
    if node is None:
        return []
    edges = node.get_edges() if hasattr(node, "get_edges") else []
    out: list[str] = []
    for edge in edges or []:
        target = getattr(edge, "target_config", None) or getattr(edge, "key", None) or ""
        if target:
            out.append(str(target))
    return out


def to_pig_latin(text: str) -> str:
    def convert(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()
        if re.match(r"^[aeiou]", lower):
            converted = f"{lower}yay"
        else:
            split = re.match(r"^([^aeiouy]+)(.*)$", lower)
            converted = f"{split.group(2)}{split.group(1)}ay" if split and split.group(2) else f"{lower}ay"
        if word[0].isupper():
            converted = converted[0].upper() + converted[1:]
        return converted

    return re.sub(r"[A-Za-z]+", convert, text or "")


def to_rot13(text: str) -> str:
    def convert(ch: str) -> str:
        if "A" <= ch <= "Z":
            return chr((ord(ch) - 65 + 13) % 26 + 65)
        if "a" <= ch <= "z":
            return chr((ord(ch) - 97 + 13) % 26 + 97)
        return ch

    return "".join(convert(ch) for ch in (text or ""))


def apply_tool(key: str, text: str, persona: Persona, locale: str) -> str:
    if key == "pig-latin":
        return to_pig_latin(text)
    if key == "rot13":
        return to_rot13(text)
    pack = JOKES.get(locale) or JOKES["en"]
    line = pack.get(persona.id) or pack["anonymous-amelia"]
    return f"{(text or '').rstrip()}\n\nTagline: {line}"


def finalize_tool_line(tools: list[str]) -> str:
    ran = set(tools)
    return "\n".join(
        [
            f"Pig Latin: {'applied — keep it' if 'pig-latin' in ran else 'NOT applied — do not convert any words to Pig Latin'}.",
            (
                "ROT13: applied — the draft is already ROT13. Copy every letter. Do not decode it."
                if "rot13" in ran
                else "ROT13: NOT applied — do not encode any text."
            ),
            (
                "Joke tagline: applied — keep the Tagline line exactly as written."
                if "joke-tagline" in ran
                else "Joke tagline: NOT applied — do not add a tagline."
            ),
        ]
    )


def pig_latin_ratio(text: str) -> float:
    words = re.findall(r"[A-Za-z]{3,}", text or "")
    if not words:
        return 0.0
    return sum(1 for word in words if re.search(r"[a-z]ay$", word, re.I)) / len(words)


def english_score(text: str) -> float:
    words = re.findall(r"[a-z]{3,}", (text or "").lower())
    if not words:
        return 0.0
    return sum(1 for word in words if word in ENGLISH_WORDS) / len(words)


def cipher_ran(tools: list[str]) -> bool:
    ran = set(tools)
    return "rot13" in ran or "pig-latin" in ran


def guard_finalize(final_text: str, transformed: str, tools: list[str]) -> tuple[str, list[str]]:
    """Keep app-run tools authoritative. Finalize may polish, not invent a cipher."""
    ran = set(tools)
    notes: list[str] = []
    text = (final_text or "").strip()
    if not text:
        return transformed, ["finalize returned nothing; kept tool output"]
    if "rot13" in ran and english_score(text) - english_score(transformed) > 0.08:
        return transformed, ["finalize decoded ROT13; kept tool output"]
    if "pig-latin" in ran and pig_latin_ratio(transformed) - pig_latin_ratio(text) > 0.15:
        return transformed, ["finalize removed Pig Latin; kept tool output"]
    if "pig-latin" not in ran and pig_latin_ratio(text) - pig_latin_ratio(transformed) > 0.15:
        return transformed, ["finalize added Pig Latin that was not checked; kept tool output"]
    if "rot13" not in ran and english_score(to_rot13(text)) - english_score(text) > 0.08:
        return transformed, ["finalize added ROT13 that was not checked; kept tool output"]
    if "joke-tagline" in ran:
        match = re.search(r"^Tagline: .*$", transformed or "", re.M)
        tagline = match.group(0) if match else ""
        if tagline and tagline not in text:
            text = re.sub(r"\n*^Tagline:.*$", "", text, flags=re.M).rstrip() + f"\n\n{tagline}"
            notes.append("finalize changed the tagline; restored the tool's tagline")
    elif re.search(r"^Tagline:", text, re.M) and not re.search(r"^Tagline:", transformed or "", re.M):
        text = re.sub(r"\n*^Tagline:.*$", "", text, flags=re.M).rstrip()
        notes.append("finalize added a tagline that was not checked; removed it")
    return text, notes


def language_line(locale: str) -> str:
    return "Write the answer in Spanish." if locale == "es" else "Write the answer in English."


def finalize_user(locale: str, specialist: str, tools: list[str], transformed: str) -> str:
    lang = (
        "A cipher already ran. Copy the draft's wording. Do not translate it back to plain language."
        if cipher_ran(tools)
        else language_line(locale)
    )
    return (
        f"{lang}\nSpecialist: {specialist}\n\nTOOLS THAT RAN:\n{finalize_tool_line(tools)}\n\n"
        f"DRAFT:\n{transformed}\n\nReturn the final text only."
    )


def run_one_judge(key: str, persona: Persona, locale: str, input_text: str, output_text: str) -> dict[str, Any]:
    """Score the specialist draft. LaunchDarkly: judge_config, then a local Ollama JSON call."""
    metric_default = (
        "$ld:ai:judge:capstone-source-fidelity"
        if "fidelity" in key
        else "$ld:ai:judge:capstone-recommendation-discipline"
    )
    system_file = (
        "judge-source-fidelity-system.txt" if "fidelity" in key else "judge-recommendation-discipline-system.txt"
    )
    try:
        config = ai_client().judge_config(
            key,
            build_context(persona, "judge", locale),
            AIJudgeConfigDefault(
                enabled=True,
                model=ModelConfig(name=default_ollama_model(), parameters={"temperature": 0}),
                provider=ProviderConfig(name="Custom"),
                messages=[LDMessage(role="system", content=read_message_file(system_file).strip())],
                evaluation_metric_key=metric_default,
            ),
        )
        model = resolve_model(config)
        system = read_message_file(system_file).strip()
        raw = ollama_complete(
            model,
            [
                {"role": "system", "content": f'{system}\n\nRespond with JSON: {{"score":0.0,"reasoning":"..."}}'},
                {"role": "user", "content": f"MESSAGE HISTORY:\n{input_text}\n\nRESPONSE TO EVALUATE:\n{output_text}"},
            ],
        )
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise RuntimeError("Judge reply was not JSON.")
        parsed = json.loads(match.group(0))
        score = parsed.get("score")
        ok = isinstance(score, (int, float)) and not isinstance(score, bool)
        tracker = None
        try:
            tracker = config.create_tracker()
        except Exception:
            tracker = getattr(config, "tracker", None)
        if tracker is not None and hasattr(tracker, "track_judge_result"):
            tracker.track_judge_result(
                JudgeResult(
                    judge_config_key=key,
                    success=ok,
                    sampled=True,
                    metric_key=getattr(config, "evaluation_metric_key", None) or metric_default,
                    score=float(score) if ok else None,
                    reasoning=str(parsed.get("reasoning") or "") or None,
                )
            )
        return {
            "key": key,
            "success": ok,
            "score": float(score) if ok else None,
            "reasoning": str(parsed.get("reasoning") or ""),
            "passed": bool(ok and float(score) >= pass_threshold()),
            "threshold": pass_threshold(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "key": key,
            "success": False,
            "score": None,
            "reasoning": "",
            "passed": False,
            "error": str(exc),
            "threshold": pass_threshold(),
        }


def generate_stream(
    persona: Persona,
    action: str,
    ticker_results: list[dict[str, Any]] | None,
    selected_tools: list[str] | None,
    locale: str,
) -> Iterator[dict[str, Any]]:
    action = action if action in VALID_SPECIALISTS else "report"
    locale = "es" if locale == "es" else "en"
    wanted = {str(item) for item in (selected_tools or [])}
    tools = [key for key in TOOL_ORDER if key in wanted]
    blocks = ticker_results if isinstance(ticker_results, list) else []
    stories_text = format_stories_for_prompt(blocks)
    has_stories = any((block.get("stories") or []) for block in blocks if isinstance(block, dict))
    if not has_stories:
        yield {"type": "error", "message": "Load stories first, then generate."}
        yield {"type": "done"}
        return

    context = build_context(persona, action, locale)
    try:
        # Agent graphs — https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
        graph = ai_client().agent_graph(graph_key(), context)
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": f"agent_graph failed: {exc}"}
        yield {"type": "done"}
        return
    try:
        graph_tracker = graph.create_tracker()
    except Exception:  # noqa: BLE001
        graph_tracker = None
    yield {
        "type": "run",
        "action": action,
        "locale": locale,
        "personaId": persona.id,
        "personaName": persona.name,
        "graphKey": graph_key(),
        "tools": tools,
    }

    yield {"type": "status", "message": "assess"}
    assess_cfg = evaluate_agent("assess", context, {"action": action, "locale": locale, "stories": stories_text})
    assess_raw = ollama_complete(
        resolve_model(assess_cfg),
        [
            {"role": "system", "content": getattr(assess_cfg, "instructions", None) or ""},
            {
                "role": "user",
                "content": f"UI action hint: {action}\n{language_line(locale)}\n\nHEADLINES:\n{stories_text}\n\nReturn JSON only.",
            },
        ],
    )
    specialist, reason = parse_assess(assess_raw, action)
    if specialist != action:
        specialist = action
        reason = f"{reason} (using the action)"
    assess_targets = outgoing_targets(graph, node_key("assess"))
    edge_ok = (not getattr(graph, "enabled", False)) or node_key(specialist) in assess_targets
    if getattr(graph, "enabled", False) and not edge_ok:
        specialist = "report"
        reason = f"{reason}; graph edge missing, fall through to report"
    yield {"type": "node", "role": "assess", "specialist": specialist, "reason": reason, "clip": clip(f"{specialist}: {reason}")}

    yield {"type": "status", "message": specialist}
    spec_cfg = evaluate_agent(
        specialist, context, {"action": action, "locale": locale, "stories": stories_text, "specialist": specialist}
    )
    if specialist == "questions":
        spec_user = (
            f"{language_line(locale)}\n\nCANDIDATE QUESTIONS:\n{read_message_file('questions.txt')}\n\n"
            f"HEADLINES:\n{stories_text}"
        )
    else:
        spec_user = f"{language_line(locale)}\n\nHEADLINES:\n{stories_text}\n\nProduce the {specialist} output now."
    draft = ollama_complete(
        resolve_model(spec_cfg),
        [
            {"role": "system", "content": getattr(spec_cfg, "instructions", None) or ""},
            {"role": "user", "content": spec_user},
        ],
    )
    try:
        node_tracker = spec_cfg.create_tracker()
    except Exception:  # noqa: BLE001
        node_tracker = None
    resumption_token = getattr(node_tracker, "resumption_token", None) if node_tracker is not None else None
    yield {"type": "draft", "specialist": specialist, "text": draft, "clip": clip(draft), "resumptionToken": resumption_token}

    yield {"type": "status", "message": "judges"}
    judges = [
        run_one_judge(judge_key("fidelity"), persona, locale, stories_text, draft),
        run_one_judge(judge_key("discipline"), persona, locale, stories_text, draft),
    ]
    yield {"type": "judges", "results": judges, "draft": draft}

    transformed = draft
    for key in tools:
        if key == "joke-tagline":
            yield {"type": "info", "message": f"Setting humor level to {HUMOR_LEVEL.get(persona.id, 50)}%"}
        transformed = apply_tool(key, transformed, persona, locale)
        if node_tracker is not None and hasattr(node_tracker, "track_tool_call"):
            # Library tools — https://launchdarkly.com/docs/home/agentcontrol/tools
            try:
                node_tracker.track_tool_call(key)
            except Exception:  # noqa: BLE001
                pass
        yield {"type": "tool", "key": key, "text": transformed, "clip": clip(transformed)}

    finalize_targets = outgoing_targets(graph, node_key(specialist))
    if getattr(graph, "enabled", False) and node_key("finalize") not in finalize_targets:
        yield {"type": "error", "message": f"Graph has no edge from {node_key(specialist)} to {node_key('finalize')}."}
        yield {"type": "done", "resumptionToken": resumption_token}
        return
    if graph_tracker is not None:
        try:
            graph_tracker.track_handoff_success(node_key(specialist), node_key("finalize"))
        except Exception:  # noqa: BLE001
            pass

    yield {"type": "status", "message": "finalize"}
    fin_cfg = evaluate_agent(
        "finalize",
        context,
        {"action": action, "locale": locale, "specialist": specialist, "draft": transformed},
    )
    raw_final = ollama_complete(
        resolve_model(fin_cfg),
        [
            {"role": "system", "content": getattr(fin_cfg, "instructions", None) or ""},
            {"role": "user", "content": finalize_user(locale, specialist, tools, transformed)},
        ],
    )
    final_text, notes = guard_finalize(raw_final, transformed, tools)
    for note in notes:
        yield {"type": "info", "message": note, "kind": "guard"}
    ld_transaction = build_ld_transaction(
        persona=persona,
        action=action,
        locale=locale,
        stories_text=stories_text,
        tools=tools,
        graph=graph,
        specialist=specialist,
        assess_cfg=assess_cfg,
        spec_cfg=spec_cfg,
        fin_cfg=fin_cfg,
        judges=judges,
        transformed=transformed,
    )
    yield {"type": "finalize", "text": final_text, "clip": clip(final_text)}
    try:
        if graph_tracker is not None:
            graph_tracker.track_path([node_key("assess"), node_key(specialist), node_key("finalize")])
            graph_tracker.track_invocation_success()
        if node_tracker is not None and hasattr(node_tracker, "track_success"):
            node_tracker.track_success()
    except Exception:  # noqa: BLE001
        pass
    yield {
        "type": "done",
        "specialist": specialist,
        "tools": tools,
        "path": [node_key("assess"), node_key(specialist), node_key("finalize")],
        "resumptionToken": resumption_token,
        "draft": draft,
        "text": final_text,
        "ldTransaction": ld_transaction,
    }


def submit_feedback(*, persona: Persona, locale: str, resumption_token: str, kind: str) -> dict[str, Any]:
    """Rebuild the specialist tracker and record thumbs.

    LaunchDarkly: create_tracker + track_feedback
    https://launchdarkly.com/docs/sdk/features/ai-metrics
    """
    token = (resumption_token or "").strip()
    if not token:
        raise RuntimeError("Generate first. Feedback attaches to the specialist draft.")
    kind_l = (kind or "").strip().lower()
    if kind_l in {"positive", "up", "+"}:
        fb = FeedbackKind.Positive
        normalized = "positive"
    elif kind_l in {"negative", "down", "-"}:
        fb = FeedbackKind.Negative
        normalized = "negative"
    else:
        raise RuntimeError("kind must be positive or negative.")
    result = ai_client().create_tracker(token, build_context(persona, "feedback", locale))
    if not getattr(result, "is_success", False):
        raise RuntimeError(getattr(result, "error", None) or "Could not rebuild the specialist tracker from the resumption token.")
    tracker = result.value
    tracker.track_feedback({"kind": fb})
    return {"ok": True, "kind": normalized}
