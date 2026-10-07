"""
agent_core.py — selected generators, one Terraform brief, then terraform validate.

=============================================================================
HOW TO READ THIS FILE
=============================================================================

  1. Data          contexts codegen-1b and codegen-3b, plus Claude when the key is set
  2. LaunchDarkly  one completion config, evaluated for every selected model
  3. Providers     Ollama or Anthropic, chosen from the served variation
  4. Files         output/<model-id>/main.tf, then terraform validate -json

LaunchDarkly insertion (read first):
  generate_stream() → LDAIClient.completion_config(...)
  then tracker.track_metrics_of(...)
  Docs: https://launchdarkly.com/docs/sdk/ai/python
  Docs: https://launchdarkly.com/docs/home/agentcontrol/quickstart
  Keywords: AgentControl · completion config · track_metrics_of · runtime variables

{{ model_name }} and {{ variation_key }} are filled by the SDK so the
ancestry comment can differ. The app does not apply the file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
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
from ldai.providers.types import JudgeResult, LDAIMetrics
from ldai.tracker import TokenUsage
from ldclient import Context
from ldclient.config import Config
from ldclient.client import LDClient

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
MESSAGES_DIR = EXAMPLE_ROOT / "rest" / "messages"
OUTPUT_ROOT = EXAMPLE_ROOT / "output"
PLUGIN_CACHE = OUTPUT_ROOT / ".plugin-cache"

DEFAULT_CONFIG_KEY = "terraform-codegen-compare"
DEFAULT_JUDGE_KEY = "terraform-codegen-judge"
DEFAULT_JUDGE_METRIC = "$ld:ai:judge:terraform-brief"
DEFAULT_JUDGE_MODEL = "claude-sonnet-5"
PASS_THRESHOLD = 0.65

# Order is the click. local-3b stays available and starts unchecked.
GENERATORS = (
    {
        "id": "local-1b",
        "context_key": "codegen-1b",
        "model_name": "llama3.2:1b",
        "variation_key": "local-1b",
        "provider": "ollama",
        "note": "inexpensive",
        "enabled": True,
    },
    {
        "id": "local-8b",
        "context_key": "codegen-8b",
        "model_name": "llama3.1:8b",
        "variation_key": "local-8b",
        "provider": "ollama",
        "note": "local ceiling",
        "enabled": True,
    },
    {
        "id": "local-3b",
        "context_key": "codegen-3b",
        "model_name": "llama3.2:3b",
        "variation_key": "local-3b",
        "provider": "ollama",
        "note": "mid",
        "enabled": False,
    },
)

# Smaller hosted model. More likely to pass validate than the local models.
HAIKU_GENERATOR = {
    "id": "claude-haiku",
    "context_key": "codegen-haiku",
    "model_name": "claude-haiku-4-5-20251001",
    "variation_key": "claude-haiku",
    "provider": "anthropic",
    "note": "smaller hosted",
    "enabled": True,
}

# Reference hosted model already used in 22. Offered when ANTHROPIC_API_KEY is set.
CLAUDE_GENERATOR = {
    "id": "claude-sonnet",
    "context_key": "codegen-sonnet",
    "model_name": "claude-sonnet-5",
    "variation_key": "claude-sonnet",
    "provider": "anthropic",
    "note": "reference",
    "enabled": True,
}

# Brief size the comparison treats as a full file.
EXPECTED_RESOURCES = 13
EXPECTED_DESCRIPTIONS = 11

_ld_client: LDClient | None = None
_ai_client: LDAIClient | None = None


def anthropic_ready() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def available_generators() -> list[dict[str, Any]]:
    rows = [dict(spec) for spec in GENERATORS]
    if anthropic_ready():
        rows.append(dict(HAIKU_GENERATOR))
        rows.append(dict(CLAUDE_GENERATOR))
    return rows


def config_key() -> str:
    key = os.environ.get("LD_AGENT_CONFIG_KEY", "").strip()
    return key or DEFAULT_CONFIG_KEY


def judge_key() -> str:
    key = os.environ.get("LD_JUDGE_KEY", "").strip()
    return key or DEFAULT_JUDGE_KEY


def pass_threshold() -> float:
    raw = os.environ.get("JUDGE_PASS_THRESHOLD", "").strip()
    if not raw:
        return PASS_THRESHOLD
    try:
        return float(raw)
    except ValueError:
        return PASS_THRESHOLD


def read_message(name: str) -> str:
    return (MESSAGES_DIR / name).read_text(encoding="utf-8")


def completion_default() -> AICompletionConfigDefault:
    """SDK default when terraform-codegen-compare is missing.

    LaunchDarkly: CompletionConfig default.
    https://launchdarkly.com/docs/sdk/ai/python
    """
    model = os.environ.get("OLLAMA_MODEL", "").strip() or "llama3.2:3b"
    return AICompletionConfigDefault(
        enabled=True,
        model=ModelConfig(name=model),
        provider=ProviderConfig(name="Custom"),
        messages=[
            LDMessage(role="system", content=read_message("system.txt").strip()),
            LDMessage(role="user", content=read_message("user.txt").strip()),
        ],
    )


def init_launchdarkly() -> None:
    """LaunchDarkly: server SDK plus the AI SDK for the completion config.

    https://launchdarkly.com/docs/sdk/ai/python
    """
    global _ld_client, _ai_client
    if _ai_client is not None:
        return
    sdk_key = os.environ.get("LD_SDK_KEY", "").strip()
    if not sdk_key:
        raise RuntimeError(
            "LD_SDK_KEY is required. Export a server-side SDK key for the "
            "environment that targets terraform-codegen-compare."
        )
    ldclient.set_config(Config(sdk_key))
    client = ldclient.get()
    deadline = time.time() + 5.0
    while time.time() < deadline and not client.is_initialized():
        time.sleep(0.05)
    if not client.is_initialized():
        raise RuntimeError(
            "LaunchDarkly client failed to initialize within 5s. "
            "Check LD_SDK_KEY and network access to LaunchDarkly."
        )
    _ld_client = client
    _ai_client = LDAIClient(client)


def ai_client() -> LDAIClient:
    if _ai_client is None:
        init_launchdarkly()
    assert _ai_client is not None
    return _ai_client


def build_context(context_key: str) -> Context:
    return Context.builder(context_key).name(context_key).build()


def messages_as_dicts(config: Any) -> list[dict[str, str]]:
    rows = []
    for message in config.messages or []:
        role = getattr(message, "role", None) or message.get("role")
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            content = message.get("content")
        role_text = str(role or "user").lower()
        if "." in role_text:
            role_text = role_text.rsplit(".", 1)[-1]
        rows.append({"role": role_text, "content": content or ""})
    return rows


def uses_anthropic(model: str) -> bool:
    return model.strip().lower().startswith("claude")


def served_model_name(config: Any) -> str:
    model = getattr(config, "model", None)
    name = getattr(model, "name", None) if model is not None else None
    if not name and isinstance(model, dict):
        name = model.get("name")
    if not name:
        raise RuntimeError("Served variation has no model name.")
    return str(name)


def folder_name(model: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", model.strip())
    return cleaned.strip("-") or "model"


def price_fields(config: Any) -> dict[str, Any]:
    """Raw price or cost parameters on the served model. No per-token math."""
    model = getattr(config, "model", None)
    blob: dict[str, Any] = {}
    if model is not None and hasattr(model, "to_dict"):
        rendered = model.to_dict() or {}
        for section in ("parameters", "custom"):
            section_value = rendered.get(section) or {}
            if isinstance(section_value, dict):
                blob.update(section_value)
    found: dict[str, Any] = {}
    for key, value in blob.items():
        if re.search(r"cost|price", str(key), re.I):
            found[str(key)] = value
    return found


def variation_key_served(context_key: str) -> str | None:
    """LaunchDarkly: variation_detail — variation key lives on _ldMeta.

    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    client = _ld_client
    if client is None:
        return None
    detail = client.variation_detail(
        config_key(),
        build_context(context_key),
        completion_default().to_dict(),
    )
    value = detail.value if isinstance(detail.value, dict) else {}
    meta = value.get("_ldMeta") or {}
    key = meta.get("variationKey")
    return str(key) if key else None


def flag_not_found(context_key: str) -> bool:
    client = _ld_client
    if client is None:
        return False
    detail = client.variation_detail(
        config_key(),
        build_context(context_key),
        completion_default().to_dict(),
    )
    reason = detail.reason if isinstance(detail.reason, dict) else {}
    kind = str(reason.get("kind") or "")
    error_kind = str(reason.get("errorKind") or reason.get("error_kind") or "")
    return kind.upper() == "ERROR" and error_kind.upper() == "FLAG_NOT_FOUND"


def ollama_chat(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload = json.dumps({"model": model, "stream": True, "messages": messages}).encode()
    request = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parts: list[str] = []
    ttft_ms: int | None = None
    input_tokens = 0
    output_tokens = 0
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("error"):
                    raise RuntimeError(str(data["error"]))
                content = ((data.get("message") or {}).get("content")) or ""
                if content:
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started) * 1000)
                    parts.append(content)
                if data.get("done"):
                    input_tokens = int(data.get("prompt_eval_count") or 0)
                    output_tokens = int(data.get("eval_count") or 0)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Ollama request failed ({host}, model={model}): HTTP {exc.code} {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Ollama request failed ({host}, model={model}): {exc.reason}"
        ) from exc
    text = "".join(parts)
    if input_tokens == 0 and output_tokens == 0:
        prompt = "".join(message["content"] for message in messages)
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(1, len(text) // 4)
    return {
        "text": text,
        "ttft_ms": ttft_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def anthropic_chat(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """Stream one Claude completion from the served variation. The key stays in the process.

    The caller wraps this in track_metrics_of so AgentControl records the run.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Package 'anthropic' is required in the repo .venv.") from exc

    system = "\n\n".join(item["content"] for item in messages if item.get("role") == "system")
    chat = [
        {"role": item["role"], "content": item["content"]}
        for item in messages
        if item.get("role") in {"user", "assistant"}
    ]
    client = anthropic.Anthropic(api_key=api_key)
    started = time.perf_counter()
    ttft_ms: int | None = None
    parts: list[str] = []
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": chat or [{"role": "user", "content": "Write main.tf."}],
    }
    if system:
        kwargs["system"] = system
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            if text and ttft_ms is None:
                ttft_ms = int((time.perf_counter() - started) * 1000)
            parts.append(text)
        final = stream.get_final_message()
    usage = getattr(final, "usage", None)
    incoming = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
    outgoing = int(getattr(usage, "output_tokens", 0) or 0) if usage else estimate_tokens("".join(parts))
    return {
        "text": "".join(parts),
        "input_tokens": incoming,
        "output_tokens": outgoing,
        "ttft_ms": ttft_ms,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }


def extract_hcl(text: str) -> str:
    fenced = re.search(r"```(?:hcl|terraform)?\s*\n(.*?)```", text, re.S | re.I)
    body = fenced.group(1) if fenced else text
    ancestry = body.find("# ancestry:")
    terraform_at = body.find("terraform ")
    start = ancestry if ancestry >= 0 else terraform_at
    if start > 0:
        body = body[start:]
    body = body.strip()
    return f"{body}\n" if body else ""


def file_stats(hcl: str) -> dict[str, Any]:
    """Counts a reader can compare even when the blocks are in a different order."""
    return {
        "lines": len(hcl.splitlines()),
        "resources": len(re.findall(r'(?m)^resource\s+"', hcl)),
        "descriptions": len(re.findall(r'(?m)^\s*description\s*=', hcl)),
        "ancestry": hcl.lstrip().startswith("# ancestry:"),
        "expected_resources": EXPECTED_RESOURCES,
        "expected_descriptions": EXPECTED_DESCRIPTIONS,
    }


def write_main_tf(model: str, hcl: str) -> Path:
    folder = OUTPUT_ROOT / folder_name(model)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "main.tf"
    path.write_text(hcl, encoding="utf-8")
    return path


def _validate_payload(stdout: str) -> dict[str, Any] | None:
    """Pull the validate JSON object out of stdout. Terraform may prefix a log line."""
    text = (stdout or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    if isinstance(parsed, dict) and ("valid" in parsed or "error_count" in parsed):
        return parsed
    return None


def terraform_validate(folder: Path) -> dict[str, Any]:
    """Run terraform init and validate. Does not apply and does not need a token."""
    binary = shutil.which("terraform")
    if binary is None:
        return {
            "ok": False,
            "phase": "missing",
            "output": "terraform is not on PATH. The file is still on disk.",
        }
    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_PLUGIN_CACHE_DIR"] = str(PLUGIN_CACHE)
    PLUGIN_CACHE.mkdir(parents=True, exist_ok=True)
    init = subprocess.run(
        [binary, "init", "-backend=false", "-input=false", "-no-color"],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    # Init can fail on duplicate blocks and still leave a JSON validate result.
    # Always ask validate for the issue count.
    result = subprocess.run(
        [binary, "validate", "-json"],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    payload = _validate_payload(result.stdout)
    init_text = (init.stdout + init.stderr).strip()
    if payload:
        error_count = int(payload.get("error_count") or 0)
        warning_count = int(payload.get("warning_count") or 0)
        lines: list[str] = []
        for item in payload.get("diagnostics") or []:
            if not isinstance(item, dict):
                continue
            severity = item.get("severity") or "error"
            summary = item.get("summary") or ""
            detail = item.get("detail") or ""
            lines.append(f"{severity}: {summary}")
            if detail:
                lines.append(str(detail))
        if not lines and payload.get("valid"):
            lines.append("Success! The configuration is valid.")
        if not lines:
            lines.append(init_text or "terraform validate returned no diagnostics.")
        return {
            "ok": bool(payload.get("valid")),
            "phase": "validate",
            "issue_count": error_count + warning_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "output": "\n".join(lines)[-8000:],
        }
    counted = len(re.findall(r"(?m)^Error:", init_text))
    return {
        "ok": False,
        "phase": "init" if init.returncode != 0 else "validate",
        "issue_count": counted,
        "error_count": counted,
        "warning_count": 0,
        "output": (init_text or (result.stdout + result.stderr).strip() or "terraform validate returned no output.")[-8000:],
    }


def metric_payload(summary: Any, prices: dict[str, Any]) -> dict[str, Any]:
    tokens = getattr(summary, "tokens", None)
    cost = prices.get("cost")
    return {
        "duration_ms": getattr(summary, "duration_ms", None),
        "time_to_first_token_ms": getattr(summary, "time_to_first_token", None),
        "input_tokens": getattr(tokens, "input", None) if tokens else None,
        "output_tokens": getattr(tokens, "output", None) if tokens else None,
        "total_tokens": getattr(tokens, "total", None) if tokens else None,
        "success": getattr(summary, "success", None),
        "cost": cost,
        "prices": prices,
    }


def generate_one(spec: dict[str, str]) -> Iterator[dict[str, Any]]:
    column = spec["id"]
    context = build_context(spec["context_key"])
    yield {
        "type": "eval",
        "column": column,
        "surface": "agent config",
        "key": config_key(),
    }
    if column == "local-1b" and flag_not_found(spec["context_key"]):
        yield {
            "type": "status",
            "column": column,
            "message": (
                f"Completion config '{config_key()}' was not found. "
                "Using the in-code prompt. Provision with rest/create-config.sh."
            ),
        }

    variables = {
        "model_name": spec["model_name"],
        "variation_key": spec["variation_key"],
    }
    # LaunchDarkly: completion_config substitutes {{ model_name }} and {{ variation_key }}.
    # https://launchdarkly.com/docs/home/agentcontrol/quickstart
    config = ai_client().completion_config(
        config_key(),
        context,
        completion_default(),
        variables,
    )
    if not config.enabled:
        yield {
            "type": "error",
            "column": column,
            "message": (
                f"AgentControl config '{config_key()}' is off for {column}. "
                "Run rest/create-config.sh."
            ),
        }
        return

    try:
        model = served_model_name(config)
        messages = messages_as_dicts(config)
        if not messages:
            raise RuntimeError("Served variation has no messages.")
        tracker = config.create_tracker()
    except Exception as exc:
        yield {"type": "error", "column": column, "message": str(exc)}
        return

    served_variation = variation_key_served(spec["context_key"])
    if served_variation != spec["variation_key"]:
        if spec.get("provider") == "anthropic" or served_variation:
            hint = {
                "local-8b": "Run rest/add-local-8b-variation.sh.",
                "claude-haiku": "Run rest/add-haiku-variation.sh.",
                "claude-sonnet": "Run rest/add-claude-variation.sh.",
            }.get(spec["id"], "Run rest/update-targeting.sh.")
            yield {
                "type": "error",
                "column": column,
                "message": (
                    f"AgentControl did not serve variation '{spec['variation_key']}' "
                    f"(served {served_variation or 'none'}). {hint}"
                ),
            }
            return
    print(
        f"[generate] {column}: variation={served_variation!r} model={model}",
        flush=True,
    )
    yield {
        "type": "meta",
        "column": column,
        "model": model,
        "variationKey": served_variation or spec["variation_key"],
        "intendedModel": spec["model_name"],
        "folder": f"output/{folder_name(model)}/main.tf",
    }
    yield {"type": "status", "column": column, "message": f"Generating {model}…"}

    captured: dict[str, Any] = {}

    def run() -> str:
        # The served variation picks the provider. Both paths sit inside track_metrics_of.
        if uses_anthropic(model):
            result = anthropic_chat(model, messages)
        else:
            result = ollama_chat(model, messages)
        captured.update(result)
        if result.get("ttft_ms") is not None:
            tracker.track_time_to_first_token(int(result["ttft_ms"]))
        return str(result.get("text") or "")

    def extract(_text: str) -> LDAIMetrics:
        incoming = int(captured.get("input_tokens") or 0)
        outgoing = int(captured.get("output_tokens") or 0)
        return LDAIMetrics(
            success=True,
            tokens=TokenUsage(total=incoming + outgoing, input=incoming, output=outgoing),
        )

    try:
        # LaunchDarkly: track_metrics_of records duration, tokens, and success.
        # https://launchdarkly.com/docs/sdk/ai/python
        text = tracker.track_metrics_of(extract, run)
    except Exception as exc:
        yield {"type": "error", "column": column, "message": str(exc)}
        yield {
            "type": "metrics",
            "column": column,
            "metrics": metric_payload(tracker.get_summary(), price_fields(config)),
        }
        return

    summary = tracker.get_summary()
    yield {
        "type": "metrics",
        "column": column,
        "metrics": metric_payload(summary, price_fields(config)),
    }

    record = served_record(spec["context_key"])
    yield from publish_file(
        column,
        model,
        text,
        messages=messages,
        variables=variables,
        context_key=spec["context_key"],
        served=record,
        config=config,
    )


def served_record(context_key: str) -> dict[str, Any]:
    """LaunchDarkly: variation_detail — reason and variation key for the drawer.

    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    client = _ld_client
    if client is None:
        return {}
    detail = client.variation_detail(
        config_key(),
        build_context(context_key),
        completion_default().to_dict(),
    )
    value = detail.value if isinstance(detail.value, dict) else {}
    meta = value.get("_ldMeta") or {}
    reason = detail.reason if isinstance(getattr(detail, "reason", None), dict) else {}
    return {
        "variationKey": meta.get("variationKey"),
        "reason": reason,
        "enabled": meta.get("enabled"),
        "version": meta.get("version"),
    }


def judge_default() -> AIJudgeConfigDefault:
    """SDK default when terraform-codegen-judge is missing.

    LaunchDarkly: judge config default.
    https://launchdarkly.com/docs/home/agentcontrol/judges
    """
    return AIJudgeConfigDefault(
        enabled=True,
        model=ModelConfig(name=DEFAULT_JUDGE_MODEL, parameters={"temperature": 0}),
        provider=ProviderConfig(name="anthropic"),
        evaluation_metric_key=DEFAULT_JUDGE_METRIC,
        messages=[
            LDMessage(role="system", content=read_message("judge-system.txt").strip()),
        ],
    )


def parse_judge_score(text: str) -> tuple[float, str] | None:
    body = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", body, re.S | re.I)
    if fenced:
        body = fenced.group(1).strip()
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None
    score = data.get("score")
    reasoning = data.get("reasoning")
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
        return None
    if not isinstance(reasoning, str):
        return None
    return float(score), reasoning.strip()


def judge_file(hcl: str, checked: dict[str, Any]) -> dict[str, Any]:
    """Score one file with the Sonnet judge config. Pass and fail files both run.

    LaunchDarkly: judge_config serves the prompt. track_metrics_of and
    track_judge_result record the call. The Python judge runner only speaks
    OpenAI, so this app calls Anthropic with the served prompt.
    https://launchdarkly.com/docs/home/agentcontrol/judges
    https://launchdarkly.com/docs/sdk/ai/python
    """
    context = build_context("codegen-judge")
    config = ai_client().judge_config(judge_key(), context, judge_default())
    if not config.enabled:
        return {"success": False, "error": f"Judge config '{judge_key()}' is off.", "passed": False}
    model = served_model_name(config)
    system = ""
    for message in messages_as_dicts(config):
        if message.get("role") == "system":
            system = message.get("content") or ""
            break
    if not system:
        system = read_message("judge-system.txt").strip()
    issue_count = checked.get("issue_count")
    preview = (checked.get("output") or "")[:2000]
    history = (
        "Task: Score this main.tf against the LaunchDarkly Terraform brief. "
        "Expected: an ancestry comment, required_providers source "
        "launchdarkly/launchdarkly ~> 2.0, provider \"launchdarkly\" with "
        "var.access_token, variables access_token, project_key, and environment_key, "
        "flags codegen-release and codegen-plan, two flag environments, six segments, "
        "and three metrics. Descriptions on flags, segments, and metrics come from the name.\n\n"
        f"terraform validate ok={bool(checked.get('ok'))} issues={issue_count}\n{preview}"
    )
    evaluation_input = f"MESSAGE HISTORY:\n{history}\n\nRESPONSE TO EVALUATE:\n{hcl}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": evaluation_input},
    ]
    tracker = config.create_tracker()
    captured: dict[str, Any] = {}

    def run() -> str:
        result = anthropic_chat(model, messages, max_tokens=1024)
        captured.update(result)
        if result.get("ttft_ms") is not None:
            tracker.track_time_to_first_token(int(result["ttft_ms"]))
        return str(result.get("text") or "")

    def extract(_text: str) -> LDAIMetrics:
        incoming = int(captured.get("input_tokens") or 0)
        outgoing = int(captured.get("output_tokens") or 0)
        return LDAIMetrics(
            success=True,
            tokens=TokenUsage(total=incoming + outgoing, input=incoming, output=outgoing),
        )

    try:
        text = tracker.track_metrics_of(extract, run)
    except Exception as exc:
        tracker.track_error()
        return {
            "success": False,
            "error": str(exc),
            "passed": False,
            "model": model,
            "configKey": judge_key(),
            "evaluationInput": evaluation_input,
            "system": system,
        }
    parsed = parse_judge_score(text)
    metric = getattr(config, "evaluation_metric_key", None) or DEFAULT_JUDGE_METRIC
    if parsed is None:
        result = JudgeResult(
            judge_config_key=judge_key(),
            success=False,
            sampled=True,
            metric_key=metric,
            error_message="Judge reply was not a score JSON object.",
        )
        tracker.track_judge_result(result)
        return {
            "success": False,
            "error": result.error_message,
            "passed": False,
            "model": model,
            "configKey": judge_key(),
            "metricKey": metric,
            "raw": text[:2000],
            "evaluationInput": evaluation_input,
            "system": system,
            "metrics": metric_payload(tracker.get_summary(), {}),
        }
    score, reasoning = parsed
    judge_result = JudgeResult(
        judge_config_key=judge_key(),
        success=True,
        sampled=True,
        metric_key=metric,
        score=score,
        reasoning=reasoning,
    )
    tracker.track_judge_result(judge_result)
    return {
        "success": True,
        "score": score,
        "reasoning": reasoning,
        "passed": score >= pass_threshold(),
        "threshold": pass_threshold(),
        "model": model,
        "configKey": judge_key(),
        "metricKey": metric,
        "evaluationInput": evaluation_input,
        "system": system,
        "metrics": metric_payload(tracker.get_summary(), {}),
    }


def publish_file(
    column: str,
    model: str,
    text: str,
    *,
    messages: list[dict[str, str]],
    variables: dict[str, str],
    context_key: str,
    served: dict[str, Any],
    config: Any,
) -> Iterator[dict[str, Any]]:
    hcl = extract_hcl(text)
    if not hcl.strip():
        yield {"type": "error", "column": column, "message": "The model returned an empty file."}
        return
    stats = file_stats(hcl)
    path = write_main_tf(model, hcl)
    yield {
        "type": "file",
        "column": column,
        "path": str(path.relative_to(EXAMPLE_ROOT)),
        "hcl": hcl,
        "stats": stats,
    }
    yield {"type": "status", "column": column, "message": "terraform validate…"}
    checked = terraform_validate(path.parent)
    yield {"type": "validate", "column": column, **checked}
    yield {"type": "status", "column": column, "message": "Judging the file…"}
    try:
        judged = judge_file(hcl, checked)
    except Exception as exc:
        judged = {"success": False, "error": str(exc), "passed": False}
    yield {"type": "judge", "column": column, "judge": judged}
    provider_name = ""
    if getattr(config, "provider", None) is not None:
        provider_name = str(getattr(config.provider, "name", "") or "")
    yield {
        "type": "details",
        "column": column,
        "ldTransaction": {
            "sent": {
                "configKey": config_key(),
                "context": {"kind": "user", "key": context_key, "name": context_key},
                "variables": variables,
                "messages": messages,
            },
            "received": {
                "configKey": config_key(),
                "provider": provider_name or ("anthropic" if uses_anthropic(model) else "ollama"),
                "model": model,
                "variationKey": served.get("variationKey"),
                "reason": served.get("reason") or {},
                "enabled": served.get("enabled"),
                "version": served.get("version"),
                "messages": messages,
                "validate": {
                    "ok": checked.get("ok"),
                    "issueCount": checked.get("issue_count"),
                    "phase": checked.get("phase"),
                },
                "judge": {
                    "configKey": judged.get("configKey") or judge_key(),
                    "model": judged.get("model"),
                    "score": judged.get("score"),
                    "passed": judged.get("passed"),
                    "threshold": judged.get("threshold") or pass_threshold(),
                    "reasoning": judged.get("reasoning"),
                    "error": judged.get("error"),
                    "metricKey": judged.get("metricKey"),
                    "system": judged.get("system"),
                    "evaluationInput": judged.get("evaluationInput"),
                },
            },
        },
    }


def generate_stream(selected: list[str] | None = None) -> Iterator[dict[str, Any]]:
    """One click. Selected models run in order. Each file is validated before the next call."""
    wanted = available_generators()
    if selected:
        chosen = {item for item in selected}
        wanted = [spec for spec in wanted if spec["id"] in chosen]
    if not wanted:
        yield {"type": "error", "column": "", "message": "Pick at least one model."}
        yield {"type": "done"}
        return
    for spec in wanted:
        yield from generate_one(spec)
    yield {"type": "done"}
