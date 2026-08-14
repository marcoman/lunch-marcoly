"""Discover gaps between repository references and inventory."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .inventory import Inventory
from .scan import Hit, hits_by_key, roles_for_key, scan_repository, repo_root_from_ld


@dataclass
class GapRow:
    key: str
    resource: str
    provenance: str  # evaluation | provisioning | both | none
    paths: str


def inventory_keys(inv: Inventory) -> dict[str, str]:
    """Map key → resource type from inventory."""
    out: dict[str, str] = {}
    for f in inv.flags:
        k = f.get("key")
        if isinstance(k, str):
            out[k] = "flag"
    for c in inv.agent_configs:
        k = c.get("key")
        if isinstance(k, str):
            out[k] = "ai-config"
    return out


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def build_discover_report(inv: Inventory) -> tuple[list[Hit], list[GapRow], list[GapRow]]:
    repo = repo_root_from_ld(inv.root)
    hits = scan_repository(repo)
    by_key = hits_by_key(hits)
    inv_map = inventory_keys(inv)

    missing_from_inventory: list[GapRow] = []
    for key, key_hits in sorted(by_key.items()):
        if key in inv_map:
            continue
        # Prefer majority resource type
        resources = [h.resource for h in key_hits]
        resource = max(set(resources), key=resources.count)
        paths = "; ".join(sorted({f"{h.path}:{h.line}" for h in key_hits})[:3])
        missing_from_inventory.append(
            GapRow(key=key, resource=resource, provenance=roles_for_key(key_hits), paths=paths)
        )

    missing_from_repo: list[GapRow] = []
    for key, resource in sorted(inv_map.items()):
        if key in by_key:
            continue
        missing_from_repo.append(
            GapRow(key=key, resource=resource, provenance="none", paths="—")
        )

    return hits, missing_from_inventory, missing_from_repo


def format_discover(
    missing_from_inventory: list[GapRow],
    missing_from_repo: list[GapRow],
    *,
    hit_count: int,
) -> str:
    lines: list[str] = []
    max_w = 100

    def section(title: str, rows: list[GapRow]) -> None:
        lines.append(title)
        if not rows:
            lines.append("  (none)")
            lines.append("")
            return
        headers = ("KEY", "TYPE", "PROVENANCE", "PATHS")
        data = [
            (
                _truncate(r.key, 36),
                r.resource,
                r.provenance,
                _truncate(r.paths, 40),
            )
            for r in rows
        ]
        widths = [len(h) for h in headers]
        for row in data:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        # Cap total width ~100
        while sum(widths) + 2 * (len(widths) - 1) > max_w and max(widths) > 8:
            widths[widths.index(max(widths))] -= 1

        def fmt(row: tuple[str, ...]) -> str:
            cells = [_truncate(cell, widths[i]).ljust(widths[i]) for i, cell in enumerate(row)]
            return "  ".join(cells)

        lines.append(fmt(headers))
        lines.append(fmt(tuple("-" * w for w in widths)))
        for row in data:
            lines.append(fmt(row))
        lines.append("")

    section("In repo, not in inventory", missing_from_inventory)
    section("In inventory, not in repo", missing_from_repo)
    lines.append(
        f"summary: hits={hit_count}  "
        f"missing_from_inventory={len(missing_from_inventory)}  "
        f"missing_from_repo={len(missing_from_repo)}"
    )
    return "\n".join(lines)


def discover_to_json(
    hits: list[Hit],
    missing_from_inventory: list[GapRow],
    missing_from_repo: list[GapRow],
) -> dict[str, Any]:
    return {
        "hits": [h.to_dict() for h in hits],
        "missing_from_inventory": [asdict(r) for r in missing_from_inventory],
        "missing_from_repo": [asdict(r) for r in missing_from_repo],
    }
