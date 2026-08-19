using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;
using LaunchDarkly.Sdk.Server.Ai;
using LaunchDarkly.Sdk.Server.Ai.Adapters;
using LaunchDarkly.Sdk.Server.Ai.Config;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;
using LaunchDarkly.Sdk.Server.Ai.Tracking;

namespace AgentJudges;

/// <summary>
/// Domain logic for 24-agent-judges (no HTTP here).
///
/// =============================================================================
/// HOW TO READ THIS FILE
/// =============================================================================
///
/// Same equity-briefing product as 21, plus a <b>runtime judge gate</b>:
///
///   1. Data          Toby + Charlie personas
///   2. LaunchDarkly  CompletionConfig for drafts; JudgeConfig for each judge
///   3. Providers     Ollama stream for drafts; Ollama non-streaming JSON for judges
///   4. Generation    draft → both judges → optional one Charlie rewrite
///
/// LaunchDarkly insertion (read first):
///   GenerateStreamAsync() → LdAiClient.CompletionConfig(...) then JudgeConfig(...) per judge
///   Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
///   Keywords: Judges · custom judges · JudgeConfig · runtime gate
///
/// No CreateJudge — run Ollama yourself with format=json (same teaching gate as Node).
/// </summary>
public static class AgentCore
{
    /// <summary>Selectable demo identity — also the LaunchDarkly user context.</summary>
    public sealed record Persona(string Id, string Name, string Profile);

    public static readonly IReadOnlyList<Persona> Personas = new List<Persona>
    {
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
        new("conservative-charlie", "Conservative Charlie", "conservative"),
    };

    /// <summary>Rewrite target when either judge score is below the pass threshold.</summary>
    public static readonly Persona Charlie = Personas[1];

    private const string CannedStories =
        "No ticker stories loaded yet. Ask the user to click Get Stories.";

    private const string DefaultConfigKey = "equity-briefing-judged";
    private const string DefaultJudgeFidelityKey = "equity-briefing-source-fidelity";
    private const string DefaultJudgeDisciplineKey = "equity-briefing-recommendation-discipline";
    private const string DefaultOllamaModelName = "llama3.2:3b";
    private const double DefaultPassThreshold = 0.70;
    private const string JudgeJsonSuffix =
        "Respond with JSON {\"score\":0.0-1.0,\"reasoning\":\"...\"}.";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(180) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    public static string ConfigKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_AGENT_CONFIG_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultConfigKey : key;
    }

    public static string JudgeFidelityKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_JUDGE_FIDELITY_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultJudgeFidelityKey : key;
    }

    public static string JudgeDisciplineKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_JUDGE_DISCIPLINE_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultJudgeDisciplineKey : key;
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
    /// Initialize the shared LaunchDarkly clients once at process start.
    ///
    /// LaunchDarkly: server-side SDK + AI SDK for AgentControl completion + judge configs.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    public static void InitLaunchDarkly()
    {
        if (_aiClient != null) return;

        var sdkKey = (Environment.GetEnvironmentVariable("LD_SDK_KEY") ?? "").Trim();
        if (sdkKey.Length == 0)
        {
            throw new InvalidOperationException(
                "LD_SDK_KEY is required. Export a server-side SDK key for the " +
                "environment that targets equity-briefing-judged.");
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
    {
        if (_aiClient == null)
        {
            throw new InvalidOperationException(
                "LaunchDarkly AI client is not initialized. Call InitLaunchDarkly() first.");
        }
        return _aiClient;
    }

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

    /// <summary>
    /// SDK default when the completion config key is missing / unreachable
    /// (concise-skeptic / Charlie shape from rest/messages/skeptic-*.txt).
    ///
    /// LaunchDarkly: CompletionConfig default for evaluation.
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
    /// SDK default for a judge config key (system message + evaluation metric).
    ///
    /// LaunchDarkly: JudgeConfig default — prompts/model from LD when the key exists.
    /// https://launchdarkly.com/docs/home/agentcontrol/judges
    /// </summary>
    private static LdAiJudgeConfigDefault JudgeDefault(string systemFile, string metricKey) =>
        LdAiJudgeConfigDefault.New()
            .Enable()
            .SetModelName(DefaultOllamaModel())
            .SetModelProviderName("Custom")
            .SetEvaluationMetricKey(metricKey)
            .AddMessage(ReadMessageFile(systemFile).Trim(), LdAiConfigTypes.Role.System)
            .Build();

    private static string DefaultMetricForJudgeKey(string key)
    {
        if (key.Contains("fidelity", StringComparison.Ordinal)) return "$ld:ai:judge:source-fidelity";
        if (key.Contains("discipline", StringComparison.Ordinal)) return "$ld:ai:judge:recommendation-discipline";
        var suffix = key.Replace("equity-briefing-", "", StringComparison.Ordinal);
        if (suffix.Length == 0) suffix = "custom";
        return $"$ld:ai:judge:{suffix}";
    }

    /// <summary>
    /// Fetch model + messages from AgentControl (completion mode).
    ///
    /// LaunchDarkly: CompletionConfig evaluation with message variables.
    /// https://launchdarkly.com/docs/home/agentcontrol/quickstart
    /// </summary>
    private static LdAiCompletionConfig EvaluateCompletion(Persona persona, string storiesText)
    {
        var variables = new Dictionary<string, object> { ["stories"] = storiesText };
        return RequireAiClient().CompletionConfig(
            ConfigKey(), BuildContext(persona), SkepticCompletionDefault(), variables);
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

    /// <summary>
    /// Map served provider/model to a local caller (ollama).
    /// Custom / Ollama models use provider Custom and model id like llama3.2:3b.
    /// </summary>
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
            throw new InvalidOperationException(
                "AgentControl variation has no model name. " +
                "Check modelConfigKey on the served variation in LaunchDarkly.");
        }
        return ("ollama", model);
    }

    private static string JudgeInputText(string storiesText, List<string> tickers)
    {
        var tickerLine = tickers.Count > 0 ? $"Tickers: {string.Join(", ", tickers)}\n\n" : "";
        return tickerLine +
               "Task: Write a short equity briefing comparing the tickers using only the headlines below.\n\n" +
               $"HEADLINES:\n{storiesText}";
    }

    private static List<string> ExtractTickers(List<Dictionary<string, object?>>? tickerResults)
    {
        if (tickerResults == null) return new List<string>();
        return tickerResults
            .Select(r => (r.GetValueOrDefault("ticker") as string ?? "").Trim())
            .Where(t => t.Length > 0)
            .ToList();
    }

    private static Dictionary<string, object?> PersonaMap(Persona persona) => new()
    {
        ["id"] = persona.Id,
        ["name"] = persona.Name,
        ["profile"] = persona.Profile,
    };

    private static int EstimateTokens(string? text) => Math.Max(1, (text ?? "").Length / 4);

    private sealed class Metrics
    {
        public long? LatencyMs;
        public long? TtftMs;
        public int? PromptTokens;
        public int? CompletionTokens;
        public int? TotalTokens;
        public string? FinishReason;

        public Dictionary<string, object?> ToMap() => new()
        {
            ["latency_ms"] = LatencyMs,
            ["ttft_ms"] = TtftMs,
            ["prompt_tokens"] = PromptTokens,
            ["completion_tokens"] = CompletionTokens,
            ["total_tokens"] = TotalTokens,
            ["finish_reason"] = FinishReason,
        };
    }

    private static void FillTokenEstimates(
        List<Dictionary<string, string>> messages, string completion, Metrics metrics)
    {
        var prompt = string.Concat(messages.Select(m => m.GetValueOrDefault("content") ?? ""));
        metrics.PromptTokens = EstimateTokens(prompt);
        metrics.CompletionTokens = EstimateTokens(completion);
        metrics.TotalTokens = (metrics.PromptTokens ?? 0) + (metrics.CompletionTokens ?? 0);
    }

    private static async IAsyncEnumerable<string> OllamaStreamAsync(
        string model, List<Dictionary<string, string>> messages, [EnumeratorCancellation] CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var url = $"{host}/api/chat";

        using var request = new HttpRequestMessage(HttpMethod.Post, url)
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
                $"Ollama request failed ({host}, model={model}): {exc.Message}. " +
                "Is Ollama running, and does the model id match `ollama list`?", exc);
        }

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): HTTP {(int)response.StatusCode}. " +
                "Is Ollama running, and does the model id match `ollama list`?");
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

    /// <summary>
    /// Stream Ollama tokens. Kept as its own async iterator because C# disallows
    /// <c>yield return</c> inside a try block that has a catch clause.
    /// </summary>
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

    private static void TrackGenerationSuccess(ILdAiConfigTracker? tracker, Metrics metrics)
    {
        if (tracker == null) return;
        try
        {
            tracker.TrackSuccess();
            if (metrics.LatencyMs != null) tracker.TrackDuration(metrics.LatencyMs.Value);
            if (metrics.TtftMs != null) tracker.TrackTimeToFirstToken(metrics.TtftMs.Value);
            var total = metrics.TotalTokens ?? 0;
            var input = metrics.PromptTokens ?? 0;
            var output = metrics.CompletionTokens ?? 0;
            if (total != 0 || input != 0 || output != 0)
            {
                tracker.TrackTokens(new Usage(total, input, output));
            }
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
    /// Non-streaming Ollama chat with format=json for judge score + reasoning.
    /// Workaround for no CreateJudge in this teaching demo (same as Node).
    /// </summary>
    private static async Task<JsonElement> OllamaJudgeJsonAsync(
        string model, List<Dictionary<string, string>> messages, CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var url = $"{host}/api/chat";

        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { model, stream = false, format = "json", messages }),
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
    /// Run one judge: JudgeConfig from LD, then Ollama JSON score.
    ///
    /// LaunchDarkly: JudgeConfig — prompts/model from LD; gate runs locally via Ollama JSON.
    /// https://launchdarkly.com/docs/home/agentcontrol/judges
    /// </summary>
    private static async Task<Dictionary<string, object?>> RunOneJudgeAsync(
        string key, Persona persona, string inputText, string outputText, CancellationToken ct)
    {
        var metricDefault = DefaultMetricForJudgeKey(key);
        var systemFile = key.Contains("fidelity", StringComparison.Ordinal)
            ? "judge-source-fidelity-system.txt"
            : "judge-recommendation-discipline-system.txt";

        try
        {
            // LaunchDarkly: JudgeConfig evaluation (no CreateJudge).
            var config = RequireAiClient().JudgeConfig(
                key, BuildContext(persona), JudgeDefault(systemFile, metricDefault));

            var metric = string.IsNullOrWhiteSpace(config.EvaluationMetricKey)
                ? metricDefault
                : config.EvaluationMetricKey;

            if (!config.Enabled)
            {
                return new Dictionary<string, object?>
                {
                    ["key"] = key,
                    ["success"] = false,
                    ["error"] = "judge config disabled or unsupported (enabled=false)",
                    ["score"] = null,
                    ["reasoning"] = null,
                    ["metricKey"] = metric,
                    ["sampled"] = true,
                    ["passed"] = false,
                };
            }

            string model;
            try
            {
                var runtime = ResolveRuntime(config.Model.Name, config.Provider.Name);
                model = runtime.Model;
            }
            catch
            {
                model = DefaultOllamaModel();
            }
            if (string.IsNullOrWhiteSpace(model)) model = DefaultOllamaModel();

            var served = MessagesAsDicts(config.Messages);
            var system = SystemMessageText(served);
            if (system.Length == 0) system = ReadMessageFile(systemFile).Trim();
            if (!system.Contains("Respond with JSON", StringComparison.Ordinal))
            {
                system = $"{system}\n\n{JudgeJsonSuffix}";
            }

            var user =
                $"MESSAGE HISTORY:\n{inputText}\n\nRESPONSE TO EVALUATE:\n{outputText}";
            var messages = new List<Dictionary<string, string>>
            {
                new() { ["role"] = "system", ["content"] = system },
                new() { ["role"] = "user", ["content"] = user },
            };

            var parsed = await OllamaJudgeJsonAsync(model, messages, ct);
            double? score = null;
            if (parsed.TryGetProperty("score", out var scoreEl) &&
                scoreEl.ValueKind is JsonValueKind.Number)
            {
                score = scoreEl.GetDouble();
            }
            string? reasoning = null;
            if (parsed.TryGetProperty("reasoning", out var reasonEl) &&
                reasonEl.ValueKind == JsonValueKind.String)
            {
                reasoning = reasonEl.GetString();
            }

            var passed = score != null && score.Value >= PassThreshold();

            try
            {
                var tracker = config.CreateTracker();
                // JudgeResult(string metricKey, double score, bool sampled, bool success, string judgeConfigKey)
                tracker.TrackJudgeResult(new JudgeResult(
                    metric, score ?? 0.0, sampled: true, success: true, judgeConfigKey: key));
            }
            catch
            {
                // Best-effort Monitoring hook.
            }

            return new Dictionary<string, object?>
            {
                ["key"] = key,
                ["success"] = true,
                ["error"] = null,
                ["score"] = score,
                ["reasoning"] = reasoning,
                ["metricKey"] = metric,
                ["sampled"] = true,
                ["passed"] = passed,
            };
        }
        catch (Exception exc)
        {
            return new Dictionary<string, object?>
            {
                ["key"] = key,
                ["success"] = false,
                ["error"] = exc.Message,
                ["score"] = null,
                ["reasoning"] = null,
                ["metricKey"] = metricDefault,
                ["sampled"] = true,
                ["passed"] = false,
            };
        }
    }

    private static async Task<List<Dictionary<string, object?>>> RunJudgesAsync(
        Persona persona, string inputText, string draft, CancellationToken ct)
    {
        return new List<Dictionary<string, object?>>
        {
            await RunOneJudgeAsync(JudgeFidelityKey(), persona, inputText, draft, ct),
            await RunOneJudgeAsync(JudgeDisciplineKey(), persona, inputText, draft, ct),
        };
    }

    private static bool JudgesPassed(List<Dictionary<string, object?>> results)
        => results.All(r => r.GetValueOrDefault("passed") is true);

    /// <summary>
    /// Draft → decorate → judge → optional one Charlie rewrite.
    /// SSE extras vs 21: section, judges, rewrite_meta.
    /// </summary>
    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        List<Dictionary<string, object?>>? tickerResults,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        var storiesText = FormatStories(tickerResults);
        var tickers = ExtractTickers(tickerResults);
        var stories = tickerResults ?? new List<Dictionary<string, object?>>();
        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();
        var threshold = PassThreshold();

        LdAiCompletionConfig? config = null;
        Exception? evalError = null;
        try
        {
            // LaunchDarkly: evaluate completion config (model + messages).
            config = EvaluateCompletion(persona, storiesText);
        }
        catch (Exception exc)
        {
            evalError = exc;
        }

        if (evalError != null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"LaunchDarkly completionConfig failed: {evalError.Message}",
            };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        if (config is { Enabled: false })
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] =
                    $"AgentControl config '{ConfigKey()}' is off / enabled=false. Run rest/create-config.sh.",
            };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        string provider = "—";
        string model = "—";
        var messages = new List<Dictionary<string, string>>();
        ILdAiConfigTracker? tracker = null;
        Exception? setupError = null;
        try
        {
            var runtime = ResolveRuntime(config!.Model.Name, config.Provider.Name);
            provider = runtime.Provider;
            model = runtime.Model;
            messages = MessagesAsDicts(config.Messages);
            if (messages.Count == 0) throw new InvalidOperationException("Served variation has no messages.");
            tracker = config.CreateTracker();
        }
        catch (Exception exc)
        {
            setupError = exc;
        }

        if (setupError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = setupError.Message };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var promptPreview = UserMessageText(messages);
        if (promptPreview.Length == 0) promptPreview = storiesText;

        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = PersonaMap(persona),
            ["input"] = promptPreview,
            ["provider"] = provider,
            ["model"] = model,
            ["mode"] = "launchdarkly",
            ["configKey"] = ConfigKey(),
            ["judgeKeys"] = new[] { JudgeFidelityKey(), JudgeDisciplineKey() },
            ["passThreshold"] = threshold,
            ["stories"] = stories,
        };

        yield return new Dictionary<string, object?>
        {
            ["type"] = "section",
            ["title"] = $"Draft ({persona.Name})",
            ["kind"] = "draft",
        };

        var draftParts = new StringBuilder();
        var draftFailed = false;
        await foreach (var (evt, text) in GenerateOllamaAsync(model, messages, sw, metrics, ct))
        {
            if (evt.GetValueOrDefault("type") as string == "_complete")
            {
                if (text != null) draftParts.Clear().Append(text);
                continue;
            }
            if (evt.GetValueOrDefault("type") as string == "error")
            {
                draftFailed = true;
            }
            else if (evt.GetValueOrDefault("type") as string == "token")
            {
                draftParts.Append(evt.GetValueOrDefault("text") as string ?? "");
            }
            yield return evt;
        }

        if (draftFailed || metrics.FinishReason == "error")
        {
            TrackGenerationError(tracker);
            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        if (tracker != null)
        {
            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            TrackGenerationSuccess(tracker, metrics);
        }

        var draft = draftParts.ToString().Trim();
        yield return new Dictionary<string, object?>
        {
            ["type"] = "status",
            ["message"] = "Running judges (Source Fidelity + Recommendation Discipline)…",
        };

        List<Dictionary<string, object?>>? judgeResults = null;
        Exception? judgeError = null;
        try
        {
            judgeResults = await RunJudgesAsync(persona, JudgeInputText(storiesText, tickers), draft, ct);
        }
        catch (Exception exc)
        {
            judgeError = exc;
        }

        if (judgeError != null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"Judge evaluation failed: {judgeError.Message}",
            };
            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var passed = JudgesPassed(judgeResults!);
        yield return new Dictionary<string, object?>
        {
            ["type"] = "section",
            ["title"] = "Judge scores",
            ["kind"] = "judges",
        };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "judges",
            ["passed"] = passed,
            ["threshold"] = threshold,
            ["results"] = judgeResults,
        };

        if (passed)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "status",
                ["message"] = $"Both judges ≥ {threshold:F2} — no rewrite.",
            };
            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        yield return new Dictionary<string, object?>
        {
            ["type"] = "status",
            ["message"] = "Gate failed — rewriting once with Conservative Charlie…",
        };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "section",
            ["title"] = "Rewrite (Conservative Charlie)",
            ["kind"] = "rewrite",
        };

        var rewriteMetrics = new Metrics();
        var rewriteSw = Stopwatch.StartNew();
        Exception? rewriteError = null;
        string? cProvider = null;
        string? cModel = null;
        List<Dictionary<string, string>>? cMessages = null;
        ILdAiConfigTracker? cTracker = null;

        try
        {
            var charlieConfig = EvaluateCompletion(Charlie, storiesText);
            if (!charlieConfig.Enabled)
            {
                throw new InvalidOperationException("Charlie variation enabled=false; check targeting.");
            }
            var resolved = ResolveRuntime(charlieConfig.Model.Name, charlieConfig.Provider.Name);
            cProvider = resolved.Provider;
            cModel = resolved.Model;
            cMessages = MessagesAsDicts(charlieConfig.Messages);
            cTracker = charlieConfig.CreateTracker();
        }
        catch (Exception exc)
        {
            rewriteError = exc;
        }

        if (rewriteError != null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"Charlie rewrite failed: {rewriteError.Message}",
            };
        }
        else
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "rewrite_meta",
                ["persona"] = PersonaMap(Charlie),
                ["provider"] = cProvider,
                ["model"] = cModel,
            };

            await foreach (var (evt, _) in GenerateOllamaAsync(cModel!, cMessages!, rewriteSw, rewriteMetrics, ct))
            {
                if (evt.GetValueOrDefault("type") as string == "_complete") continue;
                yield return evt;
            }

            if (cTracker != null && rewriteMetrics.FinishReason != "error")
            {
                rewriteMetrics.LatencyMs = (long)rewriteSw.Elapsed.TotalMilliseconds;
                TrackGenerationSuccess(cTracker, rewriteMetrics);
            }
        }

        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "status",
            ["message"] = "Rewrite complete (one rewrite max; scores above are for the draft).",
        };
        yield return new Dictionary<string, object?> { ["type"] = "done" };
    }
}
