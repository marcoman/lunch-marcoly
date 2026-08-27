using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate the progressive-rollout highlight flag for one user context.
/// LaunchDarkly: server-side string variation.
/// https://launchdarkly.com/docs/sdk/features/evaluations
/// </summary>
sealed class HighlightEval : IDisposable
{
    internal const string FlagHighlight = "enable-grid-selection-highlight";
    private static readonly HashSet<string> ValidColors =
        new(StringComparer.OrdinalIgnoreCase) { "yellow", "red", "blue", "green", "purple" };
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

    internal object Evaluate(string username)
    {
        var raw = "none";
        if (_client is { Initialized: true } && !string.IsNullOrWhiteSpace(username))
            raw = _client.StringVariation(FlagHighlight, Context.New(username), "none");
        var color = ValidColors.Contains(raw.Trim()) ? raw.Trim().ToLowerInvariant() : "none";
        return new
        {
            username,
            flagValue = raw,
            highlightColor = color,
            colorLabel = color == "none" ? "(no-color)" : $"({color})",
        };
    }

    public void Dispose() => _client?.Dispose();
}
