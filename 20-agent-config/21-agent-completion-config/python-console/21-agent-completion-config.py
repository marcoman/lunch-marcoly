#!/usr/bin/env python3
"""
21-agent-completion-config.py — curses console for AgentControl completion config.

Fixed chrome (hotkeys) at the top; scrollable output below.
Reuses agent_core + yahoo_news from the sibling python/ web folder.

LaunchDarkly: model + system/user messages come from the completion config at
generate time (same agent_core path as the web UI). Press (l)d for the last
sent/received evaluation; generate only shows ~80-char prompt previews.
"""

from __future__ import annotations

import curses
import json
import os
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON_WEB = HERE.parent / "python"
sys.path.insert(0, str(PYTHON_WEB))

from agent_core import (  # noqa: E402
    PERSONAS,
    config_key,
    generate_stream,
    init_launchdarkly,
    system_message_text,
    user_message_text,
)
from yahoo_news import (  # noqa: E402
    DEFAULT_TICKER_1,
    DEFAULT_TICKER_2,
    fetch_stories_for_tickers,
    get_last_pair_cached,
    normalize_ticker,
)

APP_BANNER = "21-agent-completion-config[python-console]"
CHROME_ROWS = 3
FOOTER_ROWS = 1
PAD_MAX_LINES = 4000
# Emphasize the first line of prompts; keep the generate pane readable.
PROMPT_PREVIEW_CHARS = 80

MENU_LEFT = (
    "(t)ickers",
    "st(o)ries",
    "(s)tatus",
    "(l)d",
    "(c)lear",
    "(g)enerate report",
    "(q)uit",
)
MENU_RIGHT = "(n)ext user"

# Color pair ids (initialized in init_styles).
PAIR_HOTKEY = 1
PAIR_NAME = 2
PAIR_OK = 3
PAIR_ERROR = 4
PAIR_BUSY = 5
PAIR_WARN = 6
PAIR_MUTED = 7
PAIR_TICKER1 = 8
PAIR_TICKER2 = 9
PAIR_STORY1 = 10
PAIR_STORY2 = 11
PAIR_PROMPT = 12
PAIR_RESPONSE = 13

# Named palettes. Curses has no built-in themes; these map roles → (fg, bold?).
THEMES: dict[str, dict[str, tuple[int, bool]]] = {
    "default": {
        "hotkey": (curses.COLOR_CYAN, True),
        "name": (curses.COLOR_YELLOW, True),
        "ok": (curses.COLOR_GREEN, True),
        "error": (curses.COLOR_RED, True),
        "busy": (curses.COLOR_CYAN, True),
        "warn": (curses.COLOR_YELLOW, True),
        "muted": (curses.COLOR_WHITE, False),
        "ticker1": (curses.COLOR_GREEN, True),
        "ticker2": (curses.COLOR_MAGENTA, True),
        "story1": (curses.COLOR_GREEN, False),
        "story2": (curses.COLOR_MAGENTA, False),
        "prompt": (curses.COLOR_BLUE, False),
        "response": (curses.COLOR_CYAN, False),
    },
    "high-contrast": {
        "hotkey": (curses.COLOR_WHITE, True),
        "name": (curses.COLOR_YELLOW, True),
        "ok": (curses.COLOR_GREEN, True),
        "error": (curses.COLOR_RED, True),
        "busy": (curses.COLOR_WHITE, True),
        "warn": (curses.COLOR_YELLOW, True),
        "muted": (curses.COLOR_WHITE, False),
        "ticker1": (curses.COLOR_GREEN, True),
        "ticker2": (curses.COLOR_CYAN, True),
        "story1": (curses.COLOR_GREEN, False),
        "story2": (curses.COLOR_CYAN, False),
        "prompt": (curses.COLOR_YELLOW, False),
        "response": (curses.COLOR_WHITE, True),
    },
}

ACTIVE_THEME = "default"

ROLE_PAIRS = {
    "hotkey": PAIR_HOTKEY,
    "name": PAIR_NAME,
    "ok": PAIR_OK,
    "error": PAIR_ERROR,
    "busy": PAIR_BUSY,
    "warn": PAIR_WARN,
    "muted": PAIR_MUTED,
    "ticker1": PAIR_TICKER1,
    "ticker2": PAIR_TICKER2,
    "story1": PAIR_STORY1,
    "story2": PAIR_STORY2,
    "prompt": PAIR_PROMPT,
    "response": PAIR_RESPONSE,
}


def init_styles(theme_name: str = ACTIVE_THEME) -> bool:
    """Enable color pairs from a named theme. Returns True if colors on."""
    if not curses.has_colors():
        return False
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK

    theme = THEMES.get(theme_name) or THEMES["default"]
    for role, pair_id in ROLE_PAIRS.items():
        fg, _bold = theme.get(role, (curses.COLOR_WHITE, False))
        curses.init_pair(pair_id, fg, bg)
    return True


def theme_bold(role: str, theme_name: str = ACTIVE_THEME) -> bool:
    theme = THEMES.get(theme_name) or THEMES["default"]
    return bool(theme.get(role, (curses.COLOR_WHITE, False))[1])


def attr_or(base: int, *extras: int) -> int:
    out = base
    for extra in extras:
        out |= extra
    return out


def clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def preview_text(text: str, max_chars: int = PROMPT_PREVIEW_CHARS) -> str:
    """First non-empty line, capped — for generate chrome and LD message previews."""
    cleaned = (text or "").strip()
    if not cleaned:
        return "(none)"
    first_line = cleaned.splitlines()[0].strip()
    if len(first_line) > max_chars:
        return first_line[: max_chars - 1] + "…"
    return first_line


def align_pair(left: str, right: str, width: int, gap: int = 2) -> str:
    """Put left at the start and right at the end of a fixed-width line."""
    if width <= 0:
        return ""
    if len(left) + gap + len(right) > width:
        room = max(0, width - gap - len(left))
        right = clip(right, room)
        room_left = max(0, width - gap - len(right))
        left = clip(left, room_left)
    pad = max(gap, width - len(left) - len(right))
    return clip(left + (" " * pad) + right, width)


def fmt(value: object) -> str:
    if value is None or value == "":
        return "—"
    return str(value)


def has_usable_stories(stories: list) -> bool:
    return any((block.get("stories") or []) for block in (stories or []))


def story_count_for_ticker(stories: list, ticker: str) -> int:
    symbol = normalize_ticker(ticker)
    for block in stories or []:
        if normalize_ticker(str(block.get("ticker") or "")) == symbol:
            return len(block.get("stories") or [])
    return 0


def format_tickers_label(ticker1: str, ticker2: str, stories: list) -> str:
    t1 = ticker1 or "(not set)"
    t2 = ticker2 or "(not set)"
    n1 = story_count_for_ticker(stories, ticker1)
    n2 = story_count_for_ticker(stories, ticker2)
    return f"Tickers: {t1} ({n1} stories) {t2} ({n2} stories)"


class App:
    def __init__(self, stdscr: curses.window) -> None:
        self.stdscr = stdscr
        self.persona_index = 0
        self.ticker1 = DEFAULT_TICKER_1
        self.ticker2 = DEFAULT_TICKER_2
        self.stories: list = []
        self.footer = "Ready."
        self.footer_kind = "info"  # info | ok | error | busy | warn
        self.busy = False
        self.pad_lines: list = []
        self.scroll = 0
        self.pad: curses.window | None = None
        self.colors = False
        # Last AgentControl evaluation (same shape as web LD details drawer).
        self.last_ld_transaction: dict | None = None
        self.last_provider: str | None = None
        self.last_model: str | None = None
        self.last_variation_key: str | None = None
        self.last_fallback: bool = False
        self._restore_cached_stories()
        self._ensure_pad()

    def style(self, kind: str) -> int:
        """Return a curses attribute for chrome/footer/output styling."""
        if kind in {"normal", "info", ""}:
            return curses.A_NORMAL
        bold = theme_bold(kind) if kind in ROLE_PAIRS else False
        if not self.colors:
            if kind in {
                "hotkey",
                "name",
                "ok",
                "ticker1",
                "ticker2",
                "story1",
                "story2",
                "response",
            }:
                return curses.A_BOLD
            if kind in {"muted", "prompt"}:
                return curses.A_DIM
            return curses.A_NORMAL
        pair_id = ROLE_PAIRS.get(kind)
        if pair_id is None:
            return curses.A_NORMAL
        attr = curses.color_pair(pair_id)
        if bold or kind in {"hotkey", "name", "ok", "error", "busy", "warn"}:
            attr = attr_or(attr, curses.A_BOLD)
        elif kind == "muted":
            attr = attr_or(attr, curses.A_DIM)
        return attr

    def _restore_cached_stories(self) -> None:
        """Load last disk-cached ticker pair into session (shared with python web)."""
        cached = get_last_pair_cached()
        if not cached:
            return
        self.ticker1 = str(cached.get("ticker1") or self.ticker1)
        self.ticker2 = str(cached.get("ticker2") or self.ticker2)
        blocks = cached.get("tickers") or []
        if isinstance(blocks, list) and blocks:
            self.stories = blocks
            self.footer = "Restored saved stories from disk cache."
            self.footer_kind = "ok"

    @property
    def persona(self):
        return PERSONAS[self.persona_index]

    def _ensure_pad(self) -> None:
        height = max(PAD_MAX_LINES, len(self.pad_lines) + 64)
        width = max(curses.COLS, 80)
        self.pad = curses.newpad(height, width)

    def output_height(self) -> int:
        return max(1, curses.LINES - CHROME_ROWS - FOOTER_ROWS)

    def output_width(self) -> int:
        return max(1, curses.COLS)

    def append(self, text: str = "", kind: str = "normal", autoscroll: bool = True) -> None:
        """Append text to the log (may contain newlines)."""
        width = max(20, self.output_width() - 1)
        chunks = text.split("\n") if text else [""]
        for chunk in chunks:
            if chunk == "":
                self.pad_lines.append(("", kind))
            else:
                wrapped = textwrap.wrap(
                    chunk,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=False,
                ) or [""]
                for line in wrapped:
                    self.pad_lines.append((line, kind))

        if len(self.pad_lines) > PAD_MAX_LINES:
            overflow = len(self.pad_lines) - PAD_MAX_LINES
            self.pad_lines = self.pad_lines[overflow:]
            self.scroll = max(0, self.scroll - overflow)

        self._redraw_pad_content()
        if autoscroll:
            self.scroll_to_bottom()
        self.refresh()

    def append_token(self, token: str, kind: str = "response") -> None:
        """Append streaming token text without forcing a newline."""
        if not token:
            return
        width = max(20, self.output_width() - 1)
        parts = token.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                self.pad_lines.append(("", kind))
            if not part:
                continue
            if not self.pad_lines:
                self.pad_lines.append(("", kind))
            current, cur_kind = self.pad_lines[-1]
            if cur_kind != kind and current:
                self.pad_lines.append(("", kind))
                current, cur_kind = self.pad_lines[-1]
            combined = current + part
            if len(combined) <= width:
                self.pad_lines[-1] = (combined, kind)
            else:
                space = width - len(current)
                if space > 0:
                    self.pad_lines[-1] = (current + part[:space], kind)
                    rest = part[space:]
                else:
                    rest = part
                while rest:
                    self.pad_lines.append((rest[:width], kind))
                    rest = rest[width:]
        if len(self.pad_lines) > PAD_MAX_LINES:
            overflow = len(self.pad_lines) - PAD_MAX_LINES
            self.pad_lines = self.pad_lines[overflow:]
            self.scroll = max(0, self.scroll - overflow)
        self._redraw_pad_content()
        self.scroll_to_bottom()
        self.refresh()

    def _redraw_pad_content(self) -> None:
        if self.pad is None:
            self._ensure_pad()
        assert self.pad is not None
        if len(self.pad_lines) + 8 > self.pad.getmaxyx()[0]:
            self._ensure_pad()
        assert self.pad is not None
        self.pad.erase()
        max_y, max_x = self.pad.getmaxyx()
        for i, entry in enumerate(self.pad_lines):
            if i >= max_y - 1:
                break
            if isinstance(entry, tuple):
                line, kind = entry
            else:
                line, kind = str(entry), "normal"
            try:
                self.pad.addnstr(i, 0, line, max_x - 1, self.style(kind))
            except curses.error:
                pass

    def scroll_to_bottom(self) -> None:
        visible = self.output_height()
        self.scroll = max(0, len(self.pad_lines) - visible)

    def scroll_by(self, delta: int) -> None:
        visible = self.output_height()
        max_scroll = max(0, len(self.pad_lines) - visible)
        self.scroll = max(0, min(max_scroll, self.scroll + delta))
        self.refresh()

    def set_footer(self, text: str, kind: str = "info") -> None:
        self.footer = text
        self.footer_kind = kind
        self.refresh()

    def _addnstr(self, y: int, x: int, text: str, max_len: int, attr: int = curses.A_NORMAL) -> None:
        if max_len <= 0 or x >= curses.COLS:
            return
        try:
            self.stdscr.addnstr(y, x, text, max_len, attr)
        except curses.error:
            pass

    def _write_hotkey_text(self, y: int, x: int, text: str, max_x: int) -> None:
        """Write menu text, bold+cyan on the letter inside (…)."""
        normal = curses.A_NORMAL
        hot = self.style("hotkey")
        i = 0
        col = x
        while i < len(text) and col < max_x:
            if (
                text[i] == "("
                and i + 2 < len(text)
                and text[i + 2] == ")"
                and text[i + 1].isalpha()
            ):
                self._addnstr(y, col, "(", 1, normal)
                col += 1
                if col >= max_x:
                    break
                self._addnstr(y, col, text[i + 1], 1, hot)
                col += 1
                if col >= max_x:
                    break
                self._addnstr(y, col, ")", 1, normal)
                col += 1
                i += 3
                continue
            self._addnstr(y, col, text[i], 1, normal)
            col += 1
            i += 1

    def _chrome_provider_model(self) -> str:
        if self.last_provider and self.last_model:
            return f"{self.last_provider} / {self.last_model}"
        return f"config:{config_key()}"

    def draw_chrome(self) -> None:
        width = max(1, curses.COLS - 1)

        left0 = APP_BANNER
        right0 = format_tickers_label(self.ticker1, self.ticker2, self.stories)
        row0 = align_pair(left0, right0, width)
        self.stdscr.move(0, 0)
        self.stdscr.clrtoeol()
        right0_x = row0.rfind(right0) if right0 else width
        if right0_x < 0:
            right0_x = max(0, width - len(right0))
        self._addnstr(0, 0, left0, right0_x, self.style("muted"))
        self._addnstr(0, right0_x, right0, width - right0_x, curses.A_NORMAL)

        # Row 1 — AgentControl key + last served model (left) + user (right)
        left1 = self._chrome_provider_model()
        name = self.persona.name
        right1 = f"Name: {name}."
        row1 = align_pair(left1, right1, width)
        self.stdscr.move(1, 0)
        self.stdscr.clrtoeol()
        right1_x = row1.rfind(right1) if right1 else width
        if right1_x < 0:
            right1_x = max(0, width - len(right1))
        self._addnstr(1, 0, left1, right1_x, curses.A_NORMAL)
        prefix = "Name: "
        self._addnstr(1, right1_x, prefix, width - right1_x, curses.A_NORMAL)
        name_x = right1_x + len(prefix)
        if name_x < width:
            self._addnstr(1, name_x, f"{name}.", width - name_x, self.style("name"))

        left2 = "  ".join(MENU_LEFT)
        right2 = MENU_RIGHT
        row2 = align_pair(left2, right2, width)
        self.stdscr.move(2, 0)
        self.stdscr.clrtoeol()
        right2_x = row2.rfind(right2) if right2 else width
        if right2_x < 0:
            right2_x = max(0, width - len(right2))
        self._write_hotkey_text(2, 0, left2, right2_x)
        self._write_hotkey_text(2, right2_x, right2, width)

    def draw_footer(self) -> None:
        y = curses.LINES - 1
        try:
            self.stdscr.move(y, 0)
            self.stdscr.clrtoeol()
            kind = self.footer_kind if self.footer_kind != "info" else "info"
            attr = self.style(kind) if kind != "info" else curses.A_NORMAL
            self.stdscr.addnstr(y, 0, clip(self.footer, curses.COLS), curses.COLS - 1, attr)
        except curses.error:
            pass

    def refresh(self) -> None:
        self.draw_chrome()
        self.draw_footer()
        self.stdscr.noutrefresh()
        if self.pad is not None:
            top = CHROME_ROWS
            bottom = curses.LINES - FOOTER_ROWS - 1
            right = curses.COLS - 1
            try:
                self.pad.noutrefresh(
                    self.scroll,
                    0,
                    top,
                    0,
                    bottom,
                    right,
                )
            except curses.error:
                pass
        curses.doupdate()

    def prompt_line(self, label: str) -> str | None:
        """Read a line from the footer; Esc cancels (returns None)."""
        curses.echo()
        curses.curs_set(1)
        y = curses.LINES - 1
        try:
            self.stdscr.move(y, 0)
            self.stdscr.clrtoeol()
            prompt = clip(label, max(1, curses.COLS - 2))
            self.stdscr.addnstr(y, 0, prompt, curses.COLS - 1)
            self.stdscr.refresh()
            raw = self.stdscr.getstr(y, len(prompt), 40)
            text = raw.decode("utf-8", errors="replace").strip()
            return text
        except curses.error:
            return None
        finally:
            curses.noecho()
            curses.curs_set(0)
            self.refresh()

    # --- commands ----------------------------------------------------------

    def cmd_status(self) -> None:
        """Ops snapshot + one-line last LD variation (full detail: press l)."""
        self.append("— status —", "muted")
        self.append(f"User:     {self.persona.name} ({self.persona.profile})", "name")
        self.append(f"Tickers:  {self.ticker1}", "ticker1")
        self.append(f"          {self.ticker2}", "ticker2")
        self.append(f"Config:   {config_key()}", "muted")
        if self.last_provider and self.last_model:
            self.append(
                f"Provider: {self.last_provider} / {self.last_model}", "muted"
            )
        else:
            self.append("Provider: (generate once to see served model)", "muted")
        # Lean LD line — full sent/received lives in (l)d.
        if self.last_ld_transaction:
            var = self.last_variation_key or "(none)"
            fb = " yes" if self.last_fallback else " no"
            self.append(f"Last LD:  variation={var}  fallback={fb}", "ok")
        else:
            self.append("Last LD:  (none yet — press g, then l)", "muted")
        self.append("Stories:", "muted")
        self._append_stories()
        self.set_footer("Status shown. Press l for LD sent/received.", "ok")

    def cmd_ld(self) -> None:
        """Show last LaunchDarkly sent/received transaction (web LD details twin)."""
        if not self.last_ld_transaction:
            self.append("— ld —", "muted")
            self.append("No LD evaluation yet. Press g to generate first.", "warn")
            self.set_footer("Generate first, then press l.", "warn")
            return

        sent = self.last_ld_transaction.get("sent") or {}
        received = self.last_ld_transaction.get("received") or {}
        ctx = sent.get("context") or {}
        variables = sent.get("variables") or {}
        sdk_default = sent.get("sdkDefault") or {}
        reason = received.get("reason") or {}

        self.append("— ld (last generate) —", "muted")
        self.append("Sent (request)", "ok")
        self.append(f"  configKey:  {fmt(sent.get('configKey'))}", "muted")
        self.append(
            f"  context:    kind={fmt(ctx.get('kind'))}  "
            f"key={fmt(ctx.get('key'))}  name={fmt(ctx.get('name'))}",
            "muted",
        )
        if ctx.get("anonymous") is not None:
            self.append(f"  anonymous:  {ctx.get('anonymous')}", "muted")
        stories_var = variables.get("stories") or ""
        self.append(f"  variables.stories: {preview_text(str(stories_var))}", "prompt")
        self.append(
            f"  sdkDefault: model={fmt(sdk_default.get('model'))}  "
            f"provider={fmt(sdk_default.get('provider'))}",
            "muted",
        )

        self.append("Received (evaluation)", "ok")
        self.append(f"  fallback:   {fmt(received.get('fallback'))}", "muted")
        self.append(f"  enabled:    {fmt(received.get('enabled'))}", "muted")
        self.append(f"  variation:  {fmt(received.get('variationKey'))}", "name")
        self.append(
            f"  reason:     {fmt(reason.get('kind') if isinstance(reason, dict) else reason)}",
            "muted",
        )
        if isinstance(reason, dict) and reason.get("ruleIndex") is not None:
            self.append(
                f"  rule:       index={fmt(reason.get('ruleIndex'))}  "
                f"id={fmt(reason.get('ruleId'))}",
                "muted",
            )
        self.append(
            f"  provider:   {fmt(received.get('provider'))} / {fmt(received.get('model'))}",
            "muted",
        )

        messages = received.get("messages") or []
        self.append("  messages (preview):", "muted")
        if not messages:
            self.append("    (none)", "muted")
        else:
            for msg in messages:
                role = msg.get("role") or "?"
                body = preview_text(str(msg.get("content") or ""))
                self.append(f"    [{role}] {body}", "prompt")

        # Pretty-printed reason for targeting debugging (usually a few fields).
        if reason:
            self.append("  reason JSON:", "muted")
            try:
                reason_json = json.dumps(reason, indent=2, sort_keys=True)
            except (TypeError, ValueError):
                reason_json = str(reason)
            for line in reason_json.splitlines():
                self.append(f"    {line}", "muted")

        self.set_footer("LD details shown (message bodies truncated to ~80 chars).", "ok")

    def cmd_clear(self) -> None:
        """Wipe the output pad; keep persona, tickers, stories, and last LD tx."""
        self.pad_lines = []
        self.scroll = 0
        self._ensure_pad()
        self._redraw_pad_content()
        self.set_footer("Output cleared.", "ok")

    def _append_stories(self) -> None:
        if not self.stories:
            self.append("  (no stories loaded — press o)", "muted")
            return
        for index, block in enumerate(self.stories):
            slot = 1 if index == 0 else 2
            ticker_kind = f"ticker{slot}"
            story_kind = f"story{slot}"
            ticker = block.get("ticker") or "?"
            name = block.get("name") or ticker
            cache_note = " [cached]" if block.get("from_cache") else ""
            self.append(f"  {ticker} ({name}){cache_note}", ticker_kind)
            items = block.get("stories") or []
            if not items:
                err = block.get("error") or "no stories"
                self.append(f"    · {err}", "muted")
                continue
            for story in items:
                title = story.get("title") or "(untitled)"
                publisher = story.get("publisher") or ""
                line = f"    · {title}"
                if publisher:
                    line += f" — {publisher}"
                self.append(line, story_kind)
            if block.get("error"):
                self.append(f"    note: {block['error']}", "warn")

    def cmd_tickers(self) -> None:
        self.set_footer("Enter tickers…", "busy")
        t1_raw = self.prompt_line("Ticker 1: ")
        if t1_raw is None:
            self.set_footer("Cancelled.", "warn")
            return
        t2_raw = self.prompt_line("Ticker 2: ")
        if t2_raw is None:
            self.set_footer("Cancelled.", "warn")
            return
        if t1_raw:
            self.ticker1 = normalize_ticker(t1_raw) or DEFAULT_TICKER_1
        if t2_raw:
            self.ticker2 = normalize_ticker(t2_raw) or DEFAULT_TICKER_2
        self.append(f"Tickers set to {self.ticker1}  {self.ticker2}")
        self.set_footer(f"Tickers: {self.ticker1}  {self.ticker2}", "ok")

    def cmd_stories(self) -> None:
        self.busy = True
        self.set_footer(
            f"Fetching Yahoo stories for {self.ticker1} and {self.ticker2}…",
            "busy",
        )
        try:
            result = fetch_stories_for_tickers(self.ticker1, self.ticker2, count=2)
            self.stories = result.get("tickers") or []
            self.append(
                f"— stories ({self.ticker1} / {self.ticker2}) —", "muted"
            )
            self._append_stories()
            errors = result.get("errors") or []
            if errors:
                self.set_footer(" · ".join(errors), "warn")
            else:
                self.set_footer("Stories loaded. Press g to generate.", "ok")
        except Exception as exc:  # noqa: BLE001
            self.append(f"Error fetching stories: {exc}")
            self.set_footer(str(exc), "error")
        finally:
            self.busy = False
            self.refresh()

    def cmd_next_user(self) -> None:
        self.persona_index = (self.persona_index + 1) % len(PERSONAS)
        self.append(f"User: {self.persona.name} ({self.persona.profile})")
        self.set_footer(f"User: {self.persona.name}", "ok")
        self.refresh()

    def _remember_meta(self, event: dict) -> None:
        """Keep chrome + status/ld in sync with the last generate meta event."""
        self.last_provider = str(event.get("provider") or "") or None
        self.last_model = str(event.get("model") or "") or None
        self.last_fallback = bool(event.get("fallback"))
        self.last_variation_key = str(event.get("variationKey") or "") or None
        tx = event.get("ldTransaction")
        if isinstance(tx, dict):
            self.last_ld_transaction = tx
            received = tx.get("received") or {}
            if not self.last_variation_key:
                key = received.get("variationKey")
                self.last_variation_key = str(key) if key else None
            if received.get("fallback"):
                self.last_fallback = True
            if self.last_fallback and not self.last_variation_key:
                self.last_variation_key = "code-baseline"

    def cmd_generate(self) -> None:
        if not has_usable_stories(self.stories):
            self.set_footer("Load stories first (press o), then g.", "warn")
            return

        self.busy = True
        self.set_footer(f"Generating AI report for {self.persona.name}…", "busy")
        self.append(f"— generate ({self.persona.name}) —", "muted")
        saw_token = False
        try:
            for event in generate_stream(self.persona, ticker_results=self.stories):
                etype = event.get("type")
                if etype == "meta":
                    self._remember_meta(event)
                    variation = event.get("variationKey") or (
                        "code-baseline" if event.get("fallback") else "(unknown)"
                    )
                    self.append(
                        f"LD: {variation}  "
                        f"{event.get('provider')} / {event.get('model')}",
                        "muted",
                    )
                    # Truncated previews — full messages via (l)d.
                    user_preview = preview_text(str(event.get("input") or ""))
                    tx = event.get("ldTransaction")
                    received = (tx.get("received") if isinstance(tx, dict) else None) or {}
                    messages = received.get("messages") or []
                    sys_preview = preview_text(system_message_text(messages))
                    user_from_msg = preview_text(user_message_text(messages))
                    if user_from_msg != "(none)":
                        user_preview = user_from_msg
                    self.append(f"System: {sys_preview}", "prompt")
                    self.append(f"Prompt: {user_preview}", "prompt")
                    self.append("Response:", "muted")
                    continue
                if etype == "status":
                    self.append(str(event.get("message") or ""), "warn")
                    continue
                if etype == "token":
                    self.append_token(str(event.get("text") or ""), "response")
                    saw_token = True
                    self.set_footer(f"Streaming… {self.persona.name}", "busy")
                    continue
                if etype == "error":
                    if saw_token:
                        self.append("")
                    self.append(
                        f"Error: {event.get('message') or 'Generation error'}",
                        "error",
                    )
                    self.set_footer(
                        str(event.get("message") or "Generation error"), "error"
                    )
                    continue
                if etype == "metrics":
                    if saw_token:
                        self.append("")
                    metrics = event.get("metrics") or {}
                    self.append(
                        "Metrics: "
                        f"latency_ms={fmt(metrics.get('latency_ms'))}  "
                        f"ttft_ms={fmt(metrics.get('ttft_ms'))}  "
                        f"prompt_tokens={fmt(metrics.get('prompt_tokens'))}  "
                        f"completion_tokens={fmt(metrics.get('completion_tokens'))}  "
                        f"total_tokens={fmt(metrics.get('total_tokens'))}  "
                        f"finish_reason={fmt(metrics.get('finish_reason'))}",
                        "muted",
                    )
                    continue
                if etype == "done":
                    self.set_footer(
                        f"Done — {self.persona.name}. Press l for LD details.",
                        "ok",
                    )
        except Exception as exc:  # noqa: BLE001
            self.append(f"Error: {exc}")
            self.set_footer(str(exc), "error")
        finally:
            self.busy = False
            self.refresh()


def run(stdscr: curses.window) -> None:
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(-1)

    theme = (os.environ.get("AGENT_CONSOLE_THEME") or ACTIVE_THEME).strip().lower()
    if theme not in THEMES:
        theme = ACTIVE_THEME

    app = App(stdscr)
    app.colors = init_styles(theme)

    # LaunchDarkly: server SDK + AI SDK (required for completion_config).
    try:
        init_launchdarkly()
        ld_ok = True
        hint = (
            f"Ready (config:{config_key()}). "
            "o → g → n to compare personas. l = LD details."
        )
    except Exception as exc:  # noqa: BLE001
        ld_ok = False
        hint = f"LD init failed: {exc}"

    if app.footer_kind == "ok" and app.stories and ld_ok:
        app.refresh()
    else:
        app.set_footer(hint, "ok" if ld_ok else "error")

    while True:
        app.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            app._ensure_pad()
            app._redraw_pad_content()
            app.scroll_to_bottom()
            app.refresh()
            continue

        if key in (curses.KEY_UP,):
            app.scroll_by(-1)
            continue
        if key in (curses.KEY_DOWN,):
            app.scroll_by(1)
            continue
        if key in (curses.KEY_PPAGE,):
            app.scroll_by(-app.output_height())
            continue
        if key in (curses.KEY_NPAGE,):
            app.scroll_by(app.output_height())
            continue

        if app.busy:
            continue

        if key in (ord("q"), ord("Q")):
            break

        if key in (ord("s"), ord("S")):
            app.cmd_status()
        elif key in (ord("l"), ord("L")):
            app.cmd_ld()
        elif key in (ord("c"), ord("C")):
            app.cmd_clear()
        elif key in (ord("t"), ord("T")):
            app.cmd_tickers()
        elif key in (ord("o"), ord("O")):
            app.cmd_stories()
        elif key in (ord("g"), ord("G")):
            app.cmd_generate()
        elif key in (ord("n"), ord("N")):
            app.cmd_next_user()
        elif key in (ord("h"), ord("H"), ord("?")):
            app.set_footer(f"{'  '.join(MENU_LEFT)}   {MENU_RIGHT}", "info")
        else:
            app.set_footer("Unknown key. Use menu hotkeys (t o s l c g q n).", "warn")


def main() -> None:
    curses.wrapper(run)


if __name__ == "__main__":
    main()
