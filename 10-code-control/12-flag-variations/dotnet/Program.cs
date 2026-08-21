using System.Net.Http.Headers;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

const string AppBanner = "12-flag-variations[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8080;

var flags = new VariationFlags();
var controls = new VariationControls();
var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", () => Results.Json(new
{
    appBanner = AppBanner,
    hostOs = VariationFlags.HostOs,
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
        var fallthrough = body.ContainsKey("fallthrough") ? body["fallthrough"]?.DeepClone() : null;
        return Results.Json(await controls.ApplyAsync(key, on, fallthrough));
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

sealed class VariationFlags : IDisposable
{
    private const string EmojiFlag = "show-anonymous-host-os-emoji";
    private const string LabelFlag = "configure-navigation-count-label";
    private const string LuckyFlag = "configure-lucky-number";
    private const string MaxMovesFlag = "configure-max-navigation-moves";
    private const string HostOsAttribute = "hostOs";
    private const string AnonymousKey = "anonymous";
    private readonly LdClient? _client;

    public static string HostOs => RuntimeInformation.IsOSPlatform(OSPlatform.Linux) ? "linux"
        : RuntimeInformation.IsOSPlatform(OSPlatform.OSX) ? "macos"
        : RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "windows"
        : "other";

    public VariationFlags()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
        {
            Console.WriteLine("Warning: LD_SDK_KEY not set — flags use defaults.");
            return;
        }
        _client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!_client.Initialized)
            Console.WriteLine("Warning: LaunchDarkly SDK did not initialize — flags use defaults.");
    }

    /// <summary>
    /// Evaluate boolean, string, number, and JSON variations using user and anonymous contexts.
    /// https://launchdarkly.com/docs/sdk/features/flag-types
    /// https://launchdarkly.com/docs/sdk/features/anonymous
    /// </summary>
    public object Evaluate(string username)
    {
        var userContext = Context.Builder(username).Build();
        var anonymousContext = Context.Builder(AnonymousKey)
            .Anonymous(true)
            .Set(HostOsAttribute, HostOs)
            .Private(HostOsAttribute)
            .Build();
        var defaultMaxMoves = LdValue.ObjectFrom(
            new Dictionary<string, LdValue> { ["maxMoves"] = LdValue.Of(100) });

        var showEmoji = _client?.BoolVariation(EmojiFlag, anonymousContext, false) ?? false;
        var countLabel = _client?.StringVariation(LabelFlag, userContext, "Count") ?? "Count";
        var luckyNumber = _client?.DoubleVariation(LuckyFlag, userContext, 0) ?? 0;
        var maxMovesValue = _client?.JsonVariation(MaxMovesFlag, userContext, defaultMaxMoves)
            ?? defaultMaxMoves;
        var maxMovesNode = maxMovesValue.Get("maxMoves");
        var maxMoves = maxMovesNode.Type == LdValueType.Number
            ? Convert.ToInt32(maxMovesNode.AsDouble)
            : 100;
        if (maxMoves == 0) maxMoves = 100;

        return new
        {
            countLabel = string.IsNullOrEmpty(countLabel) ? "Count" : countLabel,
            luckyNumber,
            maxMoves,
            osEmoji = showEmoji ? OsEmoji(HostOs) : "",
            ldContext = new
            {
                user = new
                {
                    kind = "user",
                    key = username,
                    note = "String, number, and JSON flags evaluate against this user context.",
                },
                anonymous = new
                {
                    kind = "user",
                    key = AnonymousKey,
                    anonymous = true,
                    attributes = new Dictionary<string, string> { [HostOsAttribute] = HostOs },
                    privateAttributes = new[] { HostOsAttribute },
                    flagKey = EmojiFlag,
                    note = $"{EmojiFlag} uses this anonymous context. hostOs is private.",
                },
            },
        };
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

sealed class VariationControls
{
    private static readonly (string Key, string Label, string Summary)[] ControlledFlags =
    [
        ("show-anonymous-host-os-emoji", "Show anonymous host OS emoji",
            "Boolean, evaluated with an anonymous context and private hostOs."),
        ("configure-navigation-count-label", "Configure navigation count label",
            "String variation — fallthrough chooses the header label."),
        ("configure-lucky-number", "Configure lucky number",
            "Number variation — fallthrough chooses Lucky Number is: N."),
        ("configure-max-navigation-moves", "Configure max navigation moves",
            "JSON variation — fallthrough chooses the session maxMoves cap."),
    ];
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(30) };

    public object ApiConfig() => new
    {
        configured = Missing().Count == 0,
        missing = Missing(),
        projectKey = Env("LD_PROJECT_KEY"),
        environmentKey = Env("LD_ENVIRONMENT_KEY"),
        apiHost = ApiHost,
    };

    /// <summary>
    /// Read and update targeting with LaunchDarkly semantic patches; variation definitions stay intact.
    /// https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
    /// </summary>
    public async Task<object> ListAsync()
    {
        if (Missing().Count > 0)
            return ConfigWithFlags(ControlledFlags.Select(meta => new
            {
                key = meta.Key, label = meta.Label, summary = meta.Summary, on = (bool?)null,
                targetingHint = "Set missing env vars to enable controls.",
            }).Cast<object>().ToList());

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

    public async Task<object> ApplyAsync(string key, bool? on, JsonNode? fallthrough)
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
            var wanted = NormalizeFallthrough(fallthrough);
            var variationId = VariationId(flag, wanted);
            if (variationId is null && on is not false)
                throw new ArgumentException($"No variation matching fallthrough={wanted.ToJsonString()} on {key}");
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
            ["comment"] = $"12-flag-variations UI: {action}",
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

    private object Summarize(JsonObject flag, (string Key, string Label, string Summary) meta)
    {
        var environment = flag["environments"]?[EnvironmentKey] as JsonObject ?? new JsonObject();
        var variations = flag["variations"] as JsonArray ?? [];
        var on = environment["on"]?.GetValue<bool>() ?? false;
        var offIndex = Int(environment["offVariation"]);
        var fallIndex = Int(environment["fallthrough"]?["variation"]);
        var offValue = VariationValue(variations, offIndex);
        var fallValue = VariationValue(variations, fallIndex);
        var kind = VariationKind(variations);
        var rows = variations.Select((node, index) =>
        {
            var value = node?["value"]?.DeepClone();
            return new
            {
                index,
                value,
                name = node?["name"]?.ToString() ?? "",
                description = node?["description"]?.ToString() ?? "",
                token = TokenFor(value),
            };
        }).ToList();
        var options = kind == "boolean"
            ? []
            : rows.Select(row => new
            {
                token = row.token,
                label = string.IsNullOrEmpty(row.name) ? row.token : row.name,
                value = row.value,
            }).Cast<object>().ToArray();
        var rules = (environment["rules"] as JsonArray)?.Count ?? 0;
        var targets = (environment["targets"] as JsonArray)?.Count ?? 0;
        var contextTargets = (environment["contextTargets"] as JsonArray)?.Count ?? 0;
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
            variationKind = kind,
            fallthroughOptions = options,
            fallthroughToken = fallValue is null ? null : TokenFor(fallValue),
            variations = rows,
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

    private static JsonNode NormalizeFallthrough(JsonNode value)
    {
        if (value is JsonValue scalar && scalar.TryGetValue<string>(out var text))
        {
            try { return JsonNode.Parse(text) ?? JsonValue.Create(text)!; }
            catch { return JsonValue.Create(text)!; }
        }
        return value.DeepClone();
    }

    private static string? VariationId(JsonObject flag, JsonNode wanted)
    {
        foreach (var node in flag["variations"] as JsonArray ?? [])
        {
            var value = node?["value"];
            if (!JsonNode.DeepEquals(value, wanted) &&
                !NumbersEqual(value, wanted)) continue;
            return node?["_id"]?.ToString() ?? node?["id"]?.ToString();
        }
        return null;
    }

    private static bool NumbersEqual(JsonNode? left, JsonNode? right) =>
        double.TryParse(left?.ToString(), out var a) &&
        double.TryParse(right?.ToString(), out var b) && a.Equals(b);
    private static string VariationKind(JsonArray values)
    {
        if (values.Count == 0) return "other";
        var nodes = values.Select(node => node?["value"]).ToList();
        if (nodes.All(node => node is JsonValue value && value.TryGetValue<bool>(out _))) return "boolean";
        if (nodes.All(node => node is JsonValue value && value.TryGetValue<string>(out _))) return "string";
        if (nodes.All(node => node is JsonValue value &&
            (value.TryGetValue<int>(out _) || value.TryGetValue<double>(out _)))) return "number";
        if (nodes.All(node => node is JsonObject or JsonArray)) return "json";
        return "other";
    }
    private static string TokenFor(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<string>(out var text) ? text : Json(node);
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
