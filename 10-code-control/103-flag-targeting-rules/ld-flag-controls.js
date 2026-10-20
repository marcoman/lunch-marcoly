/** REST controls for the targeting-rules lab's single string flag.
 * Controls change only on/off and fallthrough; provisioned rules remain intact.
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */

const { FLAG_TEAM_DISPLAY_LABELS, FLAG_TEAM_LABEL_STYLE } = require("./team-style");

const CONTROLLED_FLAGS = [
  [FLAG_TEAM_LABEL_STYLE, "Configure team label style", "String style selected by provisioned targeting rules on public team."],
  [FLAG_TEAM_DISPLAY_LABELS, "Configure team display labels", "JSON words for the pill and the team switch. Team values stay red, blue, and yellow."],
];

const API_HOST = process.env.LD_API_HOST || "https://app.launchdarkly.com";
const API_VERSION = process.env.LD_API_VERSION || "20240415";

function api_config() {
  const values = {
    LD_API_ACCESS_TOKEN: (process.env.LD_API_ACCESS_TOKEN || "").trim(),
    LD_PROJECT_KEY: (process.env.LD_PROJECT_KEY || "").trim(),
    LD_ENVIRONMENT_KEY: (process.env.LD_ENVIRONMENT_KEY || "").trim(),
  };
  const missing = Object.entries(values).filter(([, value]) => !value).map(([key]) => key);
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
    try { payload = JSON.parse(raw); } catch { payload = {}; }
  }
  if (!response.ok) throw new Error(`LaunchDarkly API ${response.status}: ${payload.message || raw}`);
  return payload;
}

function variationValue(flag, index) {
  return Number.isInteger(index) ? flag.variations?.[index]?.value ?? null : null;
}

function optionToken(variation) {
  const value = variation.value;
  if (value && typeof value === "object") return variation.name || JSON.stringify(value);
  return value;
}

function summarize(flag, environmentKey, label, summary) {
  const environment = flag.environments?.[environmentKey] || {};
  const fallthroughIndex = environment.fallthrough?.variation;
  const variations = flag.variations || [];
  const options = variations.map((variation) => ({
    token: optionToken(variation),
    label: variation.name || optionToken(variation),
    value: variation.value,
  }));
  const ruleCount = (environment.rules || []).length;
  const fallVariation = Number.isInteger(fallthroughIndex) ? variations[fallthroughIndex] : null;
  const kind = variations.some((item) => item.value && typeof item.value === "object") ? "json" : "string";
  return {
    key: flag.key,
    name: flag.name || label,
    label,
    summary,
    on: Boolean(environment.on),
    variationKind: kind,
    fallthroughOptions: options,
    fallthroughToken: fallVariation ? optionToken(fallVariation) : null,
    servedWhenOff: variationValue(flag, environment.offVariation),
    servedWhenOnFallthrough: variationValue(flag, fallthroughIndex),
    ruleCount,
    targetingHint: `${ruleCount} provisioned rules remain unchanged; this lab controls only flag state and fallthrough.`,
  };
}

async function listFlagControls() {
  const config = api_config();
  if (!config.configured) {
    return {
      ...config,
      flags: CONTROLLED_FLAGS.map(([key, label, summary]) => ({
        key,
        label,
        summary,
        on: null,
        targetingHint: "Set missing environment variables to enable controls.",
      })),
    };
  }
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  const flags = [];
  const errors = [];
  for (const [key, label, summary] of CONTROLLED_FLAGS) {
    try {
      const flag = await request("GET", `/flags/${encodeURIComponent(config.projectKey)}/${key}${query}`);
      flags.push(summarize(flag, config.environmentKey, label, summary));
    } catch (error) {
      errors.push({ key, error: error.message });
      flags.push({ key, label, summary, on: null, targetingHint: error.message });
    }
  }
  return { ...config, flags, errors };
}

async function applyFlagControl(flagKey, options = {}) {
  if (!CONTROLLED_FLAGS.some(([key]) => key === flagKey)) {
    throw new Error(`Flag key not allowed for controls: ${flagKey}`);
  }
  const hasOn = Object.prototype.hasOwnProperty.call(options, "on");
  const hasFallthrough = Object.prototype.hasOwnProperty.call(options, "fallthrough");
  if (!hasOn && !hasFallthrough) throw new Error('Provide "on" and/or "fallthrough"');
  const config = api_config();
  if (!config.configured) throw new Error(`Flag controls need ${config.missing.join(", ")}`);
  const path = `/flags/${encodeURIComponent(config.projectKey)}/${flagKey}`;
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  const flag = await request("GET", path + query);
  const instructions = [];
  if (hasOn) instructions.push({ kind: options.on ? "turnFlagOn" : "turnFlagOff" });
  if (hasFallthrough) {
    const wanted = String(options.fallthrough);
    const variation = (flag.variations || []).find((item) => optionToken(item) === wanted || item.value === wanted);
    const variationId = variation?._id || variation?.id;
    if (!variationId) throw new Error(`No variation matching fallthrough=${JSON.stringify(options.fallthrough)}`);
    instructions.push({ kind: "updateFallthroughVariationOrRollout", variationId });
  }
  await request("PATCH", path, {
    environmentKey: config.environmentKey,
    comment: "13-flag-targeting-rules UI: on/off or fallthrough",
    instructions,
  });
  const updated = await request("GET", path + query);
  return {
    ok: true,
    action: instructions.map((item) => item.kind).join("+"),
    instructions: instructions.map((item) => item.kind),
    projectKey: config.projectKey,
    environmentKey: config.environmentKey,
    flag: summarize(
      updated,
      config.environmentKey,
      CONTROLLED_FLAGS.find(([key]) => key === flagKey)[1],
      CONTROLLED_FLAGS.find(([key]) => key === flagKey)[2],
    ),
  };
}

module.exports = { api_config, listFlagControls, applyFlagControl };
