using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate the highlight flag; LaunchDarkly applies the scheduled change remotely.
/// Feature flag evaluation: https://launchdarkly.com/docs/sdk/features/evaluating
/// </summary>
sealed class ScheduledHighlight : IDisposable
{
    public const string FlagKey = "enable-grid-selection-highlight-sched";
    public const string DefaultValue = "none";
    private static readonly HashSet<string> Valid = ["none", "green"];
    private readonly LdClient? _client;

    public ScheduledHighlight()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — highlight defaults to none.");
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
        var ldContext = new { kind = "user", key = username, name = username };
        if (_client is not { Initialized: true })
        {
            return new
            {
                flagKey = FlagKey,
                flagValue = DefaultValue,
                highlightColor = DefaultValue,
                variationIndex = (int?)null,
                reason = new Dictionary<string, object?>
                {
                    ["kind"] = "ERROR",
                    ["errorKind"] = "CLIENT_NOT_READY",
                },
                ldContext,
            };
        }

        var context = Context.Builder(username).Kind("user").Name(username).Build();
        var detail = _client.StringVariationDetail(FlagKey, context, DefaultValue);
        var value = Valid.Contains(detail.Value) ? detail.Value : DefaultValue;
        return new
        {
            flagKey = FlagKey,
            flagValue = value,
            highlightColor = value,
            variationIndex = detail.VariationIndex < 0 ? (int?)null : detail.VariationIndex,
            reason = ReasonPayload(detail.Reason),
            ldContext,
        };
    }

    private static string NormalizeUsername(string? raw)
    {
        var username = (raw ?? "").Trim();
        if (username.Length == 0) throw new ArgumentException("Username is required.");
        return username;
    }

    private static Dictionary<string, object?> ReasonPayload(EvaluationReason reason)
    {
        var kind = reason.Kind switch
        {
            EvaluationReasonKind.Off => "OFF",
            EvaluationReasonKind.Fallthrough => "FALLTHROUGH",
            EvaluationReasonKind.TargetMatch => "TARGET_MATCH",
            EvaluationReasonKind.RuleMatch => "RULE_MATCH",
            EvaluationReasonKind.PrerequisiteFailed => "PREREQUISITE_FAILED",
            EvaluationReasonKind.Error => "ERROR",
            _ => reason.Kind.ToString(),
        };
        var payload = new Dictionary<string, object?> { ["kind"] = kind };
        if (reason.Kind == EvaluationReasonKind.Error)
            payload["errorKind"] = reason.ErrorKind.ToString();
        return payload;
    }

    public void Dispose() => _client?.Dispose();
}
