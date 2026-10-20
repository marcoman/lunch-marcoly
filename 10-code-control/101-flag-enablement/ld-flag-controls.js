/**
 * LaunchDarkly REST helpers for in-app flag on/off controls (101-flag-enablement).
 *
 * Feature flags — semantic patch (turnFlagOn / turnFlagOff / fallthrough)
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */

const http = require("http");
const https = require("https");
const {
  DEFAULT_STRING_ON_COLOR,
  FLAG_CONTEXT,
  FLAG_COUNT,
  FLAG_HIGHLIGHT,
  isHighlightOffValue,
} = require("./highlight-style");
const { FLAG_OS_EMOJI } = require("./host-os");

const CONTROLLED_FLAGS = [
  {
    key: FLAG_HIGHLIGHT,
    label: "Enable grid selection highlight",
    summary:
      "String flag: off → none (X only); on → fallthrough color. " +
      "Use the color dropdown to set fallthrough among existing variations.",
  },
  {
    key: FLAG_CONTEXT,
    label: "Enable grid highlight color override",
    summary:
      "Boolean gate only — LaunchDarkly does not pick the colors. " +
      "When on (with a colored highlight), the app parses human / robot / beta " +
      "in the username and maps them to yellow / red / blue " +
      "(human+beta → green, robot+beta → purple). " +
      "Try a login like human-beta.",
  },
  {
    key: FLAG_COUNT,
    label: "Move count",
    summary: "Show Count: N in the header.",
  },
  {
    key: FLAG_OS_EMOJI,
    label: "Host OS emoji",
    summary: "OS emoji before the username (private hostOs attribute).",
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
    Authorization: (process.env.LD_API_ACCESS_TOKEN || "").trim(),
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

function variationValue(flag, index) {
  const variations = flag.variations || [];
  if (!Number.isInteger(index) || index < 0 || index >= variations.length) return null;
  return variations[index].value;
}

function isStringVariations(flag) {
  const values = (flag.variations || []).map((variation) => variation.value);
  return values.length > 0 && values.every((value) => typeof value === "string");
}

function summarizeFlag(flag, environmentKey, meta) {
  const environment = (flag.environments || {})[environmentKey] || {};
  const on = Boolean(environment.on);
  const offIndex = environment.offVariation;
  const fallthroughIndex = (environment.fallthrough || {}).variation;
  const rules = environment.rules || [];
  const targets = environment.targets || [];
  const contextTargets = environment.contextTargets || [];
  const variations = (flag.variations || []).map((variation, index) => ({
    index,
    value: variation.value,
    name: variation.name || "",
    description: variation.description || "",
  }));
  const offValue = variationValue(flag, offIndex);
  const fallthroughValue = variationValue(flag, fallthroughIndex);
  const variationKind = isStringVariations(flag)
    ? "string"
    : variations.length && variations.every((variation) => typeof variation.value === "boolean")
      ? "boolean"
      : "other";
  const colorOptions = [];
  if (variationKind === "string" && (flag.key || meta.key) === FLAG_HIGHLIGHT) {
    for (const variation of flag.variations || []) {
      const value = variation.value;
      if (typeof value === "string" && value.trim() && !isHighlightOffValue(value)) {
        colorOptions.push(value);
      }
    }
  }

  let targetingHint;
  if (on) {
    targetingHint =
      rules.length || targets.length || contextTargets.length
        ? `Flag is ON. Fallthrough serves ${JSON.stringify(fallthroughValue)}; individual targets/rules may override for some contexts.`
        : `Flag is ON with no extra targets/rules in this environment — evaluations use the fallthrough variation (${JSON.stringify(fallthroughValue)}).`;
  } else {
    targetingHint = `Flag is OFF — evaluations receive the off variation (${JSON.stringify(offValue)}), regardless of fallthrough.`;
  }

  return {
    key: flag.key || meta.key,
    name: flag.name || meta.label,
    label: meta.label,
    summary: meta.summary,
    on,
    variationKind,
    colorOptions,
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
        key: item.key,
        label: item.label,
        summary: item.summary,
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
      flags.push({
        key: meta.key,
        label: meta.label,
        summary: meta.summary,
        on: null,
        targetingHint: message,
        error: message,
      });
    }
  }
  return { ...config, flags, errors };
}

function variationIdForValue(flag, wanted) {
  for (const variation of flag.variations || []) {
    const value = variation.value;
    const matches =
      value === wanted ||
      (typeof value === "string" &&
        typeof wanted === "string" &&
        value.trim().toLowerCase() === wanted.trim().toLowerCase());
    if (!matches) continue;
    const id = variation._id || variation.id;
    if (typeof id === "string" && id) return id;
  }
  return null;
}

function fallthroughInstruction(flag, preferred, { onlyIfOff }) {
  if (flag.key !== FLAG_HIGHLIGHT || !isStringVariations(flag)) return null;

  const color = (preferred || DEFAULT_STRING_ON_COLOR).trim().toLowerCase();
  let colorId = variationIdForValue(flag, color);
  let chosen = color;
  if (!colorId) {
    for (const variation of flag.variations || []) {
      const value = variation.value;
      if (typeof value === "string" && !isHighlightOffValue(value)) {
        colorId = variation._id || variation.id;
        chosen = value;
        break;
      }
    }
  }
  if (!colorId) return null;

  if (onlyIfOff && preferred == null) {
    let fallIndex = null;
    for (const environment of Object.values(flag.environments || {})) {
      fallIndex = (environment.fallthrough || {}).variation;
      if (fallIndex != null) break;
    }
    const fallValue = variationValue(flag, fallIndex);
    if (fallValue != null && !isHighlightOffValue(fallValue)) return null;
  }

  return {
    kind: "updateFallthroughVariationOrRollout",
    variationId: colorId,
    _chosenValue: chosen,
  };
}

function highlightOnInstructions(flag, fallthroughValue) {
  const instructions = [{ kind: "turnFlagOn" }];
  const fallthrough = fallthroughInstruction(flag, fallthroughValue, {
    onlyIfOff: fallthroughValue == null,
  });
  if (fallthrough) instructions.push(fallthrough);
  return instructions;
}

function stripInternalFields(instructions) {
  return instructions.map((instruction) => {
    const cleaned = {};
    for (const [key, value] of Object.entries(instruction)) {
      if (!key.startsWith("_")) cleaned[key] = value;
    }
    return cleaned;
  });
}

async function applyFlagControl(flagKey, { on, fallthrough } = {}) {
  if (!ALLOWED_KEYS.has(flagKey)) {
    throw new Error(`Flag key not allowed for controls: ${flagKey}`);
  }
  const turnOn = on === undefined ? null : on;
  const fallthroughValue =
    fallthrough == null || String(fallthrough).trim() === ""
      ? null
      : String(fallthrough).trim();
  if (turnOn === null && fallthroughValue === null) {
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

  if (turnOn === true) {
    actions.push("turnFlagOn");
    instructions.push(...highlightOnInstructions(flag, fallthroughValue));
  } else if (turnOn === false) {
    actions.push("turnFlagOff");
    instructions.push({ kind: "turnFlagOff" });
    if (fallthroughValue !== null) {
      const fallthroughInstructionValue = fallthroughInstruction(flag, fallthroughValue, {
        onlyIfOff: false,
      });
      if (fallthroughInstructionValue) {
        instructions.push(fallthroughInstructionValue);
        actions.push("updateFallthrough");
      }
    }
  } else if (fallthroughValue !== null) {
    const fallthroughInstructionValue = fallthroughInstruction(flag, fallthroughValue, {
      onlyIfOff: false,
    });
    if (!fallthroughInstructionValue) {
      throw new Error(
        `No string variation matching fallthrough=${JSON.stringify(fallthroughValue)} on ${flagKey}`
      );
    }
    instructions.push(fallthroughInstructionValue);
    actions.push("updateFallthrough");
  }

  const patchInstructions = stripInternalFields(instructions);
  const action = actions.join("+") || "noop";
  await request("PATCH", flagPath, {
    environmentKey: config.environmentKey,
    comment: `101-flag-enablement UI: ${action}`,
    instructions: patchInstructions,
  });

  flag = await request("GET", `${flagPath}${query}`);
  const meta = CONTROLLED_FLAGS.find((item) => item.key === flagKey);
  return {
    ok: true,
    action,
    instructions: patchInstructions.map((instruction) => instruction.kind),
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
