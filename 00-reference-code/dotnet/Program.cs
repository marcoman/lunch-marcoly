// 00-reference-code[dotnet] — baseline static grid navigator, with no LaunchDarkly.

const string AppBanner = "00-reference-code[dotnet]";
var port = int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var configuredPort)
    ? configuredPort
    : 8080;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.Logging.ClearProviders();

var app = builder.Build();
app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);

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
