//! Console grid navigator demonstrating LaunchDarkly targeting rules.

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

// LaunchDarkly targeting rules inspect the public team context attribute.
// No team omits it so evaluation reaches the plain fallthrough.
// https://launchdarkly.com/docs/home/flags/target-rules
const FLAG_TEAM_STYLE: &str = "configure-team-label-style";
const APP_BANNER: &str = "13-flag-targeting-rules[rust]";
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";
const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];

struct Login {
    username: String,
    team: String,
}

struct FlagValues {
    team_label: String,
    style: String,
}

struct Position {
    row: i32,
    col: i32,
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
                eprintln!(
                    "Warning: LaunchDarkly SDK did not initialize — flag uses plain default."
                );
                None
            }
        });
        if std::env::var("LD_SDK_KEY").is_err() {
            eprintln!("Warning: LD_SDK_KEY not set — flag uses plain default.");
        }
        Self { client }
    }

    /// Evaluate the string variation with team as a public context attribute.
    /// https://launchdarkly.com/docs/home/flags/context-attributes
    fn evaluate_flags(&self, username: &str, team: &str) -> FlagValues {
        let mut builder = ContextBuilder::new(username);
        if !team.is_empty() {
            builder.set_value("team", AttributeValue::String(team.to_string().into()));
        }
        let context = builder
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let candidate = self.client.as_ref().map_or_else(
            || "plain".to_string(),
            |client| client.str_variation(&context, FLAG_TEAM_STYLE, "plain".to_string()),
        );
        let style = match candidate.as_str() {
            "plain" | "colored-red" | "colored-blue" | "colored-yellow" => candidate,
            _ => "plain".to_string(),
        };
        FlagValues {
            team_label: team_label(team).to_string(),
            style,
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

fn team_label(team: &str) -> &'static str {
    match team {
        "red" => "Team Red",
        "blue" => "Team Blue",
        "yellow" => "Team Yellow",
        _ => "No team",
    }
}

fn colored_team(flags: &FlagValues) -> String {
    let color = match flags.style.as_str() {
        "colored-red" => "\x1b[31m",
        "colored-blue" => "\x1b[34m",
        "colored-yellow" => "\x1b[33m",
        _ => "",
    };
    if color.is_empty() {
        flags.team_label.clone()
    } else {
        format!("{color}{}{RESET}{BG}", flags.team_label)
    }
}

/// Prompt for the user key and public team attribute used by targeting rules.
fn read_login() -> io::Result<Login> {
    println!("{APP_BANNER}");
    println!("Login\n");
    let username = loop {
        print!("Username: ");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        let name = line.trim().to_string();
        if !name.is_empty() {
            break name;
        }
        println!("Username is required.");
    };

    let team = loop {
        print!("Team [1=None 2=Red 3=Blue 4=Yellow]: ");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        match line.trim() {
            "1" => break "",
            "2" => break "red",
            "3" => break "blue",
            "4" => break "yellow",
            _ => println!("Choose 1, 2, 3, or 4."),
        }
    };
    Ok(Login {
        username,
        team: team.to_string(),
    })
}

fn format_pos(row: i32, col: i32) -> String {
    format!("{}/{}", ROWS[row as usize], COLS[col as usize])
}

fn cell_line(selected: bool, line: usize) -> &'static str {
    if selected {
        ["┏━━━┓", "┃ X ┃", "┗━━━┛"][line]
    } else {
        ["┌───┐", "│   │", "└───┘"][line]
    }
}

fn print_line(out: &mut impl Write, y: u16, text: &str) -> io::Result<()> {
    queue!(out, MoveTo(0, y), Print(text), Print("\x1b[K"))?;
    Ok(())
}

fn render(
    out: &mut impl Write,
    login: &Login,
    row: i32,
    col: i32,
    previous: Option<&Position>,
    flags: &FlagValues,
) -> io::Result<()> {
    execute!(
        out,
        MoveTo(0, 0),
        terminal::Clear(ClearType::All),
        Print(BG)
    )?;
    let previous_text = previous
        .map(|position| format_pos(position.row, position.col))
        .unwrap_or_else(|| "—".to_string());
    let lines = [
        APP_BANNER.to_string(),
        format!("Name: {}", login.username),
        format!("Team: {}", colored_team(flags)),
        format!("Current position: {}", format_pos(row, col)),
        format!("Previous position: {previous_text}"),
        String::new(),
        "Use arrow keys or WASD to move (L to logout, Q to quit).".to_string(),
        String::new(),
    ];
    let mut y = 0;
    for line in lines {
        print_line(out, y, &line)?;
        y += 1;
    }
    for r in 0..3 {
        for line in 0..3 {
            let row_text = (0..3)
                .map(|c| cell_line(r == row && c == col, line))
                .collect::<Vec<_>>()
                .join(" ");
            print_line(out, y, &row_text)?;
            y += 1;
        }
    }
    out.flush()
}

/// Re-evaluate the team style every 500 ms while navigating.
fn run_grid(out: &mut impl Write, app: &App, login: &Login) -> io::Result<SessionAction> {
    let (mut row, mut col) = (1, 1);
    let mut previous = None;
    loop {
        let flags = app.evaluate_flags(&login.username, &login.team);
        render(out, login, row, col, previous.as_ref(), &flags)?;
        if !event::poll(Duration::from_millis(500))? {
            continue;
        }
        if let Event::Key(KeyEvent {
            code, modifiers, ..
        }) = event::read()?
        {
            if modifiers.contains(KeyModifiers::CONTROL) {
                return Ok(SessionAction::Quit);
            }
            let movement = match code {
                KeyCode::Char('q' | 'Q') => return Ok(SessionAction::Quit),
                KeyCode::Char('l' | 'L') => return Ok(SessionAction::Logout),
                KeyCode::Up | KeyCode::Char('w' | 'W') => Some((-1, 0)),
                KeyCode::Down | KeyCode::Char('s' | 'S') => Some((1, 0)),
                KeyCode::Left | KeyCode::Char('a' | 'A') => Some((0, -1)),
                KeyCode::Right | KeyCode::Char('d' | 'D') => Some((0, 1)),
                _ => None,
            };
            if let Some((dr, dc)) = movement {
                let next_row = (row + dr).clamp(0, 2);
                let next_col = (col + dc).clamp(0, 2);
                if next_row != row || next_col != col {
                    previous = Some(Position { row, col });
                    row = next_row;
                    col = next_col;
                }
            }
        }
    }
}

fn main() -> io::Result<()> {
    let app = App::new();
    let mut stdout = io::stdout();
    loop {
        let login = read_login()?;
        terminal::enable_raw_mode()?;
        execute!(stdout, Hide)?;
        let action = run_grid(&mut stdout, &app, &login);
        execute!(stdout, Show, Print(RESET))?;
        terminal::disable_raw_mode()?;
        if action? == SessionAction::Quit {
            break;
        }
    }
    Ok(())
}
