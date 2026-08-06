/**
 * agentCore.js — domain logic for 21-agent-completion-config (no HTTP here).
 *
 * =============================================================================
 * HOW TO READ THIS FILE
 * =============================================================================
 *
 * Same product flow as 01-reference-agent, but at generate time LaunchDarkly
 * AgentControl supplies **model**, **system** message, and **user** message.
 *
 *   1. Data          Personas (UI labels + LD context key/name)
 *   2. LaunchDarkly  Init server SDK + AI SDK; completionConfig evaluation
 *   3. Providers     Route by served provider/model (Ollama Custom, …)
 *   4. Generation    generateStream() — evaluate config, then stream LLM tokens
 *
 * LaunchDarkly insertion point (read this first):
 *   generateStream() → LDAIClient.completionConfig(...)
 *   Docs: https://launchdarkly.com/docs/sdk/ai/node-js
 *   Keywords: AgentControl · completion config · AI SDK · message variables
 *
 * Variables: the config user message includes {{ stories }}; we pass
 * { stories: <formatted headlines> } so LaunchDarkly substitutes at evaluate time.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { initAi } = require("@launchdarkly/server-sdk-ai");
const { formatStoriesForPrompt } = require("./yahooNews");

const HERE = __dirname;
const EXAMPLE_ROOT = path.resolve(HERE, "..");
const BASELINE_MESSAGES_DIR = path.join(EXAMPLE_ROOT, "rest", "messages");

const CANNED_STORIES =
  "No ticker stories loaded yet. Ask the user to click Get Stories.";

const DEFAULT_CONFIG_KEY = "equity-briefing-completion";
const DEFAULT_OLLAMA_MODEL = "llama3.2:3b";

const PERSONAS = [
  {
    id: "conservative-charlie",
    name: "Conservative Charlie",
    profile: "conservative",
    anonymous: false,
  },
  {
    id: "neutral-nancy",
    name: "Neutral Nancy",
    profile: "neutral",
    anonymous: false,
  },
  {
    id: "thoughtless-toby",
    name: "Thoughtless Toby",
    profile: "risk-taker",
    anonymous: false,
  },
  // No name targeting — anonymous context falls through to baseline-analyst.
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
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch (exc) {
    throw new Error(`Could not read baseline message file ${filePath}: ${exc.message}`);
  }
}

/** In-code baseline system prompt (same text as rest/messages/baseline-system.txt). */
function baselineSystemPrompt() {
  return readMessageFile("baseline-system.txt").trim();
}

/** User prompt template with {{ stories }} (rest/messages/baseline-user.txt). */
function baselineUserTemplate() {
  return readMessageFile("baseline-user.txt").trim();
}

/** Fill {{ stories }} locally when using the code baseline fallback. */
function renderBaselineUser(storiesText) {
  const template = baselineUserTemplate();
  return template
    .replaceAll("{{ stories }}", storiesText)
    .replaceAll("{{stories}}", storiesText);
}

/** Chat messages for the in-code baseline-analyst fallback. */
function baselineMessages(storiesText) {
  return [
    { role: "system", content: baselineSystemPrompt() },
    { role: "user", content: renderBaselineUser(storiesText) },
  ];
}

/**
 * SDK default when the config key is missing / unreachable.
 *
 * Also documents the intended offline shape. When the config exists but is
 * turned off, LaunchDarkly still returns the disabled variation
 * (enabled=false) — see generateStream() for the app-level fallback.
 * https://launchdarkly.com/docs/sdk/ai/node-js
 */
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

/**
 * Initialize the shared LaunchDarkly clients once at process start.
 *
 * LaunchDarkly: server-side SDK + AI SDK for AgentControl completion configs.
 * https://launchdarkly.com/docs/sdk/ai/node-js
 */
async function initLaunchDarkly() {
  if (aiClient != null) return;

  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error(
      "LD_SDK_KEY is required. Export a server-side SDK key for the " +
        "environment that targets equity-briefing-completion."
    );
  }

  ldClient = LaunchDarkly.init(sdkKey);
  try {
    await ldClient.waitForInitialization({ timeout: 5 });
  } catch (exc) {
    throw new Error(
      "LaunchDarkly client failed to initialize within 5s. " +
        "Check LD_SDK_KEY and network access to LaunchDarkly. " +
        `(${exc.message || exc})`
    );
  }
  aiClient = initAi(ldClient);
}

function getAiClient() {
  if (aiClient == null) {
    throw new Error("LaunchDarkly AI client is not initialized. Call initLaunchDarkly() first.");
  }
  return aiClient;
}

/**
 * Build the LD evaluation context for this persona.
 *
 * Named personas: user key + name (name targeting matches Charlie/Nancy/Toby).
 * Anonymous Amelia: fixed key, anonymous=true — not indexed as a known user;
 * name rules do not match → fallthrough (baseline-analyst).
 * https://launchdarkly.com/docs/sdk/features/anonymous
 */
function buildContext(persona) {
  const context = {
    kind: "user",
    key: persona.id,
    name: persona.name,
  };
  if (persona.anonymous) {
    context.anonymous = true;
  }
  return context;
}

/**
 * Fetch model + messages from AgentControl (completion mode).
 *
 * LaunchDarkly capability: completionConfig evaluation with message variables.
 * https://launchdarkly.com/docs/sdk/features/agentcontrol-config
 */
async function evaluateCompletion(persona, storiesText) {
  return getAiClient().completionConfig(
    configKey(),
    buildContext(persona),
    baselineCompletionDefault(),
    { stories: storiesText }
  );
}

/**
 * Metadata for the served variation (public SDK: variationDetail).
 *
 * The typed AI config exposes model/messages/provider/enabled, but not
 * variationKey. That lives on the raw evaluation's `_ldMeta`.
 * https://launchdarkly.com/docs/sdk/features/evaluation-reasons
 */
async function evaluationMeta(persona) {
  if (ldClient == null) {
    throw new Error("LaunchDarkly client is not initialized.");
  }
  const detail = await ldClient.variationDetail(
    configKey(),
    buildContext(persona),
    baselineCompletionDefault()
  );
  const value = detail && typeof detail.value === "object" && detail.value ? detail.value : {};
  const meta = value._ldMeta || {};
  return {
    variationKey: meta.variationKey,
    version: meta.version,
    versionKey: meta.versionKey,
    mode: meta.mode,
    modelKey: meta.modelKey,
    modelVersion: meta.modelVersion,
    enabledMeta: meta.enabled,
    variationIndex: detail.variationIndex,
    reason: detail.reason,
  };
}

function logServedVariation(persona, meta) {
  if (!meta) {
    console.log(`[generate] ${persona.name}: variation=(unknown)`);
    return;
  }
  const key = meta.variationKey || "(none)";
  const reason = meta.reason || {};
  const reasonKind =
    reason && typeof reason === "object" && "kind" in reason ? reason.kind : reason;
  console.log(`[generate] ${persona.name}: variation='${key}' reason='${reasonKind}'`);
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
          "(baseline-analyst shape; used if config key is missing).",
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

function messagesAsDicts(config) {
  const out = [];
  for (const msg of config.messages || []) {
    out.push({ role: msg.role, content: msg.content });
  }
  return out;
}

function userMessageText(messages) {
  for (const msg of messages) {
    if (msg.role === "user") return msg.content || "";
  }
  return "";
}

function systemMessageText(messages) {
  for (const msg of messages) {
    if (msg.role === "system") return msg.content || "";
  }
  return "";
}

function systemPromptPreview(messages, maxChars = 40) {
  const text = systemMessageText(messages).trim();
  if (!text) return "(none)";
  const firstLine = text.split(/\r?\n/)[0].trim();
  if (firstLine.length > maxChars) {
    return `${firstLine.slice(0, maxChars - 1)}…`;
  }
  return firstLine;
}

function logSystemPromptSource(source, messages, persona) {
  const preview = systemPromptPreview(messages);
  console.log(`[generate] ${persona.name}: system prompt from ${source}: '${preview}'`);
}

/**
 * Map served provider/model to a local caller (ollama).
 *
 * Custom / Ollama models from rest/create-model-config.sh use provider Custom
 * and model id llama3.2:3b → call local Ollama.
 */
function resolveRuntime(config) {
  const model = (config.model && config.model.name) || "";
  const providerName = (config.provider && config.provider.name) || "";
  const pl = providerName.trim().toLowerCase();

  if (pl === "custom" || pl === "ollama" || model.includes(":")) {
    return { provider: "ollama", model };
  }
  if (
    pl === "bedrock" ||
    model.startsWith("us.") ||
    model.startsWith("amazon.") ||
    model.startsWith("anthropic.") ||
    model.startsWith("meta.")
  ) {
    return { provider: "bedrock", model };
  }
  if (!model) {
    throw new Error(
      "AgentControl variation has no model name. " +
        "Check modelConfigKey on the served variation in LaunchDarkly."
    );
  }
  return { provider: "ollama", model };
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(String(text || "").length / 4));
}

function fillTokenEstimates(messages, completion, metrics) {
  const prompt = messages.map((m) => m.content || "").join("");
  metrics.prompt_tokens = estimateTokens(prompt);
  metrics.completion_tokens = estimateTokens(completion);
  metrics.total_tokens = (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);
}

async function* ollamaStream(model, messages) {
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
      body: JSON.stringify({ model, stream: true, messages }),
      signal: AbortSignal.timeout(120000),
    });
  } catch (exc) {
    throw new Error(
      `Ollama request failed (${host}, model=${model}): ${exc.message || exc}. ` +
        "Is Ollama running, and does the AgentControl model id match `ollama list`?"
    );
  }
  if (!res.ok || !res.body) {
    throw new Error(
      `Ollama request failed (${host}, model=${model}): HTTP ${res.status}. ` +
        "Is Ollama running, and does the AgentControl model id match `ollama list`?"
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

async function* generateOllama(model, messages, started, metrics) {
  const textParts = [];
  let first = true;
  for await (const chunk of ollamaStream(model, messages)) {
    if (first) {
      metrics.ttft_ms = Math.round(performance.now() - started);
      first = false;
    }
    textParts.push(chunk);
    yield { type: "token", text: chunk };
  }
  metrics.finish_reason = "stop";
  fillTokenEstimates(messages, textParts.join(""), metrics);
}

function trackGeneration(tracker, metrics) {
  if (!tracker) return;
  try {
    tracker.trackSuccess();
    if (metrics.latency_ms != null) tracker.trackDuration(metrics.latency_ms);
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
  } catch {
    // Metrics are best-effort; never fail the stream for tracker errors.
  }
}

/**
 * Evaluate AgentControl, then stream tokens from the served model.
 *
 * Event contract matches 01-reference-agent (meta / token / error / metrics / done).
 *
 * When the AgentControl config is disabled (or returns enabled=false),
 * fall back to the in-code baseline-analyst prompts + local Ollama model —
 * same text as rest/messages/baseline-*.txt.
 */
async function* generateStream(persona, tickerResults = null) {
  const storiesText = formatStories(tickerResults);
  const started = performance.now();
  const metrics = emptyMetrics();
  let tracker = null;
  let usingFallback = false;
  let config = null;
  let servedMeta = null;
  let fallbackReason = null;

  try {
    // LaunchDarkly: evaluate completion config (model + messages).
    config = await evaluateCompletion(persona, storiesText);
    servedMeta = await evaluationMeta(persona);
  } catch (exc) {
    usingFallback = true;
    config = null;
    servedMeta = null;
    fallbackReason = `LaunchDarkly evaluation failed (${exc.message || exc}); using code baseline.`;
  }

  if (!usingFallback && config && !config.enabled) {
    usingFallback = true;
    fallbackReason =
      `AgentControl config '${configKey()}' is off / enabled=false; ` +
      "using code baseline-analyst.";
  }

  if (usingFallback) {
    const messages = baselineMessages(storiesText);
    const provider = "ollama";
    const model = defaultOllamaModel();
    const mode = "baseline-fallback";
    console.log(`[generate] ${persona.name}: variation='code-baseline' reason='FALLBACK'`);
    logSystemPromptSource("code baseline (AgentControl off)", messages, persona);
    const promptPreview = userMessageText(messages) || storiesText;
    yield {
      type: "meta",
      persona: { ...persona },
      input: promptPreview,
      provider,
      model: `${model} (code baseline)`,
      mode,
      configKey: configKey(),
      fallback: true,
      stories: tickerResults || [],
      ldTransaction: buildLdTransaction({
        persona,
        storiesText,
        configKeyValue: configKey(),
        fallback: true,
        mode,
        provider,
        model: `${model} (code baseline)`,
        messages,
        servedMeta,
        enabled: config == null ? false : Boolean(config.enabled),
      }),
    };
    if (fallbackReason) {
      yield { type: "status", message: fallbackReason };
    }
    try {
      yield* generateOllama(model, messages, started, metrics);
    } catch (exc) {
      yield { type: "error", message: String(exc.message || exc) };
      metrics.finish_reason = "error";
    }
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  let provider;
  let model;
  let messages;
  try {
    ({ provider, model } = resolveRuntime(config));
    messages = messagesAsDicts(config);
    if (!messages.length) {
      throw new Error("Served variation has no messages.");
    }
    if (typeof config.createTracker === "function") {
      tracker = config.createTracker();
    }
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
    yield { type: "done" };
    return;
  }

  logServedVariation(persona, servedMeta);
  logSystemPromptSource(`LaunchDarkly (${configKey()})`, messages, persona);
  const promptPreview = userMessageText(messages) || storiesText;
  yield {
    type: "meta",
    persona: { ...persona },
    input: promptPreview,
    provider,
    model,
    mode: "launchdarkly",
    configKey: configKey(),
    variationKey: (servedMeta || {}).variationKey,
    fallback: false,
    stories: tickerResults || [],
    ldTransaction: buildLdTransaction({
      persona,
      storiesText,
      configKeyValue: configKey(),
      fallback: false,
      mode: "launchdarkly",
      provider,
      model,
      messages,
      servedMeta,
      enabled: Boolean(config.enabled),
    }),
  };

  try {
    if (provider === "ollama") {
      yield* generateOllama(model, messages, started, metrics);
    } else if (provider === "bedrock") {
      yield {
        type: "error",
        message:
          "Bedrock is not wired in the Node example. " +
          "Use an Ollama / Custom model on the variation, or run the Python web app for Bedrock.",
      };
      metrics.finish_reason = "error";
    } else {
      throw new Error(`Unsupported runtime provider '${provider}'.`);
    }
    metrics.latency_ms = Math.round(performance.now() - started);
    trackGeneration(tracker, metrics);
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
    if (tracker && typeof tracker.trackError === "function") {
      try {
        tracker.trackError();
      } catch {
        // ignore
      }
    }
  }

  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield { type: "done" };
}

module.exports = {
  PERSONAS,
  configKey,
  personaById,
  initLaunchDarkly,
  generateStream,
  buildContext,
  baselineCompletionDefault,
};
