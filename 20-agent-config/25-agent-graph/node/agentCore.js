/**
 * agentCore.js — domain logic for 25-agent-graph (no HTTP here).
 *
 * =============================================================================
 * HOW TO READ THIS FILE
 * =============================================================================
 *
 * Equity briefing UI with LaunchDarkly **Agent Graphs**:
 *
 *   1. Data          Charlie / Amelia / Toby + humor easter egg
 *   2. LaunchDarkly  agentGraph + agentConfig (mode=agent instructions)
 *   3. Providers     Local Ollama per node (LD does not call the model)
 *   4. Generation    assess → specialist → (optional scorers) → finalize
 *
 * LaunchDarkly insertion point (read this first):
 *   generateStream() → aiClient.agentGraph(...) then aiClient.agentConfig(...) per node
 *   Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
 *   Keywords: AgentControl · Agent graphs · Agents · Library tools · trackToolCall
 *
 * Scorers (questions gap/ground, joke corny) are app-invoked for Trace — scores appear
 * in the tool *name* (e.g. score-question-gap:0.82); they do not change specialist text.
 *
 * Routing: after assess, the chosen specialist (and later finalize) must match an
 * **outgoing edge** on the evaluated Agent Graph. Invalid edges → redirect to report
 * (or fail) and record handoff/redirect metrics on the graph tracker.
 *
 * Why manual walk (not an automatic graph runner):
 *   Classroom Trace needs a visible assess → specialist → finalize path with Ollama —
 *   so we evaluate the graph + each node via the AI SDK, invoke Ollama ourselves, and
 *   validate handoffs against graph edges (AgentGraphDefinition.getNode(...).getEdges()).
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

const DEFAULT_GRAPH_KEY = "equity-briefing-graph";
const DEFAULT_NODE_ASSESS = "equity-briefing-graph-assess";
const DEFAULT_NODE_REPORT = "equity-briefing-graph-report";
const DEFAULT_NODE_QUESTIONS = "equity-briefing-graph-questions";
const DEFAULT_NODE_GOOD = "equity-briefing-graph-good";
const DEFAULT_NODE_JOKE = "equity-briefing-graph-joke";
const DEFAULT_NODE_FINALIZE = "equity-briefing-graph-finalize";
const DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
// Joke path: higher temperature for more variety (not "never repeat").
const DEFAULT_JOKE_TEMPERATURE = 0.95;
const DEFAULT_CORNY_HIGH = 0.8;
const DEFAULT_CORNY_LOW = 0.2;

const TOOL_QUESTION_GAP = "score-question-gap";
const TOOL_JOKE_CORNY = "score-joke-corny";

// Soft angle hints — nudge variety without banning prior jokes.
const JOKE_ANGLE_HINTS = [
  "bulls vs bears",
  "earnings season nerves",
  "index funds vs stock picking",
  "coffee and candlesticks",
  "diversification as a lifestyle",
  "the eternally loading chart",
  "hot takes cooling overnight",
  "FOMO meeting patience",
];

const VALID_SPECIALISTS = new Set(["report", "questions", "good", "joke"]);
const ACTIONS_NEEDING_STORIES = new Set(["report", "questions", "good"]);

// Humor easter egg — app code only (not an LLM message).
const HUMOR_LEVEL = {
  "conservative-charlie": 25,
  "anonymous-amelia": 50,
  "thoughtless-toby": 90,
};

/** Selectable demo identity — also the LaunchDarkly user context. */
const PERSONAS = [
  { id: "conservative-charlie", name: "Conservative Charlie", profile: "conservative", anonymous: false },
  { id: "anonymous-amelia", name: "Anonymous Amelia", profile: "anonymous", anonymous: true },
  { id: "thoughtless-toby", name: "Thoughtless Toby", profile: "risk-taker", anonymous: false },
];

const NODE_DEFAULTS = {
  assess: DEFAULT_NODE_ASSESS,
  report: DEFAULT_NODE_REPORT,
  questions: DEFAULT_NODE_QUESTIONS,
  good: DEFAULT_NODE_GOOD,
  joke: DEFAULT_NODE_JOKE,
  finalize: DEFAULT_NODE_FINALIZE,
};

const NODE_ENV_MAP = {
  assess: "LD_NODE_ASSESS",
  report: "LD_NODE_REPORT",
  questions: "LD_NODE_QUESTIONS",
  good: "LD_NODE_GOOD",
  joke: "LD_NODE_JOKE",
  finalize: "LD_NODE_FINALIZE",
};

const INSTRUCTIONS_FILES = {
  assess: "assess-instructions.txt",
  report: "report-baseline-instructions.txt",
  questions: "questions-instructions.txt",
  good: "good-instructions.txt",
  joke: "joke-instructions.txt",
  finalize: "finalize-instructions.txt",
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

function graphKey() {
  return String(process.env.LD_GRAPH_KEY || DEFAULT_GRAPH_KEY).trim() || DEFAULT_GRAPH_KEY;
}

function nodeKey(role) {
  const envName = NODE_ENV_MAP[role];
  if (envName) {
    const raw = String(process.env[envName] || "").trim();
    if (raw) return raw;
  }
  return NODE_DEFAULTS[role];
}

/** Map a graph config key back to a specialist/role name. */
function roleFromNodeKey(configKey) {
  for (const role of ["assess", "report", "questions", "good", "joke", "finalize"]) {
    if (configKey === nodeKey(role)) return role;
  }
  const marker = "equity-briefing-graph-";
  if (configKey.startsWith(marker)) {
    const suffix = configKey.slice(marker.length);
    if (VALID_SPECIALISTS.has(suffix) || suffix === "assess" || suffix === "finalize") {
      return suffix;
    }
  }
  return null;
}

/**
 * Return target config keys for edges leaving sourceKey (empty if unavailable).
 * LaunchDarkly: AgentGraphDefinition.getNode(key).getEdges() — each edge's
 * `key` field is the target agent config key.
 */
function graphOutgoingTargets(graph, sourceKey) {
  if (!graph || !graph.enabled || typeof graph.getNode !== "function") return [];
  const node = graph.getNode(sourceKey);
  if (!node || typeof node.getEdges !== "function") return [];
  const out = [];
  for (const edge of node.getEdges() || []) {
    const target = (edge && edge.key) || "";
    if (target) out.push(String(target));
  }
  return out;
}

/**
 * Validate preferred specialist against assess → * edges on the LD graph.
 *
 * Returns [specialistRole, note, edgeValidated].
 * If the graph is disabled, keeps preferred and sets edgeValidated=false.
 */
function resolveSpecialistAgainstEdges(graph, preferred, graphTracker) {
  preferred = VALID_SPECIALISTS.has(preferred) ? preferred : "report";
  const assessKey = nodeKey("assess");
  const preferredKey = nodeKey(preferred);

  if (!graph || !graph.enabled) {
    return [preferred, "graph disabled — skip edge validation", false];
  }

  const children = graphOutgoingTargets(graph, assessKey);
  if (!children.length) {
    return [preferred, "assess has no outgoing edges — using preferred", false];
  }

  if (children.includes(preferredKey)) {
    return [preferred, `edge ok: assess → ${preferred}`, true];
  }

  // Invalid handoff — prefer report if that edge exists, else first child.
  const reportKey = nodeKey("report");
  try {
    graphTracker.trackHandoffFailure(assessKey, preferredKey);
  } catch (_) {
    /* best-effort */
  }

  if (children.includes(reportKey)) {
    try {
      graphTracker.trackRedirect(assessKey, reportKey);
    } catch (_) {
      /* best-effort */
    }
    return ["report", `no edge assess → ${preferred}; redirected to report`, true];
  }

  const fallbackKey = children[0];
  let fallbackRole = roleFromNodeKey(fallbackKey) || "report";
  if (!VALID_SPECIALISTS.has(fallbackRole)) fallbackRole = "report";
  try {
    graphTracker.trackRedirect(assessKey, fallbackKey);
  } catch (_) {
    /* best-effort */
  }
  return [fallbackRole, `no edge assess → ${preferred}; redirected to ${fallbackRole}`, true];
}

/** Check specialist → finalize edge when the graph is enabled. */
function finalizeEdgeOk(graph, specialistKey) {
  const finalizeKey = nodeKey("finalize");
  if (!graph || !graph.enabled) {
    return [true, "graph disabled — skip finalize edge check"];
  }
  const children = graphOutgoingTargets(graph, specialistKey);
  if (children.includes(finalizeKey)) {
    return [true, `edge ok: ${specialistKey} → finalize`];
  }
  return [false, `no edge ${specialistKey} → finalize`];
}

function defaultOllamaModel() {
  return String(process.env.OLLAMA_MODEL || DEFAULT_OLLAMA_MODEL).trim() || DEFAULT_OLLAMA_MODEL;
}

function jokeTemperature() {
  const raw = String(process.env.JOKE_TEMPERATURE || "").trim();
  if (!raw) return DEFAULT_JOKE_TEMPERATURE;
  const n = Number(raw);
  if (!Number.isFinite(n)) return DEFAULT_JOKE_TEMPERATURE;
  return Math.max(0, Math.min(1.5, n));
}

function cornyHighThreshold() {
  const raw = String(process.env.JOKE_CORNY_HIGH || "").trim();
  if (!raw) return DEFAULT_CORNY_HIGH;
  const n = Number(raw);
  return Number.isFinite(n) ? n : DEFAULT_CORNY_HIGH;
}

function cornyLowThreshold() {
  const raw = String(process.env.JOKE_CORNY_LOW || "").trim();
  if (!raw) return DEFAULT_CORNY_LOW;
  const n = Number(raw);
  return Number.isFinite(n) ? n : DEFAULT_CORNY_LOW;
}

function humorLevelFor(persona) {
  return HUMOR_LEVEL[persona.id] != null ? HUMOR_LEVEL[persona.id] : 50;
}

function formatStories(tickerResults) {
  if (!tickerResults || !tickerResults.length) return CANNED_STORIES;
  return formatStoriesForPrompt(tickerResults);
}

function loadQuestionsList() {
  const filePath = path.join(MESSAGES_DIR, "questions.txt");
  let raw;
  try {
    raw = fs.readFileSync(filePath, "utf8");
  } catch (exc) {
    throw new Error(`Could not read questions list ${filePath}: ${exc.message || exc}`);
  }
  const lines = [];
  for (const rawLine of raw.split("\n")) {
    const s = rawLine.trim();
    if (!s || s.startsWith("#")) continue;
    lines.push(s);
  }
  return lines.map((q) => `- ${q}`).join("\n");
}

function readMessageFile(name) {
  const filePath = path.join(MESSAGES_DIR, name);
  try {
    return fs.readFileSync(filePath, "utf8");
  } catch (exc) {
    throw new Error(`Could not read message file ${filePath}: ${exc.message || exc}`);
  }
}

// ---------------------------------------------------------------------------
// LaunchDarkly
// ---------------------------------------------------------------------------

/**
 * Initialize the LaunchDarkly server SDK + AI client once at startup.
 * LaunchDarkly: base client (flags/targeting) + initAi() wraps it for Agent Configs/Graphs.
 * https://launchdarkly.com/docs/sdk/ai/node-js
 */
async function initLaunchDarkly() {
  if (aiClient) return;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error(
      "LD_SDK_KEY is required. Export a server-side SDK key for the environment that targets equity-briefing-graph."
    );
  }
  ldClient = LaunchDarkly.init(sdkKey);
  await ldClient.waitForInitialization({ timeout: 5 });
  aiClient = initAi(ldClient);
}

/**
 * Build the LaunchDarkly context. Anonymous Amelia sets anonymous=true so she
 * evaluates via fallthrough targeting instead of persona-key rules.
 * LaunchDarkly: contexts — https://launchdarkly.com/docs/home/contexts
 */
function buildContext(persona, action) {
  const ctx = {
    kind: "user",
    key: persona.id,
    name: persona.name,
    action,
    profile: persona.profile,
  };
  if (persona.anonymous) {
    ctx.anonymous = true;
  }
  return ctx;
}

function agentDefault(instructionsFile) {
  return {
    enabled: true,
    model: { name: defaultOllamaModel(), parameters: { temperature: 0 } },
    provider: { name: "Custom" },
    instructions: readMessageFile(instructionsFile).trim(),
  };
}

/**
 * Evaluate one agent-mode node.
 * LaunchDarkly: aiClient.agentConfig(key, context, defaultValue, variables) —
 * https://launchdarkly.com/docs/home/agentcontrol/agents
 */
async function evaluateAgent(role, context, variables) {
  return aiClient.agentConfig(nodeKey(role), context, agentDefault(INSTRUCTIONS_FILES[role]), variables || {});
}

function resolveRuntime(config) {
  const model = (config.model && config.model.name) || "";
  const providerName = ((config.provider && config.provider.name) || "").trim().toLowerCase();
  if (providerName === "custom" || providerName === "ollama" || model.includes(":")) {
    return ["ollama", model || defaultOllamaModel()];
  }
  if (!model) return ["ollama", defaultOllamaModel()];
  return ["ollama", model];
}

function clip(text, maxLen = 55) {
  const s = String(text || "").replace(/\s+/g, " ").trim();
  if (s.length <= maxLen) return s;
  return s.slice(0, Math.max(0, maxLen - 1)) + "…";
}

function parseJsonObject(raw) {
  const text = String(raw || "").trim();
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;
  try {
    const data = JSON.parse(match[0]);
    return data && typeof data === "object" ? data : null;
  } catch (_) {
    return null;
  }
}

function clamp01(value, def = 0.5) {
  const n = Number(value);
  if (!Number.isFinite(n)) return def;
  return Math.max(0, Math.min(1, n));
}

/** Pull candidate questions from specialist text (for scoring only). */
function extractQuestionsFromDraft(draft) {
  const out = [];
  for (const rawLine of String(draft || "").split("\n")) {
    let s = rawLine.trim();
    if (!s) continue;
    s = s.replace(/^[-*•]+\s*/, "");
    s = s.replace(/^\d+[.)]\s*/, "");
    if (!s.includes("?")) continue;
    if (s.length < 12) continue;
    out.push(s);
    if (out.length >= 5) break;
  }
  return out;
}

/**
 * App-side scorer: gap + ground in [0,1]. Does not change specialist output.
 *
 * LaunchDarkly: Library tool key score-question-gap (attached for Monitoring).
 * https://launchdarkly.com/docs/home/agentcontrol/tools
 */
async function scoreQuestionGap(question, headlines, model) {
  const user =
    "Score this follow-up question against the headlines.\n" +
    'Return JSON only: {"gap":0.0,"ground":0.0}\n' +
    "- gap: how poorly the headlines answer it (1.0 = large information gap).\n" +
    "- ground: how well the question fits this headline domain (1.0 = on-topic).\n" +
    "Use decimals in [0,1].\n\n" +
    `QUESTION:\n${question}\n\n` +
    `HEADLINES:\n${headlines}\n`;
  const raw = await ollamaComplete(
    model,
    [
      { role: "system", content: "You are a strict scoring tool. Output JSON only." },
      { role: "user", content: user },
    ],
    0.0
  );
  const data = parseJsonObject(raw) || {};
  return { gap: clamp01(data.gap, 0.5), ground: clamp01(data.ground, 0.5) };
}

/** App-side easter-egg scorer: corniness in [0,1]. */
async function scoreJokeCorny(joke, model) {
  const user =
    "Score how corny this joke is.\n" +
    'Return JSON only: {"corny":0.0}\n' +
    "0.0 = dry/subtle; 1.0 = very corny dad-joke energy. Decimal in [0,1].\n\n" +
    `JOKE:\n${joke}\n`;
  const raw = await ollamaComplete(
    model,
    [
      { role: "system", content: "You are a whimsical scoring tool. Output JSON only." },
      { role: "user", content: user },
    ],
    0.0
  );
  const data = parseJsonObject(raw) || {};
  return clamp01(data.corny, 0.5);
}

/** Trace display: score lives in the tool name (teaching visibility). */
function formatToolNameWithScore(base, score) {
  return `${base}:${Number(score).toFixed(2)}`;
}

/** Return [specialist, reason]. Invalid/unknown → report. */
function parseAssessJson(raw, actionHint) {
  let specialist = VALID_SPECIALISTS.has(actionHint) ? actionHint : "report";
  let reason = "fallback";
  const text = String(raw || "").trim();
  const match = text.match(/\{[\s\S]*\}/);
  if (match) {
    try {
      const data = JSON.parse(match[0]);
      const cand = String((data && data.specialist) || "").trim().toLowerCase();
      if (VALID_SPECIALISTS.has(cand)) specialist = cand;
      reason = String((data && data.reason) || reason).trim() || reason;
      return [specialist, reason];
    } catch (_) {
      // fall through to hint-based fallback below
    }
  }
  if (VALID_SPECIALISTS.has(actionHint)) {
    return [actionHint, "assess parse failed; used UI action hint"];
  }
  return ["report", "assess parse failed; fall through to report"];
}

/** Non-streaming completion (assess / buffer specialist). */
async function ollamaComplete(model, messages, temperature = 0.0) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  let res;
  try {
    res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, stream: false, options: { temperature } }),
    });
  } catch (exc) {
    throw new Error(
      `Ollama request failed (${exc.message || exc}). Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `Ollama request failed (HTTP ${res.status} ${body}). Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
  const data = await res.json();
  const message = data.message || {};
  return String(message.content || "");
}

async function* ollamaStream(model, messages, temperature = 0.0) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  let res;
  try {
    res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, stream: true, options: { temperature } }),
    });
  } catch (exc) {
    throw new Error(
      `Ollama stream failed (${exc.message || exc}). Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
  if (!res.ok || !res.body) {
    const body = res ? await res.text().catch(() => "") : "";
    throw new Error(
      `Ollama stream failed (HTTP ${res ? res.status : "?"} ${body}). Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let chunk;
        try {
          chunk = JSON.parse(trimmed);
        } catch (_) {
          continue;
        }
        const msg = chunk.message || {};
        const text = msg.content || "";
        if (text) yield text;
        if (chunk.done) return;
      }
    }
  } catch (exc) {
    throw new Error(
      `Ollama stream failed (${exc.message || exc}). Is Ollama running, and does \`ollama list\` include ${model}?`
    );
  }
}

function messagesForNode(instructions, userContent) {
  return [
    { role: "system", content: instructions || "You are a helpful assistant." },
    { role: "user", content: userContent },
  ];
}

function safeTrackInvocationFailure(tracker) {
  try {
    tracker.trackInvocationFailure();
  } catch (_) {
    /* best-effort */
  }
}

/**
 * Run assess → specialist → finalize.
 *
 * SSE event types:
 *   run, status, info, assess, route, specialist, tool, model, finalize, token,
 *   metrics, error, done
 *
 * LaunchDarkly insertion points:
 *   - aiClient.agentGraph(graphKey(), context) — topology + graph.createTracker()
 *   - aiClient.agentConfig(nodeKey(role), context, defaultValue, variables) — per node
 *   - node.getEdges() — validate assess → specialist and specialist → finalize handoffs
 *   - nodeTracker.trackToolCall(...) — Library tools for the scorer calls
 * https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
 */
async function* generateStream(persona, action, tickerResults) {
  action = String(action || "report").trim().toLowerCase();
  if (!VALID_SPECIALISTS.has(action)) action = "report";

  const storiesText = formatStories(tickerResults);
  const hasRealStories = Boolean(tickerResults && tickerResults.length) && storiesText !== CANNED_STORIES;

  if (ACTIONS_NEEDING_STORIES.has(action) && !hasRealStories) {
    yield { type: "error", message: "Load stories first (Get Stories), then try this action again." };
    yield { type: "done" };
    return;
  }

  const started = Date.now();
  const metrics = emptyMetrics();
  const context = buildContext(persona, action);

  // --- Graph evaluate (topology + tracker) ---------------------------------
  // LaunchDarkly: agentGraph — see docs link in module prelude.
  let graph;
  try {
    graph = await aiClient.agentGraph(graphKey(), context);
  } catch (exc) {
    yield { type: "error", message: `LaunchDarkly agentGraph failed: ${exc.message || exc}` };
    yield { type: "done" };
    return;
  }

  const graphTracker = graph.createTracker();
  const graphEnabled = Boolean(graph.enabled);

  yield {
    type: "run",
    action,
    personaId: persona.id,
    personaName: persona.name,
    graphKey: graphKey(),
    graphEnabled,
  };
  yield {
    type: "status",
    message:
      `Graph ${graphKey()} ` +
      (graphEnabled ? "enabled" : "disabled/missing — using node configs + local walk"),
  };

  const runPath = [nodeKey("assess")];

  // --- Humor easter egg (joke path only) -----------------------------------
  if (action === "joke") {
    const level = humorLevelFor(persona);
    yield { type: "info", message: `Setting humor level to ${level}%`, kind: "humor" };
  }

  // --- Step 1: assess ------------------------------------------------------
  yield { type: "status", message: "assess — choosing specialist…" };
  let assessCfg;
  try {
    assessCfg = await evaluateAgent("assess", context, {
      action,
      stories: hasRealStories ? storiesText : "(none)",
    });
  } catch (exc) {
    yield { type: "error", message: `assess agentConfig failed: ${exc.message || exc}` };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  const [, assessModel] = resolveRuntime(assessCfg);
  const assessUser =
    `UI action hint: ${action}\n` +
    `Headlines present: ${hasRealStories ? "yes" : "no"}\n\n` +
    `HEADLINES:\n${hasRealStories ? storiesText : "(none)"}\n\n` +
    "Return JSON only.";

  let assessRaw;
  try {
    assessRaw = await ollamaComplete(assessModel, messagesForNode(assessCfg.instructions || "", assessUser));
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  let [specialist, reason] = parseAssessJson(assessRaw, action);
  // Prefer UI action when valid (teaching: button intent wins if assess drifts).
  if (VALID_SPECIALISTS.has(action) && specialist !== action) {
    reason = `${reason} (UI hint=${action}; using hint)`;
    specialist = action;
  }

  // LaunchDarkly: validate assess → specialist against graph edges.
  const [resolvedSpecialist, edgeNote, edgeOk] = resolveSpecialistAgainstEdges(graph, specialist, graphTracker);
  specialist = resolvedSpecialist;
  if (edgeNote) {
    if (!reason.includes(edgeNote)) reason = `${reason}; ${edgeNote}`;
    yield { type: "info", message: edgeNote, kind: "edge", validated: edgeOk };
  }

  const specialistKey = nodeKey(specialist);
  runPath.push(specialistKey);
  graphTracker.trackHandoffSuccess(nodeKey("assess"), specialistKey);

  yield {
    type: "assess",
    specialist,
    reason,
    clip: clip(`${specialist}: ${reason}`),
    model: assessModel,
    configKey: nodeKey("assess"),
    edgeValidated: edgeOk,
  };
  yield {
    type: "route",
    specialist,
    reason,
    message: `Selected specialist: ${specialist}`,
    edgeValidated: edgeOk,
  };

  // --- Step 2: specialist --------------------------------------------------
  yield { type: "status", message: `${specialist} — running specialist…` };
  const variables = {
    action,
    stories: hasRealStories ? storiesText : "(none)",
    specialist,
  };
  if (specialist === "questions") {
    variables.questions = loadQuestionsList();
  }

  let specCfg;
  try {
    // report uses persona targeting on the same key; other nodes are single-variation.
    specCfg = await evaluateAgent(specialist, context, variables);
  } catch (exc) {
    yield { type: "error", message: `${specialist} agentConfig failed: ${exc.message || exc}` };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  const [, specModel] = resolveRuntime(specCfg);
  const variationKey = String(specCfg.variationKey || "");

  let specUser;
  let specTemperature = 0.0;
  if (specialist === "questions") {
    specUser =
      `CANDIDATE QUESTIONS:\n${variables.questions}\n\n` +
      `HEADLINES:\n${storiesText}\n\n` +
      "Return the top 2–3 gap-priority questions with a short why each.";
  } else if (specialist === "good") {
    specUser = `HEADLINES:\n${storiesText}\n\n` + "Produce ## Good and ## Bad sections now (both required).";
  } else if (specialist === "joke") {
    const tickers = [];
    for (const row of tickerResults || []) {
      const t = String((row && row.ticker) || "").trim();
      if (t) tickers.push(t);
    }
    // Tickers / headlines are optional upside — joke works with none.
    const extras = [];
    if (tickers.length) extras.push(`Optional tickers (use lightly if you want): ${tickers.join(", ")}`);
    if (hasRealStories) {
      extras.push("Optional headlines (use lightly if you want):\n" + clip(storiesText, 400));
    }
    const angle = JOKE_ANGLE_HINTS[Math.floor(Math.random() * JOKE_ANGLE_HINTS.length)];
    extras.push(
      `Variety nudge (optional inspiration, not a script): lean toward "${angle}" ` +
        "or another fresh angle — prefer a different setup than the most common one."
    );
    const bonus = extras.length ? "\n\n" + extras.join("\n\n") : "";
    specUser =
      "Tell a short market/investing joke now. " +
      "Aim for variety across runs. Do not require tickers or headlines." +
      bonus;
    specTemperature = jokeTemperature();
    yield {
      type: "info",
      message: `Joke sampling temperature=${specTemperature.toFixed(2)}; angle hint "${angle}"`,
      kind: "joke-variety",
    };
  } else {
    specUser = `HEADLINES:\n${storiesText}\n\n` + `Produce the ${specialist} output now.`;
  }

  let specialistDraft;
  try {
    specialistDraft = await ollamaComplete(
      specModel,
      messagesForNode(specCfg.instructions || "", specUser),
      specTemperature
    );
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  yield {
    type: "specialist",
    specialist,
    clip: clip(specialistDraft),
    model: specModel,
    configKey: specialistKey,
    variationKey,
  };

  // --- Optional scorers (Trace visibility; outcomes unchanged) --------------
  // LaunchDarkly: Library tools + trackToolCall
  // https://launchdarkly.com/docs/home/agentcontrol/tools
  let nodeTracker = null;
  try {
    nodeTracker = specCfg.createTracker();
  } catch (_) {
    nodeTracker = null;
  }

  if (specialist === "questions") {
    yield { type: "status", message: "Scoring questions (gap / ground)…" };
    const questions = extractQuestionsFromDraft(specialistDraft);
    if (!questions.length) {
      yield {
        type: "info",
        message: "No questions parsed for scoring — Trace skips tool scores.",
        kind: "tool",
      };
    }
    let callIndex = 0;
    for (const q of questions) {
      const scores = await scoreQuestionGap(q, storiesText, specModel || defaultOllamaModel());
      const { gap, ground } = scores;
      // Score in the tool *name* so Trace teaches values along the way.
      const gapName = formatToolNameWithScore(TOOL_QUESTION_GAP, gap);
      const groundName = formatToolNameWithScore("score-question-ground", ground);
      callIndex += 1;
      if (nodeTracker) {
        try {
          nodeTracker.trackToolCall(TOOL_QUESTION_GAP);
        } catch (_) {
          /* best-effort */
        }
      }
      yield {
        type: "tool",
        name: gapName,
        toolKey: TOOL_QUESTION_GAP,
        score: gap,
        scores: { gap, ground },
        args: { question: q },
        result: { gap, ground },
        callIndex,
        clip: clip(q, 40),
      };
      callIndex += 1;
      yield {
        type: "tool",
        name: groundName,
        toolKey: "score-question-ground",
        score: ground,
        args: { question: q },
        result: { ground },
        callIndex,
        clip: clip(q, 40),
      };
    }
  } else if (specialist === "joke") {
    yield { type: "status", message: "Scoring joke corniness…" };
    const corny = await scoreJokeCorny(specialistDraft, specModel || defaultOllamaModel());
    const cornyName = formatToolNameWithScore(TOOL_JOKE_CORNY, corny);
    if (nodeTracker) {
      try {
        nodeTracker.trackToolCall(TOOL_JOKE_CORNY);
      } catch (_) {
        /* best-effort */
      }
    }
    yield {
      type: "tool",
      name: cornyName,
      toolKey: TOOL_JOKE_CORNY,
      score: corny,
      args: { joke: clip(specialistDraft, 120) },
      result: { corny },
      callIndex: 1,
      clip: clip(specialistDraft, 40),
    };
    const high = cornyHighThreshold();
    const low = cornyLowThreshold();
    const level = humorLevelFor(persona);
    if (corny >= high) {
      yield {
        type: "info",
        message: `Corny ${corny.toFixed(2)} ≥ ${high.toFixed(2)} — recommend lowering humor setting (currently ${level}%).`,
        kind: "humor-tip",
      };
    } else if (corny <= low) {
      yield {
        type: "info",
        message: `Corny ${corny.toFixed(2)} ≤ ${low.toFixed(2)} — recommend raising humor setting (currently ${level}%).`,
        kind: "humor-tip",
      };
    }
  }

  const finalizeKey = nodeKey("finalize");
  const [finOk, finEdgeNote] = finalizeEdgeOk(graph, specialistKey);
  yield { type: "info", message: finEdgeNote, kind: "edge", validated: finOk };
  if (!finOk) {
    try {
      graphTracker.trackHandoffFailure(specialistKey, finalizeKey);
    } catch (_) {
      /* best-effort */
    }
    yield {
      type: "error",
      message: `Graph has no edge from ${specialistKey} to ${finalizeKey}. Fix the Agent Graph topology in LaunchDarkly.`,
    };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done", specialist, action };
    return;
  }

  runPath.push(finalizeKey);
  graphTracker.trackHandoffSuccess(specialistKey, finalizeKey);

  // --- Step 3: finalize (stream to response) -------------------------------
  // Joke drafts: pass through (still evaluate finalize + track the edge).
  // Small models otherwise invent a "market briefing" after the punchline when
  // headlines are in context (often from a prior Get Stories / localStorage).
  yield { type: "status", message: "finalize — polishing…" };
  let finCfg;
  try {
    finCfg = await evaluateAgent("finalize", context, {
      action,
      specialist,
      draft: specialistDraft,
      stories:
        specialist === "joke"
          ? "(omitted for joke)"
          : hasRealStories
            ? storiesText
            : "(none)",
    });
  } catch (exc) {
    yield { type: "error", message: `finalize agentConfig failed: ${exc.message || exc}` };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  const [, finModel] = resolveRuntime(finCfg);

  yield { type: "model", provider: "ollama", model: finModel, configKey: finalizeKey, phase: "finalize" };

  const finalParts = [];
  let firstTokenAt = null;
  try {
    if (specialist === "joke") {
      yield {
        type: "info",
        message:
          "joke finalize: pass-through specialist draft (avoids small-model expansion into briefings)",
        kind: "finalize-passthrough",
      };
      const finalTextJoke = specialistDraft || "";
      const step = 48;
      for (let i = 0; i < Math.max(finalTextJoke.length, 1); i += step) {
        const chunk = finalTextJoke.slice(i, i + step);
        if (!chunk) break;
        if (firstTokenAt === null) {
          firstTokenAt = Date.now();
          metrics.ttft_ms = firstTokenAt - started;
        }
        finalParts.push(chunk);
        yield { type: "token", text: chunk };
      }
    } else {
      const finUser =
        `Original action: ${action}\n` +
        `Specialist: ${specialist}\n\n` +
        `SPECIALIST DRAFT:\n${specialistDraft}\n\n` +
        "Return the final polished text only.";
      for await (const chunk of ollamaStream(finModel, messagesForNode(finCfg.instructions || "", finUser))) {
        if (firstTokenAt === null) {
          firstTokenAt = Date.now();
          metrics.ttft_ms = firstTokenAt - started;
        }
        finalParts.push(chunk);
        yield { type: "token", text: chunk };
      }
    }
  } catch (exc) {
    yield { type: "error", message: String(exc.message || exc) };
    safeTrackInvocationFailure(graphTracker);
    yield { type: "done" };
    return;
  }

  const finalText = finalParts.join("");
  metrics.latency_ms = Date.now() - started;
  metrics.finish_reason = "stop";

  yield { type: "finalize", clip: clip(finalText), model: finModel, configKey: finalizeKey };

  graphTracker.trackPath(runPath);
  graphTracker.trackDuration(metrics.latency_ms || 0);
  graphTracker.trackInvocationSuccess();

  // Per-node success trackers (best-effort)
  try {
    assessCfg.createTracker().trackSuccess();
    if (nodeTracker) {
      nodeTracker.trackSuccess();
    } else {
      specCfg.createTracker().trackSuccess();
    }
    finCfg.createTracker().trackSuccess();
  } catch (_) {
    /* best-effort */
  }

  yield { type: "metrics", metrics };
  yield { type: "done", path: runPath, specialist, action };
}

module.exports = {
  PERSONAS,
  personaById,
  graphKey,
  nodeKey,
  initLaunchDarkly,
  generateStream,
};
