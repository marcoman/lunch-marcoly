using System.Collections.Concurrent;
using System.Net.Http.Headers;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;

const string FlagKey = "enable-sdk-fallback-grid-highlight";
const string FlagName = "Enable: SDK fallback grid highlight";
const string CodeDefault = "none";

var port = IntEnv("PORT", 8181);
var gatePort = IntEnv("LD_STREAM_GATE_PORT", 8182);
var startWait = DoubleEnv("LD_START_WAIT", 2);
var streamOrigin = Env("LD_STREAM_ORIGIN") ?? "https://stream.launchdarkly.com";
var pollOrigin = Env("LD_POLL_ORIGIN") ?? "https://sdk.launchdarkly.com";

using var gate = new StreamGate(streamOrigin);
using var clients = new FallbackClients(gate, gatePort, startWait, pollOrigin);

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenLocalhost(port);
    options.ListenLocalhost(gatePort);
});
builder.Logging.ClearProviders();
var app = builder.Build();

app.Use(async (context, next) =>
{
    if (context.Connection.LocalPort == gatePort)
        await gate.ProxyAsync(context);
    else
        await next(context);
});

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/config", () =>
{
    var payload = new Dictionary<string, object?>(clients.Status())
    {
        ["runtime"] = "18-sdk-fallbacks[dotnet]",
        ["flag"] = new { key = FlagKey, name = FlagName },
        ["codeDefault"] = CodeDefault,
    };
    return Results.Json(payload, JsonOptions.Web);
});
app.MapGet("/api/status", () => Results.Json(clients.Status(), JsonOptions.Web));
app.MapGet("/api/evaluate", (string? username) =>
{
    if (string.IsNullOrWhiteSpace(username))
        return Results.Json(new { error = "username query parameter is required" },
            statusCode: 400);
    return Results.Json(clients.Evaluate(username.Trim()), JsonOptions.Web);
});
app.MapPost("/api/connect", () => RunControl(() => clients.Replace("stream")));
app.MapPost("/api/drop-stream", () => RunControl(clients.DropStream));
app.MapPost("/api/block-init", () => RunControl(() => clients.Replace("default")));

await app.StartAsync();
if (clients.Configured)
{
    var initial = clients.Replace("stream");
    if (!Equals(initial["initialized"], true))
        Console.Error.WriteLine("Warning: SDK did not initialize; use Connect stream to retry.");
}
else
{
    Console.Error.WriteLine("Warning: LD_SDK_KEY is unset; evaluations use none.");
}

Console.WriteLine("18-sdk-fallbacks[dotnet]");
Console.WriteLine($"Flag: {FlagName} ({FlagKey}); code default: {CodeDefault}");
Console.WriteLine($"Stream gate: http://127.0.0.1:{gatePort} → {streamOrigin.TrimEnd('/')}");
Console.WriteLine($"Open http://127.0.0.1:{port}/");
await app.WaitForShutdownAsync();

static IResult RunControl(Func<Dictionary<string, object?>> action)
{
    try
    {
        return Results.Json(action(), JsonOptions.Web);
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
    var index = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
    if (!File.Exists(index))
    {
        context.Response.StatusCode = 404;
        await context.Response.WriteAsync("Not found");
        return;
    }
    context.Response.ContentType = "text/html; charset=utf-8";
    context.Response.Headers.CacheControl = "no-store";
    await context.Response.SendFileAsync(index);
}

static string? Env(string key) =>
    Environment.GetEnvironmentVariable(key)?.Trim() is { Length: > 0 } value ? value : null;

static int IntEnv(string key, int fallback) =>
    int.TryParse(Env(key), out var value) ? value : fallback;

static double DoubleEnv(string key, double fallback) =>
    double.TryParse(Env(key), out var value) ? value : fallback;

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
/// Owns the server SDK client and changes only its streaming transport state.
/// LaunchDarkly: StringVariationDetail is called in every scenario.
/// https://launchdarkly.com/docs/sdk/features/evaluating
/// </summary>
sealed class FallbackClients(
    StreamGate gate,
    int gatePort,
    double startWait,
    string pollOrigin) : IDisposable
{
    private const string FlagKey = "enable-sdk-fallback-grid-highlight";
    private const string CodeDefault = "none";
    private const string LiveValue = "green";
    private readonly object _lock = new();
    private LdClient? _client;
    private string _mode = "starting";
    private bool _everInitialized;

    internal bool Configured =>
        !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("LD_SDK_KEY"));

    /// <summary>
    /// Construct a fresh client with public service-endpoint and start-wait
    /// configuration. Analytics are disabled because this lab tests data flow.
    /// </summary>
    private LdClient MakeClient()
    {
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim();
        if (string.IsNullOrEmpty(sdkKey))
            throw new ApiException(503, "LD_SDK_KEY is required for this lab.");
        var config = Configuration.Builder(sdkKey)
            .ServiceEndpoints(Components.ServiceEndpoints()
                .Streaming($"http://127.0.0.1:{gatePort}")
                .Polling(pollOrigin))
            .Events(Components.NoEvents)
            .DiagnosticOptOut(true)
            .DataSource(Components.StreamingDataSource()
                .InitialReconnectDelay(TimeSpan.FromMilliseconds(500)))
            .StartWaitTime(TimeSpan.FromSeconds(startWait))
            .Build();
        return new LdClient(config);
    }

    internal Dictionary<string, object?> Replace(string nextMode)
    {
        if (nextMode == "stream") gate.Open();
        else if (nextMode == "default") gate.Drop();
        else throw new ApiException(400, $"Unknown mode: {nextMode}");

        LdClient? previous;
        lock (_lock)
        {
            previous = _client;
            _client = null;
            _mode = nextMode;
            _everInitialized = false;
        }
        previous?.Dispose();
        var next = MakeClient();
        lock (_lock)
        {
            _client = next;
            _everInitialized = next.Initialized;
        }
        return Status();
    }

    internal Dictionary<string, object?> DropStream()
    {
        lock (_lock)
        {
            if (_client is null || !_client.Initialized)
                throw new ApiException(409,
                    "Connect and initialize the stream before dropping it.");
            _everInitialized = true;
            _mode = "last-known";
        }
        gate.Drop();
        return Status();
    }

    private string Source() =>
        _mode == "last-known" ? "LAST_KNOWN"
        : _mode == "stream" && _client?.Initialized == true ? "STREAM"
        : "DEFAULT";

    internal Dictionary<string, object?> Status()
    {
        lock (_lock)
        {
            var initialized = _client?.Initialized == true;
            if (initialized) _everInitialized = true;
            return new Dictionary<string, object?>
            {
                ["mode"] = _mode,
                ["source"] = Source(),
                ["initialized"] = initialized,
                ["everInitialized"] = _everInitialized,
                ["gateOpen"] = gate.Allowed,
                ["activeStreams"] = gate.ActiveCount,
                ["startWaitSeconds"] = startWait,
                ["configured"] = Configured,
            };
        }
    }

    internal Dictionary<string, object?> Evaluate(string username)
    {
        lock (_lock)
        {
            var payload = new Dictionary<string, object?>();
            if (_client is null)
            {
                payload["flagValue"] = CodeDefault;
                payload["highlightColor"] = CodeDefault;
                payload["reason"] = new Dictionary<string, object?>
                {
                    ["kind"] = "ERROR",
                    ["errorKind"] = "CLIENT_NOT_READY",
                };
            }
            else
            {
                var context = Context.Builder(username).Kind("user").Build();
                var detail = _client.StringVariationDetail(FlagKey, context, CodeDefault);
                var value = detail.Value is CodeDefault or LiveValue
                    ? detail.Value
                    : CodeDefault;
                payload["flagValue"] = value;
                payload["highlightColor"] = value;
                payload["reason"] = ReasonPayload(detail.Reason);
            }
            foreach (var (key, value) in Status()) payload[key] = value;
            return payload;
        }
    }

    private static Dictionary<string, object?> ReasonPayload(EvaluationReason reason)
    {
        var payload = new Dictionary<string, object?> { ["kind"] = KindName(reason.Kind) };
        if (reason.Kind == EvaluationReasonKind.RuleMatch)
        {
            payload["ruleIndex"] = reason.RuleIndex;
            if (!string.IsNullOrEmpty(reason.RuleId)) payload["ruleId"] = reason.RuleId;
        }
        if (reason.Kind == EvaluationReasonKind.PrerequisiteFailed
            && !string.IsNullOrEmpty(reason.PrerequisiteKey))
            payload["prerequisiteKey"] = reason.PrerequisiteKey;
        if (reason.Kind == EvaluationReasonKind.Error)
            payload["errorKind"] = Regex.Replace(
                reason.ErrorKind?.ToString() ?? "UNKNOWN", "([a-z0-9])([A-Z])", "$1_$2")
                .ToUpperInvariant();
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

    public void Dispose()
    {
        gate.Drop();
        lock (_lock)
        {
            _client?.Dispose();
            _client = null;
        }
    }
}

/// <summary>
/// Reverse-proxies the real LaunchDarkly SSE stream and can cancel every active
/// response without touching the SDK client or its in-memory feature store.
/// </summary>
sealed class StreamGate : IDisposable
{
    private readonly Uri _origin;
    private readonly HttpClient _http = new() { Timeout = Timeout.InfiniteTimeSpan };
    private readonly ConcurrentDictionary<Guid, CancellationTokenSource> _active = new();
    private volatile bool _allowed = true;

    internal StreamGate(string origin) => _origin = new Uri(origin.TrimEnd('/') + "/");
    internal bool Allowed => _allowed;
    internal int ActiveCount => _active.Count;

    internal void Open() => _allowed = true;

    internal void Drop()
    {
        _allowed = false;
        foreach (var cancellation in _active.Values) cancellation.Cancel();
        _active.Clear();
    }

    internal async Task ProxyAsync(HttpContext context)
    {
        if (!_allowed)
        {
            context.Response.StatusCode = 503;
            context.Response.Headers.Connection = "close";
            await context.Response.WriteAsync("stream gate closed");
            return;
        }

        var destination = new Uri(_origin, context.Request.Path + context.Request.QueryString);
        using var request = new HttpRequestMessage(HttpMethod.Get, destination);
        CopyHeader(context, request, "Authorization");
        CopyHeader(context, request, "Accept");
        CopyHeader(context, request, "User-Agent");
        CopyHeader(context, request, "X-LaunchDarkly-Event-Schema");
        CopyHeader(context, request, "X-LaunchDarkly-Wrapper");

        var id = Guid.NewGuid();
        using var cancellation = CancellationTokenSource.CreateLinkedTokenSource(
            context.RequestAborted);
        try
        {
            using var response = await _http.SendAsync(
                request, HttpCompletionOption.ResponseHeadersRead, cancellation.Token);
            context.Response.StatusCode = (int)response.StatusCode;
            context.Response.ContentType =
                response.Content.Headers.ContentType?.ToString() ?? "text/event-stream";
            context.Response.Headers.CacheControl = "no-cache";
            if (!response.IsSuccessStatusCode)
                return;
            if (!_allowed)
            {
                context.Response.StatusCode = 503;
                return;
            }
            _active[id] = cancellation;
            await using var stream = await response.Content.ReadAsStreamAsync(cancellation.Token);
            await stream.CopyToAsync(context.Response.Body, cancellation.Token);
        }
        catch (OperationCanceledException)
        {
            // Drop stream and client disconnects intentionally cancel this copy.
        }
        catch (HttpRequestException)
        {
            if (!context.Response.HasStarted) context.Response.StatusCode = 502;
        }
        finally
        {
            _active.TryRemove(id, out _);
        }
    }

    private static void CopyHeader(
        HttpContext context, HttpRequestMessage request, string name)
    {
        if (context.Request.Headers.TryGetValue(name, out var value))
            request.Headers.TryAddWithoutValidation(name, value.ToArray());
    }

    public void Dispose()
    {
        Drop();
        _http.Dispose();
    }
}
