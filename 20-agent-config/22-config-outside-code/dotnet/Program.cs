// 22-config-outside-code.dotnet — thin HTTP adapter for the tracked-completion demo UI.
//
//   GET  /                 → wwwroot/index.html
//   GET  /api/bootstrap    → personas, tickers, cached stories, config key
//   GET  /api/stories      → Yahoo headlines
//   POST /api/generate     → SSE (TrackMetricsOf path)
//   POST /api/feedback     → thumbs via resumption token
//
// LaunchDarkly work lives in AgentCore (CompletionConfig + TrackMetricsOf + TrackFeedback).

using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using ConfigOutsideCode;

const string AppBanner = "22-config-outside-code[dotnet]";

AgentCore.InitLaunchDarkly();

var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var envPort) ? envPort : 8223;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.ConfigureKestrel(options => options.Listen(IPAddress.Loopback, port));
builder.Logging.ClearProviders();
builder.Logging.AddSimpleConsole(o => o.SingleLine = true);

var app = builder.Build();

var json = new JsonSerializerOptions { WriteIndented = false };

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/bootstrap", () =>
{
    var cached = YahooNews.GetLastPairCached();
    var personas = AgentCore.Personas
        .Select(p => new Dictionary<string, object?>
        {
            ["id"] = p.Id,
            ["name"] = p.Name,
            ["profile"] = p.Profile,
            ["anonymous"] = p.Anonymous,
        })
        .ToList();

    var body = new Dictionary<string, object?>
    {
        ["appBanner"] = AppBanner,
        ["personas"] = personas,
        ["defaultTickers"] = new Dictionary<string, object?>
        {
            ["ticker1"] = cached?["ticker1"]?.GetValue<string>() ?? YahooNews.DefaultTicker1,
            ["ticker2"] = cached?["ticker2"]?.GetValue<string>() ?? YahooNews.DefaultTicker2,
        },
        ["cachedStories"] = cached,
        ["mode"] = "launchdarkly",
        ["provider"] = "AgentControl",
        ["model"] = $"config:{AgentCore.ConfigKey()}",
        ["configKey"] = AgentCore.ConfigKey(),
    };
    return Results.Json(body, json);
});

app.MapGet("/api/stories", async (HttpContext ctx) =>
{
    var ticker1 = ctx.Request.Query["ticker1"].FirstOrDefault() ?? YahooNews.DefaultTicker1;
    var ticker2 = ctx.Request.Query["ticker2"].FirstOrDefault() ?? YahooNews.DefaultTicker2;
    var result = await YahooNews.FetchStoriesForTickersAsync(ticker1, ticker2, 2);
    return Results.Json(result, json);
});

app.MapPost("/api/generate", async (HttpContext ctx) =>
{
    JsonNode? payload;
    try
    {
        payload = await JsonNode.ParseAsync(ctx.Request.Body);
    }
    catch
    {
        ctx.Response.StatusCode = 400;
        await ctx.Response.WriteAsJsonAsync(new { error = "Invalid JSON body." });
        return;
    }

    var personaId = payload?["personaId"]?.GetValue<string>() ?? AgentCore.Personas[0].Id;
    var persona = AgentCore.PersonaById(personaId) ?? AgentCore.Personas[0];
    var stories = (payload?["stories"] as JsonArray)?.ToList() ?? new List<JsonNode?>();

    ctx.Response.ContentType = "text/event-stream; charset=utf-8";
    ctx.Response.Headers.CacheControl = "no-store";
    ctx.Response.Headers.Connection = "close";

    try
    {
        await foreach (var evt in AgentCore.GenerateStreamAsync(persona, stories))
        {
            await ctx.Response.WriteAsync($"data: {JsonSerializer.Serialize(evt, json)}\n\n");
            await ctx.Response.Body.FlushAsync();
        }
    }
    catch (Exception exc) when (exc is IOException or OperationCanceledException)
    {
        // Client disconnected mid-stream — nothing to report.
    }
});

app.MapPost("/api/feedback", async (HttpContext ctx) =>
{
    JsonNode? payload;
    try
    {
        payload = await JsonNode.ParseAsync(ctx.Request.Body);
    }
    catch
    {
        return Results.Json(new { error = "Invalid JSON body." }, json, statusCode: 400);
    }

    var personaId = payload?["personaId"]?.GetValue<string>() ?? AgentCore.Personas[0].Id;
    var persona = AgentCore.PersonaById(personaId) ?? AgentCore.Personas[0];
    var token = payload?["resumptionToken"]?.GetValue<string>() ?? "";
    var kind = payload?["kind"]?.GetValue<string>() ?? "";

    try
    {
        return Results.Json(AgentCore.SubmitFeedback(persona, token, kind), json);
    }
    catch (Exception exc)
    {
        return Results.Json(new Dictionary<string, object?> { ["error"] = exc.Message }, json, statusCode: 400);
    }
});

Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine($"LD_AGENT_CONFIG_KEY={AgentCore.ConfigKey()}");
Console.WriteLine("Press Ctrl+C to stop.");

app.Run();
