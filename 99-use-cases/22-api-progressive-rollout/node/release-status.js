/**
 * Read and start the progressive environment release for this example.
 *
 * LaunchDarkly: environment releases — kind progressive
 * https://launchdarkly.com/docs/api/environment-releases
 */

const { FLAG_HIGHLIGHT } = require("./highlight-eval");

const ALLOCATION_SCALE = 1000;
const ROLLOUT_PERCENTAGES = [10, 20, 40, 60, 100];
const STAGE_SECONDS = Number(process.env.STAGE_SECONDS || 60);
const RANDOMIZATION_UNIT = "user";
const FLAG_API_VERSION = process.env.LD_API_VERSION || "20240415";

function apiConfig() {
  return {
    host: (process.env.LD_API_HOST || "https://app.launchdarkly.com").replace(/\/$/, ""),
    token: process.env.LD_API_ACCESS_TOKEN || "",
    project: process.env.LD_PROJECT_KEY || "",
    environment: process.env.LD_ENVIRONMENT_KEY || "",
  };
}

function schedule() {
  return ROLLOUT_PERCENTAGES.map((percent) => ({ percent, durationSeconds: STAGE_SECONDS }));
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

function summarizeRelease(item) {
  const phases = item.phases || [];
  const phase = phases[0] || {};
  const steps = (phase.steps || []).map(stepView);
  const index = phase.currentStepIndex;
  const current = Number.isInteger(index) && index >= 0 && index < steps.length ? steps[index] : null;
  const ended = item.endedAt != null || item.status === "completed" || item.status === "reverted";
  return {
    configured: true,
    flagKey: FLAG_HIGHLIGHT,
    kind: item.kind,
    status: item.status,
    statusReason: item.statusReason,
    randomizationUnit: item.randomizationUnit,
    metricCount: (item.metrics || []).length,
    hasRule: Boolean(phase.ruleId),
    stepIndex: index,
    stepCount: steps.length,
    currentPercent: current ? current.percent : null,
    steps,
    active: !ended,
  };
}

function releasesPath() {
  const cfg = apiConfig();
  return `/api/v2/projects/${cfg.project}/flags/${FLAG_HIGHLIGHT}/environments/${cfg.environment}/releases`;
}

async function flagIsOn() {
  const cfg = apiConfig();
  if (!cfg.token || !cfg.project || !cfg.environment) return null;
  const query = new URLSearchParams({ env: cfg.environment });
  const [status, flag] = await request(
    "GET",
    `/api/v2/flags/${cfg.project}/${FLAG_HIGHLIGHT}?${query}`,
    undefined,
    FLAG_API_VERSION,
  );
  if (status !== 200 || !flag || typeof flag !== "object") return null;
  const environment = (flag.environments || {})[cfg.environment] || {};
  return Boolean(environment.on);
}

async function latestProgressiveRelease() {
  const missing = missingConfig();
  if (missing) return missing;
  const query = new URLSearchParams({ queryfilter: "kind:equals:progressive", limit: "1" });
  const [status, payload] = await request("GET", `${releasesPath()}?${query}`);
  if (status !== 200 || !payload || typeof payload !== "object") {
    return apiError(status, payload);
  }
  const items = payload.items || [];
  const summary = items.length
    ? { ...summarizeRelease(items[0]), totalCount: payload.totalCount }
    : {
        configured: true,
        flagKey: FLAG_HIGHLIGHT,
        status: "none",
        metricCount: 0,
        steps: [],
        detail: "No progressive release on this flag yet.",
      };
  summary.flagOn = await flagIsOn();
  if (summary.flagOn === false) summary.active = false;
  return summary;
}

function startBody(originalVariationId, targetVariationId) {
  const durationMillis = STAGE_SECONDS * 1000;
  return {
    originalVariationId,
    targetVariationId,
    randomizationUnit: RANDOMIZATION_UNIT,
    cleanupBehavior: "remove_rules_and_update_default_rule",
    comment: "22-api-progressive-rollout: start progressive release",
    phases: [
      {
        description: "All users",
        clauses: [
          {
            contextKind: RANDOMIZATION_UNIT,
            attribute: "kind",
            op: "in",
            values: [RANDOMIZATION_UNIT],
          },
        ],
        steps: ROLLOUT_PERCENTAGES.map((percent) => ({
          allocation: percent * ALLOCATION_SCALE,
          durationMillis,
        })),
      },
    ],
  };
}

function phaseRuleIds(flag) {
  // A stopped release leaves its phase rule. The next start rejects a duplicate description.
  const environment = (flag.environments || {})[apiConfig().environment] || {};
  return (environment.rules || [])
    .map((rule) => rule && (rule._id || rule.id))
    .filter((ruleId) => typeof ruleId === "string");
}

function variationId(flag, value) {
  for (const item of flag.variations || []) {
    if (item.value === value && item._id) return String(item._id);
  }
  return null;
}

async function startProgressiveRelease() {
  // LaunchDarkly: start an environment release. Header LD-API-Version: beta.
  // https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
  const missing = missingConfig();
  if (missing) return missing;
  const cfg = apiConfig();
  const flagPath = `/api/v2/flags/${cfg.project}/${FLAG_HIGHLIGHT}`;
  const [status, flag] = await request("GET", flagPath, undefined, FLAG_API_VERSION);
  if (status === 404) {
    return {
      configured: true,
      flagKey: FLAG_HIGHLIGHT,
      error: true,
      http: status,
      detail: "Flag not found. Run rest/create-flag.sh, then start again.",
    };
  }
  if (status !== 200 || !flag || typeof flag !== "object") return apiError(status, flag);
  const noneId = variationId(flag, "none");
  const greenId = variationId(flag, "green");
  if (!noneId || !greenId) {
    return {
      configured: true,
      flagKey: FLAG_HIGHLIGHT,
      error: true,
      detail: "The flag is missing the none or green variation.",
    };
  }
  const [patchStatus, patched] = await request(
    "PATCH",
    flagPath,
    {
      environmentKey: cfg.environment,
      comment: "22-api-progressive-rollout: on, default rule stays none",
      instructions: [
        ...phaseRuleIds(flag).map((ruleId) => ({ kind: "removeRule", ruleId })),
        { kind: "turnFlagOn" },
        { kind: "updateFallthroughVariationOrRollout", variationId: noneId },
      ],
    },
    FLAG_API_VERSION,
    "application/json; domain-model=launchdarkly.semanticpatch",
  );
  if (patchStatus >= 400) return apiError(patchStatus, patched);
  const [startStatus, started] = await request("POST", releasesPath(), startBody(noneId, greenId));
  if (![200, 201].includes(startStatus) || !started || !started.phases) return apiError(startStatus, started);
  return { ...summarizeRelease(started), started: true };
}

async function stopProgressiveRelease() {
  // LaunchDarkly: stop an environment release
  // https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
  const missing = missingConfig();
  if (missing) return missing;
  const query = new URLSearchParams({ queryfilter: "kind:equals:progressive", limit: "5" });
  const [status, payload] = await request("GET", `${releasesPath()}?${query}`);
  if (status !== 200 || !payload || typeof payload !== "object") return apiError(status, payload);
  const active = (payload.items || []).find(
    (item) => item.endedAt == null && item.status !== "completed" && item.status !== "reverted",
  );
  if (!active || !active.id) {
    return {
      configured: true,
      flagKey: FLAG_HIGHLIGHT,
      error: true,
      code: "no_active_release",
      detail: "No active progressive release to stop.",
    };
  }
  const [stopStatus, stopped] = await request("PUT", `${releasesPath()}/${active.id}/stop`, {
    resolution: "roll_back_all_phases_and_remove_pending_phases",
    comment: "22-api-progressive-rollout: stop progressive release",
  });
  if (![200, 201].includes(stopStatus) || !stopped || typeof stopped !== "object") {
    return apiError(stopStatus, stopped);
  }
  return { ...summarizeRelease(stopped), stopped: true, flagOn: await flagIsOn() };
}

async function resetDemo() {
  // LaunchDarkly: turn a feature flag off
  // https://launchdarkly.com/docs/api/feature-flags/update-feature-flag
  const missing = missingConfig();
  if (missing) return missing;
  const stopped = await stopProgressiveRelease();
  if (stopped.error && stopped.code !== "no_active_release") return stopped;
  const cfg = apiConfig();
  const flagPath = `/api/v2/flags/${cfg.project}/${FLAG_HIGHLIGHT}`;
  const [flagStatus, flag] = await request("GET", flagPath, undefined, FLAG_API_VERSION);
  const instructions = [{ kind: "turnFlagOff" }];
  if (flagStatus === 200 && flag && typeof flag === "object") {
    instructions.unshift(...phaseRuleIds(flag).map((ruleId) => ({ kind: "removeRule", ruleId })));
  }
  const [status, payload] = await request(
    "PATCH",
    flagPath,
    {
      environmentKey: cfg.environment,
      comment: "22-api-progressive-rollout: reset, flag off, phase rule removed",
      instructions,
    },
    FLAG_API_VERSION,
    "application/json; domain-model=launchdarkly.semanticpatch",
  );
  if (status >= 400) return apiError(status, payload);
  const summary = await latestProgressiveRelease();
  summary.reset = true;
  summary.flagOn = false;
  summary.active = false;
  return summary;
}

module.exports = {
  schedule,
  targetingUrl,
  latestProgressiveRelease,
  startProgressiveRelease,
  stopProgressiveRelease,
  resetDemo,
};
