use crate::yahoo::{example_root, format_stories_for_prompt, TickerBlock};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

const CANNED_INPUT: &str = "No ticker stories loaded yet. Ask the user to click Get Stories, \
    then produce a brief placeholder note that you are waiting for headlines.";
const DEFAULT_BEDROCK_MODEL_ID: &str = "us.amazon.nova-lite-v1:0";

#[derive(Clone, Copy, Debug)]
pub struct Persona {
    #[allow(dead_code)]
    pub id: &'static str,
    pub name: &'static str,
    pub profile: &'static str,
}

pub const PERSONAS: [Persona; 3] = [
    Persona {
        id: "conservative-charlie",
        name: "Conservative Charlie",
        profile: "conservative",
    },
    Persona {
        id: "neutral-nancy",
        name: "Neutral Nancy",
        profile: "neutral",
    },
    Persona {
        id: "thoughtless-toby",
        name: "Thoughtless Toby",
        profile: "risk-taker",
    },
];

#[derive(Clone, Debug, Default)]
pub struct Metrics {
    pub latency_ms: Option<u64>,
    pub ttft_ms: Option<u64>,
    pub prompt_tokens: Option<usize>,
    pub completion_tokens: Option<usize>,
    pub total_tokens: Option<usize>,
    pub finish_reason: Option<String>,
}

#[derive(Clone, Debug)]
pub enum StreamEvent {
    Meta {
        provider: String,
        model: String,
        #[allow(dead_code)]
        mode: String,
        input: String,
    },
    Token {
        text: String,
    },
    Error {
        message: String,
    },
    Metrics {
        metrics: Metrics,
    },
    Done,
}

static MODE_OVERRIDE: Mutex<Option<String>> = Mutex::new(None);

pub fn set_mode_override(mode: &str) {
    let cleaned = mode.trim().to_lowercase();
    let next = match cleaned.as_str() {
        "" => None,
        "stub" | "ollama" | "bedrock" | "anthropic" => Some(cleaned),
        _ => Some("stub".into()),
    };
    *MODE_OVERRIDE.lock().unwrap() = next;
}

pub fn resolve_mode() -> String {
    if let Some(m) = MODE_OVERRIDE.lock().unwrap().clone() {
        return m;
    }
    let mode = std::env::var("AGENT_LLM_MODE")
        .unwrap_or_default()
        .trim()
        .to_lowercase();
    match mode.as_str() {
        "stub" | "ollama" | "bedrock" | "anthropic" => mode,
        "" => "stub".into(),
        _ => "stub".into(),
    }
}

pub fn model_label(mode: &str) -> String {
    if let Ok(override_model) = std::env::var("AGENT_LLM_MODEL") {
        let t = override_model.trim();
        if !t.is_empty() {
            return t.to_string();
        }
    }
    match mode {
        "stub" => "default-no-llm".into(),
        "ollama" => std::env::var("OLLAMA_MODEL")
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "llama3.2:3b".into()),
        "bedrock" => std::env::var("AGENT_BEDROCK_MODEL_ID")
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| DEFAULT_BEDROCK_MODEL_ID.into()),
        "anthropic" => std::env::var("ANTHROPIC_MODEL")
            .ok()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "claude-3-haiku-20240307".into()),
        _ => "(unknown)".into(),
    }
}

pub fn ollama_host() -> String {
    let host = std::env::var("OLLAMA_HOST").unwrap_or_else(|_| "http://127.0.0.1:11434".into());
    host.trim_end_matches('/').to_string()
}

pub fn load_system_prompt() -> Result<String, String> {
    let path = example_root().join("prompts").join("system_prompt.txt");
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("could not read system prompt at {}: {e}", path.display()))?;
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err(format!("system prompt file is empty: {}", path.display()));
    }
    Ok(text)
}

fn build_user_input(ticker_results: &[TickerBlock]) -> String {
    if ticker_results.is_empty() {
        CANNED_INPUT.to_string()
    } else {
        format_stories_for_prompt(ticker_results)
    }
}

fn estimate_tokens(text: &str) -> usize {
    (text.len() / 4).max(1)
}

fn fill_token_estimates(completion: &str, metrics: &mut Metrics, user_input: &str) {
    let sys = load_system_prompt().unwrap_or_default();
    let pt = estimate_tokens(&(sys + user_input));
    let ct = estimate_tokens(completion);
    metrics.prompt_tokens = Some(pt);
    metrics.completion_tokens = Some(ct);
    metrics.total_tokens = Some(pt + ct);
}

fn stub_response(persona: &Persona, ticker_results: &[TickerBlock]) -> String {
    let mut lines = vec![
        "[stub / default-no-llm]".to_string(),
        format!("Persona: {} ({})", persona.name, persona.profile),
        String::new(),
        "Headline briefing (stub):".into(),
    ];
    if ticker_results.is_empty() {
        lines.push("- (no stories loaded — click Get Stories)".into());
    } else {
        for block in ticker_results {
            let ticker = if block.ticker.is_empty() {
                "?"
            } else {
                &block.ticker
            };
            lines.push(format!("- {ticker}:"));
            if block.stories.is_empty() {
                lines.push("  (no stories)".into());
            }
            for story in &block.stories {
                let title = if story.title.is_empty() {
                    "(untitled)"
                } else {
                    &story.title
                };
                lines.push(format!("  • {title}"));
            }
        }
    }
    lines.push(String::new());
    lines.push(format!(
        "As a {} analyst, this is boilerplate report text for UI testing. \
         Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.",
        persona.profile
    ));
    lines.join("\n")
}

pub fn probe_ollama(timeout: Duration) -> bool {
    let url = format!("{}/api/tags", ollama_host());
    ureq::get(&url)
        .timeout(timeout)
        .call()
        .map(|r| r.status() < 300)
        .unwrap_or(false)
}

pub fn ensure_llm_mode() -> String {
    if std::env::var("AGENT_LLM_MODE")
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false)
    {
        return resolve_mode();
    }
    if probe_ollama(Duration::from_millis(600)) {
        std::env::set_var("AGENT_LLM_MODE", "ollama");
    } else {
        std::env::set_var("AGENT_LLM_MODE", "stub");
    }
    resolve_mode()
}

fn chunk_text(text: &str, size: usize) -> Vec<String> {
    let size = size.max(1);
    text.chars()
        .collect::<Vec<_>>()
        .chunks(size)
        .map(|c| c.iter().collect())
        .collect()
}

fn ollama_stream(
    model: &str,
    ticker_results: &[TickerBlock],
    on_chunk: &mut dyn FnMut(String),
) -> Result<(), String> {
    let sys = load_system_prompt()?;
    let body = json!({
        "model": model,
        "stream": true,
        "messages": [
            {"role": "system", "content": sys},
            {"role": "user", "content": build_user_input(ticker_results)},
        ]
    });
    let host = ollama_host();
    let url = format!("{host}/api/chat");
    let resp = ureq::post(&url)
        .timeout(Duration::from_secs(120))
        .set("Content-Type", "application/json")
        .send_json(body)
        .map_err(|e| {
            format!(
                "Ollama request failed ({host}): {e}. Is Ollama running, and is OLLAMA_MODEL pulled?"
            )
        })?;
    if !(200..300).contains(&resp.status()) {
        return Err(format!(
            "Ollama request failed ({host}): HTTP {}. Is Ollama running, and is OLLAMA_MODEL pulled?",
            resp.status()
        ));
    }
    let reader = BufReader::new(resp.into_reader());
    for line in reader.lines() {
        let line = line.map_err(|e| e.to_string())?;
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let data: Value = serde_json::from_str(line).map_err(|e| e.to_string())?;
        if let Some(err) = data.get("error") {
            if !err.is_null() {
                return Err(err.to_string());
            }
        }
        if let Some(content) = data
            .pointer("/message/content")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
        {
            on_chunk(content.to_string());
        }
        if data.get("done").and_then(|v| v.as_bool()).unwrap_or(false) {
            break;
        }
    }
    Ok(())
}

/// Stream generation events to `on_event` (meta / token / error / metrics / done).
pub fn generate_stream(
    persona: &Persona,
    ticker_results: &[TickerBlock],
    on_event: &mut dyn FnMut(StreamEvent),
) {
    let mode = resolve_mode();
    let model = model_label(&mode);
    let user_input = build_user_input(ticker_results);
    on_event(StreamEvent::Meta {
        provider: mode.clone(),
        model: model.clone(),
        mode: mode.clone(),
        input: user_input.clone(),
    });

    let started = Instant::now();
    let mut metrics = Metrics::default();

    match mode.as_str() {
        "stub" => {
            let text = stub_response(persona, ticker_results);
            let mut first = true;
            for chunk in chunk_text(&text, 12) {
                if first {
                    metrics.ttft_ms = Some(started.elapsed().as_millis() as u64);
                    first = false;
                }
                on_event(StreamEvent::Token { text: chunk });
                thread::sleep(Duration::from_millis(20));
            }
            metrics.finish_reason = Some("stop".into());
            fill_token_estimates(&text, &mut metrics, &user_input);
        }
        "ollama" => {
            let mut parts = Vec::new();
            let mut first = true;
            let result = {
                let mut on_chunk = |chunk: String| {
                    if first {
                        metrics.ttft_ms = Some(started.elapsed().as_millis() as u64);
                        first = false;
                    }
                    parts.push(chunk.clone());
                    on_event(StreamEvent::Token { text: chunk });
                };
                ollama_stream(&model, ticker_results, &mut on_chunk)
            };
            match result {
                Ok(()) => {
                    metrics.finish_reason = Some("stop".into());
                    fill_token_estimates(&parts.join(""), &mut metrics, &user_input);
                }
                Err(err) => {
                    on_event(StreamEvent::Error { message: err });
                    metrics.finish_reason = Some("error".into());
                }
            }
        }
        "bedrock" => {
            on_event(StreamEvent::Error {
                message: "Mode 'bedrock' is not wired in the Rust example yet. \
                    Use AGENT_LLM_MODE=stub or ollama here, or run the Python web app for Bedrock."
                    .into(),
            });
            metrics.finish_reason = Some("error".into());
        }
        other => {
            on_event(StreamEvent::Error {
                message: format!(
                    "Mode '{other}' is configured but not implemented in this reference yet. \
                     Use AGENT_LLM_MODE=stub or ollama."
                ),
            });
            metrics.finish_reason = Some("error".into());
        }
    }

    metrics.latency_ms = Some(started.elapsed().as_millis() as u64);
    on_event(StreamEvent::Metrics { metrics });
    on_event(StreamEvent::Done);
}
