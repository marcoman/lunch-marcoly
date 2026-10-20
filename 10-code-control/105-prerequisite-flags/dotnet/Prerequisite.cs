using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate the parent and dependent flags. LaunchDarkly enforces the prerequisite.
/// https://launchdarkly.com/docs/home/flags/prereqs
/// </summary>
sealed class Prerequisite : IDisposable
{
    public const string FlagHighlight = "enable-grid-selection-highlight-prereq";
    public const string FlagCount = "show-navigation-move-count-prereq";
    public static readonly HashSet<string> ValidColors =
        ["green", "yellow", "red", "blue", "purple", "pink"];
    private readonly LdClient? _client;

    public Prerequisite()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — flags use safe defaults.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey)
            .StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize.");
    }

    public object Evaluate(string rawUsername)
    {
        var username = NormalizeUsername(rawUsername);
        var context = Context.Builder(username).Kind("user").Build();
        var parentDetail = _client?.StringVariationDetail(FlagHighlight, context, "none");
        var childDetail = _client?.BoolVariationDetail(FlagCount, context, false);

        object parentValue = parentDetail?.Value ?? "none";
        var childValue = childDetail?.Value ?? false;
        var parentReason = parentDetail is null
            ? new Dictionary<string, object?> { ["kind"] = "OFFLINE" }
            : ReasonPayload(parentDetail.Value.Reason);
        var childReason = childDetail is null
            ? new Dictionary<string, object?> { ["kind"] = "OFFLINE" }
            : ReasonPayload(childDetail.Value.Reason);
        var prerequisiteFailed = Equals(childReason["kind"], "PREREQUISITE_FAILED");

        return new
        {
            username,
            highlightColor = HighlightColor(parentValue),
            showMoveCount = childValue,
            prerequisiteMet = _client is not null && Equals(parentValue, "green") && !prerequisiteFailed,
            ldContext = new { kind = "user", key = username },
            parent = new
            {
                key = FlagHighlight,
                value = parentValue,
                variationIndex = VariationIndex(parentDetail),
                reason = parentReason,
            },
            child = new
            {
                key = FlagCount,
                value = childValue,
                variationIndex = VariationIndex(childDetail),
                reason = childReason,
            },
        };
    }

    public static string NormalizeUsername(string? raw)
    {
        var username = (raw ?? "").Trim().ToLowerInvariant();
        if (username.Length == 0)
            throw new ArgumentException("username is required");
        return username;
    }

    private static int? VariationIndex<T>(EvaluationDetail<T>? detail)
    {
        if (detail is null) return null;
        var index = detail.Value.VariationIndex;
        return index < 0 ? null : index;
    }

    private static string HighlightColor(object value)
    {
        if (value is not string text) return "none";
        var candidate = text.Trim().ToLowerInvariant();
        return ValidColors.Contains(candidate) ? candidate : "none";
    }

    private static Dictionary<string, object?> ReasonPayload(EvaluationReason reason)
    {
        var payload = new Dictionary<string, object?> { ["kind"] = KindName(reason.Kind) };
        if (reason.Kind == EvaluationReasonKind.RuleMatch)
        {
            payload["ruleIndex"] = reason.RuleIndex;
            if (!string.IsNullOrEmpty(reason.RuleId))
                payload["ruleId"] = reason.RuleId;
        }
        if (reason.Kind == EvaluationReasonKind.PrerequisiteFailed
            && !string.IsNullOrEmpty(reason.PrerequisiteKey))
            payload["prerequisiteKey"] = reason.PrerequisiteKey;
        if (reason.Kind == EvaluationReasonKind.Error)
            payload["errorKind"] = reason.ErrorKind.ToString();
        return payload;
    }

    private static string KindName(EvaluationReasonKind kind) => kind switch
    {
        EvaluationReasonKind.Off => "OFF",
        EvaluationReasonKind.Fallthrough => "FALLTHROUGH",
        EvaluationReasonKind.TargetMatch => "TARGET_MATCH",
        EvaluationReasonKind.RuleMatch => "RULE_MATCH",
        EvaluationReasonKind.PrerequisiteFailed => "PREREQUISITE_FAILED",
        EvaluationReasonKind.Error => "ERROR",
        _ => kind.ToString(),
    };

    public void Dispose() => _client?.Dispose();
}
