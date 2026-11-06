using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Read and start the guarded environment release for this example.
/// LaunchDarkly: environment releases — kind guarded
/// https://launchdarkly.com/docs/api/environment-releases
/// </summary>
static class ReleaseStatus
{
    private const int AllocationScale = 1000;
    private static readonly (int Percent, int Seconds)[] RolloutSteps =
        [(10, 120), (20, 120), (30, 60), (50, 60)];
    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(30) };

    private static string Host =>
        (Environment.GetEnvironmentVariable("LD_API_HOST") ?? "https://app.launchdarkly.com").TrimEnd('/');
    private static string Token => Environment.GetEnvironmentVariable("LD_API_ACCESS_TOKEN") ?? "";
    private static string Project => Environment.GetEnvironmentVariable("LD_PROJECT_KEY") ?? "";
    private static string EnvironmentKey => Environment.GetEnvironmentVariable("LD_ENVIRONMENT_KEY") ?? "";
    private static string FlagApiVersion => Environment.GetEnvironmentVariable("LD_API_VERSION") ?? "20240415";

    internal static JsonArray Schedule()
    {
        var steps = new JsonArray();
        foreach (var step in RolloutSteps)
            steps.Add(new JsonObject { ["percent"] = step.Percent, ["durationSeconds"] = step.Seconds });
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
        var (status, payload) = await RequestAsync(HttpMethod.Get, $"{ReleasesPath()}?queryfilter=kind:equals:guarded&limit=1");
        if (status == 404)
        {
            var missingFlag = new JsonObject
            {
                ["configured"] = true,
                ["flagKey"] = HighlightEval.FlagHighlight,
                ["status"] = "none",
                ["detail"] = "No flag yet. Start creates it.",
                ["flagOn"] = false,
            };
            missingFlag["headline"] = Headline(missingFlag);
            return missingFlag;
        }
        if (status != 200 || payload is not JsonObject body)
            return ApiError(status, payload);
        var items = body["items"] as JsonArray;
        var summary = items is { Count: > 0 } && items[0] is JsonObject item
            ? Summarize(item)
            : NoneSummary("No guarded release on this flag yet.");
        var on = await FlagIsOnAsync();
        summary["flagOn"] = on;
        if (on == false)
            summary["active"] = false;
        summary["headline"] = Headline(summary);
        return summary;
    });

    /// <summary>
    /// Start the guarded release. Header LD-API-Version: beta.
    /// https://launchdarkly.com/docs/api/environment-releases-beta/start-an-environment-release
    /// </summary>
    internal static Task<JsonObject> StartAsync() => WithConfig(async () =>
    {
        var warnings = await EnsureMetricsAsync();
        var flagError = await EnsureFlagAsync();
        if (flagError is not null)
            return flagError;
        var (status, payload) = await RequestAsync(HttpMethod.Get, FlagPath(), version: FlagApiVersion);
        if (status != 200 || payload is not JsonObject flag)
            return ApiError(status, payload);
        var noneId = VariationId(flag, "none");
        var greenId = VariationId(flag, "green");
        if (noneId is null || greenId is null)
            return Error("The flag is missing the none or green variation.");
        var instructions = RemoveRules(flag);
        instructions.Add(new JsonObject { ["kind"] = "turnFlagOn" });
        instructions.Add(new JsonObject { ["kind"] = "updateFallthroughVariationOrRollout", ["variationId"] = noneId });
        var (patchStatus, patched) = await RequestAsync(HttpMethod.Patch, FlagPath(), new JsonObject
        {
            ["environmentKey"] = EnvironmentKey,
            ["comment"] = "23-api-guarded-rollout: on, default rule stays none",
            ["instructions"] = instructions,
        }, FlagApiVersion, "application/json; domain-model=launchdarkly.semanticpatch");
        if (patchStatus >= 400)
            return ApiError(patchStatus, patched);
        var (startStatus, started) = await RequestAsync(HttpMethod.Post, ReleasesPath(), StartBody(noneId, greenId));
        if (startStatus is not (200 or 201) || started is not JsonObject release || release["phases"] is null)
            return ApiError(startStatus, started);
        var summary = Summarize(release);
        summary["started"] = true;
        summary["flagOn"] = true;
        summary["headline"] = Headline(summary);
        if (warnings.Count > 0)
            summary["metricDescriptionWarning"] = string.Join(" ", warnings);
        return summary;
    });

    internal static Task<JsonObject> StopAsync() => WithConfig(async () =>
    {
        var (status, payload) = await RequestAsync(HttpMethod.Get, $"{ReleasesPath()}?queryfilter=kind:equals:guarded&limit=5");
        if (status != 200 || payload is not JsonObject body)
            return ApiError(status, payload);
        string? releaseId = null;
        if (body["items"] is JsonArray items)
        {
            foreach (var node in items)
            {
                if (node is not JsonObject item)
                    continue;
                var itemStatus = item["status"]?.GetValue<string>();
                var ended = item["endedAt"] is JsonValue endedValue && endedValue.GetValueKind() != System.Text.Json.JsonValueKind.Null;
                if (!ended && itemStatus is not ("completed" or "reverted"))
                    releaseId = item["id"]?.GetValue<string>();
                if (releaseId is not null)
                    break;
            }
        }
        if (releaseId is null)
            return Error("No active guarded release to stop.", code: "no_active_release");
        var (stopStatus, stopped) = await RequestAsync(HttpMethod.Put, $"{ReleasesPath()}/{releaseId}/stop", new JsonObject
        {
            ["resolution"] = "roll_back_all_phases_and_remove_pending_phases",
            ["comment"] = "23-api-guarded-rollout: stop guarded release",
        });
        if (stopStatus is not (200 or 201) || stopped is not JsonObject release)
            return ApiError(stopStatus, stopped);
        var summary = Summarize(release);
        summary["stopped"] = true;
        summary["flagOn"] = await FlagIsOnAsync();
        summary["headline"] = Headline(summary);
        return summary;
    });

    internal static Task<JsonObject> ResetAsync() => WithConfig(async () =>
    {
        var stopped = await StopAsync();
        if (stopped["error"]?.GetValue<bool>() == true && stopped["code"]?.GetValue<string>() != "no_active_release")
            return stopped;
        var (flagStatus, payload) = await RequestAsync(HttpMethod.Get, FlagPath(), version: FlagApiVersion);
        var instructions = flagStatus == 200 && payload is JsonObject flag ? RemoveRules(flag) : new JsonArray();
        instructions.Add(new JsonObject { ["kind"] = "turnFlagOff" });
        var (status, patched) = await RequestAsync(HttpMethod.Patch, FlagPath(), new JsonObject
        {
            ["environmentKey"] = EnvironmentKey,
            ["comment"] = "23-api-guarded-rollout: reset, flag off, phase rule removed",
            ["instructions"] = instructions,
        }, FlagApiVersion, "application/json; domain-model=launchdarkly.semanticpatch");
        if (status >= 400)
            return ApiError(status, patched);
        var summary = await LatestAsync();
        summary["reset"] = true;
        summary["flagOn"] = false;
        summary["active"] = false;
        summary["headline"] = "Flag is off. Every context receives none.";
        return summary;
    });

    private static async Task<JsonObject?> EnsureFlagAsync()
    {
        var (status, payload) = await RequestAsync(HttpMethod.Get, FlagPath(), version: FlagApiVersion);
        if (status == 200 && payload is JsonObject)
            return null;
        if (status != 404)
            return ApiError(status, payload);
        var variations = new JsonArray
        {
            Variation("none", "No highlight", "Selected cell stays dark. The release starts here."),
            Variation("green", "Green", "Selected cell turns green. The release moves traffic here."),
            Variation("yellow", "Yellow", "Yellow highlight. This release does not target it."),
            Variation("red", "Red", "Red highlight. This release does not target it."),
            Variation("blue", "Blue", "Blue highlight. This release does not target it."),
            Variation("purple", "Purple", "Purple highlight. This release does not target it."),
        };
        var (created, body) = await RequestAsync(HttpMethod.Post, $"/api/v2/flags/{Project}", new JsonObject
        {
            ["key"] = HighlightEval.FlagHighlight,
            ["name"] = "API guarded grid highlight",
            ["description"] = "Guarded rollout of the grid highlight from none to green, started with the environment releases API. Latency, error rate, and movement are the guardrails.",
            ["temporary"] = false,
            ["tags"] = new JsonArray("grid-navigator", "use-case", "api-guarded-rollout", "environment-release", "guarded-rollout", "string"),
            ["variations"] = variations,
            ["defaults"] = new JsonObject { ["onVariation"] = 1, ["offVariation"] = 0 },
        }, FlagApiVersion);
        return created is 200 or 201 ? null : ApiError(created, body);
    }

    private static async Task<List<string>> EnsureMetricsAsync()
    {
        var warnings = new List<string>();
        foreach (var definition in Metrics.Definitions())
        {
            var key = definition["key"]!.GetValue<string>();
            var path = $"/api/v2/metrics/{Project}/{key}";
            var (status, existing) = await RequestAsync(HttpMethod.Get, path, version: FlagApiVersion);
            if (status == 404)
            {
                var (created, payload) = await RequestAsync(HttpMethod.Post, $"/api/v2/metrics/{Project}", Metrics.CreateBody(definition), FlagApiVersion);
                if (created is not (200 or 201))
                    warnings.Add($"{key}: create failed ({created}) {payload?["message"]?.GetValue<string>()}");
                continue;
            }
            if (status != 200 || existing is not JsonObject metric)
            {
                warnings.Add($"{key}: could not read the metric ({status})");
                continue;
            }
            var description = definition["description"]!.GetValue<string>();
            if (metric["description"]?.GetValue<string>() == description)
                continue;
            var (patched, patchedBody) = await RequestAsync(HttpMethod.Patch, path, new JsonArray
            {
                new JsonObject { ["op"] = "replace", ["path"] = "/description", ["value"] = description },
            }, FlagApiVersion);
            if (patched >= 400)
                warnings.Add($"{key}: description was not updated ({patched}) {patchedBody?["message"]?.GetValue<string>()}");
        }
        return warnings;
    }

    private static JsonObject StartBody(string noneId, string greenId)
    {
        var metrics = new JsonArray();
        foreach (var definition in Metrics.Definitions())
            metrics.Add(new JsonObject { ["metricKey"] = definition["key"]!.DeepClone(), ["autoRollback"] = true });
        var steps = new JsonArray();
        foreach (var step in RolloutSteps)
            steps.Add(new JsonObject { ["allocation"] = step.Percent * AllocationScale, ["durationMillis"] = step.Seconds * 1000 });
        return new JsonObject
        {
            ["originalVariationId"] = noneId,
            ["targetVariationId"] = greenId,
            ["randomizationUnit"] = "user",
            ["cleanupBehavior"] = "remove_rules_and_update_default_rule",
            ["comment"] = "23-api-guarded-rollout: start guarded release",
            ["bypassHealthChecks"] = new JsonArray("metric_events_any", "metric_events_with_context"),
            ["metrics"] = metrics,
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
                            ["values"] = new JsonArray("user"),
                        },
                    },
                    ["steps"] = steps,
                },
            },
        };
    }

    private static JsonObject Summarize(JsonObject item)
    {
        var phases = item["phases"] as JsonArray;
        var phase = phases is { Count: > 0 } && phases[0] is JsonObject first ? first : new JsonObject();
        var steps = new JsonArray();
        if (phase["steps"] is JsonArray rawSteps)
        {
            foreach (var node in rawSteps)
            {
                if (node is not JsonObject step)
                    continue;
                steps.Add(new JsonObject
                {
                    ["percent"] = step["allocation"]?.GetValue<int?>() is int allocation ? allocation / (double)AllocationScale : null,
                    ["durationSeconds"] = step["durationMillis"]?.GetValue<int?>() is int duration ? duration / 1000 : null,
                });
            }
        }
        var regressed = new JsonArray();
        if (phase["metricStatuses"] is JsonObject statuses)
        {
            foreach (var pair in statuses)
            {
                if (pair.Value?.GetValue<string>() == "regressed")
                    regressed.Add(pair.Key);
            }
        }
        var status = item["status"]?.GetValue<string>();
        var ended = item["endedAt"] is JsonValue endedAt && endedAt.GetValueKind() != System.Text.Json.JsonValueKind.Null
            || status is "completed" or "reverted";
        var summary = new JsonObject
        {
            ["configured"] = true,
            ["flagKey"] = HighlightEval.FlagHighlight,
            ["kind"] = item["kind"]?.DeepClone(),
            ["status"] = status,
            ["statusReason"] = item["statusReason"]?.DeepClone(),
            ["metricCount"] = item["metrics"] is JsonArray metrics ? metrics.Count : 0,
            ["regressedMetrics"] = regressed,
            ["stepIndex"] = phase["currentStepIndex"]?.GetValue<int?>(),
            ["stepCount"] = steps.Count,
            ["steps"] = steps,
            ["active"] = !ended,
        };
        summary["headline"] = Headline(summary);
        return summary;
    }

    private static string Headline(JsonObject item)
    {
        if (item["flagOn"]?.GetValue<bool?>() == false)
            return "Flag is off. Every context receives none.";
        var status = item["status"]?.GetValue<string>();
        if (string.IsNullOrEmpty(status) || status == "none")
            return item["detail"]?.GetValue<string>() ?? "No guarded release yet.";
        var names = item["regressedMetrics"] is JsonArray metrics
            ? string.Join(", ", metrics.Select(node => node?.GetValue<string>()).Where(name => !string.IsNullOrEmpty(name)))
            : "";
        var rolled = status == "reverted" || item["stopped"]?.GetValue<bool?>() == true;
        if (rolled && (item["statusReason"]?.GetValue<string>() == "reverted_regression_detected" || names.Length > 0))
            return $"Rolled back to none. {(names.Length == 0 ? "A guardrail" : names)} regressed.";
        if (rolled)
            return "Rolled back to none.";
        if (status == "waiting" && item["statusReason"]?.GetValue<string>() == "waiting_regression_detected")
            return $"Paused. {(names.Length == 0 ? "A guardrail" : names)} regressed.";
        if (status == "completed")
            return "Completed.";
        if (status == "in_progress" || item["active"]?.GetValue<bool?>() == true)
            return "Monitoring.";
        return status;
    }

    private static async Task<bool?> FlagIsOnAsync()
    {
        var (status, payload) = await RequestAsync(
            HttpMethod.Get,
            $"{FlagPath()}?env={EnvironmentKey}",
            version: FlagApiVersion);
        if (status != 200 || payload is not JsonObject flag)
            return null;
        return flag["environments"]?[EnvironmentKey]?["on"]?.GetValue<bool?>();
    }

    private static JsonArray RemoveRules(JsonObject flag)
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

    private static JsonObject Variation(string value, string name, string description) => new()
    {
        ["value"] = value,
        ["name"] = name,
        ["description"] = description,
    };

    private static JsonObject NoneSummary(string detail) => new()
    {
        ["configured"] = true,
        ["flagKey"] = HighlightEval.FlagHighlight,
        ["status"] = "none",
        ["metricCount"] = 0,
        ["steps"] = new JsonArray(),
        ["detail"] = detail,
    };

    private static string FlagPath() => $"/api/v2/flags/{Project}/{HighlightEval.FlagHighlight}";

    private static string ReleasesPath() =>
        $"/api/v2/projects/{Project}/flags/{HighlightEval.FlagHighlight}/environments/{EnvironmentKey}/releases";

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
            JsonNode? payload;
            try
            {
                payload = string.IsNullOrWhiteSpace(text) ? new JsonObject() : JsonNode.Parse(text);
            }
            catch (System.Text.Json.JsonException)
            {
                payload = new JsonObject { ["message"] = text.Length > 240 ? text[..240] : text };
            }
            return ((int)response.StatusCode, payload);
        }
        catch (Exception err) when (err is HttpRequestException or TaskCanceledException)
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
        return Error(detail, status, code);
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
