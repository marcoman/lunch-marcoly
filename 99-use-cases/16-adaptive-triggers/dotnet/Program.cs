using System.Net.Http.Headers;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;

const string AppBanner = "16-adaptive-triggers[dotnet]";

var argsList = args.ToList();
using var flags = new HighlightEval();

if (argsList is ["--evaluate-once", var username])
{
    Console.WriteLine(JsonSerializer.Serialize(flags.Evaluate(username), JsonOptions.Web));
    return;
}

var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8161;
var controls = new AdaptiveControls(flags);

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/config", () => Results.Json(controls.ConfigResponse(), JsonOptions.Web));
app.MapGet("/api/highlight", (string? username) =>
{
    if (string.IsNullOrWhiteSpace(username))
        return Results.Json(new { error = "username query parameter is required" }, statusCode: 400);
    return Results.Json(flags.Evaluate(username.Trim()), JsonOptions.Web);
});
app.MapGet("/api/status", async () =>
{
    try
    {
        return Results.Json(await controls.GetStatusAsync(), JsonOptions.Web);
    }
    catch (ApiException exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: exception.Status);
    }
});
app.MapPost("/api/start-live", () => RunControl(controls.StartLiveAsync));
app.MapPost("/api/stop", () => RunControl(controls.StopLiveAsync));
app.MapPost("/api/track-latency", async (HttpContext context) =>
{
    try
    {
        var body = await JsonNode.ParseAsync(context.Request.Body) as JsonObject ?? new JsonObject();
        var name = body["username"]?.GetValue<string>()?.Trim() ?? "";
        double latency = double.NaN;
        if (body["latencyMs"] is JsonValue value)
            value.TryGetValue(out latency);
        if (string.IsNullOrEmpty(name) || double.IsNaN(latency) || latency < 0 || latency > 500)
            return Results.Json(new { error = "username and latencyMs (0–500) are required." }, statusCode: 400);
        flags.TrackLatency(name, latency);
        return Results.Json(new
        {
            tracked = true,
            eventKey = HighlightEval.EventKey,
            latencyMs = latency,
            aboveThreshold = latency > HighlightEval.ThresholdMs,
        }, JsonOptions.Web);
    }
    catch (InvalidOperationException exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: 503);
    }
    catch (Exception exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: 500);
    }
});

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Flag: {HighlightEval.FlagName} ({HighlightEval.FlagHighlight})");
Console.WriteLine($"Metric event key: {HighlightEval.EventKey} — threshold {HighlightEval.ThresholdMs} ms");
Console.WriteLine($"Open http://127.0.0.1:{port}/");
app.Run();

static async Task<IResult> RunControl(Func<Task<object>> action)
{
    try
    {
        return Results.Json(await action(), JsonOptions.Web);
    }
    catch (ApiException exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: exception.Status);
    }
    catch (Exception exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: 500);
    }
}

static async Task ServeIndexAsync(HttpContext context)
{
    var path = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
    if (!File.Exists(path))
    {
        context.Response.StatusCode = StatusCodes.Status404NotFound;
        await context.Response.WriteAsync("Not found");
        return;
    }

    context.Response.ContentType = "text/html; charset=utf-8";
    context.Response.Headers.CacheControl = "no-store";
    await context.Response.SendFileAsync(path);
}

static class JsonOptions
{
    internal static readonly JsonSerializerOptions Web = new(JsonSerializerDefaults.Web)
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };
}

sealed class ApiException(int status, string message) : Exception(message)
{
    internal int Status { get; } = status;
}

/// <summary>
/// Privileged REST controls stay on the .NET host: targeting patches, audit
/// attribution, and dashboard deep links.
/// https://launchdarkly.com/docs/home/flags/triggers
/// https://launchdarkly.com/docs/api/audit-log/get-audit-log-entries
/// </summary>
sealed class AdaptiveControls
{
    private readonly HighlightEval _flags;
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(20) };
    private string? _cachedSdkEnvironmentKey;

    internal AdaptiveControls(HighlightEval flags) => _flags = flags;

    internal object ConfigResponse()
    {
        var config = ApiConfig();
        return new
        {
            controls = new
            {
                configured = config.Configured,
                missing = config.Missing,
                projectKey = config.ProjectKey,
                environmentKey = config.EnvironmentKey,
            },
            flag = new { key = HighlightEval.FlagHighlight, name = HighlightEval.FlagName },
            metricKey = HighlightEval.MetricKey,
            eventKey = HighlightEval.EventKey,
            thresholdMs = HighlightEval.ThresholdMs,
            links = DashboardLinks(config.ProjectKey, config.EnvironmentKey),
        };
    }

    internal async Task<object> GetStatusAsync()
    {
        var config = ApiConfig();
        var sdk = new SdkStatus(_flags.Initialized, null, null);
        if (!config.Configured)
            return StatusPayload(config, sdk, null, null);

        var flag = await LdApiAsync(HttpMethod.Get,
            $"/flags/{Escape(config.ProjectKey!)}/{Escape(HighlightEval.FlagHighlight)}");
        var targeting = flag["environments"]?[config.EnvironmentKey!] as JsonObject;
        var fallthroughIndex = Int(targeting?["fallthrough"]?["variation"]);
        string? fallthrough = null;
        if (fallthroughIndex is int index)
            fallthrough = VariationValue(flag, index);

        object? lastChange = null;
        try
        {
            var sdkEnvironment = await ResolveSdkEnvironmentKeyAsync();
            sdk = new SdkStatus(
                _flags.Initialized,
                sdkEnvironment,
                sdkEnvironment is null ? null : sdkEnvironment == config.EnvironmentKey);
            lastChange = await FetchLastChangeAsync(config);
        }
        catch
        {
            // Diagnostics are best effort.
        }

        return StatusPayload(config, sdk, lastChange, new
        {
            key = HighlightEval.FlagHighlight,
            name = flag["name"]?.GetValue<string>() ?? HighlightEval.FlagName,
            on = targeting?["on"]?.GetValue<bool>(),
            fallthrough,
        });
    }

    /// <summary>
    /// Turn targeting on and serve green. The adaptive trigger later switches
    /// this default rule; it does not use the SDK fallback.
    /// </summary>
    internal async Task<object> StartLiveAsync()
    {
        var config = RequireConfigured();
        var path = $"/flags/{Escape(config.ProjectKey!)}/{Escape(HighlightEval.FlagHighlight)}";
        var flag = await LdApiAsync(HttpMethod.Get, path);
        var variationId = VariationId(flag, HighlightEval.LiveValue)
            ?? throw new ApiException(409, $"Flag {HighlightEval.FlagHighlight} has no {HighlightEval.LiveValue} variation.");
        await LdApiAsync(HttpMethod.Patch, path, new JsonObject
        {
            ["environmentKey"] = config.EnvironmentKey,
            ["comment"] = "16-adaptive-triggers: start live from lab control",
            ["instructions"] = new JsonArray
            {
                new JsonObject { ["kind"] = "turnFlagOn" },
                new JsonObject
                {
                    ["kind"] = "updateFallthroughVariationOrRollout",
                    ["variationId"] = variationId,
                },
            },
        });
        return await GetStatusAsync();
    }

    /// <summary>
    /// Turn targeting off. Does not delete the adaptive trigger.
    /// </summary>
    internal async Task<object> StopLiveAsync()
    {
        var config = RequireConfigured();
        await LdApiAsync(HttpMethod.Patch,
            $"/flags/{Escape(config.ProjectKey!)}/{Escape(HighlightEval.FlagHighlight)}",
            new JsonObject
            {
                ["environmentKey"] = config.EnvironmentKey,
                ["comment"] = "16-adaptive-triggers: stop from lab control",
                ["instructions"] = new JsonArray { new JsonObject { ["kind"] = "turnFlagOff" } },
            });
        return await GetStatusAsync();
    }

    private async Task<string?> ResolveSdkEnvironmentKeyAsync()
    {
        if (_cachedSdkEnvironmentKey is not null) return _cachedSdkEnvironmentKey;
        var sdkKey = Env("LD_SDK_KEY");
        var config = ApiConfig();
        if (sdkKey is null || !config.Configured) return null;
        var body = await LdApiAsync(HttpMethod.Get,
            $"/projects/{Escape(config.ProjectKey!)}/environments?limit=100");
        foreach (var item in body["items"] as JsonArray ?? [])
        {
            if (item?["apiKey"]?.GetValue<string>() == sdkKey)
            {
                _cachedSdkEnvironmentKey = item["key"]?.GetValue<string>();
                return _cachedSdkEnvironmentKey;
            }
        }
        return null;
    }

    private async Task<object?> FetchLastChangeAsync(ControlConfig config)
    {
        var spec = $"proj/{config.ProjectKey}:env/{config.EnvironmentKey}:flag/{HighlightEval.FlagHighlight}";
        var body = await LdApiAsync(HttpMethod.Get, $"/auditlog?spec={Escape(spec)}&limit=1");
        var entry = (body["items"] as JsonArray)?[0] as JsonObject;
        if (entry is null) return null;
        var actor = entry["member"]?["email"]?.GetValue<string>()
            ?? entry["token"]?["name"]?.GetValue<string>();
        var raw = entry["description"]?.GetValue<string>() ?? entry["titleVerb"]?.GetValue<string>() ?? "";
        var summary = string.Join("; ", raw.Replace("*", "").Replace("~", "").Replace("`", "")
            .Split('\n', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries));
        return new
        {
            date = entry["date"]?.DeepClone(),
            summary,
            actor,
            byAutomation = actor is null,
        };
    }

    private object? DashboardLinks(string? projectKey, string? environmentKey)
    {
        if (projectKey is null) return null;
        var envQuery = environmentKey is null
            ? ""
            : $"?env={Escape(environmentKey)}&selected-env={Escape(environmentKey)}";
        var flagBase = $"{AppHost}/projects/{Escape(projectKey)}/flags/{Escape(HighlightEval.FlagHighlight)}";
        return new
        {
            flagTargeting = $"{flagBase}{envQuery}",
            flagMonitoring = $"{flagBase}/monitoring{envQuery}",
            metric = $"{AppHost}/projects/{Escape(projectKey)}/metrics/{Escape(HighlightEval.MetricKey)}",
            environments = $"{AppHost}/projects/{Escape(projectKey)}/settings/environments",
        };
    }

    private async Task<JsonObject> LdApiAsync(HttpMethod method, string path, JsonObject? body = null)
    {
        var config = RequireConfigured();
        using var request = new HttpRequestMessage(method, $"{ApiHost}/api/v2{path}");
        request.Headers.TryAddWithoutValidation("Authorization", Env("LD_API_ACCESS_TOKEN")!);
        request.Headers.Add("LD-API-Version", "20240415");
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        if (body is not null)
        {
            request.Content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            request.Content.Headers.ContentType =
                MediaTypeHeaderValue.Parse("application/json; domain-model=launchdarkly.semanticpatch");
        }
        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        JsonObject parsed;
        try
        {
            parsed = string.IsNullOrWhiteSpace(raw)
                ? new JsonObject()
                : JsonNode.Parse(raw)?.AsObject() ?? new JsonObject();
        }
        catch (JsonException)
        {
            parsed = new JsonObject();
        }
        if (!response.IsSuccessStatusCode)
        {
            var message = parsed["message"]?.GetValue<string>()
                ?? $"LaunchDarkly API returned {(int)response.StatusCode}";
            throw new ApiException((int)response.StatusCode, message);
        }
        _ = config;
        return parsed;
    }

    private static object StatusPayload(
        ControlConfig config, SdkStatus sdk, object? lastChange, object? flag) => new
    {
        configured = config.Configured,
        missing = config.Missing,
        projectKey = config.ProjectKey,
        environmentKey = config.EnvironmentKey,
        links = config.Links,
        sdk,
        lastChange,
        flag,
    };

    private ControlConfig ApiConfig()
    {
        var missing = new[] { "LD_API_ACCESS_TOKEN", "LD_PROJECT_KEY", "LD_ENVIRONMENT_KEY" }
            .Where(key => Env(key) is null).ToList();
        var project = Env("LD_PROJECT_KEY");
        var environment = Env("LD_ENVIRONMENT_KEY");
        return new ControlConfig(
            missing.Count == 0,
            missing,
            project,
            environment,
            DashboardLinks(project, environment));
    }

    private ControlConfig RequireConfigured()
    {
        var config = ApiConfig();
        if (!config.Configured)
            throw new ApiException(503,
                $"This control needs {string.Join(", ", config.Missing)} on the .NET host.");
        return config;
    }

    private static string? VariationId(JsonObject flag, string wanted)
    {
        foreach (var node in flag["variations"] as JsonArray ?? [])
        {
            if (string.Equals(node?["value"]?.ToString()?.Trim(), wanted, StringComparison.OrdinalIgnoreCase))
                return node?["_id"]?.GetValue<string>() ?? node?["id"]?.GetValue<string>();
        }
        return null;
    }

    private static string? VariationValue(JsonObject flag, int index)
    {
        var variations = flag["variations"] as JsonArray ?? [];
        if (index < 0 || index >= variations.Count) return null;
        return variations[index]?["value"]?.GetValue<string>();
    }

    private static int? Int(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<int>(out var number) ? number : null;

    private static string Escape(string value) => Uri.EscapeDataString(value);
    private static string? Env(string key) =>
        Environment.GetEnvironmentVariable(key)?.Trim() is { Length: > 0 } value ? value : null;
    private static string ApiHost => (Env("LD_API_HOST") ?? "https://app.launchdarkly.com").TrimEnd('/');
    private static string AppHost => (Env("LD_APP_HOST") ?? ApiHost).TrimEnd('/');

    private sealed record ControlConfig(
        bool Configured,
        List<string> Missing,
        string? ProjectKey,
        string? EnvironmentKey,
        object? Links);

    private sealed record SdkStatus(bool Initialized, string? EnvironmentKey, bool? MatchesRestEnvironment);
}
