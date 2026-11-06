"""REST controls and SDK evaluation for the multitenant datacenter lab.

The Flags tab writes targeting rules. A size row sends one multi-context and
reads the variation back. No secrets are returned to the page.

Feature flags — targeting rules
https://launchdarkly.com/docs/home/flags/targeting-rules

Feature flags — multi-contexts
https://launchdarkly.com/docs/home/flags/multi-contexts

REST API — patch feature flag
https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PALETTE = "mtdc-border-palette"
FILL = "mtdc-service-fill"
SEGMENT = "mtdc-gdpr-eu"
TARGETS = (
    "mtdc-security",
    "mtdc-firewall",
    "mtdc-data-sharing",
    "mtdc-marketing",
)
GDPR_FLAGS = frozenset({"mtdc-data-sharing", "mtdc-marketing"})
PALETTES = ("none", "roygbiv", "contrast", "earth", "ocean", "color-vision-aware")
SIZES = ("small", "medium", "large")
EVALUATIONS = (
    (PALETTE, "none"),
    (FILL, False),
    ("mtdc-security", False),
    ("mtdc-firewall", False),
    ("mtdc-data-sharing", False),
    ("mtdc-marketing", False),
)

LD_API_HOST = os.environ.get("LD_API_HOST") or "https://app.launchdarkly.com"
LD_API_VERSION = os.environ.get("LD_API_VERSION") or "20240415"
_sdk_client: Any = None


def api_config() -> dict[str, Any]:
    """Return whether the control can call the REST API. No secrets."""
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    project = (os.environ.get("LD_PROJECT_KEY") or "").strip()
    environment = (os.environ.get("LD_ENVIRONMENT_KEY") or "").strip()
    missing = []
    if not token:
        missing.append("LD_API_ACCESS_TOKEN")
    if not project:
        missing.append("LD_PROJECT_KEY")
    if not environment:
        missing.append("LD_ENVIRONMENT_KEY")
    return {
        "configured": not missing,
        "missing": missing,
        "projectKey": project or None,
        "environmentKey": environment or None,
    }


def _request(method: str, path: str, body: dict[str, Any] | None = None, semantic: bool = False) -> dict[str, Any]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    token = (os.environ.get("LD_API_ACCESS_TOKEN") or "").strip()
    url = f"{LD_API_HOST.rstrip('/')}/api/v2{path}"
    data = None
    headers = {
        "Authorization": token,
        "LD-API-Version": LD_API_VERSION,
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = (
            "application/json; domain-model=launchdarkly.semanticpatch"
            if semantic
            else "application/json"
        )
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"LaunchDarkly {exc.code} on {method} {path}: {detail[:300]}") from exc


def _variation_id(flag: dict[str, Any], value: Any) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") == value:
            return variation.get("_id")
    return None


def _fallthrough_value(flag: dict[str, Any], env: dict[str, Any]) -> Any:
    index = (env.get("fallthrough") or {}).get("variation")
    variations = flag.get("variations") or []
    if isinstance(index, int) and 0 <= index < len(variations):
        return variations[index].get("value")
    return None


def _rule_selection(env: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Sizes and datacenters from the checkbox rule. The segment rule is skipped."""
    sizes: list[str] = []
    datacenters: list[str] = []
    if not env.get("on"):
        return sizes, datacenters
    for rule in env.get("rules") or []:
        clauses = rule.get("clauses") or []
        if any(clause.get("op") == "segmentMatch" for clause in clauses):
            continue
        for clause in clauses:
            values = [str(value) for value in clause.get("values") or []]
            if clause.get("attribute") == "sizeClass":
                sizes = [value for value in values if value in SIZES]
            if clause.get("attribute") == "key" and clause.get("contextKind") == "datacenter":
                datacenters = values
    return sizes, datacenters


def snapshot() -> dict[str, Any]:
    """Current toggle state for the Flags tab. No secrets."""
    cfg = api_config()
    if not cfg["configured"]:
        return {**cfg, "ok": True, "flags": []}
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flags = []
    for key in (PALETTE, FILL, *TARGETS):
        flag = _request("GET", f"/flags/{project}/{key}?{query}")
        env = (flag.get("environments") or {}).get(environment) or {}
        sizes, datacenters = _rule_selection(env)
        flags.append({
            "key": key,
            "on": bool(env.get("on")),
            "fallthrough": _fallthrough_value(flag, env),
            "sizes": sizes,
            "datacenters": datacenters,
        })
    return {**cfg, "ok": True, "flags": flags}


def _patch(project: str, environment: str, key: str, instructions: list[dict[str, Any]], comment: str) -> None:
    _request(
        "PATCH",
        f"/flags/{project}/{key}",
        {"environmentKey": environment, "comment": comment, "instructions": instructions},
        semantic=True,
    )


def _ensure_segment(project: str, environment: str) -> None:
    """Create mtdc-gdpr-eu when this environment does not have it yet."""
    try:
        _request("GET", f"/segments/{project}/{environment}/{SEGMENT}")
        return
    except RuntimeError as exc:
        if "LaunchDarkly 404" not in str(exc):
            raise
    _request(
        "POST",
        f"/segments/{project}/{environment}",
        {
            "name": "MTDC GDPR EU",
            "key": SEGMENT,
            "tags": ["24-multitenant-datacenter"],
            "description": "Datacenters with gdpr true.",
        },
    )
    _request(
        "PATCH",
        f"/segments/{project}/{environment}/{SEGMENT}",
        {
            "environmentKey": environment,
            "comment": "24-multitenant-datacenter: gdpr true",
            "instructions": [{
                "kind": "addRule",
                "clauses": [{
                    "contextKind": "datacenter",
                    "attribute": "gdpr",
                    "op": "in",
                    "values": [True],
                }],
            }],
        },
        semantic=True,
    )


def apply_control(body: dict[str, Any]) -> dict[str, Any]:
    """Write one Flags-tab control into the configured environment."""
    key = str(body.get("key") or "").strip()
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Flag controls need " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{key}?{query}")
    env = (flag.get("environments") or {}).get(environment) or {}
    if key == PALETTE:
        palette = str(body.get("palette") or "none")
        if palette not in PALETTES:
            raise ValueError(f"Unknown palette: {palette}")
        instructions: list[dict[str, Any]] = []
        if palette == "none":
            instructions.append({"kind": "turnFlagOff"})
        else:
            variation_id = _variation_id(flag, palette)
            if not variation_id:
                raise ValueError(f"No variation for {palette}")
            instructions.append({"kind": "turnFlagOn"})
            instructions.append({"kind": "updateFallthroughVariationOrRollout", "variationId": variation_id})
        _patch(project, environment, key, instructions, f"24-multitenant-datacenter: border {palette}")
        return {"ok": True, "key": key}
    if key == FILL:
        on = bool(body.get("on"))
        instructions = [{"kind": "turnFlagOff"}]
        if on:
            variation_id = _variation_id(flag, True)
            if not variation_id:
                raise ValueError("No true variation")
            instructions = [
                {"kind": "turnFlagOn"},
                {"kind": "updateFallthroughVariationOrRollout", "variationId": variation_id},
            ]
        _patch(project, environment, key, instructions, "24-multitenant-datacenter: fill " + ("on" if on else "off"))
        return {"ok": True, "key": key}
    if key not in TARGETS:
        raise ValueError(f"Flag key not allowed for controls: {key}")
    sizes = [str(value) for value in body.get("sizes") or [] if str(value) in SIZES]
    datacenters = [str(value) for value in body.get("datacenters") or [] if value]
    if key in GDPR_FLAGS:
        _ensure_segment(project, environment)
    instructions = [
        {"kind": "removeRule", "ruleId": rule["_id"]}
        for rule in env.get("rules") or []
        if rule.get("_id")
    ]
    false_id = _variation_id(flag, False)
    true_id = _variation_id(flag, True)
    if not false_id or not true_id:
        raise ValueError(f"{key} is missing a boolean variation")
    if key in GDPR_FLAGS:
        instructions.append({
            "kind": "addRule",
            "variationId": false_id,
            "clauses": [{
                "contextKind": "datacenter",
                "attribute": "segmentMatch",
                "op": "segmentMatch",
                "values": [SEGMENT],
            }],
        })
    matched = bool(sizes and datacenters)
    if matched:
        instructions.append({
            "kind": "addRule",
            "variationId": true_id,
            "clauses": [
                {"contextKind": "customer", "attribute": "sizeClass", "op": "in", "values": sizes},
                {"contextKind": "datacenter", "attribute": "key", "op": "in", "values": datacenters},
            ],
        })
    instructions.append({"kind": "updateFallthroughVariationOrRollout", "variationId": false_id})
    instructions.append({"kind": "turnFlagOn" if matched else "turnFlagOff"})
    _patch(project, environment, key, instructions, f"24-multitenant-datacenter: {key}")
    return {"ok": True, "key": key}


def _sdk():
    """One server SDK client for the life of the process."""
    global _sdk_client
    if _sdk_client is not None:
        return _sdk_client
    sdk_key = (os.environ.get("LD_SDK_KEY") or "").strip()
    if not sdk_key:
        return None
    import ldclient
    from ldclient.config import Config

    ldclient.set_config(Config(sdk_key))
    _sdk_client = ldclient.get()
    return _sdk_client


def _multi_context(payload: dict[str, Any]) -> Any:
    from ldclient import Context

    datacenter = payload.get("datacenter") or {}
    service = payload.get("service") or {}
    customer = payload.get("customer") or {}
    dc = (
        Context.builder(str(datacenter.get("key") or "datacenter"))
        .kind("datacenter")
        .set("geo", datacenter.get("geo"))
        .set("gdpr", bool(datacenter.get("gdpr")))
        .build()
    )
    service_builder = (
        Context.builder(str(service.get("key") or "service"))
        .kind("service")
        .set("name", service.get("name"))
        .set("tenancy", service.get("tenancy"))
        .set("instances", int(service.get("instances") or 0))
    )
    if service.get("customer"):
        service_builder = service_builder.set("customer", service.get("customer"))
    cust = (
        Context.builder(str(customer.get("key") or "customer"))
        .kind("customer")
        .set("sizeClass", customer.get("sizeClass"))
        .set("tenancy", customer.get("tenancy"))
        .build()
    )
    return Context.create_multi(dc, service_builder.build(), cust)


def evaluate_context(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate the six flags for one multi-context. The default is the safe off value.

    LaunchDarkly: evaluating flags
    https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    """
    client = _sdk()
    if client is None:
        return {"configured": False, "missing": ["LD_SDK_KEY"], "flags": []}
    context = _multi_context(payload)
    flags = []
    for key, default in EVALUATIONS:
        detail = client.variation_detail(key, context, default)
        reason = getattr(detail, "reason", None)
        if isinstance(reason, dict):
            kind = str(reason.get("kind", "UNKNOWN"))
        else:
            kind = str(getattr(reason, "kind", None) or "UNKNOWN")
        flags.append({"key": key, "value": detail.value, "reason": kind})
    return {"configured": True, "flags": flags}


def close_sdk() -> None:
    if _sdk_client is not None:
        _sdk_client.close()
