using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate api-progressive-grid-highlight for one username.
/// The schedule lives in an environment release. This only reads the variation.
/// LaunchDarkly: string flag variation
/// https://launchdarkly.com/docs/sdk/features/evaluations
/// </summary>
sealed class HighlightEval : IDisposable
{
    internal const string FlagHighlight = "api-progressive-grid-highlight";
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

    internal JsonObject Evaluate(string username)
    {
        var context = Context.Builder(username).Name(username).Build();
        if (_client is not { Initialized: true })
            return Build(username, "none", "ERROR", null);
        var detail = _client.StringVariationDetail(FlagHighlight, context, "none");
        return Build(username, detail.Value, detail.Reason.Kind.ToString().ToUpperInvariant(), detail.VariationIndex);
    }

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
