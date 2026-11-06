/**
 * Guardrail metrics for the guarded environment release.
 *
 * Same three checks as 15-guarded-rollout. Green contexts report the slider.
 * None contexts report 50 ms. Error-rate events are not sent.
 *
 * LaunchDarkly: custom metrics
 * https://launchdarkly.com/docs/home/metrics/custom-metrics
 */

const { buildContext, evaluateHighlight } = require("./highlight-eval");

const LATENCY_THRESHOLD_MS = 200;
const HEALTHY_LATENCY_MS = 50;
const SAMPLE_COUNT = 24;
const EVENT_LATENCY = "grid-navigation-latency";
const EVENT_MOVEMENT = "grid-navigation-count";

const METRIC_DEFINITIONS = [
  {
    key: "grid-nav-latency",
    name: "Grid navigation latency",
    description:
      "Milliseconds reported for one grid move. Lower is better. " +
      "Above 200 ms is the latency guardrail. " +
      "In 23-api-guarded-rollout, contexts receiving green send the slider value " +
      "and contexts still on none send 50 ms, so a high slider makes the new variation look slower. " +
      "In 15-guarded-rollout a harness draws a random delay.",
    kind: "custom",
    isNumeric: true,
    eventKey: EVENT_LATENCY,
    unit: "milliseconds",
    successCriteria: "LowerThanBaseline",
    analysisUnits: ["user"],
    unitAggregationType: "average",
    analysisType: "mean",
    tags: ["grid-navigator", "use-case", "guarded-rollout", "latency"],
    role: "violation",
  },
  {
    key: "grid-highlight-error-rate",
    name: "Grid highlight error rate",
    description:
      "One event means the selected cell showed the wrong highlight color. " +
      "Lower is better. The guardrail is 0% errors. " +
      "23-api-guarded-rollout sends no events, so this guardrail stays normal " +
      "while you watch latency.",
    kind: "custom",
    isNumeric: false,
    eventKey: "grid-highlight-color-error",
    successCriteria: "LowerThanBaseline",
    analysisUnits: ["user"],
    tags: ["grid-navigator", "use-case", "guarded-rollout", "error-rate"],
    role: "normal",
  },
  {
    key: "grid-nav-movement",
    name: "Grid navigation movement",
    description:
      "How many times the user moved on the grid. Higher is better. " +
      "The guardrail is at least one navigation. " +
      "23-api-guarded-rollout sends 1 on each move and each automatic report, " +
      "so this guardrail stays normal.",
    kind: "custom",
    isNumeric: true,
    eventKey: EVENT_MOVEMENT,
    unit: "navigations",
    successCriteria: "HigherThanBaseline",
    analysisUnits: ["user"],
    unitAggregationType: "sum",
    analysisType: "mean",
    tags: ["grid-navigator", "use-case", "guarded-rollout", "movement"],
    role: "normal",
  },
];

function metricViews() {
  return METRIC_DEFINITIONS.map(({ key, name, eventKey, description, role }) => ({
    key, name, eventKey, description, role,
  }));
}

function createBody(definition) {
  const body = { ...definition };
  delete body.role;
  return body;
}

function sampleUsernames(username) {
  const names = [username];
  for (let index = 1; index < SAMPLE_COUNT; index += 1) names.push(`${username}-${index}`);
  return names;
}

async function trackObserved(client, username, latencyMs) {
  let green = 0;
  let none = 0;
  for (const name of sampleUsernames(username)) {
    const served = (await evaluateHighlight(client, name)).highlightColor;
    const value = served === "green" ? latencyMs : HEALTHY_LATENCY_MS;
    const context = buildContext(name);
    client.track(EVENT_LATENCY, context, null, value);
    client.track(EVENT_MOVEMENT, context, null, 1);
    if (served === "green") green += 1;
    else none += 1;
  }
  await client.flush();
  return {
    tracked: true,
    latencyMs,
    healthyMs: HEALTHY_LATENCY_MS,
    aboveThreshold: latencyMs > LATENCY_THRESHOLD_MS,
    greenContexts: green,
    noneContexts: none,
    movement: 1,
    colorErrors: 0,
    latencyEvent: EVENT_LATENCY,
    movementEvent: EVENT_MOVEMENT,
  };
}

module.exports = {
  LATENCY_THRESHOLD_MS,
  METRIC_DEFINITIONS,
  metricViews,
  createBody,
  trackObserved,
};
