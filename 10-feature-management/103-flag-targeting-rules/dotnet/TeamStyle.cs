using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluates the team-label string flag against the public team context attribute.
/// Targeting rules: https://launchdarkly.com/docs/home/flags/target-rules
/// </summary>
sealed class TeamStyle : IDisposable
{
    public const string FlagKey = "configure-team-label-style";
    // JSON flag: words on screen. Style values stay colored-red/blue/yellow/plain.
    // https://launchdarkly.com/docs/sdk/features/flag-types
    public const string LabelsKey = "configure-team-display-labels";
    private const string Plain = "plain";
    private static readonly Dictionary<string, string> Labels = new()
    {
        [""] = "No team",
        ["red"] = "Team Red",
        ["blue"] = "Team Blue",
        ["yellow"] = "Team Yellow",
    };
    private static readonly Dictionary<string, string?> Colors = new()
    {
        [Plain] = null,
        ["colored-red"] = "red",
        ["colored-blue"] = "blue",
        ["colored-yellow"] = "yellow",
    };
    private readonly LdClient? _client;

    public TeamStyle()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — flag uses plain default.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey)
            .StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize — flag uses plain default.");
    }

    public object Evaluate(string username, string? rawTeam)
    {
        var team = NormalizeTeam(rawTeam);
        var context = BuildContext(username, team);
        var detail = _client?.StringVariationDetail(FlagKey, context, Plain);
        var candidate = detail?.Value ?? Plain;
        var style = Colors.ContainsKey(candidate) ? candidate : Plain;
        var color = Colors[style];
        var labels = ReadLabels(context, out var labelIndex, out var labelReason);
        return new
        {
            team,
            teamLabel = labels[team.Length == 0 ? "none" : team],
            labels,
            style,
            colored = color is not null,
            cssColor = color,
            ldContext = new
            {
                kind = "user",
                key = username,
                attributes = team.Length == 0
                    ? new Dictionary<string, string>()
                    : new Dictionary<string, string> { ["team"] = team },
                teamAttribute = team.Length == 0 ? null : team,
                teamOmitted = team.Length == 0,
                privateAttributes = Array.Empty<string>(),
                note = "team is public; No team omits the attribute so rules skip to fallthrough.",
            },
            variationIndex = detail?.VariationIndex,
            reason = detail is null ? new { kind = "OFFLINE" } : ReasonPayload(detail.Value.Reason),
            labelEvaluation = new
            {
                flagKey = LabelsKey,
                value = labels,
                variationIndex = labelIndex,
                reason = labelReason,
            },
        };
    }

    private static Dictionary<string, string> DefaultLabels() => new()
    {
        ["none"] = Labels[""],
        ["red"] = Labels["red"],
        ["blue"] = Labels["blue"],
        ["yellow"] = Labels["yellow"],
    };

    /// <summary>One JSON-flag read. Missing keys keep the built-in words.</summary>
    private Dictionary<string, string> ReadLabels(
        Context context, out int? variationIndex, out object reason)
    {
        var labels = DefaultLabels();
        if (_client is null)
        {
            variationIndex = null;
            reason = new { kind = "OFFLINE" };
            return labels;
        }
        var fallback = LdValue.Parse(
            "{\"none\":\"No team\",\"red\":\"Team Red\",\"blue\":\"Team Blue\",\"yellow\":\"Team Yellow\"}");
        var detail = _client.JsonVariationDetail(LabelsKey, context, fallback);
        if (detail.Value.Type == LdValueType.Object)
        {
            foreach (var key in new[] { "none", "red", "blue", "yellow" })
            {
                var text = detail.Value.Get(key);
                if (text.Type == LdValueType.String && !string.IsNullOrWhiteSpace(text.AsString))
                    labels[key] = text.AsString.Trim();
            }
        }
        variationIndex = detail.VariationIndex;
        reason = ReasonPayload(detail.Reason);
        return labels;
    }

    private static string NormalizeTeam(string? raw)
    {
        var team = (raw ?? "").Trim().ToLowerInvariant();
        if (!Labels.ContainsKey(team))
            throw new ArgumentException("team must be empty, red, blue, or yellow");
        return team;
    }

    /// <summary>
    /// Builds a user context and omits team entirely for No team.
    /// Context attributes: https://launchdarkly.com/docs/home/flags/context-attributes
    /// </summary>
    private static Context BuildContext(string username, string team)
    {
        var builder = Context.Builder(username);
        if (team.Length > 0) builder.Set("team", team);
        return builder.Build();
    }

    private static object ReasonPayload(EvaluationReason reason)
    {
        var payload = new Dictionary<string, object?> { ["kind"] = reason.Kind.ToString() };
        if (reason.Kind == EvaluationReasonKind.RuleMatch)
        {
            payload["ruleIndex"] = reason.RuleIndex;
            payload["ruleId"] = reason.RuleId;
        }
        if (reason.Kind == EvaluationReasonKind.Error)
            payload["errorKind"] = reason.ErrorKind.ToString();
        return payload;
    }

    public void Dispose() => _client?.Dispose();
}
