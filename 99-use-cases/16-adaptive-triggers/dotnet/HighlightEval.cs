using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Server-side string variation and numeric custom events for the adaptive trigger.
/// LaunchDarkly: evaluations and custom metric track.
/// https://launchdarkly.com/docs/sdk/features/evaluations
/// https://launchdarkly.com/docs/sdk/features/events
/// </summary>
sealed class HighlightEval : IDisposable
{
    internal const string FlagHighlight = "enable-adaptive-grid-highlight";
    internal const string EventKey = "adaptive-grid-nav-latency";
    internal const string FlagName = "Enable: adaptive grid highlight";
    internal const string MetricKey = "adaptive-grid-nav-latency-metric";
    internal const string LiveValue = "green";
    internal const int ThresholdMs = 200;
    private static readonly HashSet<string> ValidColors = new(StringComparer.OrdinalIgnoreCase) { "green" };
    private readonly LdClient? _client;

    internal HighlightEval()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.Error.WriteLine("Warning: LD_SDK_KEY is unset — evaluation stays at code fallback none.");
            return;
        }

        _client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(10)).Build());
        if (!_client.Initialized)
        {
            Console.Error.WriteLine("Warning: LaunchDarkly initialization failed — evaluation stays at code fallback none.");
            _client.Dispose();
            _client = null;
        }
    }

    internal bool Initialized => _client is { Initialized: true };

    internal object Evaluate(string username)
    {
        var raw = "none";
        if (Initialized && !string.IsNullOrWhiteSpace(username))
            raw = _client!.StringVariation(FlagHighlight, BuildContext(username), "none");
        return BuildResponse(username, raw);
    }

    /// <summary>
    /// Send the slider value as a numeric custom metric and flush so the lab can see it promptly.
    /// </summary>
    internal void TrackLatency(string username, double latencyMs)
    {
        if (!Initialized)
            throw new InvalidOperationException("LD_SDK_KEY is missing or the SDK did not initialize.");
        var data = LdValue.BuildObject().Add("source", "16-adaptive-triggers").Build();
        _client!.Track(EventKey, BuildContext(username), data, latencyMs);
        _client.Flush();
    }

    internal static Context BuildContext(string username) => Context.New(username);

    internal static object BuildResponse(string username, string? raw)
    {
        var value = (raw ?? "none").Trim().ToLowerInvariant();
        var highlightColor = ValidColors.Contains(value) ? value : "none";
        return new
        {
            username,
            flagValue = value,
            highlightColor,
            colorLabel = highlightColor == "none" ? "(no-color)" : $"({highlightColor})",
        };
    }

    public void Dispose() => _client?.Dispose();
}
