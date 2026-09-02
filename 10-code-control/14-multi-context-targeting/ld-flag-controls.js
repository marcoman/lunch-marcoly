/** REST controls for the multi-context lab's boolean partner-badge flag.
 * Controls change only on/off and fallthrough; provisioned AND rules remain intact.
 * https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
 */

const { FLAG_PARTNER_BADGE } = require("./partner");

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

function optionToken(value) {
  return typeof value === "boolean" ? (value ? "true" : "false") : value;
}

function summarize(flag, environmentKey) {
  const environment = flag.environments?.[environmentKey] || {};
  const fallthroughIndex = environment.fallthrough?.variation;
  const options = (flag.variations || []).map((variation) => ({
    token: optionToken(variation.value),
    label: variation.name || String(variation.value),
    value: variation.value,
  }));
  const ruleCount = (environment.rules || []).length;
  return {
    key: FLAG_PARTNER_BADGE,
    name: flag.name || "Show partner org badge",
    label: "Show: partner org badge",
    summary: "Boolean true only for alice+acme and bob+globex (provisioned AND rules).",
    on: Boolean(environment.on),
    variationKind: "boolean",
    fallthroughOptions: options,
    fallthroughToken: optionToken(variationValue(flag, fallthroughIndex)),
    servedWhenOff: variationValue(flag, environment.offVariation),
    servedWhenOnFallthrough: variationValue(flag, fallthroughIndex),
    ruleCount,
    targetingHint: `${ruleCount} provisioned multi-context rules remain unchanged; this lab controls only flag state and fallthrough.`,
  };
}

async function listFlagControls() {
  const config = api_config();
  if (!config.configured) {
    return {
      ...config,
      flags: [{
        key: FLAG_PARTNER_BADGE,
        label: "Show: partner org badge",
        summary: "Boolean targeted by user+organization multi-context rules.",
        on: null,
        targetingHint: "Set missing environment variables to enable controls.",
      }],
    };
  }
  const query = `?env=${encodeURIComponent(config.environmentKey)}`;
  const flag = await request("GET", `/flags/${encodeURIComponent(config.projectKey)}/${FLAG_PARTNER_BADGE}${query}`);
  return { ...config, flags: [summarize(flag, config.environmentKey)], errors: [] };
}

async function applyFlagControl(flagKey, options = {}) {
  if (flagKey !== FLAG_PARTNER_BADGE) {
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
    let wanted = options.fallthrough;
    if (wanted === "true") wanted = true;
    if (wanted === "false") wanted = false;
    const variation = (flag.variations || []).find((item) => item.value === wanted);
    const variationId = variation?._id || variation?.id;
    if (!variationId) throw new Error(`No variation matching fallthrough=${JSON.stringify(options.fallthrough)}`);
    instructions.push({ kind: "updateFallthroughVariationOrRollout", variationId });
  }
  await request("PATCH", path, {
    environmentKey: config.environmentKey,
    comment: "14-multi-context-targeting UI: on/off or fallthrough",
    instructions,
  });
  const updated = await request("GET", path + query);
  return {
    ok: true,
    action: instructions.map((item) => item.kind).join("+"),
    instructions: instructions.map((item) => item.kind),
    projectKey: config.projectKey,
    environmentKey: config.environmentKey,
    flag: summarize(updated, config.environmentKey),
  };
}

module.exports = { api_config, listFlagControls, applyFlagControl };
