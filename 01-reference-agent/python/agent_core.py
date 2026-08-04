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
  3. Prompting     Build chat messages (system = profile, user = stories)
  4. Generation    generate_stream() — the main orchestration loop
  5. Providers     Stub (default), Ollama (local), Bedrock (AWS cloud)
  6. News          yahoo_news.py — Yahoo Finance headlines for two tickers

Request / response contract used by the web server
--------------------------------------------------
generate_stream(persona, ticker_results=None) yields event dicts:

  meta     — once at start: persona, input, provider, model, mode, stories
  token    — zero or more times: streamed text fragments
  error    — optional: human-readable failure for the Status panel
  metrics  — once near the end: latency, tokens, finish_reason, …
  done     — once at the very end: stream complete

UI flow (browser)
-----------------
  load page → GET /api/bootstrap
           → user sets tickers → GET /api/stories (Get Stories)
           → GET /api/generate?personaId=&ticker1=&ticker2= (SSE)
           → Previous/Next/Refresh re-generate using current tickers
             (server re-fetches latest headlines for the LLM)

Profile vs input
----------------
  * The USER message is built from the two tickers' latest headlines.
  * Only the SYSTEM / instruction text changes by persona.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Iterator

from yahoo_news import format_stories_for_prompt

# ---------------------------------------------------------------------------
# 1. Data — fixed demo content
# ---------------------------------------------------------------------------

# Fallback user prompt when no stories have been loaded yet.
CANNED_INPUT = (
    "No ticker stories loaded yet. Ask the user to click Get Stories, "
    "then produce a brief placeholder note that you are waiting for headlines."
)

# System-style instructions keyed by profile type.
# These are NOT LaunchDarkly-controlled in the reference app; later examples
# may replace this map with AgentControl / AI Config variations.
PROFILE_INSTRUCTIONS = {
    "conservative": (
        "You are Conservative Charlie, a cautious market analyst writing short "
        "report prose. Prefer caution, risk flags, and measured language. "
        "Base claims only on the supplied headlines."
    ),
    "neutral": (
        "You are Neutral Nancy, a balanced market analyst writing short report "
        "prose. Weigh both sides evenly and stay practical. "
        "Base claims only on the supplied headlines."
    ),
    "risk-taker": (
        "You are Thoughtless Toby, an aggressive market commentator writing "
        "short report prose. Favor bold opportunity language and speed. "
        "Base claims only on the supplied headlines."
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

# Sensible Bedrock defaults when env vars are incomplete.
# Override with AGENT_BEDROCK_MODEL_ID / AGENT_LLM_MODEL, AWS_REGION, AWS_PROFILE.
#
# Recommended text/report models (verified with Administrator profile):
#   us.amazon.nova-lite-v1:0                         — Nova Lite
#   us.anthropic.claude-haiku-4-5-20251001-v1:0      — Claude Haiku 4.5
#   qwen.qwen3-32b-v1:0                              — Qwen3 32B (general, not Coder)
DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-lite-v1:0"
DEFAULT_AWS_REGION = "us-east-1"
# Named profile in ~/.aws/credentials (includes aws_session_token for STS).
DEFAULT_AWS_PROFILE = "Administrator"

# Curated ids for prose / report generation (not coding-specialized).
REPORT_MODEL_IDS = (
    "us.amazon.nova-lite-v1:0",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "qwen.qwen3-32b-v1:0",
)


def resolve_mode() -> str:
    """Return AGENT_LLM_MODE, defaulting to stub for zero-credential demos.

    Supported today: stub, ollama, bedrock.
    Reserved for later wiring: anthropic (direct Messages API).
    """
    mode = os.environ.get("AGENT_LLM_MODE", "stub").strip().lower()
    if mode in {"stub", "ollama", "bedrock", "anthropic"}:
        return mode
    return "stub"


def resolve_aws_region() -> str:
    """Region for the Bedrock Runtime client.

    Precedence: AWS_REGION → AWS_DEFAULT_REGION → us-east-1.
    """
    return (
        os.environ.get("AWS_REGION", "").strip()
        or os.environ.get("AWS_DEFAULT_REGION", "").strip()
        or DEFAULT_AWS_REGION
    )


def resolve_aws_profile() -> str:
    """AWS shared-config / SSO profile used for Bedrock.

    Precedence: AWS_PROFILE → DEFAULT_AWS_PROFILE ("Administrator").

    Expected local setup:
      aws sso login --profile Administrator
      # profile defined in ~/.aws/config under [profile Administrator]
    """
    return os.environ.get("AWS_PROFILE", "").strip() or DEFAULT_AWS_PROFILE


def _bedrock_runtime_client(region: str):
    """Return a bedrock-runtime client authenticated via the named profile.

    Ambient AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN from
    the shell (e.g. ~/.zshrc) normally override AWS_PROFILE. For this demo we
    temporarily clear those so the SSO profile in ~/.aws/config is used.
    """
    import boto3

    profile = resolve_aws_profile()
    cleared: dict[str, str] = {}
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
    ):
        if key in os.environ:
            cleared[key] = os.environ.pop(key)

    previous_profile = os.environ.get("AWS_PROFILE")
    os.environ["AWS_PROFILE"] = profile
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.client("bedrock-runtime")
    finally:
        os.environ.update(cleared)
        if previous_profile is None:
            os.environ.pop("AWS_PROFILE", None)
        else:
            os.environ["AWS_PROFILE"] = previous_profile


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
        return (
            os.environ.get("AGENT_BEDROCK_MODEL_ID", "").strip()
            or DEFAULT_BEDROCK_MODEL_ID
        )
    if mode == "anthropic":
        return os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307").strip()
    return "(unknown)"


# ---------------------------------------------------------------------------
# 3. Prompting
# ---------------------------------------------------------------------------

def build_user_input(ticker_results: list[dict[str, Any]] | None) -> str:
    """Build the user message from Yahoo headlines (or a waiting placeholder)."""
    if not ticker_results:
        return CANNED_INPUT
    return format_stories_for_prompt(ticker_results)


def build_messages(
    persona: Persona, ticker_results: list[dict[str, Any]] | None = None
) -> list[dict[str, str]]:
    """Build the chat transcript sent to real LLM providers.

    system  ← profile instructions (varies by persona)
    user    ← story-based briefing prompt (same story set for every persona)
    """
    system = PROFILE_INSTRUCTIONS[persona.profile]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": build_user_input(ticker_results)},
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


def _fill_token_estimates(
    persona: Persona,
    completion_text: str,
    metrics: Metrics,
    user_input: str,
) -> None:
    """Populate token metrics from character-length estimates."""
    metrics.prompt_tokens = estimate_tokens(
        PROFILE_INSTRUCTIONS[persona.profile] + user_input
    )
    metrics.completion_tokens = estimate_tokens(completion_text)
    metrics.total_tokens = (metrics.prompt_tokens or 0) + (metrics.completion_tokens or 0)


# ---------------------------------------------------------------------------
# 4. Generation — main orchestration (what the HTTP handler consumes)
# ---------------------------------------------------------------------------

def generate_stream(
    persona: Persona,
    ticker_results: list[dict[str, Any]] | None = None,
) -> Iterator[dict[str, object]]:
    """Run one generation and yield UI events in order.

    Steps:
      1. Emit meta (persona, input text, provider/model, stories snapshot).
      2. Stream tokens from the selected provider.
      3. On failure, emit error (Status panel) but still finish cleanly.
      4. Emit metrics, then done.
    """
    mode = resolve_mode()
    provider = provider_label(mode)
    model = model_label(mode)
    user_input = build_user_input(ticker_results)

    # Step 1 — describe the run up front.
    yield {
        "type": "meta",
        "persona": asdict(persona),
        "input": user_input,
        "provider": provider,
        "model": model,
        "mode": mode,
        "stories": ticker_results or [],
    }

    started = time.perf_counter()
    metrics = Metrics()

    # Step 2 / 3 — call the provider and stream tokens (or surface an error).
    try:
        if mode == "stub":
            yield from _generate_stub(persona, started, metrics, user_input, ticker_results)
        elif mode == "ollama":
            yield from _generate_ollama(
                persona, model, started, metrics, ticker_results, user_input
            )
        elif mode == "bedrock":
            yield from _generate_bedrock(
                persona, model, started, metrics, ticker_results, user_input
            )
        else:
            # Direct Anthropic Messages API is reserved for a later pass.
            yield {
                "type": "error",
                "message": (
                    f"Mode '{mode}' is configured but not implemented in this reference yet. "
                    "Use AGENT_LLM_MODE=stub, ollama, or bedrock."
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
    persona: Persona,
    started: float,
    metrics: Metrics,
    user_input: str,
    ticker_results: list[dict[str, Any]] | None,
) -> Iterator[dict[str, object]]:
    """Stub provider: stream boilerplate chunks (default-no-llm)."""
    text = _stub_response(persona, ticker_results)
    first = True
    for chunk in _chunk_text(text, size=12):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        yield {"type": "token", "text": chunk}
        time.sleep(0.02)
    metrics.finish_reason = "stop"
    _fill_token_estimates(persona, text, metrics, user_input)


def _generate_ollama(
    persona: Persona,
    model: str,
    started: float,
    metrics: Metrics,
    ticker_results: list[dict[str, Any]] | None,
    user_input: str,
) -> Iterator[dict[str, object]]:
    """Ollama provider: forward streamed tokens from the local server."""
    text_parts: list[str] = []
    first = True
    for chunk in _ollama_stream(persona, model, ticker_results):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        text_parts.append(chunk)
        yield {"type": "token", "text": chunk}
    metrics.finish_reason = "stop"
    _fill_token_estimates(persona, "".join(text_parts), metrics, user_input)


def _generate_bedrock(
    persona: Persona,
    model: str,
    started: float,
    metrics: Metrics,
    ticker_results: list[dict[str, Any]] | None,
    user_input: str,
) -> Iterator[dict[str, object]]:
    """Bedrock provider: stream tokens via ConverseStream.

    Credentials come from AWS SSO via AWS_PROFILE (default: Administrator).
    Run `aws sso login --profile Administrator` when the session expires.
    Shell exports of AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN are ignored
    for Bedrock so the named SSO profile wins.
    """
    text_parts: list[str] = []
    first = True
    for chunk in _bedrock_stream(persona, model, metrics, ticker_results):
        if first:
            metrics.ttft_ms = int((time.perf_counter() - started) * 1000)
            first = False
        text_parts.append(chunk)
        yield {"type": "token", "text": chunk}
    if not metrics.finish_reason:
        metrics.finish_reason = "stop"
    if metrics.prompt_tokens is None or metrics.completion_tokens is None:
        _fill_token_estimates(persona, "".join(text_parts), metrics, user_input)


# ---------------------------------------------------------------------------
# 5. Providers (helpers)
# ---------------------------------------------------------------------------

def _stub_response(
    persona: Persona, ticker_results: list[dict[str, Any]] | None
) -> str:
    """Boilerplate text for AGENT_LLM_MODE=stub (default-no-llm).

    Includes persona + story titles so UI wiring is obvious without a real model.
    """
    lines = [
        "[stub / default-no-llm]",
        f"Persona: {persona.name} ({persona.profile})",
        "",
        "Headline briefing (stub):",
    ]
    if not ticker_results:
        lines.append("- (no stories loaded — click Get Stories)")
    else:
        for block in ticker_results:
            ticker = block.get("ticker") or "?"
            lines.append(f"- {ticker}:")
            stories = block.get("stories") or []
            if not stories:
                lines.append("  (no stories)")
            for story in stories:
                lines.append(f"  • {story.get('title') or '(untitled)'}")
    lines.extend(
        [
            "",
            f"As a {persona.profile} analyst, this is boilerplate report text for UI testing. "
            "Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.",
        ]
    )
    return "\n".join(lines)


def _chunk_text(text: str, size: int = 12) -> Iterator[str]:
    """Split text into small pieces so stub mode can simulate streaming."""
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _ollama_stream(
    persona: Persona,
    model: str,
    ticker_results: list[dict[str, Any]] | None,
) -> Iterator[str]:
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
        "messages": build_messages(persona, ticker_results),
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


def _map_bedrock_stop_reason(stop_reason: str | None) -> str:
    """Map Bedrock Converse stopReason values to our Metrics.finish_reason."""
    if not stop_reason:
        return "stop"
    mapping = {
        "end_turn": "stop",
        "stop_sequence": "stop",
        "max_tokens": "length",
        "content_filtered": "content_filtered",
        "guardrail_intervened": "content_filtered",
        "tool_use": "tool_use",
    }
    return mapping.get(stop_reason, stop_reason)


def _bedrock_stream(
    persona: Persona,
    model: str,
    metrics: Metrics,
    ticker_results: list[dict[str, Any]] | None,
) -> Iterator[str]:
    """Stream tokens from Amazon Bedrock Runtime ConverseStream.

    Requires (typical local setup):
      aws sso login --profile Administrator
      ~/.aws/config with [profile Administrator] (SSO session)
      AWS_PROFILE            (defaults to Administrator)
      AWS_REGION             (defaults to us-east-1)
      AGENT_BEDROCK_MODEL_ID (defaults to Nova Lite)
      boto3 installed into the repository .venv

    Prompt shape:
      system=[{text: profile instructions}]
      messages=[{role: user, content: [{text: story briefing}]}]

    Event handling:
      contentBlockDelta → yield text delta (UI streaming)
      metadata          → fill real token usage when present
      messageStop       → finish_reason
    """
    try:
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for AGENT_LLM_MODE=bedrock. "
            "From the repository root: source .venv/bin/activate && "
            "pip install -r requirements.txt"
        ) from exc

    region = resolve_aws_region()
    profile = resolve_aws_profile()
    try:
        client = _bedrock_runtime_client(region)
    except Exception as exc:  # noqa: BLE001 — surface profile/config errors in Status
        raise RuntimeError(
            f"Could not create Bedrock client (profile={profile}, region={region}): {exc}. "
            "Confirm `aws sso login --profile Administrator` and that ~/.aws/config "
            "defines [profile Administrator]."
        ) from exc

    messages = build_messages(persona, ticker_results)
    system_text = next(
        (m["content"] for m in messages if m["role"] == "system"),
        PROFILE_INSTRUCTIONS[persona.profile],
    )
    user_text = next(
        (m["content"] for m in messages if m["role"] == "user"),
        build_user_input(ticker_results),
    )
    request = {
        "modelId": model,
        "system": [{"text": system_text}],
        "messages": [
            {
                "role": "user",
                "content": [{"text": user_text}],
            }
        ],
        "inferenceConfig": {
            "maxTokens": 1024,
            "temperature": 0.5,
        },
    }

    try:
        response = client.converse_stream(**request)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            f"Bedrock ConverseStream failed "
            f"(profile={profile}, region={region}, model={model}): {exc}. "
            "Credentials may be valid while IAM still denies bedrock:InvokeModel / "
            "InvokeModelWithResponseStream — ask an admin to grant invoke on the "
            "model or inference-profile ARN for the SSO Administrator role."
        ) from exc

    stream = response.get("stream")
    if stream is None:
        raise RuntimeError("Bedrock response did not include a stream.")

    try:
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
            elif "internalServerException" in event:
                raise RuntimeError(event["internalServerException"].get("message") or event)
            elif "modelStreamErrorException" in event:
                raise RuntimeError(event["modelStreamErrorException"].get("message") or event)
            elif "validationException" in event:
                raise RuntimeError(event["validationException"].get("message") or event)
            elif "throttlingException" in event:
                raise RuntimeError(event["throttlingException"].get("message") or event)
            elif "serviceUnavailableException" in event:
                raise RuntimeError(event["serviceUnavailableException"].get("message") or event)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(
            f"Bedrock stream interrupted (profile={profile}, region={region}, model={model}): {exc}"
        ) from exc
