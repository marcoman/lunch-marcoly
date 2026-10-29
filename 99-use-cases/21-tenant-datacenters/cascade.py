"""Cascade release for Medium tenants. The lab writes each step.

Phase 1 turns tenant-security on, one name every 10 seconds, and only in
DC01 through DC04. A rule matches the context key and the datacenter, so a
name that also sits in DC05 stays off there. M01 and M03 are only in DC05,
so they are not in the sequence.

The page then waits. Good starts phase 2 on tenant-firewall. Small in DC01,
then Small in DC02, then the Medium names in those two datacenters. A Small
box gets the firewall and not the lock, so its subscript stays 0. Bad clears
the firewall and leaves the lock. After phase 2, Good turns tenant-box-fill
on for the Medium presences that have both icons. Small is not in that set.

Start clears fill, security, and firewall first. The border palette stays.

Targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules
Contexts — https://launchdarkly.com/docs/home/flags/contexts
"""

from __future__ import annotations

import threading
import time
import urllib.parse
from typing import Any

from fill_rollout import flag_console_url, reset_fill_rollout
from flags import FLAG_FILL, FLAG_FIREWALL, FLAG_SECURITY
from ld_flag_controls import _request, api_config
from security_waves import reset_security_wave
from tenants import build_customers

STAGE_MS = 10_000
CONTEXT_KIND = "tenant"
PHASE1_DCS = ("DC01", "DC02", "DC03", "DC04")
PHASE2_DCS = ("DC01", "DC02")
_SECURITY_PREFIX = "Cascade security "
_FIREWALL_PREFIX = "Cascade firewall "
_FILL_PREFIX = "Cascade fill "

_lock = threading.Lock()
_timer: threading.Timer | None = None
_next_at: float | None = None
_phase: str | None = None
_waiting = False
_fault: str | None = None


def _medium_steps(allowed: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    """Medium names that occupy at least one datacenter in this phase, in name order."""
    steps = []
    for customer in build_customers():
        if customer["sizeClass"] != "medium":
            continue
        sites = tuple(dc for dc in customer["datacenters"] if dc in allowed)
        if not sites:
            continue
        steps.append(
            {
                "id": customer["name"],
                "kind": "name",
                "key": customer["name"],
                "datacenters": sites,
            }
        )
    steps.sort(key=lambda step: step["key"])
    return tuple(steps)


def _small_datacenter_steps() -> tuple[dict[str, Any], ...]:
    """One step per datacenter. Every Small presence in that datacenter matches."""
    return tuple(
        {
            "id": "small-" + datacenter,
            "kind": "datacenter",
            "sizeClass": "small",
            "datacenter": datacenter,
        }
        for datacenter in PHASE2_DCS
    )


PHASE1_STEPS = _medium_steps(PHASE1_DCS)
FILL_STEPS = _medium_steps(PHASE2_DCS)
PHASE2_STEPS = _small_datacenter_steps() + FILL_STEPS


def _variation(flag: dict[str, Any], wanted: bool) -> str | None:
    for variation in flag.get("variations") or []:
        if variation.get("value") is wanted:
            vid = variation.get("_id") or variation.get("id")
            return vid if isinstance(vid, str) else None
    return None


def _fetch(flag_key: str) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    cfg = api_config()
    if not cfg["configured"]:
        raise RuntimeError("Cascade needs " + ", ".join(cfg["missing"]) + ".")
    project = cfg["projectKey"]
    environment = cfg["environmentKey"]
    query = urllib.parse.urlencode({"env": environment})
    flag = _request("GET", f"/flags/{project}/{flag_key}?{query}")
    env = (flag.get("environments") or {}).get(environment) or {}
    return flag, env, project, environment


def _patch(project: str, environment: str, flag_key: str, instructions: list[dict[str, Any]], comment: str) -> None:
    _request(
        "PATCH",
        f"/flags/{project}/{flag_key}",
        {"environmentKey": environment, "comment": comment, "instructions": instructions},
    )


def _clause_values(rule: dict[str, Any], attribute: str) -> list[Any]:
    found: list[Any] = []
    for clause in rule.get("clauses") or []:
        if clause.get("attribute") != attribute or clause.get("op") != "in" or clause.get("negate"):
            continue
        found.extend(clause.get("values") or [])
    return found


def _step_id(step: dict[str, Any]) -> str:
    return str(step.get("id") or step.get("key"))


def _matches(rule: dict[str, Any], step: dict[str, Any]) -> bool:
    """A datacenter step matches size class and one site. A name step matches the key."""
    sites = {value for value in _clause_values(rule, "datacenter") if isinstance(value, str)}
    if step.get("kind") == "datacenter":
        classes = {value for value in _clause_values(rule, "sizeClass") if isinstance(value, str)}
        return step["sizeClass"] in classes and step["datacenter"] in sites
    keys = {value for value in _clause_values(rule, "key") if isinstance(value, str)}
    return step["key"] in keys and set(step["datacenters"]).issubset(sites)


def _released(env: dict[str, Any], prefix: str, steps: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    """Steps whose rule is already on the flag, in cascade order."""
    done: list[dict[str, Any]] = []
    for rule in env.get("rules") or []:
        description = str(rule.get("description") or "")
        if not description.startswith(prefix):
            continue
        for step in steps:
            if _matches(rule, step):
                done.append(step)
    order = {_step_id(step): index for index, step in enumerate(steps)}
    done.sort(key=lambda step: order.get(_step_id(step), 0))
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for step in done:
        if _step_id(step) in seen:
            continue
        seen.add(_step_id(step))
        unique.append(step)
    return unique


def _datacenter_rule(prefix: str, step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    """Every Small tenant in one datacenter. The other sites for that name stay off.

    LaunchDarkly: addRule — https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    return {
        "kind": "addRule",
        "description": prefix + "small " + step["datacenter"],
        "clauses": [
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "sizeClass",
                "op": "in",
                "values": [step["sizeClass"]],
                "negate": False,
            },
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "datacenter",
                "op": "in",
                "values": [step["datacenter"]],
                "negate": False,
            },
        ],
        "variationId": variation_id,
    }


def _step_rule(prefix: str, step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    if step.get("kind") == "datacenter":
        return _datacenter_rule(prefix, step, variation_id)
    return _presence_rule(prefix, step, variation_id)


def _presence_rule(prefix: str, step: dict[str, Any], variation_id: str) -> dict[str, Any]:
    """Match this tenant key and these datacenters. Clauses in one rule are combined with and.

    The context key stays the tenant name. Datacenter is an attribute, so the
    same name can be on in DC03 and off in DC05.

    LaunchDarkly: addRule — https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    sites = ", ".join(step["datacenters"])
    return {
        "kind": "addRule",
        "description": prefix + step["key"],
        "clauses": [
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "key",
                "op": "in",
                "values": [step["key"]],
                "negate": False,
            },
            {
                "contextKind": CONTEXT_KIND,
                "attribute": "datacenter",
                "op": "in",
                "values": list(step["datacenters"]),
                "negate": False,
            },
        ],
        "variationId": variation_id,
    }


def _reset_firewall() -> None:
    """Remove firewall rules and targets, and turn tenant-firewall off."""
    flag, env, project, environment = _fetch(FLAG_FIREWALL)
    false_id = _variation(flag, False)
    if not false_id:
        raise RuntimeError("tenant-firewall has no Off variation.")
    instructions: list[dict[str, Any]] = []
    for rule in env.get("rules") or []:
        rid = rule.get("_id") or rule.get("id")
        if isinstance(rid, str):
            instructions.append({"kind": "removeRule", "ruleId": rid})
    for index, variation in enumerate(flag.get("variations") or []):
        vid = variation.get("_id") or variation.get("id")
        if not isinstance(vid, str):
            continue
        pools = list(env.get("contextTargets") or []) + list(env.get("targets") or [])
        if any(pool.get("variation") == index and pool.get("values") for pool in pools):
            instructions.append({"kind": "clearTargets", "variationId": vid})
    instructions.extend(
        [
            {"kind": "updateFallthroughVariationOrRollout", "variationId": false_id},
            {"kind": "turnFlagOff"},
        ]
    )
    _patch(project, environment, FLAG_FIREWALL, instructions, "21-tenant-datacenters: reset cascade firewall")


def _label(step: dict[str, Any] | None) -> str | None:
    if not step:
        return None
    if step.get("kind") == "datacenter":
        return "Small · " + step["datacenter"]
    return step["key"] + " · " + ", ".join(step["datacenters"])


def _cancel_timer() -> None:
    global _timer, _next_at
    if _timer is not None:
        _timer.cancel()
        _timer = None
    _next_at = None


def _arm_timer() -> None:
    global _timer, _next_at
    if _timer is not None:
        _timer.cancel()
    delay = STAGE_MS / 1000
    _next_at = time.monotonic() + delay
    _timer = threading.Timer(delay, _advance)
    _timer.daemon = True
    _timer.start()


def _turn_on(flag_key: str, step: dict[str, Any], prefix: str, comment: str) -> None:
    """Serve the false variation by default, turn the flag on, and add one presence rule."""
    flag, _env, project, environment = _fetch(flag_key)
    true_id = _variation(flag, True)
    false_id = _variation(flag, False)
    if not true_id or not false_id:
        raise RuntimeError(flag_key + " needs true and false variations.")
    _patch(
        project,
        environment,
        flag_key,
        [
            {"kind": "updateOffVariation", "variationId": false_id},
            {"kind": "updateFallthroughVariationOrRollout", "variationId": false_id},
            {"kind": "turnFlagOn"},
            _step_rule(prefix, step, true_id),
        ],
        comment,
    )


def _add_step(flag_key: str, step: dict[str, Any], prefix: str, comment: str) -> None:
    flag, _env, project, environment = _fetch(flag_key)
    true_id = _variation(flag, True)
    if not true_id:
        raise RuntimeError(flag_key + " needs a true variation.")
    _patch(
        project,
        environment,
        flag_key,
        [_step_rule(prefix, step, true_id)],
        comment,
    )


def _enable_fill(steps: tuple[dict[str, Any], ...]) -> None:
    """One patch. Every phase-2 presence gets Fill. Everyone else stays Empty.

    LaunchDarkly: targeting rules — https://launchdarkly.com/docs/home/flags/targeting-rules
    """
    flag, _env, project, environment = _fetch(FLAG_FILL)
    true_id = _variation(flag, True)
    false_id = _variation(flag, False)
    if not true_id or not false_id:
        raise RuntimeError("tenant-box-fill needs Fill and Empty variations.")
    instructions: list[dict[str, Any]] = [
        {"kind": "updateOffVariation", "variationId": false_id},
        {"kind": "updateFallthroughVariationOrRollout", "variationId": false_id},
        {"kind": "turnFlagOn"},
    ]
    instructions.extend(_step_rule(_FILL_PREFIX, step, true_id) for step in steps)
    _patch(project, environment, FLAG_FILL, instructions, "21-tenant-datacenters: cascade fill")


def _clear_three() -> None:
    """Security wave reset also stops that timer. Fill and firewall follow."""
    reset_security_wave()
    _reset_firewall()
    reset_fill_rollout()


def _phase_rows(security_done: int, firewall_done: int, fill_done: bool, phase: str | None, waiting: bool) -> list[dict[str, Any]]:
    def state(name: str, done: int, total: int, finished: bool) -> str:
        if finished or (phase == "fill" and name == "fill"):
            return "done"
        if phase == name and (waiting or done):
            return "active" if not finished else "done"
        if done:
            return "done" if done >= total else "active"
        if name == "security" and phase in ("firewall", "fill"):
            return "done"
        if name == "firewall" and phase == "fill":
            return "done"
        return "pending"

    security_state = "done" if security_done >= len(PHASE1_STEPS) and PHASE1_STEPS else state("security", security_done, len(PHASE1_STEPS), False)
    if phase == "security" and not waiting and security_done < len(PHASE1_STEPS):
        security_state = "active"
    firewall_state = "pending"
    if phase == "firewall":
        firewall_state = "active"
    elif phase == "fill" or (firewall_done >= len(PHASE2_STEPS) and PHASE2_STEPS):
        firewall_state = "done"
    fill_state = "done" if fill_done or phase == "fill" else "pending"
    return [
        {"id": "security", "label": "Security", "state": security_state, "released": security_done, "total": len(PHASE1_STEPS)},
        {"id": "firewall", "label": "Firewall", "state": firewall_state, "released": firewall_done, "total": len(PHASE2_STEPS)},
        {"id": "fill", "label": "Fill", "state": fill_state, "released": 1 if fill_state == "done" else 0, "total": 1},
    ]


def _detail(status: str, phase: str | None, step: str | None, fault: str | None) -> str:
    if fault:
        return fault
    if status == "unconfigured":
        return "Set the REST credentials on the server to run the cascade."
    if status == "idle":
        return (
            "Start clears fill, security, and firewall. "
            "Phase 1 then locks Medium in DC01 through DC04, one name every 10 seconds. "
            "M01 and M03 stay in DC05."
        )
    if status == "paused":
        return "The cascade stopped mid-release. Reset clears fill, security, and firewall."
    if status == "gate" and phase == "security":
        return (
            "Phase 1 is on. Good releases the firewall: Small in DC01, Small in DC02, "
            "then Medium. Bad clears the lock."
        )
    if status == "gate" and phase == "firewall":
        return "Phase 2 is on. Good fills every box that has the lock and the firewall. Bad removes the firewall and keeps the lock."
    if status == "complete":
        return "Fill is on where security and the firewall are both on. The subscript stays 2."
    if phase == "firewall":
        return "Firewall · " + (step or "")
    return "Security · " + (step or "")


def _view() -> dict[str, Any]:
    """Read the three flags and the in-process timer. Does not write."""
    cfg = api_config()
    with _lock:
        phase = _phase
        waiting = _waiting
        fault = _fault
        scheduled = _timer is not None and _timer.is_alive()
        remaining = None
        if scheduled and _next_at is not None:
            remaining = max(0, int((_next_at - time.monotonic()) * 1000))
    base = {
        "key": FLAG_SECURITY,
        "stageMs": STAGE_MS,
        "flagUrl": flag_console_url(cfg.get("projectKey"), cfg.get("environmentKey"), FLAG_SECURITY),
        "securitySteps": [_label(step) for step in PHASE1_STEPS],
        "firewallSteps": [_label(step) for step in PHASE2_STEPS],
    }
    if not cfg["configured"]:
        rows = _phase_rows(0, 0, False, None, False)
        return {
            **base,
            **cfg,
            "status": "unconfigured",
            "phase": None,
            "step": None,
            "scheduled": False,
            "remainingMs": None,
            "phases": rows,
            "detail": _detail("unconfigured", None, None, None),
        }
    try:
        _security_flag, security_env, _project, _environment = _fetch(FLAG_SECURITY)
        _firewall_flag, firewall_env, _project, _environment = _fetch(FLAG_FIREWALL)
        _fill_flag, fill_env, _project, _environment = _fetch(FLAG_FILL)
    except Exception as exc:
        rows = _phase_rows(0, 0, False, None, False)
        return {
            **base,
            **cfg,
            "status": "unconfigured",
            "phase": None,
            "step": None,
            "scheduled": scheduled,
            "remainingMs": remaining,
            "phases": rows,
            "detail": str(exc),
            "error": str(exc),
        }
    security_done = _released(security_env, _SECURITY_PREFIX, PHASE1_STEPS)
    firewall_done = _released(firewall_env, _FIREWALL_PREFIX, PHASE2_STEPS)
    fill_done = _released(fill_env, _FILL_PREFIX, FILL_STEPS)
    fill_on = len(fill_done) >= len(FILL_STEPS) and bool(FILL_STEPS)
    if phase is None and not scheduled:
        if fill_on:
            phase = "fill"
            waiting = False
        elif len(firewall_done) >= len(PHASE2_STEPS) and firewall_done:
            phase, waiting = "firewall", True
        elif firewall_done:
            phase, waiting = "firewall", False
        elif len(security_done) >= len(PHASE1_STEPS) and security_done:
            phase, waiting = "security", True
        elif security_done:
            phase, waiting = "security", False
    if phase == "fill" or fill_on:
        status = "complete"
        phase = "fill"
        step = None
    elif waiting and phase in ("security", "firewall"):
        status = "gate"
        current = firewall_done if phase == "firewall" else security_done
        step = _label(current[-1] if current else None)
    elif phase in ("security", "firewall") and scheduled:
        status = "running"
        current = firewall_done if phase == "firewall" else security_done
        step = _label(current[-1] if current else None)
    elif phase in ("security", "firewall"):
        status = "paused"
        current = firewall_done if phase == "firewall" else security_done
        step = _label(current[-1] if current else None)
    else:
        status = "idle"
        step = None
    active_key = {"security": FLAG_SECURITY, "firewall": FLAG_FIREWALL, "fill": FLAG_FILL}.get(phase or "", FLAG_SECURITY)
    rows = _phase_rows(len(security_done), len(firewall_done), fill_on, phase if status != "idle" else None, waiting)
    return {
        **base,
        **cfg,
        "key": active_key,
        "flagUrl": flag_console_url(cfg.get("projectKey"), cfg.get("environmentKey"), active_key),
        "status": status,
        "phase": phase if status != "idle" else None,
        "step": step,
        "scheduled": scheduled,
        "remainingMs": remaining,
        "phases": rows,
        "detail": _detail(status, phase, step, fault),
        "fault": fault,
    }


def cascade_status() -> dict[str, Any]:
    """The card on the Cascade tab. Phase, latest name, and the gate."""
    return _view()


def _advance() -> None:
    """Write the next name. Called by the timer, not by a click."""
    global _fault, _phase, _waiting
    with _lock:
        phase = _phase
        if phase not in ("security", "firewall") or _waiting:
            _cancel_timer()
            return
        try:
            if phase == "security":
                flag_key, prefix, steps = FLAG_SECURITY, _SECURITY_PREFIX, PHASE1_STEPS
            else:
                flag_key, prefix, steps = FLAG_FIREWALL, _FIREWALL_PREFIX, PHASE2_STEPS
            _flag, env, _project, _environment = _fetch(flag_key)
            done = {_step_id(step) for step in _released(env, prefix, steps)}
            nxt = next((step for step in steps if _step_id(step) not in done), None)
            if nxt is None:
                _waiting = True
                _cancel_timer()
                _fault = None
                return
            _add_step(flag_key, nxt, prefix, "21-tenant-datacenters: cascade " + prefix + _step_id(nxt))
            done.add(_step_id(nxt))
            _fault = None
            if any(_step_id(step) not in done for step in steps):
                _arm_timer()
            else:
                _waiting = True
                _cancel_timer()
        except Exception as exc:
            _fault = str(exc)
            _cancel_timer()


def start_cascade() -> dict[str, Any]:
    """Clear the three flags, then lock the first Medium name in this phase.

    Later names follow every 10 seconds. The first step lands on this call.
    """
    global _fault, _phase, _waiting
    if not PHASE1_STEPS:
        raise RuntimeError("Cascade phase 1 has no Medium tenants in DC01 through DC04.")
    with _lock:
        _cancel_timer()
        _fault = None
        _phase = None
        _waiting = False
        _clear_three()
        first = PHASE1_STEPS[0]
        _turn_on(FLAG_SECURITY, first, _SECURITY_PREFIX, "21-tenant-datacenters: start cascade security")
        _phase = "security"
        _waiting = False
        if len(PHASE1_STEPS) > 1:
            _arm_timer()
        else:
            _waiting = True
    return cascade_status()


def good_cascade() -> dict[str, Any]:
    """Leave the gate. Phase 1 starts the firewall. Phase 2 turns fill on."""
    global _fault, _phase, _waiting
    with _lock:
        view_phase = _phase
        waiting = _waiting
        if not waiting or view_phase not in ("security", "firewall"):
            # The timer is gone after a restart. Trust the flags.
            status = _view_unlocked_flags()
            view_phase = status["phase"]
            waiting = status["waiting"]
        if not waiting or view_phase not in ("security", "firewall"):
            raise ValueError("The cascade is not waiting at a gate.")
        _fault = None
        _cancel_timer()
        if view_phase == "security":
            if not PHASE2_STEPS:
                raise RuntimeError("Cascade phase 2 has no Medium tenants in DC01 and DC02.")
            first = PHASE2_STEPS[0]
            _turn_on(FLAG_FIREWALL, first, _FIREWALL_PREFIX, "21-tenant-datacenters: start cascade firewall")
            _phase = "firewall"
            _waiting = len(PHASE2_STEPS) == 1
            if len(PHASE2_STEPS) > 1:
                _arm_timer()
        else:
            _enable_fill(FILL_STEPS)
            _phase = "fill"
            _waiting = False
    return cascade_status()


def _view_unlocked_flags() -> dict[str, str | bool | None]:
    """Caller holds _lock. Used when memory was cleared but the rules remain."""
    try:
        _security_flag, security_env, _project, _environment = _fetch(FLAG_SECURITY)
        _firewall_flag, firewall_env, _project, _environment = _fetch(FLAG_FIREWALL)
        _fill_flag, fill_env, _project, _environment = _fetch(FLAG_FILL)
    except Exception:
        return {"phase": None, "waiting": False}
    if len(_released(fill_env, _FILL_PREFIX, FILL_STEPS)) >= len(FILL_STEPS) and FILL_STEPS:
        return {"phase": "fill", "waiting": False}
    firewall_done = _released(firewall_env, _FIREWALL_PREFIX, PHASE2_STEPS)
    if len(firewall_done) >= len(PHASE2_STEPS) and firewall_done:
        return {"phase": "firewall", "waiting": True}
    security_done = _released(security_env, _SECURITY_PREFIX, PHASE1_STEPS)
    if len(security_done) >= len(PHASE1_STEPS) and security_done:
        return {"phase": "security", "waiting": True}
    return {"phase": None, "waiting": False}


def bad_cascade() -> dict[str, Any]:
    """Phase 1 clears the lock. Phase 2 turns the firewall off and leaves the lock."""
    global _fault, _phase, _waiting
    with _lock:
        view_phase = _phase
        waiting = _waiting
        if not waiting or view_phase not in ("security", "firewall"):
            status = _view_unlocked_flags()
            view_phase = status["phase"]
            waiting = status["waiting"]
        if not waiting or view_phase not in ("security", "firewall"):
            raise ValueError("The cascade is not waiting at a gate.")
        _cancel_timer()
        _fault = None
        if view_phase == "firewall":
            _reset_firewall()
            _phase = "security"
            _waiting = True
        else:
            reset_security_wave()
            _phase = None
            _waiting = False
    return cascade_status()


def reset_cascade() -> dict[str, Any]:
    """Stop the timer and return fill, security, and firewall to off."""
    global _fault, _phase, _waiting
    with _lock:
        _cancel_timer()
        _fault = None
        _phase = None
        _waiting = False
        _clear_three()
    return cascade_status()
