//! Console grid navigator with LaunchDarkly flag evaluation.

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{AttributeValue, Client, ConfigBuilder, ContextBuilder};
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Duration;

// LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/evaluating

const FLAG_HIGHLIGHT: &str = "configure-grid-selection-green-highlight";
const FLAG_CONTEXT: &str = "configure-grid-selection-context-highlight";
const FLAG_COUNT: &str = "show-navigation-move-count";
const FLAG_OS_EMOJI: &str = "show-host-os-emoji";
const HOST_OS_ATTR: &str = "hostOs";

const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";

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
    show_move_count: bool,
    highlight_color: String,
    cohort_label: String,
    os_emoji: String,
}

struct Cohorts {
    human: bool,
    robot: bool,
    beta: bool,
}

struct App {
    client: Option<Arc<Client>>,
    host_os: String,
}

fn detect_host_os() -> String {
    match std::env::consts::OS {
        "linux" => "linux",
        "windows" => "windows",
        "macos" => "macos",
        _ => "other",
    }
    .to_string()
}

fn os_emoji_for(host_os: &str, show_os_emoji: bool) -> String {
    if !show_os_emoji {
        return String::new();
    }
    match host_os {
        "linux" => "🐧".to_string(),
        "macos" => "🍎".to_string(),
        "windows" => "🪟".to_string(),
        _ => "😊".to_string(),
    }
}

fn display_name(username: &str, os_emoji: &str) -> String {
    if os_emoji.is_empty() {
        username.to_string()
    } else {
        format!("{os_emoji} {username}")
    }
}

fn parse_cohorts(username: &str) -> Cohorts {
    let lower = username.to_lowercase();
    Cohorts {
        human: lower.contains("human"),
        robot: lower.contains("robot"),
        beta: lower.contains("beta"),
    }
}

fn color_label_name(highlight_color: &str) -> &str {
    if highlight_color == "none" {
        "no-color"
    } else {
        highlight_color
    }
}

fn format_cohort_label(username: &str, highlight_color: &str, context_highlight: bool) -> String {
    let color_name = color_label_name(highlight_color);
    let mut parts = Vec::new();
    if context_highlight {
        let cohorts = parse_cohorts(username);
        if cohorts.human {
            parts.push("human");
        }
        if cohorts.robot {
            parts.push("robot");
        }
        if cohorts.beta {
            parts.push("beta");
        }
    }
    if parts.is_empty() {
        format!("({color_name})")
    } else {
        format!("({}-{})", parts.join("-"), color_name)
    }
}

fn resolve_highlight_color(username: &str, highlight_enabled: bool, context_highlight: bool) -> String {
    if !highlight_enabled {
        return "none".to_string();
    }
    if !context_highlight {
        return "pink".to_string();
    }
    let cohorts = parse_cohorts(username);
    if cohorts.human && cohorts.beta {
        return "green".to_string();
    }
    if cohorts.robot && cohorts.beta {
        return "purple".to_string();
    }
    if cohorts.human {
        return "yellow".to_string();
    }
    if cohorts.robot {
        return "red".to_string();
    }
    if cohorts.beta {
        return "blue".to_string();
    }
    "pink".to_string()
}

fn build_flag_response(
    username: &str,
    highlight_enabled: bool,
    context_highlight: bool,
    show_move_count: bool,
    show_os_emoji: bool,
    host_os: &str,
) -> FlagValues {
    let color = resolve_highlight_color(username, highlight_enabled, context_highlight);
    let label = format_cohort_label(username, &color, context_highlight);
    FlagValues {
        show_move_count,
        highlight_color: color,
        cohort_label: label,
        os_emoji: os_emoji_for(host_os, show_os_emoji),
    }
}

fn ansi_color(color: &str) -> &'static str {
    match color {
        "pink" => "\x1b[95m",
        "yellow" => "\x1b[93m",
        "red" => "\x1b[91m",
        "blue" => "\x1b[94m",
        "green" => "\x1b[92m",
        "purple" => "\x1b[35m",
        _ => "",
    }
}

fn colorize(text: &str, color: &str) -> String {
    if color.is_empty() || color == "none" {
        return text.to_string();
    }
    let ansi = ansi_color(color);
    if ansi.is_empty() {
        text.to_string()
    } else {
        format!("{ansi}{text}{RESET}{BG}")
    }
}

impl App {
    fn new() -> Self {
        let sdk_key = std::env::var("LD_SDK_KEY").ok();
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
                eprintln!("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
                None
            }
        });
        if std::env::var("LD_SDK_KEY").is_err() {
            eprintln!("Warning: LD_SDK_KEY not set — flags default to off.");
        }
        Self {
            client,
            host_os: detect_host_os(),
        }
    }

    fn evaluate_flags(&self, username: &str) -> FlagValues {
        let Some(client) = &self.client else {
            return build_flag_response(username, false, false, false, false, &self.host_os);
        };
        let context = ContextBuilder::new(username)
            .set_value(
                HOST_OS_ATTR,
                AttributeValue::String(self.host_os.clone().into()),
            )
            .add_private_attribute(HOST_OS_ATTR)
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let highlight = client.bool_variation(&context, FLAG_HIGHLIGHT, false);
        let context_highlight = client.bool_variation(&context, FLAG_CONTEXT, false);
        let show_count = client.bool_variation(&context, FLAG_COUNT, false);
        let show_os_emoji = client.bool_variation(&context, FLAG_OS_EMOJI, false);
        build_flag_response(
            username,
            highlight,
            context_highlight,
            show_count,
            show_os_emoji,
            &self.host_os,
        )
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

fn format_pos(row: i32, col: i32) -> String {
    format!("{}/{}", ROWS[row as usize], COLS[col as usize])
}

fn try_move(row: i32, col: i32, dr: i32, dc: i32) -> MoveResult {
    let nr = (row + dr).clamp(0, 2);
    let nc = (col + dc).clamp(0, 2);
    if nr == row && nc == col {
        MoveResult { row, col, moved: false }
    } else {
        MoveResult {
            row: nr,
            col: nc,
            moved: true,
        }
    }
}

fn read_username() -> io::Result<String> {
    println!("Login\n");
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
    let plain = match line {
        0 => "┏━━━┓",
        1 => "┃ X ┃",
        _ => "┗━━━┛",
    };
    if selected {
        if !color.is_empty() && color != "none" {
            colorize(plain, color)
        } else {
            plain.to_string()
        }
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
    row: i32,
    col: i32,
    previous: Option<&Position>,
    move_count: i32,
    flags: &FlagValues,
) -> io::Result<()> {
    execute!(out, MoveTo(0, 0), terminal::Clear(ClearType::All))?;
    queue!(out, Print(BG))?;

    let prev_text = previous
        .map(|p| format_pos(p.row, p.col))
        .unwrap_or_else(|| "—".to_string());

    let cohort = format!(" {}", flags.cohort_label);

    let mut y = 0u16;
    print_line(
        out,
        y,
        &format!(
            "Name: {}{}",
            colorize(&display_name(username, &flags.os_emoji), &flags.highlight_color),
            colorize(&cohort, &flags.highlight_color)
        ),
    )?;
    y += 1;
    print_line(out, y, &format!("Current position: {}", format_pos(row, col)))?;
    y += 1;
    print_line(out, y, &format!("Previous position: {prev_text}"))?;
    if flags.show_move_count {
        y += 1;
        print_line(out, y, &format!("Count: {move_count}"))?;
    }
    y += 2;
    print_line(out, y, "Use arrow keys or WASD to move (L to logout, Q to quit).")?;
    y += 2;

    for r in 0..3 {
        let cell_color = &flags.highlight_color;
        let top = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected { cell_color.as_str() } else { "none" };
                cell_line(selected, color, 0)
            })
            .collect::<Vec<_>>()
            .join(" ");
        let mid = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected { cell_color.as_str() } else { "none" };
                cell_line(selected, color, 1)
            })
            .collect::<Vec<_>>()
            .join(" ");
        let bot = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected { cell_color.as_str() } else { "none" };
                cell_line(selected, color, 2)
            })
            .collect::<Vec<_>>()
            .join(" ");
        print_line(out, y, &top)?;
        y += 1;
        print_line(out, y, &mid)?;
        y += 1;
        print_line(out, y, &bot)?;
        y += 1;
    }

    out.flush()?;
    Ok(())
}

fn run_grid(out: &mut impl Write, app: &App, username: &str) -> io::Result<SessionAction> {
    let mut row = 1;
    let mut col = 1;
    let mut previous: Option<Position> = None;
    let mut move_count = 0;

    loop {
        let flags = app.evaluate_flags(username);
        render(out, username, row, col, previous.as_ref(), move_count, &flags)?;

        if !event::poll(Duration::from_millis(500))? {
            continue;
        }
        if let Event::Key(KeyEvent { code, modifiers, .. }) = event::read()? {
            if modifiers.contains(KeyModifiers::CONTROL) {
                return Ok(SessionAction::Quit);
            }
            let movement = match code {
                KeyCode::Char('q') | KeyCode::Char('Q') => return Ok(SessionAction::Quit),
                KeyCode::Char('l') | KeyCode::Char('L') => return Ok(SessionAction::Logout),
                KeyCode::Up | KeyCode::Char('w') | KeyCode::Char('W') => Some((-1, 0)),
                KeyCode::Down | KeyCode::Char('s') | KeyCode::Char('S') => Some((1, 0)),
                KeyCode::Left | KeyCode::Char('a') | KeyCode::Char('A') => Some((0, -1)),
                KeyCode::Right | KeyCode::Char('d') | KeyCode::Char('D') => Some((0, 1)),
                _ => None,
            };
            let Some((dr, dc)) = movement else {
                continue;
            };
            let result = try_move(row, col, dr, dc);
            if result.moved {
                previous = Some(Position { row, col });
                row = result.row;
                col = result.col;
                move_count += 1;
            }
        }
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
