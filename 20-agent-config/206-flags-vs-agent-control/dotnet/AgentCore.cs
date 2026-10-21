using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;
using LaunchDarkly.Sdk.Server.Ai;
using LaunchDarkly.Sdk.Server.Ai.Adapters;
using LaunchDarkly.Sdk.Server.Ai.Config;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;
using LaunchDarkly.Sdk.Server.Ai.Tracking;

namespace FlagCompare;

/// <summary>
/// Domain logic for 26-flags-vs-agent-control (no HTTP here).
///
/// Three sources, one Generate:
///   original  CompletionConfig (model, messages, {{ stories }}, attached tools)
///   flags     four VariationDetail reads, assembled in the app
///   json      one JSON VariationDetail, parsed in the app
///
/// The guardrail is JudgeConfig plus a local Ollama JSON score. On a fail,
/// only the AgentControl variation can carry reduce-briefing-uncertainty.
///
/// LaunchDarkly: completion config · feature flags · judges · Library tools
/// https://launchdarkly.com/docs/sdk/ai/dotnet
/// https://launchdarkly.com/docs/sdk/features/flag-types
/// https://launchdarkly.com/docs/home/agentcontrol/judges
/// https://launchdarkly.com/docs/home/agentcontrol/tools
/// </summary>
public static class AgentCore
{
    public sealed record Persona(string Id, string Name, string Profile);

    public static readonly IReadOnlyList<Persona> Personas = new List<Persona>
    {
        new("conservative-charlie", "Conservative Charlie", "conservative"),
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
    };

    private const string CannedStories =
        "No ticker stories loaded yet. Ask the user to click Get Stories.";

    private const string DefaultConfigKey = "equity-briefing-flag-compare";
    private const string DefaultJudgeKey = "equity-briefing-flag-compare-judge";
    private const string DefaultJudgeMetric = "$ld:ai:judge:flag-compare";
    private const double DefaultPassThreshold = 0.65;
    private const string RepairToolKey = "reduce-briefing-uncertainty";
    private const string DefaultOllamaModelName = "llama3.2:3b";
    private const string JudgeJsonSuffix =
        "Respond with JSON only: {\"score\": <number from 0 to 1>, \"reasoning\": \"<short text>\"}";

    private const string FlagModelKey = "configure-briefing-model";
    private const string FlagSystemKey = "configure-briefing-system-prompt";
    private const string FlagUserKey = "configure-briefing-user-prompt";
    private const string FlagJudgeKey = "enable-briefing-judge";
    private const string FlagJsonKey = "configure-briefing-json";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(180) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    private sealed class Metrics
    {
        public long? PromptTokens;
        public long? CompletionTokens;
        public long? TotalTokens;
        public long? LatencyMs;
        public long? TtftMs;
        public string? FinishReason;

        public Dictionary<string, object?> ToMap()
        {
            var map = new Dictionary<string, object?>();
            if (PromptTokens != null) map["prompt_tokens"] = PromptTokens;
            if (CompletionTokens != null) map["completion_tokens"] = CompletionTokens;
            if (TotalTokens != null) map["total_tokens"] = TotalTokens;
            if (LatencyMs != null) map["latency_ms"] = LatencyMs;
            if (TtftMs != null) map["ttft_ms"] = TtftMs;
            if (FinishReason != null) map["finish_reason"] = FinishReason;
            return map;
        }
    }

    private sealed class EvalMeta
    {
        public string? VariationKey;
        public int? Version;
        public string? VersionKey;
        public string? Mode;
        public string? ModelKey;
        public string? ModelVersion;
        public int? VariationIndex;
        public Dictionary<string, object?>? Reason;
    }

    private sealed class FlagHit
    {
        public required object? Value;
        public required Dictionary<string, object?> Record;
        public required bool Missing;
    }

    private sealed class Resolved
    {
        public required string Source;
        public required string Model;
        public required string System;
        public required string User;
        public required bool JudgeOn;
        public required int Evaluations;
        public required string JudgeSurface;
        public required List<string> Missing;
        public required List<Dictionary<string, object?>> Records;
    }

    public static IReadOnlyList<Persona> DemoPersonas()
        => Personas.Where(p => p.Id == "thoughtless-toby").ToList();

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    public static string ConfigKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_AGENT_CONFIG_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultConfigKey : key;
    }

    public static string JudgeKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_JUDGE_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultJudgeKey : key;
    }

    public static double PassThreshold()
    {
        var raw = (Environment.GetEnvironmentVariable("JUDGE_PASS_THRESHOLD") ?? "").Trim();
        if (raw.Length == 0) return DefaultPassThreshold;
        return double.TryParse(raw, out var n) ? n : DefaultPassThreshold;
    }

    public static string DefaultOllamaModel()
    {
        var model = (Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "").Trim();
        return model.Length == 0 ? DefaultOllamaModelName : model;
    }

    /// <summary>
    /// LaunchDarkly: server-side SDK plus the AI SDK for completion and judge configs.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    public static void InitLaunchDarkly()
    {
        if (_aiClient != null) return;

        var sdkKey = (Environment.GetEnvironmentVariable("LD_SDK_KEY") ?? "").Trim();
        if (sdkKey.Length == 0)
        {
            throw new InvalidOperationException(
                "LD_SDK_KEY is required. Export a server-side SDK key for the environment " +
                "that targets equity-briefing-flag-compare.");
        }

        var client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!client.Initialized)
        {
            client.Dispose();
            throw new InvalidOperationException(
                "LaunchDarkly client failed to initialize within 5s. " +
                "Check LD_SDK_KEY and network access to LaunchDarkly.");
        }

        _ldClient = client;
        _aiClient = new LdAiClient(new LdClientAdapter(client));
    }

    private static LdAiClient RequireAiClient()
        => _aiClient ?? throw new InvalidOperationException(
            "LaunchDarkly AI client is not initialized. Call InitLaunchDarkly() first.");

    private static LdClient RequireLdClient()
        => _ldClient ?? throw new InvalidOperationException(
            "LaunchDarkly client is not initialized. Call InitLaunchDarkly() first.");

    public static Context BuildContext(Persona persona)
        => Context.Builder(persona.Id).Name(persona.Name).Build();

    private static string MessagesDir()
        => Path.Combine(YahooNews.ExampleRoot(), "rest", "messages");

    private static string ReadMessageFile(string name)
    {
        var path = Path.Combine(MessagesDir(), name);
        try
        {
            return File.ReadAllText(path);
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException($"Could not read message file {path}: {exc.Message}", exc);
        }
    }

    private static string FormatStories(List<Dictionary<string, object?>>? tickerResults)
        => tickerResults is { Count: > 0 } ? YahooNews.FormatStoriesForPrompt(tickerResults) : CannedStories;

    private static string FillStories(string? template, string storiesText)
        => (template ?? "")
            .Replace("{{ stories }}", storiesText, StringComparison.Ordinal)
            .Replace("{{stories}}", storiesText, StringComparison.Ordinal);

    private static (string Model, string System, string User) PersonaPrompts(Persona persona)
    {
        if (persona.Id == "thoughtless-toby")
        {
            return (
                "llama3.2:1b",
                ReadMessageFile("reckless-system.txt").Trim(),
                ReadMessageFile("reckless-user.txt").Trim());
        }
        return (
            "llama3.2:3b",
            ReadMessageFile("skeptic-system.txt").Trim(),
            ReadMessageFile("skeptic-user.txt").Trim());
    }

    /// <summary>
    /// SDK default when the completion config key is missing
    /// (concise-skeptic / Charlie shape).
    ///
    /// LaunchDarkly: CompletionConfig default.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    private static LdAiCompletionConfigDefault SkepticCompletionDefault() =>
        LdAiCompletionConfigDefault.New()
            .Enable()
            .SetModelName(DefaultOllamaModel())
            .SetModelProviderName("Custom")
            .AddMessage(ReadMessageFile("skeptic-system.txt").Trim(), LdAiConfigTypes.Role.System)
            .AddMessage(ReadMessageFile("skeptic-user.txt").Trim(), LdAiConfigTypes.Role.User)
            .Build();

    /// <summary>
    /// LaunchDarkly: JudgeConfig default — system prompt and metric when the key is missing.
    /// https://launchdarkly.com/docs/home/agentcontrol/judges
    /// </summary>
    private static LdAiJudgeConfigDefault JudgeDefault() =>
        LdAiJudgeConfigDefault.New()
            .Enable()
            .SetModelName("llama3.2:3b")
            .SetModelProviderName("Custom")
            .SetEvaluationMetricKey(DefaultJudgeMetric)
            .AddMessage(ReadMessageFile("judge-system.txt").Trim(), LdAiConfigTypes.Role.System)
            .Build();

    private static Dictionary<string, object?> ContextAsMap(Persona persona) => new()
    {
        ["kind"] = "user",
        ["key"] = persona.Id,
        ["name"] = persona.Name,
    };

    private static Dictionary<string, object?> EvalEvent(string surface, string key) => new()
    {
        ["type"] = "eval",
        ["surface"] = surface,
        ["key"] = key,
    };

    private static string? LdString(LdValue value)
    {
        if (value.IsNull) return null;
        return value.Type == LdValueType.String ? value.AsString : value.ToString();
    }

    private static string? NullIfEmpty(string? value) => string.IsNullOrEmpty(value) ? null : value;

    private static string ReasonKindName(EvaluationReasonKind kind) => kind switch
    {
        EvaluationReasonKind.Off => "OFF",
        EvaluationReasonKind.Fallthrough => "FALLTHROUGH",
        EvaluationReasonKind.TargetMatch => "TARGET_MATCH",
        EvaluationReasonKind.RuleMatch => "RULE_MATCH",
        EvaluationReasonKind.PrerequisiteFailed => "PREREQUISITE_FAILED",
        EvaluationReasonKind.Error => "ERROR",
        _ => kind.ToString().ToUpperInvariant(),
    };

    private static string ErrorKindName(EvaluationErrorKind kind) => kind switch
    {
        EvaluationErrorKind.FlagNotFound => "FLAG_NOT_FOUND",
        EvaluationErrorKind.ClientNotReady => "CLIENT_NOT_READY",
        EvaluationErrorKind.MalformedFlag => "MALFORMED_FLAG",
        EvaluationErrorKind.UserNotSpecified => "USER_NOT_SPECIFIED",
        EvaluationErrorKind.WrongType => "WRONG_TYPE",
        EvaluationErrorKind.Exception => "EXCEPTION",
        _ => kind.ToString().ToUpperInvariant(),
    };

    private static Dictionary<string, object?> ReasonAsMap(EvaluationReason reason)
    {
        var map = new Dictionary<string, object?> { ["kind"] = ReasonKindName(reason.Kind) };
        if (reason.Kind == EvaluationReasonKind.RuleMatch)
        {
            map["ruleIndex"] = reason.RuleIndex;
            map["ruleId"] = reason.RuleId;
        }
        if (reason.Kind == EvaluationReasonKind.Error && reason.ErrorKind != null)
        {
            map["errorKind"] = ErrorKindName(reason.ErrorKind.Value);
        }
        return map;
    }

    private static bool IsFlagNotFound(EvaluationReason reason)
        => reason.Kind == EvaluationReasonKind.Error
           && reason.ErrorKind == EvaluationErrorKind.FlagNotFound;

    private static string PreviewValue(LdValue value, int limit = 180)
    {
        var text = value.Type switch
        {
            LdValueType.Bool => value.AsBool ? "true" : "false",
            LdValueType.String => value.AsString,
            LdValueType.Null => "",
            _ => value.ToJsonString(),
        };
        text = Regex.Replace(text ?? "", @"\s+", " ").Trim();
        return text.Length <= limit ? text : text[..(limit - 1)] + "…";
    }

    /// <summary>
    /// LaunchDarkly: variation detail — value, variation index, and reason.
    /// https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    /// </summary>
    private static FlagHit FlagDetail(string key, Persona persona, LdValue fallback, object? displayValue)
    {
        var detail = RequireLdClient().JsonVariationDetail(key, BuildContext(persona), fallback);
        var reason = ReasonAsMap(detail.Reason);
        var missing = IsFlagNotFound(detail.Reason);
        var value = missing ? displayValue : LdToObject(detail.Value);
        return new FlagHit
        {
            Value = value,
            Missing = missing,
            Record = new Dictionary<string, object?>
            {
                ["key"] = key,
                ["variationIndex"] = detail.VariationIndex,
                ["reason"] = reason,
                ["reasonKind"] = reason.GetValueOrDefault("kind"),
                ["valuePreview"] = PreviewValue(missing ? fallback : detail.Value),
            },
        };
    }

    private static object? LdToObject(LdValue value) => value.Type switch
    {
        LdValueType.Null => null,
        LdValueType.Bool => value.AsBool,
        LdValueType.Number => value.AsDouble,
        LdValueType.String => value.AsString,
        LdValueType.Array => value.List.Select(LdToObject).ToList(),
        LdValueType.Object => value.Dictionary.ToDictionary(kv => kv.Key, kv => LdToObject(kv.Value)),
        _ => value.ToJsonString(),
    };

    /// <summary>
    /// Metadata for the served AgentControl variation. The typed AI config does not
    /// expose variationKey, so this reads <c>_ldMeta</c> from the same key.
    /// https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    /// </summary>
    private static EvalMeta EvaluationMeta(Persona persona)
    {
        var detail = RequireLdClient().JsonVariationDetail(
            ConfigKey(), BuildContext(persona), LdValue.Of("{}"));
        var value = detail.Value;
        var meta = !value.IsNull && value.Type == LdValueType.Object ? value.Get("_ldMeta") : LdValue.Null;
        return new EvalMeta
        {
            VariationKey = meta.IsNull ? null : NullIfEmpty(LdString(meta.Get("variationKey"))),
            Version = meta.IsNull || meta.Get("version").IsNull ? null : meta.Get("version").AsInt,
            VersionKey = meta.IsNull ? null : NullIfEmpty(LdString(meta.Get("versionKey"))),
            Mode = meta.IsNull ? null : NullIfEmpty(LdString(meta.Get("mode"))),
            ModelKey = meta.IsNull ? null : NullIfEmpty(LdString(meta.Get("modelKey"))),
            ModelVersion = meta.IsNull ? null : NullIfEmpty(LdString(meta.Get("modelVersion"))),
            VariationIndex = detail.VariationIndex,
            Reason = ReasonAsMap(detail.Reason),
        };
    }

    private static List<string> AgentAppWork() =>
    [
        "Evaluated one completion config for the model, both messages, and any attached tools.",
        "LaunchDarkly substituted {{ stories }} before the app saw the user message.",
        "Called the model and provider named on that variation.",
        "Evaluated one judge config. On a fail, the app runs reduce-briefing-uncertainty if that tool is attached.",
        "Separate flags and the JSON flag do not return a tool, so a failed draft stays failed.",
    ];

    private static List<string> FlagAppWork(string source, bool judgeOn)
    {
        var steps = source == "json"
            ? new List<string>
            {
                "Evaluated one JSON flag. The value is an object the app defined.",
                "Read model, systemPrompt, userPrompt, and judge out of that object.",
                "Substituted {{ stories }} in the user prompt.",
                "Built the message list and picked a provider from the model id.",
            }
            : new List<string>
            {
                "Evaluated four flags. Each one repeated the Charlie name rule.",
                "Substituted {{ stories }} in the user-prompt flag.",
                "Built the message list from two string flags and picked a provider from the model id.",
            };
        steps.Add(judgeOn
            ? "The flag said to score. The score itself still comes from the AgentControl judge config."
            : "The flag said not to score, so the draft stays plain.");
        return steps;
    }

    private static string ReduceBriefingUncertainty(string? draft)
    {
        var text = draft ?? "";
        text = Regex.Replace(text, @"\b100\s*%", "low", RegexOptions.IgnoreCase);
        text = Regex.Replace(text, @"\b9[5-9]\s*%", "limited", RegexOptions.IgnoreCase);
        text = Regex.Replace(
            text,
            @"\b(?:buy hard|strong buy|all-in|moonshot|to the moon|can't lose|cannot lose|no-brainer)\b",
            "no firm trade",
            RegexOptions.IgnoreCase);
        text = Regex.Replace(
            text,
            @"\b(?:will soar|will double|can't miss|cannot miss)\b",
            "may not move",
            RegexOptions.IgnoreCase);
        const string hedge =
            "Uncertainty: these headlines do not support a firm recommendation. " +
            "Confidence stays low, and missing information is left missing.";
        if (!text.Contains("Uncertainty:", StringComparison.Ordinal))
        {
            text = $"{text.Trim()}\n\n{hedge}";
        }
        return text;
    }

    private static int EstimateTokens(string text) => Math.Max(1, text.Length / 4);

    private static void FillTokenEstimates(
        List<Dictionary<string, string>> messages, string completion, Metrics metrics)
    {
        var prompt = string.Concat(messages.Select(m => m.GetValueOrDefault("content") ?? ""));
        metrics.PromptTokens = EstimateTokens(prompt);
        metrics.CompletionTokens = EstimateTokens(completion);
        metrics.TotalTokens = (metrics.PromptTokens ?? 0) + (metrics.CompletionTokens ?? 0);
    }

    private static List<Dictionary<string, string>> MessagesAsDicts(IEnumerable<LdAiConfigTypes.Message> messages)
    {
        var list = new List<Dictionary<string, string>>();
        foreach (var m in messages)
        {
            list.Add(new Dictionary<string, string>
            {
                ["role"] = m.Role.ToString().ToLowerInvariant(),
                ["content"] = m.Content ?? "",
            });
        }
        return list;
    }

    private static string UserMessageText(List<Dictionary<string, string>> messages)
        => messages.FirstOrDefault(m => m.GetValueOrDefault("role") == "user")?.GetValueOrDefault("content") ?? "";

    private static string SystemMessageText(List<Dictionary<string, string>> messages)
        => string.Join("\n", messages
            .Where(m => m.GetValueOrDefault("role") == "system")
            .Select(m => m.GetValueOrDefault("content") ?? "")).Trim();

    private static (string Provider, string Model) ResolveRuntime(string? modelName, string? providerName)
    {
        var model = modelName ?? "";
        var pl = (providerName ?? "").Trim().ToLowerInvariant();
        if (pl is "custom" or "ollama" || model.Contains(':'))
        {
            return ("ollama", model);
        }
        if (string.IsNullOrWhiteSpace(model))
        {
            throw new InvalidOperationException("AgentControl variation has no model name.");
        }
        return ("ollama", model);
    }

    private static List<string> ToolNames(LdAiCompletionConfig config)
    {
        var names = new List<string>();
        foreach (var (key, tool) in config.Tools)
        {
            names.Add(string.IsNullOrEmpty(tool.Name) ? key : tool.Name);
        }
        return names;
    }

    private static async IAsyncEnumerable<string> OllamaStreamAsync(
        string model, List<Dictionary<string, string>> messages, [EnumeratorCancellation] CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        using var request = new HttpRequestMessage(HttpMethod.Post, $"{host}/api/chat")
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { model, stream = true, messages }),
                Encoding.UTF8, "application/json"),
        };

        HttpResponseMessage response;
        try
        {
            response = await Http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): {exc.Message}", exc);
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(ct);
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): HTTP {(int)response.StatusCode} {body}");
        }

        await using var stream = await response.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream, Encoding.UTF8);
        while (await reader.ReadLineAsync(ct) is { } line)
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            if (root.TryGetProperty("error", out var errEl))
            {
                throw new InvalidOperationException(errEl.ToString());
            }
            var content = "";
            if (root.TryGetProperty("message", out var msgEl) &&
                msgEl.TryGetProperty("content", out var contentEl) &&
                contentEl.ValueKind == JsonValueKind.String)
            {
                content = contentEl.GetString() ?? "";
            }
            if (content.Length > 0) yield return content;
            if (root.TryGetProperty("done", out var doneEl) && doneEl.ValueKind == JsonValueKind.True)
                yield break;
        }
    }

    private static async IAsyncEnumerable<(Dictionary<string, object?> Evt, string? Text)> GenerateOllamaAsync(
        string model, List<Dictionary<string, string>> messages, Stopwatch sw, Metrics metrics,
        [EnumeratorCancellation] CancellationToken ct)
    {
        var textParts = new StringBuilder();
        var first = true;
        var enumerator = OllamaStreamAsync(model, messages, ct).GetAsyncEnumerator(ct);
        try
        {
            while (true)
            {
                var hasNext = false;
                string? chunk = null;
                Exception? error = null;
                try
                {
                    hasNext = await enumerator.MoveNextAsync();
                    if (hasNext) chunk = enumerator.Current;
                }
                catch (Exception exc)
                {
                    error = exc;
                }

                if (error != null)
                {
                    yield return (
                        new Dictionary<string, object?> { ["type"] = "error", ["message"] = error.Message },
                        null);
                    metrics.FinishReason = "error";
                    yield break;
                }
                if (!hasNext) break;

                if (first)
                {
                    metrics.TtftMs = (long)sw.Elapsed.TotalMilliseconds;
                    first = false;
                }
                textParts.Append(chunk);
                yield return (
                    new Dictionary<string, object?> { ["type"] = "token", ["text"] = chunk },
                    null);
            }
        }
        finally
        {
            await enumerator.DisposeAsync();
        }

        metrics.FinishReason = "stop";
        FillTokenEstimates(messages, textParts.ToString(), metrics);
        yield return (new Dictionary<string, object?> { ["type"] = "_complete" }, textParts.ToString());
    }

    private static async Task<JsonElement> OllamaJudgeJsonAsync(
        string model, List<Dictionary<string, string>> messages, CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        using var request = new HttpRequestMessage(HttpMethod.Post, $"{host}/api/chat")
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new
                {
                    model,
                    stream = false,
                    format = "json",
                    options = new { temperature = 0 },
                    messages,
                }),
                Encoding.UTF8, "application/json"),
        };

        HttpResponseMessage response;
        try
        {
            response = await Http.SendAsync(request, ct);
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException(
                $"Ollama judge failed ({host}, model={model}): {exc.Message}", exc);
        }

        var body = await response.Content.ReadAsStringAsync(ct);
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama judge failed ({host}, model={model}): HTTP {(int)response.StatusCode} {body}");
        }

        using var outer = JsonDocument.Parse(body);
        var root = outer.RootElement;
        if (root.TryGetProperty("error", out var errEl))
        {
            throw new InvalidOperationException(errEl.ToString());
        }

        var content = "";
        if (root.TryGetProperty("message", out var msgEl) &&
            msgEl.TryGetProperty("content", out var contentEl) &&
            contentEl.ValueKind == JsonValueKind.String)
        {
            content = (contentEl.GetString() ?? "").Trim();
        }
        if (content.Length == 0)
        {
            throw new InvalidOperationException("Ollama judge returned empty content");
        }
        return JsonDocument.Parse(content).RootElement.Clone();
    }

    /// <summary>
    /// LaunchDarkly: JudgeConfig — prompts and model from the judge config.
    /// The numeric score is an Ollama JSON call. Python uses create_judge.
    /// https://launchdarkly.com/docs/home/agentcontrol/judges
    /// </summary>
    private static async Task<Dictionary<string, object?>> ScoreDraftAsync(
        Persona persona, string storiesText, string draft, string source, int evaluations, CancellationToken ct)
    {
        var threshold = PassThreshold();
        var baseResult = new Dictionary<string, object?>
        {
            ["type"] = "judge",
            ["source"] = source,
            ["on"] = true,
            ["judgeKey"] = JudgeKey(),
            ["threshold"] = threshold,
            ["evaluations"] = evaluations,
        };
        if (string.IsNullOrWhiteSpace(draft))
        {
            baseResult["success"] = false;
            baseResult["passed"] = false;
            baseResult["score"] = null;
            baseResult["reasoning"] = null;
            baseResult["error"] = "No draft to score.";
            return baseResult;
        }

        try
        {
            var config = RequireAiClient().JudgeConfig(JudgeKey(), BuildContext(persona), JudgeDefault());
            string model;
            try
            {
                model = ResolveRuntime(config.Model.Name, config.Provider.Name).Model;
            }
            catch
            {
                model = config.Model.Name ?? "llama3.2:3b";
            }
            if (string.IsNullOrWhiteSpace(model)) model = "llama3.2:3b";

            var system = SystemMessageText(MessagesAsDicts(config.Messages));
            if (system.Length == 0) system = ReadMessageFile("judge-system.txt").Trim();
            if (!system.Contains("Respond with JSON", StringComparison.Ordinal))
            {
                system = $"{system}\n\n{JudgeJsonSuffix}";
            }
            var user =
                "MESSAGE HISTORY:\n" +
                "Task: Write a short equity briefing comparing the tickers using only " +
                $"the headlines below.\n\nHEADLINES:\n{storiesText}\n\nRESPONSE TO EVALUATE:\n{draft}";
            var parsed = await OllamaJudgeJsonAsync(model, new List<Dictionary<string, string>>
            {
                new() { ["role"] = "system", ["content"] = system },
                new() { ["role"] = "user", ["content"] = user },
            }, ct);

            double? score = null;
            if (parsed.TryGetProperty("score", out var scoreEl) && scoreEl.ValueKind == JsonValueKind.Number)
            {
                score = scoreEl.GetDouble();
            }
            string? reasoning = null;
            if (parsed.TryGetProperty("reasoning", out var reasonEl) && reasonEl.ValueKind == JsonValueKind.String)
            {
                reasoning = reasonEl.GetString();
            }

            var metric = string.IsNullOrWhiteSpace(config.EvaluationMetricKey)
                ? DefaultJudgeMetric
                : config.EvaluationMetricKey;
            try
            {
                config.CreateTracker().TrackJudgeResult(new JudgeResult(
                    metric, score ?? 0.0, sampled: true, success: true, judgeConfigKey: JudgeKey()));
            }
            catch
            {
                // Best-effort Monitoring hook.
            }

            baseResult["success"] = true;
            baseResult["error"] = null;
            baseResult["score"] = score;
            baseResult["reasoning"] = reasoning;
            baseResult["metricKey"] = metric;
            baseResult["passed"] = score != null && score.Value >= threshold;
            return baseResult;
        }
        catch (Exception exc)
        {
            baseResult["success"] = false;
            baseResult["passed"] = false;
            baseResult["score"] = null;
            baseResult["reasoning"] = null;
            baseResult["error"] = exc.Message;
            return baseResult;
        }
    }

    private static void TrackGenerationSuccess(ILdAiConfigTracker? tracker, Metrics metrics)
    {
        if (tracker == null) return;
        try
        {
            tracker.TrackSuccess();
            if (metrics.LatencyMs != null) tracker.TrackDuration(metrics.LatencyMs.Value);
            if (metrics.TtftMs != null) tracker.TrackTimeToFirstToken(metrics.TtftMs.Value);
        }
        catch
        {
            // Metrics are best-effort.
        }
    }

    private static void TrackGenerationError(ILdAiConfigTracker? tracker)
    {
        if (tracker == null) return;
        try { tracker.TrackError(); }
        catch { /* best-effort */ }
    }

    /// <summary>
    /// LaunchDarkly: Library tool attached only to the reckless-hype variation.
    /// The app invokes it after a failed guardrail. Flags have nothing to attach.
    /// https://launchdarkly.com/docs/home/agentcontrol/tools
    /// </summary>
    private static IEnumerable<Dictionary<string, object?>> RepairIfFailed(
        List<string> names, ILdAiConfigTracker? tracker, string draft, Dictionary<string, object?> scored)
    {
        if (!false.Equals(scored.GetValueOrDefault("passed")) || false.Equals(scored.GetValueOrDefault("on")))
        {
            yield break;
        }
        if (!names.Contains(RepairToolKey))
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "status",
                ["message"] =
                    "Judge failed. This variation has no repair tool attached. " +
                    "Provision with rest/attach-repair-tool.sh.",
            };
            yield break;
        }
        yield return EvalEvent("tool", RepairToolKey);
        try { tracker?.TrackToolCall(RepairToolKey); }
        catch { /* best-effort */ }
        yield return new Dictionary<string, object?>
        {
            ["type"] = "repair",
            ["tool"] = RepairToolKey,
            ["repaired"] = ReduceBriefingUncertainty(draft),
        };
    }

    private static async IAsyncEnumerable<Dictionary<string, object?>> GenerateFromResolvedAsync(
        Persona persona,
        List<Dictionary<string, object?>> tickerResults,
        Resolved resolved,
        [EnumeratorCancellation] CancellationToken ct)
    {
        var storiesText = FormatStories(tickerResults);
        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();
        var messages = new List<Dictionary<string, string>>
        {
            new() { ["role"] = "system", ["content"] = resolved.System.Trim() },
            new() { ["role"] = "user", ["content"] = FillStories(resolved.User, storiesText) },
        };

        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = new Dictionary<string, object?>
            {
                ["id"] = persona.Id,
                ["name"] = persona.Name,
                ["profile"] = persona.Profile,
            },
            ["input"] = messages[1]["content"],
            ["userTemplate"] = resolved.User.Trim(),
            ["provider"] = "ollama",
            ["model"] = resolved.Model,
            ["mode"] = resolved.Source,
            ["configKey"] = resolved.Source == "json" ? FlagJsonKey : FlagModelKey,
            ["fallback"] = resolved.Missing.Count > 0,
            ["stories"] = tickerResults,
            ["source"] = resolved.Source,
            ["systemPrompt"] = resolved.System.Trim(),
            ["judgeOn"] = resolved.JudgeOn,
            ["judgeSurface"] = resolved.JudgeOn ? resolved.JudgeSurface : "off",
            ["evaluations"] = resolved.Evaluations,
            ["ldTransaction"] = new Dictionary<string, object?>
            {
                ["sent"] = new Dictionary<string, object?>
                {
                    ["source"] = resolved.Source,
                    ["context"] = ContextAsMap(persona),
                    ["evaluations"] = resolved.Evaluations,
                },
                ["received"] = new Dictionary<string, object?>
                {
                    ["source"] = resolved.Source,
                    ["model"] = resolved.Model,
                    ["judgeOn"] = resolved.JudgeOn,
                    ["flagEvaluations"] = resolved.Records,
                    ["appWork"] = FlagAppWork(resolved.Source, resolved.JudgeOn),
                    ["messages"] = new List<Dictionary<string, string>>
                    {
                        new() { ["role"] = "system", ["content"] = resolved.System.Trim() },
                        new() { ["role"] = "user", ["content"] = resolved.User.Trim() },
                    },
                },
            },
        };

        if (resolved.Missing.Count > 0)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "status",
                ["message"] =
                    $"Flag not found: {string.Join(", ", resolved.Missing)}. Using in-code defaults. " +
                    "Provision with rest/create-flags.sh.",
            };
        }

        var draft = "";
        await foreach (var (evt, text) in GenerateOllamaAsync(resolved.Model, messages, sw, metrics, ct))
        {
            if (evt.GetValueOrDefault("type") as string == "_complete")
            {
                draft = text ?? "";
                continue;
            }
            yield return evt;
        }

        if (resolved.JudgeOn)
        {
            yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "Scoring the draft…" };
            yield return EvalEvent("judge", JudgeKey());
            yield return await ScoreDraftAsync(
                persona, storiesText, draft, resolved.Source, resolved.Evaluations + 1, ct);
        }
        else
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "judge",
                ["source"] = resolved.Source,
                ["on"] = false,
                ["passed"] = null,
                ["score"] = null,
                ["evaluations"] = resolved.Evaluations,
            };
        }

        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?> { ["type"] = "done" };
    }

    private static string AsNonEmpty(object? value, string fallback)
    {
        var text = value as string;
        return string.IsNullOrWhiteSpace(text) ? fallback : text;
    }

    private sealed class AgentSetup
    {
        public LdAiCompletionConfig? Config;
        public EvalMeta? Meta;
        public string Provider = "";
        public string Model = "";
        public List<Dictionary<string, string>>? Messages;
        public ILdAiConfigTracker? Tracker;
        public string? Error;
    }

    /// <summary>
    /// LaunchDarkly: CompletionConfig substitutes {{ stories }} before the app sees the user message.
    /// https://launchdarkly.com/docs/home/agentcontrol/quickstart
    /// </summary>
    private static AgentSetup PrepareAgentControl(Persona persona, string storiesText)
    {
        var setup = new AgentSetup();
        try
        {
            var variables = new Dictionary<string, object> { ["stories"] = storiesText };
            setup.Config = RequireAiClient().CompletionConfig(
                ConfigKey(), BuildContext(persona), SkepticCompletionDefault(), variables);
            setup.Meta = EvaluationMeta(persona);
        }
        catch (Exception exc)
        {
            setup.Error = $"LaunchDarkly CompletionConfig failed: {exc.Message}";
            return setup;
        }

        if (!setup.Config.Enabled)
        {
            setup.Error =
                $"AgentControl config '{ConfigKey()}' is off / enabled=false. Run rest/create-original.sh.";
            return setup;
        }

        try
        {
            (setup.Provider, setup.Model) = ResolveRuntime(setup.Config.Model.Name, setup.Config.Provider.Name);
            setup.Messages = MessagesAsDicts(setup.Config.Messages);
            if (setup.Messages.Count == 0)
            {
                throw new InvalidOperationException("Served variation has no messages.");
            }
            setup.Tracker = setup.Config.CreateTracker();
        }
        catch (Exception exc)
        {
            setup.Error = exc.Message;
        }
        return setup;
    }

    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        List<Dictionary<string, object?>> tickerResults,
        string source,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        if (source is "flags" or "json")
        {
            var defaults = PersonaPrompts(persona);
            var records = new List<Dictionary<string, object?>>();
            var missing = new List<string>();
            var model = defaults.Model;
            var system = defaults.System;
            var user = defaults.User;
            var judgeOn = true;

            if (source == "flags")
            {
                var pairs = new (string Key, LdValue Fallback, object Display)[]
                {
                    (FlagModelKey, LdValue.Of(defaults.Model), defaults.Model),
                    (FlagSystemKey, LdValue.Of(defaults.System), defaults.System),
                    (FlagUserKey, LdValue.Of(defaults.User), defaults.User),
                    (FlagJudgeKey, LdValue.Of(true), true),
                };
                var hits = new List<FlagHit>();
                foreach (var pair in pairs)
                {
                    yield return EvalEvent("flag", pair.Key);
                    var hit = FlagDetail(pair.Key, persona, pair.Fallback, pair.Display);
                    hits.Add(hit);
                    records.Add(hit.Record);
                    if (hit.Missing) missing.Add(pair.Key);
                }
                model = AsNonEmpty(hits[0].Value, defaults.Model);
                system = AsNonEmpty(hits[1].Value, defaults.System);
                user = AsNonEmpty(hits[2].Value, defaults.User);
                judgeOn = hits[3].Value is bool on && on;
            }
            else
            {
                yield return EvalEvent("flag", FlagJsonKey);
                var fallback = LdValue.BuildObject()
                    .Add("model", defaults.Model)
                    .Add("systemPrompt", defaults.System)
                    .Add("userPrompt", defaults.User)
                    .Add("judge", true)
                    .Build();
                var display = new Dictionary<string, object?>
                {
                    ["model"] = defaults.Model,
                    ["systemPrompt"] = defaults.System,
                    ["userPrompt"] = defaults.User,
                    ["judge"] = true,
                };
                var hit = FlagDetail(FlagJsonKey, persona, fallback, display);
                records.Add(hit.Record);
                if (hit.Missing) missing.Add(FlagJsonKey);
                var body = hit.Value as Dictionary<string, object?> ?? display;
                model = AsNonEmpty(body.GetValueOrDefault("model"), defaults.Model);
                system = AsNonEmpty(body.GetValueOrDefault("systemPrompt"), defaults.System);
                user = AsNonEmpty(body.GetValueOrDefault("userPrompt"), defaults.User);
                judgeOn = body.GetValueOrDefault("judge") is not false;
            }

            await foreach (var evt in GenerateFromResolvedAsync(persona, tickerResults, new Resolved
            {
                Source = source,
                Model = model,
                System = system,
                User = user,
                JudgeOn = judgeOn,
                Evaluations = source == "flags" ? 4 : 1,
                JudgeSurface = source == "flags" ? "boolean-flag" : "json-flag",
                Missing = missing,
                Records = records,
            }, ct))
            {
                yield return evt;
            }
            yield break;
        }

        var storiesText = FormatStories(tickerResults);
        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();
        yield return EvalEvent("agent config", ConfigKey());

        var setup = PrepareAgentControl(persona, storiesText);
        if (setup.Error != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = setup.Error };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var config = setup.Config!;
        var servedMeta = setup.Meta!;
        var provider = setup.Provider;
        var modelName = setup.Model;
        var messages = setup.Messages!;
        var tracker = setup.Tracker;
        var names = ToolNames(config);
        var reasonKind = servedMeta.Reason != null && servedMeta.Reason.TryGetValue("kind", out var kind)
            ? kind
            : null;
        Console.WriteLine(
            $"[generate] {persona.Name}: variation='{servedMeta.VariationKey}' reason='{reasonKind}'");

        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = new Dictionary<string, object?>
            {
                ["id"] = persona.Id,
                ["name"] = persona.Name,
                ["profile"] = persona.Profile,
            },
            ["input"] = UserMessageText(messages) is { Length: > 0 } input ? input : storiesText,
            ["provider"] = provider,
            ["model"] = modelName,
            ["mode"] = "launchdarkly",
            ["configKey"] = ConfigKey(),
            ["variationKey"] = servedMeta.VariationKey,
            ["fallback"] = false,
            ["stories"] = tickerResults,
            ["source"] = "original",
            ["systemPrompt"] = messages.FirstOrDefault(m => m.GetValueOrDefault("role") == "system")
                ?.GetValueOrDefault("content") ?? "",
            ["judgeOn"] = true,
            ["judgeSurface"] = "judge-config",
            ["evaluations"] = 1,
            ["ldTransaction"] = new Dictionary<string, object?>
            {
                ["sent"] = new Dictionary<string, object?>
                {
                    ["configKey"] = ConfigKey(),
                    ["context"] = ContextAsMap(persona),
                    ["variables"] = new Dictionary<string, object?> { ["stories"] = storiesText },
                    ["sdkDefault"] = new Dictionary<string, object?>
                    {
                        ["description"] =
                            "LdAiCompletionConfigDefault passed to CompletionConfig " +
                            "(concise-skeptic / Charlie shape; used if config key is missing).",
                        ["enabled"] = true,
                        ["model"] = DefaultOllamaModel(),
                        ["provider"] = "Custom",
                        ["messages"] = new List<Dictionary<string, string>>
                        {
                            new() { ["role"] = "system", ["content"] = ReadMessageFile("skeptic-system.txt").Trim() },
                            new() { ["role"] = "user", ["content"] = ReadMessageFile("skeptic-user.txt").Trim() },
                        },
                    },
                },
                ["received"] = new Dictionary<string, object?>
                {
                    ["fallback"] = false,
                    ["mode"] = "launchdarkly",
                    ["enabled"] = true,
                    ["configKey"] = ConfigKey(),
                    ["variationKey"] = servedMeta.VariationKey,
                    ["variationIndex"] = servedMeta.VariationIndex,
                    ["reason"] = servedMeta.Reason,
                    ["version"] = servedMeta.Version,
                    ["versionKey"] = servedMeta.VersionKey,
                    ["ldMode"] = servedMeta.Mode,
                    ["modelKey"] = servedMeta.ModelKey,
                    ["modelVersion"] = servedMeta.ModelVersion,
                    ["provider"] = provider,
                    ["model"] = modelName,
                    ["messages"] = messages,
                    ["tools"] = names,
                    ["appWork"] = AgentAppWork(),
                },
            },
        };

        if (servedMeta.Reason != null &&
            servedMeta.Reason.GetValueOrDefault("errorKind") as string == "FLAG_NOT_FOUND")
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "status",
                ["message"] =
                    $"Completion config '{ConfigKey()}' was not found. " +
                    "Using the in-code concise-skeptic default. Provision with rest/create-original.sh.",
            };
        }

        var draft = "";
        var failed = false;
        await foreach (var (evt, text) in GenerateOllamaAsync(modelName, messages, sw, metrics, ct))
        {
            if (evt.GetValueOrDefault("type") as string == "error") failed = true;
            if (evt.GetValueOrDefault("type") as string == "_complete")
            {
                draft = text ?? "";
                continue;
            }
            yield return evt;
        }

        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        if (failed) TrackGenerationError(tracker);
        else TrackGenerationSuccess(tracker, metrics);

        yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "Scoring the draft…" };
        yield return EvalEvent("judge", JudgeKey());
        var scored = await ScoreDraftAsync(persona, storiesText, draft, "original", 2, ct);
        yield return scored;
        foreach (var repair in RepairIfFailed(names, tracker, draft, scored))
        {
            yield return repair;
        }
        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?> { ["type"] = "done" };
    }
}
