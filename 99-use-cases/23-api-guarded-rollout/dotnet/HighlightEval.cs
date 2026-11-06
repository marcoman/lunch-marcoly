using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate api-guarded-grid-highlight for one username.
/// The schedule lives in an environment release. This only reads the variation.
/// LaunchDarkly: string flag variation
/// https://launchdarkly.com/docs/sdk/features/evaluations
/// </summary>
sealed class HighlightEval : IDisposable
{
    internal const string FlagHighlight = "api-guarded-grid-highlight";
    private static readonly HashSet<string> ValidColors =
        new(StringComparer.OrdinalIgnoreCase) { "yellow", "red", "blue", "green", "purple" };
    private readonly LdClient? _client;

    internal HighlightEval()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
            return;
        _client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(10)).Build());
        if (!_client.Initialized)
        {
            _client.Dispose();
            _client = null;
        }
    }

    internal bool Ready => _client is { Initialized: true };

    internal JsonObject Evaluate(string username)
    {
        if (!Ready)
            return Build(username, "none", "ERROR", null);
        var detail = _client!.StringVariationDetail(FlagHighlight, ContextFor(username), "none");
        return Build(username, detail.Value, ReasonKind(detail.Reason), detail.VariationIndex);
    }

    /// <summary>
    /// Green contexts report the slider. None contexts report 50 ms.
    /// LaunchDarkly: custom events with a numeric metric value.
    /// https://launchdarkly.com/docs/sdk/features/events
    /// </summary>
    internal JsonObject TrackObserved(string username, double latencyMs)
    {
        var green = 0;
        var none = 0;
        foreach (var name in Metrics.SampleUsernames(username))
        {
            var served = Evaluate(name)["highlightColor"]?.GetValue<string>();
            var value = served == "green" ? latencyMs : Metrics.HealthyLatencyMs;
            var context = ContextFor(name);
            _client!.Track(Metrics.EventLatency, context, LdValue.Null, value);
            _client.Track(Metrics.EventMovement, context, LdValue.Null, 1);
            if (served == "green") green += 1;
            else none += 1;
        }
        _client!.Flush();
        return new JsonObject
        {
            ["tracked"] = true,
            ["latencyMs"] = latencyMs,
            ["healthyMs"] = Metrics.HealthyLatencyMs,
            ["aboveThreshold"] = latencyMs > Metrics.LatencyThresholdMs,
            ["greenContexts"] = green,
            ["noneContexts"] = none,
            ["movement"] = 1,
            ["colorErrors"] = 0,
            ["latencyEvent"] = Metrics.EventLatency,
            ["movementEvent"] = Metrics.EventMovement,
        };
    }

    internal static Context ContextFor(string username) => Context.Builder(username).Name(username).Build();

    private static string ReasonKind(EvaluationReason reason) => reason.Kind switch
    {
        EvaluationReasonKind.Off => "OFF",
        EvaluationReasonKind.Fallthrough => "FALLTHROUGH",
        EvaluationReasonKind.TargetMatch => "TARGET_MATCH",
        EvaluationReasonKind.RuleMatch => "RULE_MATCH",
        EvaluationReasonKind.PrerequisiteFailed => "PREREQUISITE_FAILED",
        EvaluationReasonKind.Error => "ERROR",
        _ => "UNKNOWN",
    };

    private static JsonObject Build(string username, string? raw, string reasonKind, int? variationIndex)
    {
        var color = ValidColors.Contains((raw ?? "none").Trim())
            ? (raw ?? "none").Trim().ToLowerInvariant()
            : "none";
        return new JsonObject
        {
            ["username"] = username,
            ["flagKey"] = FlagHighlight,
            ["flagValue"] = raw ?? "none",
            ["highlightColor"] = color,
            ["colorLabel"] = color == "none" ? "(no-color)" : $"({color})",
            ["variationIndex"] = variationIndex,
            ["reason"] = new JsonObject { ["kind"] = reasonKind },
            ["ldContext"] = new JsonObject
            {
                ["kind"] = "user",
                ["key"] = username,
                ["name"] = username,
            },
        };
    }

    public void Dispose() => _client?.Dispose();
}
