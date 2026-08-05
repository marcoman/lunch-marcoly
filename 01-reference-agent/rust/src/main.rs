//! 01-reference-agent[rust] — terminal UI matching the Python / Node / Java / Go consoles.

mod agent;
mod yahoo;

use agent::{
    ensure_llm_mode, generate_stream, model_label, ollama_host, probe_ollama, resolve_mode,
    set_mode_override, StreamEvent, PERSONAS,
};
use crossterm::{
    cursor::MoveTo,
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, Clear, ClearType},
};
use regex::Regex;
use std::io::{self, IsTerminal, Write};
use std::time::Duration;
use yahoo::{
    fetch_stories_for_tickers, get_last_pair_cached, normalize_ticker, TickerBlock,
    DEFAULT_TICKER_1, DEFAULT_TICKER_2,
};

const APP_BANNER: &str = "01-reference-agent[rust]";
const CHROME_ROWS: u16 = 3;
const FOOTER_ROWS: u16 = 1;
const PAD_MAX: usize = 4000;
const MENU_RIGHT: &str = "(n)ext user";
const MENU_LEFT: [&str; 6] = [
    "(t)ickers",
    "st(o)ries",
    "(s)tatus",
    "(g)enerate report",
    "(m)ode",
    "(q)uit",
];
const LLM_MODES: [&str; 3] = ["stub", "ollama", "bedrock"];

const RESET: &str = "\x1b[0m";
const BOLD: &str = "\x1b[1m";
const DIM: &str = "\x1b[2m";
const CYAN: &str = "\x1b[36m";
const YELLOW: &str = "\x1b[33m";
const GREEN: &str = "\x1b[32m";
const MAGENTA: &str = "\x1b[35m";
const BLUE: &str = "\x1b[34m";
const RED: &str = "\x1b[31m";
const WHITE: &str = "\x1b[37m";

#[derive(Clone)]
struct PadLine {
    text: String,
    kind: String,
}

struct App {
    persona_index: usize,
    ticker1: String,
    ticker2: String,
    stories: Vec<TickerBlock>,
    pad_lines: Vec<PadLine>,
    scroll: usize,
    footer: String,
    footer_kind: String,
    busy: bool,
}

fn paint(text: &str, kind: &str) -> String {
    let style = match kind {
        "hotkey" => format!("{BOLD}{CYAN}"),
        "name" => format!("{BOLD}{YELLOW}"),
        "ok" => format!("{BOLD}{GREEN}"),
        "error" => format!("{BOLD}{RED}"),
        "busy" => format!("{BOLD}{CYAN}"),
        "warn" => format!("{BOLD}{YELLOW}"),
        "muted" => format!("{DIM}{WHITE}"),
        "ticker1" | "story1" => format!("{BOLD}{GREEN}"),
        "ticker2" | "story2" => format!("{BOLD}{MAGENTA}"),
        "prompt" => BLUE.to_string(),
        "response" => CYAN.to_string(),
        _ => String::new(),
    };
    if style.is_empty() {
        text.to_string()
    } else {
        format!("{style}{text}{RESET}")
    }
}

fn clip(text: &str, width: usize) -> String {
    if width == 0 {
        return String::new();
    }
    let count = text.chars().count();
    if count <= width {
        return text.to_string();
    }
    if width <= 1 {
        return text.chars().take(width).collect();
    }
    let mut s: String = text.chars().take(width - 1).collect();
    s.push('…');
    s
}

fn align_pair(left: &str, right: &str, width: usize, gap: usize) -> String {
    if width == 0 {
        return String::new();
    }
    let gap = gap.max(2);
    let mut left = left.to_string();
    let mut right = right.to_string();
    if left.chars().count() + gap + right.chars().count() > width {
        let room = width.saturating_sub(gap + left.chars().count());
        right = clip(&right, room);
        let room = width.saturating_sub(gap + right.chars().count());
        left = clip(&left, room);
    }
    let pad = gap.max(width.saturating_sub(left.chars().count() + right.chars().count()));
    clip(&(left + &" ".repeat(pad) + &right), width)
}

fn term_size() -> (u16, u16) {
    terminal::size().unwrap_or((100, 32))
}

fn style_hotkeys(text: &str) -> String {
    let re = Regex::new(r"\(([A-Za-z])\)").unwrap();
    re.replace_all(text, |caps: &regex::Captures| {
        format!("({})", paint(&caps[1], "hotkey"))
    })
    .into_owned()
}

fn wrap_text(text: &str, width: usize) -> Vec<String> {
    if text.is_empty() {
        return vec![String::new()];
    }
    let mut out = Vec::new();
    for raw in text.split('\n') {
        if raw.is_empty() {
            out.push(String::new());
            continue;
        }
        let mut rest: String = raw.to_string();
        while rest.chars().count() > width {
            let chunk: String = rest.chars().take(width).collect();
            rest = rest.chars().skip(width).collect();
            out.push(chunk);
        }
        out.push(rest);
    }
    if out.is_empty() {
        vec![String::new()]
    } else {
        out
    }
}

fn story_count(stories: &[TickerBlock], ticker: &str) -> usize {
    let symbol = normalize_ticker(ticker);
    stories
        .iter()
        .find(|b| normalize_ticker(&b.ticker) == symbol)
        .map(|b| b.stories.len())
        .unwrap_or(0)
}

fn tickers_label(t1: &str, t2: &str, stories: &[TickerBlock]) -> String {
    let a = if t1.is_empty() { "(not set)" } else { t1 };
    let b = if t2.is_empty() { "(not set)" } else { t2 };
    format!(
        "Tickers: {a} ({} stories) {b} ({} stories)",
        story_count(stories, t1),
        story_count(stories, t2)
    )
}

fn opt_num<T: std::fmt::Display>(v: Option<T>) -> String {
    v.map(|x| x.to_string()).unwrap_or_else(|| "—".into())
}

impl App {
    fn new() -> Self {
        let mut app = Self {
            persona_index: 0,
            ticker1: DEFAULT_TICKER_1.into(),
            ticker2: DEFAULT_TICKER_2.into(),
            stories: vec![],
            pad_lines: vec![],
            scroll: 0,
            footer: "Ready.".into(),
            footer_kind: "info".into(),
            busy: false,
        };
        app.restore_cache();
        app
    }

    fn persona(&self) -> &agent::Persona {
        &PERSONAS[self.persona_index]
    }

    fn restore_cache(&mut self) {
        if let Some((t1, t2, blocks)) = get_last_pair_cached() {
            self.ticker1 = t1;
            self.ticker2 = t2;
            self.stories = blocks;
            self.footer = "Restored saved stories from disk cache.".into();
            self.footer_kind = "ok".into();
        }
    }

    fn set_footer(&mut self, text: impl Into<String>, kind: &str) {
        self.footer = text.into();
        self.footer_kind = kind.into();
    }

    fn output_height(&self) -> usize {
        let (_, rows) = term_size();
        (rows as usize)
            .saturating_sub(CHROME_ROWS as usize)
            .saturating_sub(FOOTER_ROWS as usize)
            .max(1)
    }

    fn scroll_to_bottom(&mut self) {
        self.scroll = self.pad_lines.len().saturating_sub(self.output_height());
    }

    fn scroll_by(&mut self, delta: isize) {
        let max_scroll = self.pad_lines.len().saturating_sub(self.output_height());
        let next = self.scroll as isize + delta;
        self.scroll = next.clamp(0, max_scroll as isize) as usize;
    }

    fn append(&mut self, text: &str, kind: &str) {
        let (cols, _) = term_size();
        let width = (cols as usize).saturating_sub(1).max(20);
        for line in wrap_text(text, width) {
            self.pad_lines.push(PadLine {
                text: line,
                kind: kind.into(),
            });
        }
        if self.pad_lines.len() > PAD_MAX {
            let drop_n = self.pad_lines.len() - PAD_MAX;
            self.pad_lines.drain(0..drop_n);
        }
        self.scroll_to_bottom();
    }

    fn append_token(&mut self, token: &str, kind: &str) {
        if token.is_empty() {
            return;
        }
        let (cols, _) = term_size();
        let width = (cols as usize).saturating_sub(1).max(20);
        let parts: Vec<&str> = token.split('\n').collect();
        for (i, part) in parts.iter().enumerate() {
            if i > 0 {
                self.pad_lines.push(PadLine {
                    text: String::new(),
                    kind: kind.into(),
                });
            }
            if part.is_empty() {
                continue;
            }
            if self.pad_lines.is_empty() {
                self.pad_lines.push(PadLine {
                    text: String::new(),
                    kind: kind.into(),
                });
            }
            let last = self.pad_lines.last().unwrap();
            if last.kind != kind && !last.text.is_empty() {
                self.pad_lines.push(PadLine {
                    text: String::new(),
                    kind: kind.into(),
                });
            }
            let current = self.pad_lines.last().unwrap().text.clone();
            let combined = format!("{current}{part}");
            if combined.chars().count() <= width {
                let last = self.pad_lines.last_mut().unwrap();
                last.text = combined;
                last.kind = kind.into();
            } else {
                let cur_len = current.chars().count();
                let space = width.saturating_sub(cur_len);
                let part_chars: Vec<char> = part.chars().collect();
                if space > 0 {
                    let last = self.pad_lines.last_mut().unwrap();
                    last.text = format!(
                        "{current}{}",
                        part_chars.iter().take(space).collect::<String>()
                    );
                    last.kind = kind.into();
                    let mut rest = &part_chars[space..];
                    while !rest.is_empty() {
                        let n = rest.len().min(width);
                        self.pad_lines.push(PadLine {
                            text: rest[..n].iter().collect(),
                            kind: kind.into(),
                        });
                        rest = &rest[n..];
                    }
                } else {
                    let mut rest = part_chars.as_slice();
                    while !rest.is_empty() {
                        let n = rest.len().min(width);
                        self.pad_lines.push(PadLine {
                            text: rest[..n].iter().collect(),
                            kind: kind.into(),
                        });
                        rest = &rest[n..];
                    }
                }
            }
        }
        if self.pad_lines.len() > PAD_MAX {
            let drop_n = self.pad_lines.len() - PAD_MAX;
            self.pad_lines.drain(0..drop_n);
        }
        self.scroll_to_bottom();
    }

    fn render(&self, out: &mut impl Write) -> io::Result<()> {
        let (cols, _) = term_size();
        let width = (cols as usize).saturating_sub(1).max(1);
        let mode = resolve_mode();
        let model = model_label(&mode);
        let right0 = tickers_label(&self.ticker1, &self.ticker2, &self.stories);
        let left1 = format!("AGENT_LLM_MODE={mode}  model={model}");
        let name_label = format!("Name: {}.", self.persona().name);
        let left_menu = MENU_LEFT.join("  ");

        let chrome0 = align_pair(APP_BANNER, &right0, width, 2);
        let chrome1 = align_pair(&left1, &name_label, width, 2);
        let chrome2 = align_pair(&left_menu, MENU_RIGHT, width, 2);

        execute!(out, MoveTo(0, 0), Clear(ClearType::All))?;

        let mut y = 0u16;
        let c0_right = chrome0.rfind(&right0).unwrap_or(0);
        let line0 = format!(
            "{}{}{}\x1b[K",
            paint(APP_BANNER, "muted"),
            " ".repeat(c0_right.saturating_sub(APP_BANNER.chars().count())),
            clip(&right0, width.saturating_sub(c0_right))
        );
        queue!(out, MoveTo(0, y), Print(line0))?;
        y += 1;

        let c1_right = chrome1.rfind(&name_label).unwrap_or(0);
        let line1 = format!(
            "{}{}Name: {}.\x1b[K",
            clip(&left1, c1_right),
            " ".repeat(c1_right.saturating_sub(left1.chars().count())),
            paint(self.persona().name, "name")
        );
        queue!(out, MoveTo(0, y), Print(line1))?;
        y += 1;

        let c2_right = chrome2.rfind(MENU_RIGHT).unwrap_or(0);
        let line2 = format!(
            "{}{}{}\x1b[K",
            style_hotkeys(&clip(&left_menu, c2_right)),
            " ".repeat(c2_right.saturating_sub(left_menu.chars().count())),
            style_hotkeys(MENU_RIGHT)
        );
        queue!(out, MoveTo(0, y), Print(line2))?;
        y += 1;

        let view_h = self.output_height();
        let end = (self.scroll + view_h).min(self.pad_lines.len());
        let slice = &self.pad_lines[self.scroll..end];
        for i in 0..view_h {
            if i < slice.len() {
                let entry = &slice[i];
                let line = format!("{}\x1b[K", paint(&clip(&entry.text, width), &entry.kind));
                queue!(out, MoveTo(0, y), Print(line))?;
            } else {
                queue!(out, MoveTo(0, y), Print("\x1b[K"))?;
            }
            y += 1;
        }
        let footer = format!(
            "{}\x1b[K",
            paint(&clip(&self.footer, width), &self.footer_kind)
        );
        queue!(out, MoveTo(0, y), Print(footer))?;
        out.flush()?;
        Ok(())
    }

    fn append_stories(&mut self) {
        if self.stories.is_empty() {
            self.append("  (no stories loaded — press o)", "muted");
            return;
        }
        for (index, block) in self.stories.clone().iter().enumerate() {
            let slot = if index == 0 { 1 } else { 2 };
            let ticker = if block.ticker.is_empty() {
                "?"
            } else {
                block.ticker.as_str()
            };
            let name = if block.name.is_empty() {
                ticker
            } else {
                block.name.as_str()
            };
            let cache = if block.from_cache { " [cached]" } else { "" };
            self.append(
                &format!("  {ticker} ({name}){cache}"),
                &format!("ticker{slot}"),
            );
            if block.stories.is_empty() {
                let msg = block
                    .error
                    .clone()
                    .unwrap_or_else(|| "no stories".into());
                self.append(&format!("    · {msg}"), "muted");
                continue;
            }
            for story in &block.stories {
                let mut line = format!(
                    "    · {}",
                    if story.title.is_empty() {
                        "(untitled)"
                    } else {
                        &story.title
                    }
                );
                if !story.publisher.is_empty() {
                    line.push_str(" — ");
                    line.push_str(&story.publisher);
                }
                self.append(&line, &format!("story{slot}"));
            }
            if let Some(err) = &block.error {
                self.append(&format!("    note: {err}"), "warn");
            }
        }
    }

    fn cmd_status(&mut self) {
        let mode = resolve_mode();
        let p = *self.persona();
        self.append("— status —", "muted");
        self.append(&format!("User:     {} ({})", p.name, p.profile), "name");
        self.append(&format!("Tickers:  {}", self.ticker1), "ticker1");
        self.append(&format!("          {}", self.ticker2), "ticker2");
        self.append(
            &format!("Provider: {mode} / {}", model_label(&mode)),
            "muted",
        );
        self.append("Stories:", "muted");
        self.append_stories();
        self.set_footer("Status shown.", "ok");
    }

    fn prompt_line(&mut self, out: &mut impl Write, label: &str) -> io::Result<String> {
        self.set_footer(label, "busy");
        self.render(out)?;
        terminal::disable_raw_mode()?;
        print!("{label}");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        terminal::enable_raw_mode()?;
        // Drain any pending key events from the cooked→raw transition.
        while event::poll(Duration::from_millis(0))? {
            let _ = event::read()?;
        }
        Ok(line.trim().to_string())
    }

    fn cmd_tickers(&mut self, out: &mut impl Write) -> io::Result<()> {
        let t1 = self.prompt_line(out, "Ticker 1: ")?;
        let t2 = self.prompt_line(out, "Ticker 2: ")?;
        if !t1.is_empty() {
            let n = normalize_ticker(&t1);
            self.ticker1 = if n.is_empty() {
                DEFAULT_TICKER_1.into()
            } else {
                n
            };
        }
        if !t2.is_empty() {
            let n = normalize_ticker(&t2);
            self.ticker2 = if n.is_empty() {
                DEFAULT_TICKER_2.into()
            } else {
                n
            };
        }
        self.append(
            &format!("Tickers set to {}  {}", self.ticker1, self.ticker2),
            "ok",
        );
        self.set_footer(
            format!("Tickers: {}  {}", self.ticker1, self.ticker2),
            "ok",
        );
        Ok(())
    }

    fn cmd_stories(&mut self, out: &mut impl Write) -> io::Result<()> {
        self.busy = true;
        self.set_footer(
            format!(
                "Fetching Yahoo stories for {} and {}…",
                self.ticker1, self.ticker2
            ),
            "busy",
        );
        self.render(out)?;
        let result = fetch_stories_for_tickers(&self.ticker1, &self.ticker2, 2);
        self.stories = result.tickers;
        self.append(
            &format!("— stories ({} / {}) —", self.ticker1, self.ticker2),
            "muted",
        );
        self.append_stories();
        if result.errors.is_empty() {
            self.set_footer("Stories loaded. Press g to generate.", "ok");
        } else {
            self.set_footer(result.errors.join(" · "), "warn");
        }
        self.busy = false;
        Ok(())
    }

    fn cmd_next_user(&mut self) {
        self.persona_index = (self.persona_index + 1) % PERSONAS.len();
        let p = *self.persona();
        self.append(&format!("User: {} ({})", p.name, p.profile), "name");
        self.set_footer(format!("User: {}", p.name), "ok");
    }

    fn cmd_mode(&mut self) {
        let current = resolve_mode();
        let idx = LLM_MODES.iter().position(|m| *m == current).unwrap_or(0);
        let nxt = LLM_MODES[(idx + 1) % LLM_MODES.len()];
        if nxt == "ollama" && !probe_ollama(Duration::from_millis(600)) {
            self.append(
                &format!(
                    "Ollama not reachable at {}. Start Ollama and pull a model.",
                    ollama_host()
                ),
                "warn",
            );
            self.set_footer("Ollama not reachable — mode left unchanged.", "warn");
            return;
        }
        set_mode_override(nxt);
        std::env::set_var("AGENT_LLM_MODE", nxt);
        let mode = resolve_mode();
        let model = model_label(&mode);
        self.append(
            &format!("Mode set to AGENT_LLM_MODE={mode}  model={model}"),
            "ok",
        );
        if mode == "ollama" {
            self.append(
                &format!("Using Ollama at {} with model {model}.", ollama_host()),
                "muted",
            );
        }
        self.set_footer(format!("AGENT_LLM_MODE={mode}  model={model}"), "ok");
    }

    fn cmd_generate(&mut self, out: &mut impl Write) -> io::Result<()> {
        let usable = self.stories.iter().any(|b| !b.stories.is_empty());
        if !usable {
            self.set_footer("Load stories first (press o), then g.", "warn");
            return Ok(());
        }
        self.busy = true;
        let persona = *self.persona();
        let persona_name = persona.name.to_string();
        let stories = self.stories.clone();
        self.set_footer(
            format!("Generating AI report for {persona_name}…"),
            "busy",
        );
        self.append(&format!("— generate ({persona_name}) —"), "muted");
        self.render(out)?;

        let mut saw_token = false;
        let mut render_err: Option<io::Error> = None;
        generate_stream(&persona, &stories, &mut |event| {
            if render_err.is_some() {
                return;
            }
            match event {
                StreamEvent::Meta {
                    provider,
                    model,
                    input,
                    ..
                } => {
                    self.append(&format!("Provider: {provider} / {model}"), "muted");
                    self.append("Prompt:", "muted");
                    self.append(&input, "prompt");
                    self.append("Response:", "muted");
                }
                StreamEvent::Token { text } => {
                    self.append_token(&text, "response");
                    saw_token = true;
                    self.set_footer(format!("Streaming… {persona_name}"), "busy");
                }
                StreamEvent::Error { message } => {
                    if saw_token {
                        self.append("", "normal");
                    }
                    let msg = if message.is_empty() {
                        "Generation error".into()
                    } else {
                        message
                    };
                    self.append(&format!("Error: {msg}"), "error");
                    self.set_footer(msg, "error");
                }
                StreamEvent::Metrics { metrics: m } => {
                    if saw_token {
                        self.append("", "normal");
                    }
                    self.append(
                        &format!(
                            "Metrics: latency_ms={}  ttft_ms={}  prompt_tokens={}  completion_tokens={}  total_tokens={}  finish_reason={}",
                            opt_num(m.latency_ms),
                            opt_num(m.ttft_ms),
                            opt_num(m.prompt_tokens),
                            opt_num(m.completion_tokens),
                            opt_num(m.total_tokens),
                            m.finish_reason.unwrap_or_else(|| "—".into()),
                        ),
                        "muted",
                    );
                }
                StreamEvent::Done => {
                    self.set_footer(
                        format!("Done — report complete for {persona_name}."),
                        "ok",
                    );
                }
            }
            if let Err(e) = self.render(out) {
                render_err = Some(e);
            }
        });
        self.busy = false;
        if let Some(e) = render_err {
            return Err(e);
        }
        Ok(())
    }
}

fn main() -> io::Result<()> {
    if !io::stdin().is_terminal() {
        eprintln!("rust console requires an interactive TTY.");
        std::process::exit(1);
    }

    let mode = ensure_llm_mode();
    let mut app = App::new();
    if !(app.footer_kind == "ok" && !app.stories.is_empty()) {
        app.set_footer(
            format!(
                "Ready ({}/{}). Arrow keys scroll. (m)ode cycles LLM.",
                mode,
                model_label(&mode)
            ),
            "info",
        );
    }

    let mut stdout = io::stdout();
    terminal::enable_raw_mode()?;
    let result = (|| -> io::Result<()> {
        loop {
            app.render(&mut stdout)?;
            if !event::poll(Duration::from_millis(250))? {
                continue;
            }
            let Event::Key(KeyEvent {
                code, modifiers, ..
            }) = event::read()?
            else {
                continue;
            };

            if modifiers.contains(KeyModifiers::CONTROL) && code == KeyCode::Char('c') {
                break;
            }
            match code {
                KeyCode::Char('q') | KeyCode::Char('Q') => break,
                KeyCode::Up => app.scroll_by(-1),
                KeyCode::Down => app.scroll_by(1),
                KeyCode::PageUp => app.scroll_by(-(app.output_height() as isize)),
                KeyCode::PageDown => app.scroll_by(app.output_height() as isize),
                _ if app.busy => {}
                KeyCode::Char('s') | KeyCode::Char('S') => app.cmd_status(),
                KeyCode::Char('t') | KeyCode::Char('T') => app.cmd_tickers(&mut stdout)?,
                KeyCode::Char('o') | KeyCode::Char('O') => app.cmd_stories(&mut stdout)?,
                KeyCode::Char('g') | KeyCode::Char('G') => app.cmd_generate(&mut stdout)?,
                KeyCode::Char('m') | KeyCode::Char('M') => app.cmd_mode(),
                KeyCode::Char('n') | KeyCode::Char('N') => app.cmd_next_user(),
                KeyCode::Char('h') | KeyCode::Char('H') | KeyCode::Char('?') => {
                    app.set_footer(format!("{}   {MENU_RIGHT}", MENU_LEFT.join("  ")), "info");
                }
                KeyCode::Char(_) => {
                    app.set_footer("Unknown key. Use menu hotkeys (t o s g m q n).", "warn");
                }
                _ => {}
            }
        }
        Ok(())
    })();

    terminal::disable_raw_mode()?;
    print!("{RESET}\r\n");
    let _ = stdout.flush();
    result
}
