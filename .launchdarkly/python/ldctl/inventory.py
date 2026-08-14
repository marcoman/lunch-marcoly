"""Load and validate .launchdarkly inventory YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FLAG_FIELDS = ("key", "kind")
REQUIRED_AGENT_FIELDS = ("key",)
REQUIRED_METRIC_FIELDS = ("key",)
KNOWN_FLAG_KINDS = frozenset({"boolean", "string", "number", "json"})


@dataclass
class ValidationIssue:
    severity: str  # error | warning
    path: str
    message: str


@dataclass
class Inventory:
    root: Path
    project: dict[str, Any]
    flags: list[dict[str, Any]] = field(default_factory=list)
    agent_configs: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    guarded_rollouts: list[dict[str, Any]] = field(default_factory=list)


def find_ld_root(start: Path | None = None) -> Path:
    """Walk up from start (or cwd) for a directory containing project.yaml."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "project.yaml").is_file() and (candidate / "inventory").is_dir():
            return candidate
        nested = candidate / ".launchdarkly"
        if (nested / "project.yaml").is_file() and (nested / "inventory").is_dir():
            return nested
    raise FileNotFoundError(
        "Could not find .launchdarkly/ (expected project.yaml + inventory/). "
        "Run from the repo root or pass --root."
    )


def _load_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"missing inventory file: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if data is not None else {}


def load_inventory(root: Path) -> Inventory:
    root = root.resolve()
    project = _load_yaml(root / "project.yaml")
    flags_doc = _load_yaml(root / "inventory" / "flags.yaml")
    agents_doc = _load_yaml(root / "inventory" / "agent-configs.yaml")
    metrics_doc = _load_yaml(root / "inventory" / "metrics.yaml")
    plans_path = root / "plans" / "guarded-rollouts.yaml"
    plans_doc = _load_yaml(plans_path) if plans_path.is_file() else {}

    return Inventory(
        root=root,
        project=project if isinstance(project, dict) else {},
        flags=list(flags_doc.get("flags") or []),
        agent_configs=list(agents_doc.get("agent_configs") or []),
        metrics=list(metrics_doc.get("metrics") or []),
        guarded_rollouts=list(plans_doc.get("guarded_rollouts") or []),
    )


def _repo_root(ld_root: Path) -> Path:
    # .launchdarkly lives at repo root
    return ld_root.parent if ld_root.name == ".launchdarkly" else ld_root


def validate_inventory(inv: Inventory) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    repo = _repo_root(inv.root)

    if not inv.project.get("project_key"):
        issues.append(
            ValidationIssue("warning", "project.yaml", "project_key is empty; set LD_PROJECT_KEY at runtime")
        )
    if not inv.project.get("environment_key"):
        issues.append(
            ValidationIssue(
                "warning", "project.yaml", "environment_key is empty; set LD_ENVIRONMENT_KEY at runtime"
            )
        )

    flag_keys: set[str] = set()
    for i, flag in enumerate(inv.flags):
        loc = f"inventory/flags.yaml[{i}]"
        if not isinstance(flag, dict):
            issues.append(ValidationIssue("error", loc, "entry must be a mapping"))
            continue
        for field_name in REQUIRED_FLAG_FIELDS:
            if not flag.get(field_name):
                issues.append(ValidationIssue("error", loc, f"missing required field '{field_name}'"))
        key = flag.get("key")
        if isinstance(key, str):
            if key in flag_keys:
                issues.append(ValidationIssue("error", loc, f"duplicate flag key '{key}'"))
            flag_keys.add(key)
        kind = flag.get("kind")
        if kind and kind not in KNOWN_FLAG_KINDS:
            issues.append(
                ValidationIssue(
                    "error",
                    loc,
                    f"unknown kind '{kind}' (expected one of {sorted(KNOWN_FLAG_KINDS)})",
                )
            )
        _check_examples(issues, loc, flag.get("examples"), repo)

    agent_keys: set[str] = set()
    for i, cfg in enumerate(inv.agent_configs):
        loc = f"inventory/agent-configs.yaml[{i}]"
        if not isinstance(cfg, dict):
            issues.append(ValidationIssue("error", loc, "entry must be a mapping"))
            continue
        for field_name in REQUIRED_AGENT_FIELDS:
            if not cfg.get(field_name):
                issues.append(ValidationIssue("error", loc, f"missing required field '{field_name}'"))
        key = cfg.get("key")
        if isinstance(key, str):
            if key in agent_keys:
                issues.append(ValidationIssue("error", loc, f"duplicate agent config key '{key}'"))
            agent_keys.add(key)
        _check_examples(issues, loc, cfg.get("examples"), repo)
        for j, var in enumerate(cfg.get("variations") or []):
            if not isinstance(var, dict) or not var.get("key"):
                issues.append(
                    ValidationIssue("error", f"{loc}.variations[{j}]", "variation needs a key")
                )

    metric_keys: set[str] = set()
    for i, metric in enumerate(inv.metrics):
        loc = f"inventory/metrics.yaml[{i}]"
        if not isinstance(metric, dict):
            issues.append(ValidationIssue("error", loc, "entry must be a mapping"))
            continue
        for field_name in REQUIRED_METRIC_FIELDS:
            if not metric.get(field_name):
                issues.append(ValidationIssue("error", loc, f"missing required field '{field_name}'"))
        key = metric.get("key")
        if isinstance(key, str):
            if key in metric_keys:
                issues.append(ValidationIssue("error", loc, f"duplicate metric key '{key}'"))
            metric_keys.add(key)
        _check_examples(issues, loc, metric.get("examples"), repo)

    for i, plan in enumerate(inv.guarded_rollouts):
        loc = f"plans/guarded-rollouts.yaml[{i}]"
        if not isinstance(plan, dict):
            issues.append(ValidationIssue("error", loc, "entry must be a mapping"))
            continue
        flag_key = plan.get("flag_key")
        if flag_key and flag_key not in flag_keys:
            issues.append(
                ValidationIssue(
                    "warning",
                    loc,
                    f"flag_key '{flag_key}' not listed in inventory/flags.yaml",
                )
            )
        for mk in plan.get("metric_keys") or []:
            if mk not in metric_keys:
                issues.append(
                    ValidationIssue(
                        "warning",
                        loc,
                        f"metric_key '{mk}' not listed in inventory/metrics.yaml",
                    )
                )
        _check_examples(issues, loc, plan.get("examples"), repo)

    return issues


def _check_examples(
    issues: list[ValidationIssue],
    loc: str,
    examples: Any,
    repo: Path,
) -> None:
    if examples is None:
        return
    if not isinstance(examples, list):
        issues.append(ValidationIssue("error", loc, "examples must be a list"))
        return
    for j, ex in enumerate(examples):
        if isinstance(ex, str):
            rel = ex
        elif isinstance(ex, dict) and ex.get("path"):
            rel = str(ex["path"])
        else:
            issues.append(ValidationIssue("error", f"{loc}.examples[{j}]", "need path string or {path: …}"))
            continue
        full = repo / rel
        if not full.exists():
            issues.append(
                ValidationIssue("error", f"{loc}.examples[{j}]", f"example path does not exist: {rel}")
            )
