//! Console grid navigator: username login and 3×3 keyboard navigation.

use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use std::io::{self, Write};

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

fn cell_line(selected: bool, line: usize) -> String {
    match (selected, line) {
        (true, 0) => "┏━━━┓".to_string(),
        (true, 1) => "┃ X ┃".to_string(),
        (true, _) => "┗━━━┛".to_string(),
        (false, 0) => "┌───┐".to_string(),
        (false, 1) => "│   │".to_string(),
        (_, _) => "└───┘".to_string(),
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
) -> io::Result<()> {
    execute!(out, MoveTo(0, 0), terminal::Clear(ClearType::All))?;

    let prev_text = previous
        .map(|p| format_pos(p.row, p.col))
        .unwrap_or_else(|| "—".to_string());

    let mut y = 0u16;
    print_line(out, y, &format!("Name: {username}"))?;
    y += 1;
    print_line(out, y, &format!("Current position: {}", format_pos(row, col)))?;
    y += 1;
    print_line(out, y, &format!("Previous position: {prev_text}"))?;
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

fn run_grid(out: &mut impl Write, username: &str) -> io::Result<SessionAction> {
    let mut row = 1;
    let mut col = 1;
    let mut previous: Option<Position> = None;

    render(out, username, row, col, previous.as_ref())?;

    loop {
        if !event::poll(std::time::Duration::from_millis(100))? {
            continue;
        }
        if let Event::Key(KeyEvent { code, modifiers, .. }) = event::read()? {
            if modifiers.contains(KeyModifiers::CONTROL) {
                return Ok(SessionAction::Quit);
            }
            let session_action = match code {
                KeyCode::Char('q') | KeyCode::Char('Q') => return Ok(SessionAction::Quit),
                KeyCode::Char('l') | KeyCode::Char('L') => return Ok(SessionAction::Logout),
                KeyCode::Up | KeyCode::Char('w') | KeyCode::Char('W') => Some((-1, 0)),
                KeyCode::Down | KeyCode::Char('s') | KeyCode::Char('S') => Some((1, 0)),
                KeyCode::Left | KeyCode::Char('a') | KeyCode::Char('A') => Some((0, -1)),
                KeyCode::Right | KeyCode::Char('d') | KeyCode::Char('D') => Some((0, 1)),
                _ => None,
            };
            let Some((dr, dc)) = session_action else {
                continue;
            };
            let result = try_move(row, col, dr, dc);
            if result.moved {
                previous = Some(Position { row, col });
                row = result.row;
                col = result.col;
            }
            render(out, username, row, col, previous.as_ref())?;
        }
    }
}

fn main() -> io::Result<()> {
    let mut stdout = io::stdout();

    loop {
        let username = read_username()?;
        terminal::enable_raw_mode()?;
        execute!(stdout, Hide)?;

        let action = run_grid(&mut stdout, &username)?;

        execute!(stdout, Show)?;
        terminal::disable_raw_mode()?;

        if action == SessionAction::Quit {
            break;
        }
    }

    Ok(())
}
