/**
 * agentCore.js — domain logic for 01-reference-agent (no HTTP here).
 *
 * generateStream(persona, tickerResults) yields event objects:
 *   meta | token | error | metrics | done
 */

"use strict";

const fs = require("fs");
const path = require("path");
const { formatStoriesForPrompt } = require("./yahooNews");

const EXAMPLE_ROOT = path.resolve(__dirname, "..");
const SYSTEM_PROMPT_PATH = path.join(EXAMPLE_ROOT, "prompts", "system_prompt.txt");

const CANNED_INPUT =
  "No ticker stories loaded yet. Ask the user to click Get Stories, " +
  "then produce a brief placeholder note that you are waiting for headlines.";

const DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-lite-v1:0";
const DEFAULT_AWS_REGION = "us-east-1";
const DEFAULT_AWS_PROFILE = "Administrator";

const PERSONAS = [
  { id: "conservative-charlie", name: "Conservative Charlie", profile: "conservative" },
  { id: "neutral-nancy", name: "Neutral Nancy", profile: "neutral" },
  { id: "thoughtless-toby", name: "Thoughtless Toby", profile: "risk-taker" },
];

function loadSystemPrompt() {
  let text;
  try {
    text = fs.readFileSync(SYSTEM_PROMPT_PATH, "utf8").trim();
  } catch (exc) {
    throw new Error(`Could not read system prompt at ${SYSTEM_PROMPT_PATH}: ${exc.message}`);
  }
  if (!text) {
    throw new Error(`System prompt file is empty: ${SYSTEM_PROMPT_PATH}`);
  }
  return text;
}

function resolveMode() {
  const mode = String(process.env.AGENT_LLM_MODE || "stub")
    .trim()
    .toLowerCase();
  if (["stub", "ollama", "bedrock", "anthropic"].includes(mode)) return mode;
  return "stub";
}

function resolveAwsRegion() {
  return (
    String(process.env.AWS_REGION || "").trim() ||
    String(process.env.AWS_DEFAULT_REGION || "").trim() ||
    DEFAULT_AWS_REGION
  );
}

function resolveAwsProfile() {
  return String(process.env.AWS_PROFILE || "").trim() || DEFAULT_AWS_PROFILE;
}

function providerLabel(mode) {
  return (
    {
      stub: "stub",
      ollama: "ollama",
      bedrock: "bedrock",
      anthropic: "anthropic",
    }[mode] || mode
  );
}

function modelLabel(mode) {
  const override = String(process.env.AGENT_LLM_MODEL || "").trim();
  if (override) return override;
  if (mode === "stub") return "default-no-llm";
  if (mode === "ollama") {
    return String(process.env.OLLAMA_MODEL || "llama3.2:3b").trim() || "llama3.2:3b";
  }
  if (mode === "bedrock") {
    return (
      String(process.env.AGENT_BEDROCK_MODEL_ID || "").trim() || DEFAULT_BEDROCK_MODEL_ID
    );
  }
  if (mode === "anthropic") {
    return String(process.env.ANTHROPIC_MODEL || "claude-3-haiku-20240307").trim();
  }
  return "(unknown)";
}

function buildUserInput(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_INPUT;
  return formatStoriesForPrompt(tickerResults);
}

function buildMessages(persona, tickerResults) {
  void persona;
  return [
    { role: "system", content: loadSystemPrompt() },
    { role: "user", content: buildUserInput(tickerResults) },
  ];
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(String(text || "").length / 4));
}

function personaById(personaId) {
  return PERSONAS.find((p) => p.id === personaId) || null;
}

function emptyMetrics() {
  return {
    latency_ms: null,
    ttft_ms: null,
    prompt_tokens: null,
    completion_tokens: null,
    total_tokens: null,
    finish_reason: null,
  };
}

function fillTokenEstimates(completionText, metrics, userInput) {
  metrics.prompt_tokens = estimateTokens(loadSystemPrompt() + userInput);
  metrics.completion_tokens = estimateTokens(completionText);
  metrics.total_tokens = (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function* chunkText(text, size = 12) {
  for (let i = 0; i < text.length; i += size) {
    yield text.slice(i, i + size);
  }
}

function stubResponse(persona, tickerResults) {
  const lines = [
    "[stub / default-no-llm]",
    `Persona: ${persona.name} (${persona.profile})`,
    "",
    "Headline briefing (stub):",
  ];
  if (!tickerResults || !tickerResults.length) {
    lines.push("- (no stories loaded — click Get Stories)");
  } else {
    for (const block of tickerResults) {
      const ticker = block.ticker || "?";
      lines.push(`- ${ticker}:`);
      const stories = block.stories || [];
      if (!stories.length) lines.push("  (no stories)");
      for (const story of stories) {
        lines.push(`  • ${story.title || "(untitled)"}`);
      }
    }
  }
  lines.push("");
  lines.push(
    `As a ${persona.profile} analyst, this is boilerplate report text for UI testing. ` +
      "Switch AGENT_LLM_MODE to ollama or bedrock for a real model response."
  );
  return lines.join("\n");
}

async function* generateStub(persona, started, metrics, userInput, tickerResults) {
  const text = stubResponse(persona, tickerResults);
  let first = true;
  for (const chunk of chunkText(text, 12)) {
    if (first) {
      metrics.ttft_ms = Math.round(performance.now() - started);
      first = false;
    }
    yield { type: "token", text: chunk };
    await sleep(20);
  }
  metrics.finish_reason = "stop";
  fillTokenEstimates(text, metrics, userInput);
}

async function* ollamaStream(persona, model, tickerResults) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(
    /\/$/,
    ""
  );
  const url = `${host}/api/chat`;
  let res;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        stream: true,
        messages: buildMessages(persona, tickerResults),
      }),
      signal: AbortSignal.timeout(120000),
    });
  } catch (exc) {
    throw new Error(
      `Ollama request failed (${host}): ${exc.message || exc}. ` +
        "Is Ollama running, and is OLLAMA_MODEL pulled?"
    );
  }
  if (!res.ok || !res.body) {
    throw new Error(
      `Ollama request failed (${host}): HTTP ${res.status}. ` +
        "Is Ollama running, and is OLLAMA_MODEL pulled?"
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      const data = JSON.parse(line);
      if (data.error) throw new Error(String(data.error));
      const content = (data.message && data.message.content) || "";
      if (content) yield content;
      if (data.done) return;
    }
  }
}

async function* generateOllama(
  persona,
  model,
  started,
  metrics,
  tickerResults,
  userInput
) {
  const textParts = [];
  let first = true;
  for await (const chunk of ollamaStream(persona, model, tickerResults)) {
    if (first) {
      metrics.ttft_ms = Math.round(performance.now() - started);
      first = false;
    }
    textParts.push(chunk);
    yield { type: "token", text: chunk };
  }
  metrics.finish_reason = "stop";
  fillTokenEstimates(textParts.join(""), metrics, userInput);
}

async function* generateStream(persona, tickerResults = null) {
  const mode = resolveMode();
  const provider = providerLabel(mode);
  const model = modelLabel(mode);
  const userInput = buildUserInput(tickerResults);

  yield {
    type: "meta",
    persona: { ...persona },
    input: userInput,
    provider,
    model,
    mode,
    stories: tickerResults || [],
  };

  const started = performance.now();
  const metrics = emptyMetrics();

  try {
    if (mode === "stub") {
      yield* generateStub(persona, started, metrics, userInput, tickerResults);
    } else if (mode === "ollama") {
      yield* generateOllama(
        persona,
        model,
        started,
        metrics,
        tickerResults,
        userInput
      );
    } else if (mode === "bedrock") {
      yield {
        type: "error",
        message:
          "Mode 'bedrock' is not wired in the Node example yet. " +
          "Use AGENT_LLM_MODE=stub or ollama here, or run the Python web app for Bedrock.",
      };
      metrics.finish_reason = "error";
    } else {
      yield {
        type: "error",
        message:
          `Mode '${mode}' is configured but not implemented in this reference yet. ` +
          "Use AGENT_LLM_MODE=stub or ollama.",
      };
      metrics.finish_reason = "error";
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
  }

  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield { type: "done" };
}

module.exports = {
  PERSONAS,
  DEFAULT_AWS_REGION,
  DEFAULT_AWS_PROFILE,
  DEFAULT_BEDROCK_MODEL_ID,
  loadSystemPrompt,
  resolveMode,
  resolveAwsRegion,
  resolveAwsProfile,
  providerLabel,
  modelLabel,
  personaById,
  generateStream,
};
