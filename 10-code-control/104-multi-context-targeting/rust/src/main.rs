//! Console grid navigator demonstrating LaunchDarkly multi-context targeting.

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{
    AttributeValue, Client, ConfigBuilder, ContextBuilder, MultiContextBuilder,
};
use std::io::{self, Write};
use std::sync::Arc;
use std::time::Duration;

// LaunchDarkly: one variation call with kind multi (user + organization).
// https://launchdarkly.com/docs/home/flags/multi-contexts
const FLAG_PARTNER_BADGE: &str = "show-partner-org-badge";
const APP_BANNER: &str = "14-multi-context-targeting[rust]";
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";
const GREEN: &str = "\x1b[32m";
const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];

struct Login {
    username: String,
    org: String,
}

struct FlagValues {
    org_label: String,
    partner: bool,
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
                    "Warning: LaunchDarkly SDK did not initialize — partner badge stays false."
                );
                None
            }
        });
        if std::env::var("LD_SDK_KEY").is_err() {
            eprintln!("Warning: LD_SDK_KEY not set — partner badge stays false.");
        }
        Self { client }
    }

    /// Evaluate show-partner-org-badge. Org is a separate context kind, not a user attribute.
    fn evaluate_flags(&self, username: &str, org: &str) -> FlagValues {
        let org_label = org_label(org);
        let user = ContextBuilder::new(username)
            .kind("user")
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let organization = ContextBuilder::new(org)
            .kind("organization")
            .set_value("name", AttributeValue::String(org_label.to_string().into()))
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").kind("organization").build().unwrap());
        let context = MultiContextBuilder::new()
            .add_context(user)
            .add_context(organization)
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let partner = self
            .client
            .as_ref()
            .map_or(false, |client| client.bool_variation(&context, FLAG_PARTNER_BADGE, false));
        FlagValues {
            org_label: org_label.to_string(),
            partner,
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

fn org_label(org: &str) -> &'static str {
    if org == "globex" {
        "Globex"
    } else {
        "Acme"
    }
}

fn name_line(username: &str, flags: &FlagValues) -> String {
    if flags.partner {
        format!("Name: {username}  {GREEN}partner{RESET}{BG}")
    } else {
        format!("Name: {username}")
    }
}

/// Prompt for Alice/Bob and Acme/Globex — the two multi-context keys.
fn read_login() -> io::Result<Login> {
    println!("{APP_BANNER}");
    println!("Login\n");
    let username = loop {
        print!("User [1=Alice 2=Bob]: ");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        match line.trim() {
            "1" => break "alice".to_string(),
            "2" => break "bob".to_string(),
            _ => println!("Choose 1 or 2."),
        }
    };

    let org = loop {
        print!("Org  [1=Acme 2=Globex]: ");
        io::stdout().flush()?;
        let mut line = String::new();
        io::stdin().read_line(&mut line)?;
        match line.trim() {
            "1" => break "acme",
            "2" => break "globex",
            _ => println!("Choose 1 or 2."),
        }
    };
    Ok(Login {
        username,
        org: org.to_string(),
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
        name_line(&login.username, flags),
        format!("Org: {}", flags.org_label),
        format!("Current position: {}", format_pos(row, col)),
        format!("Previous position: {previous_text}"),
        String::new(),
        "1/2 user Alice/Bob, 3/4 org Acme/Globex. Arrows or WASD. L logout, Q quit.".to_string(),
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

/// Re-evaluate the partner badge every 500 ms; 1–4 walk the 2×2 without logout.
fn run_grid(out: &mut impl Write, app: &App, login: &mut Login) -> io::Result<SessionAction> {
    let (mut row, mut col) = (1, 1);
    let mut previous = None;
    loop {
        let flags = app.evaluate_flags(&login.username, &login.org);
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
            match code {
                KeyCode::Char('q' | 'Q') => return Ok(SessionAction::Quit),
                KeyCode::Char('l' | 'L') => return Ok(SessionAction::Logout),
                KeyCode::Char('1') => login.username = "alice".to_string(),
                KeyCode::Char('2') => login.username = "bob".to_string(),
                KeyCode::Char('3') => login.org = "acme".to_string(),
                KeyCode::Char('4') => login.org = "globex".to_string(),
                _ => {
                    let movement = match code {
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
    }
}

fn main() -> io::Result<()> {
    let app = App::new();
    let mut stdout = io::stdout();
    loop {
        let mut login = read_login()?;
        terminal::enable_raw_mode()?;
        execute!(stdout, Hide)?;
        let action = run_grid(&mut stdout, &app, &mut login);
        execute!(stdout, Show, Print(RESET))?;
        terminal::disable_raw_mode()?;
        if action? == SessionAction::Quit {
            break;
        }
    }
    Ok(())
}
