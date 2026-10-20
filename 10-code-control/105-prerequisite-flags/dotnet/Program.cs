using System.Text.Json.Nodes;

const string AppBanner = "15-prerequisite-flags[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8080;
var flags = new Prerequisite();
var controls = new FlagControls();
var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/bootstrap", () => Results.Json(new
{
    appBanner = AppBanner,
    controls = controls.ApiConfig(),
}));
app.MapGet("/api/flags", (string? username) =>
{
    try
    {
        return Results.Json(flags.Evaluate(username ?? ""));
    }
    catch (ArgumentException exception)
    {
        return Results.BadRequest(new { error = exception.Message });
    }
});
app.MapGet("/api/flag-controls", async () =>
{
    try { return Results.Json(await controls.ListAsync()); }
    catch (Exception exception)
    {
        return Results.Json(new { configured = true, flags = Array.Empty<object>(), error = exception.Message },
            statusCode: 502);
    }
});
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
        var hasFallthrough = body.ContainsKey("fallthrough");
        var fallthrough = hasFallthrough ? body["fallthrough"] : null;
        return Results.Json(await controls.ApplyAsync(key, on, hasFallthrough, fallthrough));
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
