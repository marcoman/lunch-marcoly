//! Console grid navigator — create and evaluate a single LaunchDarkly highlight flag.

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
use std::time::{Duration, Instant};

const FLAG_HIGHLIGHT: &str = "configure-grid-selection-green-highlight";
const DEFAULT_HIGHLIGHT: &str = "none";

const ROWS: [&str; 3] = ["t", "m", "b"];
const APP_BANNER: &str = "11-create-eval-flag[rust]";

const COLS: [&str; 3] = ["l", "m", "r"];

struct FlagValues {
    username: String,
    flag_value: String,
    highlight_color: String,
    color_label: String,
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

            let deadline = Instant::now() + Duration::from_secs(10);
            while !client.initialized() && Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(50));
            }
            if client.initialized() {
                Some(Arc::new(client))
            } else {
                eprintln!("Warning: LaunchDarkly SDK did not initialize — highlight defaults to none.");
                None
            }
        });
        if std::env::var("LD_SDK_KEY").is_err() {
            eprintln!("Warning: LD_SDK_KEY not set — highlight defaults to none.");
        }
        Self { client }
    }

    fn evaluate_highlight(&self, username: &str) -> FlagValues {
        let Some(client) = &self.client else {
            return build_response(username, DEFAULT_HIGHLIGHT);
        };
        let context = ContextBuilder::new(username).build().unwrap_or_else(|_| {
            ContextBuilder::new("anonymous").build().unwrap()
        });
        let raw = client.str_variation(
            &context,
            FLAG_HIGHLIGHT,
            DEFAULT_HIGHLIGHT.to_string(),
        );
        build_response(username, &raw)
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

fn normalize_highlight_color(raw: &str) -> String {
    let color = raw.trim().to_lowercase();
    if color_names().contains(color.as_str()) {
        color
    } else {
        "none".to_string()
    }
}

fn color_label(highlight_color: &str) -> String {
    if highlight_color == "none" {
        "(no-color)".to_string()
    } else {
        format!("({highlight_color})")
    }
}

fn build_response(username: &str, raw: &str) -> FlagValues {
    let color = normalize_highlight_color(raw);
    let flag_value = if raw.trim().is_empty() {
        "none".to_string()
    } else {
        raw.trim().to_string()
    };
    FlagValues {
        username: username.to_string(),
        flag_value,
        highlight_color: color.clone(),
        color_label: color_label(&color),
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
    let name_line = format!("Name: {} {}", username, flags.color_label);

    let mut y = 0u16;
    print_colored_line(out, y, APP_BANNER, None)?;
    y += 1;
    print_colored_line(out, y, &name_line, highlight)?;
    y += 1;
    print_colored_line(out, y, &format!("Flag value: {}", flags.flag_value), None)?;
    y += 1;
    print_colored_line(out, y, &format!("Current position: {}", format_pos(row, col)), None)?;
    y += 1;
    print_colored_line(out, y, &format!("Previous position: {prev_text}"), None)?;
    y += 2;
    print_colored_line(out, y, "Use arrow keys or WASD to move (L to logout, Q to quit).", None)?;
    y += 1;
    print_colored_line(out, y, "Toggle the flag in LaunchDarkly — changes appear within ~1s.", None)?;
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
    let mut last_eval;

    loop {
        let flags = app.evaluate_highlight(username);
        render(out, username, row, col, previous.as_ref(), &flags)?;
        last_eval = Instant::now();

        loop {
            if last_eval.elapsed() >= Duration::from_millis(500) {
                break;
            }
            if event::poll(Duration::from_millis(50))? {
                break;
            }
        }

        if last_eval.elapsed() >= Duration::from_millis(500) && !event::poll(Duration::from_millis(0))? {
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
    let args: Vec<String> = std::env::args().collect();
    if args.len() >= 3 && args[1] == "--evaluate-once" {
        let app = App::new();
        let result = app.evaluate_highlight(&args[2]);
        println!(
            "{{\"username\":\"{}\",\"flagValue\":\"{}\",\"highlightColor\":\"{}\",\"colorLabel\":\"{}\"}}",
            result.username.replace('\\', "\\\\").replace('"', "\\\""),
            result.flag_value.replace('\\', "\\\\").replace('"', "\\\""),
            result.highlight_color.replace('\\', "\\\\").replace('"', "\\\""),
            result.color_label.replace('\\', "\\\\").replace('"', "\\\""),
        );
        return Ok(());
    }

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
