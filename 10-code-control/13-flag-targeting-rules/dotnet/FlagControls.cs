using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Controls flag on/off and fallthrough without editing provisioned targeting rules.
/// https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
/// </summary>
sealed class FlagControls
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
            return ConfigWithFlags([
                new
                {
                    key = TeamStyle.FlagKey,
                    label = "Configure team label style",
                    summary = "String targeting by public team context attribute.",
                    on = (bool?)null,
                    targetingHint = "Set missing environment variables to enable controls.",
                },
            ]);
        var flag = await GetFlagAsync();
        return ConfigWithFlags([Summarize(flag)], []);
    }

    public async Task<object> ApplyAsync(
        string key, bool? on, bool hasFallthrough, string? fallthrough)
    {
        if (key != TeamStyle.FlagKey)
            throw new ArgumentException($"Flag key not allowed for controls: {key}");
        if (on is null && !hasFallthrough)
            throw new ArgumentException("Provide \"on\" and/or \"fallthrough\"");
        RequireConfigured();

        var flag = await GetFlagAsync();
        var instructions = new JsonArray();
        if (on is true) instructions.Add(new JsonObject { ["kind"] = "turnFlagOn" });
        else if (on is false) instructions.Add(new JsonObject { ["kind"] = "turnFlagOff" });
        if (hasFallthrough)
        {
            var variationId = VariationId(flag, fallthrough ?? "");
            if (variationId is null)
                throw new ArgumentException($"No variation matching fallthrough={JsonValue.Create(fallthrough)?.ToJsonString()}");
            instructions.Add(new JsonObject
            {
                ["kind"] = "updateFallthroughVariationOrRollout",
                ["variationId"] = variationId,
            });
        }
        await RequestAsync(HttpMethod.Patch,
            $"/flags/{Escape(Project)}/{TeamStyle.FlagKey}",
            new JsonObject
            {
                ["environmentKey"] = EnvironmentKey,
                ["comment"] = "13-flag-targeting-rules UI: on/off or fallthrough",
                ["instructions"] = instructions,
            });
        flag = await GetFlagAsync();
        return new
        {
            ok = true,
            action = string.Join("+", instructions.Select(item => item?["kind"]?.ToString())),
            instructions = instructions.Select(item => item?["kind"]?.ToString()).ToArray(),
            projectKey = Project,
            environmentKey = EnvironmentKey,
            flag = Summarize(flag),
        };
    }

    private object ConfigWithFlags(List<object> flags, List<object>? errors = null) => new
    {
        configured = Missing().Count == 0,
        missing = Missing(),
        projectKey = Env("LD_PROJECT_KEY"),
        environmentKey = Env("LD_ENVIRONMENT_KEY"),
        apiHost = ApiHost,
        flags,
        errors = errors ?? [],
    };

    private static object Summarize(JsonObject flag)
    {
        var environment = flag["environments"]?[EnvironmentKey] as JsonObject ?? new JsonObject();
        var variations = flag["variations"] as JsonArray ?? [];
        var fallIndex = Int(environment["fallthrough"]?["variation"]);
        var offIndex = Int(environment["offVariation"]);
        var fallValue = VariationValue(variations, fallIndex);
        var options = variations.Select(node => new
        {
            token = node?["value"]?.GetValue<string>(),
            label = node?["name"]?.ToString() ?? node?["value"]?.GetValue<string>(),
            value = node?["value"]?.GetValue<string>(),
        }).ToArray();
        var ruleCount = (environment["rules"] as JsonArray)?.Count ?? 0;
        return new
        {
            key = TeamStyle.FlagKey,
            name = flag["name"]?.ToString() ?? "Configure team label style",
            label = "Configure team label style",
            summary = "String style selected by provisioned targeting rules on public team.",
            on = environment["on"]?.GetValue<bool>() ?? false,
            variationKind = "string",
            fallthroughOptions = options,
            fallthroughToken = fallValue,
            servedWhenOff = VariationValue(variations, offIndex),
            servedWhenOnFallthrough = fallValue,
            ruleCount,
            targetingHint = $"{ruleCount} provisioned rules remain unchanged; this lab controls only flag state and fallthrough.",
        };
    }

    private async Task<JsonObject> GetFlagAsync() =>
        await RequestAsync(HttpMethod.Get,
            $"/flags/{Escape(Project)}/{TeamStyle.FlagKey}?env={Escape(EnvironmentKey)}");

    private async Task<JsonObject> RequestAsync(
        HttpMethod method, string path, JsonObject? body = null)
    {
        RequireConfigured();
        using var request = new HttpRequestMessage(method, $"{ApiHost.TrimEnd('/')}/api/v2{path}");
        request.Headers.TryAddWithoutValidation("Authorization", Token);
        request.Headers.Add("LD-API-Version", Env("LD_API_VERSION") ?? "20240415");
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        if (body is not null)
        {
            request.Content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            request.Content.Headers.ContentType =
                MediaTypeHeaderValue.Parse("application/json; domain-model=launchdarkly.semanticpatch");
        }
        using var response = await _http.SendAsync(request);
        var raw = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            var message = JsonNode.Parse(raw)?["message"]?.ToString() ?? raw;
            throw new InvalidOperationException($"LaunchDarkly API {(int)response.StatusCode}: {message}");
        }
        return string.IsNullOrWhiteSpace(raw)
            ? new JsonObject()
            : JsonNode.Parse(raw)?.AsObject() ?? new JsonObject();
    }

    private static string? VariationId(JsonObject flag, string wanted)
    {
        foreach (var node in flag["variations"] as JsonArray ?? [])
        {
            if (node?["value"]?.GetValue<string>() == wanted)
                return node?["_id"]?.ToString() ?? node?["id"]?.ToString();
        }
        return null;
    }

    private static string? VariationValue(JsonArray values, int? index) =>
        index is >= 0 && index < values.Count ? values[index.Value]?["value"]?.GetValue<string>() : null;
    private static int? Int(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<int>(out var number) ? number : null;
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
            throw new InvalidOperationException($"Flag controls need {string.Join(", ", missing)}");
    }
    private static string Token => Env("LD_API_ACCESS_TOKEN")!;
    private static string Project => Env("LD_PROJECT_KEY")!;
    private static string EnvironmentKey => Env("LD_ENVIRONMENT_KEY")!;
    private static string ApiHost => Env("LD_API_HOST") ?? "https://app.launchdarkly.com";
}
