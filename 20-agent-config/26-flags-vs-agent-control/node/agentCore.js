/**
 * agentCore.js — domain logic for 26-flags-vs-agent-control (no HTTP here).
 *
 * Three sources, one Generate:
 *   original  completionConfig (model, messages, {{ stories }}, attached tools)
 *   flags     four variationDetail reads, assembled in the app
 *   json      one JSON variationDetail, parsed in the app
 *
 * The guardrail is judgeConfig plus a local Ollama JSON score. On a fail,
 * only the AgentControl variation can carry reduce-briefing-uncertainty.
 *
 * Node note: createJudge needs @launchdarkly/server-sdk-ai-openai, which still
 * peers AI SDK 1.x. This port stays on AI SDK 2.x and scores with Ollama,
 * matching 24. Python still uses create_judge.
 *
 * LaunchDarkly: completion config · feature flags · judges · Library tools
 * https://launchdarkly.com/docs/sdk/ai/node-js
 * https://launchdarkly.com/docs/sdk/features/flag-types
 * https://launchdarkly.com/docs/home/agentcontrol/judges
 * https://launchdarkly.com/docs/home/agentcontrol/tools
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

const DEFAULT_CONFIG_KEY = "equity-briefing-flag-compare";
const DEFAULT_JUDGE_KEY = "equity-briefing-flag-compare-judge";
const DEFAULT_JUDGE_METRIC = "$ld:ai:judge:flag-compare";
const DEFAULT_PASS_THRESHOLD = 0.65;
const REPAIR_TOOL_KEY = "reduce-briefing-uncertainty";
const DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
const JUDGE_JSON_SUFFIX =
  'Respond with JSON only: {"score": <number from 0 to 1>, "reasoning": "<short text>"}';

const FLAG_MODEL_KEY = "configure-briefing-model";
const FLAG_SYSTEM_KEY = "configure-briefing-system-prompt";
const FLAG_USER_KEY = "configure-briefing-user-prompt";
const FLAG_JUDGE_KEY = "enable-briefing-judge";
const FLAG_JSON_KEY = "configure-briefing-json";

const PERSONAS = [
  { id: "conservative-charlie", name: "Conservative Charlie", profile: "conservative" },
  { id: "thoughtless-toby", name: "Thoughtless Toby", profile: "risk-taker" },
];

let ldClient = null;
let aiClient = null;

function demoPersonas() {
  return PERSONAS.filter((p) => p.id === "thoughtless-toby");
}

function personaById(personaId) {
  return PERSONAS.find((p) => p.id === personaId) || null;
}

function configKey() {
  return String(process.env.LD_AGENT_CONFIG_KEY || DEFAULT_CONFIG_KEY).trim() || DEFAULT_CONFIG_KEY;
}

function judgeKey() {
  return String(process.env.LD_JUDGE_KEY || DEFAULT_JUDGE_KEY).trim() || DEFAULT_JUDGE_KEY;
}

function passThreshold() {
  const raw = String(process.env.JUDGE_PASS_THRESHOLD || "").trim();
  const n = Number(raw);
  return raw && Number.isFinite(n) ? n : DEFAULT_PASS_THRESHOLD;
}

function defaultOllamaModel() {
  return String(process.env.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim() || DEFAULT_OLLAMA_MODEL;
}

function readMessageFile(name) {
  return fs.readFileSync(path.join(MESSAGES_DIR, name), "utf8");
}

function formatStories(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_STORIES;
  return formatStoriesForPrompt(tickerResults);
}

function fillStories(template, storiesText) {
  return String(template || "")
    .replaceAll("{{ stories }}", storiesText)
    .replaceAll("{{stories}}", storiesText);
}

function personaPrompts(persona) {
  if (persona.id === "thoughtless-toby") {
    return {
      model: "llama3.2:1b",
      system: readMessageFile("reckless-system.txt").trim(),
      user: readMessageFile("reckless-user.txt").trim(),
    };
  }
  return {
    model: "llama3.2:3b",
    system: readMessageFile("skeptic-system.txt").trim(),
    user: readMessageFile("skeptic-user.txt").trim(),
  };
}

function buildContext(persona) {
  return { kind: "user", key: persona.id, name: persona.name };
}

function completionDefault() {
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

function judgeDefault() {
  return {
    enabled: true,
    model: { name: "llama3.2:3b", parameters: { temperature: 0 } },
    provider: { name: "Custom" },
    evaluationMetricKey: DEFAULT_JUDGE_METRIC,
    messages: [{ role: "system", content: readMessageFile("judge-system.txt").trim() }],
  };
}

async function initLaunchDarkly() {
  if (aiClient) return;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error(
      "LD_SDK_KEY is required. Export a server-side SDK key for the environment " +
        "that targets equity-briefing-flag-compare."
    );
  }
  ldClient = LaunchDarkly.init(sdkKey);
  await ldClient.waitForInitialization({ timeout: 10 });
  aiClient = initAi(ldClient);
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

function toolNames(config) {
  const tools = config && config.tools;
  if (!tools) return [];
  const entries = tools instanceof Map ? [...tools.entries()] : Object.entries(tools);
  return entries.map(([key, tool]) => String((tool && tool.name) || key));
}

function plainReason(reason) {
  if (!reason || typeof reason !== "object") return {};
  const out = {};
  if (reason.kind != null) out.kind = String(reason.kind);
  if (reason.errorKind != null) out.errorKind = String(reason.errorKind);
  if (reason.ruleIndex != null && reason.ruleIndex >= 0) out.ruleIndex = reason.ruleIndex;
  if (reason.ruleId) out.ruleId = String(reason.ruleId);
  return out;
}

function previewValue(value, limit = 180) {
  let text;
  if (typeof value === "boolean") text = value ? "true" : "false";
  else if (value && typeof value === "object") text = JSON.stringify(value);
  else text = String(value || "");
  text = text.replace(/\s+/g, " ").trim();
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

async function flagDetail(key, persona, fallback) {
  // LaunchDarkly: variationDetail — value, variation index, and reason.
  // https://launchdarkly.com/docs/sdk/features/evaluation-reasons
  const detail = await ldClient.variationDetail(key, buildContext(persona), fallback);
  const reason = plainReason(detail && detail.reason);
  return {
    value: detail ? detail.value : fallback,
    variationIndex: detail ? detail.variationIndex : null,
    reason,
    record: {
      key,
      variationIndex: detail ? detail.variationIndex : null,
      reason,
      reasonKind: reason.kind,
      valuePreview: previewValue(detail ? detail.value : fallback),
    },
    missing: reason.kind === "ERROR" && reason.errorKind === "FLAG_NOT_FOUND",
  };
}

async function evaluationMeta(persona) {
  const detail = await ldClient.variationDetail(
    configKey(),
    buildContext(persona),
    completionDefault()
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
    variationIndex: detail.variationIndex,
    reason: plainReason(detail.reason),
  };
}

function agentAppWork() {
  return [
    "Evaluated one completion config for the model, both messages, and any attached tools.",
    "LaunchDarkly substituted {{ stories }} before the app saw the user message.",
    "Called the model and provider named on that variation.",
    "Evaluated one judge config. On a fail, the app runs reduce-briefing-uncertainty if that tool is attached.",
    "Separate flags and the JSON flag do not return a tool, so a failed draft stays failed.",
  ];
}

function flagAppWork(source, judgeOn) {
  const steps =
    source === "json"
      ? [
          "Evaluated one JSON flag. The value is an object the app defined.",
          "Read model, systemPrompt, userPrompt, and judge out of that object.",
          "Substituted {{ stories }} in the user prompt.",
          "Built the message list and picked a provider from the model id.",
        ]
      : [
          "Evaluated four flags. Each one repeated the Charlie name rule.",
          "Substituted {{ stories }} in the user-prompt flag.",
          "Built the message list from two string flags and picked a provider from the model id.",
        ];
  steps.push(
    judgeOn
      ? "The flag said to score. The score itself still comes from the AgentControl judge config."
      : "The flag said not to score, so the draft stays plain."
  );
  return steps;
}

function reduceBriefingUncertainty(draft) {
  let text = String(draft || "");
  const swaps = [
    [/\b100\s*%/gi, "low"],
    [/\b9[5-9]\s*%/gi, "limited"],
    [
      /\b(?:buy hard|strong buy|all-in|moonshot|to the moon|can't lose|cannot lose|no-brainer)\b/gi,
      "no firm trade",
    ],
    [/\b(?:will soar|will double|can't miss|cannot miss)\b/gi, "may not move"],
  ];
  for (const [pattern, repl] of swaps) text = text.replace(pattern, repl);
  const hedge =
    "Uncertainty: these headlines do not support a firm recommendation. " +
    "Confidence stays low, and missing information is left missing.";
  if (!text.includes("Uncertainty:")) text = `${text.trim()}\n\n${hedge}`;
  return text;
}

function estimateTokens(text) {
  return Math.max(1, Math.floor(String(text).length / 4));
}

function fillTokenEstimates(messages, completion, metrics) {
  const prompt = messages.map((m) => m.content || "").join("");
  metrics.prompt_tokens = estimateTokens(prompt);
  metrics.completion_tokens = estimateTokens(completion);
  metrics.total_tokens = metrics.prompt_tokens + metrics.completion_tokens;
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

async function scoreDraft(persona, storiesText, draft, source, evaluations) {
  // LaunchDarkly: judgeConfig — prompts and model from the judge config.
  // The numeric score is an Ollama JSON call. Python uses create_judge.
  // https://launchdarkly.com/docs/home/agentcontrol/judges
  const threshold = passThreshold();
  const base = {
    type: "judge",
    source,
    on: true,
    judgeKey: judgeKey(),
    threshold,
    evaluations,
  };
  if (!String(draft || "").trim()) {
    return { ...base, success: false, passed: false, score: null, reasoning: null, error: "No draft to score." };
  }
  try {
    const config = await aiClient.judgeConfig(judgeKey(), buildContext(persona), judgeDefault());
    let model = (config.model && config.model.name) || "llama3.2:3b";
    try {
      ({ model } = resolveRuntime(config));
    } catch (_) {}
    let system = messagesAsDicts(config)
      .filter((m) => m.role === "system")
      .map((m) => m.content || "")
      .join("\n")
      .trim();
    if (!system) system = readMessageFile("judge-system.txt").trim();
    if (!system.includes("Respond with JSON")) system = `${system}\n\n${JUDGE_JSON_SUFFIX}`;
    const user =
      "MESSAGE HISTORY:\n" +
      "Task: Write a short equity briefing comparing the tickers using only " +
      `the headlines below.\n\nHEADLINES:\n${storiesText}\n\nRESPONSE TO EVALUATE:\n${draft}`;
    const parsed = await ollamaJudgeJson(model, [
      { role: "system", content: system },
      { role: "user", content: user },
    ]);
    const score =
      parsed.score != null && Number.isFinite(Number(parsed.score)) ? Number(parsed.score) : null;
    const reasoning = parsed.reasoning != null ? String(parsed.reasoning) : null;
    const tracker = config.tracker || (config.createTracker && config.createTracker());
    if (tracker && typeof tracker.trackJudgeResult === "function") {
      try {
        tracker.trackJudgeResult({
          judgeConfigKey: judgeKey(),
          success: true,
          sampled: true,
          metricKey: config.evaluationMetricKey || DEFAULT_JUDGE_METRIC,
          score: score ?? undefined,
          reasoning: reasoning || undefined,
        });
      } catch (_) {}
    }
    return {
      ...base,
      success: true,
      error: null,
      score,
      reasoning,
      metricKey: config.evaluationMetricKey || DEFAULT_JUDGE_METRIC,
      passed: score != null && score >= threshold,
    };
  } catch (exc) {
    return {
      ...base,
      success: false,
      passed: false,
      score: null,
      reasoning: null,
      error: String(exc.message || exc),
    };
  }
}

function* repairIfFailed(names, tracker, draft, scored) {
  if (scored.passed !== false || scored.on === false) return;
  if (!names.includes(REPAIR_TOOL_KEY)) {
    yield {
      type: "status",
      message:
        "Judge failed. This variation has no repair tool attached. " +
        "Provision with rest/attach-repair-tool.sh.",
    };
    return;
  }
  yield { type: "eval", surface: "tool", key: REPAIR_TOOL_KEY };
  if (tracker && typeof tracker.trackToolCall === "function") {
    try {
      tracker.trackToolCall(REPAIR_TOOL_KEY);
    } catch (_) {}
  }
  yield {
    type: "repair",
    tool: REPAIR_TOOL_KEY,
    repaired: reduceBriefingUncertainty(draft),
  };
}

async function* generateFromResolved(persona, tickerResults, resolved) {
  const storiesText = formatStories(tickerResults);
  const started = performance.now();
  const metrics = {};
  const messages = [
    { role: "system", content: resolved.system.trim() },
    { role: "user", content: fillStories(resolved.user, storiesText) },
  ];
  yield {
    type: "meta",
    persona: { ...persona },
    input: messages[1].content,
    userTemplate: resolved.user.trim(),
    provider: "ollama",
    model: resolved.model,
    mode: resolved.source,
    configKey: resolved.source === "json" ? FLAG_JSON_KEY : FLAG_MODEL_KEY,
    fallback: resolved.missing.length > 0,
    stories: tickerResults || [],
    source: resolved.source,
    systemPrompt: resolved.system.trim(),
    judgeOn: resolved.judgeOn,
    judgeSurface: resolved.judgeOn ? resolved.judgeSurface : "off",
    evaluations: resolved.evaluations,
    ldTransaction: {
      sent: {
        source: resolved.source,
        context: buildContext(persona),
        evaluations: resolved.evaluations,
      },
      received: {
        source: resolved.source,
        model: resolved.model,
        judgeOn: resolved.judgeOn,
        flagEvaluations: resolved.records,
        appWork: flagAppWork(resolved.source, resolved.judgeOn),
        messages: [
          { role: "system", content: resolved.system.trim() },
          { role: "user", content: resolved.user.trim() },
        ],
      },
    },
  };
  if (resolved.missing.length) {
    yield {
      type: "status",
      message:
        `Flag not found: ${resolved.missing.join(", ")}. Using in-code defaults. ` +
        "Provision with rest/create-flags.sh.",
    };
  }
  const draftParts = [];
  try {
    for await (const event of generateOllama(resolved.model, messages, started, metrics)) {
      if (event.type === "token") draftParts.push(event.text || "");
      yield event;
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
  }
  const draft = draftParts.join("");
  if (resolved.judgeOn) {
    yield { type: "status", message: "Scoring the draft…" };
    yield { type: "eval", surface: "judge", key: judgeKey() };
    yield await scoreDraft(
      persona,
      storiesText,
      draft,
      resolved.source,
      resolved.evaluations + 1
    );
  } else {
    yield {
      type: "judge",
      source: resolved.source,
      on: false,
      passed: null,
      score: null,
      evaluations: resolved.evaluations,
    };
  }
  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield { type: "done" };
}

async function* generateStream(persona, tickerResults, source = "original") {
  if (source === "flags" || source === "json") {
    const defaults = personaPrompts(persona);
    const records = [];
    const missing = [];
    let model = defaults.model;
    let system = defaults.system;
    let user = defaults.user;
    let judgeOn = true;
    if (source === "flags") {
      const pairs = [
        [FLAG_MODEL_KEY, defaults.model],
        [FLAG_SYSTEM_KEY, defaults.system],
        [FLAG_USER_KEY, defaults.user],
        [FLAG_JUDGE_KEY, true],
      ];
      const details = [];
      for (const [key, fallback] of pairs) {
        yield { type: "eval", surface: "flag", key };
        const detail = await flagDetail(key, persona, fallback);
        details.push(detail);
        records.push(detail.record);
        if (detail.missing) missing.push(key);
      }
      model = String(details[0].value || defaults.model);
      system = String(details[1].value || defaults.system);
      user = String(details[2].value || defaults.user);
      judgeOn = Boolean(details[3].value);
    } else {
      yield { type: "eval", surface: "flag", key: FLAG_JSON_KEY };
      const fallback = {
        model: defaults.model,
        systemPrompt: defaults.system,
        userPrompt: defaults.user,
        judge: true,
      };
      const detail = await flagDetail(FLAG_JSON_KEY, persona, fallback);
      records.push(detail.record);
      if (detail.missing) missing.push(FLAG_JSON_KEY);
      const body = detail.value && typeof detail.value === "object" ? detail.value : fallback;
      model = String(body.model || defaults.model);
      system = String(body.systemPrompt || defaults.system);
      user = String(body.userPrompt || defaults.user);
      judgeOn = body.judge !== false && Boolean(body.judge ?? true);
    }
    yield* generateFromResolved(persona, tickerResults, {
      source,
      model,
      system,
      user,
      judgeOn,
      evaluations: source === "flags" ? 4 : 1,
      judgeSurface: source === "flags" ? "boolean-flag" : "json-flag",
      missing,
      records,
    });
    return;
  }

  const storiesText = formatStories(tickerResults);
  const started = performance.now();
  const metrics = {};
  yield { type: "eval", surface: "agent config", key: configKey() };

  let config;
  let servedMeta = null;
  try {
    config = await aiClient.completionConfig(
      configKey(),
      buildContext(persona),
      completionDefault(),
      { stories: storiesText }
    );
    servedMeta = await evaluationMeta(persona);
  } catch (exc) {
    yield { type: "error", message: `LaunchDarkly completionConfig failed: ${exc.message || exc}` };
    yield { type: "done" };
    return;
  }

  if (!config.enabled) {
    yield {
      type: "error",
      message: `AgentControl config '${configKey()}' is off / enabled=false. Run rest/create-original.sh.`,
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

  const names = toolNames(config);
  console.log(
    `[generate] ${persona.name}: variation=${JSON.stringify(servedMeta && servedMeta.variationKey)} ` +
      `reason=${JSON.stringify(servedMeta && servedMeta.reason && servedMeta.reason.kind)}`
  );

  yield {
    type: "meta",
    persona: { ...persona },
    input: userMessageText(messages) || storiesText,
    provider,
    model,
    mode: "launchdarkly",
    configKey: configKey(),
    variationKey: servedMeta && servedMeta.variationKey,
    fallback: false,
    stories: tickerResults || [],
    source: "original",
    systemPrompt: (messages.find((m) => m.role === "system") || {}).content || "",
    judgeOn: true,
    judgeSurface: "judge-config",
    evaluations: 1,
    ldTransaction: {
      sent: {
        configKey: configKey(),
        context: buildContext(persona),
        variables: { stories: storiesText },
        sdkDefault: {
          description:
            "AICompletionConfigDefault passed to completionConfig " +
            "(concise-skeptic / Charlie shape; used if config key is missing).",
          enabled: true,
          model: defaultOllamaModel(),
          provider: "Custom",
          messages: completionDefault().messages,
        },
      },
      received: {
        fallback: false,
        mode: "launchdarkly",
        enabled: true,
        configKey: configKey(),
        variationKey: servedMeta && servedMeta.variationKey,
        variationIndex: servedMeta && servedMeta.variationIndex,
        reason: servedMeta && servedMeta.reason,
        version: servedMeta && servedMeta.version,
        versionKey: servedMeta && servedMeta.versionKey,
        ldMode: servedMeta && servedMeta.mode,
        modelKey: servedMeta && servedMeta.modelKey,
        modelVersion: servedMeta && servedMeta.modelVersion,
        provider,
        model,
        messages,
        tools: names,
        appWork: agentAppWork(),
      },
    },
  };

  if (servedMeta && servedMeta.reason && servedMeta.reason.errorKind === "FLAG_NOT_FOUND") {
    yield {
      type: "status",
      message:
        `Completion config '${configKey()}' was not found. ` +
        "Using the in-code concise-skeptic default. Provision with rest/create-original.sh.",
    };
  }

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
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    if (tracker && typeof tracker.trackError === "function") {
      try {
        tracker.trackError();
      } catch (_) {}
    }
  }

  const draft = draftParts.join("");
  yield { type: "status", message: "Scoring the draft…" };
  yield { type: "eval", surface: "judge", key: judgeKey() };
  const scored = await scoreDraft(persona, storiesText, draft, "original", 2);
  yield scored;
  yield* repairIfFailed(names, tracker, draft, scored);
  metrics.latency_ms = Math.round(performance.now() - started);
  yield { type: "metrics", metrics };
  yield { type: "done" };
}

module.exports = {
  PERSONAS,
  configKey,
  demoPersonas,
  generateStream,
  initLaunchDarkly,
  judgeKey,
  personaById,
};
