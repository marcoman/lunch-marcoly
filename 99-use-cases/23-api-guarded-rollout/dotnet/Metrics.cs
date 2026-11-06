using System.Text.Json.Nodes;

/// <summary>
/// Guardrail metrics for the guarded environment release.
/// LaunchDarkly: custom metrics
/// https://launchdarkly.com/docs/home/metrics/custom-metrics
/// </summary>
static class Metrics
{
    internal const int LatencyThresholdMs = 200;
    internal const double HealthyLatencyMs = 50;
    internal const int SampleCount = 24;
    internal const string EventLatency = "grid-navigation-latency";
    internal const string EventMovement = "grid-navigation-count";

    internal static JsonArray Views()
    {
        var views = new JsonArray();
        foreach (var item in Definitions())
        {
            views.Add(new JsonObject
            {
                ["key"] = item["key"]?.DeepClone(),
                ["name"] = item["name"]?.DeepClone(),
                ["eventKey"] = item["eventKey"]?.DeepClone(),
                ["description"] = item["description"]?.DeepClone(),
                ["role"] = item["role"]?.DeepClone(),
            });
        }
        return views;
    }

    internal static IEnumerable<JsonObject> Definitions()
    {
        yield return Metric(
            "grid-nav-latency",
            "Grid navigation latency",
            "Milliseconds reported for one grid move. Lower is better. " +
            "Above 200 ms is the latency guardrail. " +
            "In 23-api-guarded-rollout, contexts receiving green send the slider value " +
            "and contexts still on none send 50 ms, so a high slider makes the new variation look slower. " +
            "In 15-guarded-rollout a harness draws a random delay.",
            EventLatency,
            true,
            "milliseconds",
            "average",
            "mean",
            "LowerThanBaseline",
            "violation",
            "latency");
        yield return Metric(
            "grid-highlight-error-rate",
            "Grid highlight error rate",
            "One event means the selected cell showed the wrong highlight color. " +
            "Lower is better. The guardrail is 0% errors. " +
            "23-api-guarded-rollout sends no events, so this guardrail stays normal " +
            "while you watch latency.",
            "grid-highlight-color-error",
            false,
            null,
            null,
            null,
            "LowerThanBaseline",
            "normal",
            "error-rate");
        yield return Metric(
            "grid-nav-movement",
            "Grid navigation movement",
            "How many times the user moved on the grid. Higher is better. " +
            "The guardrail is at least one navigation. " +
            "23-api-guarded-rollout sends 1 on each move and each automatic report, " +
            "so this guardrail stays normal.",
            EventMovement,
            true,
            "navigations",
            "sum",
            "mean",
            "HigherThanBaseline",
            "normal",
            "movement");
    }

    internal static JsonObject CreateBody(JsonObject definition)
    {
        var body = definition.DeepClone().AsObject();
        body.Remove("role");
        return body;
    }

    internal static IEnumerable<string> SampleUsernames(string username)
    {
        yield return username;
        for (var index = 1; index < SampleCount; index += 1)
            yield return $"{username}-{index}";
    }

    private static JsonObject Metric(
        string key,
        string name,
        string description,
        string eventKey,
        bool numeric,
        string? unit,
        string? unitAggregationType,
        string? analysisType,
        string successCriteria,
        string role,
        string tag)
    {
        var body = new JsonObject
        {
            ["key"] = key,
            ["name"] = name,
            ["description"] = description,
            ["kind"] = "custom",
            ["isNumeric"] = numeric,
            ["eventKey"] = eventKey,
            ["successCriteria"] = successCriteria,
            ["analysisUnits"] = new JsonArray("user"),
            ["tags"] = new JsonArray("grid-navigator", "use-case", "guarded-rollout", tag),
            ["role"] = role,
        };
        if (numeric)
        {
            body["unit"] = unit;
            body["unitAggregationType"] = unitAggregationType;
            body["analysisType"] = analysisType;
        }
        return body;
    }
}
