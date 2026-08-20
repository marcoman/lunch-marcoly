using System.Diagnostics;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Threading.Channels;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;
using LaunchDarkly.Sdk.Server.Ai;
using LaunchDarkly.Sdk.Server.Ai.Adapters;
using LaunchDarkly.Sdk.Server.Ai.Config;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;
using LaunchDarkly.Sdk.Server.Ai.Tracking;
using static AgentTools.JsonHelpers;

namespace AgentTools;

/// <summary>Selectable demo identity — also the LaunchDarkly evaluation context.</summary>
public sealed record Persona(string Id, string Name, string Profile, string? Model, bool Anonymous);

/// <summary>Generation metrics surfaced on the SSE "metrics" event (snake_case on the wire).</summary>
public sealed class Metrics
{
    public long? LatencyMs { get; set; }
    public long? TtftMs { get; set; }
    public int? PromptTokens { get; set; }
    public int? CompletionTokens { get; set; }
    public int? TotalTokens { get; set; }
    public string? FinishReason { get; set; }

    public JsonObject ToJson() => new()
    {
        ["latency_ms"] = LatencyMs,
        ["ttft_ms"] = TtftMs,
        ["prompt_tokens"] = PromptTokens,
        ["completion_tokens"] = CompletionTokens,
        ["total_tokens"] = TotalTokens,
        ["finish_reason"] = FinishReason,
    };

    public void AddOllamaTokens(JsonObject data)
    {
        var prompt = GetInt(data, "prompt_eval_count");
        var completion = GetInt(data, "eval_count");
        PromptTokens = (PromptTokens ?? 0) + prompt;
        CompletionTokens = (CompletionTokens ?? 0) + completion;
        TotalTokens = (PromptTokens ?? 0) + (CompletionTokens ?? 0);
    }

    public void AddAnthropicTokens(JsonObject response)
    {
        if (response["usage"] is not JsonObject usage) return;
        var input = GetInt(usage, "input_tokens");
        var output = GetInt(usage, "output_tokens");
        PromptTokens = (PromptTokens ?? 0) + input;
        CompletionTokens = (CompletionTokens ?? 0) + output;
        TotalTokens = (PromptTokens ?? 0) + (CompletionTokens ?? 0);
    }
}

/// <summary>
/// Domain logic for 23-agent-tools (no HTTP here).
///
/// Teaching focus: AgentControl <b>Library tools</b> attached to a completion
/// variation; the app runs a model-driven tool loop and records
/// <c>tracker.TrackToolCall</c> for Monitoring.
///
///   1. Data          Personas (Claude → Anthropic; Llama/Gwen → Ollama, local runtime choice)
///   2. LaunchDarkly  <see cref="LdAiClient.CompletionConfig"/> on equity-briefing-tools
///   3. Providers     Anthropic (cloud) or Ollama (local offline path)
///   4. Generation    tool loop: analyze each ticker → compare → final briefing
///
/// LaunchDarkly: AgentControl · Library tools · CompletionConfig · TrackToolCall · TrackMetricsOf
/// https://launchdarkly.com/docs/home/agentcontrol/tools
/// https://launchdarkly.com/docs/sdk/ai/dotnet
/// </summary>
public static class AgentCore
{
    public static readonly IReadOnlyList<Persona> Personas = new[]
    {
        new Persona("analyst-claude", "Analyst Claude", "anthropic", null, false),
        new Persona("analyst-llama", "Analyst Llama", "ollama", "llama3.2:3b", false),
        // Smaller sibling — expect more skips; Ollama guardrails still apply.
        new Persona("analyst-gwen", "Analyst Gwen", "ollama", "llama3.2:1b", false),
    };

    private const string CannedStories = "No ticker stories loaded yet. Ask the user to click Get Stories.";

    // LaunchDarkly: ai-config key=equity-briefing-tools name="Equity briefing tools" mode=completion
    // Tools: analyze-ticker-stories · compare-ticker-analyses
    private const string DefaultConfigKeyValue = "equity-briefing-tools";
    private const string DefaultAnthropicModelValue = "claude-sonnet-5";
    // Tool-capable local default (1b is too weak for reliable tool loops).
    private const string DefaultOllamaModelValue = "llama3.2:3b";

    public const string ToolAnalyze = "analyze-ticker-stories";
    public const string ToolCompare = "compare-ticker-analyses";
    private const int MaxToolSteps = 6;

    // Extra system guidance for small local models (Ollama personas).
    private const string OllamaToolSuffix =
        "Local-model rules (Ollama):\n" +
        "- You MUST call tools before writing any briefing.\n" +
        "- One tool call per turn when possible: analyze ticker 1, then analyze ticker 2, " +
        "then compare-ticker-analyses.\n" +
        "- Never call compare in the same turn as analyze.\n" +
        "- Pass the exact analyze JSON as analysis_a / analysis_b — do not invent fields.\n" +
        "- Do not skip compare-ticker-analyses after two analyzes.";

    private static readonly HashSet<string> PositiveWords = new(StringComparer.Ordinal)
    {
        "surge", "soar", "gain", "gains", "rise", "rises", "jump", "jumps", "beat", "beats",
        "record", "growth", "upgrade", "bullish", "profit", "profits", "strong", "rally",
    };

    private static readonly HashSet<string> NegativeWords = new(StringComparer.Ordinal)
    {
        "fall", "falls", "drop", "drops", "plunge", "cut", "cuts", "miss", "misses", "loss",
        "losses", "downgrade", "bearish", "weak", "lawsuit", "probe", "decline", "risk", "risks",
    };

    private static readonly Regex WordPattern = new("[a-zA-Z]+", RegexOptions.Compiled);

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(120) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;
    private static readonly object InitLock = new();

    public static Persona? PersonaById(string personaId) =>
        Personas.FirstOrDefault(p => p.Id == personaId);

    public static string ConfigKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_AGENT_CONFIG_KEY") ?? "").Trim();
        return key.Length > 0 ? key : DefaultConfigKeyValue;
    }

    public static string DefaultAnthropicModel()
    {
        var model = (Environment.GetEnvironmentVariable("ANTHROPIC_MODEL") ?? "").Trim();
        return model.Length > 0 ? model : DefaultAnthropicModelValue;
    }

    public static string DefaultOllamaModel()
    {
        var model = (Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "").Trim();
        return model.Length > 0 ? model : DefaultOllamaModelValue;
    }

    /// <summary>Preferred LLM runtime for this UI persona (local app choice, not LD targeting).</summary>
    private static string PersonaRuntime(Persona persona)
    {
        var profile = (persona.Profile ?? "").Trim().ToLowerInvariant();
        return profile is "ollama" or "local" or "gwen" or "llama" ? "ollama" : "anthropic";
    }

    /// <summary>
    /// Resolve (provider, model) for this persona. LaunchDarkly supplies the Anthropic model
    /// on the variation; Ollama personas use the pinned Persona.Model (or OLLAMA_MODEL / default).
    /// </summary>
    private static (string Provider, string Model) PersonaModelName(Persona persona, string ldModel)
    {
        if (PersonaRuntime(persona) == "ollama")
        {
            var pinned = (persona.Model ?? "").Trim();
            return ("ollama", pinned.Length > 0 ? pinned : DefaultOllamaModel());
        }
        var model = ldModel.StartsWith("claude", StringComparison.Ordinal) ? ldModel : DefaultAnthropicModel();
        return ("anthropic", model);
    }

    private static string BaselineMessagesDir() => Path.Combine(YahooNews.ExampleRoot(), "rest", "messages");

    private static string ReadMessageFile(string name)
    {
        var path = Path.Combine(BaselineMessagesDir(), name);
        try
        {
            return File.ReadAllText(path, Encoding.UTF8).Trim();
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException($"Could not read {path}: {exc.Message}", exc);
        }
    }

    public static string BaselineSystemPrompt() => ReadMessageFile("baseline-system.txt");

    public static string BaselineUserTemplate() => ReadMessageFile("baseline-user.txt");

    /// <summary>Plain-text headlines for {{ stories }} (avoids HTML-escaping of JSON quotes).</summary>
    public static string StoriesAsPromptText(JsonArray? tickerResults)
    {
        if (tickerResults is null || tickerResults.Count == 0) return CannedStories;
        var lines = new List<string>();
        foreach (var node in tickerResults)
        {
            if (node is not JsonObject block) continue;
            var ticker = GetStr(block, "ticker", "?").Trim().ToUpperInvariant();
            if (ticker.Length == 0) ticker = "?";
            var name = GetStr(block, "name", ticker).Trim();
            lines.Add($"{ticker} ({name})");
            var stories = block["stories"] as JsonArray;
            if (stories is null || stories.Count == 0)
            {
                lines.Add("  - (no stories available)");
                var error = GetStr(block, "error");
                if (error.Length > 0) lines.Add($"  - note: {error}");
            }
            else
            {
                var i = 1;
                foreach (var s in stories)
                {
                    if (s is not JsonObject story) continue;
                    var title = GetStr(story, "title").Trim();
                    if (title.Length == 0) title = "(untitled)";
                    var source = YahooNews.FormatStorySource(story);
                    if (source.Length == 0) source = "unknown";
                    lines.Add($"  {i}. {title} — {source}");
                    i++;
                }
            }
            lines.Add("");
        }
        return string.Join("\n", lines).Trim();
    }

    /// <summary>UI-friendly sections for the User Prompt panel (heading / body / code).</summary>
    private static JsonArray PromptDisplaySections(string storiesText) => new()
    {
        new JsonObject { ["kind"] = "heading", ["text"] = "Task" },
        new JsonObject
        {
            ["kind"] = "body",
            ["text"] = "Write an equity briefing for these tickers using the required tools.",
        },
        new JsonObject { ["kind"] = "heading", ["text"] = "Stories" },
        new JsonObject { ["kind"] = "code", ["text"] = storiesText },
        new JsonObject { ["kind"] = "heading", ["text"] = "Reminder" },
        new JsonObject
        {
            ["kind"] = "body",
            ["text"] =
                "Call analyze-ticker-stories once per ticker (pass that ticker's headlines), " +
                "then compare-ticker-analyses, then write the briefing from tool results only.",
        },
    };

    /// <summary>
    /// Initialize the server SDK + AI client once at process start.
    ///
    /// LaunchDarkly .NET AI SDK — completion mode.
    /// https://launchdarkly.com/docs/sdk/ai/dotnet
    /// </summary>
    public static void InitLaunchDarkly()
    {
        lock (InitLock)
        {
            if (_aiClient is not null) return;
            var sdkKey = (Environment.GetEnvironmentVariable("LD_SDK_KEY") ?? "").Trim();
            if (sdkKey.Length == 0)
            {
                throw new InvalidOperationException(
                    "LD_SDK_KEY is required. Export a server-side SDK key for the " +
                    $"environment that targets {DefaultConfigKeyValue}.");
            }
            var config = Configuration.Builder(sdkKey).Build();
            _ldClient = new LdClient(config);
            if (!_ldClient.Initialized)
            {
                throw new InvalidOperationException(
                    "LaunchDarkly client failed to initialize. Check LD_SDK_KEY and network.");
            }
            _aiClient = new LdAiClient(new LdClientAdapter(_ldClient));
        }
    }

    private static LdAiClient AiClient()
    {
        if (_aiClient is null) InitLaunchDarkly();
        return _aiClient!;
    }

    public static Context BuildContext(Persona persona)
    {
        var builder = Context.Builder(persona.Id).Name(persona.Name);
        if (persona.Anonymous) builder = builder.Anonymous(true);
        return builder.Build();
    }

    private static LdAiCompletionConfigDefault BaselineCompletionDefault() =>
        LdAiCompletionConfigDefault.New()
            .Enable()
            .SetModelName(DefaultAnthropicModel())
            .SetModelProviderName("anthropic")
            .AddMessage(BaselineSystemPrompt(), LdAiConfigTypes.Role.System)
            .AddMessage(BaselineUserTemplate(), LdAiConfigTypes.Role.User)
            .Build();

    /// <summary>LaunchDarkly: CompletionConfig — model, messages, and attached Library tools.</summary>
    private static LdAiCompletionConfig EvaluateCompletion(Persona persona, string storiesText)
    {
        var variables = new Dictionary<string, object> { ["stories"] = storiesText };
        return AiClient().CompletionConfig(ConfigKey(), BuildContext(persona), BaselineCompletionDefault(), variables);
    }

    private static List<(string Role, string Content)> MessagesAsList(LdAiCompletionConfig config)
    {
        var result = new List<(string, string)>();
        foreach (var msg in config.Messages)
        {
            result.Add((msg.Role.ToString().ToLowerInvariant(), msg.Content));
        }
        return result;
    }

    private static string UserMessageText(List<(string Role, string Content)> messages)
    {
        for (var i = messages.Count - 1; i >= 0; i--)
        {
            if (messages[i].Role == "user") return messages[i].Content;
        }
        return "";
    }

    private static JsonObject ContextAsJson(Persona persona)
    {
        var obj = new JsonObject
        {
            ["kind"] = "user",
            ["key"] = persona.Id,
            ["name"] = persona.Name,
        };
        if (persona.Anonymous) obj["anonymous"] = true;
        return obj;
    }

    private static JsonArray MessagesToJsonArray(IEnumerable<(string Role, string Content)> messages)
    {
        var arr = new JsonArray();
        foreach (var (role, content) in messages)
        {
            arr.Add(new JsonObject { ["role"] = role, ["content"] = content });
        }
        return arr;
    }

    /// <summary>Payload for the UI 'LD details' overlay (last generate: sent + received).</summary>
    private static JsonObject BuildLdTransaction(
        Persona persona,
        string storiesText,
        string configKeyValue,
        bool fallback,
        string mode,
        string provider,
        string model,
        IEnumerable<(string Role, string Content)> messages,
        JsonObject? servedMeta,
        bool? enabled)
    {
        var sdkDefault = new JsonObject
        {
            ["description"] =
                "LdAiCompletionConfigDefault passed to CompletionConfig " +
                "(baseline shape with Library tools; used if config key is missing).",
            ["enabled"] = true,
            ["model"] = DefaultAnthropicModel(),
            ["provider"] = "anthropic",
            ["messages"] = new JsonArray
            {
                new JsonObject { ["role"] = "system", ["content"] = BaselineSystemPrompt() },
                new JsonObject { ["role"] = "user", ["content"] = BaselineUserTemplate() },
            },
        };

        var sent = new JsonObject
        {
            ["configKey"] = configKeyValue,
            ["context"] = ContextAsJson(persona),
            ["variables"] = new JsonObject { ["stories"] = storiesText },
            ["sdkDefault"] = sdkDefault,
        };

        var received = new JsonObject
        {
            ["fallback"] = fallback,
            ["mode"] = mode,
            ["enabled"] = enabled,
            ["configKey"] = configKeyValue,
            ["variationKey"] = servedMeta?["variationKey"]?.DeepClone(),
            ["variationIndex"] = servedMeta?["variationIndex"]?.DeepClone(),
            ["reason"] = servedMeta?["reason"]?.DeepClone(),
            ["version"] = servedMeta?["version"]?.DeepClone(),
            ["versionKey"] = servedMeta?["versionKey"]?.DeepClone(),
            ["ldMode"] = servedMeta?["mode"]?.DeepClone(),
            ["modelKey"] = servedMeta?["modelKey"]?.DeepClone(),
            ["modelVersion"] = servedMeta?["modelVersion"]?.DeepClone(),
            ["provider"] = provider,
            ["model"] = model,
            ["messages"] = MessagesToJsonArray(messages),
        };

        return new JsonObject { ["sent"] = sent, ["received"] = received };
    }

    /// <summary>Converts a Library tool's JSON-schema parameters (LdValue map) into a JsonObject.</summary>
    private static JsonObject ToolParametersToJson(LdAiConfigTypes.Tool tool)
    {
        var obj = new JsonObject();
        foreach (var kv in tool.Parameters)
        {
            obj[kv.Key] = LdValueToJsonNode(kv.Value);
        }
        obj["type"] ??= "object";
        obj["properties"] ??= new JsonObject();
        return obj;
    }

    /// <summary>Converts config.Tools to Anthropic tools= shape.</summary>
    private static List<JsonObject> LdToolsToAnthropic(LdAiCompletionConfig config)
    {
        var result = new List<JsonObject>();
        foreach (var (key, tool) in config.Tools)
        {
            var name = string.IsNullOrEmpty(tool.Name) ? key : tool.Name;
            result.Add(new JsonObject
            {
                ["name"] = name,
                ["description"] = tool.Description ?? "",
                ["input_schema"] = ToolParametersToJson(tool),
            });
        }
        return result;
    }

    /// <summary>Converts config.Tools to OpenAI/Ollama Chat Completions tools= shape.</summary>
    private static List<JsonObject> LdToolsToOpenAi(LdAiCompletionConfig config)
    {
        var result = new List<JsonObject>();
        foreach (var (key, tool) in config.Tools)
        {
            var name = string.IsNullOrEmpty(tool.Name) ? key : tool.Name;
            result.Add(new JsonObject
            {
                ["type"] = "function",
                ["function"] = new JsonObject
                {
                    ["name"] = name,
                    ["description"] = tool.Description ?? "",
                    ["parameters"] = ToolParametersToJson(tool),
                },
            });
        }
        return result;
    }

    private static JsonObject DispatchTool(string name, JsonObject args) => name switch
    {
        ToolAnalyze => HandleAnalyzeTickerStories(args),
        ToolCompare => HandleCompareTickerAnalyses(args),
        _ => new JsonObject { ["error"] = $"Unknown tool: {name}" },
    };

    /// <summary>True when obj resembles HandleAnalyzeTickerStories output.</summary>
    private static bool LooksLikeAnalyzeResult(JsonNode? obj) =>
        obj is JsonObject o && o.ContainsKey("ticker") && (o.ContainsKey("tone_score") || o.ContainsKey("claims"));

    /// <summary>
    /// Prefer real analyze tool results over model-invented compare args.
    /// Small local models often call compare in parallel with inventing analysis_a/b.
    /// </summary>
    private static (JsonObject Args, bool Rewritten) NormalizeCompareArgs(
        JsonObject rawInput, List<JsonObject> analyzeResults)
    {
        var a = rawInput["analysis_a"] as JsonObject ?? new JsonObject();
        var b = rawInput["analysis_b"] as JsonObject ?? new JsonObject();
        if (LooksLikeAnalyzeResult(a) && LooksLikeAnalyzeResult(b))
        {
            return (new JsonObject { ["analysis_a"] = a.DeepClone(), ["analysis_b"] = b.DeepClone() }, false);
        }
        if (analyzeResults.Count >= 2)
        {
            return (new JsonObject
            {
                ["analysis_a"] = analyzeResults[^2].DeepClone(),
                ["analysis_b"] = analyzeResults[^1].DeepClone(),
            }, true);
        }
        return (new JsonObject { ["analysis_a"] = a.DeepClone(), ["analysis_b"] = b.DeepClone() }, false);
    }

    private static string OllamaToolName(JsonObject call) =>
        call["function"] is JsonObject fn ? GetStr(fn, "name") : "";

    /// <summary>Run analyzes before compare within the same model turn.</summary>
    private static List<JsonObject> SortOllamaToolCalls(List<JsonObject> calls)
    {
        int Order(JsonObject call)
        {
            var name = OllamaToolName(call);
            if (name == ToolAnalyze) return 0;
            if (name == ToolCompare) return 1;
            return 2;
        }
        return calls.OrderBy(Order).ToList();
    }

    private static int SentimentScore(string text)
    {
        var score = 0;
        foreach (Match m in WordPattern.Matches(text.ToLowerInvariant()))
        {
            if (PositiveWords.Contains(m.Value)) score++;
            else if (NegativeWords.Contains(m.Value)) score--;
        }
        return score;
    }

    /// <summary>Deterministic single-ticker analysis grounded in headline titles.</summary>
    private static JsonObject HandleAnalyzeTickerStories(JsonObject args)
    {
        var ticker = GetStr(args, "ticker").Trim().ToUpperInvariant();
        if (ticker.Length == 0) ticker = "?";
        var rawStories = args["stories"] as JsonArray ?? new JsonArray();
        var claims = new JsonArray();
        var score = 0;
        foreach (var item in rawStories)
        {
            if (item is not JsonObject story) continue;
            var title = GetStr(story, "title").Trim();
            if (title.Length == 0) continue;
            var tone = SentimentScore(title);
            score += tone;
            var claim = tone switch
            {
                > 0 => $"Positive headline signal for {ticker}: {title}",
                < 0 => $"Negative headline signal for {ticker}: {title}",
                _ => $"Neutral headline for {ticker}: {title}",
            };
            claims.Add(new JsonObject { ["claim"] = claim, ["evidence_title"] = title });
        }
        var summary = claims.Count == 0
            ? $"No usable headlines provided for {ticker}."
            : score > 0
                ? $"{ticker}: net positive headline tone ({claims.Count} stories)."
                : score < 0
                    ? $"{ticker}: net negative headline tone ({claims.Count} stories)."
                    : $"{ticker}: mixed/neutral headline tone ({claims.Count} stories).";
        return new JsonObject
        {
            ["ticker"] = ticker,
            ["claims"] = claims,
            ["summary"] = summary,
            ["tone_score"] = score,
        };
    }

    private static string Stance(int score) => score > 0 ? "constructive" : score < 0 ? "cautious" : "neutral";

    private static JsonArray EvidenceTitles(JsonObject analysis)
    {
        var result = new JsonArray();
        if (analysis["claims"] is JsonArray claims)
        {
            foreach (var c in claims)
            {
                if (c is not JsonObject claim) continue;
                var title = GetStr(claim, "evidence_title").Trim();
                if (title.Length > 0) result.Add(title);
            }
        }
        return result;
    }

    /// <summary>Compare two analyze-ticker-stories results; optional preferred ticker.</summary>
    private static JsonObject HandleCompareTickerAnalyses(JsonObject args)
    {
        var a = args["analysis_a"] as JsonObject ?? new JsonObject();
        var b = args["analysis_b"] as JsonObject ?? new JsonObject();
        var ta = GetStr(a, "ticker", "A").ToUpperInvariant();
        var tb = GetStr(b, "ticker", "B").ToUpperInvariant();
        var sa = GetInt(a, "tone_score");
        var sb = GetInt(b, "tone_score");

        string? preferred = sa > sb ? ta : sb > sa ? tb : null;

        var rationaleParts = new List<string>
        {
            $"{ta} tone_score={sa} ({Stance(sa)}); {tb} tone_score={sb} ({Stance(sb)}).",
            preferred is not null
                ? $"{preferred} is the better option on headline tone alone."
                : "No clear preferred ticker on headline tone.",
        };

        return new JsonObject
        {
            ["ticker1"] = new JsonObject
            {
                ["ticker"] = ta,
                ["recommendation"] = Stance(sa),
                ["evidence"] = EvidenceTitles(a),
            },
            ["ticker2"] = new JsonObject
            {
                ["ticker"] = tb,
                ["recommendation"] = Stance(sb),
                ["evidence"] = EvidenceTitles(b),
            },
            ["preferred_ticker"] = preferred,
            ["rationale"] = string.Join(" ", rationaleParts),
        };
    }

    /// <summary>Non-streaming Ollama /api/chat with tools (OpenAI-compatible shape).</summary>
    private static async Task<JsonObject> OllamaChatAsync(string model, JsonArray messages, List<JsonObject> tools)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var payload = new JsonObject
        {
            ["model"] = model,
            ["stream"] = false,
            ["messages"] = messages.DeepClone(),
        };
        if (tools.Count > 0)
        {
            var toolsArr = new JsonArray();
            foreach (var t in tools) toolsArr.Add(t.DeepClone());
            payload["tools"] = toolsArr;
        }

        using var request = new HttpRequestMessage(HttpMethod.Post, $"{host}/api/chat")
        {
            Content = new StringContent(payload.ToJsonString(), Encoding.UTF8, "application/json"),
        };

        HttpResponseMessage response;
        try
        {
            response = await Http.SendAsync(request);
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): {exc.Message}. Is the Ollama daemon running?", exc);
        }

        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): HTTP {(int)response.StatusCode} {body}. " +
                $"Is Ollama running, and does `ollama list` include {model}?");
        }
        return (JsonNode.Parse(body) as JsonObject) ?? new JsonObject();
    }

    /// <summary>Anthropic Messages API call with tools=.</summary>
    private static async Task<JsonObject> AnthropicMessagesAsync(
        string apiKey, string model, string system, JsonArray chat, List<JsonObject> tools)
    {
        var payload = new JsonObject
        {
            ["model"] = model,
            ["max_tokens"] = 1024,
            ["messages"] = chat.DeepClone(),
        };
        if (!string.IsNullOrWhiteSpace(system)) payload["system"] = system;
        if (tools.Count > 0)
        {
            var toolsArr = new JsonArray();
            foreach (var t in tools) toolsArr.Add(t.DeepClone());
            payload["tools"] = toolsArr;
        }

        using var request = new HttpRequestMessage(HttpMethod.Post, "https://api.anthropic.com/v1/messages")
        {
            Content = new StringContent(payload.ToJsonString(), Encoding.UTF8, "application/json"),
        };
        request.Headers.Add("x-api-key", apiKey);
        request.Headers.Add("anthropic-version", "2023-06-01");

        var response = await Http.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        if (!response.IsSuccessStatusCode)
        {
            var truncated = body.Length > 300 ? body[..300] : body;
            throw new InvalidOperationException($"Anthropic request failed: HTTP {(int)response.StatusCode} {truncated}");
        }
        return (JsonNode.Parse(body) as JsonObject) ?? new JsonObject();
    }

    private static string AnthropicText(JsonObject response)
    {
        var sb = new StringBuilder();
        if (response["content"] is JsonArray content)
        {
            foreach (var block in content)
            {
                if (block is JsonObject b && GetStr(b, "type") == "text")
                {
                    sb.Append(GetStr(b, "text"));
                }
            }
        }
        return sb.ToString();
    }

    private static AiMetrics OllamaMetricsExtractor(JsonObject data)
    {
        var prompt = GetInt(data, "prompt_eval_count");
        var completion = GetInt(data, "eval_count");
        return new AiMetrics(success: true, tokens: new Usage(prompt + completion, prompt, completion));
    }

    private static AiMetrics AnthropicMetricsExtractor(JsonObject response)
    {
        if (response["usage"] is not JsonObject usage) return new AiMetrics(success: true);
        var input = GetInt(usage, "input_tokens");
        var output = GetInt(usage, "output_tokens");
        return new AiMetrics(success: true, tokens: new Usage(input + output, input, output));
    }

    private static JsonObject PersonaJson(Persona persona)
    {
        var obj = new JsonObject
        {
            ["id"] = persona.Id,
            ["name"] = persona.Name,
            ["profile"] = persona.Profile,
        };
        if (persona.Model is not null) obj["model"] = persona.Model;
        obj["anonymous"] = persona.Anonymous;
        return obj;
    }

    private static JsonObject StatusEvent(string message) => new() { ["type"] = "status", ["message"] = message };

    private static JsonObject ErrorEvent(string message) => new() { ["type"] = "error", ["message"] = message };

    private static JsonObject MetricsEvent(Metrics metrics) => new() { ["type"] = "metrics", ["metrics"] = metrics.ToJson() };

    private static JsonObject DoneEvent() => new() { ["type"] = "done" };

    private static JsonObject ToolEvent(string name, JsonObject args, JsonObject result, int callIndex, JsonNode round) =>
        new()
        {
            ["type"] = "tool",
            ["name"] = name,
            ["args"] = args.DeepClone(),
            ["result"] = result.DeepClone(),
            ["callIndex"] = callIndex,
            ["round"] = round,
        };

    private static JsonObject FallbackMeta(Persona persona, string storiesText, JsonArray inputSections, JsonArray? tickerResults)
    {
        var baselineMsgs = new List<(string Role, string Content)>
        {
            ("system", BaselineSystemPrompt()),
            ("user", BaselineUserTemplate()),
        };
        return new JsonObject
        {
            ["type"] = "meta",
            ["persona"] = PersonaJson(persona),
            ["input"] = storiesText,
            ["inputSections"] = inputSections,
            ["provider"] = "anthropic",
            ["model"] = $"{DefaultAnthropicModel()} (code baseline)",
            ["mode"] = "baseline-fallback",
            ["configKey"] = ConfigKey(),
            ["fallback"] = true,
            ["stories"] = tickerResults?.DeepClone() ?? new JsonArray(),
            ["ldTransaction"] = BuildLdTransaction(
                persona,
                storiesText,
                ConfigKey(),
                fallback: true,
                mode: "baseline-fallback",
                provider: "anthropic",
                model: $"{DefaultAnthropicModel()} (code baseline)",
                messages: baselineMsgs,
                servedMeta: null,
                enabled: false),
        };
    }

    /// <summary>
    /// Evaluate config, run the model tool loop (Anthropic or Ollama), and stream the final
    /// briefing tokens as SSE events: meta, status, tool, token, error, metrics, done.
    /// </summary>
    public static async IAsyncEnumerable<JsonObject> GenerateStreamAsync(Persona persona, JsonArray? tickerResults)
    {
        // A Channel bridges try/catch-heavy async logic (RunGenerateAsync) to an async
        // iterator; C# forbids `yield return` inside a try block that has a catch clause.
        var channel = Channel.CreateUnbounded<JsonObject>(new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = true,
        });

        _ = Task.Run(async () =>
        {
            try
            {
                await RunGenerateAsync(persona, tickerResults, channel.Writer);
            }
            catch (Exception exc)
            {
                await channel.Writer.WriteAsync(ErrorEvent($"Unexpected error: {exc.Message}"));
                await channel.Writer.WriteAsync(DoneEvent());
            }
            finally
            {
                channel.Writer.TryComplete();
            }
        });

        await foreach (var evt in channel.Reader.ReadAllAsync())
        {
            yield return evt;
        }
    }

    private static async Task RunGenerateAsync(Persona persona, JsonArray? tickerResults, ChannelWriter<JsonObject> writer)
    {
        var storiesText = StoriesAsPromptText(tickerResults);
        var started = Stopwatch.StartNew();
        var metrics = new Metrics();
        var inputSections = PromptDisplaySections(storiesText);

        LdAiCompletionConfig? config = null;
        Exception? evalError = null;
        try
        {
            config = EvaluateCompletion(persona, storiesText);
        }
        catch (Exception exc)
        {
            evalError = exc;
        }

        if (config is null)
        {
            await writer.WriteAsync(FallbackMeta(persona, storiesText, inputSections, tickerResults));
            await writer.WriteAsync(StatusEvent(
                $"LaunchDarkly evaluation failed ({evalError!.Message}); using code baseline."));
            await writer.WriteAsync(ErrorEvent(
                "Tool loop requires a live AgentControl config. " +
                $"Provision with rest/create-tools.sh && rest/create-config.sh. ({evalError.Message})"));
            metrics.FinishReason = "error";
            metrics.LatencyMs = started.ElapsedMilliseconds;
            await writer.WriteAsync(MetricsEvent(metrics));
            await writer.WriteAsync(DoneEvent());
            return;
        }

        if (!config.Enabled)
        {
            await writer.WriteAsync(FallbackMeta(persona, storiesText, inputSections, tickerResults));
            await writer.WriteAsync(StatusEvent($"AgentControl config '{ConfigKey()}' is off; tools path disabled."));
            await writer.WriteAsync(ErrorEvent("Enable the AgentControl config and attach Library tools to generate."));
            metrics.FinishReason = "error";
            metrics.LatencyMs = started.ElapsedMilliseconds;
            await writer.WriteAsync(MetricsEvent(metrics));
            await writer.WriteAsync(DoneEvent());
            return;
        }

        var ldModel = string.IsNullOrEmpty(config.Model?.Name) ? DefaultAnthropicModel() : config.Model!.Name;
        var (provider, modelName) = PersonaModelName(persona, ldModel);

        var messages = MessagesAsList(config);
        var anthropicTools = LdToolsToAnthropic(config);
        var openaiTools = LdToolsToOpenAi(config);
        var toolNames = anthropicTools.Select(t => GetStr(t, "name")).Where(n => n.Length > 0).ToList();
        var tracker = config.CreateTracker();

        var toolNamesJson = new JsonArray();
        foreach (var n in toolNames) toolNamesJson.Add(n);

        await writer.WriteAsync(new JsonObject
        {
            ["type"] = "meta",
            ["persona"] = PersonaJson(persona),
            ["input"] = UserMessageText(messages).Length > 0 ? UserMessageText(messages) : storiesText,
            ["inputSections"] = inputSections,
            ["provider"] = provider,
            ["model"] = modelName,
            ["mode"] = "launchdarkly",
            ["configKey"] = ConfigKey(),
            ["fallback"] = false,
            ["stories"] = tickerResults?.DeepClone() ?? new JsonArray(),
            ["tools"] = toolNamesJson,
            ["tracked"] = true,
            ["ldTransaction"] = BuildLdTransaction(
                persona,
                storiesText,
                ConfigKey(),
                fallback: false,
                mode: "launchdarkly",
                provider: provider,
                model: modelName,
                messages: messages,
                servedMeta: null,
                enabled: true),
        });

        if (toolNames.Count == 0)
        {
            await writer.WriteAsync(StatusEvent("No tools attached on this variation. Run rest/attach-tools.sh."));
        }

        var system = "";
        var chat = new JsonArray();
        foreach (var (role, content) in messages)
        {
            if (role == "system")
            {
                system = system.Length > 0 ? $"{system}\n\n{content}" : content;
            }
            else
            {
                chat.Add(new JsonObject { ["role"] = role, ["content"] = content });
            }
        }

        var finalText = "";
        var toolCallIndex = 0;
        Exception? loopError = null;

        try
        {
            if (provider == "ollama")
            {
                var ollamaMessages = new JsonArray();
                var ollamaSystem = system.Length > 0 ? $"{system}\n\n{OllamaToolSuffix}".Trim() : OllamaToolSuffix;
                if (ollamaSystem.Length > 0)
                {
                    ollamaMessages.Add(new JsonObject { ["role"] = "system", ["content"] = ollamaSystem });
                }
                foreach (var node in chat) ollamaMessages.Add(node?.DeepClone());

                var analyzeResults = new List<JsonObject>();
                var calledTools = new List<string>();
                var nudgedForTools = false;
                var brokeEarly = false;

                for (var step = 0; step < MaxToolSteps; step++)
                {
                    var data = await tracker.TrackMetricsOf(
                        OllamaMetricsExtractor,
                        () => OllamaChatAsync(modelName, ollamaMessages, openaiTools));
                    metrics.AddOllamaTokens(data);

                    var message = data["message"] as JsonObject ?? new JsonObject();
                    var toolCallsArr = message["tool_calls"] as JsonArray ?? new JsonArray();
                    var content = GetStr(message, "content");

                    if (toolCallsArr.Count == 0)
                    {
                        // Small models sometimes skip tools entirely — nudge once.
                        if (!nudgedForTools && toolNames.Count > 0 && analyzeResults.Count == 0 && step < MaxToolSteps - 1)
                        {
                            nudgedForTools = true;
                            await writer.WriteAsync(StatusEvent(
                                $"{persona.Name} skipped tools on the first turn — nudging once " +
                                "to run analyze → analyze → compare."));
                            ollamaMessages.Add(message.DeepClone());
                            ollamaMessages.Add(new JsonObject
                            {
                                ["role"] = "user",
                                ["content"] =
                                    "Stop writing the briefing. Call tools now: " +
                                    $"{ToolAnalyze} once per ticker, then " +
                                    $"{ToolCompare} with the exact analyze JSON results, " +
                                    "then write the briefing.",
                            });
                            continue;
                        }

                        finalText = content;
                        brokeEarly = true;
                        break;
                    }

                    ollamaMessages.Add(message.DeepClone());
                    var toolCalls = toolCallsArr.OfType<JsonObject>().ToList();
                    foreach (var call in SortOllamaToolCalls(toolCalls))
                    {
                        if (call["function"] is not JsonObject fn) continue;
                        var name = GetStr(fn, "name");
                        JsonObject rawInput;
                        var argumentsNode = fn["arguments"];
                        if (argumentsNode is JsonValue av && av.TryGetValue<string>(out var argsStr))
                        {
                            rawInput = (JsonNode.Parse(argsStr) as JsonObject) ?? new JsonObject();
                        }
                        else
                        {
                            rawInput = argumentsNode as JsonObject ?? new JsonObject();
                            rawInput = (JsonObject)rawInput.DeepClone();
                        }

                        var rewritten = false;
                        if (name == ToolCompare)
                        {
                            (rawInput, rewritten) = NormalizeCompareArgs(rawInput, analyzeResults);
                            if (rewritten)
                            {
                                await writer.WriteAsync(StatusEvent(
                                    "Rewrote compare args from prior analyze results " +
                                    "(local model invented or parallel-called compare)."));
                            }
                        }

                        var result = DispatchTool(name, rawInput);
                        tracker.TrackToolCall(name);
                        calledTools.Add(name);
                        if (name == ToolAnalyze && LooksLikeAnalyzeResult(result))
                        {
                            analyzeResults.Add(result);
                        }
                        toolCallIndex++;
                        await writer.WriteAsync(ToolEvent(name, rawInput, result, toolCallIndex, step + 1));
                        ollamaMessages.Add(new JsonObject { ["role"] = "tool", ["content"] = result.ToJsonString() });
                    }
                }

                if (!brokeEarly)
                {
                    await writer.WriteAsync(StatusEvent($"Hit MAX_TOOL_STEPS={MaxToolSteps}; using last model text if any."));
                    if (finalText.Length == 0) finalText = "(No final text after tool loop.)";
                }

                // Guardrail: if the local model analyzed twice but never compared, run compare once.
                if (!calledTools.Contains(ToolCompare) && analyzeResults.Count >= 2 && toolNames.Count > 0)
                {
                    await writer.WriteAsync(StatusEvent(
                        $"{persona.Name} skipped compare-ticker-analyses — running it from prior " +
                        "analyze results, then asking for a final briefing."));
                    var compareArgs = new JsonObject
                    {
                        ["analysis_a"] = analyzeResults[^2].DeepClone(),
                        ["analysis_b"] = analyzeResults[^1].DeepClone(),
                    };
                    var result = DispatchTool(ToolCompare, compareArgs);
                    tracker.TrackToolCall(ToolCompare);
                    toolCallIndex++;
                    await writer.WriteAsync(ToolEvent(ToolCompare, compareArgs, result, toolCallIndex, "guardrail"));
                    ollamaMessages.Add(new JsonObject
                    {
                        ["role"] = "user",
                        ["content"] =
                            $"{ToolCompare} returned:\n{result.ToJsonString()}\n\n" +
                            "Write the short equity briefing now using ONLY the tool " +
                            "results (analyze + compare). Cite evidence titles.",
                    });
                    try
                    {
                        var data = await tracker.TrackMetricsOf(
                            OllamaMetricsExtractor,
                            () => OllamaChatAsync(modelName, ollamaMessages, new List<JsonObject>()));
                        metrics.AddOllamaTokens(data);
                        var brief = GetStr(data["message"] as JsonObject, "content");
                        if (brief.Length > 0) finalText = brief;
                    }
                    catch (Exception exc)
                    {
                        await writer.WriteAsync(StatusEvent($"Post-compare briefing call failed: {exc.Message}"));
                    }
                }
            }
            else
            {
                var apiKey = (Environment.GetEnvironmentVariable("ANTHROPIC_API_KEY") ?? "").Trim();
                if (apiKey.Length == 0)
                {
                    await writer.WriteAsync(ErrorEvent(
                        "ANTHROPIC_API_KEY is required for Analyst Claude. " +
                        "Switch to Analyst Llama or Analyst Gwen for local Ollama, " +
                        "or export your Claude key."));
                    metrics.FinishReason = "error";
                    metrics.LatencyMs = started.ElapsedMilliseconds;
                    await writer.WriteAsync(MetricsEvent(metrics));
                    await writer.WriteAsync(DoneEvent());
                    return;
                }

                var brokeEarly = false;
                for (var step = 0; step < MaxToolSteps; step++)
                {
                    var response = await tracker.TrackMetricsOf(
                        AnthropicMetricsExtractor,
                        () => AnthropicMessagesAsync(apiKey, modelName, system, chat, anthropicTools));
                    metrics.AddAnthropicTokens(response);

                    var stop = GetStr(response, "stop_reason");
                    if (stop != "tool_use")
                    {
                        finalText = AnthropicText(response);
                        brokeEarly = true;
                        break;
                    }

                    var assistantContent = new JsonArray();
                    var toolResults = new JsonArray();
                    if (response["content"] is JsonArray contentArr)
                    {
                        foreach (var el in contentArr)
                        {
                            if (el is not JsonObject block) continue;
                            var btype = GetStr(block, "type");
                            if (btype == "text")
                            {
                                assistantContent.Add(new JsonObject { ["type"] = "text", ["text"] = GetStr(block, "text") });
                            }
                            else if (btype == "tool_use")
                            {
                                var name = GetStr(block, "name");
                                var toolId = GetStr(block, "id");
                                var rawInput = block["input"] is JsonObject inputObj
                                    ? (JsonObject)inputObj.DeepClone()
                                    : new JsonObject();

                                var result = DispatchTool(name, rawInput);
                                tracker.TrackToolCall(name);
                                toolCallIndex++;
                                await writer.WriteAsync(ToolEvent(name, rawInput, result, toolCallIndex, step + 1));

                                assistantContent.Add(new JsonObject
                                {
                                    ["type"] = "tool_use",
                                    ["id"] = toolId,
                                    ["name"] = name,
                                    ["input"] = rawInput.DeepClone(),
                                });
                                toolResults.Add(new JsonObject
                                {
                                    ["type"] = "tool_result",
                                    ["tool_use_id"] = toolId,
                                    ["content"] = result.ToJsonString(),
                                });
                            }
                        }
                    }
                    chat.Add(new JsonObject { ["role"] = "assistant", ["content"] = assistantContent });
                    chat.Add(new JsonObject { ["role"] = "user", ["content"] = toolResults });
                }

                if (!brokeEarly)
                {
                    await writer.WriteAsync(StatusEvent($"Hit MAX_TOOL_STEPS={MaxToolSteps}; using last model text if any."));
                    if (finalText.Length == 0) finalText = "(No final text after tool loop.)";
                }
            }
        }
        catch (Exception exc)
        {
            loopError = exc;
        }

        if (loopError is not null)
        {
            await writer.WriteAsync(ErrorEvent(loopError.Message));
            metrics.FinishReason = "error";
            metrics.LatencyMs = started.ElapsedMilliseconds;
            await writer.WriteAsync(MetricsEvent(metrics));
            await writer.WriteAsync(DoneEvent());
            return;
        }

        if (finalText.Length > 0)
        {
            metrics.TtftMs = started.ElapsedMilliseconds;
            const int size = 24;
            for (var i = 0; i < finalText.Length; i += size)
            {
                var chunk = finalText.Substring(i, Math.Min(size, finalText.Length - i));
                await writer.WriteAsync(new JsonObject { ["type"] = "token", ["text"] = chunk });
            }
        }
        metrics.FinishReason = "stop";
        metrics.LatencyMs = started.ElapsedMilliseconds;
        await writer.WriteAsync(MetricsEvent(metrics));
        await writer.WriteAsync(DoneEvent());
    }
}
