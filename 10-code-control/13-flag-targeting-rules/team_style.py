"""Team-label targeting helpers for 13-flag-targeting-rules.

LaunchDarkly: targeting rules evaluate the public ``team`` context attribute.
https://launchdarkly.com/docs/home/flags/target-rules
"""

from __future__ import annotations

from typing import Any

from ldclient import Context

FLAG_TEAM_LABEL_STYLE = "configure-team-label-style"
PLAIN = "plain"

TEAM_LABELS = {
    "": "No team",
    "red": "Team Red",
    "blue": "Team Blue",
    "yellow": "Team Yellow",
}
STYLE_COLORS = {
    "plain": None,
    "colored-red": "red",
    "colored-blue": "blue",
    "colored-yellow": "yellow",
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


def normalize_team(team: str | None) -> str:
    """Validate a team query value and return its canonical form."""
    value = (team or "").strip().lower()
    if value not in TEAM_LABELS:
        raise ValueError("team must be empty, red, blue, or yellow")
    return value


def build_context(username: str, team: str) -> Context:
    """Build the user context; omit ``team`` entirely for No team.

    LaunchDarkly: ``team`` is intentionally public so evaluations appear in
    analytics and targeting rules can inspect it.
    https://launchdarkly.com/docs/home/flags/context-attributes
    """
    builder = Context.builder(username)
    if team:
        builder.set("team", team)
    return builder.build()


def evaluate_team_style(client: Any, username: str, team: str | None) -> dict[str, Any]:
    """Evaluate the string flag and return display plus evaluation details."""
    normalized_team = normalize_team(team)
    context = build_context(username, normalized_team)
    detail = (
        client.variation_detail(FLAG_TEAM_LABEL_STYLE, context, PLAIN)
        if client is not None
        else None
    )
    candidate = detail.value if detail is not None else PLAIN
    style = candidate if candidate in STYLE_COLORS else PLAIN
    css_color = STYLE_COLORS[style]
    reason = _reason_payload(detail.reason) if detail is not None else {"kind": "OFFLINE"}
    variation_index = detail.variation_index if detail is not None else None

    attributes: dict[str, str] = {}
    if normalized_team:
        attributes["team"] = normalized_team

    return {
        "team": normalized_team,
        "teamLabel": TEAM_LABELS[normalized_team],
        "style": style,
        "colored": css_color is not None,
        "cssColor": css_color,
        "ldContext": {
            "kind": "user",
            "key": username,
            "attributes": attributes,
            "teamAttribute": normalized_team or None,
            "teamOmitted": not normalized_team,
            "privateAttributes": [],
            "note": "team is public; No team omits the attribute so rules skip to fallthrough.",
        },
        "variationIndex": variation_index,
        "reason": reason,
    }
