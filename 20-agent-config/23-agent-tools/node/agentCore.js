/**
 * agentCore.js — domain logic for 23-agent-tools (no HTTP here).
 *
 * Teaching focus: AgentControl **Library tools** attached to a completion
 * variation; the app runs a model-driven tool loop and records
 * trackToolCall for Monitoring.
 *
 * LaunchDarkly: AgentControl · Library tools · trackToolCall
 * https://launchdarkly.com/docs/home/agentcontrol/tools
 * https://launchdarkly.com/docs/sdk/ai/node-js
 */

"use strict";

const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { initAi } = require("@launchdarkly/server-sdk-ai");
const { formatStorySource } = require("./yahooNews");

const HERE = __dirname;
const EXAMPLE_ROOT = path.resolve(HERE, "..");
const BASELINE_MESSAGES_DIR = path.join(EXAMPLE_ROOT, "rest", "messages");

const CANNED_STORIES =
  "No ticker stories loaded yet. Ask the user to click Get Stories.";

// LaunchDarkly: ai-config key=equity-briefing-tools name="Equity briefing tools" mode=completion
// Tools: analyze-ticker-stories · compare-ticker-analyses

const DEFAULT_CONFIG_KEY = "equity-briefing-tools";
const DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5";
const DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
const TOOL_ANALYZE = "analyze-ticker-stories";
const TOOL_COMPARE = "compare-ticker-analyses";
const MAX_TOOL_STEPS = 6;

const OLLAMA_TOOL_SUFFIX =
  "Local-model rules (Ollama):\n" +
  "- You MUST call tools before writing any briefing.\n" +
  "- One tool call per turn when possible: analyze ticker 1, then analyze ticker 2, " +
  "then compare-ticker-analyses.\n" +
  "- Never call compare in the same turn as analyze.\n" +
  "- Pass the exact analyze JSON as analysis_a / analysis_b — do not invent fields.\n" +
  "- Do not skip compare-ticker-analyses after two analyzes.";

const POSITIVE_WORDS = new Set([
  "surge",
  "soar",
  "gain",
  "gains",
  "rise",
  "rises",
  "jump",
  "jumps",
  "beat",
  "beats",
  "record",
  "growth",
  "upgrade",
  "bullish",
  "profit",
  "profits",
  "strong",
  "rally",
]);

const NEGATIVE_WORDS = new Set([
  "fall",
  "falls",
  "drop",
  "drops",
  "plunge",
  "cut",
  "cuts",
  "miss",
  "misses",
  "loss",
  "losses",
  "downgrade",
  "bearish",
  "weak",
  "lawsuit",
  "probe",
  "decline",
  "risk",
  "risks",
]);

const PERSONAS = [
  {
    id: "analyst-claude",
    name: "Analyst Claude",
    profile: "anthropic",
    model: null,
    anonymous: false,
  },
  {
    id: "analyst-llama",
    name: "Analyst Llama",
    profile: "ollama",
    model: "llama3.2:3b",
    anonymous: false,
  },
  {
    id: "analyst-gwen",
    name: "Analyst Gwen",
    profile: "ollama",
    model: "llama3.2:1b",
    anonymous: false,
  },
];

const TOOL_HANDLERS = {
  [TOOL_ANALYZE]: handleAnalyzeTickerStories,
  [TOOL_COMPARE]: handleCompareTickerAnalyses,
};

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

function defaultAnthropicModel() {
  const model = String(process.env.ANTHROPIC_MODEL || DEFAULT_ANTHROPIC_MODEL).trim();
  return model || DEFAULT_ANTHROPIC_MODEL;
}

function defaultOllamaModel() {
  const model = String(process.env.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim();
  return model || DEFAULT_OLLAMA_MODEL;
}

function personaRuntime(persona) {
  const profile = String(persona.profile || "").trim().toLowerCase();
  if (["ollama", "local", "gwen", "llama"].includes(profile)) return "ollama";
  return "anthropic";
}

function personaModelName(persona, ldModel) {
  if (personaRuntime(persona) === "ollama") {
    const pinned = String(persona.model || "").trim();
    return ["ollama", pinned || defaultOllamaModel()];
  }
  const model = String(ldModel || "").startsWith("claude") ? ldModel : defaultAnthropicModel();
  return ["anthropic", model];
}

function readMessageFile(name) {
  const filePath = path.join(BASELINE_MESSAGES_DIR, name);
  try {
    return fs.readFileSync(filePath, "utf8").trim();
  } catch (exc) {
    throw new Error(`Could not read ${filePath}: ${exc.message || exc}`);
  }
}

function baselineSystemPrompt() {
  return readMessageFile("baseline-system.txt");
}

function baselineUserTemplate() {
  return readMessageFile("baseline-user.txt");
}

function storiesAsPromptText(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_STORIES;
  const lines = [];
  for (const block of tickerResults) {
    const ticker = String(block.ticker || "?").trim().toUpperCase() || "?";
    const name = String(block.name || ticker).trim();
    lines.push(`${ticker} (${name})`);
    const stories = block.stories || [];
    if (!stories.length) {
      lines.push("  - (no stories available)");
      if (block.error) lines.push(`  - note: ${block.error}`);
    } else {
      stories.forEach((story, i) => {
        if (!story || typeof story !== "object") return;
        const title = String(story.title || "").trim() || "(untitled)";
        const source = formatStorySource(story) || "unknown";
        lines.push(`  ${i + 1}. ${title} — ${source}`);
      });
    }
    lines.push("");
  }
  return lines.join("\n").trim();
}

function promptDisplaySections(storiesText) {
  return [
    { kind: "heading", text: "Task" },
    {
      kind: "body",
      text: "Write an equity briefing for these tickers using the required tools.",
    },
    { kind: "heading", text: "Stories" },
    { kind: "code", text: storiesText },
    { kind: "heading", text: "Reminder" },
    {
      kind: "body",
      text:
        "Call analyze-ticker-stories once per ticker (pass that ticker's headlines), " +
        "then compare-ticker-analyses, then write the briefing from tool results only.",
    },
  ];
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

function baselineCompletionDefault() {
  return {
    enabled: true,
    model: { name: defaultAnthropicModel() },
    provider: { name: "anthropic" },
    messages: [
      { role: "system", content: baselineSystemPrompt() },
      { role: "user", content: baselineUserTemplate() },
    ],
  };
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
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].role === "user") return messages[i].content || "";
  }
  return "";
}

function toolsEntries(config) {
  const tools = config.tools;
  if (!tools) return [];
  if (tools instanceof Map) return [...tools.entries()];
  return Object.entries(tools);
}

function ldToolsToAnthropic(config) {
  const out = [];
  for (const [key, tool] of toolsEntries(config)) {
    const name = tool.name || key;
    const description = tool.description || "";
    const parameters = tool.parameters || { type: "object", properties: {} };
    out.push({
      name: String(name),
      description: String(description),
      input_schema: parameters,
    });
  }
  return out;
}

function ldToolsToOpenai(config) {
  const out = [];
  for (const [key, tool] of toolsEntries(config)) {
    const name = tool.name || key;
    const description = tool.description || "";
    const parameters = tool.parameters || { type: "object", properties: {} };
    out.push({
      type: "function",
      function: {
        name: String(name),
        description: String(description),
        parameters,
      },
    });
  }
  return out;
}

function dispatchTool(name, rawInput) {
  const handler = TOOL_HANDLERS[name];
  if (!handler) return { error: `Unknown tool: ${name}` };
  return handler(rawInput);
}

function looksLikeAnalyzeResult(obj) {
  if (!obj || typeof obj !== "object") return false;
  return "ticker" in obj && ("tone_score" in obj || "claims" in obj);
}

function normalizeCompareArgs(rawInput, analyzeResults) {
  const a =
    rawInput.analysis_a && typeof rawInput.analysis_a === "object" ? rawInput.analysis_a : {};
  const b =
    rawInput.analysis_b && typeof rawInput.analysis_b === "object" ? rawInput.analysis_b : {};
  if (looksLikeAnalyzeResult(a) && looksLikeAnalyzeResult(b)) {
    return [{ analysis_a: a, analysis_b: b }, false];
  }
  if (analyzeResults.length >= 2) {
    return [
      {
        analysis_a: analyzeResults[analyzeResults.length - 2],
        analysis_b: analyzeResults[analyzeResults.length - 1],
      },
      true,
    ];
  }
  return [{ analysis_a: a, analysis_b: b }, false];
}

function ollamaToolName(call) {
  const fn = call && call.function;
  if (!fn || typeof fn !== "object") return "";
  return String(fn.name || "");
}

function sortOllamaToolCalls(calls) {
  const order = (call) => {
    const name = ollamaToolName(call);
    if (name === TOOL_ANALYZE) return 0;
    if (name === TOOL_COMPARE) return 1;
    return 2;
  };
  return [...calls].sort((a, b) => order(a) - order(b));
}

function sentimentScore(text) {
  const tokens = String(text || "")
    .toLowerCase()
    .match(/[a-zA-Z]+/g) || [];
  let score = 0;
  for (const tok of tokens) {
    if (POSITIVE_WORDS.has(tok)) score += 1;
    else if (NEGATIVE_WORDS.has(tok)) score -= 1;
  }
  return score;
}

function handleAnalyzeTickerStories(args) {
  const ticker = String(args.ticker || "").trim().toUpperCase() || "?";
  const rawStories = args.stories || [];
  const claims = [];
  let score = 0;
  for (const item of rawStories) {
    if (!item || typeof item !== "object") continue;
    const title = String(item.title || "").trim();
    if (!title) continue;
    const tone = sentimentScore(title);
    score += tone;
    let claim;
    if (tone > 0) claim = `Positive headline signal for ${ticker}: ${title}`;
    else if (tone < 0) claim = `Negative headline signal for ${ticker}: ${title}`;
    else claim = `Neutral headline for ${ticker}: ${title}`;
    claims.push({ claim, evidence_title: title });
  }
  let summary;
  if (!claims.length) summary = `No usable headlines provided for ${ticker}.`;
  else if (score > 0) summary = `${ticker}: net positive headline tone (${claims.length} stories).`;
  else if (score < 0) summary = `${ticker}: net negative headline tone (${claims.length} stories).`;
  else summary = `${ticker}: mixed/neutral headline tone (${claims.length} stories).`;
  return {
    ticker,
    claims,
    summary,
    tone_score: score,
  };
}

function handleCompareTickerAnalyses(args) {
  const a = args.analysis_a && typeof args.analysis_a === "object" ? args.analysis_a : {};
  const b = args.analysis_b && typeof args.analysis_b === "object" ? args.analysis_b : {};
  const ta = String(a.ticker || "A").toUpperCase();
  const tb = String(b.ticker || "B").toUpperCase();
  const sa = Number(a.tone_score || 0);
  const sb = Number(b.tone_score || 0);

  const stance = (score) => {
    if (score > 0) return "constructive";
    if (score < 0) return "cautious";
    return "neutral";
  };

  let evidenceA = (a.claims || [])
    .filter((c) => c && typeof c === "object")
    .map((c) => c.evidence_title)
    .filter(Boolean);
  let evidenceB = (b.claims || [])
    .filter((c) => c && typeof c === "object")
    .map((c) => c.evidence_title)
    .filter(Boolean);

  let preferred = null;
  if (sa > sb) preferred = ta;
  else if (sb > sa) preferred = tb;

  const rationaleParts = [
    `${ta} tone_score=${sa} (${stance(sa)}); ${tb} tone_score=${sb} (${stance(sb)}).`,
  ];
  if (preferred) {
    rationaleParts.push(`${preferred} is the better option on headline tone alone.`);
  } else {
    rationaleParts.push("No clear preferred ticker on headline tone.");
  }

  return {
    ticker1: { ticker: ta, recommendation: stance(sa), evidence: evidenceA },
    ticker2: { ticker: tb, recommendation: stance(sb), evidence: evidenceB },
    preferred_ticker: preferred,
    rationale: rationaleParts.join(" "),
  };
}

function ollamaMetrics(data) {
  const prompt = Number(data.prompt_eval_count || 0);
  const completion = Number(data.eval_count || 0);
  return {
    success: true,
    tokens: { total: prompt + completion, input: prompt, output: completion },
  };
}

async function ollamaChat(model, messages, tools) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  const payload = { model, stream: false, messages };
  if (tools && tools.length) payload.tools = tools;

  let res;
  try {
    res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(120000),
    });
  } catch (exc) {
    throw new Error(
      `Ollama request failed (${host}, model=${model}): ${exc.message || exc}. Is the Ollama daemon running?`
    );
  }

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(
      `Ollama request failed (${host}, model=${model}): HTTP ${res.status} ${detail}. ` +
        `Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
  return res.json();
}

function anthropicMetrics(response) {
  const usage = response.usage || {};
  const input = Number(usage.input_tokens || 0);
  const output = Number(usage.output_tokens || 0);
  return {
    success: true,
    tokens: { total: input + output, input, output },
  };
}

function anthropicText(response) {
  const parts = [];
  for (const block of response.content || []) {
    if (block.type === "text") parts.push(String(block.text || ""));
  }
  return parts.join("");
}

async function anthropicChat(apiKey, model, system, chat, tools) {
  const body = {
    model,
    max_tokens: 1024,
    messages: chat,
  };
  if (system) body.system = system;
  if (tools && tools.length) body.tools = tools;

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(120000),
  });
  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`Anthropic HTTP ${res.status}: ${errBody.slice(0, 300)}`);
  }
  return res.json();
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

async function* generateStream(persona, tickerResults) {
  const storiesText = storiesAsPromptText(tickerResults);
  const started = performance.now();
  const metrics = emptyMetrics();
  const inputSections = promptDisplaySections(storiesText);

  let config;
  try {
    config = await evaluateCompletion(persona, storiesText);
  } catch (exc) {
    yield {
      type: "meta",
      persona: { ...persona },
      input: storiesText,
      inputSections,
      provider: "anthropic",
      model: `${defaultAnthropicModel()} (code baseline)`,
      mode: "baseline-fallback",
      configKey: configKey(),
      fallback: true,
      stories: tickerResults || [],
    };
    yield {
      type: "status",
      message: `LaunchDarkly evaluation failed (${exc.message || exc}); using code baseline.`,
    };
    yield {
      type: "error",
      message:
        "Tool loop requires a live AgentControl config. " +
        `Provision with rest/create-tools.sh && rest/create-config.sh. (${exc.message || exc})`,
    };
    metrics.finish_reason = "error";
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  if (!config.enabled) {
    yield {
      type: "meta",
      persona: { ...persona },
      input: storiesText,
      inputSections,
      provider: "anthropic",
      model: `${defaultAnthropicModel()} (code baseline)`,
      mode: "baseline-fallback",
      configKey: configKey(),
      fallback: true,
      stories: tickerResults || [],
    };
    yield {
      type: "status",
      message: `AgentControl config '${configKey()}' is off; tools path disabled.`,
    };
    yield {
      type: "error",
      message: "Enable the AgentControl config and attach Library tools to generate.",
    };
    metrics.finish_reason = "error";
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  const ldModel =
    (config.model && config.model.name) || defaultAnthropicModel();
  const [provider, modelName] = personaModelName(persona, ldModel);

  const messages = messagesAsDicts(config);
  const anthropicTools = ldToolsToAnthropic(config);
  const openaiTools = ldToolsToOpenai(config);
  const toolNames = anthropicTools.map((t) => t.name);
  const tracker = config.createTracker();

  yield {
    type: "meta",
    persona: { ...persona },
    input: userMessageText(messages) || storiesText,
    inputSections,
    provider,
    model: modelName,
    mode: "launchdarkly",
    configKey: configKey(),
    fallback: false,
    stories: tickerResults || [],
    tools: toolNames,
    tracked: true,
  };

  if (!toolNames.length) {
    yield {
      type: "status",
      message: "No tools attached on this variation. Run rest/attach-tools.sh.",
    };
  }

  let system = "";
  const chat = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      system = system ? `${system}\n\n${msg.content}` : msg.content;
    } else {
      chat.push({ role: msg.role, content: msg.content });
    }
  }

  let finalText = "";
  let toolCallIndex = 0;

  try {
    if (provider === "ollama") {
      const ollamaMessages = [];
      const ollamaSystem = system
        ? `${system}\n\n${OLLAMA_TOOL_SUFFIX}`.trim()
        : OLLAMA_TOOL_SUFFIX;
      if (ollamaSystem) ollamaMessages.push({ role: "system", content: ollamaSystem });
      ollamaMessages.push(...chat);

      const analyzeResults = [];
      const calledTools = [];
      let nudgedForTools = false;
      let hitMaxSteps = true;

      for (let step = 0; step < MAX_TOOL_STEPS; step += 1) {
        const data = await tracker.trackMetricsOf(ollamaMetrics, () =>
          ollamaChat(modelName, ollamaMessages, openaiTools)
        );
        metrics.prompt_tokens =
          (metrics.prompt_tokens || 0) + Number(data.prompt_eval_count || 0);
        metrics.completion_tokens =
          (metrics.completion_tokens || 0) + Number(data.eval_count || 0);
        metrics.total_tokens = (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);

        const message = data.message || {};
        const toolCalls = message.tool_calls || [];
        const content = String(message.content || "");

        if (!toolCalls.length) {
          if (
            !nudgedForTools &&
            toolNames.length &&
            !analyzeResults.length &&
            step < MAX_TOOL_STEPS - 1
          ) {
            nudgedForTools = true;
            yield {
              type: "status",
              message: `${persona.name} skipped tools on the first turn — nudging once to run analyze → analyze → compare.`,
            };
            ollamaMessages.push(message);
            ollamaMessages.push({
              role: "user",
              content:
                "Stop writing the briefing. Call tools now: " +
                `${TOOL_ANALYZE} once per ticker, then ${TOOL_COMPARE} with the exact analyze JSON results, ` +
                "then write the briefing.",
            });
            continue;
          }
          finalText = content;
          hitMaxSteps = false;
          break;
        }

        ollamaMessages.push(message);
        for (const call of sortOllamaToolCalls(
          toolCalls.filter((c) => c && typeof c === "object")
        )) {
          const fn = call.function;
          if (!fn || typeof fn !== "object") continue;
          const name = String(fn.name || "");
          let rawInput = fn.arguments;
          if (typeof rawInput === "string") {
            try {
              rawInput = JSON.parse(rawInput);
            } catch {
              rawInput = {};
            }
          }
          if (!rawInput || typeof rawInput !== "object") rawInput = {};

          if (name === TOOL_COMPARE) {
            const [normalized, rewritten] = normalizeCompareArgs(rawInput, analyzeResults);
            rawInput = normalized;
            if (rewritten) {
              yield {
                type: "status",
                message:
                  "Rewrote compare args from prior analyze results (local model invented or parallel-called compare).",
              };
            }
          }

          const result = dispatchTool(name, rawInput);
          tracker.trackToolCall(name);
          calledTools.push(name);
          if (name === TOOL_ANALYZE && looksLikeAnalyzeResult(result)) {
            analyzeResults.push(result);
          }
          toolCallIndex += 1;
          yield {
            type: "tool",
            name,
            args: rawInput,
            result,
            callIndex: toolCallIndex,
            round: step + 1,
          };
          ollamaMessages.push({
            role: "tool",
            content: JSON.stringify(result),
          });
        }
      }

      if (hitMaxSteps) {
        yield {
          type: "status",
          message: `Hit MAX_TOOL_STEPS=${MAX_TOOL_STEPS}; using last model text if any.`,
        };
        finalText = finalText || "(No final text after tool loop.)";
      }

      if (
        !calledTools.includes(TOOL_COMPARE) &&
        analyzeResults.length >= 2 &&
        toolNames.length
      ) {
        yield {
          type: "status",
          message: `${persona.name} skipped compare-ticker-analyses — running it from prior analyze results, then asking for a final briefing.`,
        };
        const compareArgs = {
          analysis_a: analyzeResults[analyzeResults.length - 2],
          analysis_b: analyzeResults[analyzeResults.length - 1],
        };
        const result = dispatchTool(TOOL_COMPARE, compareArgs);
        tracker.trackToolCall(TOOL_COMPARE);
        toolCallIndex += 1;
        yield {
          type: "tool",
          name: TOOL_COMPARE,
          args: compareArgs,
          result,
          callIndex: toolCallIndex,
          round: "guardrail",
        };
        ollamaMessages.push({
          role: "user",
          content:
            `${TOOL_COMPARE} returned:\n${JSON.stringify(result)}\n\n` +
            "Write the short equity briefing now using ONLY the tool results (analyze + compare). Cite evidence titles.",
        });
        try {
          const data = await tracker.trackMetricsOf(ollamaMetrics, () =>
            ollamaChat(modelName, ollamaMessages, [])
          );
          metrics.prompt_tokens =
            (metrics.prompt_tokens || 0) + Number(data.prompt_eval_count || 0);
          metrics.completion_tokens =
            (metrics.completion_tokens || 0) + Number(data.eval_count || 0);
          metrics.total_tokens =
            (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);
          const brief = String((data.message || {}).content || "");
          if (brief) finalText = brief;
        } catch (exc) {
          yield {
            type: "status",
            message: `Post-compare briefing call failed: ${exc.message || exc}`,
          };
        }
      }
    } else {
      const apiKey = String(process.env.ANTHROPIC_API_KEY || "").trim();
      if (!apiKey) {
        yield {
          type: "error",
          message:
            "ANTHROPIC_API_KEY is required for Analyst Claude. Switch to Analyst Llama or Analyst Gwen for local Ollama, or export your Claude key.",
        };
        metrics.finish_reason = "error";
        metrics.latency_ms = Math.round(performance.now() - started);
        yield { type: "metrics", metrics };
        yield { type: "done" };
        return;
      }

      let hitMaxSteps = true;
      for (let step = 0; step < MAX_TOOL_STEPS; step += 1) {
        const response = await tracker.trackMetricsOf(anthropicMetrics, () =>
          anthropicChat(apiKey, modelName, system, chat, anthropicTools)
        );
        const stop = response.stop_reason;
        const usage = response.usage || {};
        metrics.prompt_tokens =
          (metrics.prompt_tokens || 0) + Number(usage.input_tokens || 0);
        metrics.completion_tokens =
          (metrics.completion_tokens || 0) + Number(usage.output_tokens || 0);
        metrics.total_tokens =
          (metrics.prompt_tokens || 0) + (metrics.completion_tokens || 0);

        if (stop !== "tool_use") {
          finalText = anthropicText(response);
          hitMaxSteps = false;
          break;
        }

        const assistantContent = [];
        const toolResults = [];
        for (const block of response.content || []) {
          const btype = block.type;
          if (btype === "text") {
            assistantContent.push({ type: "text", text: block.text || "" });
          } else if (btype === "tool_use") {
            const name = String(block.name || "");
            const toolId = String(block.id || "");
            let rawInput = block.input || {};
            if (!rawInput || typeof rawInput !== "object") rawInput = {};
            const result = dispatchTool(name, rawInput);
            tracker.trackToolCall(name);
            toolCallIndex += 1;
            yield {
              type: "tool",
              name,
              args: rawInput,
              result,
              callIndex: toolCallIndex,
              round: step + 1,
            };
            assistantContent.push({
              type: "tool_use",
              id: toolId,
              name,
              input: rawInput,
            });
            toolResults.push({
              type: "tool_result",
              tool_use_id: toolId,
              content: JSON.stringify(result),
            });
          }
        }
        chat.push({ role: "assistant", content: assistantContent });
        chat.push({ role: "user", content: toolResults });
      }

      if (hitMaxSteps) {
        yield {
          type: "status",
          message: `Hit MAX_TOOL_STEPS=${MAX_TOOL_STEPS}; using last model text if any.`,
        };
        finalText = finalText || "(No final text after tool loop.)";
      }
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    metrics.finish_reason = "error";
    metrics.latency_ms = Math.round(performance.now() - started);
    yield { type: "metrics", metrics };
    yield { type: "done" };
    return;
  }

  yield* chunkYield(finalText, metrics, started);
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
};
