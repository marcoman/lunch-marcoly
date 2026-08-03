"""
agent_core.py — domain logic for 01-reference-agent (no HTTP here).

=============================================================================
HOW TO READ THIS FILE
=============================================================================

This module is intentionally separate from HTTP so the *same* flow can later
power a Python console app (and, eventually, other languages by porting the
ideas).

Logical layers, top to bottom:

  1. Data          Personas, shared canned input, profile instructions
  2. Config        Resolve provider mode + model labels from env vars
  3. Prompting     Build chat messages (system = profile, user = canned input)
  4. Generation    generate_stream() — the main orchestration loop
  5. Providers     Stub (default) and Ollama (optional local LLM)

Request / response contract used by the web server
--------------------------------------------------
generate_stream(persona) yields a sequence of event dicts. The HTTP layer
wraps each dict as an SSE `data:` line. Event types:

  meta     — once at start: persona, input, provider, model, mode
  token    — zero or more times: streamed text fragments
  error    — optional: human-readable failure for the Status panel
  metrics  — once near the end: latency, tokens, finish_reason, …
  done     — once at the very end: stream complete

UI flow (browser)
-----------------
  load page → GET /api/bootstrap → pick persona index 0
           → GET /api/generate?personaId=… (SSE)
           → Previous/Next/Refresh repeat generate with the same canned input

Profile vs input
----------------
  * The canned USER message is identical for every persona.
  * Only the SYSTEM / instruction text changes (conservative / neutral /
    risk-taker). That is how Charlie, Nancy, and Toby differ in v1.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Iterator

# ---------------------------------------------------------------------------
# 1. Data — fixed demo content
# ---------------------------------------------------------------------------

# Shared user prompt for every persona (v1 has exactly one canned input).
CANNED_INPUT = "Should we launch the new feature to all customers this week?"

# System-style instructions keyed by profile type.
# These are NOT LaunchDarkly-controlled in the reference app; later examples
# may replace this map with AgentControl / AI Config variations.
PROFILE_INSTRUCTIONS = {
    "conservative": (
        "You are Conservative Charlie. Prefer caution, gradual rollout, "
        "risk mitigation, and clear rollback plans. Be measured and skeptical of haste."
    ),
    "neutral": (
        "You are Neutral Nancy. Weigh pros and cons evenly. Be balanced, practical, "
        "and avoid extreme recommendations."
    ),
    "risk-taker": (
        "You are Thoughtless Toby. Favor speed and bold launches. Minimize process "
        "overhead and push for shipping quickly. Be enthusiastic and underweight risk."
    ),
}


@dataclass(frozen=True)
class Persona:
    """One selectable demo identity.

    id       Stable machine key (used in URLs / APIs).
    name     Human-readable label shown in the UI.
    profile  conservative | neutral | risk-taker — selects instructions.
    """

    id: str
    name: str
    profile: str


# Ordered list: Previous / Next wrap around this sequence.
PERSONAS: tuple[Persona, ...] = (
    Persona("conservative-charlie", "Conservative Charlie", "conservative"),
    Persona("neutral-nancy", "Neutral Nancy", "neutral"),
    Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
)


@dataclass
class Metrics:
    """Industry-standard LLM timing / usage fields for the Metrics panel.

    Values may be None when a provider does not supply them; the UI shows "—".
    """

    latency_ms: int | None = None
    ttft_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 2. Config — environment-driven provider selection (no LaunchDarkly here)
# ---------------------------------------------------------------------------

def resolve_mode() -> str:
    """Return AGENT_LLM_MODE, defaulting to stub for zero-credential demos.

    Supported today: stub, ollama.
    Reserved for later wiring: bedrock, anthropic.
    """
    mode = os.environ.get("AGENT_LLM_MODE", "stub").strip().lower()
    if mode in {"stub", "ollama", "bedrock", "anthropic"}:
        return mode
    return "stub"


def provider_label(mode: str) -> str:
    """Short provider name shown next to the model in the UI."""
    return {
        "stub": "stub",
        "ollama": "ollama",
        "bedrock": "bedrock",
        "anthropic": "anthropic",
    }.get(mode, mode)


def model_label(mode: str) -> str:
    """Model id / display name for the Provider / model panel.

    Precedence:
      1. AGENT_LLM_MODEL override (any mode)
      2. Mode-specific defaults / env vars
    """
    override = os.environ.get("AGENT_LLM_MODEL", "").strip()
    if override:
        return override
    if mode == "stub":
        return "default-no-llm"
    if mode == "ollama":
        return os.environ.get("OLLAMA_MODEL", "llama3.1:8b").strip() or "llama3.1:8b"
    if mode == "bedrock":
        return os.environ.get("AGENT_BEDROCK_MODEL_ID", "").strip() or "(unset)"
    if mode == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307").strip()
    return "(unknown)"


# ---------------------------------------------------------------------------
# 3. Prompting
# ---------------------------------------------------------------------------

def build_messages(persona: Persona) -> list[dict[str, str]]:
    """Build the chat transcript sent to real LLM providers.

    system  ← profile instructions (varies by persona)
    user    ← CANNED_INPUT (same for everyone in v1)
    """
    system = PROFILE_INSTRUCTIONS[persona.profile]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": CANNED_INPUT},
    ]


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) when usage is not returned.

    Good enough for the Metrics panel in stub / Ollama demos. Cloud providers
    should prefer real usage fields when we add them.
    """
    return max(1, len(text) // 4)


def persona_by_id(persona_id: str) -> Persona | None:
    """Look up a persona by API id, or None if unknown."""
    for persona in PERSONAS:
        if persona.id == persona_id:
            return persona
    return None


def _fill_token_estimates(persona: Persona, completion_text: str, metrics: Metrics) -> None:
    """Populate token metrics from character-length estimates."""
    metrics.prompt_tokens = estimate_tokens(
        PROFILE_INSTRUCTIONS[persona.profile] + CANNED_INPUT
    )
    metrics.completion_tokens = estimate_tokens(completion_text)
    metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)


# ---------------------------------------------------------------------------
# 4. Generation — main orchestration (what the HTTP handler consumes)
# ---------------------------------------------------------------------------

def generate_stream(persona: Persona) -> Iterator[dict[str, object]]:
    """Run one generation and yield UI events in order.

    Steps:
      1. Emit meta (so the UI can paint input / provider / model immediately).
      2. Stream tokens from the selected provider.
      3. On failure, emit error (Status panel) but still finish cleanly.
      4. Emit metrics, then done.
    """
    mode = resolve_mode()
    provider = provider_label(mode)
    model = model_label(mode)

    # Step 1 — describe the run up front.
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": CANNED_INPUT,
        "provider": provider,
        "model": model,
        "mode": mode,
    }

    started = time.perf_counter()
    metrics = Metrics()

    # Step 2 / 3 — call the provider and stream tokens (or surface an error).
    try:
        if mode == "stub":
            yield from _generate_stub(persona, started, metrics)
        elif mode == "ollama":
            yield from _generate_ollama(persona, model, started, metrics)
        else:
            # Bedrock / Anthropic are reserved: show a clear Status message.
            yield {
                "type": "error",
                "message": (
                    f"Mode '{mode}' is configured but not implemented in this reference yet. "
                    "Use AGENT_LLM_MODE=stub or ollama."
                ),
            }
            metrics.finish_reason = "error"

    except Exception as exc:  # noqa: BLE001 — show provider failures in Status
        yield {"type": "error", "message": str(exc)}
        metrics.finish_reason = "error"

    # Step 4 — always close with metrics + done so the UI can re-enable buttons.
    metrics.latency_ms = int((time.perf_counter() - started) * 1000)
    yield {"type": "metrics", "metrics": metrics.to_dict()}
    yield {"type": "done"}


def _generate_stub(
    persona: Persona, started: float, metrics: Metrics
) -> Iterator[dict[str, object]]:
    """Stub provider: stream boilerplate chunks (default-no-llm)."""
    text = _stub_response(persona)
    first = True
    for chunk in _chunk_text(text, size=12):
        if first:
            # Time to first token = first chunk leaving this generator.
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        yield {"type": "token", "text": chunk}
        # Small delay so the browser visibly streams (matches real LLMs).
        time.sleep(0.02)
    metrics.finish_reason = "stop"
    _fill_token_estimates(persona, text, metrics)


def _generate_ollama(
    persona: Persona, model: str, started: float, metrics: Metrics
) -> Iterator[dict[str, object]]:
    """Ollama provider: forward streamed tokens from the local server."""
    text_parts: list[str] = []
    first = True
    for chunk in _ollama_stream(persona, model):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        text_parts.append(chunk)
        yield {"type": "token", "text": chunk}
    metrics.finish_reason = "stop"
    _fill_token_estimates(persona, "".join(text_parts), metrics)


# ---------------------------------------------------------------------------
# 5. Providers (helpers)
# ---------------------------------------------------------------------------

def _stub_response(persona: Persona) -> str:
    """Boilerplate text for AGENT_LLM_MODE=stub (default-no-llm).

    Includes persona + profile so it is obvious the UI wiring works when
    flipping Previous / Next without a real model.
    """
    return (
        f"[stub / default-no-llm]\n"
        f"Persona: {persona.name} ({persona.profile})\n\n"
        f"Regarding: {CANNED_INPUT}\n\n"
        f"As a {persona.profile} advisor, here is a boilerplate recommendation for UI testing. "
        f"Switch AGENT_LLM_MODE to ollama (or a cloud provider) for a real model response."
    )


def _chunk_text(text: str, size: int = 12) -> Iterator[str]:
    """Split text into small pieces so stub mode can simulate streaming."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _ollama_stream(persona: Persona, model: str) -> Iterator[str]:
    """Stream tokens from a local Ollama /api/chat endpoint.

    Requires:
      OLLAMA_HOST   (default http://127.0.0.1:11434)
      OLLAMA_MODEL  (or AGENT_LLM_MODEL), and the model already pulled.

    Ollama returns NDJSON lines; each line may include a partial message.content.
    """
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    url = f"{host}/api/chat"
    payload = {
        "model": model,
        "stream": True,
        "messages": build_messages(persona),
    }
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
            f"Ollama request failed ({host}): {exc}. "
            "Is Ollama running, and is OLLAMA_MODEL pulled?"
        ) from exc
