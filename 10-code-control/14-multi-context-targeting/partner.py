"""Multi-context evaluation helpers for 14-multi-context-targeting.

LaunchDarkly: one variation call with kind multi (user + organization).
https://launchdarkly.com/docs/home/flags/multi-contexts
Keywords: multi-context, context kinds, targeting rules
"""

from __future__ import annotations

from typing import Any

from ldclient import Context

FLAG_PARTNER_BADGE = "show-partner-org-badge"

ORG_LABELS = {
    "acme": "Acme",
    "globex": "Globex",
}

# Oracle for collect-results.py only — application evaluate_* must not use this.
EXPECTED_PARTNER = {
    ("alice", "acme"): True,
    ("alice", "globex"): False,
    ("bob", "acme"): False,
    ("bob", "globex"): True,
}


def _reason_payload(reason: Any) -> dict[str, Any]:
    """Normalize SDK EvaluationReason objects into JSON-friendly dicts."""
    if reason is None:
        return {"kind": "UNKNOWN"}
    if isinstance(reason, dict):
        return reason
    payload: dict[str, Any] = {"kind": getattr(reason, "kind", str(reason))}
    for attr in ("rule_index", "rule_id", "prerequisite_key", "error_kind"):
        value = getattr(reason, attr, None)
        if value is not None:
            payload[attr] = value
    return payload


def normalize_username(username: str) -> str:
    """Trim and lowercase the user context key."""
    value = (username or "").strip().lower()
    if not value:
        raise ValueError("username is required")
    return value


def normalize_org(org: str | None) -> str:
    """Validate organization key (acme or globex)."""
    value = (org or "").strip().lower()
    if value not in ORG_LABELS:
        raise ValueError("org must be acme or globex")
    return value


def build_multi_context(username: str, org: str) -> Context:
    """Build user + organization multi-context. Do not put org on the user.

    LaunchDarkly: Context.create_multi — associated contexts, kind multi
    https://launchdarkly.com/docs/sdk/features/user-context
    """
    user_key = normalize_username(username)
    org_key = normalize_org(org)
    user = Context.builder(user_key).kind("user").build()
    organization = (
        Context.builder(org_key)
        .kind("organization")
        .set("name", ORG_LABELS[org_key])
        .build()
    )
    return Context.create_multi(user, organization)


def evaluate_partner(client: Any, username: str, org: str | None) -> dict[str, Any]:
    """Evaluate show-partner-org-badge. The SDK variation is the source of truth."""
    user_key = normalize_username(username)
    org_key = normalize_org(org)
    context = build_multi_context(user_key, org_key)
    detail = (
        client.variation_detail(FLAG_PARTNER_BADGE, context, False)
        if client is not None
        else None
    )
    partner = bool(detail.value) if detail is not None else False
    reason = _reason_payload(detail.reason) if detail is not None else {"kind": "OFFLINE"}
    variation_index = detail.variation_index if detail is not None else None
    return {
        "username": user_key,
        "org": org_key,
        "orgLabel": ORG_LABELS[org_key],
        "partner": partner,
        "ldContext": {
            "kind": "multi",
            "user": {"key": user_key},
            "organization": {"key": org_key, "name": ORG_LABELS[org_key]},
            "note": "Org is a separate context kind, not a user attribute.",
        },
        "variationIndex": variation_index,
        "reason": reason,
    }
