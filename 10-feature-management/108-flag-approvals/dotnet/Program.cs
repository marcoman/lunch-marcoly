using System.Text.Json.Nodes;

const string AppBanner = "108-flag-approvals[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8183;
var flags = new CountFlag();
var approvals = new Approvals();
var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/flags", (string? username) =>
{
    try { return Results.Json(flags.Evaluate(username)); }
    catch (ArgumentException exception)
    {
        return Results.BadRequest(new { error = exception.Message });
    }
});
app.MapGet("/api/approval", async () =>
{
    try { return Results.Json(await approvals.StateAsync()); }
    catch (Exception exception)
    {
        var body = approvals.ApiConfig();
        body["ok"] = false;
        body["request"] = null;
        body["error"] = exception.Message;
        return Results.Json(body, statusCode: 502);
    }
});
app.MapPost("/api/approval", async (HttpContext context) =>
{
    try
    {
        await ReadObjectAsync(context);
        return Results.Json(await approvals.RequestAsync());
    }
    catch (Exception exception)
    {
        return Error(exception);
    }
});
app.MapPost("/api/approval/apply", async (HttpContext context) =>
{
    try
    {
        var body = await ReadObjectAsync(context);
        return Results.Json(await approvals.ApplyAsync(body["id"]?.ToString()));
    }
    catch (Exception exception)
    {
        return Error(exception);
    }
});
app.MapPost("/api/approval/reset", async (HttpContext context) =>
{
    try
    {
        await ReadObjectAsync(context);
        return Results.Json(await approvals.ResetAsync());
    }
    catch (Exception exception)
    {
        return Error(exception);
    }
});

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
app.Run();

static IResult Error(Exception exception)
{
    var status = exception is ArgumentException or System.Text.Json.JsonException ? 400 : 502;
    if (exception is ApprovalResetException reset)
    {
        return Results.Json(new { ok = false, error = reset.Message, request = (object?)null, steps = reset.Steps }, statusCode: status);
    }
    return Results.Json(new { ok = false, error = exception.Message }, statusCode: status);
}

static async Task<JsonObject> ReadObjectAsync(HttpContext context)
{
    var node = await JsonNode.ParseAsync(context.Request.Body);
    return node as JsonObject ?? throw new ArgumentException("Request body must be a JSON object");
}

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
