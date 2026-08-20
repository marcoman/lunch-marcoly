// 25-agent-graph — thin HTTP adapter for the Agent Graphs demo.
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
//   1. Serve wwwroot/index.html
//   2. JSON bootstrap (personas, tickers, graph/node keys, actions)
//   3. Yahoo Finance headlines
//   4. Bridge browser SSE → AgentCore.GenerateStreamAsync()
//
// The LaunchDarkly work lives in AgentCore.cs (AgentGraph + AgentConfig).
//
// Request map
// -----------
//   GET  /                 → index.html
//   GET  /api/bootstrap    → personas, tickers, graphKey, nodeKeys, actions
//   GET  /api/stories      → Yahoo headlines for two tickers
//   POST /api/generate     → SSE (assess → specialist → finalize)

using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using AgentGraph;

const string AppBanner = "25-agent-graph[dotnet]";
var Port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var envPort) ? envPort : 8253;

AgentCore.InitLaunchDarkly();

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{Port}");
builder.Logging.ClearProviders();
builder.Logging.AddSimpleConsole(o => o.SingleLine = true);

var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", HandleBootstrapAsync);
app.MapGet("/api/stories", HandleStoriesAsync);
app.MapPost("/api/generate", HandleGenerateAsync);

Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{Port}/");
Console.WriteLine($"LD_GRAPH_KEY={AgentCore.GraphKey()}");
Console.WriteLine(
    "Nodes: " + string.Join(", ", new[] { "assess", "report", "questions", "good", "joke", "finalize" }
        .Select(r => $"{r}={AgentCore.NodeKey(r)}")));
Console.WriteLine("Press Ctrl+C to stop.");

app.Run();

static async Task ServeIndexAsync(HttpContext ctx)
{
    var path = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
    if (!File.Exists(path))
    {
        path = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot", "index.html");
    }
    if (!File.Exists(path))
    {
        ctx.Response.StatusCode = 404;
        await ctx.Response.WriteAsync("Not found");
        return;
    }
    ctx.Response.ContentType = "text/html; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    await ctx.Response.Body.WriteAsync(await File.ReadAllBytesAsync(path));
}

static async Task WriteJsonAsync(HttpContext ctx, int status, object? body)
{
    ctx.Response.StatusCode = status;
    ctx.Response.ContentType = "application/json; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    await ctx.Response.WriteAsync(JsonSerializer.Serialize(body), Encoding.UTF8);
}

static async Task HandleBootstrapAsync(HttpContext ctx)
{
    var cached = YahooNews.GetLastPairCached();
    var personas = AgentCore.Personas.Select(p => new Dictionary<string, object?>
    {
        ["id"] = p.Id,
        ["name"] = p.Name,
        ["profile"] = p.Profile,
        ["anonymous"] = p.Anonymous,
    }).ToList();

    var body = new Dictionary<string, object?>
    {
        ["appBanner"] = AppBanner,
        ["personas"] = personas,
        ["defaultTickers"] = new Dictionary<string, object?>
        {
            ["ticker1"] = (cached?.GetValueOrDefault("ticker1") as string) ?? YahooNews.DefaultTicker1,
            ["ticker2"] = (cached?.GetValueOrDefault("ticker2") as string) ?? YahooNews.DefaultTicker2,
        },
        ["cachedStories"] = cached,
        ["mode"] = "launchdarkly-agent-graph",
        ["provider"] = "AgentControl",
        ["model"] = $"graph:{AgentCore.GraphKey()}",
        ["graphKey"] = AgentCore.GraphKey(),
        ["nodeKeys"] = new Dictionary<string, object?>
        {
            ["assess"] = AgentCore.NodeKey("assess"),
            ["report"] = AgentCore.NodeKey("report"),
            ["questions"] = AgentCore.NodeKey("questions"),
            ["good"] = AgentCore.NodeKey("good"),
            ["joke"] = AgentCore.NodeKey("joke"),
            ["finalize"] = AgentCore.NodeKey("finalize"),
        },
        ["actions"] = new List<Dictionary<string, object?>>
        {
            new() { ["id"] = "report", ["label"] = "Generate AI Report", ["needsStories"] = true },
            new() { ["id"] = "questions", ["label"] = "Identify questions", ["needsStories"] = true },
            new() { ["id"] = "good", ["label"] = "Identify good & bad", ["needsStories"] = true },
            new() { ["id"] = "joke", ["label"] = "Tell me a joke", ["needsStories"] = false },
        },
    };
    await WriteJsonAsync(ctx, 200, body);
}

static async Task HandleStoriesAsync(HttpContext ctx)
{
    var ticker1 = ctx.Request.Query["ticker1"].FirstOrDefault() ?? YahooNews.DefaultTicker1;
    var ticker2 = ctx.Request.Query["ticker2"].FirstOrDefault() ?? YahooNews.DefaultTicker2;
    var body = await YahooNews.FetchStoriesForTickersAsync(ticker1, ticker2, 2);
    await WriteJsonAsync(ctx, 200, body);
}

static List<Dictionary<string, object?>> ReadStoriesPayload(JsonNode? payload)
{
    var stories = new List<Dictionary<string, object?>>();

    // Match Python/Node: payload.stories. Also accept tickerResults (Java alias).
    JsonArray? arr = null;
    if (payload?["stories"] is JsonArray storiesArr) arr = storiesArr;
    else if (payload?["tickerResults"] is JsonArray tickerArr) arr = tickerArr;

    if (arr == null) return stories;
    foreach (var item in arr)
    {
        if (item is JsonObject obj) stories.Add(JsonUtil.ToMap(obj));
    }
    return stories;
}

static async Task HandleGenerateAsync(HttpContext ctx)
{
    string raw;
    using (var reader = new StreamReader(ctx.Request.Body, Encoding.UTF8))
    {
        raw = await reader.ReadToEndAsync();
    }

    JsonNode? payload;
    try
    {
        payload = string.IsNullOrWhiteSpace(raw) ? new JsonObject() : JsonNode.Parse(raw);
    }
    catch
    {
        await WriteJsonAsync(ctx, 400, new Dictionary<string, object?> { ["error"] = "Invalid JSON body." });
        return;
    }

    var personaId = JsonUtil.AsString(payload?["personaId"]) ?? AgentCore.Personas[0].Id;
    var persona = AgentCore.PersonaById(personaId) ?? AgentCore.Personas[0];
    var action = (JsonUtil.AsString(payload?["action"]) ?? "report").Trim().ToLowerInvariant();
    var stories = ReadStoriesPayload(payload);

    ctx.Response.StatusCode = 200;
    ctx.Response.ContentType = "text/event-stream; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    ctx.Response.Headers.Connection = "close";

    try
    {
        await foreach (var evt in AgentCore.GenerateStreamAsync(persona, action, stories, ctx.RequestAborted))
        {
            var line = $"data: {JsonSerializer.Serialize(evt)}\n\n";
            await ctx.Response.WriteAsync(line, Encoding.UTF8, ctx.RequestAborted);
            await ctx.Response.Body.FlushAsync(ctx.RequestAborted);
        }
    }
    catch (OperationCanceledException)
    {
        // Client disconnected.
    }
}
