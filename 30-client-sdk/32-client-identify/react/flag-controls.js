/**
 * Lab Controls proxy — LaunchDarkly REST from Node, never from the page.
 *
 * Feature flags PATCH (semantic patch)
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 * Keywords: turnFlagOn, turnFlagOff, updateFallthroughVariationOrRollout
 */

const FLAG_HIGHLIGHT = "enable-identify-grid-highlight";
const FLAG_COUNT = "show-identify-move-count";
const DEFAULT_ON_COLOR = "green";

const CONTROLLED = [
  {
    key: FLAG_HIGHLIGHT,
    label: "Identify grid highlight",
    summary:
      "String flag with key targeting: alice→green, bob→blue, else none. Leave ON for the identify demo.",
  },
  {
    key: FLAG_COUNT,
    label: "Identify move count",
    summary:
      "Boolean flag with key targeting: alice→visible, bob/else hidden. Leave ON for the identify demo.",
  },
];

const ALLOWED = new Set(CONTROLLED.map((item) => item.key));

function apiConfig() {
  const token = (process.env.LD_API_ACCESS_TOKEN || "").trim();
  const project = (process.env.LD_PROJECT_KEY || "").trim();
  const environment = (process.env.LD_ENVIRONMENT_KEY || "").trim();
  const missing = [];
  if (!token) missing.push("LD_API_ACCESS_TOKEN");
  if (!project) missing.push("LD_PROJECT_KEY");
  if (!environment) missing.push("LD_ENVIRONMENT_KEY");
  return {
    configured: missing.length === 0,
    missing,
    projectKey: project || null,
    environmentKey: environment || null,
    apiHost: process.env.LD_API_HOST || "https://app.launchdarkly.com",
  };
}

function ldRequest(method, path, body) {
  const cfg = apiConfig();
  if (!cfg.configured) {
    const err = new Error("Flag controls need " + cfg.missing.join(", ") + " in the server environment.");
    err.status = 503;
    throw err;
  }
  const token = (process.env.LD_API_ACCESS_TOKEN || "").trim();
  const version = process.env.LD_API_VERSION || "20240415";
  const url = `${cfg.apiHost.replace(/\/$/, "")}/api/v2${path}`;
  const headers = {
    Authorization: token,
    "LD-API-Version": version,
    Accept: "application/json",
  };
  const opts = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] =
      method === "PATCH"
        ? "application/json; domain-model=launchdarkly.semanticpatch"
        : "application/json";
    opts.body = JSON.stringify(body);
  }
  return fetch(url, opts).then(async (res) => {
    const text = await res.text();
    const parsed = text ? JSON.parse(text) : {};
    if (!res.ok) {
      const err = new Error(parsed.message || text || `LaunchDarkly API ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return parsed;
  });
}

function variationValue(flag, index) {
  const variations = flag.variations || [];
  if (index == null || index < 0 || index >= variations.length) return null;
  return variations[index].value;
}

function variationIdForValue(flag, wanted) {
  const want = typeof wanted === "string" ? wanted.trim().toLowerCase() : wanted;
  for (const variation of flag.variations || []) {
    const val = variation.value;
    const match =
      val === wanted ||
      (typeof val === "string" && typeof want === "string" && val.trim().toLowerCase() === want);
    if (!match) continue;
    const id = variation._id || variation.id;
    if (typeof id === "string" && id) return id;
  }
  return null;
}

function isOffValue(val) {
  return val === "none" || val === false;
}

function summarizeFlag(flag, environmentKey, meta) {
  const env = (flag.environments || {})[environmentKey] || {};
  const on = Boolean(env.on);
  const offIdx = env.offVariation;
  const fallIdx = (env.fallthrough || {}).variation;
  const offValue = variationValue(flag, typeof offIdx === "number" ? offIdx : null);
  const fallValue = variationValue(flag, typeof fallIdx === "number" ? fallIdx : null);
  const key = flag.key || meta.key;
  const stringVars = (flag.variations || []).every((v) => typeof v.value === "string");
  const colorOptions = [];
  if (key === FLAG_HIGHLIGHT && stringVars) {
    for (const variation of flag.variations || []) {
      if (typeof variation.value === "string" && !isOffValue(variation.value)) {
        colorOptions.push(variation.value);
      }
    }
  }
  let targetingHint;
  if (on) {
    targetingHint = `Flag is ON — fallthrough ${JSON.stringify(fallValue)}.`;
  } else {
    targetingHint = `Flag is OFF — off variation ${JSON.stringify(offValue)}.`;
  }
  return {
    key,
    name: flag.name || meta.label,
    label: meta.label,
    summary: meta.summary,
    on,
    variationKind: key === FLAG_HIGHLIGHT ? "string" : "boolean",
    colorOptions,
    servedWhenOff: offValue,
    servedWhenOnFallthrough: fallValue,
    targetingHint,
  };
}

function fallthroughInstruction(flag, preferred) {
  if (flag.key !== FLAG_HIGHLIGHT) return null;
  const color = (preferred || DEFAULT_ON_COLOR).trim().toLowerCase();
  let colorId = variationIdForValue(flag, color);
  if (!colorId) {
    for (const variation of flag.variations || []) {
      if (typeof variation.value === "string" && !isOffValue(variation.value)) {
        colorId = variation._id || variation.id;
        break;
      }
    }
  }
  if (!colorId) return null;
  return { kind: "updateFallthroughVariationOrRollout", variationId: colorId };
}

async function listFlagControls() {
  const cfg = apiConfig();
  if (!cfg.configured) {
    return {
      ...cfg,
      flags: CONTROLLED.map((item) => ({
        ...item,
        on: null,
        targetingHint: "Set missing env vars to enable controls.",
      })),
    };
  }
  const query = new URLSearchParams({ env: cfg.environmentKey }).toString();
  const flags = [];
  const errors = [];
  for (const meta of CONTROLLED) {
    try {
      const flag = await ldRequest("GET", `/flags/${cfg.projectKey}/${meta.key}?${query}`);
      flags.push(summarizeFlag(flag, cfg.environmentKey, meta));
    } catch (exc) {
      errors.push({ key: meta.key, error: String(exc.message || exc) });
      flags.push({
        ...meta,
        on: null,
        targetingHint: String(exc.message || exc),
        error: String(exc.message || exc),
      });
    }
  }
  return { ...cfg, flags, errors };
}

async function applyFlagControl(flagKey, { on, fallthrough } = {}) {
  if (!ALLOWED.has(flagKey)) {
    const err = new Error(`Flag key not allowed for controls: ${flagKey}`);
    err.status = 400;
    throw err;
  }
  if (on === undefined && fallthrough == null) {
    const err = new Error('Provide "on" and/or "fallthrough"');
    err.status = 400;
    throw err;
  }
  const cfg = apiConfig();
  const query = new URLSearchParams({ env: cfg.environmentKey }).toString();
  let flag = await ldRequest("GET", `/flags/${cfg.projectKey}/${flagKey}?${query}`);
  const instructions = [];
  if (on === true) {
    instructions.push({ kind: "turnFlagOn" });
    const fall = fallthroughInstruction(flag, fallthrough);
    if (fall) instructions.push(fall);
  } else if (on === false) {
    instructions.push({ kind: "turnFlagOff" });
    if (fallthrough != null) {
      const fall = fallthroughInstruction(flag, fallthrough);
      if (fall) instructions.push(fall);
    }
  } else if (fallthrough != null) {
    const fall = fallthroughInstruction(flag, fallthrough);
    if (!fall) {
      const err = new Error(`No string variation matching fallthrough=${fallthrough}`);
      err.status = 400;
      throw err;
    }
    instructions.push(fall);
  }
  await ldRequest("PATCH", `/flags/${cfg.projectKey}/${flagKey}`, {
    environmentKey: cfg.environmentKey,
    comment: "32-client-identify UI",
    instructions,
  });
  flag = await ldRequest("GET", `/flags/${cfg.projectKey}/${flagKey}?${query}`);
  const meta = CONTROLLED.find((item) => item.key === flagKey);
  return {
    ok: true,
    projectKey: cfg.projectKey,
    environmentKey: cfg.environmentKey,
    flag: summarizeFlag(flag, cfg.environmentKey, meta),
  };
}

export {
  FLAG_HIGHLIGHT,
  FLAG_COUNT,
  apiConfig,
  listFlagControls,
  applyFlagControl,
};
