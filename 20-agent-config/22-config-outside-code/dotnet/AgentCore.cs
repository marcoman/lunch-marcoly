using System.Diagnostics;
using System.Text;
using System.Text.Json.Nodes;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;
using LaunchDarkly.Sdk.Server.Ai;
using LaunchDarkly.Sdk.Server.Ai.Adapters;
using LaunchDarkly.Sdk.Server.Ai.Config;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;
using LaunchDarkly.Sdk.Server.Ai.Tracking;

namespace ConfigOutsideCode;

/// <summary>
/// Domain logic for 22-config-outside-code (no HTTP here).
///
/// =============================================================================
/// HOW TO READ THIS FILE
/// =============================================================================
///
/// Teaching focus: AgentControl completion config **outside code**, with
/// <c>TrackMetricsOf</c> + thumbs feedback as the headline (Monitoring tab) —
/// the .NET twin of the Node/Python examples in this series.
///
///   1. Data          Best Betty → Anthropic; Anonymous Amelia → Ollama
///   2. LaunchDarkly   <see cref="LdAiClient.CompletionConfig"/> evaluation of the AI config key
///   3. Providers      Ollama (default) or Anthropic (Best Betty)
///   4. Generation     GenerateStreamAsync() — evaluate, TrackMetricsOf, mint feedback token
///
/// LaunchDarkly insertion points:
///   InitLaunchDarkly()  → LdClient + LdAiClient(LdClientAdapter)
///   EvaluateCompletion() → aiClient.CompletionConfig(configKey, context, fallback, variables)
///   GenerateStreamAsync() → tracker.TrackMetricsOf(extractor, providerCall)
///   SubmitFeedback()    → aiClient.CreateTracker(resumptionToken, context).TrackFeedback(...)
///
/// Keywords: AgentControl · completion config · AI metrics · feedback
/// Docs:
///   https://launchdarkly.com/docs/sdk/ai/dotnet
///   https://launchdarkly.com/docs/home/agentcontrol/quickstart
///   https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs
/// </summary>
public static class AgentCore
{
    public sealed record Persona(string Id, string Name, string Profile, bool Anonymous);

    /// <summary>A single chat message. Plain app-level type — not the SDK's LdAiConfigTypes.Message,
    /// whose constructor is internal to the AI SDK package.</summary>
    public sealed record ChatMessage(string Role, string Content);

    public static readonly IReadOnlyList<Persona> Personas = new[]
    {
        // Best Betty → tracked-anthropic (Claude). Anonymous Amelia → tracked-ollama (fallthrough).
        new Persona("best-betty", "Best Betty", "best", false),
        new Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
    };

    private const string CannedStories = "No ticker stories loaded yet. Ask the user to click Get Stories.";

    // LaunchDarkly: ai-config key=equity-briefing-tracked-completion name="Equity briefing tracked completion" mode=completion
    // https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tracked-completion
    private const string DefaultConfigKey = "equity-briefing-tracked-completion";
    private const string DefaultOllamaModelName = "llama3.2:1b";
    private const string DefaultAnthropicModel = "claude-sonnet-5";

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(120) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    public static Persona? PersonaById(string personaId) =>
        Personas.FirstOrDefault(p => p.Id == personaId);

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
    /// Initialize the shared LaunchDarkly server SDK + AI SDK once at process start.
    ///
    /// LaunchDarkly: LdClient (server-side SDK), wrapped by LdAiClient (AI SDK).
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    public static void InitLaunchDarkly()
    {
        if (_aiClient != null) return;
        var sdkKey = (Environment.GetEnvironmentVariable("LD_SDK_KEY") ?? "").Trim();
        if (sdkKey.Length == 0)
        {
            throw new InvalidOperationException(
                $"LD_SDK_KEY is required. Export a server-side SDK key for the environment that targets {DefaultConfigKey}.");
        }

        var config = Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(10)).Build();
        var ldClient = new LdClient(config);
        if (!ldClient.Initialized)
        {
            ldClient.Dispose();
            throw new InvalidOperationException(
                "LaunchDarkly client failed to initialize within start wait. " +
                "Check LD_SDK_KEY and network access to LaunchDarkly.");
        }

        _ldClient = ldClient;
        _aiClient = new LdAiClient(new LdClientAdapter(ldClient));
    }

    private static LdAiClient RequireAiClient() =>
        _aiClient ?? throw new InvalidOperationException("LaunchDarkly AI client not initialized.");

    /// <summary>
    /// Build the LD evaluation context for this persona.
    ///
    /// Best Betty: named user (name targeting → tracked-anthropic).
    /// Anonymous Amelia: fixed key + anonymous=true — not indexed as a known user;
    /// name rules do not match → fallthrough (tracked-ollama).
    /// https://launchdarkly.com/docs/sdk/features/anonymous
    /// </summary>
    public static Context BuildContext(Persona persona) =>
        Context.Builder(persona.Id).Name(persona.Name).Anonymous(persona.Anonymous).Build();

    private static string ReadMessageFile(string name) =>
        File.ReadAllText(Path.Combine(YahooNews.ExampleRoot(), "rest", "messages", name)).Trim();

    /// <summary>In-code baseline system prompt (same text as rest/messages/baseline-system.txt).</summary>
    public static string BaselineSystemPrompt() => ReadMessageFile("baseline-system.txt");

    /// <summary>User prompt template with {{ stories }} (rest/messages/baseline-user.txt).</summary>
    public static string BaselineUserTemplate() => ReadMessageFile("baseline-user.txt");

    /// <summary>Fill {{ stories }} locally when using the code baseline fallback.</summary>
    public static string RenderBaselineUser(string storiesText) =>
        BaselineUserTemplate().Replace("{{ stories }}", storiesText).Replace("{{stories}}", storiesText);

    /// <summary>Chat messages for the in-code baseline-analyst fallback.</summary>
    public static List<ChatMessage> BaselineMessages(string storiesText) => new()
    {
        new ChatMessage("system", BaselineSystemPrompt()),
        new ChatMessage("user", RenderBaselineUser(storiesText)),
    };

    /// <summary>
    /// SDK default when the config key is missing / unreachable (baseline-analyst shape).
    ///
    /// When the config exists but is turned off, LaunchDarkly still returns a
    /// disabled variation (config.Enabled == false) — see GenerateStreamAsync().
    /// </summary>
    private static LdAiCompletionConfigDefault BaselineCompletionDefault() =>
        LdAiCompletionConfigDefault.New()
            .Enable()
            .SetModelName(DefaultOllamaModel())
            .SetModelProviderName("Custom")
            .AddMessage(BaselineSystemPrompt(), LdAiConfigTypes.Role.System)
            .AddMessage(BaselineUserTemplate(), LdAiConfigTypes.Role.User)
            .Build();

    private static string FormatStories(IReadOnlyList<JsonNode?> tickerResults) =>
        tickerResults.Count == 0 ? CannedStories : YahooNews.FormatStoriesForPrompt(tickerResults);

    /// <summary>
    /// Evaluate AgentControl completion config.
    ///
    /// LaunchDarkly: <c>LdAiClient.CompletionConfig</c> — the same evaluation the
    /// Node/Python AI SDKs perform via `completionConfig` / `completion_config`.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    private static LdAiCompletionConfig EvaluateCompletion(Persona persona, string storiesText) =>
        RequireAiClient().CompletionConfig(
            ConfigKey(),
            BuildContext(persona),
            BaselineCompletionDefault(),
            new Dictionary<string, object> { ["stories"] = storiesText });

    private static List<ChatMessage> MessagesAsList(LdAiCompletionConfig config) =>
        config.Messages.Select(m => new ChatMessage(m.Role.ToString().ToLowerInvariant(), m.Content)).ToList();

    private static string UserMessageText(List<ChatMessage> messages) =>
        messages.LastOrDefault(m => m.Role == "user")?.Content ?? "";

    private static string FirstNonEmpty(string a, string b) => string.IsNullOrEmpty(a) ? b : a;

    private static (string Provider, string Model) ResolveRuntime(LdAiCompletionConfig config)
    {
        var model = config.Model.Name;
        var providerName = config.Provider.Name.ToLowerInvariant();

        if (providerName == "anthropic" || model.StartsWith("claude-", StringComparison.Ordinal))
        {
            return ("anthropic", model.Length == 0 ? DefaultAnthropicModel : model);
        }
        if (providerName == "custom" || providerName == "ollama" || model.Contains(':'))
        {
            return ("ollama", model.Length == 0 ? DefaultOllamaModel() : model);
        }
        if (model.Length == 0)
        {
            throw new InvalidOperationException("AgentControl variation has no model name.");
        }
        return ("ollama", model);
    }

    private static int EstimateTokens(string? text) => Math.Max(1, (text ?? "").Length / 4);

    private static IEnumerable<string> Chunk(string text, int size)
    {
        for (var i = 0; i < text.Length; i += size)
        {
            yield return text.Substring(i, Math.Min(size, text.Length - i));
        }
    }

    private static string Truncate(string text, int max) => text.Length <= max ? text : text[..max];

    private sealed record ProviderResult(string Text, int InputTokens, int OutputTokens);

    private static async Task<ProviderResult> OllamaCompleteAsync(string model, List<ChatMessage> messages)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var payload = new JsonObject
        {
            ["model"] = model,
            ["stream"] = false,
            ["messages"] = new JsonArray(messages
                .Select(m => (JsonNode)new JsonObject { ["role"] = m.Role, ["content"] = m.Content })
                .ToArray()),
        };

        using var request = new HttpRequestMessage(HttpMethod.Post, $"{host}/api/chat")
        {
            Content = new StringContent(payload.ToJsonString(), Encoding.UTF8, "application/json"),
        };
        using var response = await Http.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException($"Ollama HTTP {(int)response.StatusCode}: {Truncate(body, 200)}");
        }

        var data = JsonNode.Parse(body) as JsonObject;
        var text = data?["message"]?["content"]?.GetValue<string>() ?? "";
        var prompt = string.Concat(messages.Select(m => m.Content));
        return new ProviderResult(text, EstimateTokens(prompt), EstimateTokens(text));
    }

    private static async Task<ProviderResult> AnthropicCompleteAsync(string model, List<ChatMessage> messages)
    {
        var apiKey = (Environment.GetEnvironmentVariable("ANTHROPIC_API_KEY") ?? "").Trim();
        if (apiKey.Length == 0)
        {
            throw new InvalidOperationException(
                "ANTHROPIC_API_KEY is required for Anthropic variations (Best Betty → tracked-anthropic).");
        }

        var systemParts = messages.Where(m => m.Role == "system").Select(m => m.Content).ToList();
        var chat = messages
            .Where(m => m.Role is "user" or "assistant")
            .Select(m => (JsonNode)new JsonObject { ["role"] = m.Role, ["content"] = m.Content })
            .ToList();
        if (chat.Count == 0)
        {
            chat.Add(new JsonObject { ["role"] = "user", ["content"] = "Summarize the stories." });
        }

        var payload = new JsonObject
        {
            ["model"] = model,
            ["max_tokens"] = 1024,
            ["messages"] = new JsonArray(chat.ToArray()),
        };
        if (systemParts.Count > 0) payload["system"] = string.Join("\n\n", systemParts);

        using var request = new HttpRequestMessage(HttpMethod.Post, "https://api.anthropic.com/v1/messages")
        {
            Content = new StringContent(payload.ToJsonString(), Encoding.UTF8, "application/json"),
        };
        request.Headers.Add("x-api-key", apiKey);
        request.Headers.Add("anthropic-version", "2023-06-01");

        using var response = await Http.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException($"Anthropic HTTP {(int)response.StatusCode}: {Truncate(body, 300)}");
        }

        var data = JsonNode.Parse(body) as JsonObject;
        var text = string.Concat((data?["content"] as JsonArray ?? new JsonArray())
            .Where(b => b?["type"]?.GetValue<string>() == "text")
            .Select(b => b?["text"]?.GetValue<string>() ?? ""));
        var usage = data?["usage"];
        var input = usage?["input_tokens"]?.GetValue<int>() ?? 0;
        var output = usage?["output_tokens"]?.GetValue<int>() ?? 0;
        return new ProviderResult(text, input, output);
    }

    private sealed class RunMetrics
    {
        public long? LatencyMs;
        public long? TtftMs;
        public int? PromptTokens;
        public int? CompletionTokens;
        public int? TotalTokens;
        public string? FinishReason;

        public Dictionary<string, object?> ToDict() => new()
        {
            ["latency_ms"] = LatencyMs,
            ["ttft_ms"] = TtftMs,
            ["prompt_tokens"] = PromptTokens,
            ["completion_tokens"] = CompletionTokens,
            ["total_tokens"] = TotalTokens,
            ["finish_reason"] = FinishReason,
        };
    }

    private static Dictionary<string, object?> PersonaDict(Persona p) => new()
    {
        ["id"] = p.Id,
        ["name"] = p.Name,
        ["profile"] = p.Profile,
        ["anonymous"] = p.Anonymous,
    };

    private static List<object?> StoriesOrEmpty(IReadOnlyList<JsonNode?> tickerResults) =>
        tickerResults.Cast<object?>().ToList();

    private static Dictionary<string, object?> StatusEvent(string message) => new()
    {
        ["type"] = "status",
        ["message"] = message,
    };

    private static Dictionary<string, object?> ErrorEvent(string message) => new()
    {
        ["type"] = "error",
        ["message"] = message,
    };

    private static Dictionary<string, object?> TokenEvent(string text) => new()
    {
        ["type"] = "token",
        ["text"] = text,
    };

    private static Dictionary<string, object?> MetricsEvent(RunMetrics metrics) => new()
    {
        ["type"] = "metrics",
        ["metrics"] = metrics.ToDict(),
    };

    private static Dictionary<string, object?> DoneEvent(string? resumptionToken) => new()
    {
        ["type"] = "done",
        ["resumptionToken"] = resumptionToken,
    };

    /// <summary>
    /// Evaluate AgentControl, then stream tokens from the served model.
    ///
    /// Event contract: meta | status | token | error | metrics | done.
    ///
    /// When the AgentControl config is disabled (or LaunchDarkly is unreachable),
    /// fall back to the in-code baseline-analyst prompts + local Ollama model —
    /// same text as rest/messages/baseline-*.txt. `yield return` cannot appear
    /// inside a try/catch, so each risky step below captures its outcome first
    /// and the events are yielded once we're back on the happy path.
    /// </summary>
    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona, List<JsonNode?> tickerResults)
    {
        var storiesText = FormatStories(tickerResults);
        var stopwatch = Stopwatch.StartNew();
        var metrics = new RunMetrics();

        LdAiCompletionConfig? config = null;
        string? evalErrorMessage = null;
        try
        {
            config = EvaluateCompletion(persona, storiesText);
        }
        catch (Exception exc)
        {
            evalErrorMessage = exc.Message;
        }

        var disabled = config is { Enabled: false };
        if (evalErrorMessage != null || disabled)
        {
            var reasonMessage = evalErrorMessage != null
                ? $"LaunchDarkly evaluation failed ({evalErrorMessage}); using code baseline."
                : $"AgentControl config '{ConfigKey()}' is off; using code baseline.";
            var messages = BaselineMessages(storiesText);
            var model = DefaultOllamaModel();

            yield return new Dictionary<string, object?>
            {
                ["type"] = "meta",
                ["persona"] = PersonaDict(persona),
                ["input"] = FirstNonEmpty(UserMessageText(messages), storiesText),
                ["provider"] = "ollama",
                ["model"] = $"{model} (code baseline)",
                ["mode"] = "baseline-fallback",
                ["configKey"] = ConfigKey(),
                ["fallback"] = true,
                ["stories"] = StoriesOrEmpty(tickerResults),
            };
            yield return StatusEvent(reasonMessage);

            string? genErrorMessage = null;
            ProviderResult? fallbackResult = null;
            try
            {
                fallbackResult = await OllamaCompleteAsync(model, messages);
            }
            catch (Exception exc)
            {
                genErrorMessage = exc.Message;
            }

            if (genErrorMessage != null)
            {
                yield return ErrorEvent(genErrorMessage);
                metrics.FinishReason = "error";
            }
            else if (fallbackResult != null)
            {
                metrics.PromptTokens = fallbackResult.InputTokens;
                metrics.CompletionTokens = fallbackResult.OutputTokens;
                metrics.TotalTokens = fallbackResult.InputTokens + fallbackResult.OutputTokens;
                if (fallbackResult.Text.Length > 0)
                {
                    metrics.TtftMs = stopwatch.ElapsedMilliseconds;
                    foreach (var chunk in Chunk(fallbackResult.Text, 24)) yield return TokenEvent(chunk);
                }
                metrics.FinishReason = "stop";
            }

            metrics.LatencyMs = stopwatch.ElapsedMilliseconds;
            yield return MetricsEvent(metrics);
            yield return DoneEvent(null);
            yield break;
        }

        string provider = "";
        string model2 = "";
        List<ChatMessage> msgs = new();
        ILdAiConfigTracker? tracker = null;
        string? setupErrorMessage = null;
        try
        {
            (provider, model2) = ResolveRuntime(config!);
            msgs = MessagesAsList(config!);
            if (msgs.Count == 0) throw new InvalidOperationException("Served variation has no messages.");
            tracker = config!.CreateTracker();
        }
        catch (Exception exc)
        {
            setupErrorMessage = exc.Message;
        }

        if (setupErrorMessage != null || tracker is null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "meta",
                ["persona"] = PersonaDict(persona),
                ["input"] = storiesText,
                ["provider"] = "—",
                ["model"] = "—",
                ["mode"] = "launchdarkly",
                ["configKey"] = ConfigKey(),
                ["stories"] = StoriesOrEmpty(tickerResults),
            };
            yield return ErrorEvent(setupErrorMessage ?? "Unknown setup error.");
            metrics.FinishReason = "error";
            metrics.LatencyMs = stopwatch.ElapsedMilliseconds;
            yield return MetricsEvent(metrics);
            yield return DoneEvent(null);
            yield break;
        }

        // LaunchDarkly: ResumptionToken captured up front so thumbs can reconstruct
        // the same tracker (same runId) even after this response has completed.
        var resumptionToken = tracker.ResumptionToken;
        Console.WriteLine($"[generate] {persona.Name}: provider={provider} model={model2} config={ConfigKey()}");

        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = PersonaDict(persona),
            ["input"] = FirstNonEmpty(UserMessageText(msgs), storiesText),
            ["provider"] = provider,
            ["model"] = model2,
            ["mode"] = "launchdarkly",
            ["configKey"] = ConfigKey(),
            ["fallback"] = false,
            ["stories"] = StoriesOrEmpty(tickerResults),
            ["tracked"] = true,
        };

        ProviderResult? result = null;
        string? genError = null;
        try
        {
            // LaunchDarkly: TrackMetricsOf — duration, success/error, tokens → Monitoring.
            result = provider switch
            {
                "anthropic" => await tracker.TrackMetricsOf(
                    r => new AiMetrics(true, new Usage(r.InputTokens + r.OutputTokens, r.InputTokens, r.OutputTokens)),
                    () => AnthropicCompleteAsync(model2, msgs)),
                "ollama" => await tracker.TrackMetricsOf(
                    r => new AiMetrics(true, new Usage(r.InputTokens + r.OutputTokens, r.InputTokens, r.OutputTokens)),
                    () => OllamaCompleteAsync(model2, msgs)),
                _ => throw new InvalidOperationException($"Unsupported runtime provider '{provider}'."),
            };
        }
        catch (Exception exc)
        {
            genError = exc.Message;
        }

        if (genError != null)
        {
            yield return ErrorEvent(genError);
            metrics.FinishReason = "error";
        }
        else if (result != null)
        {
            metrics.PromptTokens = result.InputTokens;
            metrics.CompletionTokens = result.OutputTokens;
            metrics.TotalTokens = result.InputTokens + result.OutputTokens;
            if (result.Text.Length > 0)
            {
                metrics.TtftMs = stopwatch.ElapsedMilliseconds;
                foreach (var chunk in Chunk(result.Text, 24)) yield return TokenEvent(chunk);
            }
            metrics.FinishReason = "stop";
        }

        metrics.LatencyMs = stopwatch.ElapsedMilliseconds;
        yield return MetricsEvent(metrics);
        yield return DoneEvent(resumptionToken);
    }

    /// <summary>
    /// Record thumbs feedback against a tracker rebuilt from its resumption token.
    ///
    /// LaunchDarkly: <c>LdAiClient.CreateTracker(token, context).TrackFeedback</c> —
    /// same resumption-token contract as the Node AI SDK's `createTracker` + `trackFeedback`.
    /// https://launchdarkly.com/docs/sdk/features/ai-metrics#net-ai
    /// </summary>
    public static Dictionary<string, object?> SubmitFeedback(Persona persona, string resumptionToken, string kind)
    {
        var token = resumptionToken.Trim();
        if (token.Length == 0) throw new ArgumentException("resumptionToken is required.");

        var kindLower = kind.Trim().ToLowerInvariant();
        Feedback feedback;
        string normalized;
        if (kindLower is "positive" or "up" or "thumbsup" or "+")
        {
            feedback = Feedback.Positive;
            normalized = "positive";
        }
        else if (kindLower is "negative" or "down" or "thumbsdown" or "-")
        {
            feedback = Feedback.Negative;
            normalized = "negative";
        }
        else
        {
            throw new ArgumentException("kind must be positive or negative.");
        }

        var context = BuildContext(persona);
        var tracker = RequireAiClient().CreateTracker(token, context);
        tracker.TrackFeedback(feedback);
        return new Dictionary<string, object?> { ["ok"] = true, ["kind"] = normalized };
    }
}
