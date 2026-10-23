"""Release tenant-security on a timer. The lab writes each step.

By name, add one individual target every 10 seconds: S01, then S02, through
Small, Medium, and Large. A targeted name locks in every datacenter that
name occupies, because those contexts share a key.

By datacenter, add one targeting rule every 30 seconds for Large only. The rule
matches the large segment and one datacenter segment, so only the boxes in
that datacenter lock. Small and Medium stay off.

Full deployment walks Small, then Medium, then Large, one step every 20
seconds. Small is two rules on the size attribute: size 1, then size 2.
Medium is one rule per datacenter, DC01 through DC05. Large is one individual
target per name, L01 then L02. Unknown is in none of the waves.

LaunchDarkly stores the targets and the rules. It does not schedule the next
step. The timer in this module does.

LaunchDarkly: individual targets — https://launchdarkly.com/docs/home/flags/individual-targeting
LaunchDarkly: targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules
LaunchDarkly: segments — https://launchdarkly.com/docs/home/flags/segments
"""

from __future__ import annotations

import threading
import time
import urllib.parse
from typing import Any

from fill_rollout import flag_console_url
from flags import FLAG_SECURITY, SEGMENTS
from ld_flag_controls import _request, api_config
from tenants import build_customers

# By name is the fast demo. By datacenter steps through one site at a time.
# Full deployment is the mixed walk: size, then datacenter, then name.
NAME_STAGE_MS = 10_000
DC_STAGE_MS = 30_000
FULL_STAGE_MS = 20_000
FAMILIES = (
    {"segment": "small", "label": "Small"},
    {"segment": "medium", "label": "Medium"},
    {"segment": "large", "label": "Large"},
)
MODE_LABEL = {"name": "by name", "datacenter": "by datacenter", "full": "full deployment"}
CONTEXT_KIND = "tenant"
SMALL_SEGMENT = "tenant-size-small"
MEDIUM_SEGMENT = "tenant-size-medium"
LARGE_SEGMENT = "tenant-size-large"


def _name_steps() -> tuple[dict[str, str], ...]:
    """S01 through S28, then M01 through M10, then L01 through L10."""
    customers = build_customers()
    steps: list[dict[str, str]] = []
    for family in FAMILIES:
        names = sorted(customer["name"] for customer in customers if customer["sizeClass"] == family["segment"])
        for name in names:
            steps.append({"family": family["segment"], "key": name})
    return tuple(steps)


def _datacenter_steps() -> tuple[dict[str, Any], ...]:
    """Large in DC01, then DC02, through DC05. Segment keys come from flags.py."""
    steps = []
    for segment in SEGMENTS:
        if not str(segment["key"]).startswith("tenant-dc-"):
            continue
        label = str(segment["values"][0])
        steps.append(
            {
                "family": "large",
                "label": label,
                "segments": (LARGE_SEGMENT, segment["key"]),
            }
        )
    return tuple(steps)


def _full_steps() -> tuple[dict[str, Any], ...]:
    """Small by size, Medium by datacenter, Large by name.

    Size 1 is every odd Small. Size 2 is every even Small. Medium reuses the
    datacenter segments with the medium segment. Large reuses the L names.
    """
    steps: list[dict[str, Any]] = []
    for size in (1, 2):
        steps.append(
            {
                "id": f"small-{size}",
                "kind": "size",
                "family": "small",
                "label": f"size {size}",
                "segment": SMALL_SEGMENT,
                "size": size,
            }
        )
    for segment in SEGMENTS:
        if not str(segment["key"]).startswith("tenant-dc-"):
            continue
        label = str(segment["values"][0])
        steps.append(
            {
                "id": "medium-" + label,
                "kind": "datacenter",
                "family": "medium",
                "label": label,
                "segments": (MEDIUM_SEGMENT, segment["key"]),
            }
        )
    customers = build_customers()
    for name in sorted(customer["name"] for customer in customers if customer["sizeClass"] == "large"):
        steps.append({"id": "large-" + name, "kind": "name", "family": "large", "label": name, "key": name})
    return tuple(steps)


def _stage_ms(mode: str | None) -> int:
    if mode == "name":
        return NAME_STAGE_MS
    if mode == "full":
        return FULL_STAGE_MS
    return DC_STAGE_MS


NAME_STEPS = _name_steps()
DC_STEPS = _datacenter_steps()
FULL_STEPS = _full_steps()

_lock = threading.Lock()
_timer: threading.Timer | None = None
_next_at: float | None = None
_mode: str | None = None
_fault: str | None = None


def _variation(flag: dict[str, Any], wanted: bool) -> tuple[str | None, int | None]:
    for index, variation in enumerate(flag.get("variations") or []):
        if variation.get("value") is wanted:
            vid = variation.get("_id") or variation.get("id")
            return (vid if isinstance(vid, str) else None), index
    return None, None


def _rule_id(rule: dict[str, Any]) -> str | None:
    rid = rule.get("_id") or rule.get("id")
    return rid if isinstance(rid, str) else None


def _fetch() -> tuple[dict[str, Any], dict[str, Any], str, str]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Security waves need " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{FLAG_SECURITY}?{query}")
    env = (flag.get("environments") or {}).get(environment) or {}
    return flag, env, project, environment


def _patch(project: str, environment: str, instructions: list[dict[str, Any]], comment: str) -> None:
    _request(
        "PATCH",
        f"/flags/{project}/{FLAG_SECURITY}",
        {"environmentKey": environment, "comment": comment, "instructions": instructions},
    )


def _tenant_targets(env: dict[str, Any], true_index: int | None) -> set[str]:
    """Context keys individually targeted to the Enabled variation."""
    if true_index is None:
        return set()
    found: set[str] = set()
    for pool in env.get("contextTargets") or []:
        if pool.get("variation") != true_index or pool.get("contextKind") != CONTEXT_KIND:
            continue
        for value in pool.get("values") or []:
            if isinstance(value, str):
                found.add(value)
    return found


def _segment_values(rule: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for clause in rule.get("clauses") or []:
        if clause.get("op") != "segmentMatch":
            continue
        for value in clause.get("values") or []:
            if isinstance(value, str):
                found.add(value)
    return found


def _released_datacenters(env: dict[str, Any]) -> list[str]:
    """Datacenters whose rule matches Large and that datacenter segment."""
    found: set[str] = set()
    for rule in env.get("rules") or []:
        segments = _segment_values(rule)
        if LARGE_SEGMENT not in segments:
            continue
        for step in DC_STEPS:
            if step["segments"][1] in segments:
                found.add(step["label"])
    return [step["label"] for step in DC_STEPS if step["label"] in found]


def _has_targets(env: dict[str, Any]) -> bool:
    for key in ("contextTargets", "targets"):
        for pool in env.get(key) or []:
            if pool.get("values"):
                return True
    return False


def _clear_target_instructions(flag: dict[str, Any], env: dict[str, Any]) -> list[dict[str, Any]]:
    instructions = []
    for index, variation in enumerate(flag.get("variations") or []):
        vid = variation.get("_id") or variation.get("id")
        if not isinstance(vid, str):
            continue
        found = False
        for key in ("contextTargets", "targets"):
            for pool in env.get(key) or []:
                if pool.get("variation") == index and pool.get("values"):
                    found = True
        if found:
            instructions.append({"kind": "clearTargets", "variationId": vid})
    return instructions


def _remove_rules(env: dict[str, Any]) -> list[dict[str, Any]]:
    instructions = []
    for rule in env.get("rules") or []:
        rid = _rule_id(rule)
        if rid:
            instructions.append({"kind": "removeRule", "ruleId": rid})
    return instructions


def _add_target(key: str, variation_id: str) -> dict[str, Any]:
    """One tenant key on the Enabled variation.

    LaunchDarkly: addTargets — https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    """
    return {
        "kind": "addTargets",
        "values": [key],
        "contextKind": CONTEXT_KIND,
        "variationId": variation_id,
    }


def _segment_rule(description: str, segments: tuple[str, ...], variation_id: str) -> dict[str, Any]:
    """Every segmentMatch clause must match. Clauses in one rule are combined with and.

    LaunchDarkly: addRule with segmentMatch
    https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    return {
        "kind": "addRule",
        "description": description,
        "clauses": [
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "",
                "op": "segmentMatch",
                "values": [segment],
                "negate": False,
            }
            for segment in segments
        ],
        "variationId": variation_id,
    }


def _dc_rule(step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    """Both clauses must match: large segment, and this datacenter segment."""
    return _segment_rule("Large tenants in " + step["label"], step["segments"], variation_id)


def _size_rule(step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    """Small segment, and the size attribute. Size 1, then size 2.

    LaunchDarkly: targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    return {
        "kind": "addRule",
        "description": "Small tenants of size " + str(step["size"]),
        "clauses": [
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "",
                "op": "segmentMatch",
                "values": [step["segment"]],
                "negate": False,
            },
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "size",
                "op": "in",
                "values": [step["size"]],
                "negate": False,
            },
        ],
        "variationId": variation_id,
    }


def _medium_rule(step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    """Both clauses must match: medium segment, and this datacenter segment."""
    return _segment_rule("Medium tenants in " + step["label"], step["segments"], variation_id)


def _full_instruction(step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    if step["kind"] == "name":
        return _add_target(step["key"], variation_id)
    if step["kind"] == "size":
        return _size_rule(step, variation_id)
    return _medium_rule(step, variation_id)


def _attr_values(rule: dict[str, Any], attribute: str) -> set[Any]:
    found: set[Any] = set()
    for clause in rule.get("clauses") or []:
        if clause.get("attribute") != attribute or clause.get("op") != "in":
            continue
        for value in clause.get("values") or []:
            found.add(value)
    return found


def _has_full_rules(env: dict[str, Any]) -> bool:
    """True when a Small size rule or a Medium datacenter rule is on the flag."""
    for rule in env.get("rules") or []:
        segments = _segment_values(rule)
        if SMALL_SEGMENT in segments and _attr_values(rule, "size"):
            return True
        if MEDIUM_SEGMENT in segments and any(segment.startswith("tenant-dc-") for segment in segments):
            return True
    return False


def _full_released(env: dict[str, Any], targeted: set[str]) -> list[dict[str, Any]]:
    """Full-deployment steps already written, in sequence order."""
    sizes: set[int] = set()
    datacenters: set[str] = set()
    for rule in env.get("rules") or []:
        segments = _segment_values(rule)
        if SMALL_SEGMENT in segments:
            for value in _attr_values(rule, "size"):
                try:
                    sizes.add(int(value))
                except (TypeError, ValueError):
                    continue
        if MEDIUM_SEGMENT in segments:
            for step in FULL_STEPS:
                if step["kind"] == "datacenter" and step["segments"][1] in segments:
                    datacenters.add(step["label"])
    released = []
    for step in FULL_STEPS:
        if step["kind"] == "size" and step["size"] in sizes:
            released.append(step)
        elif step["kind"] == "datacenter" and step["label"] in datacenters:
            released.append(step)
        elif step["kind"] == "name" and step["key"] in targeted:
            released.append(step)
    return released


def _cancel_timer() -> None:
    global _timer, _next_at, _mode
    if _timer is not None:
        _timer.cancel()
        _timer = None
    _next_at = None
    _mode = None


def _arm_timer(mode: str) -> None:
    global _timer, _next_at, _mode
    if _timer is not None:
        _timer.cancel()
        _timer = None
    _mode = mode
    delay = _stage_ms(mode) / 1000
    _next_at = time.monotonic() + delay
    _timer = threading.Timer(delay, _advance)
    _timer.daemon = True
    _timer.start()


def _families(
    mode: str | None,
    names: list[dict[str, str]],
    datacenters: list[str],
    full_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    released_names = {step["key"] for step in names}
    released_full = {step["id"] for step in full_steps}
    rows = []
    for family in FAMILIES:
        total = sum(1 for step in NAME_STEPS if step["family"] == family["segment"])
        got = 0
        state = "pending"
        if mode == "name":
            got = sum(1 for step in NAME_STEPS if step["family"] == family["segment"] and step["key"] in released_names)
            if got >= total:
                state = "done"
            elif got:
                state = "active"
        elif mode == "datacenter" and family["segment"] == "large":
            total = len(DC_STEPS)
            got = len(datacenters)
            if got >= total:
                state = "done"
            elif got:
                state = "active"
        elif mode == "full":
            family_steps = [step for step in FULL_STEPS if step["family"] == family["segment"]]
            total = len(family_steps)
            got = sum(1 for step in family_steps if step["id"] in released_full)
            if total and got >= total:
                state = "done"
            elif got:
                state = "active"
        rows.append(
            {
                "segment": family["segment"],
                "label": family["label"],
                "state": state,
                "released": got,
                "total": total,
            }
        )
    return rows


def _detail(
    status: str,
    mode: str | None,
    families: list[dict[str, Any]],
    step: str | None,
    fault: str | None,
    stale: bool,
) -> str:
    if fault:
        return fault
    if status == "unconfigured":
        return "Set the REST credentials on the server to run a wave."
    if status == "missing":
        return "Create tenant-security with rest/create-all.sh."
    if stale:
        return "This flag has targeting from outside the wave. Reset clears it."
    if status == "off" or not mode:
        return (
            "Off. By name releases S01, then the next name every 10 seconds. "
            "By datacenter releases Large in DC01, then the next datacenter every 30 seconds. "
            "Full deployment releases Small by size, then Medium from DC01 through DC05, then L01, every 20 seconds."
        )
    mode_label = MODE_LABEL[mode]
    if status == "complete":
        if mode == "datacenter":
            return "Large is locked in every datacenter, by datacenter. Small and Medium stay off."
        if mode == "full":
            return "Small, Medium, and Large have the lock. Unknown stays off."
        return "Small, Medium, and Large have the lock, by name. Unknown stays off."
    active = next((family for family in families if family["state"] == "active"), None)
    if active and step:
        return active["label"] + " · " + mode_label + " · " + step
    done = [family for family in families if family["state"] == "done"]
    nxt = next((family for family in families if family["state"] == "pending"), None)
    last = done[-1]["label"] if done else "This step"
    line = last + " · " + mode_label + " · " + (step or "")
    if nxt:
        return line + ". " + nxt["label"] + " follows when the timer ends."
    return line


def _snapshot(
    flag: dict[str, Any] | None,
    env: dict[str, Any] | None,
    *,
    scheduled: bool,
    remaining: int | None,
    fault: str | None,
    configured: bool,
    missing: bool,
) -> dict[str, Any]:
    """Turn the flag's targets and rules into the card the page draws."""
    names: list[dict[str, str]] = []
    datacenters: list[str] = []
    full_steps: list[dict[str, Any]] = []
    mode = None
    on = False
    stale = False
    if flag and env and not missing:
        on = bool(env.get("on"))
        _true_id, true_index = _variation(flag, True)
        targeted = _tenant_targets(env, true_index)
        names = [step for step in NAME_STEPS if step["key"] in targeted]
        datacenters = _released_datacenters(env)
        full_steps = _full_released(env, targeted)
        if _has_full_rules(env):
            mode = "full"
        elif names:
            mode = "name"
        elif datacenters:
            mode = "datacenter"
        elif on and (env.get("rules") or _has_targets(env)):
            stale = True
    families = _families(mode, names, datacenters, full_steps)
    if not configured:
        status = "unconfigured"
    elif missing:
        status = "missing"
    elif not on or mode is None:
        status = "off"
    elif mode == "name" and len(names) >= len(NAME_STEPS):
        status = "complete"
    elif mode == "datacenter" and len(datacenters) >= len(DC_STEPS):
        status = "complete"
    elif mode == "full" and len(full_steps) >= len(FULL_STEPS):
        status = "complete"
    else:
        status = "running"
    step = None
    if mode == "name" and names:
        step = names[-1]["key"]
    elif mode == "datacenter" and datacenters:
        step = datacenters[-1]
    elif mode == "full" and full_steps:
        step = full_steps[-1]["label"]
    return {
        "status": status,
        "on": on,
        "mode": mode,
        "modeLabel": MODE_LABEL.get(mode or "", None),
        "families": families,
        "step": step,
        "scheduled": scheduled,
        "remainingMs": remaining,
        "stale": stale,
        "detail": _detail(status, mode, families, step, fault, stale),
        "fault": fault,
    }


def _timer_view() -> tuple[bool, int | None, str | None]:
    with _lock:
        scheduled = _timer is not None and _timer.is_alive()
        remaining = None
        if scheduled and _next_at is not None:
            remaining = max(0, int((_next_at - time.monotonic()) * 1000))
        return scheduled, remaining, _fault


def security_status() -> dict[str, Any]:
    """Read which wave is in progress, and which step was written last.

    The page pulses the family chip from families[].state and prints detail.
    """
    cfg = api_config()
    scheduled, remaining, fault = _timer_view()
    base = {
        "key": FLAG_SECURITY,
        "nameStageMs": NAME_STAGE_MS,
        "datacenterStageMs": DC_STAGE_MS,
        "fullStageMs": FULL_STAGE_MS,
        "flagUrl": flag_console_url(cfg.get("projectKey"), cfg.get("environmentKey"), FLAG_SECURITY),
        "nameCount": len(NAME_STEPS),
        "datacenterCount": len(DC_STEPS),
        "fullCount": len(FULL_STEPS),
    }
    if not cfg["configured"]:
        snap = _snapshot(None, None, scheduled=False, remaining=None, fault=None, configured=False, missing=False)
        return {**base, **cfg, **snap, "stageMs": _stage_ms(snap.get("mode"))}
    try:
        flag, env, _project, _environment = _fetch()
    except Exception as exc:
        snap = _snapshot(
            None,
            None,
            scheduled=scheduled,
            remaining=remaining,
            fault=None,
            configured=True,
            missing=True,
        )
        return {**base, **cfg, **snap, "stageMs": _stage_ms(snap.get("mode")), "error": str(exc)}
    snap = _snapshot(
        flag,
        env,
        scheduled=scheduled,
        remaining=remaining,
        fault=fault,
        configured=True,
        missing=False,
    )
    return {**base, **cfg, **snap, "stageMs": _stage_ms(snap.get("mode"))}


def _advance() -> None:
    """Write the next step. Called by the timer, not by a click."""
    global _fault
    with _lock:
        mode = _mode
        if mode not in MODE_LABEL:
            _cancel_timer()
            return
        try:
            flag, env, project, environment = _fetch()
            true_id, true_index = _variation(flag, True)
            if not true_id:
                raise RuntimeError("tenant-security needs an Enabled variation.")
            if mode == "name":
                targeted = _tenant_targets(env, true_index)
                nxt = next((step for step in NAME_STEPS if step["key"] not in targeted), None)
                if nxt is None:
                    _cancel_timer()
                    return
                _patch(
                    project,
                    environment,
                    [_add_target(nxt["key"], true_id)],
                    "21-tenant-datacenters: security wave " + nxt["key"],
                )
                more = any(step["key"] not in targeted and step["key"] != nxt["key"] for step in NAME_STEPS)
            elif mode == "datacenter":
                released = set(_released_datacenters(env))
                nxt = next((step for step in DC_STEPS if step["label"] not in released), None)
                if nxt is None:
                    _cancel_timer()
                    return
                _patch(
                    project,
                    environment,
                    [_dc_rule(nxt, true_id)],
                    "21-tenant-datacenters: security wave " + nxt["label"],
                )
                more = any(step["label"] not in released and step["label"] != nxt["label"] for step in DC_STEPS)
            else:
                targeted = _tenant_targets(env, true_index)
                released_ids = {step["id"] for step in _full_released(env, targeted)}
                nxt = next((step for step in FULL_STEPS if step["id"] not in released_ids), None)
                if nxt is None:
                    _cancel_timer()
                    return
                _patch(
                    project,
                    environment,
                    [_full_instruction(nxt, true_id)],
                    "21-tenant-datacenters: security wave " + nxt["label"],
                )
                more = any(step["id"] not in released_ids and step["id"] != nxt["id"] for step in FULL_STEPS)
            _fault = None
            if more:
                _arm_timer(mode)
            else:
                _cancel_timer()
        except Exception as exc:
            _fault = str(exc)
            _cancel_timer()


def start_security_wave(mode: str) -> dict[str, Any]:
    """Turn the flag on and write the first step. Later steps follow on the timer.

    mode "name" targets S01. mode "datacenter" adds the Large-in-DC01 rule.
    mode "full" adds the Small size-1 rule. Any start clears the other waves.
    """
    global _fault
    if mode not in MODE_LABEL:
        raise ValueError('mode must be "name", "datacenter", or "full"')
    with _lock:
        _cancel_timer()
        _fault = None
        flag, env, project, environment = _fetch()
        true_id, _true_index = _variation(flag, True)
        false_id, _false_index = _variation(flag, False)
        if not true_id or not false_id:
            raise RuntimeError("tenant-security needs Enabled and Off variations.")
        instructions = _remove_rules(env) + _clear_target_instructions(flag, env)
        instructions.extend(
            [
                {"kind": "updateOffVariation", "variationId": false_id},
                {"kind": "updateFallthroughVariationOrRollout", "variationId": false_id},
                {"kind": "turnFlagOn"},
            ]
        )
        if mode == "name":
            first = NAME_STEPS[0]
            instructions.append(_add_target(first["key"], true_id))
            comment = "21-tenant-datacenters: start security wave by name"
        elif mode == "datacenter":
            first = DC_STEPS[0]
            instructions.append(_dc_rule(first, true_id))
            comment = "21-tenant-datacenters: start security wave by datacenter"
        else:
            first = FULL_STEPS[0]
            instructions.append(_full_instruction(first, true_id))
            comment = "21-tenant-datacenters: start security wave full deployment"
        _patch(project, environment, instructions, comment)
        _arm_timer(mode)
    return security_status()


def reset_security_wave() -> dict[str, Any]:
    """Remove the targets and the datacenter rules, and turn tenant-security off."""
    global _fault
    with _lock:
        _cancel_timer()
        _fault = None
        flag, env, project, environment = _fetch()
        false_id, _false_index = _variation(flag, False)
        if not false_id:
            raise RuntimeError("tenant-security has no Off variation.")
        instructions = _remove_rules(env) + _clear_target_instructions(flag, env)
        instructions.extend(
            [
                {"kind": "updateFallthroughVariationOrRollout", "variationId": false_id},
                {"kind": "turnFlagOff"},
            ]
        )
        _patch(project, environment, instructions, "21-tenant-datacenters: reset security wave")
    return security_status()
