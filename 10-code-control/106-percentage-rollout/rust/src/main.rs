//! Console grid navigator for a static LaunchDarkly percentage rollout.

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{Client, ConfigBuilder, ContextBuilder, Reason};
use std::collections::HashMap;
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Duration;

// LaunchDarkly: percentage rollout — sticky assignment by context key.
// https://launchdarkly.com/docs/home/flags/rollouts
const FLAG_KEY: &str = "enable-grid-selection-highlight-pct";
const DEFAULT_VALUE: &str = "none";
const APP_BANNER: &str = "16-percentage-rollout[rust]";
const CONFIGURED_GREEN_PCT: i32 = 30;
const HISTORY_LIMIT: usize = 8;
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";
const GREEN: &str = "\x1b[92m";
const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];

struct Position {
    row: i32,
    col: i32,
}

struct MoveResult {
    row: i32,
    col: i32,
    moved: bool,
}

#[derive(PartialEq, Eq)]
enum SessionAction {
    Quit,
    Logout,
}

struct FlagValues {
    flag_value: String,
    highlight_color: String,
    variation_index: Option<isize>,
    reason_kind: String,
}

struct HistoryItem {
    username: String,
    value: String,
    reason: String,
}

struct App {
    client: Option<Arc<Client>>,
}

fn format_reason(reason: &Reason) -> String {
    match reason {
        Reason::Off => "OFF".to_string(),
        Reason::Fallthrough { .. } => "FALLTHROUGH".to_string(),
        Reason::TargetMatch => "TARGET_MATCH".to_string(),
        Reason::RuleMatch { .. } => "RULE_MATCH".to_string(),
        Reason::PrerequisiteFailed { .. } => "PREREQUISITE_FAILED".to_string(),
        Reason::Error { .. } => "ERROR".to_string(),
    }
}

impl App {
    fn new() -> Self {
        let sdk_key = std::env::var("LD_SDK_KEY").ok().filter(|key| !key.trim().is_empty());
        let client = sdk_key.and_then(|key| {
            let config = ConfigBuilder::new(&key).build().ok()?;
            let client = Client::build(config).ok()?;
            client.start_with_runtime().ok()?;
            let deadline = std::time::Instant::now() + Duration::from_secs(5);
            while !client.initialized() && std::time::Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(50));
            }
            if client.initialized() {
                Some(Arc::new(client))
            } else {
                None
            }
        });
        Self { client }
    }

    fn evaluate(&self, username: &str) -> FlagValues {
        let Some(client) = &self.client else {
            return FlagValues {
                flag_value: DEFAULT_VALUE.to_string(),
                highlight_color: DEFAULT_VALUE.to_string(),
                variation_index: None,
                reason_kind: "ERROR".to_string(),
            };
        };
        let context = ContextBuilder::new(username)
            .kind("user")
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let detail = client.str_variation_detail(&context, FLAG_KEY, DEFAULT_VALUE.to_string());
        let raw = detail.value.unwrap_or_else(|| DEFAULT_VALUE.to_string());
        let value = if raw == "none" || raw == "green" {
            raw
        } else {
            DEFAULT_VALUE.to_string()
        };
        FlagValues {
            flag_value: value.clone(),
            highlight_color: value,
            variation_index: detail.variation_index,
            reason_kind: format_reason(&detail.reason),
        }
    }
}

impl Drop for App {
    fn drop(&mut self) {
        if let Some(client) = self.client.take() {
            if let Ok(client) = Arc::try_unwrap(client) {
                client.close();
            }
        }
    }
}

fn generated_username(base: &str, index: i32) -> String {
    if index <= 0 {
        base.to_string()
    } else {
        format!("{base}{index}")
    }
}

fn colorize(text: &str, color: &str) -> String {
    if color != "green" {
        text.to_string()
    } else {
        format!("{GREEN}{text}{RESET}{BG}")
    }
}

fn format_pos(row: i32, col: i32) -> String {
    format!("{}/{}", ROWS[row as usize], COLS[col as usize])
}

fn try_move(row: i32, col: i32, dr: i32, dc: i32) -> MoveResult {
    let nr = (row + dr).clamp(0, 2);
    let nc = (col + dc).clamp(0, 2);
    MoveResult {
        row: nr,
        col: nc,
        moved: nr != row || nc != col,
    }
}

fn variation_text(flags: &FlagValues) -> String {
    flags
        .variation_index
        .map(|index| index.to_string())
        .unwrap_or_else(|| "default".to_string())
}

fn observed_line(seen: &HashMap<String, String>) -> String {
    let total = seen.len();
    if total == 0 {
        return "Observed: no unique keys yet.".to_string();
    }
    let green_count = seen.values().filter(|value| *value == "green").count();
    let none_count = total - green_count;
    let pct = ((green_count as f64 / total as f64) * 1000.0).round() / 10.0;
    format!(
        "Observed: {green_count} green / {none_count} none of {total} unique → {pct}% (configured {CONFIGURED_GREEN_PCT}%)"
    )
}

fn remember(
    username: &str,
    flags: &FlagValues,
    seen: &mut HashMap<String, String>,
    history: &mut Vec<HistoryItem>,
) {
    seen.insert(username.to_string(), flags.flag_value.clone());
    history.retain(|item| item.username != username);
    history.insert(
        0,
        HistoryItem {
            username: username.to_string(),
            value: flags.flag_value.clone(),
            reason: flags.reason_kind.clone(),
        },
    );
    history.truncate(HISTORY_LIMIT);
}

fn read_username() -> io::Result<String> {
    println!("{APP_BANNER}");
    println!("Login");
    println!("Username becomes the LaunchDarkly user context key.\n");
    loop {
        print!("Username: ");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        let name = line.trim().to_string();
        if !name.is_empty() {
            return Ok(name);
        }
        println!("Username is required.");
    }
}

fn cell_line(selected: bool, color: &str, line: usize) -> String {
    if selected {
        let plain = match line {
            0 => "┏━━━┓",
            1 => "┃ X ┃",
            _ => "┗━━━┛",
        };
        colorize(plain, color)
    } else {
        match line {
            0 => "┌───┐".to_string(),
            1 => "│   │".to_string(),
            _ => "└───┘".to_string(),
        }
    }
}

fn print_line(out: &mut impl Write, y: u16, text: &str) -> io::Result<()> {
    queue!(out, MoveTo(0, y), Print(text))?;
    Ok(())
}

fn render(
    out: &mut impl Write,
    username: &str,
    base: &str,
    index: i32,
    row: i32,
    col: i32,
    previous: Option<&Position>,
    flags: &FlagValues,
    seen: &HashMap<String, String>,
    history: &[HistoryItem],
) -> io::Result<()> {
    execute!(out, MoveTo(0, 0), terminal::Clear(ClearType::All))?;
    queue!(out, Print(BG))?;
    let prev_text = previous
        .map(|p| format_pos(p.row, p.col))
        .unwrap_or_else(|| "—".to_string());
    let prev_name = if index == 0 {
        "—".to_string()
    } else {
        generated_username(base, index - 1)
    };
    let mut y = 0u16;
    print_line(out, y, APP_BANNER)?;
    y += 1;
    print_line(out, y, &format!("Name: {}", colorize(username, &flags.highlight_color)))?;
    y += 1;
    print_line(out, y, &format!("Current: {}   Previous: {prev_text}", format_pos(row, col)))?;
    y += 1;
    print_line(
        out,
        y,
        &format!(
            "Flag value: {}   reason: {}   idx: {}",
            flags.flag_value,
            flags.reason_kind,
            variation_text(flags)
        ),
    )?;
    y += 1;
    print_line(out, y, &observed_line(seen))?;
    y += 1;
    print_line(
        out,
        y,
        &format!(
            "Arrows/WASD move.  N next ({})  P prev ({prev_name})  L logout  Q quit",
            generated_username(base, index + 1)
        ),
    )?;
    y += 2;
    for r in 0..3 {
        for line in 0..3 {
            let row_text = (0..3)
                .map(|c| {
                    let selected = r == row && c == col;
                    let color = if selected {
                        flags.highlight_color.as_str()
                    } else {
                        "none"
                    };
                    cell_line(selected, color, line)
                })
                .collect::<Vec<_>>()
                .join(" ");
            print_line(out, y, &row_text)?;
            y += 1;
        }
    }
    y += 1;
    print_line(out, y, "Recent evaluations")?;
    y += 1;
    if history.is_empty() {
        print_line(out, y, "(none yet)")?;
    } else {
        for item in history {
            print_line(
                out,
                y,
                &colorize(
                    &format!("{}  {}  {}", item.username, item.value, item.reason),
                    &item.value,
                ),
            )?;
            y += 1;
        }
    }
    out.flush()?;
    Ok(())
}

fn run_grid(out: &mut impl Write, app: &App, base: &str) -> io::Result<SessionAction> {
    let mut index = 0;
    let mut username = generated_username(base, index);
    let mut row = 1;
    let mut col = 1;
    let mut previous: Option<Position> = None;
    let mut seen: HashMap<String, String> = HashMap::new();
    let mut history: Vec<HistoryItem> = Vec::new();
    loop {
        let flags = app.evaluate(&username);
        remember(&username, &flags, &mut seen, &mut history);
        render(
            out,
            &username,
            base,
            index,
            row,
            col,
            previous.as_ref(),
            &flags,
            &seen,
            &history,
        )?;
        if !event::poll(Duration::from_millis(500))? {
            continue;
        }
        if let Event::Key(KeyEvent { code, modifiers, .. }) = event::read()? {
            if modifiers.contains(KeyModifiers::CONTROL) {
                return Ok(SessionAction::Quit);
            }
            match code {
                KeyCode::Char('q') | KeyCode::Char('Q') => return Ok(SessionAction::Quit),
                KeyCode::Char('l') | KeyCode::Char('L') => return Ok(SessionAction::Logout),
                KeyCode::Char('n') | KeyCode::Char('N') => {
                    index += 1;
                    username = generated_username(base, index);
                    row = 1;
                    col = 1;
                    previous = None;
                }
                KeyCode::Char('p') | KeyCode::Char('P') => {
                    if index > 0 {
                        index -= 1;
                        username = generated_username(base, index);
                        row = 1;
                        col = 1;
                        previous = None;
                    }
                }
                KeyCode::Up | KeyCode::Char('w') | KeyCode::Char('W') => {
                    apply_move(&mut row, &mut col, &mut previous, -1, 0);
                }
                KeyCode::Down | KeyCode::Char('s') | KeyCode::Char('S') => {
                    apply_move(&mut row, &mut col, &mut previous, 1, 0);
                }
                KeyCode::Left | KeyCode::Char('a') | KeyCode::Char('A') => {
                    apply_move(&mut row, &mut col, &mut previous, 0, -1);
                }
                KeyCode::Right | KeyCode::Char('d') | KeyCode::Char('D') => {
                    apply_move(&mut row, &mut col, &mut previous, 0, 1);
                }
                _ => {}
            }
        }
    }
}

fn apply_move(row: &mut i32, col: &mut i32, previous: &mut Option<Position>, dr: i32, dc: i32) {
    let result = try_move(*row, *col, dr, dc);
    if result.moved {
        *previous = Some(Position {
            row: *row,
            col: *col,
        });
        *row = result.row;
        *col = result.col;
    }
}

fn main() -> io::Result<()> {
    let app = App::new();
    let mut stdout = io::stdout();
    loop {
        let username = read_username()?;
        terminal::enable_raw_mode()?;
        execute!(stdout, Hide)?;
        let action = run_grid(&mut stdout, &app, &username)?;
        execute!(stdout, Show)?;
        terminal::disable_raw_mode()?;
        if action == SessionAction::Quit {
            break;
        }
    }
    Ok(())
}
