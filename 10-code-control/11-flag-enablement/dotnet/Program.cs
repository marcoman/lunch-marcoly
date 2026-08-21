using System.Net.Http.Headers;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

const string AppBanner = "11-flag-enablement[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8080;

var flags = new EnablementFlags();
var controls = new EnablementControls();

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", () => Results.Json(new
{
    appBanner = AppBanner,
    hostOs = EnablementFlags.HostOs,
    controls = controls.ApiConfig(),
}));
app.MapGet("/api/flags", (string? username) =>
{
    if (string.IsNullOrWhiteSpace(username))
        return Results.BadRequest(new { error = "username query parameter is required" });
    return Results.Json(flags.Evaluate(username.Trim()));
});
app.MapGet("/api/flag-controls", async () => Results.Json(await controls.ListAsync()));
app.MapPost("/api/flag-controls", async (HttpContext context) =>
{
    try
    {
        var body = await JsonNode.ParseAsync(context.Request.Body) as JsonObject
            ?? throw new ArgumentException("Request body must be a JSON object");
        var key = body["key"]?.GetValue<string>()?.Trim();
        if (string.IsNullOrEmpty(key)) throw new ArgumentException("\"key\" is required");
        bool? on = body.ContainsKey("on")
            ? body["on"]?.GetValue<bool>() ?? throw new ArgumentException("\"on\" must be a boolean")
            : null;
        var fallthrough = body["fallthrough"]?.ToString()?.Trim();
        return Results.Json(await controls.ApplyAsync(key, on, string.IsNullOrEmpty(fallthrough) ? null : fallthrough));
    }
    catch (ArgumentException exception)
    {
        return Results.Json(new { ok = false, error = exception.Message }, statusCode: 400);
    }
    catch (Exception exception)
    {
        return Results.Json(new { ok = false, error = exception.Message }, statusCode: 502);
    }
});

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine("Press Ctrl+C to stop.");
app.Run();

static async Task ServeIndexAsync(HttpContext context)
{
    var path = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
    if (!File.Exists(path))
    {
        context.Response.StatusCode = 404;
        await context.Response.WriteAsync("Not found");
        return;
    }
    context.Response.ContentType = "text/html; charset=utf-8";
    context.Response.Headers.CacheControl = "no-store";
    await context.Response.SendFileAsync(path);
}

sealed class EnablementFlags : IDisposable
{
    private const string HighlightFlag = "enable-grid-selection-highlight";
    private const string OverrideFlag = "enable-grid-highlight-color-override";
    private const string CountFlag = "show-navigation-move-count";
    private const string OsEmojiFlag = "show-host-os-emoji";
    private const string HostOsAttribute = "hostOs";
    private static readonly HashSet<string> ValidColors =
        new(["pink", "yellow", "red", "blue", "green", "purple", "none"]);
    private readonly LdClient? _client;

    public static string HostOs => RuntimeInformation.IsOSPlatform(OSPlatform.Linux) ? "linux"
        : RuntimeInformation.IsOSPlatform(OSPlatform.OSX) ? "macos"
        : RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "windows"
        : "other";

    public EnablementFlags()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — flags default to off.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
    }

    /// <summary>
    /// Evaluate string and boolean feature flags for one user context.
    /// LaunchDarkly contexts and private attributes:
    /// https://launchdarkly.com/docs/home/flags/contexts
    /// https://launchdarkly.com/docs/sdk/features/private-attributes
    /// </summary>
    public object Evaluate(string username)
    {
        var context = Context.Builder(username)
            .Set(HostOsAttribute, HostOs)
            .Private(HostOsAttribute)
            .Build();

        var rawHighlight = _client?.StringVariation(HighlightFlag, context, "none") ?? "none";
        var highlightEnabled = !IsOff(rawHighlight);
        var servedColor = highlightEnabled && ValidColors.Contains(rawHighlight.ToLowerInvariant())
            ? rawHighlight.ToLowerInvariant()
            : null;
        var useOverride = _client?.BoolVariation(OverrideFlag, context, false) ?? false;
        var showCount = _client?.BoolVariation(CountFlag, context, false) ?? false;
        var showEmoji = _client?.BoolVariation(OsEmojiFlag, context, false) ?? false;
        var (human, robot, beta) = Cohorts(username);
        var color = ResolveColor(highlightEnabled, useOverride, servedColor, human, robot, beta);
        var cohortParts = new List<string>();
        if (useOverride)
        {
            if (human) cohortParts.Add("human");
            if (robot) cohortParts.Add("robot");
            if (beta) cohortParts.Add("beta");
        }
        cohortParts.Add(color == "none" ? "no-color" : color);

        return new
        {
            highlightEnabled,
            contextHighlight = useOverride,
            showMoveCount = showCount,
            highlightColor = color,
            cohortLabel = $"({string.Join("-", cohortParts)})",
            osEmoji = showEmoji ? OsEmoji(HostOs) : "",
            highlightServedValue = rawHighlight,
            ldContext = new
            {
                kind = "user",
                key = username,
                attributes = new Dictionary<string, string> { [HostOsAttribute] = HostOs },
                privateAttributes = new[] { HostOsAttribute },
                appDerived = new
                {
                    cohortWords = new { human, robot, beta },
                    note = "Cohort words are parsed in app code from the username; they are not separate LD context attributes.",
                },
                note = "hostOs is private: used for targeting and redacted from analytics events.",
            },
        };
    }

    private static bool IsOff(string? value) =>
        string.IsNullOrWhiteSpace(value) ||
        new[] { "none", "false", "off" }.Contains(value.Trim().ToLowerInvariant());

    private static (bool Human, bool Robot, bool Beta) Cohorts(string username)
    {
        var value = username.ToLowerInvariant();
        return (value.Contains("human"), value.Contains("robot"), value.Contains("beta"));
    }

    private static string ResolveColor(
        bool enabled, bool useOverride, string? served, bool human, bool robot, bool beta)
    {
        if (!enabled) return "none";
        if (!useOverride) return served ?? "green";
        if (human && beta) return "green";
        if (robot && beta) return "purple";
        if (human) return "yellow";
        if (robot) return "red";
        if (beta) return "blue";
        return served ?? "green";
    }

    private static string OsEmoji(string hostOs) => hostOs switch
    {
        "linux" => "🐧",
        "macos" => "🍎",
        "windows" => "🪟",
        _ => "😊",
    };

    public void Dispose() => _client?.Dispose();
}

sealed class EnablementControls
{
    private const string HighlightFlag = "enable-grid-selection-highlight";
    private static readonly (string Key, string Label, string Summary)[] ControlledFlags =
    [
        (HighlightFlag, "Enable grid selection highlight",
            "String flag: off → none (X only); on → fallthrough color."),
        ("enable-grid-highlight-color-override", "Enable grid highlight color override",
            "Boolean gate for app-derived human / robot / beta colors."),
        ("show-navigation-move-count", "Move count", "Show Count: N in the header."),
        ("show-host-os-emoji", "Host OS emoji",
            "OS emoji before the username (private hostOs attribute)."),
    ];
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(30) };

    public object ApiConfig()
    {
        var missing = Missing();
        return new
        {
            configured = missing.Count == 0,
            missing,
            projectKey = Env("LD_PROJECT_KEY"),
            environmentKey = Env("LD_ENVIRONMENT_KEY"),
            apiHost = Env("LD_API_HOST") ?? "https://app.launchdarkly.com",
        };
    }

    /// <summary>
    /// Read flag status and apply semantic-patch controls through the LaunchDarkly REST API.
    /// https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    /// </summary>
    public async Task<object> ListAsync()
    {
        var missing = Missing();
        if (missing.Count > 0)
            return ConfigWithFlags(ControlledFlags.Select(meta => Placeholder(meta, missing)).ToList());

        var flags = new List<object>();
        var errors = new List<object>();
        foreach (var meta in ControlledFlags)
        {
            try
            {
                flags.Add(Summarize(await GetFlagAsync(meta.Key), meta));
            }
            catch (Exception exception)
            {
                errors.Add(new { key = meta.Key, error = exception.Message });
                flags.Add(new
                {
                    key = meta.Key, label = meta.Label, summary = meta.Summary, on = (bool?)null,
                    targetingHint = exception.Message, error = exception.Message,
                });
            }
        }
        return ConfigWithFlags(flags, errors);
    }

    public async Task<object> ApplyAsync(string key, bool? on, string? fallthrough)
    {
        var meta = ControlledFlags.FirstOrDefault(item => item.Key == key);
        if (string.IsNullOrEmpty(meta.Key))
            throw new ArgumentException($"Flag key not allowed for controls: {key}");
        if (on is null && fallthrough is null)
            throw new ArgumentException("Provide \"on\" and/or \"fallthrough\"");
        RequireConfigured();

        var flag = await GetFlagAsync(key);
        var instructions = new JsonArray();
        var actions = new List<string>();
        if (on is true)
        {
            instructions.Add(new JsonObject { ["kind"] = "turnFlagOn" });
            actions.Add("turnFlagOn");
        }
        else if (on is false)
        {
            instructions.Add(new JsonObject { ["kind"] = "turnFlagOff" });
            actions.Add("turnFlagOff");
        }
        if (fallthrough is not null)
        {
            var variationId = VariationId(flag, fallthrough);
            if (variationId is null && on is not false)
                throw new ArgumentException($"No variation matching fallthrough={fallthrough} on {key}");
            if (variationId is not null)
            {
                instructions.Add(new JsonObject
                {
                    ["kind"] = "updateFallthroughVariationOrRollout",
                    ["variationId"] = variationId,
                });
                actions.Add("updateFallthrough");
            }
        }

        var action = string.Join("+", actions);
        await RequestAsync(HttpMethod.Patch, $"/flags/{Escape(Project)}/{Escape(key)}", new JsonObject
        {
            ["environmentKey"] = EnvironmentKey,
            ["comment"] = $"11-flag-enablement UI: {action}",
            ["instructions"] = instructions,
        });
        flag = await GetFlagAsync(key);
        return new
        {
            ok = true,
            action,
            instructions = instructions.Select(node => node?["kind"]?.ToString()).ToArray(),
            projectKey = Project,
            environmentKey = EnvironmentKey,
            flag = Summarize(flag, meta),
        };
    }

    private object ConfigWithFlags(List<object> flags, List<object>? errors = null) => new
    {
        configured = Missing().Count == 0,
        missing = Missing(),
        projectKey = Env("LD_PROJECT_KEY"),
        environmentKey = Env("LD_ENVIRONMENT_KEY"),
        apiHost = ApiHost,
        flags,
        errors = errors ?? [],
    };

    private static object Placeholder(
        (string Key, string Label, string Summary) meta, List<string> missing) => new
    {
        key = meta.Key, label = meta.Label, summary = meta.Summary, on = (bool?)null,
        targetingHint = $"Set {string.Join(", ", missing)} to enable controls.",
    };

    private object Summarize(JsonObject flag, (string Key, string Label, string Summary) meta)
    {
        var environment = flag["environments"]?[EnvironmentKey] as JsonObject ?? new JsonObject();
        var variations = flag["variations"] as JsonArray ?? [];
        var on = environment["on"]?.GetValue<bool>() ?? false;
        var offIndex = Int(environment["offVariation"]);
        var fallIndex = Int(environment["fallthrough"]?["variation"]);
        var offValue = VariationValue(variations, offIndex);
        var fallValue = VariationValue(variations, fallIndex);
        var rules = (environment["rules"] as JsonArray)?.Count ?? 0;
        var targets = (environment["targets"] as JsonArray)?.Count ?? 0;
        var contextTargets = (environment["contextTargets"] as JsonArray)?.Count ?? 0;
        var variationRows = variations.Select((node, index) => new
        {
            index,
            value = node?["value"]?.DeepClone(),
            name = node?["name"]?.ToString() ?? "",
            description = node?["description"]?.ToString() ?? "",
        }).ToList();
        var allStrings = variationRows.Count > 0 &&
            variationRows.All(row => row.value is JsonValue value && value.TryGetValue<string>(out _));
        var allBooleans = variationRows.Count > 0 &&
            variationRows.All(row => row.value is JsonValue value && value.TryGetValue<bool>(out _));
        var colors = meta.Key == HighlightFlag && allStrings
            ? variationRows.Select(row => row.value?.GetValue<string>() ?? "")
                .Where(value => !new[] { "", "none", "false", "off" }.Contains(value.ToLowerInvariant()))
                .ToArray()
            : [];
        var hint = !on
            ? $"Flag is OFF — evaluations receive the off variation ({Json(offValue)}), regardless of fallthrough."
            : rules + targets + contextTargets > 0
                ? $"Flag is ON. Fallthrough serves {Json(fallValue)}; targets/rules may override."
                : $"Flag is ON with no extra targets/rules — evaluations use fallthrough ({Json(fallValue)}).";

        return new
        {
            key = flag["key"]?.ToString() ?? meta.Key,
            name = flag["name"]?.ToString() ?? meta.Label,
            label = meta.Label,
            summary = meta.Summary,
            on,
            variationKind = allStrings ? "string" : allBooleans ? "boolean" : "other",
            colorOptions = colors,
            variations = variationRows,
            offVariation = offIndex,
            fallthroughVariation = fallIndex,
            servedWhenOff = offValue,
            servedWhenOnFallthrough = fallValue,
            ruleCount = rules,
            targetCount = targets + contextTargets,
            targetingHint = hint,
        };
    }

    private async Task<JsonObject> GetFlagAsync(string key) =>
        await RequestAsync(HttpMethod.Get,
            $"/flags/{Escape(Project)}/{Escape(key)}?env={Escape(EnvironmentKey)}");

    private async Task<JsonObject> RequestAsync(HttpMethod method, string path, JsonObject? body = null)
    {
        RequireConfigured();
        using var request = new HttpRequestMessage(method, $"{ApiHost.TrimEnd('/')}/api/v2{path}");
        request.Headers.TryAddWithoutValidation("Authorization", Token);
        request.Headers.Add("LD-API-Version", Env("LD_API_VERSION") ?? "20240415");
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        if (body is not null)
        {
            request.Content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            request.Content.Headers.ContentType =
                MediaTypeHeaderValue.Parse("application/json; domain-model=launchdarkly.semanticpatch");
        }
        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            var detail = JsonNode.Parse(raw)?["message"]?.ToString() ?? raw;
            throw new InvalidOperationException($"LaunchDarkly API {(int)response.StatusCode}: {detail}");
        }
        return string.IsNullOrWhiteSpace(raw) ? new JsonObject() : JsonNode.Parse(raw)?.AsObject() ?? new JsonObject();
    }

    private static string? VariationId(JsonObject flag, string wanted)
    {
        foreach (var node in flag["variations"] as JsonArray ?? [])
        {
            var value = node?["value"]?.ToString();
            if (!string.Equals(value?.Trim(), wanted.Trim(), StringComparison.OrdinalIgnoreCase)) continue;
            return node?["_id"]?.ToString() ?? node?["id"]?.ToString();
        }
        return null;
    }

    private static JsonNode? VariationValue(JsonArray values, int? index) =>
        index is >= 0 && index < values.Count ? values[index.Value]?["value"]?.DeepClone() : null;
    private static int? Int(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<int>(out var number) ? number : null;
    private static string Json(JsonNode? node) => node?.ToJsonString() ?? "null";
    private static string Escape(string value) => Uri.EscapeDataString(value);
    private static string? Env(string key) =>
        Environment.GetEnvironmentVariable(key)?.Trim() is { Length: > 0 } value ? value : null;
    private static List<string> Missing() =>
        new[] { "LD_API_ACCESS_TOKEN", "LD_PROJECT_KEY", "LD_ENVIRONMENT_KEY" }
            .Where(key => Env(key) is null).ToList();
    private static void RequireConfigured()
    {
        var missing = Missing();
        if (missing.Count > 0)
            throw new InvalidOperationException($"Flag controls need {string.Join(", ", missing)} in the server environment.");
    }
    private static string Token => Env("LD_API_ACCESS_TOKEN")!;
    private static string Project => Env("LD_PROJECT_KEY")!;
    private static string EnvironmentKey => Env("LD_ENVIRONMENT_KEY")!;
    private static string ApiHost => Env("LD_API_HOST") ?? "https://app.launchdarkly.com";
}
