/** Approval request for the move-count flag.
 *
 * The page asks LaunchDarkly to turn the flag on. A person approves that
 * request in LaunchDarkly. This module applies it only after that review.
 *
 * Approvals
 * https://launchdarkly.com/docs/home/releases/approvals
 *
 * Create an approval request for a flag
 * https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
 */

const fs = require("fs");
const path = require("path");

const FLAG_KEY = "show-navigation-move-count-approval";
const DESCRIPTION = "Turn on the move count";
const API_HOST = process.env.LD_API_HOST || "https://app.launchdarkly.com";
const API_VERSION = process.env.LD_API_VERSION || "20240415";

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
    flagKey: FLAG_KEY,
    appOrigin: API_HOST.replace(/\/+$/, ""),
  };
}

async function request(method, apiPath, body, semantic = false) {
  const config = apiConfig();
  if (!config.configured) {
    throw new Error(`Approvals need ${config.missing.join(", ")}.`);
  }
  const headers = {
    Authorization: process.env.LD_API_ACCESS_TOKEN.trim(),
    "LD-API-Version": API_VERSION,
    Accept: "application/json",
  };
  if (body !== undefined) {
    headers["Content-Type"] = semantic
      ? "application/json; domain-model=launchdarkly.semanticpatch"
      : "application/json";
  }
  const response = await fetch(`${API_HOST.replace(/\/+$/, "")}/api/v2${apiPath}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(30_000),
  });
  const raw = await response.text();
  if (!response.ok) {
    throw new Error(`LaunchDarkly ${response.status}: ${raw.slice(0, 300)}`);
  }
  return raw ? JSON.parse(raw) : {};
}

function summary(item) {
  const applied = item.appliedDate != null || item.status === "completed";
  return {
    id: item._id,
    reviewStatus: item.reviewStatus || "pending",
    status: item.status || "pending",
    applied: Boolean(applied),
    description: item.description || DESCRIPTION,
  };
}

function currentRequest(items) {
  const ranked = [];
  for (const item of items) {
    const row = summary(item);
    if (row.applied || row.status === "completed" || row.status === "failed") continue;
    ranked.push([item.creationDate || 0, row]);
  }
  ranked.sort((left, right) => right[0] - left[0]);
  for (const [, row] of ranked) {
    if (row.reviewStatus !== "declined") return row;
  }
  return ranked.length ? ranked[0][1] : null;
}

function flagPath(config) {
  return (
    `/projects/${encodeURIComponent(config.projectKey)}/flags/${encodeURIComponent(FLAG_KEY)}` +
    `/environments/${encodeURIComponent(config.environmentKey)}/approval-requests`
  );
}

async function approvalState() {
  const config = apiConfig();
  if (!config.configured) return { ...config, ok: true, request: null };
  const payload = await request("GET", flagPath(config));
  const items = Array.isArray(payload.items) ? payload.items : [];
  return { ...config, ok: true, request: currentRequest(items) };
}

/** Next approval name. `.request-count` is shared with Python, Java, and .NET. */
function nextDescription() {
  const root = path.resolve(__dirname, "..");
  const counter = path.join(root, ".request-count");
  const lock = path.join(root, ".request-count.lock");
  const deadline = Date.now() + 2000;
  while (true) {
    try {
      fs.closeSync(fs.openSync(lock, "wx"));
      break;
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      if (Date.now() <= deadline) {
        const until = Date.now() + 50;
        while (Date.now() < until) {}
        continue;
      }
      try {
        if (Date.now() - fs.statSync(lock).mtimeMs > 5000) {
          fs.rmSync(lock, { force: true });
          continue;
        }
      } catch (missing) {
        if (missing.code === "ENOENT") continue;
      }
      throw new Error("Approval counter is locked.");
    }
  }
  try {
    let current = 0;
    if (fs.existsSync(counter)) {
      const raw = fs.readFileSync(counter, "utf8").trim();
      if (/^\d+$/.test(raw)) current = Number(raw);
    }
    const next = current + 1;
    const temporary = path.join(root, ".request-count.tmp");
    fs.writeFileSync(temporary, `${next}\n`);
    fs.renameSync(temporary, counter);
    return `${DESCRIPTION} · ${next}`;
  } finally {
    fs.rmSync(lock, { force: true });
  }
}

/** LaunchDarkly: approval request · semantic patch turnFlagOn */
async function requestApproval() {
  const current = await approvalState();
  const existing = current.request || {};
  if (existing.id && existing.reviewStatus !== "declined" && !existing.applied) {
    return {
      ...current,
      steps: [{
        where: "Lab API",
        text: "Open request reused. LaunchDarkly was not asked for a second one.",
      }],
    };
  }
  const description = nextDescription();
  const created = await request(
    "POST",
    flagPath(apiConfig()),
    {
      description,
      comment: "108-flag-approvals",
      instructions: [{ kind: "turnFlagOn" }],
    },
    true,
  );
  const row = summary(created);
  return {
    ...apiConfig(),
    ok: true,
    request: row,
    steps: [{
      where: "LaunchDarkly",
      text: `POST approval-requests · turnFlagOn · ${description} · review ${row.reviewStatus}`,
    }],
  };
}

/** LaunchDarkly: apply approval request */
async function applyApproval(requestId) {
  const id = String(requestId || "").trim();
  if (!id) throw new Error("Approval id is required");
  const config = apiConfig();
  const applied = await request("POST", `${flagPath(config)}/${encodeURIComponent(id)}/apply`, {
    comment: "108-flag-approvals apply",
  });
  const row = summary(applied);
  return {
    ...config,
    ok: true,
    request: row,
    steps: [{
      where: "LaunchDarkly",
      text: `POST approval-requests/${id}/apply · status ${row.status}`,
    }],
  };
}

async function resetDemo() {
  const config = apiConfig();
  if (!config.configured) throw new Error(`Approvals need ${config.missing.join(", ")}.`);
  const steps = [];
  const seen = new Map();
  const flagItems = await request("GET", flagPath(config));
  for (const item of Array.isArray(flagItems.items) ? flagItems.items : []) {
    if (item && item._id) seen.set(item._id, item);
  }
  const resource = `proj/${config.projectKey}:env/${config.environmentKey}:flag/${FLAG_KEY}`;
  try {
    const archived = await request(
      "GET",
      `/approval-requests?limit=20&filter=${encodeURIComponent(`resourceId equals ${resource}`)}`,
    );
    for (const item of Array.isArray(archived.items) ? archived.items : []) {
      if (item && item._id) seen.set(item._id, item);
    }
  } catch {
    // The flag list is enough when the account list is unavailable.
  }
  const items = [...seen.values()];
  if (!items.length) {
    steps.push({ where: "LaunchDarkly", text: "GET approval-requests · none to delete" });
  }
  for (const item of items) {
    const id = item._id;
    if (!id) continue;
    try {
      await request("DELETE", `${flagPath(config)}/${encodeURIComponent(id)}`);
      steps.push({ where: "LaunchDarkly", text: `DELETE approval-requests/${id}` });
    } catch (error) {
      steps.push({ where: "LaunchDarkly", text: `DELETE approval-requests/${id} · ${error.message}` });
    }
  }
  let patched;
  try {
    patched = await request(
      "PATCH",
      `/flags/${encodeURIComponent(config.projectKey)}/${encodeURIComponent(FLAG_KEY)}`,
      {
        environmentKey: config.environmentKey,
        comment: "108-flag-approvals reset",
        instructions: [{ kind: "turnFlagOff" }],
      },
      true,
    );
  } catch (error) {
    error.steps = steps;
    throw error;
  }
  const environment = patched.environments && patched.environments[config.environmentKey];
  const on = environment ? environment.on : null;
  steps.push({ where: "LaunchDarkly", text: `PATCH flag · turnFlagOff · on ${on}` });
  return { ...config, ok: true, request: null, steps };
}

module.exports = {
  FLAG_KEY,
  apiConfig,
  approvalState,
  requestApproval,
  applyApproval,
  resetDemo,
};
