using System.Net.Http.Headers;
using System.Text;
using System.Text.Json.Nodes;

/// <summary>
/// Approval request for the move-count flag.
/// Approvals: https://launchdarkly.com/docs/home/releases/approvals
/// Create an approval request for a flag:
/// https://launchdarkly.com/docs/api/approvals/post-approval-request-for-a-flag
/// </summary>
sealed class Approvals
{
    public const string FlagKey = CountFlag.FlagKey;
    private const string Description = "Turn on the move count";
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(30) };

    public Dictionary<string, object?> ApiConfig()
    {
        var token = Env("LD_API_ACCESS_TOKEN");
        var project = Env("LD_PROJECT_KEY");
        var environment = Env("LD_ENVIRONMENT_KEY");
        var missing = new List<string>();
        if (token.Length == 0) missing.Add("LD_API_ACCESS_TOKEN");
        if (project.Length == 0) missing.Add("LD_PROJECT_KEY");
        if (environment.Length == 0) missing.Add("LD_ENVIRONMENT_KEY");
        return new Dictionary<string, object?>
        {
            ["configured"] = missing.Count == 0,
            ["missing"] = missing,
            ["projectKey"] = project.Length == 0 ? null : project,
            ["environmentKey"] = environment.Length == 0 ? null : environment,
            ["flagKey"] = FlagKey,
            ["appOrigin"] = Host(),
        };
    }

    public async Task<Dictionary<string, object?>> StateAsync()
    {
        var config = ApiConfig();
        if (config["configured"] is not true)
        {
            config["ok"] = true;
            config["request"] = null;
            return config;
        }
        var payload = await SendAsync(HttpMethod.Get, FlagPath(config), null, false);
        config["ok"] = true;
        config["request"] = Current(Items(payload));
        return config;
    }

    /// <summary>LaunchDarkly: approval request · semantic patch turnFlagOn.</summary>
    public async Task<Dictionary<string, object?>> RequestAsync()
    {
        var current = await StateAsync();
        if (current["request"] is Dictionary<string, object?> existing
            && existing.GetValueOrDefault("reviewStatus") as string != "declined"
            && existing.GetValueOrDefault("applied") is not true)
        {
            current["steps"] = new List<Dictionary<string, string>>
            {
                new()
                {
                    ["where"] = "Lab API",
                    ["text"] = "Open request reused. LaunchDarkly was not asked for a second one.",
                },
            };
            return current;
        }
        var description = NextDescription();
        var created = await SendAsync(HttpMethod.Post, FlagPath(ApiConfig()), new JsonObject
        {
            ["description"] = description,
            ["comment"] = "108-flag-approvals",
            ["instructions"] = new JsonArray { new JsonObject { ["kind"] = "turnFlagOn" } },
        }, semantic: true);
        var row = Summary(created as JsonObject ?? new JsonObject());
        var result = ApiConfig();
        result["ok"] = true;
        result["request"] = row;
        result["steps"] = new List<Dictionary<string, string>>
        {
            new()
            {
                ["where"] = "LaunchDarkly",
                ["text"] = $"POST approval-requests · turnFlagOn · {description} · review {row["reviewStatus"]}",
            },
        };
        return result;
    }

    /// <summary>LaunchDarkly: apply approval request.</summary>
    public async Task<Dictionary<string, object?>> ApplyAsync(string? requestId)
    {
        var id = (requestId ?? "").Trim();
        if (id.Length == 0) throw new ArgumentException("Approval id is required");
        var config = ApiConfig();
        var applied = await SendAsync(
            HttpMethod.Post,
            $"{FlagPath(config)}/{Uri.EscapeDataString(id)}/apply",
            new JsonObject { ["comment"] = "108-flag-approvals apply" },
            semantic: false);
        var row = Summary(applied as JsonObject ?? new JsonObject());
        config["ok"] = true;
        config["request"] = row;
        config["steps"] = new List<Dictionary<string, string>>
        {
            new()
            {
                ["where"] = "LaunchDarkly",
                ["text"] = $"POST approval-requests/{id}/apply · status {row["status"]}",
            },
        };
        return config;
    }

    /// <summary>Delete approval requests for this flag and turn the flag off.</summary>
    public async Task<Dictionary<string, object?>> ResetAsync()
    {
        var config = ApiConfig();
        if (config["configured"] is not true)
        {
            var missing = config["missing"] as List<string> ?? [];
            throw new InvalidOperationException("Approvals need " + string.Join(", ", missing) + ".");
        }
        var steps = new List<Dictionary<string, string>>();
        var found = new Dictionary<string, JsonObject>();
        void AddItems(JsonNode? payload)
        {
            foreach (var item in Items(payload))
            {
                var id = Text(item["_id"]);
                if (!string.IsNullOrEmpty(id)) found[id] = item;
            }
        }
        AddItems(await SendAsync(HttpMethod.Get, FlagPath(config), null, false));
        var resource = $"proj/{config["projectKey"]}:env/{config["environmentKey"]}:flag/{FlagKey}";
        try
        {
            AddItems(await SendAsync(
                HttpMethod.Get,
                "/approval-requests?limit=20&filter=" + Uri.EscapeDataString($"resourceId equals {resource}"),
                null,
                false));
        }
        catch (InvalidOperationException)
        {
            // The flag list is enough when the account list is unavailable.
        }
        var items = found.Values.ToList();
        if (items.Count == 0)
            steps.Add(Step("LaunchDarkly", "GET approval-requests · none to delete"));
        foreach (var item in items)
        {
            var id = Text(item["_id"]);
            if (string.IsNullOrEmpty(id)) continue;
            try
            {
                await SendAsync(HttpMethod.Delete, $"{FlagPath(config)}/{Uri.EscapeDataString(id)}", null, false);
                steps.Add(Step("LaunchDarkly", $"DELETE approval-requests/{id}"));
            }
            catch (Exception exception)
            {
                steps.Add(Step("LaunchDarkly", $"DELETE approval-requests/{id} · {exception.Message}"));
            }
        }
        JsonNode? patched;
        try
        {
            patched = await SendAsync(HttpMethod.Patch, FlagPathOff(config), new JsonObject
            {
                ["environmentKey"] = config["environmentKey"] as string,
                ["comment"] = "108-flag-approvals reset",
                ["instructions"] = new JsonArray { new JsonObject { ["kind"] = "turnFlagOff" } },
            }, semantic: true);
        }
        catch (Exception exception)
        {
            throw new ApprovalResetException(exception.Message, steps);
        }
        var on = patched?["environments"]?[config["environmentKey"] as string ?? ""]?["on"]?.ToString();
        steps.Add(Step("LaunchDarkly", $"PATCH flag · turnFlagOff · on {on}"));
        config["ok"] = true;
        config["request"] = null;
        config["steps"] = steps;
        return config;
    }

    private static Dictionary<string, string> Step(string where, string text) => new()
    {
        ["where"] = where,
        ["text"] = text,
    };

    private static string FlagPathOff(Dictionary<string, object?> config)
    {
        var project = Uri.EscapeDataString(config["projectKey"] as string ?? "");
        return $"/flags/{project}/{Uri.EscapeDataString(FlagKey)}";
    }

    private async Task<JsonNode?> SendAsync(HttpMethod method, string path, JsonObject? body, bool semantic)
    {
        var config = ApiConfig();
        if (config["configured"] is not true)
        {
            var missing = config["missing"] as List<string> ?? [];
            throw new InvalidOperationException("Approvals need " + string.Join(", ", missing) + ".");
        }
        using var message = new HttpRequestMessage(method, Host() + "/api/v2" + path);
        message.Headers.TryAddWithoutValidation("Authorization", Env("LD_API_ACCESS_TOKEN"));
        message.Headers.TryAddWithoutValidation("LD-API-Version", Version());
        message.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        if (body != null)
        {
            var type = semantic
                ? "application/json; domain-model=launchdarkly.semanticpatch"
                : "application/json";
            message.Content = new StringContent(body.ToJsonString(), Encoding.UTF8);
            message.Content.Headers.ContentType = MediaTypeHeaderValue.Parse(type);
        }
        using var response = await _http.SendAsync(message);
        var raw = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            var detail = raw.Length > 300 ? raw[..300] : raw;
            throw new InvalidOperationException($"LaunchDarkly {(int)response.StatusCode}: {detail}");
        }
        return raw.Length == 0 ? new JsonObject() : JsonNode.Parse(raw);
    }

    private static Dictionary<string, object?> Summary(JsonObject item)
    {
        var status = Text(item["status"]) ?? "pending";
        var applied = item["appliedDate"] != null || status == "completed";
        return new Dictionary<string, object?>
        {
            ["id"] = Text(item["_id"]),
            ["reviewStatus"] = Text(item["reviewStatus"]) ?? "pending",
            ["status"] = status,
            ["applied"] = applied,
            ["description"] = Text(item["description"]) ?? Description,
        };
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<string>(out var text) ? text : null;

    private static Dictionary<string, object?>? Current(IEnumerable<JsonObject> items)
    {
        var ranked = new List<(long Created, Dictionary<string, object?> Row)>();
        foreach (var item in items)
        {
            var row = Summary(item);
            if (row["applied"] is true) continue;
            var status = row["status"] as string;
            if (status is "completed" or "failed") continue;
            var created = item["creationDate"] is JsonValue value && value.TryGetValue<long>(out var parsed) ? parsed : 0L;
            ranked.Add((created, row));
        }
        ranked.Sort((left, right) => right.Created.CompareTo(left.Created));
        foreach (var (_, row) in ranked)
        {
            if (row["reviewStatus"] as string != "declined") return row;
        }
        return ranked.Count == 0 ? null : ranked[0].Row;
    }

    private static IEnumerable<JsonObject> Items(JsonNode? payload)
    {
        if (payload?["items"] is not JsonArray items) yield break;
        foreach (var item in items)
        {
            if (item is JsonObject row) yield return row;
        }
    }

    /// <summary>Next approval name. `.request-count` is shared with Python, Node, and Java.</summary>
    private static string NextDescription()
    {
        var root = ExampleRoot();
        var counter = Path.Combine(root, ".request-count");
        var lockPath = Path.Combine(root, ".request-count.lock");
        var deadline = DateTime.UtcNow.AddSeconds(2);
        while (true)
        {
            try
            {
                using (new FileStream(lockPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    break;
                }
            }
            catch (IOException) when (File.Exists(lockPath))
            {
                if (DateTime.UtcNow <= deadline)
                {
                    Thread.Sleep(50);
                    continue;
                }
                if (DateTime.UtcNow - File.GetLastWriteTimeUtc(lockPath) > TimeSpan.FromSeconds(5))
                {
                    File.Delete(lockPath);
                    continue;
                }
                throw new InvalidOperationException("Approval counter is locked.");
            }
        }
        try
        {
            var current = 0;
            if (File.Exists(counter))
            {
                var raw = File.ReadAllText(counter).Trim();
                if (raw.Length > 0 && raw.All(char.IsDigit)) current = int.Parse(raw);
            }
            var next = current + 1;
            var temporary = Path.Combine(root, ".request-count.tmp");
            File.WriteAllText(temporary, next + "\n");
            File.Move(temporary, counter, overwrite: true);
            return $"{Description} · {next}";
        }
        finally
        {
            if (File.Exists(lockPath)) File.Delete(lockPath);
        }
    }

    private static string ExampleRoot()
    {
        foreach (var start in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
        {
            var dir = new DirectoryInfo(start);
            while (dir != null)
            {
                if (File.Exists(Path.Combine(dir.FullName, "approvals.py"))
                    && Directory.Exists(Path.Combine(dir.FullName, "python")))
                {
                    return dir.FullName;
                }
                dir = dir.Parent;
            }
        }
        throw new InvalidOperationException("Approval counter directory was not found.");
    }

    private static string FlagPath(Dictionary<string, object?> config)
    {
        var project = Uri.EscapeDataString(config["projectKey"] as string ?? "");
        var environment = Uri.EscapeDataString(config["environmentKey"] as string ?? "");
        return $"/projects/{project}/flags/{Uri.EscapeDataString(FlagKey)}/environments/{environment}/approval-requests";
    }

    private static string Env(string name) => Environment.GetEnvironmentVariable(name)?.Trim() ?? "";

    private static string Host()
    {
        var host = Env("LD_API_HOST");
        if (host.Length == 0) host = "https://app.launchdarkly.com";
        return host.TrimEnd('/');
    }

    private static string Version()
    {
        var version = Env("LD_API_VERSION");
        return version.Length == 0 ? "20240415" : version;
    }
}

sealed class ApprovalResetException : InvalidOperationException
{
    public List<Dictionary<string, string>> Steps { get; }

    public ApprovalResetException(string message, List<Dictionary<string, string>> steps) : base(message)
    {
        Steps = steps;
    }
}
