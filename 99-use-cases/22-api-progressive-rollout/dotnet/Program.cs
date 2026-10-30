using System.Text.Json.Nodes;

const string AppBanner = "22-api-progressive-rollout[dotnet]";
using var flags = new HighlightEval();

if (args is ["--evaluate-once", var username])
{
    Console.WriteLine(flags.Evaluate(username).ToJsonString());
    return;
}

var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8783;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/highlight", (string? username) =>
{
    if (string.IsNullOrWhiteSpace(username))
        return Results.Text("{\"error\":\"username query parameter is required\"}", "application/json", statusCode: 400);
    return Results.Text(flags.Evaluate(username.Trim()).ToJsonString(), "application/json");
});
app.MapGet("/api/release", async () => Json(await ReleaseStatus.LatestAsync()));
app.MapGet("/api/bootstrap", () => Json(new JsonObject
{
    ["flagKey"] = HighlightEval.FlagHighlight,
    ["targetingUrl"] = ReleaseStatus.TargetingUrl(),
    ["schedule"] = ReleaseStatus.Schedule(),
}));
app.MapPost("/api/release/start", async () => Json(await ReleaseStatus.StartAsync()));
app.MapPost("/api/release/stop", async () => Json(await ReleaseStatus.StopAsync()));
app.MapPost("/api/release/reset", async () => Json(await ReleaseStatus.ResetAsync()));

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine("Press Ctrl+C to stop.");
app.Run();

static IResult Json(JsonObject body)
{
    var failed = body["error"]?.GetValue<bool>() == true || body["configured"]?.GetValue<bool>() == false;
    return Results.Text(body.ToJsonString(), "application/json", statusCode: failed ? 400 : 200);
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
