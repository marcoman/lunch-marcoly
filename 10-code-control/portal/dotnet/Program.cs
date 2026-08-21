// Portal — series shell for 10-code-control (.NET web examples 11–13).
//
// One process for the user:
//   - Serves wwwroot/index.html on :8103 (PORTAL_PORT)
//   - Spawns each example's existing `dotnet run` as a child
//   - Embeds those pages in iframes
//
// Twin of ../python (:8100), ../node (:8101), ../java (:8102).
// Standalone entrypoints under each example's dotnet/ still work alone.
// Ctrl+C / SIGTERM stops the portal and all children.

using System.Diagnostics;
using System.Net.Sockets;

const string AppBanner = "10-code-control[portal-dotnet]";
var portalPort = int.TryParse(Environment.GetEnvironmentVariable("PORTAL_PORT"), out var envPort)
    ? envPort
    : 8103;

var here = Directory.GetCurrentDirectory();
var seriesRoot = Path.GetFullPath(Path.Combine(here, "..", ".."));

var children = new[]
{
    new Child("11", "Flag enablement",
        Path.Combine(seriesRoot, "11-flag-enablement", "dotnet"),
        "11-flag-enablement.csproj", 8113),
    new Child("12", "Flag variations",
        Path.Combine(seriesRoot, "12-flag-variations", "dotnet"),
        "12-flag-variations.csproj", 8123),
    new Child("13", "Flag targeting rules",
        Path.Combine(seriesRoot, "13-flag-targeting-rules", "dotnet"),
        "13-flag-targeting-rules.csproj", 8133)
};

var procs = new Dictionary<string, Process>();
var shuttingDown = false;
var pipeLock = new object();

if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("LD_SDK_KEY")))
{
    Console.WriteLine(
        "WARNING: LD_SDK_KEY is unset. Child examples will fail to init " +
        "LaunchDarkly until you export a server-side SDK key.");
}

StartChildren();

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls($"http://127.0.0.1:{portalPort}");
builder.Logging.ClearProviders();

var app = builder.Build();

app.MapGet("/", ServeIndexAsync);
app.MapGet("/index.html", ServeIndexAsync);
app.MapGet("/api/status", () =>
{
    var list = children.Select(c =>
    {
        procs.TryGetValue(c.Id, out var proc);
        var alive = proc is { HasExited: false };
        return new
        {
            id = c.Id,
            label = c.Label,
            port = c.Port,
            url = $"http://127.0.0.1:{c.Port}/",
            spawned = proc != null,
            alive,
            up = PortOpen(c.Port),
        };
    }).ToList();
    return Results.Json(new
    {
        appBanner = AppBanner,
        portalPort,
        language = "dotnet",
        children = list,
    });
});

Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    Console.WriteLine($"\n{AppBanner}: shutting down …");
    StopChildren();
    Environment.Exit(0);
};
AppDomain.CurrentDomain.ProcessExit += (_, _) => StopChildren();

Console.WriteLine(AppBanner);
Console.WriteLine($"Open http://127.0.0.1:{portalPort}/");
Console.WriteLine("Tabs embed .NET examples on 8113 / 8123 / 8133.");
Console.WriteLine("Ctrl+C stops the portal and all children.");

app.Run();

async Task ServeIndexAsync(HttpContext ctx)
{
    var candidates = new[]
    {
        Path.Combine(here, "wwwroot", "index.html"),
        Path.Combine(AppContext.BaseDirectory, "wwwroot", "index.html"),
    };
    foreach (var path in candidates)
    {
        if (!File.Exists(path)) continue;
        ctx.Response.ContentType = "text/html; charset=utf-8";
        ctx.Response.Headers.CacheControl = "no-store";
        await ctx.Response.SendFileAsync(path);
        return;
    }
    ctx.Response.StatusCode = 404;
    await ctx.Response.WriteAsync("Not found");
}

void StartChildren()
{
    foreach (var child in children)
    {
        var cid = child.Id;
        if (!Directory.Exists(child.Cwd))
        {
            Console.Error.WriteLine($"[{cid}] ERROR: missing cwd {child.Cwd}");
            continue;
        }

        var project = Path.Combine(child.Cwd, child.ProjectFile);
        if (!File.Exists(project))
        {
            Console.Error.WriteLine($"[{cid}] ERROR: missing project {project}");
            continue;
        }

        if (PortOpen(child.Port))
        {
            Console.WriteLine(
                $"[{cid}] WARNING: port {child.Port} already in use — " +
                "assuming an existing server; not spawning.");
            continue;
        }

        Console.WriteLine($"[{cid}] Starting {child.ProjectFile} on :{child.Port} …");
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "dotnet",
                Arguments = $"run --project \"{project}\"",
                WorkingDirectory = child.Cwd,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            foreach (System.Collections.DictionaryEntry entry in Environment.GetEnvironmentVariables())
            {
                var key = entry.Key?.ToString();
                if (key is null) continue;
                psi.Environment[key] = entry.Value?.ToString() ?? "";
            }
            psi.Environment["PORT"] = child.Port.ToString();

            var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
            proc.OutputDataReceived += (_, e) =>
            {
                if (e.Data is null) return;
                lock (pipeLock) Console.WriteLine($"[{cid}] {e.Data}");
            };
            proc.ErrorDataReceived += (_, e) =>
            {
                if (e.Data is null) return;
                lock (pipeLock) Console.WriteLine($"[{cid}] {e.Data}");
            };
            proc.Start();
            proc.BeginOutputReadLine();
            proc.BeginErrorReadLine();
            procs[cid] = proc;

            if (WaitForPort(child.Port, TimeSpan.FromSeconds(90)))
            {
                Console.WriteLine($"[{cid}] Ready http://127.0.0.1:{child.Port}/");
            }
            else
            {
                var exit = proc.HasExited ? proc.ExitCode.ToString() : "running";
                Console.Error.WriteLine(
                    $"[{cid}] ERROR: port {child.Port} not ready (exit={exit}). " +
                    "Check LD_SDK_KEY and logs above.");
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[{cid}] ERROR: spawn failed: {ex.Message}");
        }
    }
}

void StopChildren()
{
    if (shuttingDown) return;
    shuttingDown = true;

    var items = procs.ToList();
    procs.Clear();
    foreach (var (cid, proc) in items)
    {
        if (proc.HasExited) continue;
        Console.WriteLine($"[{cid}] Stopping …");
        try
        {
            proc.Kill(entireProcessTree: true);
        }
        catch
        {
            try { proc.Kill(); } catch { /* best-effort */ }
        }
    }

    foreach (var (_, proc) in items)
    {
        try { proc.WaitForExit(2000); } catch { /* best-effort */ }
        proc.Dispose();
    }

    Console.WriteLine($"{AppBanner}: stopped.");
}

static bool PortOpen(int port)
{
    try
    {
        using var client = new TcpClient();
        var task = client.ConnectAsync("127.0.0.1", port);
        return task.Wait(TimeSpan.FromMilliseconds(350)) && client.Connected;
    }
    catch
    {
        return false;
    }
}

static bool WaitForPort(int port, TimeSpan timeout)
{
    var deadline = DateTime.UtcNow + timeout;
    while (DateTime.UtcNow < deadline)
    {
        if (PortOpen(port)) return true;
        Thread.Sleep(200);
    }
    return false;
}

sealed record Child(string Id, string Label, string Cwd, string ProjectFile, int Port);
