using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Read the move-count flag. The default is hidden.
/// LaunchDarkly: server-side .NET SDK · boolean variation
/// https://launchdarkly.com/docs/sdk/server-side/dotnet
/// https://launchdarkly.com/docs/home/flags/boolean
/// </summary>
sealed class CountFlag : IDisposable
{
    public const string FlagKey = "show-navigation-move-count-approval";
    private readonly LdClient? _client;

    public CountFlag()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — the count stays hidden.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize.");
    }

    public object Evaluate(string? rawUsername)
    {
        var username = (rawUsername ?? "").Trim();
        if (username.Length == 0) throw new ArgumentException("Username is required");
        if (_client is not { Initialized: true })
        {
            return new
            {
                username,
                flagKey = FlagKey,
                showMoveCount = false,
                reason = "DEFAULT",
                sdk = false,
            };
        }
        var context = Context.Builder(username).Kind("user").Name(username).Build();
        var detail = _client.BoolVariationDetail(FlagKey, context, false);
        return new
        {
            username,
            flagKey = FlagKey,
            showMoveCount = detail.Value,
            reason = ReasonKind(detail.Reason),
            sdk = true,
        };
    }

    private static string ReasonKind(EvaluationReason reason) => reason.Kind switch
    {
        EvaluationReasonKind.Off => "OFF",
        EvaluationReasonKind.Fallthrough => "FALLTHROUGH",
        EvaluationReasonKind.TargetMatch => "TARGET_MATCH",
        EvaluationReasonKind.RuleMatch => "RULE_MATCH",
        EvaluationReasonKind.PrerequisiteFailed => "PREREQUISITE_FAILED",
        EvaluationReasonKind.Error => "ERROR",
        _ => reason.Kind.ToString(),
    };

    public void Dispose() => _client?.Dispose();
}
