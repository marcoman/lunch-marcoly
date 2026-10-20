using System.Text.Json.Nodes;

const string AppBanner = "17-scheduled-changes[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8173;
var flags = new ScheduledHighlight();
var controls = new ScheduledChangeControls();
var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", () => Results.Json(new
{
    appBanner = AppBanner,
    flagKey = ScheduledHighlight.FlagKey,
    controls = controls.ApiConfig(),
    port,
}));
app.MapGet("/api/flags", (string? username) =>
{
    try { return Results.Json(flags.Evaluate(username ?? "")); }
    catch (ArgumentException exception)
    {
        return Results.BadRequest(new { error = exception.Message });
    }
});
app.MapGet("/api/schedule", async () =>
{
    try { return Results.Json(await controls.ListAsync()); }
    catch (Exception exception)
    {
        return Results.Json(new { error = exception.Message }, statusCode: 502);
    }
});
app.MapPost("/api/schedule", async (HttpContext context) =>
{
    try
    {
        var body = await JsonNode.ParseAsync(context.Request.Body) as JsonObject
            ?? throw new ArgumentException("Request body must be a JSON object");
        var minutesNode = body["minutes"];
        var minutes = minutesNode is JsonValue value && value.TryGetValue<int>(out var parsed)
            ? parsed
            : 0;
        return Results.Json(await controls.StartAsync(minutes), statusCode: 201);
    }
    catch (Exception exception)
    {
        var status = exception is ArgumentException or System.Text.Json.JsonException ? 400 : 502;
        return Results.Json(new { ok = false, error = exception.Message }, statusCode: status);
    }
});
app.MapDelete("/api/schedule", async () =>
{
    try { return Results.Json(await controls.StopAsync()); }
    catch (Exception exception)
    {
        return Results.Json(new { ok = false, error = exception.Message }, statusCode: 502);
    }
});

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
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
