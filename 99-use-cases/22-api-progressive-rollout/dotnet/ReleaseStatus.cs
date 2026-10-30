using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Read and start the progressive environment release for this example.
/// LaunchDarkly: environment releases — kind progressive
/// https://launchdarkly.com/docs/api/environment-releases
/// </summary>
static class ReleaseStatus
{
    private const int AllocationScale = 1000;
    private static readonly int[] RolloutPercentages = [10, 20, 40, 60, 100];
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(30) };

    private static int StageSeconds =>
        int.TryParse(Environment.GetEnvironmentVariable("STAGE_SECONDS"), out var seconds) ? seconds : 60;

    private static string Host =>
        (Environment.GetEnvironmentVariable("LD_API_HOST") ?? "https://app.launchdarkly.com").TrimEnd('/');

    private static string Token => Environment.GetEnvironmentVariable("LD_API_ACCESS_TOKEN") ?? "";
    private static string Project => Environment.GetEnvironmentVariable("LD_PROJECT_KEY") ?? "";
    private static string EnvironmentKey => Environment.GetEnvironmentVariable("LD_ENVIRONMENT_KEY") ?? "";
    private static string FlagApiVersion => Environment.GetEnvironmentVariable("LD_API_VERSION") ?? "20240415";

    internal static JsonArray Schedule()
    {
        var steps = new JsonArray();
        foreach (var percent in RolloutPercentages)
            steps.Add(new JsonObject { ["percent"] = percent, ["durationSeconds"] = StageSeconds });
        return steps;
    }

    internal static string? TargetingUrl()
    {
        if (string.IsNullOrEmpty(Project) || string.IsNullOrEmpty(EnvironmentKey))
            return null;
        return $"{Host}/projects/{Project}/flags/{HighlightEval.FlagHighlight}/targeting?env={EnvironmentKey}&selected-env={EnvironmentKey}";
    }

    internal static Task<JsonObject> LatestAsync() => WithConfig(async () =>
    {
        var (status, payload) = await RequestAsync(
            HttpMethod.Get,
            $"{ReleasesPath()}?queryfilter=kind:equals:progressive&limit=1");
        if (status != 200 || payload is not JsonObject body)
            return ApiError(status, payload);
        var items = body["items"] as JsonArray;
        JsonObject summary = items is { Count: > 0 } && items[0] is JsonObject item
            ? Summarize(item)
            : new JsonObject
            {
                ["configured"] = true,
                ["flagKey"] = HighlightEval.FlagHighlight,
                ["status"] = "none",
                ["metricCount"] = 0,
                ["steps"] = new JsonArray(),
                ["detail"] = "No progressive release on this flag yet.",
            };
        summary["totalCount"] = body["totalCount"]?.GetValue<int?>();
        var on = await FlagIsOnAsync();
        summary["flagOn"] = on;
        if (on == false)
            summary["active"] = false;
        return summary;
    });

    /// <summary>
    /// Start the progressive release. Header LD-API-Version: beta.
    /// https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    /// </summary>
    internal static Task<JsonObject> StartAsync() => WithConfig(async () =>
    {
        var flagPath = $"/api/v2/flags/{Project}/{HighlightEval.FlagHighlight}";
        var (status, payload) = await RequestAsync(HttpMethod.Get, flagPath, version: FlagApiVersion);
        if (status == 404)
            return Error("Flag not found. Run rest/create-flag.sh, then start again.", status);
        if (status != 200 || payload is not JsonObject flag)
            return ApiError(status, payload);
        var noneId = VariationId(flag, "none");
        var greenId = VariationId(flag, "green");
        if (noneId is null || greenId is null)
            return Error("The flag is missing the none or green variation.");
        var instructions = RemovePhaseRules(flag);
        instructions.Add(new JsonObject { ["kind"] = "turnFlagOn" });
        instructions.Add(new JsonObject { ["kind"] = "updateFallthroughVariationOrRollout", ["variationId"] = noneId });
        var patch = new JsonObject
        {
            ["environmentKey"] = EnvironmentKey,
            ["comment"] = "22-api-progressive-rollout: on, default rule stays none",
            ["instructions"] = instructions,
        };
        var (patchStatus, patched) = await RequestAsync(
            HttpMethod.Patch,
            flagPath,
            patch,
            FlagApiVersion,
            "application/json; domain-model=launchdarkly.semanticpatch");
        if (patchStatus >= 400)
            return ApiError(patchStatus, patched);
        var (startStatus, started) = await RequestAsync(HttpMethod.Post, ReleasesPath(), StartBody(noneId, greenId));
        if (startStatus is not (200 or 201) || started is not JsonObject release || release["phases"] is null)
            return ApiError(startStatus, started);
        var summary = Summarize(release);
        summary["started"] = true;
        return summary;
    });

    /// <summary>
    /// Stop the active progressive release.
    /// https://launchdarkly.com/docs/api/environment-releases-beta/stop-an-environment-release
    /// </summary>
    internal static Task<JsonObject> StopAsync() => WithConfig(async () =>
    {
        var (status, payload) = await RequestAsync(
            HttpMethod.Get,
            $"{ReleasesPath()}?queryfilter=kind:equals:progressive&limit=5");
        if (status != 200 || payload is not JsonObject body)
            return ApiError(status, payload);
        JsonObject? active = null;
        if (body["items"] is JsonArray items)
        {
            foreach (var node in items)
            {
                if (node is not JsonObject item)
                    continue;
                var ended = item["endedAt"] is not null && item["endedAt"]!.GetValueKind() != System.Text.Json.JsonValueKind.Null;
                var itemStatus = item["status"]?.GetValue<string>();
                if (!ended && itemStatus is not ("completed" or "reverted"))
                {
                    active = item;
                    break;
                }
            }
        }
        if (active?["id"]?.GetValue<string>() is not string id || id.Length == 0)
            return Error("No active progressive release to stop.", code: "no_active_release");
        var (stopStatus, stopped) = await RequestAsync(
            HttpMethod.Put,
            $"{ReleasesPath()}/{id}/stop",
            new JsonObject
            {
                ["resolution"] = "roll_back_all_phases_and_remove_pending_phases",
                ["comment"] = "22-api-progressive-rollout: stop progressive release",
            });
        if (stopStatus is not (200 or 201) || stopped is not JsonObject release)
            return ApiError(stopStatus, stopped);
        var summary = Summarize(release);
        summary["stopped"] = true;
        summary["flagOn"] = await FlagIsOnAsync();
        return summary;
    });

    /// <summary>
    /// Roll back a running release, then turn the flag off.
    /// https://launchdarkly.com/docs/api/feature-flags/update-feature-flag
    /// </summary>
    internal static Task<JsonObject> ResetAsync() => WithConfig(async () =>
    {
        var stopped = await StopAsync();
        if (stopped["error"]?.GetValue<bool>() == true && stopped["code"]?.GetValue<string>() != "no_active_release")
            return stopped;
        var flagPath = $"/api/v2/flags/{Project}/{HighlightEval.FlagHighlight}";
        var (flagStatus, flagPayload) = await RequestAsync(HttpMethod.Get, flagPath, version: FlagApiVersion);
        var instructions = flagStatus == 200 && flagPayload is JsonObject flag
            ? RemovePhaseRules(flag)
            : new JsonArray();
        instructions.Add(new JsonObject { ["kind"] = "turnFlagOff" });
        var (status, payload) = await RequestAsync(
            HttpMethod.Patch,
            flagPath,
            new JsonObject
            {
                ["environmentKey"] = EnvironmentKey,
                ["comment"] = "22-api-progressive-rollout: reset, flag off, phase rule removed",
                ["instructions"] = instructions,
            },
            FlagApiVersion,
            "application/json; domain-model=launchdarkly.semanticpatch");
        if (status >= 400)
            return ApiError(status, payload);
        var summary = await LatestAsync();
        summary["reset"] = true;
        summary["flagOn"] = false;
        summary["active"] = false;
        return summary;
    });

    private static async Task<JsonObject> WithConfig(Func<Task<JsonObject>> action)
    {
        if (string.IsNullOrEmpty(Token) || string.IsNullOrEmpty(Project) || string.IsNullOrEmpty(EnvironmentKey))
        {
            return new JsonObject
            {
                ["configured"] = false,
                ["flagKey"] = HighlightEval.FlagHighlight,
                ["detail"] = "Set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, and LD_ENVIRONMENT_KEY, then restart.",
            };
        }
        return await action();
    }

    private static string ReleasesPath() =>
        $"/api/v2/projects/{Project}/flags/{HighlightEval.FlagHighlight}/environments/{EnvironmentKey}/releases";

    private static JsonObject StartBody(string noneId, string greenId)
    {
        var steps = new JsonArray();
        foreach (var percent in RolloutPercentages)
        {
            steps.Add(new JsonObject
            {
                ["allocation"] = percent * AllocationScale,
                ["durationMillis"] = StageSeconds * 1000,
            });
        }
        return new JsonObject
        {
            ["originalVariationId"] = noneId,
            ["targetVariationId"] = greenId,
            ["randomizationUnit"] = "user",
            ["cleanupBehavior"] = "remove_rules_and_update_default_rule",
            ["comment"] = "22-api-progressive-rollout: start progressive release",
            ["phases"] = new JsonArray
            {
                new JsonObject
                {
                    ["description"] = "All users",
                    ["clauses"] = new JsonArray
                    {
                        new JsonObject
                        {
                            ["contextKind"] = "user",
                            ["attribute"] = "kind",
                            ["op"] = "in",
                            ["values"] = new JsonArray { "user" },
                        },
                    },
                    ["steps"] = steps,
                },
            },
        };
    }

    private static JsonObject Summarize(JsonObject item)
    {
        var phase = item["phases"] is JsonArray phases && phases.Count > 0 && phases[0] is JsonObject first
            ? first
            : new JsonObject();
        var steps = new JsonArray();
        if (phase["steps"] is JsonArray rawSteps)
        {
            foreach (var node in rawSteps)
            {
                if (node is not JsonObject step)
                    continue;
                steps.Add(new JsonObject
                {
                    ["percent"] = step["allocation"]?.GetValue<int?>() is int allocation
                        ? allocation / AllocationScale
                        : null,
                    ["durationSeconds"] = step["durationMillis"]?.GetValue<int?>() is int duration
                        ? duration / 1000
                        : null,
                });
            }
        }
        int? index = phase["currentStepIndex"]?.GetValue<int?>();
        int? current = index is int i && i >= 0 && i < steps.Count && steps[i] is JsonObject currentStep
            ? currentStep["percent"]?.GetValue<int?>()
            : null;
        var status = item["status"]?.GetValue<string>();
        var ended = (item["endedAt"] is not null && item["endedAt"]!.GetValueKind() != System.Text.Json.JsonValueKind.Null)
            || status is "completed" or "reverted";
        return new JsonObject
        {
            ["configured"] = true,
            ["flagKey"] = HighlightEval.FlagHighlight,
            ["kind"] = item["kind"]?.DeepClone(),
            ["status"] = status,
            ["statusReason"] = item["statusReason"]?.DeepClone(),
            ["randomizationUnit"] = item["randomizationUnit"]?.DeepClone(),
            ["metricCount"] = item["metrics"] is JsonArray metrics ? metrics.Count : 0,
            ["hasRule"] = phase["ruleId"] is JsonValue,
            ["stepIndex"] = index,
            ["stepCount"] = steps.Count,
            ["currentPercent"] = current,
            ["steps"] = steps,
            ["active"] = !ended,
        };
    }

    private static async Task<bool?> FlagIsOnAsync()
    {
        var (status, payload) = await RequestAsync(
            HttpMethod.Get,
            $"/api/v2/flags/{Project}/{HighlightEval.FlagHighlight}?env={EnvironmentKey}",
            version: FlagApiVersion);
        if (status != 200 || payload is not JsonObject flag)
            return null;
        return flag["environments"]?[EnvironmentKey]?["on"]?.GetValue<bool?>();
    }

    /// <summary>
    /// Rules left by a stopped release. The next start rejects a duplicate description.
    /// </summary>
    private static JsonArray RemovePhaseRules(JsonObject flag)
    {
        var instructions = new JsonArray();
        if (flag["environments"]?[EnvironmentKey]?["rules"] is not JsonArray rules)
            return instructions;
        foreach (var node in rules)
        {
            if (node is not JsonObject rule)
                continue;
            var ruleId = rule["_id"]?.GetValue<string>() ?? rule["id"]?.GetValue<string>();
            if (string.IsNullOrEmpty(ruleId))
                continue;
            instructions.Add(new JsonObject { ["kind"] = "removeRule", ["ruleId"] = ruleId });
        }
        return instructions;
    }

    private static string? VariationId(JsonObject flag, string value)
    {
        if (flag["variations"] is not JsonArray variations)
            return null;
        foreach (var node in variations)
        {
            if (node is JsonObject item && item["value"]?.GetValue<string>() == value)
                return item["_id"]?.GetValue<string>();
        }
        return null;
    }

    private static async Task<(int Status, JsonNode? Payload)> RequestAsync(
        HttpMethod method,
        string path,
        JsonNode? body = null,
        string version = "beta",
        string contentType = "application/json")
    {
        using var request = new HttpRequestMessage(method, Host + path);
        request.Headers.TryAddWithoutValidation("Authorization", Token);
        request.Headers.TryAddWithoutValidation("LD-API-Version", version);
        if (body is not null)
        {
            var content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            content.Headers.ContentType = MediaTypeHeaderValue.Parse(contentType);
            request.Content = content;
        }
        try
        {
            using var response = await Http.SendAsync(request);
            var text = await response.Content.ReadAsStringAsync();
            JsonNode? payload = string.IsNullOrWhiteSpace(text) ? new JsonObject() : JsonNode.Parse(text);
            return ((int)response.StatusCode, payload);
        }
        catch (Exception err) when (err is HttpRequestException or TaskCanceledException or System.Text.Json.JsonException)
        {
            return (0, new JsonObject { ["message"] = $"Could not reach LaunchDarkly: {err.Message}" });
        }
    }

    private static JsonObject ApiError(int status, JsonNode? payload)
    {
        var message = payload?["message"]?.GetValue<string>();
        var code = payload?["code"]?.GetValue<string>();
        var detail = string.IsNullOrEmpty(message) ? "LaunchDarkly rejected the request." : message;
        if (code == "health_checks_failed")
            detail += " Log in on the grid once so the flag has a user evaluation, then start again.";
        return new JsonObject
        {
            ["configured"] = true,
            ["flagKey"] = HighlightEval.FlagHighlight,
            ["error"] = true,
            ["http"] = status,
            ["code"] = code,
            ["detail"] = detail,
        };
    }

    private static JsonObject Error(string detail, int? http = null, string? code = null) => new()
    {
        ["configured"] = true,
        ["flagKey"] = HighlightEval.FlagHighlight,
        ["error"] = true,
        ["http"] = http,
        ["code"] = code,
        ["detail"] = detail,
    };
}
