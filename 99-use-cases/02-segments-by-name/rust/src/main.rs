//! Console grid navigator with LaunchDarkly segment-by-name highlight (string flag).

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::{Color, Print, SetBackgroundColor, SetForegroundColor},
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{Client, ConfigBuilder, ContextBuilder};
use std::collections::HashSet;
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Duration;

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

const FLAG_HIGHLIGHT: &str = "configure-grid-selection-green-highlight";
const DEFAULT_HIGHLIGHT: &str = "none";

const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];

const SEGMENT_GENERIC: &str = "generic";
const SEGMENT_NAMED_COLOR: &str = "named-color";
const SEGMENT_HUMAN: &str = "human";
const SEGMENT_ROBOT: &str = "robot";
const SEGMENT_HUMAN_BETA: &str = "human-beta";
const SEGMENT_ROBOT_BETA: &str = "robot-beta";

struct SegmentInfo {
    segment_type: String,
    named_color: Option<String>,
}

struct FlagValues {
    highlight_color: String,
    segment_label: String,
    segment_type: String,
}

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

struct App {
    client: Option<Arc<Client>>,
}

impl App {
    fn new() -> Self {
        let client = std::env::var("LD_SDK_KEY").ok().and_then(|key| {
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
        Self { client }
    }

    fn evaluate_highlight(&self, username: &str) -> FlagValues {
        let info = resolve_segment_info(username);
        let Some(client) = &self.client else {
            return build_flag_response(DEFAULT_HIGHLIGHT, &info);
        };
        let context = build_segment_context(username, &info);
        let raw = client.str_variation(
            &context,
            FLAG_HIGHLIGHT,
            DEFAULT_HIGHLIGHT.to_string(),
        );
        build_flag_response(&raw, &info)
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

fn color_names() -> HashSet<&'static str> {
    ["yellow", "red", "blue", "green", "purple"]
        .into_iter()
        .collect()
}

fn letter_count(username: &str) -> usize {
    username.chars().filter(|ch| ch.is_alphabetic()).count()
}

fn resolve_segment_info(username: &str) -> SegmentInfo {
    let lower = username.to_lowercase();

    if lower == "generic" {
        return SegmentInfo {
            segment_type: SEGMENT_GENERIC.to_string(),
            named_color: None,
        };
    }
    if color_names().contains(lower.as_str()) {
        return SegmentInfo {
            segment_type: SEGMENT_NAMED_COLOR.to_string(),
            named_color: Some(lower),
        };
    }

    let is_human = letter_count(username) % 2 == 0;
    let is_beta = lower.contains("beta");

    let segment_type = if is_human && is_beta {
        SEGMENT_HUMAN_BETA
    } else if is_human {
        SEGMENT_HUMAN
    } else if is_beta {
        SEGMENT_ROBOT_BETA
    } else {
        SEGMENT_ROBOT
    };

    SegmentInfo {
        segment_type: segment_type.to_string(),
        named_color: None,
    }
}

fn build_segment_context(username: &str, info: &SegmentInfo) -> launchdarkly_server_sdk::Context {
    let mut builder = ContextBuilder::new(username);
    builder.set_string("segmentType", info.segment_type.clone());

    match info.segment_type.as_str() {
        SEGMENT_GENERIC => {
            builder.set_bool("generic", true);
        }
        SEGMENT_NAMED_COLOR => {
            if let Some(color) = &info.named_color {
                builder.set_string("namedColor", color.clone());
            }
        }
        _ => {
            let user_kind = if info.segment_type.starts_with("human") {
                "human"
            } else {
                "robot"
            };
            builder.set_string("userKind", user_kind.to_string());
            builder.set_bool("beta", info.segment_type.ends_with("beta"));
        }
    }

    builder.build().unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap())
}

fn color_label_name(highlight_color: &str) -> &str {
    if highlight_color == "none" {
        "no-color"
    } else {
        highlight_color
    }
}

fn format_segment_label(info: &SegmentInfo, highlight_color: &str) -> String {
    let color_name = color_label_name(highlight_color);
    match info.segment_type.as_str() {
        SEGMENT_GENERIC => "(generic)".to_string(),
        SEGMENT_NAMED_COLOR => format!("({color_name})"),
        SEGMENT_HUMAN | SEGMENT_ROBOT | SEGMENT_HUMAN_BETA | SEGMENT_ROBOT_BETA => {
            format!("({}-{})", info.segment_type, color_name)
        }
        _ => format!("({color_name})"),
    }
}

fn normalize_highlight_color(raw: &str) -> String {
    let color = raw.trim().to_lowercase();
    if color_names().contains(color.as_str()) {
        color
    } else {
        "none".to_string()
    }
}

fn build_flag_response(highlight_color: &str, info: &SegmentInfo) -> FlagValues {
    let color = normalize_highlight_color(highlight_color);
    FlagValues {
        highlight_color: color.clone(),
        segment_label: format_segment_label(info, &color),
        segment_type: info.segment_type.clone(),
    }
}

fn term_color(color: &str) -> Option<Color> {
    match color {
        "yellow" => Some(Color::Yellow),
        "red" => Some(Color::Red),
        "blue" => Some(Color::Blue),
        "green" => Some(Color::Green),
        "purple" => Some(Color::Magenta),
        _ => None,
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

fn cell_line(selected: bool, line: usize) -> &'static str {
    if selected {
        match line {
            0 => "┏━━━┓",
            1 => "┃ X ┃",
            _ => "┗━━━┛",
        }
    } else {
        match line {
            0 => "┌───┐",
            1 => "│   │",
            _ => "└───┘",
        }
    }
}

fn print_colored_line(
    out: &mut impl Write,
    y: u16,
    text: &str,
    color: Option<Color>,
) -> io::Result<()> {
    queue!(out, MoveTo(0, y), SetBackgroundColor(Color::Rgb { r: 30, g: 30, b: 46 }))?;
    if let Some(c) = color {
        queue!(out, SetForegroundColor(c), Print(text), SetForegroundColor(Color::Reset))?;
    } else {
        queue!(out, Print(text))?;
    }
    Ok(())
}

fn render(
    out: &mut impl Write,
    username: &str,
    row: i32,
    col: i32,
    previous: Option<&Position>,
    flags: &FlagValues,
) -> io::Result<()> {
    execute!(out, MoveTo(0, 0), terminal::Clear(ClearType::All))?;

    let prev_text = previous
        .map(|p| format_pos(p.row, p.col))
        .unwrap_or_else(|| "—".to_string());

    let highlight = term_color(&flags.highlight_color);
    let name_line = format!("Name: {} {}", username, flags.segment_label);

    let mut y = 0u16;
    print_colored_line(out, y, &name_line, highlight)?;
    y += 1;
    print_colored_line(out, y, &format!("Current position: {}", format_pos(row, col)), None)?;
    y += 1;
    print_colored_line(out, y, &format!("Previous position: {prev_text}"), None)?;
    y += 2;
    print_colored_line(out, y, "Use arrow keys or WASD to move (L to logout, Q to quit).", None)?;
    y += 2;

    let cell_color = if flags.highlight_color == "none" {
        None
    } else {
        term_color(&flags.highlight_color)
    };

    for r in 0..3 {
        for line_idx in 0..3 {
            let parts: Vec<String> = (0..3)
                .map(|c| {
                    let selected = r == row && c == col;
                    let text = cell_line(selected, line_idx);
                    if selected && cell_color.is_some() {
                        format!("\x1b[{}m{text}\x1b[0m", match cell_color {
                            Some(Color::Yellow) => "93",
                            Some(Color::Red) => "91",
                            Some(Color::Blue) => "94",
                            Some(Color::Green) => "92",
                            Some(Color::Magenta) => "35",
                            _ => "0",
                        })
                    } else {
                        text.to_string()
                    }
                })
                .collect();
            print_colored_line(out, y, &parts.join(" "), None)?;
            y += 1;
        }
    }

    out.flush()?;
    Ok(())
}

fn run_grid(out: &mut impl Write, app: &App, username: &str) -> io::Result<SessionAction> {
    let mut row = 1;
    let mut col = 1;
    let mut previous: Option<Position> = None;
    let flags = app.evaluate_highlight(username);

    loop {
        render(out, username, row, col, previous.as_ref(), &flags)?;

        if !event::poll(Duration::from_millis(100))? {
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
