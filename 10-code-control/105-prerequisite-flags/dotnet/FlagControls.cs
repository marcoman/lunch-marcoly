using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// REST controls for the two 15-prerequisite-flags keys.
/// Never edits the prerequisite relationship.
/// https://launchdarkly.com/docs/api/feature-flags/patch-feature-flag
/// </summary>
sealed class FlagControls
{
    private static readonly (string Key, string Label, string Summary)[] ControlledFlags =
    [
        (
            Prerequisite.FlagHighlight,
            "Parent · grid selection highlight",
            "15-prerequisite-flags parent (cites 11's enable-grid-selection-highlight). Must be on and serving green to satisfy the prerequisite."
        ),
        (
            Prerequisite.FlagCount,
            "Child · navigation move count",
            "15-prerequisite-flags child (cites 11's show-navigation-move-count). Unmet prerequisite serves its off variation."
        ),
    ];
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
        {
            return ConfigWithFlags(
                ControlledFlags.Select(meta => (object)new
                {
                    key = meta.Key,
                    label = meta.Label,
                    summary = meta.Summary,
                    on = (bool?)null,
                    targetingHint = "Set missing environment variables.",
                }).ToList());
        }

        var query = $"?env={Escape(EnvironmentKey)}";
        var flags = new List<object>();
        var errors = new List<object>();
        foreach (var meta in ControlledFlags)
        {
            try
            {
                var flag = await RequestAsync(
                    HttpMethod.Get,
                    $"/flags/{Escape(Project)}/{Escape(meta.Key)}{query}");
                flags.Add(Summarize(flag, meta));
            }
            catch (Exception exception)
            {
                errors.Add(new { key = meta.Key, error = exception.Message });
                flags.Add(new
                {
                    key = meta.Key,
                    label = meta.Label,
                    summary = meta.Summary,
                    on = (bool?)null,
                    targetingHint = exception.Message,
                    error = exception.Message,
                });
            }
        }
        return ConfigWithFlags(flags, errors);
    }

    public async Task<object> ApplyAsync(
        string key, bool? on, bool hasFallthrough, JsonNode? fallthrough)
    {
        if (ControlledFlags.All(item => item.Key != key))
            throw new ArgumentException($"Flag key not allowed for controls: {key}");
        if (on is null && !hasFallthrough)
            throw new ArgumentException("Provide \"on\" and/or \"fallthrough\"");
        if (hasFallthrough && key != Prerequisite.FlagHighlight)
            throw new ArgumentException("Only the parent highlight flag has color variations");
        RequireConfigured();

        var path = $"/flags/{Escape(Project)}/{Escape(key)}";
        var query = $"?env={Escape(EnvironmentKey)}";
        var flag = await RequestAsync(HttpMethod.Get, path + query);
        var instructions = new JsonArray();
        if (on is true) instructions.Add(new JsonObject { ["kind"] = "turnFlagOn" });
        else if (on is false) instructions.Add(new JsonObject { ["kind"] = "turnFlagOff" });
        if (hasFallthrough)
        {
            var variationId = VariationId(flag, fallthrough);
            if (variationId is null)
                throw new ArgumentException($"No variation matching fallthrough={fallthrough?.ToJsonString()}");
            instructions.Add(new JsonObject
            {
                ["kind"] = "updateFallthroughVariationOrRollout",
                ["variationId"] = variationId,
            });
        }
        await RequestAsync(HttpMethod.Patch, path, new JsonObject
        {
            ["environmentKey"] = EnvironmentKey,
            ["comment"] = "15-prerequisite-flags UI control",
            ["instructions"] = instructions,
        });
        flag = await RequestAsync(HttpMethod.Get, path + query);
        var meta = ControlledFlags.First(item => item.Key == key);
        return new
        {
            ok = true,
            instructions = instructions.Select(item => item?["kind"]?.ToString()).ToArray(),
            projectKey = Project,
            environmentKey = EnvironmentKey,
            flag = Summarize(flag, meta),
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

    private static object Summarize(
        JsonObject flag, (string Key, string Label, string Summary) meta)
    {
        var environment = flag["environments"]?[EnvironmentKey] as JsonObject ?? new JsonObject();
        var variations = flag["variations"] as JsonArray ?? [];
        var values = variations.Select(node => VariationNodeValue(node?["value"])).ToList();
        var prerequisites = environment["prerequisites"] as JsonArray ?? [];
        var prerequisite = prerequisites.Count > 0 ? prerequisites[0] : null;
        var fallIndex = Int(environment["fallthrough"]?["variation"]);
        var offIndex = Int(environment["offVariation"]);
        var prerequisiteKey = prerequisite?["key"]?.ToString();
        return new
        {
            key = meta.Key,
            label = meta.Label,
            summary = meta.Summary,
            on = environment["on"]?.GetValue<bool>() ?? false,
            variationKind = values.Count > 0 && values.All(value => value is string)
                ? "string"
                : "boolean",
            colorOptions = meta.Key == Prerequisite.FlagHighlight
                ? values.OfType<string>().Where(Prerequisite.ValidColors.Contains).ToArray()
                : [],
            servedWhenOff = VariationValue(variations, offIndex),
            servedWhenOnFallthrough = VariationValue(variations, fallIndex),
            prerequisite,
            prerequisiteConfigured = meta.Key != Prerequisite.FlagCount
                || prerequisiteKey == Prerequisite.FlagHighlight,
            targetingHint = meta.Key == Prerequisite.FlagHighlight
                ? "Required by child: parent must be ON and serve green."
                : prerequisite is null
                    ? "Missing prerequisite — run this example's provisioning."
                    : "Prerequisite configured; lab controls leave it unchanged.",
        };
    }

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

    private static string? VariationId(JsonObject flag, JsonNode? wanted)
    {
        var normalized = NormalizeWanted(wanted);
        foreach (var node in flag["variations"] as JsonArray ?? [])
        {
            if (ValuesEqual(node?["value"], normalized))
                return node?["_id"]?.ToString() ?? node?["id"]?.ToString();
        }
        return null;
    }

    private static object? VariationValue(JsonArray values, int? index)
    {
        if (index is not >= 0 || index >= values.Count) return null;
        return VariationNodeValue(values[index.Value]?["value"]);
    }

    private static object? VariationNodeValue(JsonNode? node)
    {
        if (node is JsonValue value)
        {
            if (value.TryGetValue<bool>(out var flag)) return flag;
            if (value.TryGetValue<string>(out var text)) return text;
            if (value.TryGetValue<int>(out var number)) return number;
        }
        return node;
    }

    private static object? NormalizeWanted(JsonNode? wanted)
    {
        if (wanted is JsonValue value)
        {
            if (value.TryGetValue<bool>(out var flag)) return flag;
            if (value.TryGetValue<string>(out var text))
            {
                if (text == "true") return true;
                if (text == "false") return false;
                return text.Trim();
            }
        }
        return wanted?.ToString();
    }

    private static bool ValuesEqual(JsonNode? left, object? wanted)
    {
        if (left is JsonValue value)
        {
            if (wanted is bool flag && value.TryGetValue<bool>(out var leftFlag))
                return leftFlag == flag;
            if (wanted is string text && value.TryGetValue<string>(out var leftText))
                return leftText == text;
        }
        return false;
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
