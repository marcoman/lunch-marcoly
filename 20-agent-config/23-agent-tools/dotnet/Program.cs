/*
 * Program.cs — thin HTTP adapter for the 23-agent-tools tools demo UI.
 *
 *   1. Serve wwwroot/index.html
 *   2. JSON bootstrap (personas, cached tickers, config key)
 *   3. Yahoo Finance headlines
 *   4. Bridge browser SSE -> AgentCore.GenerateStreamAsync() (tool loop)
 *
 * LaunchDarkly work lives in AgentCore.cs (CompletionConfig + tools + TrackToolCall).
 */

using System.Text;
using System.Text.Json.Nodes;
using AgentTools;

const string AppBanner = "23-agent-tools[dotnet]";
var Port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var envPort) ? envPort : 8233;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{Port}");
builder.Logging.SetMinimumLevel(LogLevel.Warning);

var app = builder.Build();

var wwwroot = Path.Combine(AppContext.BaseDirectory, "wwwroot");
if (!Directory.Exists(wwwroot))
{
    // dotnet run copies wwwroot to bin/*, but fall back to the source tree for dotnet watch/edit loops.
    wwwroot = Path.Combine(Directory.GetCurrentDirectory(), "wwwroot");
}

app.MapGet("/", async (HttpContext ctx) => await ServeIndexAsync(ctx, wwwroot));
app.MapGet("/index.html", async (HttpContext ctx) => await ServeIndexAsync(ctx, wwwroot));

app.MapGet("/api/bootstrap", async (HttpContext ctx) =>
{
    var cached = YahooNews.GetLastPairCached();
    var personas = new JsonArray();
    foreach (var p in AgentCore.Personas)
    {
        var row = new JsonObject
        {
            ["id"] = p.Id,
            ["name"] = p.Name,
            ["profile"] = p.Profile,
        };
        if (p.Model is not null) row["model"] = p.Model;
        row["anonymous"] = p.Anonymous;
        personas.Add(row);
    }

    var body = new JsonObject
    {
        ["appBanner"] = AppBanner,
        ["personas"] = personas,
        ["defaultTickers"] = new JsonObject
        {
            ["ticker1"] = cached?["ticker1"]?.GetValue<string>() ?? YahooNews.DefaultTicker1,
            ["ticker2"] = cached?["ticker2"]?.GetValue<string>() ?? YahooNews.DefaultTicker2,
        },
        ["cachedStories"] = cached?.DeepClone(),
        ["mode"] = "launchdarkly",
        ["provider"] = "AgentControl",
        ["model"] = $"config:{AgentCore.ConfigKey()}",
        ["configKey"] = AgentCore.ConfigKey(),
    };
    await SendJsonAsync(ctx, 200, body);
});

app.MapGet("/api/stories", async (HttpContext ctx) =>
{
    var ticker1 = ctx.Request.Query["ticker1"].FirstOrDefault() ?? YahooNews.DefaultTicker1;
    var ticker2 = ctx.Request.Query["ticker2"].FirstOrDefault() ?? YahooNews.DefaultTicker2;
    try
    {
        var body = await YahooNews.FetchStoriesForTickersAsync(ticker1, ticker2, 2);
        await SendJsonAsync(ctx, 200, body);
    }
    catch (Exception exc)
    {
        await SendJsonAsync(ctx, 500, new JsonObject { ["error"] = exc.Message });
    }
});

app.MapPost("/api/generate", async (HttpContext ctx) =>
{
    string raw;
    using (var reader = new StreamReader(ctx.Request.Body, Encoding.UTF8))
    {
        raw = await reader.ReadToEndAsync();
    }

    JsonObject payload;
    try
    {
        payload = (string.IsNullOrWhiteSpace(raw) ? new JsonObject() : JsonNode.Parse(raw) as JsonObject) ?? new JsonObject();
    }
    catch
    {
        await SendJsonAsync(ctx, 400, new JsonObject { ["error"] = "Invalid JSON body." });
        return;
    }

    var personaId = payload["personaId"]?.GetValue<string>() ?? AgentCore.Personas[0].Id;
    var persona = AgentCore.PersonaById(personaId) ?? AgentCore.Personas[0];
    var stories = payload["stories"] as JsonArray ?? new JsonArray();

    ctx.Response.StatusCode = 200;
    ctx.Response.Headers.ContentType = "text/event-stream; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    ctx.Response.Headers.Connection = "close";

    try
    {
        await foreach (var evt in AgentCore.GenerateStreamAsync(persona, stories))
        {
            var line = $"data: {evt.ToJsonString()}\n\n";
            await ctx.Response.Body.WriteAsync(Encoding.UTF8.GetBytes(line));
            await ctx.Response.Body.FlushAsync();
        }
    }
    catch (OperationCanceledException)
    {
        // Client disconnected mid-stream.
    }
});

AgentCore.InitLaunchDarkly();

Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{Port}/");
Console.WriteLine($"LD_AGENT_CONFIG_KEY={AgentCore.ConfigKey()}");
Console.WriteLine("Press Ctrl+C to stop.");

app.Run();
return;

static async Task ServeIndexAsync(HttpContext ctx, string wwwroot)
{
    var path = Path.Combine(wwwroot, "index.html");
    if (!File.Exists(path))
    {
        ctx.Response.StatusCode = 404;
        await ctx.Response.WriteAsync("Not found");
        return;
    }
    var bytes = await File.ReadAllBytesAsync(path);
    ctx.Response.StatusCode = 200;
    ctx.Response.Headers.ContentType = "text/html; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    await ctx.Response.Body.WriteAsync(bytes);
}

static async Task SendJsonAsync(HttpContext ctx, int status, JsonNode body)
{
    var raw = Encoding.UTF8.GetBytes(body.ToJsonString());
    ctx.Response.StatusCode = status;
    ctx.Response.Headers.ContentType = "application/json; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    await ctx.Response.Body.WriteAsync(raw);
}
