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
        var catalog = new (string Key, string Label, string Summary)[]
        {
            (TeamStyle.FlagKey, "Configure team label style", "String style selected by provisioned targeting rules on public team."),
            (TeamStyle.LabelsKey, "Configure team display labels", "JSON words for the pill and the team switch. Team values stay red, blue, and yellow."),
        };
        if (Missing().Count > 0)
            return ConfigWithFlags(catalog.Select(item => (object)new
            {
                key = item.Key,
                label = item.Label,
                summary = item.Summary,
                on = (bool?)null,
                targetingHint = "Set missing environment variables to enable controls.",
            }).ToList());
        var flags = new List<object>();
        var errors = new List<object>();
        foreach (var item in catalog)
        {
            try
            {
                flags.Add(Summarize(await GetFlagAsync(item.Key), item.Label, item.Summary));
            }
            catch (Exception exception)
            {
                errors.Add(new { key = item.Key, error = exception.Message });
                flags.Add(new
                {
                    key = item.Key,
                    label = item.Label,
                    summary = item.Summary,
                    on = (bool?)null,
                    targetingHint = exception.Message,
                });
            }
        }
        return ConfigWithFlags(flags, errors);
    }

    public async Task<object> ApplyAsync(
        string key, bool? on, bool hasFallthrough, string? fallthrough)
    {
        if (key != TeamStyle.FlagKey && key != TeamStyle.LabelsKey)
            throw new ArgumentException($"Flag key not allowed for controls: {key}");
        if (on is null && !hasFallthrough)
            throw new ArgumentException("Provide \"on\" and/or \"fallthrough\"");
        RequireConfigured();

        var flag = await GetFlagAsync(key);
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
            $"/flags/{Escape(Project)}/{Escape(key)}",
            new JsonObject
            {
                ["environmentKey"] = EnvironmentKey,
                ["comment"] = "13-flag-targeting-rules UI: on/off or fallthrough",
                ["instructions"] = instructions,
            });
        flag = await GetFlagAsync(key);
        return new
        {
            ok = true,
            action = string.Join("+", instructions.Select(item => item?["kind"]?.ToString())),
            instructions = instructions.Select(item => item?["kind"]?.ToString()).ToArray(),
            projectKey = Project,
            environmentKey = EnvironmentKey,
            flag = Summarize(
                flag,
                key == TeamStyle.LabelsKey ? "Configure team display labels" : "Configure team label style",
                key == TeamStyle.LabelsKey
                    ? "JSON words for the pill and the team switch. Team values stay red, blue, and yellow."
                    : "String style selected by provisioned targeting rules on public team."),
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

    private static object Summarize(JsonObject flag, string label, string summary)
    {
        var environment = flag["environments"]?[EnvironmentKey] as JsonObject ?? new JsonObject();
        var variations = flag["variations"] as JsonArray ?? [];
        var fallIndex = Int(environment["fallthrough"]?["variation"]);
        var offIndex = Int(environment["offVariation"]);
        var fallValue = VariationValue(variations, fallIndex);
        var options = variations.Select(node =>
        {
            var valueNode = node?["value"];
            var name = node?["name"]?.ToString();
            var token = valueNode is JsonObject or JsonArray
                ? name
                : valueNode?.ToString()?.Trim('"');
            return new
            {
                token,
                label = name ?? token,
                value = valueNode,
            };
        }).ToArray();
        var ruleCount = (environment["rules"] as JsonArray)?.Count ?? 0;
        var fallToken = fallIndex is >= 0 && fallIndex < options.Length ? options[fallIndex.Value].token : null;
        return new
        {
            key = flag["key"]?.ToString(),
            name = flag["name"]?.ToString() ?? label,
            label,
            summary,
            on = environment["on"]?.GetValue<bool>() ?? false,
            variationKind = "string",
            fallthroughOptions = options,
            fallthroughToken = fallToken,
            servedWhenOff = VariationValue(variations, offIndex),
            servedWhenOnFallthrough = fallValue,
            ruleCount,
            targetingHint = $"{ruleCount} provisioned rules remain unchanged; this lab controls only flag state and fallthrough.",
        };
    }

    private async Task<JsonObject> GetFlagAsync(string key) =>
        await RequestAsync(HttpMethod.Get,
            $"/flags/{Escape(Project)}/{Escape(key)}?env={Escape(EnvironmentKey)}");

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
            var name = node?["name"]?.ToString();
            var raw = node?["value"]?.ToString()?.Trim('"');
            if (name == wanted || raw == wanted)
                return node?["_id"]?.ToString() ?? node?["id"]?.ToString();
        }
        return null;
    }

    private static object? VariationValue(JsonArray values, int? index)
    {
        if (index is not >= 0 || index >= values.Count) return null;
        var node = values[index.Value]?["value"];
        if (node is JsonValue value && value.TryGetValue<string>(out var text)) return text;
        return node;
    }
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
