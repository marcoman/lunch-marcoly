using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluate the static percentage rollout without implementing bucketing in app code.
/// LaunchDarkly percentage rollout: https://launchdarkly.com/docs/home/flags/rollouts
/// </summary>
sealed class Rollout : IDisposable
{
    public const string FlagKey = "enable-grid-selection-highlight-pct";
    public const string DefaultValue = "none";
    private static readonly HashSet<string> Valid = ["none", "green"];
    private readonly LdClient? _client;

    public Rollout()
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
                stickyNote = "Safe SDK default; LaunchDarkly client is not ready.",
            };
        }

        var context = Context.Builder(username).Kind("user").Name(username).Build();
        var detail = _client.StringVariationDetail(FlagKey, context, DefaultValue);
        var raw = detail.Value;
        var value = Valid.Contains(raw) ? raw : DefaultValue;
        var index = detail.VariationIndex;
        return new
        {
            flagKey = FlagKey,
            flagValue = value,
            highlightColor = value,
            variationIndex = index < 0 ? (int?)null : index,
            reason = ReasonPayload(detail.Reason),
            ldContext,
            stickyNote =
                "LaunchDarkly buckets this user context key deterministically. " +
                "The same key keeps the same assignment while weights stay unchanged.",
        };
    }

    public static string NormalizeUsername(string? raw)
    {
        var username = (raw ?? "").Trim();
        if (username.Length == 0)
            throw new ArgumentException("Username is required.");
        return username;
    }

    private static Dictionary<string, object?> ReasonPayload(EvaluationReason reason)
    {
        var payload = new Dictionary<string, object?> { ["kind"] = KindName(reason.Kind) };
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
