/** REST controls for the two flags in 15-prerequisite-flags.
 *
 * Controls may change on/off and the parent's fallthrough color. They never
 * edit the prerequisite relationship.
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */

const { FLAG_COUNT, FLAG_HIGHLIGHT, VALID_COLORS } = require("./prerequisite");

const CONTROLLED_FLAGS = [
  {
    key: FLAG_HIGHLIGHT,
    label: "Parent · grid selection highlight",
    summary:
      "15-prerequisite-flags parent (cites 11's enable-grid-selection-highlight). Must be on and serving green to satisfy the prerequisite.",
  },
  {
    key: FLAG_COUNT,
    label: "Child · navigation move count",
    summary:
      "15-prerequisite-flags child (cites 11's show-navigation-move-count). Unmet prerequisite serves its off variation.",
  },
];
const ALLOWED = new Set(CONTROLLED_FLAGS.map((item) => item.key));
const API_HOST = process.env.LD_API_HOST || "https://app.launchdarkly.com";
const API_VERSION = process.env.LD_API_VERSION || "20240415";

function api_config() {
  const values = {
    LD_API_ACCESS_TOKEN: (process.env.LD_API_ACCESS_TOKEN || "").trim(),
    LD_PROJECT_KEY: (process.env.LD_PROJECT_KEY || "").trim(),
    LD_ENVIRONMENT_KEY: (process.env.LD_ENVIRONMENT_KEY || "").trim(),
  };
  const missing = Object.entries(values)
    .filter(([, value]) => !value)
    .map(([key]) => key);
  return {
    configured: missing.length === 0,
    missing,
    projectKey: values.LD_PROJECT_KEY || null,
    environmentKey: values.LD_ENVIRONMENT_KEY || null,
    apiHost: API_HOST,
  };
}

async function request(method, path, body) {
  const config = api_config();
  if (!config.configured) throw new Error(`Flag controls need ${config.missing.join(", ")}`);
  const headers = {
    Authorization: process.env.LD_API_ACCESS_TOKEN.trim(),
    "LD-API-Version": API_VERSION,
    Accept: "application/json",
  };
  if (body) headers["Content-Type"] = "application/json; domain-model=launchdarkly.semanticpatch";
  const response = await fetch(`${API_HOST.replace(/\/+$/, "")}/api/v2${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const raw = await response.text();
  let payload = {};
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = {};
    }
  }
  if (!response.ok) throw new Error(`LaunchDarkly API ${response.status}: ${payload.message || raw}`);
  return payload;
}

function variationValue(flag, index) {
  return Number.isInteger(index) ? flag.variations?.[index]?.value ?? null : null;
}

function summarize(flag, environmentKey, meta) {
  const environment = flag.environments?.[environmentKey] || {};
  const fallthroughIndex = environment.fallthrough?.variation;
  const values = (flag.variations || []).map((item) => item.value);
  const prerequisites = environment.prerequisites || [];
  const prerequisite = prerequisites[0] || null;
  return {
    key: meta.key,
    label: meta.label,
    summary: meta.summary,
    on: Boolean(environment.on),
    variationKind: values.length && values.every((value) => typeof value === "string") ? "string" : "boolean",
    colorOptions:
      meta.key === FLAG_HIGHLIGHT ? values.filter((value) => VALID_COLORS.has(value)) : [],
    servedWhenOff: variationValue(flag, environment.offVariation),
    servedWhenOnFallthrough: variationValue(flag, fallthroughIndex),
    prerequisite,
    prerequisiteConfigured:
      meta.key !== FLAG_COUNT || Boolean(prerequisite && prerequisite.key === FLAG_HIGHLIGHT),
    targetingHint:
      meta.key === FLAG_HIGHLIGHT
        ? "Required by child: parent must be ON and serve green."
        : prerequisite
          ? "Prerequisite configured; lab controls leave it unchanged."
          : "Missing prerequisite — run this example's provisioning.",
  };
}

async function listFlagControls() {
  const config = api_config();
  if (!config.configured) {
    return {
      ...config,
      flags: CONTROLLED_FLAGS.map((meta) => ({
        ...meta,
        on: null,
        targetingHint: "Set missing environment variables.",
      })),
    };
  }
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  const flags = [];
  const errors = [];
  for (const meta of CONTROLLED_FLAGS) {
    try {
      const flag = await request(
        "GET",
        `/flags/${encodeURIComponent(config.projectKey)}/${meta.key}${query}`,
      );
      flags.push(summarize(flag, config.environmentKey, meta));
    } catch (error) {
      errors.push({ key: meta.key, error: error.message });
      flags.push({ ...meta, on: null, targetingHint: error.message, error: error.message });
    }
  }
  return { ...config, flags, errors };
}

async function applyFlagControl(flagKey, options = {}) {
  if (!ALLOWED.has(flagKey)) throw new Error(`Flag key not allowed for controls: ${flagKey}`);
  const hasOn = Object.prototype.hasOwnProperty.call(options, "on");
  const hasFallthrough = Object.prototype.hasOwnProperty.call(options, "fallthrough");
  if (!hasOn && !hasFallthrough) throw new Error('Provide "on" and/or "fallthrough"');
  if (hasFallthrough && flagKey !== FLAG_HIGHLIGHT) {
    throw new Error("Only the parent highlight flag has color variations");
  }
  const config = api_config();
  if (!config.configured) throw new Error(`Flag controls need ${config.missing.join(", ")}`);
  const path = `/flags/${encodeURIComponent(config.projectKey)}/${flagKey}`;
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  const flag = await request("GET", path + query);
  const instructions = [];
  if (hasOn) instructions.push({ kind: options.on ? "turnFlagOn" : "turnFlagOff" });
  if (hasFallthrough) {
    const variation = (flag.variations || []).find((item) => item.value === options.fallthrough);
    const variationId = variation?._id || variation?.id;
    if (!variationId) {
      throw new Error(`No variation matching fallthrough=${JSON.stringify(options.fallthrough)}`);
    }
    instructions.push({ kind: "updateFallthroughVariationOrRollout", variationId });
  }
  await request("PATCH", path, {
    environmentKey: config.environmentKey,
    comment: "15-prerequisite-flags UI control",
    instructions,
  });
  const updated = await request("GET", path + query);
  const meta = CONTROLLED_FLAGS.find((item) => item.key === flagKey);
  return {
    ok: true,
    instructions: instructions.map((item) => item.kind),
    projectKey: config.projectKey,
    environmentKey: config.environmentKey,
    flag: summarize(updated, config.environmentKey, meta),
  };
}

module.exports = { api_config, listFlagControls, applyFlagControl };
