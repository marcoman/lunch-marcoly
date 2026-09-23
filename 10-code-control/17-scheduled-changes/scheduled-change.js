/** LaunchDarkly evaluation and REST helpers for scheduled flag changes.
 *
 * Scheduled changes API:
 * https://launchdarkly.com/docs/api/scheduled-changes
 */

const FLAG_KEY = "enable-grid-selection-highlight-sched";
const DEFAULT_VALUE = "none";
const API_HOST = process.env.LD_API_HOST || "https://app.launchdarkly.com";
const API_VERSION = process.env.LD_API_VERSION || "20240415";

function normalizeUsername(value) {
  const username = String(value || "").trim();
  if (!username) throw new Error("Username is required.");
  return username;
}

// LaunchDarkly: detailed feature-flag evaluation exposes the evaluation reason.
// https://launchdarkly.com/docs/sdk/features/evaluating#evaluation-reasons
async function evaluateHighlight(client, usernameValue) {
  const username = normalizeUsername(usernameValue);
  const context = { kind: "user", key: username, name: username };
  if (!client) {
    return {
      flagKey: FLAG_KEY,
      flagValue: DEFAULT_VALUE,
      highlightColor: DEFAULT_VALUE,
      variationIndex: null,
      reason: { kind: "ERROR", errorKind: "CLIENT_NOT_READY" },
      ldContext: context,
    };
  }

  const detail = await client.variationDetail(FLAG_KEY, context, DEFAULT_VALUE);
  const value = new Set(["none", "green"]).has(detail.value) ? detail.value : DEFAULT_VALUE;
  return {
    flagKey: FLAG_KEY,
    flagValue: value,
    highlightColor: value,
    variationIndex: detail.variationIndex ?? null,
    reason: detail.reason,
    ldContext: context,
  };
}

function apiConfig() {
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

async function request(method, apiPath, body, { semanticPatch = false } = {}) {
  const config = apiConfig();
  if (!config.configured) {
    throw new Error(`Scheduled changes need ${config.missing.join(", ")}`);
  }
  const headers = {
    Authorization: process.env.LD_API_ACCESS_TOKEN.trim(),
    "LD-API-Version": API_VERSION,
    Accept: "application/json",
  };
  if (body) {
    headers["Content-Type"] = semanticPatch
      ? "application/json; domain-model=launchdarkly.semanticpatch"
      : "application/json";
  }
  const response = await fetch(`${API_HOST.replace(/\/+$/, "")}/api/v2${apiPath}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30_000),
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
  if (!response.ok) {
    throw new Error(`LaunchDarkly API ${response.status}: ${payload.message || raw}`);
  }
  return payload;
}

function basePath() {
  const config = apiConfig();
  return `/projects/${encodeURIComponent(config.projectKey || "")}/flags/${encodeURIComponent(
    FLAG_KEY,
  )}/environments/${encodeURIComponent(config.environmentKey || "")}/scheduled-changes`;
}

async function deletePendingChanges() {
  const base = basePath();
  let deleted = 0;
  const response = await request("GET", base);
  for (const item of response.items || []) {
    if (item._id) {
      await request("DELETE", `${base}/${encodeURIComponent(item._id)}`);
      deleted += 1;
    }
  }
  return deleted;
}

// LaunchDarkly semantic patch: reset the environment before changing schedules.
// https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
async function turnFlagOff(comment) {
  const config = apiConfig();
  await request(
    "PATCH",
    `/flags/${encodeURIComponent(config.projectKey)}/${encodeURIComponent(FLAG_KEY)}`,
    {
      environmentKey: config.environmentKey,
      comment,
      instructions: [{ kind: "turnFlagOff" }],
    },
    { semanticPatch: true },
  );
}

async function listScheduledChanges() {
  const config = apiConfig();
  if (!config.configured) return { ...config, items: [] };
  const response = await request("GET", basePath());
  const items = (response.items || [])
    .sort((left, right) => (left.executionDate || 0) - (right.executionDate || 0))
    .map((item) => ({
      id: item._id,
      createdAt: item._creationDate,
      executionDate: item.executionDate,
      instructions: item.instructions || [],
    }));
  return { ...config, items };
}

async function startScheduledChange(minutes) {
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > 60) {
    throw new Error("minutes must be between 1 and 60");
  }
  const deleted = await deletePendingChanges();
  await turnFlagOff("17-scheduled-changes: reset off before starting demo");

  const now = Date.now();
  const executionDate = now + minutes * 60_000;
  const created = await request("POST", basePath(), {
    executionDate,
    instructions: [{ kind: "turnFlagOn" }],
    comment: `17-scheduled-changes: turn highlight on after ${minutes} minute(s)`,
  });
  return {
    ok: true,
    replacedCount: deleted,
    minutes,
    startedAt: now,
    scheduledChange: {
      id: created._id,
      createdAt: created._creationDate || now,
      executionDate: created.executionDate || executionDate,
      instructions: created.instructions || [{ kind: "turnFlagOn" }],
    },
  };
}

async function stopScheduledChange() {
  const cancelled = await deletePendingChanges();
  await turnFlagOff("17-scheduled-changes: stop demo and turn highlight off");
  return { ok: true, cancelledCount: cancelled, stoppedAt: Date.now() };
}

module.exports = {
  FLAG_KEY,
  apiConfig,
  evaluateHighlight,
  listScheduledChanges,
  normalizeUsername,
  startScheduledChange,
  stopScheduledChange,
};
