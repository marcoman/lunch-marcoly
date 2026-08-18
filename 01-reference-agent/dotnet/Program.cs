// 01-reference-agent[dotnet] — thin HTTP adapter for the reference agent UI.
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
// Four jobs, no LaunchDarkly:
//
//   1. Serve wwwroot/index.html
//   2. JSON bootstrap (personas, tickers, cached stories, provider/model)
//   3. Yahoo Finance headlines
//   4. Bridge browser SSE → AgentCore.GenerateStreamAsync()
//
// This is the baseline the 20-agent-config/2x .NET ports build on. Compare this
// file to 20-agent-config/21-agent-completion-config/dotnet/Program.cs to see
// exactly what LaunchDarkly AgentControl adds on top (nothing here changes shape —
// only AgentCore.cs grows an SDK call).
//
// Request map
// -----------
//   GET  /                 → wwwroot/index.html
//   GET  /api/bootstrap    → personas, default tickers, cached stories, provider/model
//   GET  /api/stories      → latest 2 headlines for ticker1 + ticker2
//   POST /api/generate     → text/event-stream of generation events

using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using ReferenceAgent;

const string AppBanner = "01-reference-agent[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var p) ? p : 8090;

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

var startupMode = AgentCore.ResolveMode();
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine($"AGENT_LLM_MODE={startupMode} model={AgentCore.ModelLabel(startupMode)}");
Console.WriteLine("Press Ctrl+C to stop.");

app.Run();

static async Task ServeIndexAsync(HttpContext ctx)
{
    var path = Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html");
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
    var mode = AgentCore.ResolveMode();
    var cached = YahooNews.GetLastPairCached();
    var personas = AgentCore.Personas.Select(p => new Dictionary<string, object?>
    {
        ["id"] = p.Id,
        ["name"] = p.Name,
        ["profile"] = p.Profile,
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
        ["mode"] = mode,
        ["provider"] = AgentCore.ProviderLabel(mode),
        ["model"] = AgentCore.ModelLabel(mode),
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

    var stories = new List<Dictionary<string, object?>>();
    if (payload?["stories"] is JsonArray storiesArr)
    {
        foreach (var item in storiesArr)
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
        await foreach (var evt in AgentCore.GenerateStreamAsync(persona, stories, ctx.RequestAborted))
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
