using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Control pending scheduled changes for this lesson's dedicated flag.
/// Scheduled changes API: https://launchdarkly.com/docs/api/scheduled-changes
/// </summary>
sealed class ScheduledChangeControls
{
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(30) };

    public object ApiConfig() => new
    {
        configured = Missing().Count == 0,
        missing = Missing(),
        projectKey = Env("LD_PROJECT_KEY"),
        environmentKey = Env("LD_ENVIRONMENT_KEY"),
        apiHost = ApiHost,
    };

    public async Task<object> ListAsync()
    {
        if (Missing().Count > 0)
            return ConfigWithItems([]);
        var response = await RequestAsync(HttpMethod.Get, BasePath);
        var items = (response["items"] as JsonArray ?? [])
            .OrderBy(item => Long(item?["executionDate"]))
            .Select(Summarize)
            .ToArray();
        return ConfigWithItems(items);
    }

    /// <summary>
    /// Replace pending schedules, turn the flag off now, then schedule turnFlagOn.
    /// </summary>
    public async Task<object> StartAsync(int minutes)
    {
        if (minutes is < 1 or > 60)
            throw new ArgumentException("minutes must be between 1 and 60");
        var deleted = await DeletePendingAsync();
        await TurnOffAsync("17-scheduled-changes: reset off before starting demo");

        var startedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        var executionDate = startedAt + minutes * 60_000L;
        var created = await RequestAsync(HttpMethod.Post, BasePath, new JsonObject
        {
            ["executionDate"] = executionDate,
            ["instructions"] = new JsonArray(new JsonObject { ["kind"] = "turnFlagOn" }),
            ["comment"] = $"17-scheduled-changes: turn highlight on after {minutes} minute(s)",
        });
        return new
        {
            ok = true,
            replacedCount = deleted,
            minutes,
            startedAt,
            scheduledChange = Summarize(created, startedAt, executionDate),
        };
    }

    /// <summary>Cancel pending changes and turn the flag off immediately.</summary>
    public async Task<object> StopAsync()
    {
        var cancelled = await DeletePendingAsync();
        await TurnOffAsync("17-scheduled-changes: stop demo and turn highlight off");
        return new
        {
            ok = true,
            cancelledCount = cancelled,
            stoppedAt = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
        };
    }

    private async Task<int> DeletePendingAsync()
    {
        RequireConfigured();
        var response = await RequestAsync(HttpMethod.Get, BasePath);
        var deleted = 0;
        foreach (var item in response["items"] as JsonArray ?? [])
        {
            var id = item?["_id"]?.ToString();
            if (string.IsNullOrEmpty(id)) continue;
            await RequestAsync(HttpMethod.Delete, $"{BasePath}/{Escape(id)}");
            deleted++;
        }
        return deleted;
    }

    private Task<JsonObject> TurnOffAsync(string comment) =>
        RequestAsync(HttpMethod.Patch, $"/flags/{Escape(Project)}/{Escape(ScheduledHighlight.FlagKey)}",
            new JsonObject
            {
                ["environmentKey"] = EnvironmentKey,
                ["comment"] = comment,
                ["instructions"] = new JsonArray(new JsonObject { ["kind"] = "turnFlagOff" }),
            }, semanticPatch: true);

    private async Task<JsonObject> RequestAsync(
        HttpMethod method, string path, JsonObject? body = null, bool semanticPatch = false)
    {
        RequireConfigured();
        using var request = new HttpRequestMessage(method, $"{ApiHost.TrimEnd('/')}/api/v2{path}");
        request.Headers.TryAddWithoutValidation("Authorization", Token);
        request.Headers.Add("LD-API-Version", Env("LD_API_VERSION") ?? "20240415");
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        if (body is not null)
        {
            request.Content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            request.Content.Headers.ContentType = MediaTypeHeaderValue.Parse(semanticPatch
                ? "application/json; domain-model=launchdarkly.semanticpatch"
                : "application/json");
        }
        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            string message;
            try { message = JsonNode.Parse(raw)?["message"]?.ToString() ?? raw; }
            catch { message = raw; }
            throw new InvalidOperationException(
                $"LaunchDarkly API {(int)response.StatusCode}: {message}");
        }
        return string.IsNullOrWhiteSpace(raw)
            ? new JsonObject()
            : JsonNode.Parse(raw)?.AsObject() ?? new JsonObject();
    }

    private object ConfigWithItems(object[] items) => new
    {
        configured = Missing().Count == 0,
        missing = Missing(),
        projectKey = Env("LD_PROJECT_KEY"),
        environmentKey = Env("LD_ENVIRONMENT_KEY"),
        apiHost = ApiHost,
        items,
    };

    private static object Summarize(JsonNode? node) => Summarize(node, null, null);
    private static object Summarize(JsonNode? node, long? createdFallback, long? executionFallback)
    {
        var item = node as JsonObject ?? new JsonObject();
        return new
        {
            id = item["_id"]?.ToString(),
            createdAt = Long(item["_creationDate"]) ?? createdFallback,
            executionDate = Long(item["executionDate"]) ?? executionFallback,
            instructions = item["instructions"] as JsonArray ?? [],
        };
    }

    private static long? Long(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<long>(out var number) ? number : null;
    private static string Escape(string value) => Uri.EscapeDataString(value);
    private static string? Env(string key) =>
        Environment.GetEnvironmentVariable(key)?.Trim() is { Length: > 0 } value ? value : null;
    private static List<string> Missing() =>
        new[] { "LD_API_ACCESS_TOKEN", "LD_PROJECT_KEY", "LD_ENVIRONMENT_KEY" }
            .Where(key => Env(key) is null).ToList();
    private static void RequireConfigured()
    {
        var missing = Missing();
        if (missing.Count > 0)
            throw new InvalidOperationException(
                $"Scheduled changes need {string.Join(", ", missing)}");
    }
    private static string Token => Env("LD_API_ACCESS_TOKEN")!;
    private static string Project => Env("LD_PROJECT_KEY")!;
    private static string EnvironmentKey => Env("LD_ENVIRONMENT_KEY")!;
    private static string ApiHost => Env("LD_API_HOST") ?? "https://app.launchdarkly.com";
    private static string BasePath =>
        $"/projects/{Escape(Project)}/flags/{Escape(ScheduledHighlight.FlagKey)}" +
        $"/environments/{Escape(EnvironmentKey)}/scheduled-changes";
}
