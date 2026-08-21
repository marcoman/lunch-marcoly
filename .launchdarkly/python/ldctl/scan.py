"""Scan the repository for LaunchDarkly flag and AI Config key references."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

IGNORE_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "target",
        "build",
        "dist",
        "__pycache__",
        ".idea",
        ".cursor",
        "vendor",
    }
)

EVAL_SUFFIXES = frozenset({".py", ".js", ".mjs", ".cjs", ".java"})
PROV_SUFFIXES = frozenset({".sh", ".tf", ".json", ".hcl"})

# Likely LD keys: kebab-case with a hyphen, or VIP
KEY_LITERAL = r"(?P<key>[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+|VIP)"

# Top-level resources we care about (not variations / segments / metrics)
_FLAG_PREFIXES = ("configure-", "show-")
_AGENT_PREFIXES = ("equity-",)
_SKIP_PREFIXES = ("seg-", "grid-")  # segments, metric keys
_SKIP_KEYS = frozenset(
    {
        "baseline-analyst",
        "concise-skeptic",
        "reckless-hype",
        "none",
        "green",
    }
)

# FLAG_FOO = "key" / const FLAG_FOO = "key" / static final String FLAG_FOO = "key"
ASSIGN_FLAG_RE = re.compile(
    rf"(?P<lhs>(?:FLAG|flag)[_A-Za-z0-9]*)\s*=\s*[\"']{KEY_LITERAL}[\"']"
)
ASSIGN_CONFIG_RE = re.compile(
    rf"(?P<lhs>(?:DEFAULT_)?(?:LD_)?(?:AGENT_)?CONFIG_KEY|(?:configKey)|(?:CONFIG_KEY))"
    rf"\s*=\s*[\"']{KEY_LITERAL}[\"']"
)
# Bash : "${LD_CONFIG_KEY:=equity-briefing-completion}"
BASH_DEFAULT_RE = re.compile(
    rf"LD_(?:AGENT_)?CONFIG_KEY:=[\"']?{KEY_LITERAL}[\"']?"
)
# "key": "flag-key" (REST JSON)
JSON_KEY_RE = re.compile(rf"[\"']key[\"']\s*:\s*[\"']{KEY_LITERAL}[\"']")
# Terraform key = "flag-key"
TF_KEY_RE = re.compile(rf"\bkey\s*=\s*[\"']{KEY_LITERAL}[\"']")
# FLAG_KEY="…" / VIP_FLAG_KEY="…"
BASH_FLAG_RE = re.compile(
    rf"(?:FLAG_KEY|VIP_FLAG_KEY|LD_CONFIG_KEY)\s*=\s*[\"']{KEY_LITERAL}[\"']"
)

VARIATION_HINT = re.compile(
    r"\b(boolVariation|stringVariation|intVariation|doubleVariation|jsonVariation|"
    r"numberVariation|variation|completion_config|completionConfig)\s*\(",
    re.I,
)

# Heuristic: typed SDK call on nearby lines → kind
KIND_FROM_CALL = [
    (re.compile(r"\bboolVariation\b|\.bool_variation\b", re.I), "boolean"),
    (re.compile(r"\bstringVariation\b|\.str_variation\b|\.string_variation\b", re.I), "string"),
    (re.compile(r"\bintVariation\b|\bdoubleVariation\b|\.int_variation\b|numberVariation", re.I), "number"),
    (re.compile(r"\bjsonVariation\b|\.json_variation\b", re.I), "json"),
]


@dataclass
class Hit:
    key: str
    resource: str  # flag | ai-config
    role: str  # evaluation | provisioning
    path: str  # repo-relative
    line: int  # 1-based
    kind_guess: str = ""
    name_guess: str = ""
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def repo_root_from_ld(ld_root: Path) -> Path:
    return ld_root.parent if ld_root.name == ".launchdarkly" else ld_root


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIR_NAMES for part in path.parts)


def _role_for_path(rel: Path) -> str | None:
    parts = {p.lower() for p in rel.parts}
    if "rest" in parts or "terraform" in parts:
        return "provisioning"
    suffix = rel.suffix.lower()
    if suffix in EVAL_SUFFIXES:
        return "evaluation"
    if suffix in PROV_SUFFIXES:
        # orphan scripts outside rest/terraform still count as provisioning-ish
        return "provisioning"
    return None


def _looks_like_noise_key(key: str) -> bool:
    noise = {
        "content-type",
        "application-json",
        "utf-8",
        "x-api-key",
        "launchdarkly",
        "grid-navigator",
        "user-agent",
    }
    low = key.lower()
    if low in noise or low in _SKIP_KEYS:
        return True
    if low.startswith("http") or ":" in key:
        return True
    if any(low.startswith(p) for p in _SKIP_PREFIXES):
        return True
    return False


def _accept_provisioning_key(key: str, resource: str) -> bool:
    """Provisioning JSON/TF emits many keys; keep teaching-repo flag/AI Config keys."""
    if key == "VIP":
        return True
    low = key.lower()
    if resource == "ai-config":
        return any(low.startswith(p) for p in _AGENT_PREFIXES) or "completion" in low
    return any(low.startswith(p) for p in _FLAG_PREFIXES)


def _kind_from_context(lines: list[str], idx: int) -> str:
    window = "\n".join(lines[max(0, idx - 3) : min(len(lines), idx + 4)])
    for pattern, kind in KIND_FROM_CALL:
        if pattern.search(window):
            return kind
    return ""


def _example_path_from_rel(rel: str) -> str:
    """Best-effort example directory for inventory examples:."""
    parts = Path(rel).parts
    if not parts:
        return ""
    # 99-use-cases/15-guarded-rollout/...
    if parts[0] == "99-use-cases" and len(parts) >= 2:
        return str(Path(parts[0]) / parts[1])
    # 20-agent-config/21-agent-completion-config/...
    if parts[0] == "20-agent-config" and len(parts) >= 2:
        return str(Path(parts[0]) / parts[1])
    # 10-code-control/11-flag-enablement/...
    return parts[0]


def scan_repository(repo: Path) -> list[Hit]:
    repo = repo.resolve()
    hits: list[Hit] = []
    seen: set[tuple[str, str, str, int]] = set()

    for path in sorted(repo.rglob("*")):
        if not path.is_file() or _is_ignored(path.relative_to(repo)):
            continue
        rel = path.relative_to(repo)
        role = _role_for_path(rel)
        if role is None:
            continue
        # Evaluation markup languages only for evaluation role; provisioning any prov suffix
        suffix = path.suffix.lower()
        if role == "evaluation" and suffix not in EVAL_SUFFIXES:
            continue
        if role == "provisioning" and suffix not in PROV_SUFFIXES and "rest" not in {
            p.lower() for p in rel.parts
        } and "terraform" not in {p.lower() for p in rel.parts}:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        rel_s = str(rel)

        for i, line in enumerate(lines):
            found: list[tuple[str, str, str]] = []  # key, resource, kind_guess

            if role == "evaluation":
                for m in ASSIGN_FLAG_RE.finditer(line):
                    found.append((m.group("key"), "flag", _kind_from_context(lines, i)))
                for m in ASSIGN_CONFIG_RE.finditer(line):
                    found.append((m.group("key"), "ai-config", ""))
                # Inline string in variation("…") rare but catch
                if VARIATION_HINT.search(line):
                    for m in re.finditer(rf"[\"']{KEY_LITERAL}[\"']", line):
                        found.append((m.group("key"), "flag", _kind_from_context(lines, i)))
            else:
                for rx in (JSON_KEY_RE, TF_KEY_RE, BASH_FLAG_RE, BASH_DEFAULT_RE):
                    for m in rx.finditer(line):
                        key = m.group("key")
                        resource = "flag"
                        if (
                            "CONFIG" in line.upper()
                            or "ai-config" in line
                            or "ai-configs" in line
                            or "CONFIG_KEY" in line
                        ):
                            resource = "ai-config"
                        if not _accept_provisioning_key(key, resource):
                            continue
                        found.append((key, resource, ""))

            for key, resource, kind_guess in found:
                if _looks_like_noise_key(key):
                    continue
                if role == "provisioning" and not _accept_provisioning_key(key, resource):
                    continue
                sig = (key, resource, rel_s, i + 1)
                if sig in seen:
                    continue
                seen.add(sig)
                hits.append(
                    Hit(
                        key=key,
                        resource=resource,
                        role=role,
                        path=rel_s,
                        line=i + 1,
                        kind_guess=kind_guess,
                        snippet=line.strip()[:80],
                    )
                )

    return hits


def hits_by_key(hits: list[Hit]) -> dict[str, list[Hit]]:
    out: dict[str, list[Hit]] = {}
    for h in hits:
        out.setdefault(h.key, []).append(h)
    return out


def roles_for_key(hits: list[Hit]) -> str:
    roles = sorted({h.role for h in hits})
    if roles == ["evaluation"]:
        return "evaluation"
    if roles == ["provisioning"]:
        return "provisioning"
    if set(roles) == {"evaluation", "provisioning"}:
        return "both"
    return ",".join(roles)
