//! Console grid navigator for LaunchDarkly scheduled flag changes.

use chrono::{Local, TimeZone};
use crossterm::{
    cursor::{Hide, MoveTo, Show},
    event::{self, Event, KeyCode, KeyEvent, KeyModifiers},
    execute, queue,
    style::Print,
    terminal::{self, ClearType},
};
use launchdarkly_server_sdk::{Client, ConfigBuilder, ContextBuilder, Reason};
use serde::Deserialize;
use serde_json::{json, Value};
use std::io::{self, Write};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

// LaunchDarkly: scheduled changes use REST for control and SDK evaluation for observation.
// https://launchdarkly.com/docs/home/flags/scheduled-changes
const FLAG_KEY: &str = "enable-grid-selection-highlight-sched";
const APP_BANNER: &str = "17-scheduled-changes[rust]";
const BG: &str = "\x1b[48;5;236m";
const RESET: &str = "\x1b[0m";
const GREEN: &str = "\x1b[92m";
const ROWS: [&str; 3] = ["t", "m", "b"];
const COLS: [&str; 3] = ["l", "m", "r"];
const DELAYS: [i64; 4] = [1, 2, 5, 10];

#[derive(Default)]
struct FlagValues {
    value: String,
    reason: String,
    variation: String,
}
struct Position {
    row: i32,
    col: i32,
}
#[derive(Clone, Default, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ScheduledChange {
    #[serde(rename = "_id")]
    id: Option<String>,
    #[serde(rename = "_creationDate")]
    created_at: Option<i64>,
    execution_date: Option<i64>,
}
#[derive(Deserialize)]
struct ListResponse {
    #[serde(default)]
    items: Vec<ScheduledChange>,
}
struct RestClient {
    token: String,
    project: String,
    environment: String,
    host: String,
    version: String,
}
struct App {
    client: Option<Arc<Client>>,
    rest: RestClient,
}
#[derive(PartialEq)]
enum SessionAction {
    Quit,
    Logout,
}

fn env_or(key: &str, fallback: &str) -> String {
    std::env::var(key)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| fallback.into())
}
fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as i64
}
fn reason_name(reason: &Reason) -> String {
    match reason {
        Reason::Off => "OFF",
        Reason::Fallthrough { .. } => "FALLTHROUGH",
        Reason::TargetMatch => "TARGET_MATCH",
        Reason::RuleMatch { .. } => "RULE_MATCH",
        Reason::PrerequisiteFailed { .. } => "PREREQUISITE_FAILED",
        Reason::Error { .. } => "ERROR",
    }
    .into()
}

impl RestClient {
    fn new() -> Self {
        Self {
            token: env_or("LD_API_ACCESS_TOKEN", ""),
            project: env_or("LD_PROJECT_KEY", ""),
            environment: env_or("LD_ENVIRONMENT_KEY", ""),
            host: env_or("LD_API_HOST", "https://app.launchdarkly.com"),
            version: env_or("LD_API_VERSION", "20240415"),
        }
    }
    fn missing(&self) -> Vec<&'static str> {
        let mut keys = Vec::new();
        if self.token.is_empty() {
            keys.push("LD_API_ACCESS_TOKEN");
        }
        if self.project.is_empty() {
            keys.push("LD_PROJECT_KEY");
        }
        if self.environment.is_empty() {
            keys.push("LD_ENVIRONMENT_KEY");
        }
        keys
    }
    fn base_path(&self) -> String {
        format!(
            "/projects/{}/flags/{}/environments/{}/scheduled-changes",
            self.project, FLAG_KEY, self.environment
        )
    }
    fn request(
        &self,
        method: &str,
        path: &str,
        body: Option<Value>,
        semantic: bool,
    ) -> Result<Value, String> {
        let missing = self.missing();
        if !missing.is_empty() {
            return Err(format!("scheduled changes need {}", missing.join(", ")));
        }
        let url = format!("{}/api/v2{}", self.host.trim_end_matches('/'), path);
        let content_type = if semantic {
            "application/json; domain-model=launchdarkly.semanticpatch"
        } else {
            "application/json"
        };
        let request = ureq::request(method, &url)
            .set("Authorization", &self.token)
            .set("LD-API-Version", &self.version)
            .set("Accept", "application/json")
            .set("Content-Type", content_type);
        let response = match body {
            Some(value) => request.send_json(value),
            None => request.call(),
        }
        .map_err(|error| match error {
            ureq::Error::Status(code, response) => {
                let text = response.into_string().unwrap_or_default();
                let message = serde_json::from_str::<Value>(&text)
                    .ok()
                    .and_then(|v| v["message"].as_str().map(str::to_owned))
                    .unwrap_or(text);
                format!("LaunchDarkly API {code}: {message}")
            }
            other => other.to_string(),
        })?;
        let text = response.into_string().map_err(|e| e.to_string())?;
        if text.is_empty() {
            Ok(json!({}))
        } else {
            serde_json::from_str(&text).map_err(|e| e.to_string())
        }
    }
    fn list(&self) -> Result<Vec<ScheduledChange>, String> {
        let value = self.request("GET", &self.base_path(), None, false)?;
        serde_json::from_value::<ListResponse>(value)
            .map(|r| r.items)
            .map_err(|e| e.to_string())
    }
    fn delete_pending(&self) -> Result<(), String> {
        for item in self.list()? {
            if let Some(id) = item.id {
                self.request(
                    "DELETE",
                    &format!("{}/{}", self.base_path(), id),
                    None,
                    false,
                )?;
            }
        }
        Ok(())
    }
    fn turn_off(&self, comment: &str) -> Result<(), String> {
        self.request(
            "PATCH",
            &format!("/flags/{}/{}", self.project, FLAG_KEY),
            Some(json!({
                "environmentKey": self.environment, "comment": comment,
                "instructions": [{"kind": "turnFlagOff"}]
            })),
            true,
        )
        .map(|_| ())
    }
    fn start(&self, minutes: i64) -> Result<(ScheduledChange, i64), String> {
        self.delete_pending()?;
        self.turn_off("17-scheduled-changes: reset off before starting demo")?;
        let started = now_ms();
        let execution = started + minutes * 60_000;
        let value = self.request("POST", &self.base_path(), Some(json!({
            "executionDate": execution, "instructions": [{"kind": "turnFlagOn"}],
            "comment": format!("17-scheduled-changes: turn highlight on after {minutes} minute(s)")
        })), false)?;
        let mut change =
            serde_json::from_value::<ScheduledChange>(value).map_err(|e| e.to_string())?;
        if change.execution_date.is_none() {
            change.execution_date = Some(execution);
        }
        Ok((change, started))
    }
    fn stop(&self) -> Result<i64, String> {
        self.delete_pending()?;
        self.turn_off("17-scheduled-changes: stop demo and turn highlight off")?;
        Ok(now_ms())
    }
}

impl App {
    fn new() -> Self {
        let client = std::env::var("LD_SDK_KEY")
            .ok()
            .filter(|v| !v.trim().is_empty())
            .and_then(|key| {
                let config = ConfigBuilder::new(&key).build().ok()?;
                let client = Client::build(config).ok()?;
                client.start_with_runtime().ok()?;
                let deadline = Instant::now() + Duration::from_secs(5);
                while !client.initialized() && Instant::now() < deadline {
                    std::thread::sleep(Duration::from_millis(50));
                }
                client.initialized().then(|| Arc::new(client))
            });
        Self {
            client,
            rest: RestClient::new(),
        }
    }
    fn evaluate(&self, username: &str) -> FlagValues {
        let Some(client) = &self.client else {
            return FlagValues {
                value: "none".into(),
                reason: "ERROR".into(),
                variation: "default".into(),
            };
        };
        let context = ContextBuilder::new(username)
            .kind("user")
            .name(username)
            .build()
            .unwrap_or_else(|_| ContextBuilder::new("anonymous").build().unwrap());
        let detail = client.str_variation_detail(&context, FLAG_KEY, "none".into());
        let raw = detail.value.unwrap_or_else(|| "none".into());
        FlagValues {
            value: if raw == "green" { raw } else { "none".into() },
            reason: reason_name(&detail.reason),
            variation: detail
                .variation_index
                .map(|v| v.to_string())
                .unwrap_or_else(|| "default".into()),
        }
    }
}
impl Drop for App {
    fn drop(&mut self) {
        if let Some(client) = self.client.take().and_then(|c| Arc::try_unwrap(c).ok()) {
            client.close();
        }
    }
}

fn colorize(text: &str, value: &str) -> String {
    if value == "green" {
        format!("{GREEN}{text}{RESET}{BG}")
    } else {
        text.into()
    }
}
fn format_pos(row: i32, col: i32) -> String {
    format!("{}/{}", ROWS[row as usize], COLS[col as usize])
}
fn clock(ms: i64) -> String {
    let seconds = ms.max(0) / 1000;
    format!("{}:{:02}", seconds / 60, seconds % 60)
}
fn wall(ms: i64) -> String {
    if ms == 0 {
        return "—".into();
    }
    Local
        .timestamp_millis_opt(ms)
        .single()
        .map(|value| value.format("%H:%M:%S").to_string())
        .unwrap_or_else(|| "—".into())
}
fn line(out: &mut impl Write, y: &mut u16, text: &str) -> io::Result<()> {
    queue!(out, MoveTo(0, *y), Print(text))?;
    *y += 1;
    Ok(())
}
#[allow(clippy::too_many_arguments)]
fn render(
    out: &mut impl Write,
    username: &str,
    row: i32,
    col: i32,
    previous: Option<&Position>,
    flags: &FlagValues,
    delay: i64,
    started: i64,
    stopped: i64,
    observed: i64,
    execution: i64,
    pending: bool,
    rest: &RestClient,
    error: &str,
) -> io::Result<()> {
    execute!(out, MoveTo(0, 0), terminal::Clear(ClearType::All))?;
    queue!(out, Print(BG))?;
    let prev = previous
        .map(|p| format_pos(p.row, p.col))
        .unwrap_or_else(|| "—".into());
    let end = if stopped != 0 { stopped } else { now_ms() };
    let elapsed = if started != 0 {
        clock(end - started)
    } else {
        "0:00".into()
    };
    let (status, timing): (String, String) = if pending {
        (
            "PENDING · LaunchDarkly will turn the flag on".into(),
            format!("Scheduled wall time: {}", wall(execution)),
        )
    } else if stopped != 0 {
        (
            "STOPPED · pending change cancelled, flag off".into(),
            if started != 0 {
                format!(
                    "Stopped at {} after {} elapsed.",
                    wall(stopped),
                    clock(stopped - started)
                )
            } else {
                format!("Stopped at {}.", wall(stopped))
            },
        )
    } else if flags.value == "green" && started != 0 {
        (
            "APPLIED · SDK now serves green".into(),
            format!(
                "Scheduled for {}{}",
                wall(execution),
                if observed != 0 {
                    format!(
                        "; green first observed here at {}",
                        clock(observed - started)
                    )
                } else {
                    String::new()
                }
            ),
        )
    } else {
        (
            "No pending change.".into(),
            "G starts a schedule. T stops it and turns the flag off.".into(),
        )
    };
    let mut y = 0;
    line(out, &mut y, APP_BANNER)?;
    line(
        out,
        &mut y,
        &format!("Name: {}", colorize(username, &flags.value)),
    )?;
    line(
        out,
        &mut y,
        &format!("Current: {}   Previous: {prev}", format_pos(row, col)),
    )?;
    line(
        out,
        &mut y,
        &format!(
            "Flag value: {}   reason: {}   idx: {}",
            flags.value, flags.reason, flags.variation
        ),
    )?;
    line(
        out,
        &mut y,
        &format!("Delay: {delay} min   Elapsed: {elapsed}"),
    )?;
    line(out, &mut y, &status)?;
    line(out, &mut y, &timing)?;
    let missing = rest.missing();
    let rest_text = if missing.is_empty() {
        "REST configured".to_string()
    } else {
        format!("REST disabled — set {}", missing.join(", "))
    };
    line(out, &mut y, &rest_text)?;
    line(
        out,
        &mut y,
        "G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit",
    )?;
    line(
        out,
        &mut y,
        "Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms.",
    )?;
    if !error.is_empty() {
        line(out, &mut y, error)?;
    }
    y += 1;
    for r in 0..3 {
        for part in 0..3 {
            let cells = (0..3)
                .map(|c| {
                    if r == row && c == col {
                        colorize(["┏━━━┓", "┃ X ┃", "┗━━━┛"][part], &flags.value)
                    } else {
                        ["┌───┐", "│   │", "└───┘"][part].into()
                    }
                })
                .collect::<Vec<String>>()
                .join(" ");
            line(out, &mut y, &cells)?;
        }
    }
    out.flush()
}

fn read_username() -> io::Result<String> {
    println!("{APP_BANNER}\nLogin\nUsername becomes the LaunchDarkly user context key.\n");
    loop {
        print!("Username: ");
        io::stdout().flush()?;
        let mut value = String::new();
        io::stdin().read_line(&mut value)?;
        if !value.trim().is_empty() {
            return Ok(value.trim().into());
        }
        println!("Username is required.");
    }
}
fn apply_move(row: &mut i32, col: &mut i32, previous: &mut Option<Position>, dr: i32, dc: i32) {
    let nr = (*row + dr).clamp(0, 2);
    let nc = (*col + dc).clamp(0, 2);
    if nr != *row || nc != *col {
        *previous = Some(Position {
            row: *row,
            col: *col,
        });
        *row = nr;
        *col = nc;
    }
}
fn run_grid(out: &mut impl Write, app: &App, username: &str) -> io::Result<SessionAction> {
    let (mut row, mut col, mut delay_index) = (1, 1, 0usize);
    let mut previous = None;
    let (mut started, mut stopped, mut observed, mut execution) = (0, 0, 0, 0);
    let mut pending = false;
    let mut error = String::new();
    loop {
        let flags = app.evaluate(username);
        if started != 0 && stopped == 0 && observed == 0 && flags.value == "green" {
            observed = now_ms();
        }
        if app.rest.missing().is_empty() {
            if let Ok(items) = app.rest.list() {
                pending = !items.is_empty();
                if let Some(item) = items.first() {
                    execution = item.execution_date.unwrap_or(execution);
                    if started == 0 {
                        started = item.created_at.unwrap_or(0);
                    }
                }
            }
        }
        render(
            out,
            username,
            row,
            col,
            previous.as_ref(),
            &flags,
            DELAYS[delay_index],
            started,
            stopped,
            observed,
            execution,
            pending,
            &app.rest,
            &error,
        )?;
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
                KeyCode::Char('m' | 'M') => delay_index = (delay_index + 1) % 4,
                KeyCode::Char('1') => delay_index = 0,
                KeyCode::Char('2') => delay_index = 1,
                KeyCode::Char('5') => delay_index = 2,
                KeyCode::Char('0') => delay_index = 3,
                KeyCode::Char('g' | 'G') => match app.rest.start(DELAYS[delay_index]) {
                    Ok((change, at)) => {
                        started = at;
                        stopped = 0;
                        observed = 0;
                        execution = change.execution_date.unwrap_or(0);
                        pending = true;
                        error.clear()
                    }
                    Err(e) => error = e,
                },
                KeyCode::Char('t' | 'T') => match app.rest.stop() {
                    Ok(at) => {
                        stopped = at;
                        pending = false;
                        error.clear()
                    }
                    Err(e) => error = e,
                },
                KeyCode::Up | KeyCode::Char('w' | 'W') => {
                    apply_move(&mut row, &mut col, &mut previous, -1, 0)
                }
                KeyCode::Down | KeyCode::Char('s' | 'S') => {
                    apply_move(&mut row, &mut col, &mut previous, 1, 0)
                }
                KeyCode::Left | KeyCode::Char('a' | 'A') => {
                    apply_move(&mut row, &mut col, &mut previous, 0, -1)
                }
                KeyCode::Right | KeyCode::Char('d' | 'D') => {
                    apply_move(&mut row, &mut col, &mut previous, 0, 1)
                }
                _ => {}
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
        let action = run_grid(&mut stdout, &app, &username);
        execute!(stdout, Show)?;
        terminal::disable_raw_mode()?;
        print!("{RESET}");
        if action? == SessionAction::Quit {
            break;
        }
    }
    Ok(())
}
