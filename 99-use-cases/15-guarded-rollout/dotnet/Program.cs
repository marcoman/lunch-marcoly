using System.Text.Json;
using System.Text.Json.Serialization;

const string AppBanner = "15-guarded-rollout[dotnet]";
using var flags = new HighlightEval();

if (args is ["--evaluate-once", var username])
{
    Console.WriteLine(JsonSerializer.Serialize(flags.Evaluate(username), JsonOptions.Web));
    return;
}

var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8080;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();
var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/highlight", (string? username) =>
{
    if (string.IsNullOrWhiteSpace(username))
        return Results.Json(new { error = "username query parameter is required" }, statusCode: 400);
    return Results.Json(flags.Evaluate(username.Trim()), JsonOptions.Web);
});

app.Lifetime.ApplicationStopping.Register(flags.Dispose);
Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{port}/");
Console.WriteLine("Press Ctrl+C to stop.");
app.Run();

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

static class JsonOptions
{
    internal static readonly JsonSerializerOptions Web = new(JsonSerializerDefaults.Web)
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
    };
}
