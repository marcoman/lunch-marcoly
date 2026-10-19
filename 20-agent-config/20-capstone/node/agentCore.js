/**
 * agentCore.js — capstone walk: assess → specialist → judges → tools → finalize.
 *
 * LaunchDarkly insertion (read first):
 *   generateStream() → agentGraph + agentConfig per node
 *   then judgeConfig on the specialist draft
 *   then trackToolCall for each checked tool
 *   thumbs use the specialist tracker's resumption token
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/tools
 * Keywords: AgentControl · agent graphs · Library tools · judges · feedback
 */

"use strict";

const fs = require("fs");
const path = require("path");
const LaunchDarkly = require("@launchdarkly/node-server-sdk");
const { initAi, LDFeedbackKind } = require("@launchdarkly/server-sdk-ai");

const HERE = __dirname;
const MESSAGES_DIR = path.join(HERE, "..", "rest", "messages");

const DEFAULT_GRAPH_KEY = "equity-briefing-capstone";
const NODE_DEFAULTS = {
  assess: "equity-briefing-capstone-assess",
  report: "equity-briefing-capstone-report",
  questions: "equity-briefing-capstone-questions",
  good: "equity-briefing-capstone-good",
  finalize: "equity-briefing-capstone-finalize",
};
const TOOL_ORDER = ["pig-latin", "rot13", "joke-tagline"];
const VALID_SPECIALISTS = new Set(["report", "questions", "good"]);
const HUMOR_LEVEL = {
  "conservative-charlie": 25,
  "anonymous-amelia": 50,
  "thoughtless-toby": 90,
};
const PERSONAS = [
  { id: "conservative-charlie", name: "Conservative Charlie", profile: "conservative", anonymous: false },
  { id: "anonymous-amelia", name: "Anonymous Amelia", profile: "anonymous", anonymous: true },
  { id: "thoughtless-toby", name: "Thoughtless Toby", profile: "risk-taker", anonymous: false },
];
const JOKES = {
  en: {
    "conservative-charlie": "The market can stay irrational longer than a footnote.",
    "anonymous-amelia": "Diversification is the joke that still pays rent.",
    "thoughtless-toby": "Buy high, sell higher, and call the difference research.",
  },
  es: {
    "conservative-charlie": "El mercado puede seguir irracional más que una nota al pie.",
    "anonymous-amelia": "Diversificar es el chiste que igual paga el alquiler.",
    "thoughtless-toby": "Compra caro, vende más caro, y llama investigación a la diferencia.",
  },
};

let ldClient = null;
let aiClient = null;

function personaById(personaId) {
  return PERSONAS.find((p) => p.id === personaId) || null;
}

function graphKey() {
  return String(process.env.LD_GRAPH_KEY || DEFAULT_GRAPH_KEY).trim() || DEFAULT_GRAPH_KEY;
}

function nodeKey(role) {
  const envName = {
    assess: "LD_NODE_ASSESS",
    report: "LD_NODE_REPORT",
    questions: "LD_NODE_QUESTIONS",
    good: "LD_NODE_GOOD",
    finalize: "LD_NODE_FINALIZE",
  }[role];
  const fromEnv = envName ? String(process.env[envName] || "").trim() : "";
  return fromEnv || NODE_DEFAULTS[role];
}

function judgeKey(which) {
  if (which === "fidelity") {
    return String(process.env.LD_JUDGE_FIDELITY_KEY || "equity-briefing-capstone-source-fidelity").trim();
  }
  return String(process.env.LD_JUDGE_DISCIPLINE_KEY || "equity-briefing-capstone-recommendation-discipline").trim();
}

function passThreshold() {
  const raw = String(process.env.JUDGE_PASS_THRESHOLD || "").trim();
  const value = raw ? Number(raw) : 0.65;
  return Number.isFinite(value) ? value : 0.65;
}

function defaultOllamaModel() {
  return String(process.env.OLLAMA_MODEL || "llama3.2:3b").trim() || "llama3.2:3b";
}

function readMessageFile(name) {
  return fs.readFileSync(path.join(MESSAGES_DIR, name), "utf8");
}

function clip(text, maxLen = 80) {
  const s = String(text || "").replace(/\s+/g, " ").trim();
  if (s.length <= maxLen) return s;
  return `${s.slice(0, Math.max(0, maxLen - 1))}…`;
}

async function initLaunchDarkly() {
  if (aiClient) return;
  const sdkKey = String(process.env.LD_SDK_KEY || "").trim();
  if (!sdkKey) {
    throw new Error("LD_SDK_KEY is required. Export a server-side SDK key before starting the capstone.");
  }
  ldClient = LaunchDarkly.init(sdkKey);
  await ldClient.waitForInitialization({ timeout: 5 });
  aiClient = initAi(ldClient);
}

function buildContext(persona, action, locale) {
  const ctx = {
    kind: "user",
    key: persona.id,
    name: persona.name,
    action,
    locale: locale === "es" ? "es" : "en",
    profile: persona.profile,
  };
  if (persona.anonymous) ctx.anonymous = true;
  return ctx;
}

function agentDefault(file) {
  return {
    enabled: true,
    model: { name: defaultOllamaModel(), parameters: { temperature: 0 } },
    provider: { name: "Custom" },
    instructions: readMessageFile(file).trim(),
  };
}

const INSTRUCTION_FILES = {
  assess: "assess-instructions.txt",
  report: "report-baseline-instructions.txt",
  questions: "questions-instructions.txt",
  good: "good-instructions.txt",
  finalize: "finalize-instructions.txt",
};

async function evaluateAgent(role, context, variables) {
  return aiClient.agentConfig(nodeKey(role), context, agentDefault(INSTRUCTION_FILES[role]), variables || {});
}

function resolveModel(config) {
  const name = (config && config.model && config.model.name) || "";
  return name || defaultOllamaModel();
}

/**
 * Summarize one served AgentControl config for the LD Details drawer.
 * LaunchDarkly: agent config evaluation metadata and variations.
 * https://launchdarkly.com/docs/home/agentcontrol/agents
 */
function configSummary(config, key) {
  const meta = (config && config._ldMeta) || {};
  return {
    key,
    enabled: Boolean(config && config.enabled),
    variationKey: meta.variationKey || null,
    version: meta.version ?? null,
    modelKey: meta.modelKey || null,
    provider: (config && config.provider && config.provider.name) || null,
    model: resolveModel(config),
  };
}

/** Build the Sent / Received document shown in the LD Details drawer. */
function buildLdTransaction({
  persona,
  action,
  locale,
  storiesText,
  tools,
  graph,
  specialist,
  assessCfg,
  specCfg,
  finCfg,
  judges,
  transformed,
}) {
  const graphConfig = graph && typeof graph.getConfig === "function" ? graph.getConfig() : null;
  const graphMeta = (graphConfig && graphConfig._ldMeta) || {};
  const context = buildContext(persona, action, locale);
  return {
    sent: {
      graphKey: graphKey(),
      context,
      variables: {
        action,
        locale,
        stories: storiesText,
        selectedTools: tools,
      },
      requestedPath: [
        nodeKey("assess"),
        nodeKey(specialist),
        nodeKey("finalize"),
      ],
      sdkDefault: {
        enabled: true,
        provider: "Custom",
        model: defaultOllamaModel(),
        description: "Capstone graph fallback: assess → specialist → finalize.",
      },
    },
    received: {
      graph: {
        key: graphKey(),
        enabled: Boolean(graph && graph.enabled),
        variationKey: graphMeta.variationKey || null,
        version: graphMeta.version ?? null,
      },
      route: specialist,
      path: [
        nodeKey("assess"),
        nodeKey(specialist),
        nodeKey("finalize"),
      ],
      nodes: [
        configSummary(assessCfg, nodeKey("assess")),
        configSummary(specCfg, nodeKey(specialist)),
        configSummary(finCfg, nodeKey("finalize")),
      ],
      tools,
      judges,
      transformedDraft: transformed,
    },
  };
}

function messagesForNode(instructions, userContent) {
  return [
    { role: "system", content: instructions || "You are a helpful assistant." },
    { role: "user", content: userContent },
  ];
}

async function ollamaComplete(model, messages) {
  const host = String(process.env.OLLAMA_HOST || "http://127.0.0.1:11434").replace(/\/$/, "");
  let res;
  try {
    res = await fetch(`${host}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages, stream: false, options: { temperature: 0 } }),
    });
  } catch (exc) {
    throw new Error(`Ollama request failed (${exc.message || exc}). Is Ollama running with ${model}?`);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Ollama request failed (HTTP ${res.status} ${body}).`);
  }
  const data = await res.json();
  return String((data.message && data.message.content) || "");
}

function parseAssess(raw, actionHint) {
  const match = String(raw || "").match(/\{[\s\S]*\}/);
  if (match) {
    try {
      const data = JSON.parse(match[0]);
      const cand = String((data && data.specialist) || "").trim().toLowerCase();
      const reason = String((data && data.reason) || "assess").trim() || "assess";
      if (VALID_SPECIALISTS.has(cand)) return [cand, reason];
    } catch (_) {
      /* use the hint */
    }
  }
  if (VALID_SPECIALISTS.has(actionHint)) return [actionHint, "assess parse failed; used the action"];
  return ["report", "assess parse failed; fall through to report"];
}

function outgoingTargets(graph, sourceKey) {
  if (!graph || !graph.enabled || typeof graph.getNode !== "function") return [];
  const node = graph.getNode(sourceKey);
  if (!node || typeof node.getEdges !== "function") return [];
  return (node.getEdges() || []).map((edge) => String((edge && edge.key) || "")).filter(Boolean);
}

function toPigLatin(text) {
  return String(text || "").replace(/[A-Za-z]+/g, (word) => {
    const lower = word.toLowerCase();
    let converted;
    if (/^[aeiou]/.test(lower)) converted = `${lower}yay`;
    else {
      const split = lower.match(/^([^aeiouy]+)(.*)$/);
      converted = split && split[2] ? `${split[2]}${split[1]}ay` : `${lower}ay`;
    }
    if (word[0] === word[0].toUpperCase()) {
      converted = converted[0].toUpperCase() + converted.slice(1);
    }
    return converted;
  });
}

function toRot13(text) {
  return String(text || "").replace(/[A-Za-z]/g, (ch) => {
    const base = ch <= "Z" ? 65 : 97;
    return String.fromCharCode(((ch.charCodeAt(0) - base + 13) % 26) + base);
  });
}

function applyTool(key, text, persona, locale) {
  if (key === "pig-latin") return toPigLatin(text);
  if (key === "rot13") return toRot13(text);
  const pack = JOKES[locale] || JOKES.en;
  const line = pack[persona.id] || pack["anonymous-amelia"];
  return `${String(text || "").replace(/\s+$/, "")}\n\nTagline: ${line}`;
}

/** Tell finalize exactly which transforms ran, so a small model does not invent one. */
function finalizeToolLine(tools) {
  const ran = new Set(tools);
  const lines = [
    `Pig Latin: ${ran.has("pig-latin") ? "applied — keep it" : "NOT applied — do not convert any words to Pig Latin"}.`,
    `ROT13: ${ran.has("rot13") ? "applied — the draft is already ROT13. Copy every letter. Do not decode it" : "NOT applied — do not encode any text"}.`,
    `Joke tagline: ${ran.has("joke-tagline") ? "applied — keep the Tagline line exactly as written" : "NOT applied — do not add a tagline"}.`,
  ];
  return lines.join("\n");
}

function pigLatinRatio(text) {
  const words = String(text || "").match(/[A-Za-z]{3,}/g) || [];
  if (!words.length) return 0;
  return words.filter((word) => /[a-z]ay$/i.test(word)).length / words.length;
}

const ENGLISH_WORDS = new Set(
  "the and for that this with from have are was were not but its has will can you your their they been into over after more than also about would could should which there these those them then when what where while stock stocks market shares price prices growth revenue earnings company companies investor investors today according said says".split(" ")
);

/** Share of words that are ordinary English. ROT13 text scores near zero. */
function englishScore(text) {
  const words = String(text || "").toLowerCase().match(/[a-z]{3,}/g) || [];
  if (!words.length) return 0;
  return words.filter((word) => ENGLISH_WORDS.has(word)).length / words.length;
}

function cipherRan(tools) {
  const ran = new Set(tools);
  return ran.has("rot13") || ran.has("pig-latin");
}

/**
 * Keep app-run tools authoritative. Finalize may polish, but it may not add a
 * cipher that was not checked or rewrite the tagline the tool appended.
 */
function guardFinalize(finalText, transformed, tools) {
  const ran = new Set(tools);
  const notes = [];
  let text = String(finalText || "").trim();
  if (!text) return { text: transformed, notes: ["finalize returned nothing; kept tool output"] };
  if (ran.has("rot13") && englishScore(text) - englishScore(transformed) > 0.08) {
    return { text: transformed, notes: ["finalize decoded ROT13; kept tool output"] };
  }
  if (ran.has("pig-latin") && pigLatinRatio(transformed) - pigLatinRatio(text) > 0.15) {
    return { text: transformed, notes: ["finalize removed Pig Latin; kept tool output"] };
  }
  if (!ran.has("pig-latin") && pigLatinRatio(text) - pigLatinRatio(transformed) > 0.15) {
    return { text: transformed, notes: ["finalize added Pig Latin that was not checked; kept tool output"] };
  }
  if (!ran.has("rot13") && englishScore(toRot13(text)) - englishScore(text) > 0.08) {
    return { text: transformed, notes: ["finalize added ROT13 that was not checked; kept tool output"] };
  }
  if (ran.has("joke-tagline")) {
    const tagline = (String(transformed).match(/^Tagline: .*$/m) || [])[0];
    if (tagline && !text.includes(tagline)) {
      text = `${text.replace(/\n*^Tagline:.*$/m, "").replace(/\s+$/, "")}\n\n${tagline}`;
      notes.push("finalize changed the tagline; restored the tool's tagline");
    }
  } else if (/^Tagline:/m.test(text) && !/^Tagline:/m.test(transformed)) {
    text = text.replace(/\n*^Tagline:.*$/m, "").replace(/\s+$/, "");
    notes.push("finalize added a tagline that was not checked; removed it");
  }
  return { text, notes };
}

function languageLine(locale) {
  return locale === "es" ? "Write the answer in Spanish." : "Write the answer in English.";
}

/** Cipher output must be copied. Asking for plain language makes the model decode it. */
function finalizeUser(locale, specialist, tools, transformed) {
  const lang = cipherRan(tools)
    ? "A cipher already ran. Copy the draft's wording. Do not translate it back to plain language."
    : languageLine(locale);
  return `${lang}\nSpecialist: ${specialist}\n\nTOOLS THAT RAN:\n${finalizeToolLine(tools)}\n\nDRAFT:\n${transformed}\n\nReturn the final text only.`;
}

async function ollamaJudge(model, messages) {
  const raw = await ollamaComplete(model, messages);
  const match = raw.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("Judge reply was not JSON.");
  return JSON.parse(match[0]);
}

async function runOneJudge(key, persona, locale, inputText, outputText) {
  const metricDefault = key.includes("fidelity")
    ? "$ld:ai:judge:capstone-source-fidelity"
    : "$ld:ai:judge:capstone-recommendation-discipline";
  const systemFile = key.includes("fidelity")
    ? "judge-source-fidelity-system.txt"
    : "judge-recommendation-discipline-system.txt";
  try {
    // Judges — https://launchdarkly.com/docs/home/agentcontrol/judges
    const config = await aiClient.judgeConfig(key, buildContext(persona, "judge", locale), {
      enabled: true,
      model: { name: defaultOllamaModel(), parameters: { temperature: 0 } },
      provider: { name: "Custom" },
      messages: [{ role: "system", content: readMessageFile(systemFile).trim() }],
      evaluationMetricKey: metricDefault,
    });
    const model = resolveModel(config);
    const parsed = await ollamaJudge(model, [
      { role: "system", content: `${readMessageFile(systemFile).trim()}\n\nRespond with JSON: {"score":0.0,"reasoning":"..."}` },
      { role: "user", content: `MESSAGE HISTORY:\n${inputText}\n\nRESPONSE TO EVALUATE:\n${outputText}` },
    ]);
    const score = Number(parsed.score);
    const ok = Number.isFinite(score);
    const tracker = config.tracker || (config.createTracker && config.createTracker());
    if (tracker && typeof tracker.trackJudgeResult === "function") {
      tracker.trackJudgeResult({
        judgeConfigKey: key,
        success: ok,
        sampled: true,
        metricKey: config.evaluationMetricKey || metricDefault,
        score: ok ? score : undefined,
        reasoning: parsed.reasoning ? String(parsed.reasoning) : undefined,
      });
    }
    return {
      key,
      success: ok,
      score: ok ? score : null,
      reasoning: parsed.reasoning ? String(parsed.reasoning) : "",
      passed: ok && score >= passThreshold(),
      threshold: passThreshold(),
    };
  } catch (exc) {
    return { key, success: false, score: null, reasoning: "", passed: false, error: String(exc.message || exc), threshold: passThreshold() };
  }
}

async function* generateStream(persona, action, tickerResults, selectedTools, locale) {
  action = VALID_SPECIALISTS.has(action) ? action : "report";
  locale = locale === "es" ? "es" : "en";
  const wanted = new Set((selectedTools || []).map((item) => String(item)));
  const tools = TOOL_ORDER.filter((key) => wanted.has(key));
  const { formatStoriesForPrompt } = require("./yahooNews");
  const blocks = Array.isArray(tickerResults) ? tickerResults : [];
  const storiesText = formatStoriesForPrompt(blocks);
  const hasStories = blocks.some((block) => (block.stories || []).length > 0);
  if (!hasStories) {
    yield { type: "error", message: "Load stories first, then generate." };
    yield { type: "done" };
    return;
  }

  const context = buildContext(persona, action, locale);
  let graph;
  try {
    // Agent graphs — https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
    graph = await aiClient.agentGraph(graphKey(), context);
  } catch (exc) {
    yield { type: "error", message: `agentGraph failed: ${exc.message || exc}` };
    yield { type: "done" };
    return;
  }
  let graphTracker = null;
  try { graphTracker = graph.createTracker(); } catch (_) { graphTracker = null; }
  yield { type: "run", action, locale, personaId: persona.id, personaName: persona.name, graphKey: graphKey(), tools };

  yield { type: "status", message: "assess" };
  const assessCfg = await evaluateAgent("assess", context, { action, locale, stories: storiesText });
  const assessRaw = await ollamaComplete(resolveModel(assessCfg), messagesForNode(
    assessCfg.instructions || "",
    `UI action hint: ${action}\n${languageLine(locale)}\n\nHEADLINES:\n${storiesText}\n\nReturn JSON only.`
  ));
  let [specialist, reason] = parseAssess(assessRaw, action);
  if (specialist !== action) {
    specialist = action;
    reason = `${reason} (using the action)`;
  }
  const assessTargets = outgoingTargets(graph, nodeKey("assess"));
  const edgeOk = !graph.enabled || assessTargets.includes(nodeKey(specialist));
  if (graph.enabled && !edgeOk) {
    specialist = "report";
    reason = `${reason}; graph edge missing, fall through to report`;
  }
  yield { type: "node", role: "assess", specialist, reason, clip: clip(`${specialist}: ${reason}`) };

  yield { type: "status", message: specialist };
  const specCfg = await evaluateAgent(specialist, context, { action, locale, stories: storiesText, specialist });
  const specUser = specialist === "questions"
    ? `${languageLine(locale)}\n\nCANDIDATE QUESTIONS:\n${readMessageFile("questions.txt")}\n\nHEADLINES:\n${storiesText}`
    : `${languageLine(locale)}\n\nHEADLINES:\n${storiesText}\n\nProduce the ${specialist} output now.`;
  const draft = await ollamaComplete(resolveModel(specCfg), messagesForNode(specCfg.instructions || "", specUser));
  let nodeTracker = null;
  try { nodeTracker = specCfg.createTracker ? specCfg.createTracker() : null; } catch (_) { nodeTracker = null; }
  const resumptionToken = (nodeTracker && nodeTracker.resumptionToken) || null;
  yield { type: "draft", specialist, text: draft, clip: clip(draft), resumptionToken };

  yield { type: "status", message: "judges" };
  const judges = [
    await runOneJudge(judgeKey("fidelity"), persona, locale, storiesText, draft),
    await runOneJudge(judgeKey("discipline"), persona, locale, storiesText, draft),
  ];
  yield { type: "judges", results: judges, draft };

  let transformed = draft;
  for (const key of tools) {
    if (key === "joke-tagline") {
      yield { type: "info", message: `Setting humor level to ${HUMOR_LEVEL[persona.id] || 50}%` };
    }
    transformed = applyTool(key, transformed, persona, locale);
    if (nodeTracker && typeof nodeTracker.trackToolCall === "function") {
      // Library tools — https://launchdarkly.com/docs/home/agentcontrol/tools
      try { nodeTracker.trackToolCall(key); } catch (_) { /* monitoring is best-effort */ }
    }
    yield { type: "tool", key, text: transformed, clip: clip(transformed) };
  }

  const finalizeTargets = outgoingTargets(graph, nodeKey(specialist));
  if (graph.enabled && !finalizeTargets.includes(nodeKey("finalize"))) {
    yield { type: "error", message: `Graph has no edge from ${nodeKey(specialist)} to ${nodeKey("finalize")}.` };
    yield { type: "done", resumptionToken };
    return;
  }
  try {
    if (graphTracker) graphTracker.trackHandoffSuccess(nodeKey(specialist), nodeKey("finalize"));
  } catch (_) { /* best-effort */ }

  yield { type: "status", message: "finalize" };
  const finCfg = await evaluateAgent("finalize", context, { action, locale, specialist, draft: transformed });
  const rawFinal = await ollamaComplete(resolveModel(finCfg), messagesForNode(
    finCfg.instructions || "",
    finalizeUser(locale, specialist, tools, transformed)
  ));
  const guarded = guardFinalize(rawFinal, transformed, tools);
  const finalText = guarded.text;
  for (const note of guarded.notes) {
    yield { type: "info", message: note, kind: "guard" };
  }
  const ldTransaction = buildLdTransaction({
    persona,
    action,
    locale,
    storiesText,
    tools,
    graph,
    specialist,
    assessCfg,
    specCfg,
    finCfg,
    judges,
    transformed,
  });
  yield { type: "finalize", text: finalText, clip: clip(finalText) };
  try {
    if (graphTracker) {
      graphTracker.trackPath([nodeKey("assess"), nodeKey(specialist), nodeKey("finalize")]);
      graphTracker.trackInvocationSuccess();
    }
    if (nodeTracker && nodeTracker.trackSuccess) nodeTracker.trackSuccess();
  } catch (_) { /* best-effort */ }
  yield {
    type: "done",
    specialist,
    tools,
    path: [nodeKey("assess"), nodeKey(specialist), nodeKey("finalize")],
    resumptionToken,
    draft,
    text: finalText,
    ldTransaction,
  };
}

async function submitFeedback({ persona, locale, resumptionToken, kind }) {
  const token = String(resumptionToken || "").trim();
  if (!token) throw new Error("Generate first. Feedback attaches to the specialist draft.");
  const kindL = String(kind || "").trim().toLowerCase();
  const positive = ["positive", "up", "+"].includes(kindL);
  const negative = ["negative", "down", "-"].includes(kindL);
  if (!positive && !negative) throw new Error("kind must be positive or negative.");
  const result = aiClient.createTracker(token, buildContext(persona, "feedback", locale));
  const tracker = result && (result.value !== undefined ? result.value : result);
  if (!tracker || typeof tracker.trackFeedback !== "function") {
    throw new Error("Could not rebuild the specialist tracker from the resumption token.");
  }
  // AI metrics / feedback — https://launchdarkly.com/docs/sdk/features/ai-metrics
  tracker.trackFeedback({ kind: positive ? LDFeedbackKind.Positive : LDFeedbackKind.Negative });
  return { ok: true, kind: positive ? "positive" : "negative" };
}

module.exports = {
  PERSONAS,
  TOOL_ORDER,
  toPigLatin,
  toRot13,
  guardFinalize,
  personaById,
  graphKey,
  nodeKey,
  judgeKey,
  initLaunchDarkly,
  generateStream,
  submitFeedback,
};
