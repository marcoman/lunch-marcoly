using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

/// <summary>
/// Evaluates the partner-badge flag with a user + organization multi-context.
/// Multi-contexts: https://launchdarkly.com/docs/home/flags/multi-contexts
/// </summary>
sealed class Partner : IDisposable
{
    public const string FlagKey = "show-partner-org-badge";
    private static readonly Dictionary<string, string> OrgLabels = new()
    {
        ["acme"] = "Acme",
        ["globex"] = "Globex",
    };
    private readonly LdClient? _client;

    public Partner()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — partner badge stays false.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey)
            .StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize — partner badge stays false.");
    }

    public object Evaluate(string rawUsername, string? rawOrg)
    {
        var username = NormalizeUsername(rawUsername);
        var org = NormalizeOrg(rawOrg);
        var context = BuildMultiContext(username, org);
        var detail = _client?.BoolVariationDetail(FlagKey, context, false);
        return new
        {
            username,
            org,
            orgLabel = OrgLabels[org],
            partner = detail?.Value ?? false,
            ldContext = new
            {
                kind = "multi",
                user = new { key = username },
                organization = new { key = org, name = OrgLabels[org] },
                note = "Org is a separate context kind, not a user attribute.",
            },
            variationIndex = detail?.VariationIndex,
            reason = detail is null ? new { kind = "OFFLINE" } : ReasonPayload(detail.Value.Reason),
        };
    }

    private static string NormalizeUsername(string? raw)
    {
        var username = (raw ?? "").Trim().ToLowerInvariant();
        if (username.Length == 0)
            throw new ArgumentException("username is required");
        return username;
    }

    private static string NormalizeOrg(string? raw)
    {
        var org = (raw ?? "").Trim().ToLowerInvariant();
        if (!OrgLabels.ContainsKey(org))
            throw new ArgumentException("org must be acme or globex");
        return org;
    }

    /// <summary>
    /// Builds user + organization multi-context. Do not put org on the user.
    /// https://launchdarkly.com/docs/sdk/features/user-context
    /// </summary>
    private static Context BuildMultiContext(string username, string org)
    {
        var user = Context.Builder(username).Kind("user").Build();
        var organization = Context.Builder(org)
            .Kind("organization")
            .Set("name", OrgLabels[org])
            .Build();
        return Context.NewMulti(user, organization);
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
