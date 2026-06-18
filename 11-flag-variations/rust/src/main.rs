//! Console grid navigator with LaunchDarkly flag variation evaluation.

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

// LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
// See: https://launchdarkly.com/docs/sdk/features/flag-types
// See: https://launchdarkly.com/docs/sdk/features/anonymous

const FLAG_ANON_OS_EMOJI: &str = "show-anonymous-host-os-emoji";
const FLAG_COUNT_LABEL: &str = "configure-navigation-count-label";
const FLAG_LUCKY_NUMBER: &str = "configure-lucky-number";
const FLAG_MAX_MOVES: &str = "configure-max-navigation-moves";
const HOST_OS_ATTR: &str = "hostOs";
const ANONYMOUS_KEY: &str = "anonymous";

const DEFAULT_COUNT_LABEL: &str = "Count";
const DEFAULT_LUCKY_NUMBER: i64 = 0;
const DEFAULT_MAX_MOVES: i32 = 100;

const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];
const BG: &str = "\x1b[48;5;236m";

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
    count_label: String,
    lucky_number: i32,
    max_moves: i32,
    os_emoji: String,
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

fn parse_max_moves(raw: &serde_json::Value) -> i32 {
    raw.get("maxMoves")
        .and_then(|v| v.as_i64())
        .map(|n| n as i32)
        .unwrap_or(DEFAULT_MAX_MOVES)
}

fn build_flag_response(count_label: String, lucky_number: i32, max_moves: i32, os_emoji: String) -> FlagValues {
    FlagValues {
        count_label: if count_label.is_empty() {
            DEFAULT_COUNT_LABEL.to_string()
        } else {
            count_label
        },
        lucky_number,
        max_moves,
        os_emoji,
    }
}

fn defaults() -> FlagValues {
    build_flag_response(
        DEFAULT_COUNT_LABEL.to_string(),
        DEFAULT_LUCKY_NUMBER as i32,
        DEFAULT_MAX_MOVES,
        String::new(),
    )
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
            return defaults();
        };

        let anon_context = ContextBuilder::new(ANONYMOUS_KEY)
            .anonymous(true)
            .set_value(
                HOST_OS_ATTR,
                AttributeValue::String(self.host_os.clone().into()),
            )
            .add_private_attribute(HOST_OS_ATTR)
            .build()
            .unwrap_or_else(|_| ContextBuilder::new(ANONYMOUS_KEY).build().unwrap());

        let user_context = ContextBuilder::new(username)
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());

        let show_emoji = client.bool_variation(&anon_context, FLAG_ANON_OS_EMOJI, false);
        let count_label = client.str_variation(
            &user_context,
            FLAG_COUNT_LABEL,
            DEFAULT_COUNT_LABEL.to_string(),
        );
        let lucky_number = client.int_variation(&user_context, FLAG_LUCKY_NUMBER, DEFAULT_LUCKY_NUMBER);
        let max_moves_raw = client.json_variation(
            &user_context,
            FLAG_MAX_MOVES,
            serde_json::json!({ "maxMoves": DEFAULT_MAX_MOVES }),
        );

        build_flag_response(
            count_label,
            lucky_number as i32,
            parse_max_moves(&max_moves_raw),
            os_emoji_for(&self.host_os, show_emoji),
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
    print_line(
        out,
        y,
        &format!("Name: {}", display_name(username, &flags.os_emoji)),
    )?;
    y += 1;
    print_line(out, y, &format!("Current position: {}", format_pos(row, col)))?;
    y += 1;
    print_line(out, y, &format!("Previous position: {prev_text}"))?;
    y += 1;
    print_line(out, y, &format!("{}: {move_count}", flags.count_label))?;
    y += 1;
    print_line(out, y, &format!("Lucky Number is: {}", flags.lucky_number))?;
    y += 2;
    print_line(out, y, "Use arrow keys or WASD to move (L to logout, Q to quit).")?;
    y += 2;

    for r in 0..3 {
        let top = (0..3)
            .map(|c| cell_line(r == row && c == col, 0))
            .collect::<Vec<_>>()
            .join(" ");
        let mid = (0..3)
            .map(|c| cell_line(r == row && c == col, 1))
            .collect::<Vec<_>>()
            .join(" ");
        let bot = (0..3)
            .map(|c| cell_line(r == row && c == col, 2))
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
            if move_count >= flags.max_moves {
                continue;
            }
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
