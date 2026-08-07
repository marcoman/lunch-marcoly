#!/usr/bin/env node
/**
 * 01-reference-agent[node-console] — terminal UI matching the Python console.
 * Reuses ../node/agentCore.js and ../node/yahooNews.js.
 */

"use strict";

const readline = require("readline");
const path = require("path");

const {
  PERSONAS,
  generateStream,
  modelLabel,
  resolveMode,
  setModeOverride,
} = require("../node/agentCore");
const {
  DEFAULT_TICKER_1,
  DEFAULT_TICKER_2,
  fetchStoriesForTickers,
  formatStorySource,
  getLastPairCached,
  normalizeTicker,
} = require("../node/yahooNews");

const APP_BANNER = "01-reference-agent[node-console]";
const CHROME_ROWS = 3;
const FOOTER_ROWS = 1;
const PAD_MAX = 4000;
const MENU_LEFT = [
  "(t)ickers",
  "st(o)ries",
  "(s)tatus",
  "(g)enerate report",
  "(m)ode",
  "(q)uit",
];
const MENU_RIGHT = "(n)ext user";
const LLM_MODES = ["stub", "ollama", "bedrock"];

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  green: "\x1b[32m",
  magenta: "\x1b[35m",
  blue: "\x1b[34m",
  red: "\x1b[31m",
  white: "\x1b[37m",
};

const KIND_STYLE = {
  hotkey: ANSI.bold + ANSI.cyan,
  name: ANSI.bold + ANSI.yellow,
  ok: ANSI.bold + ANSI.green,
  error: ANSI.bold + ANSI.red,
  busy: ANSI.bold + ANSI.cyan,
  warn: ANSI.bold + ANSI.yellow,
  muted: ANSI.dim + ANSI.white,
  ticker1: ANSI.bold + ANSI.green,
  ticker2: ANSI.bold + ANSI.magenta,
  story1: ANSI.bold + ANSI.green,
  story2: ANSI.bold + ANSI.magenta,
  prompt: ANSI.blue,
  response: ANSI.cyan,
  normal: "",
  info: "",
};

function paint(text, kind) {
  const style = KIND_STYLE[kind] || "";
  return style ? `${style}${text}${ANSI.reset}` : text;
}

function clip(text, width) {
  if (width <= 0) return "";
  if (text.length <= width) return text;
  return width <= 1 ? text.slice(0, width) : `${text.slice(0, width - 1)}…`;
}

function alignPair(left, right, width, gap = 2) {
  if (width <= 0) return "";
  if (left.length + gap + right.length > width) {
    let room = Math.max(0, width - gap - left.length);
    right = clip(right, room);
    room = Math.max(0, width - gap - right.length);
    left = clip(left, room);
  }
  const pad = Math.max(gap, width - left.length - right.length);
  return clip(left + " ".repeat(pad) + right, width);
}

function termSize() {
  return {
    cols: process.stdout.columns || 80,
    rows: process.stdout.rows || 24,
  };
}

function ollamaHost() {
  return String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
}

async function probeOllama(timeoutMs = 600) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${ollamaHost()}/api/tags`, { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function ensureLlmMode() {
  if (process.env.AGENT_LLM_MODE != null && String(process.env.AGENT_LLM_MODE).trim() !== "") {
    return resolveMode();
  }
  if (await probeOllama()) {
    process.env.AGENT_LLM_MODE = "ollama";
  } else {
    process.env.AGENT_LLM_MODE = process.env.AGENT_LLM_MODE || "stub";
  }
  return resolveMode();
}

function storyCount(stories, ticker) {
  const symbol = normalizeTicker(ticker);
  for (const block of stories || []) {
    if (normalizeTicker(String(block.ticker || "")) === symbol) {
      return (block.stories || []).length;
    }
  }
  return 0;
}

function tickersLabel(t1, t2, stories) {
  return `Tickers: ${t1 || "(not set)"} (${storyCount(stories, t1)} stories) ${t2 || "(not set)"} (${storyCount(stories, t2)} stories)`;
}

function wrapText(text, width) {
  if (!text) return [""];
  const out = [];
  for (const raw of String(text).split("\n")) {
    if (!raw) {
      out.push("");
      continue;
    }
    let rest = raw;
    while (rest.length > width) {
      out.push(rest.slice(0, width));
      rest = rest.slice(width);
    }
    out.push(rest);
  }
  return out.length ? out : [""];
}

function styleHotkeys(text) {
  return text.replace(/\(([A-Za-z])\)/g, (_, ch) => `(${paint(ch, "hotkey")})`);
}

class App {
  constructor() {
    this.personaIndex = 0;
    this.ticker1 = DEFAULT_TICKER_1;
    this.ticker2 = DEFAULT_TICKER_2;
    this.stories = [];
    this.padLines = [];
    this.scroll = 0;
    this.footer = "Ready.";
    this.footerKind = "info";
    this.busy = false;
    this._restoreCache();
  }

  get persona() {
    return PERSONAS[this.personaIndex];
  }

  _restoreCache() {
    const cached = getLastPairCached();
    if (!cached) return;
    this.ticker1 = cached.ticker1 || this.ticker1;
    this.ticker2 = cached.ticker2 || this.ticker2;
    if (Array.isArray(cached.tickers) && cached.tickers.length) {
      this.stories = cached.tickers;
      this.footer = "Restored saved stories from disk cache.";
      this.footerKind = "ok";
    }
  }

  append(text = "", kind = "normal") {
    const { cols } = termSize();
    const width = Math.max(20, cols - 1);
    for (const line of wrapText(text, width)) {
      this.padLines.push({ text: line, kind });
    }
    if (this.padLines.length > PAD_MAX) {
      this.padLines = this.padLines.slice(-PAD_MAX);
    }
    this.scrollToBottom();
  }

  appendToken(token, kind = "response") {
    if (!token) return;
    const { cols } = termSize();
    const width = Math.max(20, cols - 1);
    const parts = String(token).split("\n");
    for (let i = 0; i < parts.length; i += 1) {
      if (i > 0) this.padLines.push({ text: "", kind });
      const part = parts[i];
      if (!part) continue;
      if (!this.padLines.length) this.padLines.push({ text: "", kind });
      let { text: current, kind: curKind } = this.padLines[this.padLines.length - 1];
      if (curKind !== kind && current) {
        this.padLines.push({ text: "", kind });
        current = "";
      }
      let combined = current + part;
      if (combined.length <= width) {
        this.padLines[this.padLines.length - 1] = { text: combined, kind };
      } else {
        const space = width - current.length;
        if (space > 0) {
          this.padLines[this.padLines.length - 1] = {
            text: current + part.slice(0, space),
            kind,
          };
          let rest = part.slice(space);
          while (rest) {
            this.padLines.push({ text: rest.slice(0, width), kind });
            rest = rest.slice(width);
          }
        } else {
          let rest = part;
          while (rest) {
            this.padLines.push({ text: rest.slice(0, width), kind });
            rest = rest.slice(width);
          }
        }
      }
    }
    if (this.padLines.length > PAD_MAX) this.padLines = this.padLines.slice(-PAD_MAX);
    this.scrollToBottom();
  }

  outputHeight() {
    const { rows } = termSize();
    return Math.max(1, rows - CHROME_ROWS - FOOTER_ROWS);
  }

  scrollToBottom() {
    this.scroll = Math.max(0, this.padLines.length - this.outputHeight());
  }

  scrollBy(delta) {
    const maxScroll = Math.max(0, this.padLines.length - this.outputHeight());
    this.scroll = Math.max(0, Math.min(maxScroll, this.scroll + delta));
  }

  setFooter(text, kind = "info") {
    this.footer = text;
    this.footerKind = kind;
  }

  render() {
    const { cols } = termSize();
    const width = Math.max(1, cols - 1);
    const mode = resolveMode();
    const model = modelLabel(mode);

    const right0 = tickersLabel(this.ticker1, this.ticker2, this.stories);
    const left1 = `AGENT_LLM_MODE=${mode}  model=${model}`;
    const nameLabel = `Name: ${this.persona.name}.`;
    const leftMenu = MENU_LEFT.join("  ");

    const chrome0 = alignPair(APP_BANNER, right0, width);
    const chrome1 = alignPair(left1, nameLabel, width);
    const chrome2 = alignPair(leftMenu, MENU_RIGHT, width);

    process.stdout.write("\x1b[H\x1b[2J");

    const c0Right = Math.max(0, chrome0.lastIndexOf(right0));
    process.stdout.write(
      `${paint(APP_BANNER, "muted")}${" ".repeat(Math.max(0, c0Right - APP_BANNER.length))}${clip(right0, width - c0Right)}\x1b[K\n`
    );

    const c1Right = Math.max(0, chrome1.lastIndexOf(nameLabel));
    process.stdout.write(
      `${clip(left1, c1Right)}${" ".repeat(Math.max(0, c1Right - left1.length))}Name: ${paint(this.persona.name, "name")}.\x1b[K\n`
    );

    const c2Right = Math.max(0, chrome2.lastIndexOf(MENU_RIGHT));
    process.stdout.write(
      `${styleHotkeys(clip(leftMenu, c2Right))}${" ".repeat(Math.max(0, c2Right - leftMenu.length))}${styleHotkeys(MENU_RIGHT)}\x1b[K\n`
    );

    const viewH = this.outputHeight();
    const slice = this.padLines.slice(this.scroll, this.scroll + viewH);
    for (let i = 0; i < viewH; i += 1) {
      const entry = slice[i];
      if (!entry) {
        process.stdout.write("\x1b[K\n");
        continue;
      }
      process.stdout.write(`${paint(clip(entry.text, width), entry.kind)}\x1b[K\n`);
    }
    process.stdout.write(`${paint(clip(this.footer, width), this.footerKind)}\x1b[K`);
  }

  appendStories() {
    if (!this.stories.length) {
      this.append("  (no stories loaded — press o)", "muted");
      return;
    }
    this.stories.forEach((block, index) => {
      const slot = index === 0 ? 1 : 2;
      const ticker = block.ticker || "?";
      const name = block.name || ticker;
      const cache = block.from_cache ? " [cached]" : "";
      this.append(`  ${ticker} (${name})${cache}`, `ticker${slot}`);
      const items = block.stories || [];
      if (!items.length) {
        this.append(`    · ${block.error || "no stories"}`, "muted");
        return;
      }
      for (const story of items) {
        let line = `    · ${story.title || "(untitled)"}`;
        const source = formatStorySource(story);
        if (source) line += ` — ${source}`;
        this.append(line, `story${slot}`);
      }
      if (block.error) this.append(`    note: ${block.error}`, "warn");
    });
  }

  async cmdStatus() {
    const mode = resolveMode();
    this.append("— status —", "muted");
    this.append(`User:     ${this.persona.name} (${this.persona.profile})`, "name");
    this.append(`Tickers:  ${this.ticker1}`, "ticker1");
    this.append(`          ${this.ticker2}`, "ticker2");
    this.append(`Provider: ${mode} / ${modelLabel(mode)}`, "muted");
    this.append("Stories:", "muted");
    this.appendStories();
    this.setFooter("Status shown.", "ok");
  }

  async promptLine(label) {
    this.setFooter(label, "busy");
    this.render();
    // Pause raw/keypress handling while readline owns stdin.
    process.stdin.removeAllListeners("keypress");
    if (process.stdin.isTTY) process.stdin.setRawMode(false);
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    const answer = await new Promise((resolve) => {
      rl.question(label, (value) => {
        rl.close();
        resolve(value);
      });
    });
    readline.emitKeypressEvents(process.stdin);
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
      process.stdin.resume();
    }
    return String(answer || "").trim();
  }

  async cmdTickers() {
    const t1 = await this.promptLine("Ticker 1: ");
    const t2 = await this.promptLine("Ticker 2: ");
    if (t1) this.ticker1 = normalizeTicker(t1) || DEFAULT_TICKER_1;
    if (t2) this.ticker2 = normalizeTicker(t2) || DEFAULT_TICKER_2;
    this.append(`Tickers set to ${this.ticker1}  ${this.ticker2}`, "ok");
    this.setFooter(`Tickers: ${this.ticker1}  ${this.ticker2}`, "ok");
  }

  async cmdStories() {
    this.busy = true;
    this.setFooter(`Fetching Yahoo stories for ${this.ticker1} and ${this.ticker2}…`, "busy");
    this.render();
    try {
      const result = await fetchStoriesForTickers(this.ticker1, this.ticker2, 2);
      this.stories = result.tickers || [];
      this.append(`— stories (${this.ticker1} / ${this.ticker2}) —`, "muted");
      this.appendStories();
      if (result.errors && result.errors.length) {
        this.setFooter(result.errors.join(" · "), "warn");
      } else {
        this.setFooter("Stories loaded. Press g to generate.", "ok");
      }
    } catch (exc) {
      this.append(`Error fetching stories: ${exc.message || exc}`, "error");
      this.setFooter(String(exc.message || exc), "error");
    } finally {
      this.busy = false;
    }
  }

  cmdNextUser() {
    this.personaIndex = (this.personaIndex + 1) % PERSONAS.length;
    this.append(`User: ${this.persona.name} (${this.persona.profile})`, "name");
    this.setFooter(`User: ${this.persona.name}`, "ok");
  }

  async cmdMode() {
    const current = resolveMode();
    const idx = Math.max(0, LLM_MODES.indexOf(current));
    const nxt = LLM_MODES[(idx + 1) % LLM_MODES.length];
    if (nxt === "ollama" && !(await probeOllama())) {
      this.append(
        `Ollama not reachable at ${ollamaHost()}. Start Ollama and pull a model.`,
        "warn"
      );
      this.setFooter("Ollama not reachable — mode left unchanged.", "warn");
      return;
    }
    setModeOverride(nxt);
    process.env.AGENT_LLM_MODE = nxt;
    const mode = resolveMode();
    const model = modelLabel(mode);
    this.append(`Mode set to AGENT_LLM_MODE=${mode}  model=${model}`, "ok");
    if (mode === "ollama") {
      this.append(`Using Ollama at ${ollamaHost()} with model ${model}.`, "muted");
    }
    this.setFooter(`AGENT_LLM_MODE=${mode}  model=${model}`, "ok");
  }

  async cmdGenerate() {
    const usable = (this.stories || []).some((b) => (b.stories || []).length);
    if (!usable) {
      this.setFooter("Load stories first (press o), then g.", "warn");
      return;
    }
    this.busy = true;
    this.setFooter(`Generating AI report for ${this.persona.name}…`, "busy");
    this.append(`— generate (${this.persona.name}) —`, "muted");
    this.render();
    let sawToken = false;
    try {
      for await (const event of generateStream(this.persona, this.stories)) {
        if (event.type === "meta") {
          this.append(`Provider: ${event.provider} / ${event.model}`, "muted");
          this.append("Prompt:", "muted");
          this.append(String(event.input || ""), "prompt");
          this.append("Response:", "muted");
        } else if (event.type === "token") {
          this.appendToken(String(event.text || ""), "response");
          sawToken = true;
          this.setFooter(`Streaming… ${this.persona.name}`, "busy");
        } else if (event.type === "error") {
          if (sawToken) this.append("");
          this.append(`Error: ${event.message || "Generation error"}`, "error");
          this.setFooter(String(event.message || "Generation error"), "error");
        } else if (event.type === "metrics") {
          if (sawToken) this.append("");
          const m = event.metrics || {};
          this.append(
            `Metrics: latency_ms=${m.latency_ms ?? "—"}  ttft_ms=${m.ttft_ms ?? "—"}  ` +
              `prompt_tokens=${m.prompt_tokens ?? "—"}  completion_tokens=${m.completion_tokens ?? "—"}  ` +
              `total_tokens=${m.total_tokens ?? "—"}  finish_reason=${m.finish_reason ?? "—"}`,
            "muted"
          );
        } else if (event.type === "done") {
          this.setFooter(`Done — report complete for ${this.persona.name}.`, "ok");
        }
        this.render();
      }
    } catch (exc) {
      this.append(`Error: ${exc.message || exc}`, "error");
      this.setFooter(String(exc.message || exc), "error");
    } finally {
      this.busy = false;
    }
  }
}

function readKeypress() {
  return new Promise((resolve) => {
    const onKeypress = (str, key) => {
      process.stdin.off("keypress", onKeypress);
      resolve({ str: str || "", key: key || {} });
    };
    process.stdin.on("keypress", onKeypress);
  });
}

async function main() {
  if (!process.stdin.isTTY) {
    console.error("node-console requires an interactive TTY.");
    process.exit(1);
  }

  readline.emitKeypressEvents(process.stdin);
  process.stdin.setRawMode(true);
  process.stdin.resume();

  const mode = await ensureLlmMode();
  const app = new App();
  if (!(app.footerKind === "ok" && app.stories.length)) {
    app.setFooter(
      `Ready (${mode}/${modelLabel(mode)}). Arrow keys scroll. (m)ode cycles LLM.`,
      "info"
    );
  }

  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    try {
      process.stdin.removeAllListeners("keypress");
      if (process.stdin.isTTY) process.stdin.setRawMode(false);
      process.stdin.pause();
    } catch (_) {}
    process.stdout.write("\x1b[0m\n");
  };
  process.on("exit", cleanup);
  process.on("SIGINT", () => {
    cleanup();
    process.exit(0);
  });

  while (true) {
    app.render();
    const { str, key } = await readKeypress();

    // Quit always works (even while a fetch/generate is in flight).
    if ((key.ctrl && key.name === "c") || str === "q" || str === "Q" || key.name === "q") {
      break;
    }

    if (key.name === "up") {
      app.scrollBy(-1);
      continue;
    }
    if (key.name === "down") {
      app.scrollBy(1);
      continue;
    }
    if (key.name === "pageup") {
      app.scrollBy(-app.outputHeight());
      continue;
    }
    if (key.name === "pagedown") {
      app.scrollBy(app.outputHeight());
      continue;
    }

    if (app.busy) continue;

    const ch = (str || "").length === 1 ? str.toLowerCase() : "";
    if (ch === "s") await app.cmdStatus();
    else if (ch === "t") await app.cmdTickers();
    else if (ch === "o") await app.cmdStories();
    else if (ch === "g") await app.cmdGenerate();
    else if (ch === "m") await app.cmdMode();
    else if (ch === "n") app.cmdNextUser();
    else if (ch === "h" || ch === "?") {
      app.setFooter(`${MENU_LEFT.join("  ")}   ${MENU_RIGHT}`, "info");
    } else if (ch) {
      app.setFooter("Unknown key. Use menu hotkeys (t o s g m q n).", "warn");
    }
  }

  cleanup();
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
