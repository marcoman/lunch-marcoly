/**
 * agentCore.js — domain logic for 22-config-outside-code (no HTTP here).
 *
 * Teaching focus: AgentControl completion config **outside code**, with
 * **trackMetricsOf** + thumbs feedback as the headline (Monitoring tab).
 *
 * LaunchDarkly: AgentControl · completion config · AI metrics · feedback
 * https://launchdarkly.com/docs/sdk/ai/node-js
 * https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs
 */

"use strict";

const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { initAi, LDFeedbackKind } = require("@launchdarkly/server-sdk-ai");
const { formatStoriesForPrompt } = require("./yahooNews");

const HERE = __dirname;
const EXAMPLE_ROOT = path.resolve(HERE, "..");
const BASELINE_MESSAGES_DIR = path.join(EXAMPLE_ROOT, "rest", "messages");

const CANNED_STORIES =
  "No ticker stories loaded yet. Ask the user to click Get Stories.";

// LaunchDarkly: ai-config key=equity-briefing-tracked-completion name="Equity briefing tracked completion" mode=completion
// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tracked-completion

const DEFAULT_CONFIG_KEY = "equity-briefing-tracked-completion";
const DEFAULT_OLLAMA_MODEL = "llama3.2:1b";
const DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5";

const PERSONAS = [
  { id: "best-betty", name: "Best Betty", profile: "best", anonymous: false },
  {
    id: "anonymous-amelia",
    name: "Anonymous Amelia",
    profile: "anonymous",
    anonymous: true,
  },
];

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
  const key = String(process.env.LD_AGENT_CONFIG_KEY || DEFAULT_CONFIG_KEY).trim();
  return key || DEFAULT_CONFIG_KEY;
}

function formatStories(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_STORIES;
  return formatStoriesForPrompt(tickerResults);
}

function defaultOllamaModel() {
  const model = String(process.env.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim();
  return model || DEFAULT_OLLAMA_MODEL;
}

function readMessageFile(name) {
  const filePath = path.join(BASELINE_MESSAGES_DIR, name);
  return fs.readFileSync(filePath, "utf8").trim();
}

function baselineSystemPrompt() {
  return readMessageFile("baseline-system.txt");
}

function baselineUserTemplate() {
  return readMessageFile("baseline-user.txt");
}

function renderBaselineUser(storiesText) {
  return baselineUserTemplate()
    .replaceAll("{{ stories }}", storiesText)
    .replaceAll("{{stories}}", storiesText);
}

function baselineMessages(storiesText) {
  return [
    { role: "system", content: baselineSystemPrompt() },
    { role: "user", content: renderBaselineUser(storiesText) },
  ];
}

function baselineCompletionDefault() {
  return {
    enabled: true,
    model: { name: defaultOllamaModel() },
    provider: { name: "Custom" },
    messages: [
      { role: "system", content: baselineSystemPrompt() },
      { role: "user", content: baselineUserTemplate() },
    ],
  };
}

async function initLaunchDarkly() {
  if (aiClient) return;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error(
      `LD_SDK_KEY is required. Export a server-side SDK key for the environment that targets ${DEFAULT_CONFIG_KEY}.`
    );
  }
  ldClient = LaunchDarkly.init(sdkKey);
  await ldClient.waitForInitialization({ timeout: 10 });
  aiClient = initAi(ldClient);
}

function getAiClient() {
  if (!aiClient) throw new Error("LaunchDarkly AI client not initialized.");
  return aiClient;
}

function buildContext(persona) {
  const ctx = {
    kind: "user",
    key: persona.id,
    name: persona.name,
  };
  if (persona.anonymous) ctx.anonymous = true;
  return ctx;
}

async function evaluateCompletion(persona, storiesText) {
  return getAiClient().completionConfig(
    configKey(),
    buildContext(persona),
    baselineCompletionDefault(),
    { stories: storiesText }
  );
}

function messagesAsDicts(config) {
  const out = [];
  for (const msg of config.messages || []) {
    const role = msg.role;
    const content = msg.content;
    if (role && content != null) out.push({ role: String(role), content: String(content) });
  }
  return out;
}

function userMessageText(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") return messages[i].content || "";
  }
  return "";
}

function buildLdTransaction({
  persona,
  storiesText,
  configKeyValue,
  fallback,
  mode,
  provider,
  model,
  messages,
  servedMeta,
  enabled,
}) {
  const context = buildContext(persona);
  const reason = (servedMeta || {}).reason;
  return {
    sent: {
      configKey: configKeyValue,
      context,
      variables: { stories: storiesText },
      sdkDefault: {
        description:
          "AICompletionConfigDefault passed to completionConfig " +
          "(baseline-analyst shape; used if config key is missing). " +
          "Generation runs inside trackMetricsOf for Monitoring.",
        enabled: true,
        model: defaultOllamaModel(),
        provider: "Custom",
        messages: [
          { role: "system", content: baselineSystemPrompt() },
          { role: "user", content: baselineUserTemplate() },
        ],
      },
    },
    received: {
      fallback,
      mode,
      enabled,
      configKey: configKeyValue,
      variationKey: (servedMeta || {}).variationKey,
      variationIndex: (servedMeta || {}).variationIndex,
      reason,
      version: (servedMeta || {}).version,
      versionKey: (servedMeta || {}).versionKey,
      ldMode: (servedMeta || {}).mode,
      modelKey: (servedMeta || {}).modelKey,
      modelVersion: (servedMeta || {}).modelVersion,
      provider,
      model,
      messages,
    },
  };
}

function resolveRuntime(config) {
  const model = (config.model && config.model.name) || "";
  const providerName = ((config.provider && config.provider.name) || "").toLowerCase();
  if (providerName === "anthropic" || String(model).startsWith("claude-")) {
    return { provider: "anthropic", model: model || DEFAULT_ANTHROPIC_MODEL };
  }
  if (providerName === "custom" || providerName === "ollama" || String(model).includes(":")) {
    return { provider: "ollama", model: model || defaultOllamaModel() };
  }
  if (!model) throw new Error("AgentControl variation has no model name.");
  return { provider: "ollama", model };
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(String(text || "").length / 4));
}

function* chunkYield(text, metrics, started) {
  if (!text) {
    metrics.finish_reason = "stop";
    return;
  }
  metrics.ttft_ms = Math.round(performance.now() - started);
  const size = 24;
  for (let i = 0; i < text.length; i += size) {
    yield { type: "token", text: text.slice(i, i + size) };
  }
  metrics.finish_reason = "stop";
}

function fillFromResult(result, messages, metrics) {
  const text = String(result.text || "");
  const usage = result.usage;
  if (usage) {
    metrics.prompt_tokens = Number(usage.input_tokens || usage.prompt_tokens || 0);
    metrics.completion_tokens = Number(usage.output_tokens || usage.completion_tokens || 0);
    metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens;
  } else {
    const prompt = messages.map((m) => m.content || "").join("");
    metrics.prompt_tokens = estimateTokens(prompt);
    metrics.completion_tokens = estimateTokens(text);
    metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens;
  }
}

async function ollamaComplete(model, messages) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  const res = await fetch(`${host}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, stream: false, messages }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Ollama HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  const data = await res.json();
  return { text: String((data.message && data.message.content) || ""), raw: data };
}

function ollamaMetrics(result, messages) {
  const prompt = messages.map((m) => m.content || "").join("");
  const text = String(result.text || "");
  const input = estimateTokens(prompt);
  const output = estimateTokens(text);
  return {
    success: true,
    tokens: { total: input + output, input, output },
  };
}

async function anthropicComplete(model, messages) {
  const apiKey = String(process.env.ANTHROPIC_API_KEY || "").trim();
  if (!apiKey) {
    throw new Error(
      "ANTHROPIC_API_KEY is required for Anthropic variations (Best Betty → tracked-anthropic)."
    );
  }
  const systemParts = messages.filter((m) => m.role === "system").map((m) => m.content);
  const chat = messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({ role: m.role, content: m.content }));
  const body = {
    model,
    max_tokens: 1024,
    messages: chat.length ? chat : [{ role: "user", content: "Summarize the stories." }],
  };
  if (systemParts.length) body.system = systemParts.join("\n\n");

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Anthropic HTTP ${res.status}: ${errBody.slice(0, 300)}`);
  }
  const data = await res.json();
  const text = (data.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text || "")
    .join("");
  return { text, usage: data.usage, raw: data };
}

function anthropicMetrics(result) {
  const usage = result.usage || {};
  const input = Number(usage.input_tokens || 0);
  const output = Number(usage.output_tokens || 0);
  return {
    success: true,
    tokens: { total: input + output, input, output },
  };
}

async function* generateStream(persona, tickerResults) {
  const storiesText = formatStories(tickerResults);
  const started = performance.now();
  const metrics = emptyMetrics();
  let resumptionToken = null;

  let config;
  try {
    config = await evaluateCompletion(persona, storiesText);
  } catch (exc) {
    const messages = baselineMessages(storiesText);
    const provider = "ollama";
    const model = defaultOllamaModel();
    yield {
      type: "meta",
      persona: { ...persona },
      input: userMessageText(messages) || storiesText,
      provider,
      model: `${model} (code baseline)`,
      mode: "baseline-fallback",
      configKey: configKey(),
      fallback: true,
      stories: tickerResults || [],
      ldTransaction: buildLdTransaction({
        persona,
        storiesText,
        configKeyValue: configKey(),
        fallback: true,
        mode: "baseline-fallback",
        provider,
        model: `${model} (code baseline)`,
        messages,
        servedMeta: null,
        enabled: false,
      }),
    };
    yield {
      type: "status",
      message: `LaunchDarkly evaluation failed (${exc.message || exc}); using code baseline.`,
    };
    try {
      const result = await ollamaComplete(model, messages);
      fillFromResult(result, messages, metrics);
      yield* chunkYield(result.text || "", metrics, started);
    } catch (genExc) {
      yield { type: "error", message: String(genExc.message || genExc) };
      metrics.finish_reason = "error";
    }
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done", resumptionToken: null };
    return;
  }

  if (!config.enabled) {
    const messages = baselineMessages(storiesText);
    const provider = "ollama";
    const model = defaultOllamaModel();
    yield {
      type: "meta",
      persona: { ...persona },
      input: userMessageText(messages) || storiesText,
      provider,
      model: `${model} (code baseline)`,
      mode: "baseline-fallback",
      configKey: configKey(),
      fallback: true,
      stories: tickerResults || [],
      ldTransaction: buildLdTransaction({
        persona,
        storiesText,
        configKeyValue: configKey(),
        fallback: true,
        mode: "baseline-fallback",
        provider,
        model: `${model} (code baseline)`,
        messages,
        servedMeta: null,
        enabled: false,
      }),
    };
    yield {
      type: "status",
      message: `AgentControl config '${configKey()}' is off; using code baseline.`,
    };
    try {
      const result = await ollamaComplete(model, messages);
      fillFromResult(result, messages, metrics);
      yield* chunkYield(result.text || "", metrics, started);
    } catch (genExc) {
      yield { type: "error", message: String(genExc.message || genExc) };
      metrics.finish_reason = "error";
    }
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done", resumptionToken: null };
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
    tracker = config.createTracker();
    resumptionToken = tracker.resumptionToken || null;
  } catch (exc) {
    yield {
      type: "meta",
      persona: { ...persona },
      input: storiesText,
      provider: "—",
      model: "—",
      mode: "launchdarkly",
      configKey: configKey(),
      stories: tickerResults || [],
    };
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done", resumptionToken: null };
    return;
  }

  console.log(
    `[generate] ${persona.name}: provider=${provider} model=${model} config=${configKey()}`
  );
  yield {
    type: "meta",
    persona: { ...persona },
    input: userMessageText(messages) || storiesText,
    provider,
    model,
    mode: "launchdarkly",
    configKey: configKey(),
    fallback: false,
    stories: tickerResults || [],
    tracked: true,
    ldTransaction: buildLdTransaction({
      persona,
      storiesText,
      configKeyValue: configKey(),
      fallback: false,
      mode: "launchdarkly",
      provider,
      model,
      messages,
      servedMeta: null,
      enabled: true,
    }),
  };

  try {
    // LaunchDarkly: trackMetricsOf — duration, success/error, tokens → Monitoring
    let result;
    if (provider === "anthropic") {
      result = await tracker.trackMetricsOf(anthropicMetrics, () =>
        anthropicComplete(model, messages)
      );
    } else if (provider === "ollama") {
      result = await tracker.trackMetricsOf(
        (res) => ollamaMetrics(res, messages),
        () => ollamaComplete(model, messages)
      );
    } else {
      throw new Error(`Unsupported runtime provider '${provider}'.`);
    }
    fillFromResult(result, messages, metrics);
    yield* chunkYield(result.text || "", metrics, started);
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
  }

  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield { type: "done", resumptionToken };
}

async function submitFeedback({ persona, resumptionToken, kind }) {
  const token = String(resumptionToken || "").trim();
  if (!token) throw new Error("resumptionToken is required.");
  const kindL = String(kind || "").trim().toLowerCase();
  let fb;
  if (["positive", "up", "thumbsup", "+"].includes(kindL)) {
    fb = LDFeedbackKind.Positive;
  } else if (["negative", "down", "thumbsdown", "-"].includes(kindL)) {
    fb = LDFeedbackKind.Negative;
  } else {
    throw new Error("kind must be positive or negative.");
  }
  const ctx = buildContext(persona);
  const result = getAiClient().createTracker(token, ctx);
  const tracker = result && (result.value !== undefined ? result.value : result);
  if (!tracker || typeof tracker.trackFeedback !== "function") {
    throw new Error("Could not rebuild tracker from resumption token.");
  }
  tracker.trackFeedback({ kind: fb });
  return { ok: true, kind: kindL.startsWith("neg") || kindL === "-" || kindL === "down" ? "negative" : "positive" };
}

module.exports = {
  PERSONAS,
  configKey,
  personaById,
  initLaunchDarkly,
  generateStream,
  submitFeedback,
};
