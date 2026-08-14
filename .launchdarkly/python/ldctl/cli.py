"""CLI entry: validate | status | report | discover | instrument."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import LdClient, api_config_from_env
from .discover import build_discover_report, discover_to_json, format_discover
from .instrument import (
    apply_comments,
    format_instrument_plan,
    merge_inventory_from_hits,
    plan_instrument,
)
from .inventory import find_ld_root, load_inventory, validate_inventory
from .report import collect_status, filter_rows, format_table, rows_to_dicts
from .scan import scan_repository, repo_root_from_ld


def _add_status_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    parser.add_argument("--on", action="store_true", help="Only resources that are on in the env")
    parser.add_argument("--off", action="store_true", help="Only resources that are off in the env")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        dest="tags",
        help="Filter by live tag (repeatable; AND)",
    )
    parser.add_argument(
        "--kind",
        choices=("flag", "agent_config", "metric", "model_config"),
        help="Filter by resource kind",
    )
    parser.add_argument("--key", dest="key_substr", help="Substring match on resource key")
    parser.add_argument(
        "--example",
        dest="example_stub",
        help="(stub) Filter by inventory example path — not implemented yet",
    )
    parser.add_argument(
        "--state",
        dest="state_stub",
        choices=("present", "missing", "drift", "error"),
        help="(stub) Filter by desired-vs-actual state — not implemented yet",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ldctl",
        description="LaunchDarkly inventory visibility (validate / status / discover / instrument).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Path to .launchdarkly directory (default: discover from cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate inventory YAML schema and example paths")

    p_status = sub.add_parser("status", help="Compare inventory to live LaunchDarkly state")
    _add_status_filters(p_status)

    p_report = sub.add_parser("report", help="Alias for status (optional JSON)")
    _add_status_filters(p_report)

    p_discover = sub.add_parser(
        "discover",
        help="Find flag/AI Config keys in the repo vs inventory (both gap directions)",
    )
    p_discover.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    p_instr = sub.add_parser(
        "instrument",
        help="Plan/apply LaunchDarkly comments on py/node/java evaluation sites",
    )
    p_instr.add_argument(
        "--write",
        action="store_true",
        help="Apply comments and merge missing keys into inventory (default: dry-run)",
    )

    args = parser.parse_args(argv)

    try:
        root = args.root.resolve() if args.root else find_ld_root()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inv = load_inventory(root)

    if args.command == "validate":
        issues = validate_inventory(inv)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        for issue in issues:
            print(f"{issue.severity}: {issue.path}: {issue.message}")
        if not issues:
            print(
                f"ok: inventory valid "
                f"({len(inv.flags)} flags, {len(inv.agent_configs)} agent configs, "
                f"{len(inv.metrics)} metrics)"
            )
            return 0
        print(
            f"validate: {len(errors)} error(s), {len(warnings)} warning(s)",
            file=sys.stderr,
        )
        return 1 if errors else 0

    if args.command == "discover":
        hits, missing_inv, missing_repo = build_discover_report(inv)
        if args.json:
            print(json.dumps(discover_to_json(hits, missing_inv, missing_repo), indent=2))
        else:
            print(format_discover(missing_inv, missing_repo, hit_count=len(hits)))
        return 1 if (missing_inv or missing_repo) else 0

    if args.command == "instrument":
        items, eval_hits = plan_instrument(inv)
        print(format_instrument_plan(items, write=args.write))
        if not args.write:
            print("\n(re-run with --write to apply comments and merge inventory stubs)")
            return 0
        n_files = apply_comments(inv, items)
        # Merge from all hits (evaluation + provisioning) so declare covers both
        all_hits = scan_repository(repo_root_from_ld(inv.root))
        added = merge_inventory_from_hits(inv, all_hits)
        print(f"\nwrote comments in {n_files} file(s); inventory added keys: {added or '(none)'}")
        return 0

    # status / report
    stub_warned = False
    if getattr(args, "example_stub", None):
        print("warning: --example is a stub and is ignored in v1", file=sys.stderr)
        stub_warned = True
    if getattr(args, "state_stub", None):
        print("warning: --state is a stub and is ignored in v1", file=sys.stderr)
        stub_warned = True
    if stub_warned:
        pass

    if args.on and args.off:
        print("error: --on and --off are mutually exclusive", file=sys.stderr)
        return 2

    cfg = api_config_from_env(inv.project)
    client = LdClient(cfg)
    rows = collect_status(client, inv)
    rows = filter_rows(
        rows,
        on=bool(args.on) or None,
        off=bool(args.off),
        tags=list(args.tags or []),
        kind=args.kind,
        key_substr=args.key_substr,
    )

    if args.json:
        payload = {
            "project_key": cfg.project_key,
            "environment_key": cfg.environment_key,
            "resources": rows_to_dicts(rows),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(rows, project=cfg.project_key, environment=cfg.environment_key))

    bad = [r for r in rows if r.state in ("missing", "error", "drift")]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
