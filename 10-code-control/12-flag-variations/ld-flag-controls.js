/**
 * LaunchDarkly REST controls for the four 12-flag-variations flags.
 *
 * Feature flags — semantic patch (on/off and fallthrough)
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */

const http = require("http");
const https = require("https");

const CONTROLLED_FLAGS = [
  {
    key: "show-anonymous-host-os-emoji",
    label: "Show anonymous host OS emoji",
    summary:
      "Boolean, evaluated with an anonymous context + private hostOs. " +
      "LaunchDarkly gates visibility; the app maps host OS → emoji.",
  },
  {
    key: "configure-navigation-count-label",
    label: "Configure navigation count label",
    summary:
      "String variation — fallthrough chooses the header label " +
      "(Count / Moves / …). Toggle on/off; pick fallthrough when on.",
  },
  {
    key: "configure-lucky-number",
    label: "Configure lucky number",
    summary: "Number variation — fallthrough chooses Lucky Number is: N (0–5).",
  },
  {
    key: "configure-max-navigation-moves",
    label: "Configure max navigation moves",
    summary:
      'JSON variation — fallthrough chooses {"maxMoves": N} for the session move cap.',
  },
];

const ALLOWED_KEYS = new Set(CONTROLLED_FLAGS.map(({ key }) => key));
const LD_API_VERSION = process.env.LD_API_VERSION || "20240415";

function api_config() {
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

function request(method, apiPath, body) {
  const config = api_config();
  if (!config.configured) {
    return Promise.reject(
      new Error(`Flag controls need ${config.missing.join(", ")} in the server environment.`)
    );
  }

  const url = new URL(`/api/v2${apiPath}`, `${config.apiHost.replace(/\/+$/, "")}/`);
  const payload = body === undefined ? null : JSON.stringify(body);
  const transport = url.protocol === "http:" ? http : https;
  const headers = {
    Authorization: process.env.LD_API_ACCESS_TOKEN.trim(),
    "LD-API-Version": LD_API_VERSION,
    Accept: "application/json",
  };
  if (payload !== null) {
    headers["Content-Type"] =
      method === "PATCH"
        ? "application/json; domain-model=launchdarkly.semanticpatch"
        : "application/json";
    headers["Content-Length"] = Buffer.byteLength(payload);
  }

  return new Promise((resolve, reject) => {
    const req = transport.request(url, { method, headers, timeout: 30000 }, (res) => {
      let raw = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        raw += chunk;
      });
      res.on("end", () => {
        let parsed = {};
        if (raw) {
          try {
            parsed = JSON.parse(raw);
          } catch (_) {
            parsed = {};
          }
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(parsed);
          return;
        }
        reject(
          new Error(
            `LaunchDarkly API ${res.statusCode}: ${parsed.message || raw || res.statusMessage}`
          )
        );
      });
    });
    req.on("timeout", () => req.destroy(new Error("LaunchDarkly API request timed out")));
    req.on("error", reject);
    if (payload !== null) req.write(payload);
    req.end();
  });
}

function variationKind(flag) {
  const values = (flag.variations || []).map(({ value }) => value);
  if (!values.length) return "other";
  if (values.every((value) => typeof value === "boolean")) return "boolean";
  if (values.every((value) => typeof value === "string")) return "string";
  if (values.every((value) => typeof value === "number")) return "number";
  if (values.every((value) => value && typeof value === "object")) return "json";
  return "other";
}

function optionToken(value) {
  if (value && typeof value === "object") {
    const ordered = {};
    for (const key of Object.keys(value).sort()) ordered[key] = value[key];
    return JSON.stringify(ordered);
  }
  return String(value);
}

function normalizeFallthrough(value) {
  if (typeof value !== "string") return value;
  const text = value.trim();
  if (!text) return text;
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
}

function valuesEqual(left, right) {
  if (Object.is(left, right)) return true;
  if (
    (typeof left === "number" || typeof left === "string") &&
    (typeof right === "number" || typeof right === "string") &&
    left !== "" &&
    right !== "" &&
    Number(left) === Number(right)
  ) {
    return true;
  }
  if (typeof left === "string" && typeof right === "string") {
    return left.trim() === right.trim();
  }
  if (
    (left && typeof left === "object") ||
    (right && typeof right === "object")
  ) {
    try {
      const a = typeof left === "string" ? JSON.parse(left) : left;
      const b = typeof right === "string" ? JSON.parse(right) : right;
      return JSON.stringify(a) === JSON.stringify(b);
    } catch (_) {
      return false;
    }
  }
  return false;
}

function variationValue(flag, index) {
  return Number.isInteger(index) && flag.variations && flag.variations[index]
    ? flag.variations[index].value
    : null;
}

function summarizeFlag(flag, environmentKey, meta) {
  const environment = (flag.environments || {})[environmentKey] || {};
  const on = Boolean(environment.on);
  const offIndex = environment.offVariation;
  const fallthroughIndex = (environment.fallthrough || {}).variation;
  const kind = variationKind(flag);
  const variations = (flag.variations || []).map((variation, index) => ({
    index,
    value: variation.value,
    name: variation.name || "",
    description: variation.description || "",
    token: optionToken(variation.value),
  }));
  const fallthroughOptions =
    kind === "boolean"
      ? []
      : variations.map((variation) => ({
          token: variation.token,
          label: variation.name || variation.token,
          value: variation.value,
        }));
  const offValue = variationValue(flag, offIndex);
  const fallthroughValue = variationValue(flag, fallthroughIndex);
  const rules = environment.rules || [];
  const targets = environment.targets || [];
  const contextTargets = environment.contextTargets || [];
  let targetingHint;
  if (!on) {
    targetingHint = `Flag is OFF — evaluations receive the off variation (${JSON.stringify(
      offValue
    )}), regardless of fallthrough.`;
  } else if (rules.length || targets.length || contextTargets.length) {
    targetingHint = `Flag is ON. Fallthrough serves ${JSON.stringify(
      fallthroughValue
    )}; targets/rules may override for some contexts.`;
  } else {
    targetingHint = `Flag is ON with no extra targets/rules — evaluations use fallthrough (${JSON.stringify(
      fallthroughValue
    )}).`;
  }
  return {
    key: flag.key || meta.key,
    name: flag.name || meta.label,
    label: meta.label,
    summary: meta.summary,
    on,
    variationKind: kind,
    fallthroughOptions,
    fallthroughToken:
      fallthroughValue === null || fallthroughValue === undefined
        ? null
        : optionToken(fallthroughValue),
    variations,
    offVariation: offIndex,
    fallthroughVariation: fallthroughIndex,
    servedWhenOff: offValue,
    servedWhenOnFallthrough: fallthroughValue,
    ruleCount: rules.length,
    targetCount: targets.length + contextTargets.length,
    targetingHint,
  };
}

async function listFlagControls() {
  const config = api_config();
  if (!config.configured) {
    return {
      ...config,
      flags: CONTROLLED_FLAGS.map((item) => ({
        ...item,
        on: null,
        targetingHint: "Set missing env vars to enable controls.",
      })),
    };
  }

  const flags = [];
  const errors = [];
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  for (const meta of CONTROLLED_FLAGS) {
    try {
      const flag = await request(
        "GET",
        `/flags/${encodeURIComponent(config.projectKey)}/${encodeURIComponent(meta.key)}${query}`
      );
      flags.push(summarizeFlag(flag, config.environmentKey, meta));
    } catch (error) {
      const message = error.message || String(error);
      errors.push({ key: meta.key, error: message });
      flags.push({ ...meta, on: null, targetingHint: message, error: message });
    }
  }
  return { ...config, flags, errors };
}

function fallthroughInstruction(flag, wanted) {
  const variation = (flag.variations || []).find(({ value }) => valuesEqual(value, wanted));
  const variationId = variation && (variation._id || variation.id);
  return variationId
    ? { kind: "updateFallthroughVariationOrRollout", variationId }
    : null;
}

async function applyFlagControl(flagKey, { on, fallthrough } = {}) {
  if (!ALLOWED_KEYS.has(flagKey)) {
    throw new Error(`Flag key not allowed for controls: ${flagKey}`);
  }
  if (on === undefined && fallthrough === undefined) {
    throw new Error('Provide "on" and/or "fallthrough"');
  }
  const config = api_config();
  if (!config.configured) {
    throw new Error(
      `Flag controls need ${config.missing.join(", ")} in the server environment.`
    );
  }

  const flagPath = `/flags/${encodeURIComponent(config.projectKey)}/${encodeURIComponent(
    flagKey
  )}`;
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  let flag = await request("GET", `${flagPath}${query}`);
  const instructions = [];
  const actions = [];
  const wanted = fallthrough === undefined ? undefined : normalizeFallthrough(fallthrough);

  if (on === true) {
    instructions.push({ kind: "turnFlagOn" });
    actions.push("turnFlagOn");
  } else if (on === false) {
    instructions.push({ kind: "turnFlagOff" });
    actions.push("turnFlagOff");
  }
  if (wanted !== undefined) {
    const instruction = fallthroughInstruction(flag, wanted);
    if (!instruction && on !== false) {
      throw new Error(
        `No variation matching fallthrough=${JSON.stringify(wanted)} on ${flagKey}`
      );
    }
    if (instruction) {
      instructions.push(instruction);
      actions.push("updateFallthrough");
    }
  }

  const action = actions.join("+") || "noop";
  await request("PATCH", flagPath, {
    environmentKey: config.environmentKey,
    comment: `12-flag-variations UI: ${action}`,
    instructions,
  });
  flag = await request("GET", `${flagPath}${query}`);
  const meta = CONTROLLED_FLAGS.find(({ key }) => key === flagKey);
  return {
    ok: true,
    action,
    instructions: instructions.map(({ kind }) => kind),
    projectKey: config.projectKey,
    environmentKey: config.environmentKey,
    flag: summarizeFlag(flag, config.environmentKey, meta),
  };
}

module.exports = {
  CONTROLLED_FLAGS,
  api_config,
  listFlagControls,
  applyFlagControl,
};
