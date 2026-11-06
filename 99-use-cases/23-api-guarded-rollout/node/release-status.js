/**
 * Read and start the guarded environment release for this example.
 *
 * Including metrics makes the release kind guarded.
 *
 * LaunchDarkly: environment releases — kind guarded
 * https://launchdarkly.com/docs/api/environment-releases
 */

const { FLAG_HIGHLIGHT } = require("./highlight-eval");
const { METRIC_DEFINITIONS, createBody } = require("./metrics");

const ALLOCATION_SCALE = 1000;
const ROLLOUT_STEPS = [
  { percent: 10, durationSeconds: 120 },
  { percent: 20, durationSeconds: 120 },
  { percent: 30, durationSeconds: 60 },
  { percent: 50, durationSeconds: 60 },
];
const RANDOMIZATION_UNIT = "user";
const FLAG_API_VERSION = process.env.LD_API_VERSION || "20240415";
const METRIC_HEALTH_CHECKS = ["metric_events_any", "metric_events_with_context"];

function apiConfig() {
  return {
    host: (process.env.LD_API_HOST || "https://app.launchdarkly.com").replace(/\/$/, ""),
    token: process.env.LD_API_ACCESS_TOKEN || "",
    project: process.env.LD_PROJECT_KEY || "",
    environment: process.env.LD_ENVIRONMENT_KEY || "",
  };
}

function schedule() {
  return ROLLOUT_STEPS.map((step) => ({ ...step }));
}

function targetingUrl() {
  const cfg = apiConfig();
  if (!cfg.project || !cfg.environment) return null;
  const query = new URLSearchParams({ env: cfg.environment, "selected-env": cfg.environment });
  return `${cfg.host}/projects/${cfg.project}/flags/${FLAG_HIGHLIGHT}/targeting?${query}`;
}

function missingConfig() {
  const cfg = apiConfig();
  if (cfg.token && cfg.project && cfg.environment) return null;
  return {
    configured: false,
    flagKey: FLAG_HIGHLIGHT,
    detail: "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.",
  };
}

async function request(method, path, body, version = "beta", contentType = "application/json") {
  const cfg = apiConfig();
  const headers = { Authorization: cfg.token, "LD-API-Version": version };
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = contentType;
    init.body = JSON.stringify(body);
  }
  try {
    const response = await fetch(cfg.host + path, init);
    const text = await response.text();
    let payload = text;
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (_) {
      payload = text.slice(0, 240);
    }
    return [response.status, payload];
  } catch (err) {
    return [0, { message: `Could not reach LaunchDarkly: ${err.message}` }];
  }
}

function apiError(status, payload) {
  const message = payload && typeof payload === "object" ? payload.message : String(payload);
  const code = payload && typeof payload === "object" ? payload.code : null;
  let detail = message || "LaunchDarkly rejected the request.";
  if (code === "health_checks_failed") {
    detail += " Log in on the grid once so the flag has a user evaluation, then start again.";
  }
  return { configured: true, flagKey: FLAG_HIGHLIGHT, error: true, http: status, code, detail };
}

function stepView(step) {
  const allocation = step && step.allocation;
  const duration = step && step.durationMillis;
  return {
    percent: typeof allocation === "number" ? allocation / ALLOCATION_SCALE : null,
    durationSeconds: typeof duration === "number" ? Math.floor(duration / 1000) : null,
  };
}

function regressedMetrics(phase) {
  const statuses = (phase && phase.metricStatuses) || {};
  return Object.keys(statuses).filter((key) => statuses[key] === "regressed");
}

function headline(item) {
  if (item.flagOn === false) return "Flag is off. Every context receives none.";
  const status = item.status;
  if (status == null || status === "none") return item.detail || "No guarded release yet.";
  const names = Array.isArray(item.regressedMetrics) ? item.regressedMetrics.join(", ") : "";
  const rolledBack = status === "reverted" || item.stopped === true;
  if (rolledBack && (item.statusReason === "reverted_regression_detected" || names)) {
    return `Rolled back to none. ${names || "A guardrail"} regressed.`;
  }
  if (rolledBack) return "Rolled back to none.";
  if (status === "waiting" && item.statusReason === "waiting_regression_detected") {
    return `Paused. ${names || "A guardrail"} regressed.`;
  }
  if (status === "completed") return "Completed.";
  if (status === "in_progress" || item.active) return "Monitoring.";
  return String(status || "Waiting.");
}

function summarizeRelease(item) {
  const phases = item.phases || [];
  const phase = phases[0] || {};
  const steps = (phase.steps || []).map(stepView);
  const summary = {
    configured: true,
    flagKey: FLAG_HIGHLIGHT,
    kind: item.kind,
    status: item.status,
    statusReason: item.statusReason,
    metricCount: (item.metrics || []).length,
    regressedMetrics: regressedMetrics(phase),
    stepIndex: phase.currentStepIndex,
    stepCount: steps.length,
    steps,
    active: item.endedAt == null && item.status !== "completed" && item.status !== "reverted",
  };
  summary.headline = headline(summary);
  return summary;
}

function flagPath() {
  const cfg = apiConfig();
  return `/api/v2/flags/${cfg.project}/${FLAG_HIGHLIGHT}`;
}

function releasesPath() {
  const cfg = apiConfig();
  return `/api/v2/projects/${cfg.project}/flags/${FLAG_HIGHLIGHT}/environments/${cfg.environment}/releases`;
}

function phaseRuleIds(flag) {
  const environment = ((flag && flag.environments) || {})[apiConfig().environment] || {};
  const ids = [];
  for (const rule of environment.rules || []) {
    const ruleId = rule._id || rule.id;
    if (typeof ruleId === "string") ids.push(ruleId);
  }
  return ids;
}

function variationId(flag, value) {
  for (const item of (flag && flag.variations) || []) {
    if (item.value === value && item._id) return String(item._id);
  }
  return null;
}

function startBody(originalVariationId, targetVariationId) {
  return {
    originalVariationId,
    targetVariationId,
    randomizationUnit: RANDOMIZATION_UNIT,
    cleanupBehavior: "remove_rules_and_update_default_rule",
    comment: "23-api-guarded-rollout: start guarded release",
    bypassHealthChecks: METRIC_HEALTH_CHECKS.slice(),
    metrics: METRIC_DEFINITIONS.map((item) => ({ metricKey: item.key, autoRollback: true })),
    phases: [
      {
        description: "All users",
        clauses: [{
          contextKind: RANDOMIZATION_UNIT,
          attribute: "kind",
          op: "in",
          values: [RANDOMIZATION_UNIT],
        }],
        steps: ROLLOUT_STEPS.map((step) => ({
          allocation: step.percent * ALLOCATION_SCALE,
          durationMillis: step.durationSeconds * 1000,
        })),
      },
    ],
  };
}

async function flagIsOn() {
  const cfg = apiConfig();
  if (!cfg.token || !cfg.project || !cfg.environment) return null;
  const query = new URLSearchParams({ env: cfg.environment });
  const [status, flag] = await request("GET", `${flagPath()}?${query}`, undefined, FLAG_API_VERSION);
  if (status !== 200 || !flag || typeof flag !== "object") return null;
  const environment = (flag.environments || {})[cfg.environment] || {};
  return Boolean(environment.on);
}

async function latestGuardedRelease() {
  const missing = missingConfig();
  if (missing) return missing;
  const query = new URLSearchParams({ queryfilter: "kind:equals:guarded", limit: "1" });
  const [status, payload] = await request("GET", `${releasesPath()}?${query}`);
  let summary;
  if (status === 404) {
    summary = {
      configured: true,
      flagKey: FLAG_HIGHLIGHT,
      status: "none",
      detail: "No flag yet. Start creates it.",
      flagOn: false,
    };
    summary.headline = headline(summary);
    return summary;
  }
  if (status !== 200 || !payload || typeof payload !== "object") return apiError(status, payload);
  const items = payload.items || [];
  if (!items.length) {
    summary = {
      configured: true,
      flagKey: FLAG_HIGHLIGHT,
      status: "none",
      metricCount: 0,
      steps: [],
      detail: "No guarded release on this flag yet.",
    };
  } else {
    summary = summarizeRelease(items[0]);
  }
  summary.flagOn = await flagIsOn();
  if (summary.flagOn === false) summary.active = false;
  summary.headline = headline(summary);
  return summary;
}

async function ensureFlag() {
  const [status, flag] = await request("GET", flagPath(), undefined, FLAG_API_VERSION);
  if (status === 200 && flag && typeof flag === "object") return null;
  if (status !== 404) return apiError(status, flag);
  const [created, payload] = await request("POST", `/api/v2/flags/${apiConfig().project}`, {
    key: FLAG_HIGHLIGHT,
    name: "API guarded grid highlight",
    description: "Guarded rollout of the grid highlight from none to green, started with the environment releases API. Latency, error rate, and movement are the guardrails.",
    temporary: false,
    tags: ["grid-navigator", "use-case", "api-guarded-rollout", "environment-release", "guarded-rollout", "string"],
    variations: [
      { value: "none", name: "No highlight", description: "Selected cell stays dark. The release starts here." },
      { value: "green", name: "Green", description: "Selected cell turns green. The release moves traffic here." },
      { value: "yellow", name: "Yellow", description: "Yellow highlight. This release does not target it." },
      { value: "red", name: "Red", description: "Red highlight. This release does not target it." },
      { value: "blue", name: "Blue", description: "Blue highlight. This release does not target it." },
      { value: "purple", name: "Purple", description: "Purple highlight. This release does not target it." },
    ],
    defaults: { onVariation: 1, offVariation: 0 },
  }, FLAG_API_VERSION);
  if (created !== 200 && created !== 201) return apiError(created, payload);
  return null;
}

async function ensureMetrics() {
  const warnings = [];
  const project = apiConfig().project;
  for (const definition of METRIC_DEFINITIONS) {
    const path = `/api/v2/metrics/${project}/${definition.key}`;
    const [status, existing] = await request("GET", path, undefined, FLAG_API_VERSION);
    if (status === 404) {
      const [created, payload] = await request("POST", `/api/v2/metrics/${project}`, createBody(definition), FLAG_API_VERSION);
      if (created !== 200 && created !== 201) {
        const message = payload && typeof payload === "object" ? payload.message : payload;
        warnings.push(`${definition.key}: create failed (${created}) ${message}`);
      }
      continue;
    }
    if (status !== 200 || !existing || typeof existing !== "object") {
      warnings.push(`${definition.key}: could not read the metric (${status})`);
      continue;
    }
    if (existing.description === definition.description) continue;
    const [patched, payload] = await request(
      "PATCH",
      path,
      [{ op: "replace", path: "/description", value: definition.description }],
      FLAG_API_VERSION,
    );
    if (patched >= 400) {
      const message = payload && typeof payload === "object" ? payload.message : payload;
      warnings.push(`${definition.key}: description was not updated (${patched}) ${message}`);
    }
  }
  return warnings;
}

async function startGuardedRelease() {
  const missing = missingConfig();
  if (missing) return missing;
  const warnings = await ensureMetrics();
  const flagError = await ensureFlag();
  if (flagError) return flagError;
  const [status, flag] = await request("GET", flagPath(), undefined, FLAG_API_VERSION);
  if (status !== 200 || !flag || typeof flag !== "object") return apiError(status, flag);
  const noneId = variationId(flag, "none");
  const greenId = variationId(flag, "green");
  if (!noneId || !greenId) {
    return { configured: true, flagKey: FLAG_HIGHLIGHT, error: true, detail: "The flag is missing the none or green variation." };
  }
  const [patchStatus, patched] = await request("PATCH", flagPath(), {
    environmentKey: apiConfig().environment,
    comment: "23-api-guarded-rollout: on, default rule stays none",
    instructions: [
      ...phaseRuleIds(flag).map((ruleId) => ({ kind: "removeRule", ruleId })),
      { kind: "turnFlagOn" },
      { kind: "updateFallthroughVariationOrRollout", variationId: noneId },
    ],
  }, FLAG_API_VERSION, "application/json; domain-model=launchdarkly.semanticpatch");
  if (patchStatus >= 400) return apiError(patchStatus, patched);
  const [startStatus, started] = await request("POST", releasesPath(), startBody(noneId, greenId));
  if ((startStatus !== 200 && startStatus !== 201) || !started || !started.phases) return apiError(startStatus, started);
  const summary = summarizeRelease(started);
  summary.started = true;
  summary.flagOn = true;
  summary.headline = headline(summary);
  if (warnings.length) summary.metricDescriptionWarning = warnings.join(" ");
  return summary;
}

async function stopGuardedRelease() {
  const missing = missingConfig();
  if (missing) return missing;
  const query = new URLSearchParams({ queryfilter: "kind:equals:guarded", limit: "5" });
  const [status, payload] = await request("GET", `${releasesPath()}?${query}`);
  if (status !== 200 || !payload || typeof payload !== "object") return apiError(status, payload);
  const active = (payload.items || []).find((item) => item.endedAt == null && item.status !== "completed" && item.status !== "reverted");
  if (!active || !active.id) {
    return { configured: true, flagKey: FLAG_HIGHLIGHT, error: true, code: "no_active_release", detail: "No active guarded release to stop." };
  }
  const [stopStatus, stopped] = await request("PUT", `${releasesPath()}/${active.id}/stop`, {
    resolution: "roll_back_all_phases_and_remove_pending_phases",
    comment: "23-api-guarded-rollout: stop guarded release",
  });
  if ((stopStatus !== 200 && stopStatus !== 201) || !stopped || typeof stopped !== "object") return apiError(stopStatus, stopped);
  const summary = summarizeRelease(stopped);
  summary.stopped = true;
  summary.flagOn = await flagIsOn();
  summary.headline = headline(summary);
  return summary;
}

async function resetDemo() {
  const missing = missingConfig();
  if (missing) return missing;
  const stopped = await stopGuardedRelease();
  if (stopped.error && stopped.code !== "no_active_release") return stopped;
  const [flagStatus, flag] = await request("GET", flagPath(), undefined, FLAG_API_VERSION);
  const instructions = [];
  if (flagStatus === 200 && flag && typeof flag === "object") {
    for (const ruleId of phaseRuleIds(flag)) instructions.push({ kind: "removeRule", ruleId });
  }
  instructions.push({ kind: "turnFlagOff" });
  const [status, payload] = await request("PATCH", flagPath(), {
    environmentKey: apiConfig().environment,
    comment: "23-api-guarded-rollout: reset, flag off, phase rule removed",
    instructions,
  }, FLAG_API_VERSION, "application/json; domain-model=launchdarkly.semanticpatch");
  if (status >= 400) return apiError(status, payload);
  const summary = await latestGuardedRelease();
  summary.reset = true;
  summary.flagOn = false;
  summary.active = false;
  summary.headline = "Flag is off. Every context receives none.";
  return summary;
}

module.exports = {
  schedule,
  targetingUrl,
  startBody,
  latestGuardedRelease,
  startGuardedRelease,
  stopGuardedRelease,
  resetDemo,
};

if (require.main === module) {
  const body = startBody("none-id", "green-id");
  const steps = body.phases[0].steps;
  if (steps.map((step) => step.allocation).join() !== "10000,20000,30000,50000") process.exit(1);
  if (steps.map((step) => step.durationMillis).join() !== "120000,120000,60000,60000") process.exit(1);
  if (body.metrics.map((item) => item.metricKey).join() !== "grid-nav-latency,grid-highlight-error-rate,grid-nav-movement") process.exit(1);
  console.log("ok", body.metrics.length);
}
