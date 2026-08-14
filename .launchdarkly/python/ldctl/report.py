"""Build desired-vs-actual status rows for inventory resources."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .api import LdClient


@dataclass
class StatusRow:
    kind: str
    key: str
    desired: str
    actual: str
    state: str  # present | missing | drift | error
    detail: str = ""
    on: str = ""  # on | off | n/a | ""
    tags: str = ""


def _flag_kind_from_variations(variations: list[Any]) -> str | None:
    if not variations:
        return None
    values = [v.get("value") if isinstance(v, dict) else None for v in variations]
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "number"
    if all(isinstance(v, str) for v in values):
        return "string"
    if all(isinstance(v, (dict, list)) for v in values):
        return "json"
    return "mixed"


def _on_str(on: Any) -> str:
    if on is True:
        return "on"
    if on is False:
        return "off"
    return "n/a"


def _tags_str(tags: Any) -> str:
    if not isinstance(tags, list):
        return ""
    return ",".join(str(t) for t in tags)


def collect_status(client: LdClient, inv: Any) -> list[StatusRow]:
    rows: list[StatusRow] = []
    env = client.cfg.environment_key

    for flag in inv.flags:
        key = flag["key"]
        desired_kind = flag.get("kind") or "?"
        result = client.get_flag(key)
        if result.status == 404:
            rows.append(
                StatusRow(
                    "flag",
                    key,
                    desired_kind,
                    "—",
                    "missing",
                    "not found in project",
                )
            )
            continue
        if not result.ok or not isinstance(result.body, dict):
            rows.append(
                StatusRow(
                    "flag",
                    key,
                    desired_kind,
                    "—",
                    "error",
                    result.error or f"HTTP {result.status}",
                )
            )
            continue

        body = result.body
        actual_kind = _flag_kind_from_variations(body.get("variations") or []) or "?"
        env_cfg = (body.get("environments") or {}).get(env) or {}
        on = _on_str(env_cfg.get("on"))
        tags = _tags_str(body.get("tags"))
        detail_parts = [f"env={env}:{on}", f"variations={len(body.get('variations') or [])}"]
        state = "present"
        if desired_kind and actual_kind not in (desired_kind, "mixed", "?"):
            if flag.get("notes") and "boolean" in str(flag.get("notes")) and "string" in str(
                flag.get("notes")
            ):
                detail_parts.append(f"actual_kind={actual_kind} (known multi-kind key)")
            else:
                state = "drift"
                detail_parts.append(f"kind desired={desired_kind} actual={actual_kind}")
        rows.append(
            StatusRow(
                "flag",
                key,
                desired_kind,
                actual_kind,
                state,
                "; ".join(detail_parts),
                on=on,
                tags=tags,
            )
        )

    for cfg in inv.agent_configs:
        key = cfg["key"]
        desired = cfg.get("mode") or "completion"
        result = client.get_ai_config(key)
        if result.status == 404:
            rows.append(StatusRow("agent_config", key, desired, "—", "missing", "not found"))
            continue
        if not result.ok or not isinstance(result.body, dict):
            rows.append(
                StatusRow(
                    "agent_config",
                    key,
                    desired,
                    "—",
                    "error",
                    result.error or f"HTTP {result.status}",
                )
            )
            continue

        body = result.body
        actual_mode = body.get("mode") or "?"
        tags = _tags_str(body.get("tags"))
        var_keys = {v.get("key") for v in (body.get("variations") or []) if isinstance(v, dict)}
        desired_vars = {v.get("key") for v in (cfg.get("variations") or []) if isinstance(v, dict)}
        missing_vars = sorted(desired_vars - var_keys)
        detail = f"variations={len(var_keys)}"
        state = "present"
        if desired and actual_mode != desired:
            state = "drift"
            detail += f"; mode desired={desired} actual={actual_mode}"
        if missing_vars:
            state = "drift"
            detail += f"; missing variations: {', '.join(missing_vars)}"

        on = "n/a"
        targeting = client.get_ai_config_targeting(key)
        if targeting.ok and isinstance(targeting.body, dict):
            env_t = (targeting.body.get("environments") or {}).get(env) or {}
            on = _on_str(env_t.get("on"))
            detail += f"; env={env}:{on}"

        rows.append(
            StatusRow(
                "agent_config",
                key,
                desired,
                str(actual_mode),
                state,
                detail,
                on=on,
                tags=tags,
            )
        )

        for mc in cfg.get("model_configs") or []:
            mkey = mc.get("key")
            if not mkey:
                continue
            mres = client.get_model_config(mkey)
            if mres.status == 404:
                rows.append(
                    StatusRow("model_config", mkey, mc.get("model_id") or "", "—", "missing", "")
                )
            elif not mres.ok:
                rows.append(
                    StatusRow(
                        "model_config",
                        mkey,
                        mc.get("model_id") or "",
                        "—",
                        "error",
                        mres.error or f"HTTP {mres.status}",
                    )
                )
            else:
                mid = ""
                if isinstance(mres.body, dict):
                    mid = str(mres.body.get("id") or mres.body.get("modelId") or "present")
                rows.append(
                    StatusRow("model_config", mkey, mc.get("model_id") or "", mid, "present", "")
                )

    for metric in inv.metrics:
        key = metric["key"]
        desired = metric.get("event_key") or metric.get("name") or ""
        result = client.get_metric(key)
        if result.status == 404:
            rows.append(StatusRow("metric", key, str(desired), "—", "missing", "not found"))
            continue
        if not result.ok or not isinstance(result.body, dict):
            rows.append(
                StatusRow(
                    "metric",
                    key,
                    str(desired),
                    "—",
                    "error",
                    result.error or f"HTTP {result.status}",
                )
            )
            continue
        body = result.body
        actual_event = body.get("eventKey") or ""
        tags = _tags_str(body.get("tags"))
        state = "present"
        detail = f"kind={body.get('kind') or '?'}"
        if desired and actual_event and actual_event != desired:
            state = "drift"
            detail += f"; eventKey desired={desired} actual={actual_event}"
        elif actual_event:
            detail += f"; eventKey={actual_event}"
        rows.append(
            StatusRow(
                "metric",
                key,
                str(desired),
                str(actual_event or "present"),
                state,
                detail,
                tags=tags,
            )
        )

    return rows


def filter_rows(
    rows: list[StatusRow],
    *,
    on: bool | None = None,
    off: bool = False,
    tags: list[str] | None = None,
    kind: str | None = None,
    key_substr: str | None = None,
) -> list[StatusRow]:
    out = rows
    if on:
        out = [r for r in out if r.on == "on"]
    if off:
        out = [r for r in out if r.on == "off"]
    if kind:
        out = [r for r in out if r.kind == kind]
    if key_substr:
        sub = key_substr.lower()
        out = [r for r in out if sub in r.key.lower()]
    if tags:
        want = [t.lower() for t in tags]

        def has_all(row: StatusRow) -> bool:
            have = {t.strip().lower() for t in row.tags.split(",") if t.strip()}
            return all(t in have for t in want)

        out = [r for r in out if has_all(r)]
    return out


def rows_to_dicts(rows: list[StatusRow]) -> list[dict[str, str]]:
    return [asdict(r) for r in rows]


def format_table(rows: list[StatusRow], *, project: str, environment: str) -> str:
    lines = [
        f"project={project}  environment={environment}",
        "",
    ]
    headers = ("STATE", "ON", "KIND", "KEY", "TAGS", "DETAIL")
    data = []
    for r in rows:
        tags = r.tags if len(r.tags) <= 18 else r.tags[:17] + "…"
        detail = r.detail if len(r.detail) <= 36 else r.detail[:35] + "…"
        key = r.key if len(r.key) <= 36 else r.key[:35] + "…"
        data.append((r.state, r.on or "—", r.kind, key, tags or "—", detail))

    widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    lines.append(fmt(headers))
    lines.append(fmt(tuple("-" * w for w in widths)))
    for row in data:
        lines.append(fmt(row))

    counts: dict[str, int] = {}
    for r in rows:
        counts[r.state] = counts.get(r.state, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    lines.append("")
    lines.append(f"summary: {summary or 'empty'}  shown={len(rows)}")
    return "\n".join(lines)
