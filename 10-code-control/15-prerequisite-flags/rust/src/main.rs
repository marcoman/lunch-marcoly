//! Console grid navigator demonstrating LaunchDarkly flag prerequisites.

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{Client, ConfigBuilder, ContextBuilder, Reason};
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Duration;

// LaunchDarkly: evaluate the dependent flag even when its prerequisite fails.
// https://launchdarkly.com/docs/home/flags/prereqs
const FLAG_HIGHLIGHT: &str = "enable-grid-selection-highlight-prereq";
const FLAG_COUNT: &str = "show-navigation-move-count-prereq";
const APP_BANNER: &str = "15-prerequisite-flags[rust]";
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";
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
    username: String,
    highlight_color: String,
    show_move_count: bool,
    parent_value: String,
    parent_reason: String,
    child_value: bool,
    child_reason: String,
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
        Reason::PrerequisiteFailed { prerequisite_key } => {
            format!("PREREQUISITE_FAILED ({prerequisite_key})")
        }
        Reason::Error { .. } => "ERROR".to_string(),
    }
}

fn highlight_color(value: &str) -> String {
    match value {
        "green" | "yellow" | "red" | "blue" | "purple" | "pink" => value.to_string(),
        _ => "none".to_string(),
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
                eprintln!("Warning: LaunchDarkly SDK did not initialize.");
                None
            }
        });
        if std::env::var("LD_SDK_KEY").is_err() {
            eprintln!("Warning: LD_SDK_KEY not set — flags use safe defaults.");
        }
        Self { client }
    }

    fn evaluate_flags(&self, username: &str) -> FlagValues {
        let user_key = username.trim().to_lowercase();
        let Some(client) = &self.client else {
            return FlagValues {
                username: user_key,
                highlight_color: "none".to_string(),
                show_move_count: false,
                parent_value: "none".to_string(),
                parent_reason: "OFFLINE".to_string(),
                child_value: false,
                child_reason: "OFFLINE".to_string(),
            };
        };
        let context = ContextBuilder::new(&user_key)
            .kind("user")
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let parent = client.str_variation_detail(&context, FLAG_HIGHLIGHT, "none".to_string());
        let child = client.bool_variation_detail(&context, FLAG_COUNT, false);
        let parent_value = parent.value.unwrap_or_else(|| "none".to_string());
        let child_value = child.value.unwrap_or(false);
        FlagValues {
            username: user_key,
            highlight_color: highlight_color(&parent_value),
            show_move_count: child_value,
            parent_value,
            parent_reason: format_reason(&parent.reason),
            child_value,
            child_reason: format_reason(&child.reason),
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
    let ansi = ansi_color(color);
    if ansi.is_empty() {
        text.to_string()
    } else {
        format!("{ansi}{text}{RESET}{BG}")
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
    println!("{APP_BANNER}");
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
    let mut y = 0u16;
    print_line(out, y, APP_BANNER)?;
    y += 1;
    print_line(out, y, &format!("Name: {}", colorize(username, &flags.highlight_color)))?;
    y += 1;
    print_line(out, y, &format!("Current position: {}", format_pos(row, col)))?;
    y += 1;
    print_line(out, y, &format!("Previous position: {prev_text}"))?;
    if flags.show_move_count {
        y += 1;
        print_line(out, y, &format!("Count: {move_count}"))?;
    }
    y += 2;
    print_line(
        out,
        y,
        &format!("Parent: {}  {}", flags.parent_value, flags.parent_reason),
    )?;
    y += 1;
    print_line(
        out,
        y,
        &format!("Child:  {}  {}", flags.child_value, flags.child_reason),
    )?;
    y += 2;
    print_line(out, y, "Use arrow keys or WASD to move (L to logout, Q to quit).")?;
    y += 2;
    for r in 0..3 {
        let top = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected {
                    flags.highlight_color.as_str()
                } else {
                    "none"
                };
                cell_line(selected, color, 0)
            })
            .collect::<Vec<_>>()
            .join(" ");
        let mid = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected {
                    flags.highlight_color.as_str()
                } else {
                    "none"
                };
                cell_line(selected, color, 1)
            })
            .collect::<Vec<_>>()
            .join(" ");
        let bot = (0..3)
            .map(|c| {
                let selected = r == row && c == col;
                let color = if selected {
                    flags.highlight_color.as_str()
                } else {
                    "none"
                };
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
        render(
            out,
            &flags.username,
            row,
            col,
            previous.as_ref(),
            move_count,
            &flags,
        )?;
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
