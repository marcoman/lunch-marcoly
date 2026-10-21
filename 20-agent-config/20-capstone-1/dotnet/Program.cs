// 20-capstone — thin HTTP adapter.
//
// GET  /              → wwwroot/index.html
// GET  /api/bootstrap → personas, tools, graph keys, persisted stories
// GET  /api/stories   → headlines
// POST /api/generate  → SSE
// POST /api/feedback  → thumbs on the specialist draft
//
// LaunchDarkly work lives in AgentCore.cs.

using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Capstone;

const string AppBanner = "20-capstone[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var envPort) ? envPort : 8293;

AgentCore.InitLaunchDarkly();

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
builder.Logging.AddSimpleConsole(o => o.SingleLine = true);
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", HandleBootstrapAsync);
app.MapGet("/api/stories", HandleStoriesAsync);
app.MapPost("/api/generate", HandleGenerateAsync);
app.MapPost("/api/feedback", HandleFeedbackAsync);

Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine($"LD_GRAPH_KEY={AgentCore.GraphKey()}");
Console.WriteLine("Press Ctrl+C to stop.");
app.Run();

static async Task ServeIndexAsync(HttpContext ctx)
{
    var path = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
    if (!File.Exists(path)) path = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot", "index.html");
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
    await WriteJsonAsync(ctx, 200, new Dictionary<string, object?>
    {
        ["appBanner"] = AppBanner,
        ["personas"] = AgentCore.Personas.Select(p => new Dictionary<string, object?>
        {
            ["id"] = p.Id, ["name"] = p.Name, ["profile"] = p.Profile, ["anonymous"] = p.Anonymous,
        }).ToList(),
        ["tools"] = AgentCore.Tools,
        ["actions"] = new[]
        {
            new Dictionary<string, string> { ["id"] = "report", ["labelKey"] = "actionReport" },
            new Dictionary<string, string> { ["id"] = "questions", ["labelKey"] = "actionQuestions" },
            new Dictionary<string, string> { ["id"] = "good", ["labelKey"] = "actionGood" },
        },
        ["graphKey"] = AgentCore.GraphKey(),
        ["nodeKeys"] = new Dictionary<string, string>
        {
            ["assess"] = AgentCore.NodeKey("assess"),
            ["report"] = AgentCore.NodeKey("report"),
            ["questions"] = AgentCore.NodeKey("questions"),
            ["good"] = AgentCore.NodeKey("good"),
            ["finalize"] = AgentCore.NodeKey("finalize"),
        },
        ["judgeKeys"] = new[] { AgentCore.JudgeKey("fidelity"), AgentCore.JudgeKey("discipline") },
        ["defaultTickers"] = new Dictionary<string, object?>
        {
            ["ticker1"] = cached?.GetValueOrDefault("ticker1") ?? YahooNews.DefaultTicker1,
            ["ticker2"] = cached?.GetValueOrDefault("ticker2") ?? YahooNews.DefaultTicker2,
        },
        ["persistedStories"] = cached == null ? null : new Dictionary<string, object?>
        {
            ["ticker1"] = cached.GetValueOrDefault("ticker1"),
            ["ticker2"] = cached.GetValueOrDefault("ticker2"),
            ["tickers"] = cached.GetValueOrDefault("tickers"),
            ["savedAt"] = cached.GetValueOrDefault("updated_at"),
            ["directory"] = "20-agent-config/stories",
        },
    });
}

static async Task HandleStoriesAsync(HttpContext ctx)
{
    var ticker1 = ctx.Request.Query["ticker1"].FirstOrDefault() ?? YahooNews.DefaultTicker1;
    var ticker2 = ctx.Request.Query["ticker2"].FirstOrDefault() ?? YahooNews.DefaultTicker2;
    await WriteJsonAsync(ctx, 200, await YahooNews.FetchStoriesForTickersAsync(ticker1, ticker2, 2));
}

static async Task HandleGenerateAsync(HttpContext ctx)
{
    var payload = await ReadPayloadAsync(ctx);
    if (payload == null)
    {
        await WriteJsonAsync(ctx, 400, new Dictionary<string, object?> { ["error"] = "Invalid JSON body." });
        return;
    }
    var persona = AgentCore.PersonaById(JsonUtil.AsString(payload["personaId"]) ?? "") ?? AgentCore.Personas[1];
    var action = JsonUtil.AsString(payload["action"]) ?? "report";
    var locale = JsonUtil.AsString(payload["locale"]) == "es" ? "es" : "en";
    var tools = new List<string>();
    if (payload["tools"] is JsonArray toolArr)
    {
        foreach (var item in toolArr)
        {
            var value = JsonUtil.AsString(item);
            if (!string.IsNullOrEmpty(value)) tools.Add(value);
        }
    }
    var stories = new List<Dictionary<string, object?>>();
    if (payload["stories"] is JsonArray storyArr)
    {
        foreach (var item in storyArr)
        {
            if (item is JsonObject obj) stories.Add(JsonUtil.ToMap(obj));
        }
    }
    ctx.Response.StatusCode = 200;
    ctx.Response.ContentType = "text/event-stream; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    ctx.Response.Headers.Connection = "close";
    try
    {
        await foreach (var evt in AgentCore.GenerateStreamAsync(persona, action, stories, tools, locale, ctx.RequestAborted))
        {
            await ctx.Response.WriteAsync($"data: {JsonSerializer.Serialize(evt)}\n\n", Encoding.UTF8, ctx.RequestAborted);
            await ctx.Response.Body.FlushAsync(ctx.RequestAborted);
        }
    }
    catch (OperationCanceledException) { }
    catch (Exception exc)
    {
        await ctx.Response.WriteAsync(
            $"data: {JsonSerializer.Serialize(new Dictionary<string, object?> { ["type"] = "error", ["message"] = exc.Message })}\n\n",
            Encoding.UTF8);
    }
}

static async Task HandleFeedbackAsync(HttpContext ctx)
{
    var payload = await ReadPayloadAsync(ctx);
    if (payload == null)
    {
        await WriteJsonAsync(ctx, 400, new Dictionary<string, object?> { ["error"] = "Invalid JSON body." });
        return;
    }
    var persona = AgentCore.PersonaById(JsonUtil.AsString(payload["personaId"]) ?? "") ?? AgentCore.Personas[1];
    try
    {
        var body = AgentCore.SubmitFeedback(
            persona,
            JsonUtil.AsString(payload["locale"]) ?? "en",
            JsonUtil.AsString(payload["resumptionToken"]) ?? "",
            JsonUtil.AsString(payload["kind"]) ?? "");
        await WriteJsonAsync(ctx, 200, body);
    }
    catch (ArgumentException exc)
    {
        await WriteJsonAsync(ctx, 400, new Dictionary<string, object?> { ["ok"] = false, ["error"] = exc.Message });
    }
}

static async Task<JsonNode?> ReadPayloadAsync(HttpContext ctx)
{
    using var reader = new StreamReader(ctx.Request.Body, Encoding.UTF8);
    var raw = await reader.ReadToEndAsync();
    try
    {
        return string.IsNullOrWhiteSpace(raw) ? new JsonObject() : JsonNode.Parse(raw);
    }
    catch
    {
        return null;
    }
}
