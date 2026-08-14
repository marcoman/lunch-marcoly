"""Instrument evaluation sites with LaunchDarkly comments; optional inventory merge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .comments import (
    comment_has_key,
    comment_style_for_path,
    format_ai_config_comment,
    format_flag_comment,
    project_settings,
)
from .inventory import Inventory
from .scan import Hit, _example_path_from_rel, repo_root_from_ld, scan_repository


@dataclass
class PlanItem:
    path: str
    line: int
    key: str
    resource: str
    action: str  # insert | skip
    reason: str = ""


def _inv_meta(inv: Inventory) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    for f in inv.flags:
        k = f.get("key")
        if isinstance(k, str):
            meta[k] = {
                "resource": "flag",
                "name": f.get("name") or "",
                "kind": f.get("kind") or "",
                "mode": "",
            }
    for c in inv.agent_configs:
        k = c.get("key")
        if isinstance(k, str):
            meta[k] = {
                "resource": "ai-config",
                "name": c.get("name") or "",
                "kind": "",
                "mode": c.get("mode") or "completion",
            }
    return meta


def plan_instrument(inv: Inventory) -> tuple[list[PlanItem], list[Hit]]:
    """Plan comment inserts for evaluation hits only."""
    repo = repo_root_from_ld(inv.root)
    hits = [h for h in scan_repository(repo) if h.role == "evaluation"]
    meta = _inv_meta(inv)
    # One plan item per file:line:key (definitions)
    items: list[PlanItem] = []
    for h in hits:
        path = repo / h.path
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            items.append(PlanItem(h.path, h.line, h.key, h.resource, "skip", "unreadable"))
            continue
        idx = h.line - 1
        if idx < 0 or idx >= len(lines):
            items.append(PlanItem(h.path, h.line, h.key, h.resource, "skip", "line out of range"))
            continue
        if comment_has_key(lines, h.key, around=idx):
            items.append(PlanItem(h.path, h.line, h.key, h.resource, "skip", "already annotated"))
            continue
        items.append(PlanItem(h.path, h.line, h.key, h.resource, "insert", ""))
    return items, hits


def format_instrument_plan(items: list[PlanItem], *, write: bool) -> str:
    mode = "WRITE" if write else "DRY-RUN"
    lines = [f"instrument ({mode})", ""]
    inserts = [i for i in items if i.action == "insert"]
    skips = [i for i in items if i.action == "skip"]
    for i in inserts:
        lines.append(f"  + {i.path}:{i.line}  {i.resource} {i.key}")
    if not inserts:
        lines.append("  (no comment inserts)")
    lines.append("")
    lines.append(f"summary: insert={len(inserts)}  skip={len(skips)}")
    return "\n".join(lines)


def apply_comments(inv: Inventory, items: list[PlanItem]) -> int:
    """Apply inserts; return number of files modified."""
    repo = repo_root_from_ld(inv.root)
    project_key, api_host = project_settings(inv.project)
    meta = _inv_meta(inv)

    # Group inserts by path, apply bottom-up so line numbers stay valid
    by_path: dict[str, list[PlanItem]] = {}
    for item in items:
        if item.action != "insert":
            continue
        by_path.setdefault(item.path, []).append(item)

    modified = 0
    for rel, path_items in by_path.items():
        path = repo / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        style = comment_style_for_path(rel)
        for item in sorted(path_items, key=lambda x: x.line, reverse=True):
            idx = item.line - 1
            if comment_has_key(lines, item.key, around=idx):
                continue
            info = meta.get(item.key, {})
            resource = item.resource or info.get("resource") or "flag"
            # Prefer hit kind from a fresh scan on this line if inventory empty
            kind = str(info.get("kind") or "")
            name = str(info.get("name") or "")
            mode = str(info.get("mode") or "")
            if resource == "ai-config":
                block = format_ai_config_comment(
                    key=item.key,
                    name=name,
                    mode=mode or "completion",
                    project_key=project_key,
                    api_host=api_host,
                    style=style,
                )
            else:
                # Fill kind from scan if needed
                if not kind:
                    from .scan import scan_repository

                    for h in scan_repository(repo):
                        if h.path == rel and h.line == item.line and h.key == item.key:
                            kind = h.kind_guess
                            break
                block = format_flag_comment(
                    key=item.key,
                    name=name,
                    kind=kind,
                    project_key=project_key,
                    api_host=api_host,
                    style=style,
                )
            # Preserve indentation of target line
            indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
            indented = [indent + b if b else b for b in block]
            lines[idx:idx] = indented + ([""] if lines[idx].strip() else [])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        modified += 1
    return modified


def _load_yaml_doc(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _dump_yaml(path: Path, doc: dict[str, Any], *, header: str = "") -> None:
    with path.open("w", encoding="utf-8") as fh:
        if header:
            fh.write(header.rstrip() + "\n\n")
        yaml.safe_dump(
            doc,
            fh,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=88,
        )


def merge_inventory_from_hits(inv: Inventory, hits: list[Hit]) -> list[str]:
    """
    Append missing flag/ai-config keys from hits.
    Returns list of added keys. Never deletes; does not overwrite name/notes.
    """
    root = inv.root
    flags_path = root / "inventory" / "flags.yaml"
    agents_path = root / "inventory" / "agent-configs.yaml"
    flags_doc = _load_yaml_doc(flags_path)
    agents_doc = _load_yaml_doc(agents_path)
    flags = list(flags_doc.get("flags") or [])
    agents = list(agents_doc.get("agent_configs") or [])
    flag_keys = {f.get("key") for f in flags if isinstance(f, dict)}
    agent_keys = {c.get("key") for c in agents if isinstance(c, dict)}

    added: list[str] = []
    # Prefer evaluation hits for stubs; still add from provisioning-only keys
    by_key: dict[str, list[Hit]] = {}
    for h in hits:
        by_key.setdefault(h.key, []).append(h)

    for key, key_hits in sorted(by_key.items()):
        resources = [h.resource for h in key_hits]
        resource = max(set(resources), key=resources.count)
        example_paths = sorted(
            {
                _example_path_from_rel(h.path)
                for h in key_hits
                if _example_path_from_rel(h.path)
            }
        )
        sources = []
        for h in key_hits[:5]:
            sources.append({"path": h.path, "role": h.role})

        if resource == "ai-config":
            if key in agent_keys:
                # merge sources/examples lightly
                for c in agents:
                    if isinstance(c, dict) and c.get("key") == key:
                        _merge_examples_sources(c, example_paths, sources)
                continue
            entry: dict[str, Any] = {
                "key": key,
                "name": "",
                "mode": "completion",
                "examples": [{"path": p} for p in example_paths],
                "sources": sources,
            }
            agents.append(entry)
            agent_keys.add(key)
            added.append(key)
        else:
            if key in flag_keys:
                for f in flags:
                    if isinstance(f, dict) and f.get("key") == key:
                        _merge_examples_sources(f, example_paths, sources)
                continue
            kind = next((h.kind_guess for h in key_hits if h.kind_guess), "") or "boolean"
            entry = {
                "key": key,
                "name": "",
                "kind": kind,
                "examples": [{"path": p} for p in example_paths],
                "sources": sources,
            }
            flags.append(entry)
            flag_keys.add(key)
            added.append(key)

    flags_doc["flags"] = flags
    agents_doc["agent_configs"] = agents
    _dump_yaml(
        flags_path,
        flags_doc,
        header=(
            "# Desired feature-flag inventory for lunch-marcoly examples.\n"
            "# Visibility only — provisioning lives in each example's rest/ or terraform/.\n"
            "# sources: filled by ldctl instrument --write (evaluation + provisioning hits)."
        ),
    )
    _dump_yaml(
        agents_path,
        agents_doc,
        header=(
            "# Desired AgentControl (AI Config) inventory.\n"
            "# LaunchDarkly: AgentControl · AI Configs\n"
            "# https://docs.launchdarkly.com/home/ai-configs\n"
            "# sources: filled by ldctl instrument --write."
        ),
    )
    return added


def _merge_examples_sources(
    entry: dict[str, Any],
    example_paths: list[str],
    sources: list[dict[str, str]],
) -> None:
    existing_ex = entry.get("examples") or []
    have = set()
    for ex in existing_ex:
        if isinstance(ex, str):
            have.add(ex)
        elif isinstance(ex, dict) and ex.get("path"):
            have.add(str(ex["path"]))
    for p in example_paths:
        if p not in have:
            existing_ex.append({"path": p})
            have.add(p)
    entry["examples"] = existing_ex

    existing_src = list(entry.get("sources") or [])
    have_src = {(s.get("path"), s.get("role")) for s in existing_src if isinstance(s, dict)}
    for s in sources:
        sig = (s.get("path"), s.get("role"))
        if sig not in have_src:
            existing_src.append(s)
            have_src.add(sig)
    entry["sources"] = existing_src
