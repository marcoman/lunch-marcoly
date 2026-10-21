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

namespace AgentCompletionConfig;

/// <summary>
/// Domain logic for 21-agent-completion-config (no HTTP here).
///
/// =============================================================================
/// HOW TO READ THIS FILE
/// =============================================================================
///
/// Same product flow as 01-reference-agent, but at generate time LaunchDarkly
/// AgentControl supplies **model**, **system** message, and **user** message.
///
///   1. Data          Personas (UI labels + LD context key/name)
///   2. LaunchDarkly   Init server SDK + AI SDK; CompletionConfig evaluation
///   3. Providers      Route by served provider/model (Ollama Custom, …)
///   4. Generation     GenerateStreamAsync() — evaluate config, then stream LLM tokens
///
/// LaunchDarkly insertion point (read this first):
///   GenerateStreamAsync() → LdAiClient.CompletionConfig(...)
///   Docs: https://launchdarkly.com/docs/sdk/ai/dotnet
///   Keywords: AgentControl · completion config · AI SDK · message variables
///
/// Variables: the config user message includes {{ stories }}; we pass
/// { stories: &lt;formatted headlines&gt; } so LaunchDarkly substitutes at evaluate time.
/// </summary>
public static class AgentCore
{
    /// <summary>Selectable demo identity — also the LaunchDarkly user context.</summary>
    public sealed record Persona(string Id, string Name, string Profile, bool Anonymous);

    public static readonly IReadOnlyList<Persona> Personas = new List<Persona>
    {
        new("conservative-charlie", "Conservative Charlie", "conservative", false),
        new("neutral-nancy", "Neutral Nancy", "neutral", false),
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker", false),
        // No name targeting — anonymous context falls through to baseline-analyst.
        new("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
    };

    private const string CannedStories = "No ticker stories loaded yet. Ask the user to click Get Stories.";

    // LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
    // https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion
    private const string DefaultConfigKey = "equity-briefing-completion";
    private const string DefaultOllamaModelName = "llama3.2:3b";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(120) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    public static string ConfigKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_AGENT_CONFIG_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultConfigKey : key;
    }

    public static string DefaultOllamaModel()
    {
        var model = (Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "").Trim();
        return model.Length == 0 ? DefaultOllamaModelName : model;
    }

    /// <summary>
    /// Initialize the shared LaunchDarkly clients once at process start.
    ///
    /// LaunchDarkly: server-side SDK + AI SDK for AgentControl completion configs.
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
                "environment that targets equity-briefing-completion.");
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
            throw new InvalidOperationException("LaunchDarkly AI client is not initialized. Call InitLaunchDarkly() first.");
        }
        return _aiClient;
    }

    private static LdClient RequireLdClient()
    {
        if (_ldClient == null)
        {
            throw new InvalidOperationException("LaunchDarkly client is not initialized. Call InitLaunchDarkly() first.");
        }
        return _ldClient;
    }

    /// <summary>
    /// Build the LD evaluation context for this persona.
    ///
    /// Named personas: user key + name (name targeting matches Charlie/Nancy/Toby).
    /// Anonymous Amelia: fixed key, anonymous=true — not indexed as a known user;
    /// name rules do not match → fallthrough (baseline-analyst).
    /// https://launchdarkly.com/docs/sdk/features/anonymous
    /// </summary>
    public static Context BuildContext(Persona persona)
    {
        var builder = Context.Builder(persona.Id).Name(persona.Name);
        if (persona.Anonymous) builder.Anonymous(true);
        return builder.Build();
    }

    private static Dictionary<string, object?> ContextAsMap(Persona persona)
    {
        var map = new Dictionary<string, object?>
        {
            ["kind"] = "user",
            ["key"] = persona.Id,
            ["name"] = persona.Name,
        };
        if (persona.Anonymous) map["anonymous"] = true;
        return map;
    }

    private static string BaselineMessagesDir() => Path.Combine(YahooNews.ExampleRoot(), "rest", "messages");

    private static string ReadMessageFile(string name)
    {
        var path = Path.Combine(BaselineMessagesDir(), name);
        try
        {
            return File.ReadAllText(path);
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException($"Could not read baseline message file {path}: {exc.Message}", exc);
        }
    }

    /// <summary>In-code baseline system prompt (same text as rest/messages/baseline-system.txt).</summary>
    public static string BaselineSystemPrompt() => ReadMessageFile("baseline-system.txt").Trim();

    /// <summary>User prompt template with {{ stories }} (rest/messages/baseline-user.txt).</summary>
    public static string BaselineUserTemplate() => ReadMessageFile("baseline-user.txt").Trim();

    /// <summary>Fill {{ stories }} locally when using the code baseline fallback.</summary>
    private static string RenderBaselineUser(string storiesText)
        => BaselineUserTemplate().Replace("{{ stories }}", storiesText).Replace("{{stories}}", storiesText);

    /// <summary>Chat messages for the in-code baseline-analyst fallback.</summary>
    private static List<Dictionary<string, string>> BaselineMessages(string storiesText) => new()
    {
        new() { ["role"] = "system", ["content"] = BaselineSystemPrompt() },
        new() { ["role"] = "user", ["content"] = RenderBaselineUser(storiesText) },
    };

    /// <summary>
    /// SDK default (typed) passed to <c>LdAiClient.CompletionConfig</c> when the config key is
    /// missing / unreachable. Also documents the intended offline shape. When the config exists
    /// but is turned off, LaunchDarkly still returns the disabled variation (enabled=false) —
    /// see GenerateStreamAsync() for the app-level fallback.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    private static LdAiCompletionConfigDefault BaselineCompletionDefault() =>
        LdAiCompletionConfigDefault.New()
            .Enable()
            .SetModelName(DefaultOllamaModel())
            .SetModelProviderName("Custom")
            .AddMessage(BaselineSystemPrompt(), LdAiConfigTypes.Role.System)
            .AddMessage(BaselineUserTemplate(), LdAiConfigTypes.Role.User)
            .Build();

    /// <summary>
    /// Raw LdValue mirror of <see cref="BaselineCompletionDefault"/>, used only as the default
    /// for the plain server SDK's <c>JsonVariationDetail</c> call in <see cref="EvaluationMeta"/>
    /// (the typed AI config default above can't be reused there — its JSON encoding is internal).
    /// </summary>
    private static LdValue BaselineCompletionDefaultLdValue()
    {
        var messages = LdValue.ArrayOf(
            LdValue.ObjectFrom(new Dictionary<string, LdValue>
            {
                ["role"] = LdValue.Of("system"),
                ["content"] = LdValue.Of(BaselineSystemPrompt()),
            }),
            LdValue.ObjectFrom(new Dictionary<string, LdValue>
            {
                ["role"] = LdValue.Of("user"),
                ["content"] = LdValue.Of(BaselineUserTemplate()),
            }));

        return LdValue.ObjectFrom(new Dictionary<string, LdValue>
        {
            ["enabled"] = LdValue.Of(true),
            ["model"] = LdValue.ObjectFrom(new Dictionary<string, LdValue> { ["name"] = LdValue.Of(DefaultOllamaModel()) }),
            ["provider"] = LdValue.ObjectFrom(new Dictionary<string, LdValue> { ["name"] = LdValue.Of("Custom") }),
            ["messages"] = messages,
        });
    }

    private static string FormatStories(List<Dictionary<string, object?>>? tickerResults)
        => tickerResults is { Count: > 0 } ? YahooNews.FormatStoriesForPrompt(tickerResults) : CannedStories;

    /// <summary>
    /// Fetch model + messages from AgentControl (completion mode).
    ///
    /// LaunchDarkly capability: CompletionConfig evaluation with message variables.
    /// https://launchdarkly.com/docs/home/agentcontrol/quickstart
    /// </summary>
    private static LdAiCompletionConfig EvaluateCompletion(Persona persona, string storiesText)
    {
        var variables = new Dictionary<string, object> { ["stories"] = storiesText };
        return RequireAiClient().CompletionConfig(ConfigKey(), BuildContext(persona), BaselineCompletionDefault(), variables);
    }

    private sealed class EvalMeta
    {
        public string? VariationKey;
        public int? Version;
        public string? VersionKey;
        public string? Mode;
        public string? ModelKey;
        public string? ModelVersion;
        public bool? EnabledMeta;
        public int? VariationIndex;
        public Dictionary<string, object?>? Reason;
    }

    private static string? LdString(LdValue value)
    {
        if (value.IsNull) return null;
        return value.Type == LdValueType.String ? value.AsString : value.ToString();
    }

    private static string? NullIfEmpty(string? value) => string.IsNullOrEmpty(value) ? null : value;

    private static Dictionary<string, object?> ReasonAsMap(EvaluationReason reason)
    {
        var map = new Dictionary<string, object?> { ["kind"] = reason.Kind.ToString() };
        if (reason.Kind == EvaluationReasonKind.RuleMatch)
        {
            map["ruleIndex"] = reason.RuleIndex;
            map["ruleId"] = reason.RuleId;
        }
        if (reason.Kind == EvaluationReasonKind.PrerequisiteFailed)
        {
            map["prerequisiteKey"] = reason.PrerequisiteKey;
        }
        if (reason.Kind == EvaluationReasonKind.Error && reason.ErrorKind != null)
        {
            map["errorKind"] = reason.ErrorKind.Value.ToString();
        }
        if (reason.InExperiment)
        {
            map["inExperiment"] = true;
        }
        return map;
    }

    /// <summary>
    /// Metadata for the served variation (public SDK: JsonVariationDetail).
    ///
    /// The typed AI config exposes model/messages/provider/enabled, but not variationKey —
    /// that's internal on <c>LdAiConfig</c>. This mirrors the Node/Java ports: evaluate the
    /// same config key a second time with the plain server SDK to read <c>_ldMeta</c>.
    /// https://launchdarkly.com/docs/sdk/features/evaluation-reasons
    /// </summary>
    private static EvalMeta EvaluationMeta(Persona persona)
    {
        var detail = RequireLdClient().JsonVariationDetail(ConfigKey(), BuildContext(persona), BaselineCompletionDefaultLdValue());
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
            EnabledMeta = meta.IsNull || meta.Get("enabled").IsNull ? null : meta.Get("enabled").AsBool,
            VariationIndex = detail.VariationIndex,
            Reason = ReasonAsMap(detail.Reason),
        };
    }

    private static void LogServedVariation(Persona persona, EvalMeta? meta)
    {
        if (meta == null)
        {
            Console.WriteLine($"[generate] {persona.Name}: variation=(unknown)");
            return;
        }
        var key = meta.VariationKey ?? "(none)";
        var reasonKind = meta.Reason != null && meta.Reason.TryGetValue("kind", out var k) ? k : null;
        Console.WriteLine($"[generate] {persona.Name}: variation='{key}' reason='{reasonKind}'");
    }

    private static Dictionary<string, object?> BuildLdTransaction(
        Persona persona,
        string storiesText,
        string configKeyValue,
        bool fallback,
        string mode,
        string provider,
        string model,
        List<Dictionary<string, string>> messages,
        EvalMeta? servedMeta,
        bool enabled)
    {
        var sdkDefault = new Dictionary<string, object?>
        {
            ["description"] =
                "LdAiCompletionConfigDefault passed to CompletionConfig " +
                "(baseline-analyst shape; used if config key is missing).",
            ["enabled"] = true,
            ["model"] = DefaultOllamaModel(),
            ["provider"] = "Custom",
            ["messages"] = new List<Dictionary<string, string>>
            {
                new() { ["role"] = "system", ["content"] = BaselineSystemPrompt() },
                new() { ["role"] = "user", ["content"] = BaselineUserTemplate() },
            },
        };

        var sent = new Dictionary<string, object?>
        {
            ["configKey"] = configKeyValue,
            ["context"] = ContextAsMap(persona),
            ["variables"] = new Dictionary<string, object?> { ["stories"] = storiesText },
            ["sdkDefault"] = sdkDefault,
        };

        var received = new Dictionary<string, object?>
        {
            ["fallback"] = fallback,
            ["mode"] = mode,
            ["enabled"] = enabled,
            ["configKey"] = configKeyValue,
            ["variationKey"] = servedMeta?.VariationKey,
            ["variationIndex"] = servedMeta?.VariationIndex,
            ["reason"] = servedMeta?.Reason,
            ["version"] = servedMeta?.Version,
            ["versionKey"] = servedMeta?.VersionKey,
            ["ldMode"] = servedMeta?.Mode,
            ["modelKey"] = servedMeta?.ModelKey,
            ["modelVersion"] = servedMeta?.ModelVersion,
            ["provider"] = provider,
            ["model"] = model,
            ["messages"] = messages,
        };

        return new Dictionary<string, object?> { ["sent"] = sent, ["received"] = received };
    }

    private static List<Dictionary<string, string>> MessagesAsDicts(LdAiCompletionConfig config)
    {
        var list = new List<Dictionary<string, string>>();
        foreach (var m in config.Messages)
        {
            list.Add(new Dictionary<string, string> { ["role"] = m.Role.ToString().ToLowerInvariant(), ["content"] = m.Content ?? "" });
        }
        return list;
    }

    private static string UserMessageText(List<Dictionary<string, string>> messages)
        => messages.FirstOrDefault(m => m.GetValueOrDefault("role") == "user")?.GetValueOrDefault("content") ?? "";

    private static string SystemMessageText(List<Dictionary<string, string>> messages)
        => messages.FirstOrDefault(m => m.GetValueOrDefault("role") == "system")?.GetValueOrDefault("content") ?? "";

    private static string SystemPromptPreview(List<Dictionary<string, string>> messages, int maxChars = 40)
    {
        var text = SystemMessageText(messages).Trim();
        if (text.Length == 0) return "(none)";
        var firstLine = text.Split('\n', '\r')[0].Trim();
        return firstLine.Length > maxChars ? firstLine[..(maxChars - 1)] + "…" : firstLine;
    }

    private static void LogSystemPromptSource(string source, List<Dictionary<string, string>> messages, Persona persona)
        => Console.WriteLine($"[generate] {persona.Name}: system prompt from {source}: '{SystemPromptPreview(messages)}'");

    /// <summary>
    /// Map served provider/model to a local caller (ollama).
    ///
    /// Custom / Ollama models from rest/create-model-config.sh use provider Custom
    /// and model id llama3.2:3b → call local Ollama.
    /// </summary>
    private static (string Provider, string Model) ResolveRuntime(string? modelName, string? providerName)
    {
        var model = modelName ?? "";
        var pl = (providerName ?? "").Trim().ToLowerInvariant();

        if (pl == "custom" || pl == "ollama" || model.Contains(':'))
        {
            return ("ollama", model);
        }
        if (pl == "bedrock" || model.StartsWith("us.") || model.StartsWith("amazon.") ||
            model.StartsWith("anthropic.") || model.StartsWith("meta."))
        {
            return ("bedrock", model);
        }
        if (string.IsNullOrWhiteSpace(model))
        {
            throw new InvalidOperationException(
                "AgentControl variation has no model name. " +
                "Check modelConfigKey on the served variation in LaunchDarkly.");
        }
        return ("ollama", model);
    }

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

    private static void FillTokenEstimates(List<Dictionary<string, string>> messages, string completion, Metrics metrics)
    {
        var prompt = string.Concat(messages.Select(m => m.GetValueOrDefault("content") ?? ""));
        metrics.PromptTokens = EstimateTokens(prompt);
        metrics.CompletionTokens = EstimateTokens(completion);
        metrics.TotalTokens = (metrics.PromptTokens ?? 0) + (metrics.CompletionTokens ?? 0);
    }

    private static Dictionary<string, object?> PersonaMap(Persona persona) => new()
    {
        ["id"] = persona.Id,
        ["name"] = persona.Name,
        ["profile"] = persona.Profile,
        ["anonymous"] = persona.Anonymous,
    };

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
                "Is Ollama running, and does the AgentControl model id match `ollama list`?", exc);
        }

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): HTTP {(int)response.StatusCode}. " +
                "Is Ollama running, and does the AgentControl model id match `ollama list`?");
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

            if (root.TryGetProperty("done", out var doneEl) && doneEl.ValueKind == JsonValueKind.True) yield break;
        }
    }

    /// <summary>
    /// Stream tokens from Ollama, updating <paramref name="metrics"/> in place and yielding
    /// "token"/"error" events. Kept as its own async iterator (rather than inlined in
    /// GenerateStreamAsync) because C# disallows `yield return` inside a try block that has a
    /// catch clause — the inner try/catch below only ever *sets* a local, it never yields.
    /// </summary>
    private static async IAsyncEnumerable<Dictionary<string, object?>> GenerateOllamaAsync(
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
                    yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = error.Message };
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
                yield return new Dictionary<string, object?> { ["type"] = "token", ["text"] = chunk };
            }
        }
        finally
        {
            await enumerator.DisposeAsync();
        }

        metrics.FinishReason = "stop";
        FillTokenEstimates(messages, textParts.ToString(), metrics);
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
            // Metrics are best-effort; never fail the stream for tracker errors.
        }
    }

    private static void TrackGenerationError(ILdAiConfigTracker? tracker)
    {
        if (tracker == null) return;
        try
        {
            tracker.TrackError();
        }
        catch
        {
            // Metrics are best-effort; never fail the stream for tracker errors.
        }
    }

    /// <summary>
    /// Evaluate AgentControl, then stream tokens from the served model.
    ///
    /// Event contract matches 01-reference-agent (meta / token / error / metrics / done).
    ///
    /// When the AgentControl config is disabled (or returns enabled=false), fall back to the
    /// in-code baseline-analyst prompts + local Ollama model — same text as rest/messages/baseline-*.txt.
    /// </summary>
    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        List<Dictionary<string, object?>>? tickerResults,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        var storiesText = FormatStories(tickerResults);
        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();
        var stories = tickerResults ?? new List<Dictionary<string, object?>>();

        var usingFallback = false;
        LdAiCompletionConfig? config = null;
        EvalMeta? servedMeta = null;
        string? fallbackReason = null;

        try
        {
            // LaunchDarkly: evaluate completion config (model + messages).
            config = EvaluateCompletion(persona, storiesText);
            servedMeta = EvaluationMeta(persona);
        }
        catch (Exception exc)
        {
            usingFallback = true;
            config = null;
            servedMeta = null;
            fallbackReason = $"LaunchDarkly evaluation failed ({exc.Message}); using code baseline.";
        }

        if (!usingFallback && config is { Enabled: false })
        {
            usingFallback = true;
            fallbackReason = $"AgentControl config '{ConfigKey()}' is off / enabled=false; using code baseline-analyst.";
        }

        if (usingFallback)
        {
            var messages = BaselineMessages(storiesText);
            const string provider = "ollama";
            var model = DefaultOllamaModel();
            const string mode = "baseline-fallback";

            Console.WriteLine($"[generate] {persona.Name}: variation='code-baseline' reason='FALLBACK'");
            LogSystemPromptSource("code baseline (AgentControl off)", messages, persona);
            var promptPreview = UserMessageText(messages);
            if (promptPreview.Length == 0) promptPreview = storiesText;

            yield return new Dictionary<string, object?>
            {
                ["type"] = "meta",
                ["persona"] = PersonaMap(persona),
                ["input"] = promptPreview,
                ["provider"] = provider,
                ["model"] = $"{model} (code baseline)",
                ["mode"] = mode,
                ["configKey"] = ConfigKey(),
                ["fallback"] = true,
                ["stories"] = stories,
                ["ldTransaction"] = BuildLdTransaction(
                    persona, storiesText, ConfigKey(), true, mode, provider,
                    $"{model} (code baseline)", messages, servedMeta, config?.Enabled ?? false),
            };

            if (fallbackReason != null)
            {
                yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = fallbackReason };
            }

            await foreach (var evt in GenerateOllamaAsync(model, messages, sw, metrics, ct))
            {
                yield return evt;
            }

            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        string provider2 = "—";
        string model2 = "—";
        var messages2 = new List<Dictionary<string, string>>();
        ILdAiConfigTracker? tracker = null;
        Exception? setupError = null;
        try
        {
            var runtime = ResolveRuntime(config!.Model.Name, config.Provider.Name);
            provider2 = runtime.Provider;
            model2 = runtime.Model;
            messages2 = MessagesAsDicts(config);
            if (messages2.Count == 0) throw new InvalidOperationException("Served variation has no messages.");
            tracker = config.CreateTracker();
        }
        catch (Exception exc)
        {
            setupError = exc;
        }

        if (setupError != null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "meta",
                ["persona"] = PersonaMap(persona),
                ["input"] = storiesText,
                ["provider"] = "—",
                ["model"] = "—",
                ["mode"] = "launchdarkly",
                ["configKey"] = ConfigKey(),
                ["stories"] = stories,
            };
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = setupError.Message };
            metrics.FinishReason = "error";
            metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
            yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        LogServedVariation(persona, servedMeta);
        LogSystemPromptSource($"LaunchDarkly ({ConfigKey()})", messages2, persona);
        var promptPreview2 = UserMessageText(messages2);
        if (promptPreview2.Length == 0) promptPreview2 = storiesText;

        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = PersonaMap(persona),
            ["input"] = promptPreview2,
            ["provider"] = provider2,
            ["model"] = model2,
            ["mode"] = "launchdarkly",
            ["configKey"] = ConfigKey(),
            ["variationKey"] = servedMeta?.VariationKey,
            ["fallback"] = false,
            ["stories"] = stories,
            ["ldTransaction"] = BuildLdTransaction(
                persona, storiesText, ConfigKey(), false, "launchdarkly", provider2, model2,
                messages2, servedMeta, config!.Enabled),
        };

        if (provider2 == "ollama")
        {
            await foreach (var evt in GenerateOllamaAsync(model2, messages2, sw, metrics, ct))
            {
                yield return evt;
            }
        }
        else if (provider2 == "bedrock")
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] =
                    "Bedrock is not wired in the .NET example. " +
                    "Use an Ollama / Custom model on the variation, or run the Python web app for Bedrock.",
            };
            metrics.FinishReason = "error";
        }
        else
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"Unsupported runtime provider '{provider2}'.",
            };
            metrics.FinishReason = "error";
        }

        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        if (metrics.FinishReason == "error")
        {
            TrackGenerationError(tracker);
        }
        else
        {
            TrackGenerationSuccess(tracker, metrics);
        }

        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?> { ["type"] = "done" };
    }
}
