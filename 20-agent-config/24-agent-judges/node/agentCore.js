/**
 * agentCore.js — 24-agent-judges domain logic (no HTTP here).
 *
 * Same equity-briefing product as 21, plus a **runtime judge gate**:
 *   draft → judgeConfig (×2) + Ollama JSON → optional one Charlie rewrite
 *
 * LaunchDarkly insertion:
 *   generateStream() → completionConfig(...) then judgeConfig(...) per judge
 *   Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
 *   Keywords: Judges · custom judges · judgeConfig · runtime gate
 *
 * Node note: createJudge needs @launchdarkly/server-sdk-ai-openai, which still
 * peers AI SDK ^1.x. This example stays on AI SDK 2.x (same as 21/23) and runs
 * judges via judgeConfig + Ollama format=json — same teaching gate as Python.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { initAi } = require("@launchdarkly/server-sdk-ai");
const { formatStoriesForPrompt } = require("./yahooNews");

const HERE = __dirname;
const EXAMPLE_ROOT = path.resolve(HERE, "..");
const MESSAGES_DIR = path.join(EXAMPLE_ROOT, "rest", "messages");

const CANNED_STORIES =
  "No ticker stories loaded yet. Ask the user to click Get Stories.";

const DEFAULT_CONFIG_KEY = "equity-briefing-judged";
const DEFAULT_JUDGE_FIDELITY_KEY = "equity-briefing-source-fidelity";
const DEFAULT_JUDGE_DISCIPLINE_KEY = "equity-briefing-recommendation-discipline";
const DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
const DEFAULT_PASS_THRESHOLD = 0.65;
const JUDGE_JSON_SUFFIX =
  'Respond with JSON {"score":0.0-1.0,"reasoning":"..."}.';

const PERSONAS = [
  { id: "thoughtless-toby", name: "Thoughtless Toby", profile: "risk-taker" },
  { id: "conservative-charlie", name: "Conservative Charlie", profile: "conservative" },
];

const CHARLIE = PERSONAS[1];

let ldClient = null;
let aiClient = null;

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

function personaById(personaId) {
  return PERSONAS.find((p) => p.id === personaId) || null;
}

function configKey() {
  return String(process.env.LD_AGENT_CONFIG_KEY || DEFAULT_CONFIG_KEY).trim() || DEFAULT_CONFIG_KEY;
}

function judgeFidelityKey() {
  return (
    String(process.env.LD_JUDGE_FIDELITY_KEY || DEFAULT_JUDGE_FIDELITY_KEY).trim() ||
    DEFAULT_JUDGE_FIDELITY_KEY
  );
}

function judgeDisciplineKey() {
  return (
    String(process.env.LD_JUDGE_DISCIPLINE_KEY || DEFAULT_JUDGE_DISCIPLINE_KEY).trim() ||
    DEFAULT_JUDGE_DISCIPLINE_KEY
  );
}

function passThreshold() {
  const raw = String(process.env.JUDGE_PASS_THRESHOLD || "").trim();
  if (!raw) return DEFAULT_PASS_THRESHOLD;
  const n = Number(raw);
  return Number.isFinite(n) ? n : DEFAULT_PASS_THRESHOLD;
}

function formatStories(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_STORIES;
  return formatStoriesForPrompt(tickerResults);
}

function defaultOllamaModel() {
  return String(process.env.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim() || DEFAULT_OLLAMA_MODEL;
}

function readMessageFile(name) {
  const filePath = path.join(MESSAGES_DIR, name);
  return fs.readFileSync(filePath, "utf8");
}

async function initLaunchDarkly() {
  if (aiClient) return;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error(
      "LD_SDK_KEY is required. Export a server-side SDK key for the environment that targets equity-briefing-judged."
    );
  }
  ldClient = LaunchDarkly.init(sdkKey);
  await ldClient.waitForInitialization({ timeout: 5 });
  aiClient = initAi(ldClient);
}

function buildContext(persona) {
  return { kind: "user", key: persona.id, name: persona.name };
}

function skepticCompletionDefault() {
  return {
    enabled: true,
    model: { name: defaultOllamaModel() },
    provider: { name: "Custom" },
    messages: [
      { role: "system", content: readMessageFile("skeptic-system.txt").trim() },
      { role: "user", content: readMessageFile("skeptic-user.txt").trim() },
    ],
  };
}

function judgeDefault(systemFile, metricKey) {
  return {
    enabled: true,
    model: { name: defaultOllamaModel() },
    provider: { name: "Custom" },
    evaluationMetricKey: metricKey,
    messages: [{ role: "system", content: readMessageFile(systemFile).trim() }],
  };
}

function defaultMetricForJudgeKey(key) {
  if (key.includes("fidelity")) return "$ld:ai:judge:source-fidelity";
  if (key.includes("discipline")) return "$ld:ai:judge:recommendation-discipline";
  const suffix = key.replace("equity-briefing-", "") || "custom";
  return `$ld:ai:judge:${suffix}`;
}

async function evaluateCompletion(persona, storiesText) {
  return aiClient.completionConfig(
    configKey(),
    buildContext(persona),
    skepticCompletionDefault(),
    { stories: storiesText }
  );
}

function messagesAsDicts(config) {
  return (config.messages || []).map((m) => ({
    role: m.role,
    content: m.content || "",
  }));
}

function userMessageText(messages) {
  const hit = messages.find((m) => m.role === "user");
  return hit ? hit.content || "" : "";
}

function resolveRuntime(config) {
  const model = (config.model && config.model.name) || "";
  const providerName = ((config.provider && config.provider.name) || "").toLowerCase();
  if (providerName === "custom" || providerName === "ollama" || model.includes(":")) {
    return { provider: "ollama", model };
  }
  if (!model) throw new Error("AgentControl variation has no model name.");
  return { provider: "ollama", model };
}

function judgeInputText(storiesText, tickers) {
  const tickerLine = tickers && tickers.length ? `Tickers: ${tickers.join(", ")}\n\n` : "";
  return (
    `${tickerLine}` +
    "Task: Write a short equity briefing comparing the tickers using only the headlines below.\n\n" +
    `HEADLINES:\n${storiesText}`
  );
}

function extractTickers(tickerResults) {
  if (!tickerResults) return [];
  return tickerResults.map((r) => String(r.ticker || "").trim()).filter(Boolean);
}

async function ollamaJudgeJson(model, messages) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  const res = await fetch(`${host}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      stream: false,
      format: "json",
      options: { temperature: 0 },
      messages,
    }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ollama judge failed (${host}, model=${model}): HTTP ${res.status} ${body}`);
  }
  const data = await res.json();
  if (data.error) throw new Error(String(data.error));
  const content = ((data.message && data.message.content) || "").trim();
  if (!content) throw new Error("Ollama judge returned empty content");
  return JSON.parse(content);
}

async function runOneJudge(key, persona, inputText, outputText) {
  // LaunchDarkly: judgeConfig — prompts/model from LD; gate runs locally via Ollama JSON
  // https://launchdarkly.com/docs/home/agentcontrol/judges
  const metricDefault = defaultMetricForJudgeKey(key);
  const systemFile = key.includes("fidelity")
    ? "judge-source-fidelity-system.txt"
    : "judge-recommendation-discipline-system.txt";

  try {
    const config = await aiClient.judgeConfig(
      key,
      buildContext(persona),
      judgeDefault(systemFile, metricDefault)
    );
    const metric = config.evaluationMetricKey || metricDefault;
    if (!config.enabled) {
      return {
        key,
        success: false,
        error: "judge config disabled or unsupported (enabled=false)",
        score: null,
        reasoning: null,
        metricKey: metric,
        sampled: true,
        passed: false,
      };
    }

    let model = (config.model && config.model.name) || defaultOllamaModel();
    try {
      ({ model } = resolveRuntime(config));
    } catch (_) {
      // keep defaultOllamaModel / served name
    }
    if (!model) model = defaultOllamaModel();

    const served = messagesAsDicts(config);
    let system = served
      .filter((m) => m.role === "system")
      .map((m) => m.content || "")
      .join("\n")
      .trim();
    if (!system) system = readMessageFile(systemFile).trim();
    if (!system.includes("Respond with JSON")) {
      system = `${system}\n\n${JUDGE_JSON_SUFFIX}`;
    }

    const user =
      `MESSAGE HISTORY:\n${inputText}\n\nRESPONSE TO EVALUATE:\n${outputText}`;
    const messages = [
      { role: "system", content: system },
      { role: "user", content: user },
    ];

    const parsed = await ollamaJudgeJson(model, messages);
    const score =
      parsed.score != null && Number.isFinite(Number(parsed.score))
        ? Number(parsed.score)
        : null;
    const reasoning = parsed.reasoning != null ? String(parsed.reasoning) : null;
    const passed = score != null && score >= passThreshold();

    const tracker = config.tracker || (config.createTracker && config.createTracker());
    if (tracker && typeof tracker.trackJudgeResult === "function") {
      try {
        tracker.trackJudgeResult({
          judgeConfigKey: key,
          success: true,
          sampled: true,
          metricKey: metric,
          score: score ?? undefined,
          reasoning: reasoning || undefined,
        });
      } catch (_) {}
    }

    return {
      key,
      success: true,
      error: null,
      score,
      reasoning,
      metricKey: metric,
      sampled: true,
      passed,
    };
  } catch (exc) {
    return {
      key,
      success: false,
      error: String(exc.message || exc),
      score: null,
      reasoning: null,
      metricKey: metricDefault,
      sampled: true,
      passed: false,
    };
  }
}

async function runJudges(persona, inputText, draft) {
  return [
    await runOneJudge(judgeFidelityKey(), persona, inputText, draft),
    await runOneJudge(judgeDisciplineKey(), persona, inputText, draft),
  ];
}

function judgesPassed(results) {
  return results.every((r) => Boolean(r.passed));
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(String(text).length / 4));
}

function fillTokenEstimates(messages, completion, metrics) {
  const prompt = messages.map((m) => m.content || "").join("");
  metrics.prompt_tokens = estimateTokens(prompt);
  metrics.completion_tokens = estimateTokens(completion);
  metrics.total_tokens = (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);
}

async function* ollamaStream(model, messages) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  const res = await fetch(`${host}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, stream: true, messages }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ollama request failed (${host}, model=${model}): HTTP ${res.status} ${body}`);
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
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const data = JSON.parse(trimmed);
      if (data.error) throw new Error(String(data.error));
      const content = (data.message && data.message.content) || "";
      if (content) yield content;
      if (data.done) return;
    }
  }
}

async function* generateOllama(model, messages, started, metrics) {
  const parts = [];
  let first = true;
  for await (const chunk of ollamaStream(model, messages)) {
    if (first) {
      metrics.ttft_ms = Math.round(performance.now() - started);
      first = false;
    }
    parts.push(chunk);
    yield { type: "token", text: chunk };
  }
  metrics.finish_reason = "stop";
  fillTokenEstimates(messages, parts.join(""), metrics);
}

/**
 * Draft → decorate → judge → optional one Charlie rewrite.
 * SSE extras vs 21: section, judges, rewrite_meta
 */
async function* generateStream(persona, tickerResults) {
  const storiesText = formatStories(tickerResults);
  const tickers = extractTickers(tickerResults);
  const started = performance.now();
  const metrics = emptyMetrics();
  const threshold = passThreshold();

  let config;
  try {
    config = await evaluateCompletion(persona, storiesText);
  } catch (exc) {
    yield { type: "error", message: `LaunchDarkly completionConfig failed: ${exc.message || exc}` };
    yield { type: "done" };
    return;
  }

  if (!config.enabled) {
    yield {
      type: "error",
      message: `AgentControl config '${configKey()}' is off / enabled=false. Run rest/create-config.sh.`,
    };
    yield { type: "done" };
    return;
  }

  let provider;
  let model;
  let messages;
  let tracker;
  try {
    ({ provider, model } = resolveRuntime(config));
    messages = messagesAsDicts(config);
    if (!messages.length) throw new Error("Served variation has no messages.");
    tracker = config.tracker || (config.createTracker && config.createTracker());
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    yield { type: "done" };
    return;
  }

  yield {
    type: "meta",
    persona: { ...persona },
    input: userMessageText(messages) || storiesText,
    provider,
    model,
    mode: "launchdarkly",
    configKey: configKey(),
    judgeKeys: [judgeFidelityKey(), judgeDisciplineKey()],
    passThreshold: threshold,
    stories: tickerResults || [],
  };

  yield { type: "section", title: `Draft (${persona.name})`, kind: "draft" };

  const draftParts = [];
  try {
    for await (const event of generateOllama(model, messages, started, metrics)) {
      if (event.type === "token") draftParts.push(event.text || "");
      yield event;
    }
    if (tracker) {
      if (typeof tracker.trackSuccess === "function") tracker.trackSuccess();
      metrics.latency_ms = Math.round(performance.now() - started);
      if (typeof tracker.trackDuration === "function") tracker.trackDuration(metrics.latency_ms);
      if (metrics.ttft_ms != null && typeof tracker.trackTimeToFirstToken === "function") {
        tracker.trackTimeToFirstToken(metrics.ttft_ms);
      }
      if (
        (metrics.total_tokens || metrics.prompt_tokens || metrics.completion_tokens) &&
        typeof tracker.trackTokens === "function"
      ) {
        tracker.trackTokens({
          total: metrics.total_tokens || 0,
          input: metrics.prompt_tokens || 0,
          output: metrics.completion_tokens || 0,
        });
      }
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    if (tracker && typeof tracker.trackError === "function") {
      try {
        tracker.trackError();
      } catch (_) {}
    }
    metrics.finish_reason = "error";
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  const draft = draftParts.join("").trim();
  yield {
    type: "status",
    message: "Running judges (Source Fidelity + Recommendation Discipline)…",
  };

  let judgeResults;
  try {
    judgeResults = await runJudges(persona, judgeInputText(storiesText, tickers), draft);
  } catch (exc) {
    yield { type: "error", message: `Judge evaluation failed: ${exc.message || exc}` };
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  const passed = judgesPassed(judgeResults);
  yield { type: "section", title: "Judge scores", kind: "judges" };
  yield { type: "judges", passed, threshold, results: judgeResults };

  if (passed) {
    yield { type: "status", message: `Both judges ≥ ${threshold.toFixed(2)} — no rewrite.` };
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  yield { type: "status", message: "Gate failed — rewriting once with Conservative Charlie…" };
  yield { type: "section", title: "Rewrite (Conservative Charlie)", kind: "rewrite" };

  const rewriteMetrics = emptyMetrics();
  const rewriteStarted = performance.now();
  try {
    const charlieConfig = await evaluateCompletion(CHARLIE, storiesText);
    if (!charlieConfig.enabled) throw new Error("Charlie variation enabled=false; check targeting.");
    const resolved = resolveRuntime(charlieConfig);
    const cMessages = messagesAsDicts(charlieConfig);
    const cTracker =
      charlieConfig.tracker || (charlieConfig.createTracker && charlieConfig.createTracker());
    yield {
      type: "rewrite_meta",
      persona: { ...CHARLIE },
      provider: resolved.provider,
      model: resolved.model,
    };
    for await (const event of generateOllama(
      resolved.model,
      cMessages,
      rewriteStarted,
      rewriteMetrics
    )) {
      yield event;
    }
    if (cTracker) {
      if (typeof cTracker.trackSuccess === "function") cTracker.trackSuccess();
      rewriteMetrics.latency_ms = Math.round(performance.now() - rewriteStarted);
      if (typeof cTracker.trackDuration === "function") {
        cTracker.trackDuration(rewriteMetrics.latency_ms);
      }
    }
  } catch (exc) {
    yield { type: "error", message: `Charlie rewrite failed: ${exc.message || exc}` };
  }

  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield {
    type: "status",
    message: "Rewrite complete (one rewrite max; scores above are for the draft).",
  };
  yield { type: "done" };
}

module.exports = {
  PERSONAS,
  configKey,
  judgeFidelityKey,
  judgeDisciplineKey,
  passThreshold,
  personaById,
  initLaunchDarkly,
  generateStream,
};
