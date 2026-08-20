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
using LaunchDarkly.Sdk.Server.Ai.Graph;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;

namespace AgentGraph;

/// <summary>
/// Domain logic for 25-agent-graph (no HTTP here).
///
/// =============================================================================
/// HOW TO READ THIS FILE
/// =============================================================================
///
/// Equity briefing UI with LaunchDarkly <b>Agent Graphs</b>:
///
///   1. Data          Charlie / Amelia / Toby + humor easter egg
///   2. LaunchDarkly  AgentGraph + AgentConfig (mode=agent instructions)
///   3. Providers     Local Ollama per node (LD does not call the model)
///   4. Generation    assess → specialist → (optional scorers) → finalize
///
/// LaunchDarkly insertion point (read this first):
///   GenerateStreamAsync() → LdAiClient.AgentGraph(...) then AgentConfig(...) per node
///   Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
///   Keywords: AgentControl · Agent graphs · Agents · Library tools · TrackToolCall
///
/// Scorers (questions gap/ground, joke corny) are app-invoked for Trace — scores appear
/// in the tool *name* (e.g. score-question-gap:0.82); they do not change specialist text.
///
/// Routing: after assess, the chosen specialist (and later finalize) must match an
/// <b>outgoing edge</b> on the evaluated Agent Graph. Invalid edges → redirect to report
/// (or fail) and record handoff/redirect metrics on AiGraphTracker.
///
/// Why manual walk (not an orchestration framework):
///   Classroom Trace needs a visible assess → specialist → finalize path with Ollama — so
///   we evaluate the graph + each node via the AI SDK, invoke Ollama ourselves, and
///   validate handoffs against graph edges (AgentGraphDefinition.GetChildNodes).
/// </summary>
public static class AgentCore
{
    /// <summary>Selectable demo identity — also the LaunchDarkly user context.</summary>
    public sealed record Persona(string Id, string Name, string Profile, bool Anonymous = false);

    public static readonly IReadOnlyList<Persona> Personas = new List<Persona>
    {
        new("conservative-charlie", "Conservative Charlie", "conservative"),
        new("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
    };

    private const string CannedStories =
        "No ticker stories loaded yet. Ask the user to click Get Stories.";

    private const string DefaultGraphKeyValue = "equity-briefing-graph";
    private const string DefaultOllamaModelName = "llama3.2:3b";
    // Joke path: higher temperature for more variety (not "never repeat").
    private const double DefaultJokeTemperature = 0.95;
    private const double DefaultCornyHigh = 0.80;
    private const double DefaultCornyLow = 0.20;

    private const string ToolQuestionGap = "score-question-gap";
    private const string ToolJokeCorny = "score-joke-corny";

    // Soft angle hints — nudge variety without banning prior jokes.
    private static readonly string[] JokeAngleHints =
    {
        "bulls vs bears",
        "earnings season nerves",
        "index funds vs stock picking",
        "coffee and candlesticks",
        "diversification as a lifestyle",
        "the eternally loading chart",
        "hot takes cooling overnight",
        "FOMO meeting patience",
    };

    private static readonly HashSet<string> ValidSpecialists = new() { "report", "questions", "good", "joke" };
    private static readonly HashSet<string> ActionsNeedingStories = new() { "report", "questions", "good" };

    // Humor easter egg — app code only (not an LLM message).
    private static readonly Dictionary<string, int> HumorLevel = new()
    {
        ["conservative-charlie"] = 25,
        ["anonymous-amelia"] = 50,
        ["thoughtless-toby"] = 90,
    };

    private static readonly Dictionary<string, string> DefaultNodeKeys = new()
    {
        ["assess"] = "equity-briefing-graph-assess",
        ["report"] = "equity-briefing-graph-report",
        ["questions"] = "equity-briefing-graph-questions",
        ["good"] = "equity-briefing-graph-good",
        ["joke"] = "equity-briefing-graph-joke",
        ["finalize"] = "equity-briefing-graph-finalize",
    };

    private static readonly Dictionary<string, string> NodeEnvVars = new()
    {
        ["assess"] = "LD_NODE_ASSESS",
        ["report"] = "LD_NODE_REPORT",
        ["questions"] = "LD_NODE_QUESTIONS",
        ["good"] = "LD_NODE_GOOD",
        ["joke"] = "LD_NODE_JOKE",
        ["finalize"] = "LD_NODE_FINALIZE",
    };

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(180) };

    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    public static string GraphKey()
    {
        var key = (Environment.GetEnvironmentVariable("LD_GRAPH_KEY") ?? "").Trim();
        return key.Length == 0 ? DefaultGraphKeyValue : key;
    }

    public static string NodeKey(string role)
    {
        if (NodeEnvVars.TryGetValue(role, out var envName))
        {
            var raw = (Environment.GetEnvironmentVariable(envName) ?? "").Trim();
            if (raw.Length > 0) return raw;
        }
        return DefaultNodeKeys[role];
    }

    /// <summary>Map a graph config key back to a specialist/role name.</summary>
    private static string? RoleFromNodeKey(string configKey)
    {
        foreach (var role in new[] { "assess", "report", "questions", "good", "joke", "finalize" })
        {
            if (configKey == NodeKey(role)) return role;
        }
        const string marker = "equity-briefing-graph-";
        if (configKey.StartsWith(marker, StringComparison.Ordinal))
        {
            var suffix = configKey[marker.Length..];
            if (ValidSpecialists.Contains(suffix) || suffix is "assess" or "finalize") return suffix;
        }
        return null;
    }

    public static string DefaultOllamaModel()
    {
        var model = (Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "").Trim();
        return model.Length == 0 ? DefaultOllamaModelName : model;
    }

    public static double JokeTemperature()
    {
        var raw = (Environment.GetEnvironmentVariable("JOKE_TEMPERATURE") ?? "").Trim();
        if (raw.Length == 0) return DefaultJokeTemperature;
        return double.TryParse(raw, out var n) ? Math.Max(0.0, Math.Min(1.5, n)) : DefaultJokeTemperature;
    }

    public static double CornyHighThreshold()
    {
        var raw = (Environment.GetEnvironmentVariable("JOKE_CORNY_HIGH") ?? "").Trim();
        if (raw.Length == 0) return DefaultCornyHigh;
        return double.TryParse(raw, out var n) ? n : DefaultCornyHigh;
    }

    public static double CornyLowThreshold()
    {
        var raw = (Environment.GetEnvironmentVariable("JOKE_CORNY_LOW") ?? "").Trim();
        if (raw.Length == 0) return DefaultCornyLow;
        return double.TryParse(raw, out var n) ? n : DefaultCornyLow;
    }

    private static int HumorLevelFor(Persona persona) => HumorLevel.GetValueOrDefault(persona.Id, 50);

    private static string MessagesDir() => Path.Combine(YahooNews.ExampleRoot(), "rest", "messages");

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

    private static string LoadQuestionsList()
    {
        var path = Path.Combine(MessagesDir(), "questions.txt");
        try
        {
            var lines = new List<string>();
            foreach (var rawLine in File.ReadAllLines(path))
            {
                var s = rawLine.Trim();
                if (s.Length == 0 || s.StartsWith('#')) continue;
                lines.Add(s);
            }
            return string.Join("\n", lines.Select(q => $"- {q}"));
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException($"Could not read questions list {path}: {exc.Message}", exc);
        }
    }

    private static string FormatStories(List<Dictionary<string, object?>>? tickerResults)
        => tickerResults is { Count: > 0 } ? YahooNews.FormatStoriesForPrompt(tickerResults) : CannedStories;

    // ---------------------------------------------------------------------
    // LaunchDarkly
    // ---------------------------------------------------------------------

    /// <summary>
    /// Initialize the shared LaunchDarkly clients once at process start.
    ///
    /// LaunchDarkly: server-side SDK + AI SDK for AgentControl agent graphs + agent configs.
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
                "environment that targets equity-briefing-graph.");
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

    private static LdAiClient AiClient()
    {
        if (_aiClient == null) InitLaunchDarkly();
        return _aiClient!;
    }

    /// <summary>Build LD context. Anonymous Amelia: anonymous=true (fallthrough targeting).</summary>
    public static Context BuildContext(Persona persona, string action)
    {
        var builder = Context.Builder(persona.Id).Name(persona.Name);
        if (persona.Anonymous) builder = builder.Anonymous(true);
        builder = builder.Set("action", action).Set("profile", persona.Profile);
        return builder.Build();
    }

    /// <summary>Plain map of the evaluation context for the LD details drawer.</summary>
    private static Dictionary<string, object?> ContextAsMap(Persona persona, string action)
    {
        var map = new Dictionary<string, object?>
        {
            ["kind"] = "user",
            ["key"] = persona.Id,
            ["name"] = persona.Name,
            ["action"] = action,
            ["profile"] = persona.Profile,
        };
        if (persona.Anonymous) map["anonymous"] = true;
        return map;
    }

    /// <summary>
    /// Payload for the UI 'LD details' overlay (last generate: sent + received).
    /// Summarizes the Agent Graph walk for the completion-style drawer.
    /// </summary>
    private static Dictionary<string, object?> BuildLdTransaction(
        Persona persona,
        string action,
        string storiesText,
        string specialist,
        bool graphEnabled,
        string provider,
        string model,
        List<Dictionary<string, string>> messages,
        AgentGraphDefinition? graph)
    {
        var gk = GraphKey();
        string? variationKey = null;
        int? version = null;
        try
        {
            var flag = graph?.GetConfig();
            var meta = flag?.Meta;
            if (meta != null)
            {
                variationKey = string.IsNullOrWhiteSpace(meta.VariationKey) ? null : meta.VariationKey;
                version = meta.Version;
            }
        }
        catch
        {
            /* best-effort */
        }

        return new Dictionary<string, object?>
        {
            ["sent"] = new Dictionary<string, object?>
            {
                ["configKey"] = gk,
                ["context"] = ContextAsMap(persona, action),
                ["variables"] = new Dictionary<string, object?>
                {
                    ["stories"] = storiesText,
                    ["action"] = action,
                    ["specialist"] = specialist,
                    ["assessKey"] = NodeKey("assess"),
                    ["specialistKey"] = NodeKey(specialist),
                    ["finalizeKey"] = NodeKey("finalize"),
                },
                ["sdkDefault"] = new Dictionary<string, object?>
                {
                    ["description"] =
                        "Agent Graph walk (assess → specialist → finalize); " +
                        "SDK defaults used when a node/graph key is missing.",
                    ["enabled"] = true,
                    ["model"] = DefaultOllamaModel(),
                    ["provider"] = "Custom",
                    ["messages"] = new List<Dictionary<string, string>>
                    {
                        new()
                        {
                            ["role"] = "system",
                            ["content"] = "Agent Graph classroom walk — assess, specialist, finalize.",
                        },
                    },
                },
            },
            ["received"] = new Dictionary<string, object?>
            {
                ["fallback"] = !graphEnabled,
                ["mode"] = "agent-graph",
                ["enabled"] = graphEnabled,
                ["configKey"] = gk,
                ["variationKey"] = variationKey,
                ["version"] = version,
                ["reason"] = graphEnabled ? null : "graph disabled/missing — local node walk",
                ["provider"] = provider,
                ["model"] = model,
                ["messages"] = messages,
            },
        };
    }

    private static LdAiAgentConfigDefault AgentDefault(string instructionsFile) =>
        LdAiAgentConfigDefault.New()
            .Enable()
            .SetModelName(DefaultOllamaModel())
            .SetModelProviderName("Custom")
            .SetInstructions(ReadMessageFile(instructionsFile).Trim())
            .Build();

    private static string DefaultInstructionsFile(string role) => role switch
    {
        "assess" => "assess-instructions.txt",
        "report" => "report-baseline-instructions.txt",
        "questions" => "questions-instructions.txt",
        "good" => "good-instructions.txt",
        "joke" => "joke-instructions.txt",
        "finalize" => "finalize-instructions.txt",
        _ => throw new ArgumentOutOfRangeException(nameof(role), role, "unknown role"),
    };

    /// <summary>
    /// Evaluate one agent-mode node. LaunchDarkly: AgentConfig + instructions.
    /// </summary>
    private static LdAiAgentConfig EvaluateAgent(string role, Context context, Dictionary<string, object> variables)
        => AiClient().AgentConfig(NodeKey(role), context, AgentDefault(DefaultInstructionsFile(role)), variables);

    private static (string Provider, string Model) ResolveRuntime(LdAiAgentConfig config)
    {
        var model = config.Model.Name ?? "";
        var providerName = config.Provider.Name ?? "";
        var pl = providerName.Trim().ToLowerInvariant();
        if (pl is "custom" or "ollama" || model.Contains(':'))
        {
            return ("ollama", model.Length == 0 ? DefaultOllamaModel() : model);
        }
        if (string.IsNullOrWhiteSpace(model)) return ("ollama", DefaultOllamaModel());
        return ("ollama", model);
    }

    private static string Clip(string? text, int maxLen = 55)
    {
        var s = Regex.Replace(text ?? "", @"\s+", " ").Trim();
        if (s.Length <= maxLen) return s;
        return s[..Math.Max(0, maxLen - 1)] + "…";
    }

    private static JsonElement? ParseJsonObject(string? raw)
    {
        var text = (raw ?? "").Trim();
        var match = Regex.Match(text, @"\{[\s\S]*\}");
        if (!match.Success) return null;
        try
        {
            using var doc = JsonDocument.Parse(match.Value);
            return doc.RootElement.ValueKind == JsonValueKind.Object ? doc.RootElement.Clone() : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static JsonElement? GetProp(JsonElement? obj, string name)
        => obj is { ValueKind: JsonValueKind.Object } o && o.TryGetProperty(name, out var v) ? v : null;

    private static double Clamp01(JsonElement? el, double fallback = 0.5)
    {
        if (el is not { } e) return fallback;
        double n;
        if (e.ValueKind == JsonValueKind.Number && e.TryGetDouble(out var d)) n = d;
        else if (e.ValueKind == JsonValueKind.String && double.TryParse(e.GetString(), out var s)) n = s;
        else return fallback;
        return Math.Max(0.0, Math.Min(1.0, n));
    }

    /// <summary>Pull candidate questions from specialist text (for scoring only).</summary>
    private static List<string> ExtractQuestionsFromDraft(string? draft)
    {
        var outList = new List<string>();
        foreach (var rawLine in (draft ?? "").Split('\n'))
        {
            var s = rawLine.Trim();
            if (s.Length == 0) continue;
            s = Regex.Replace(s, @"^[-*•]+\s*", "");
            s = Regex.Replace(s, @"^\d+[.)]\s*", "");
            if (!s.Contains('?')) continue;
            if (s.Length < 12) continue;
            outList.Add(s);
            if (outList.Count >= 5) break;
        }
        return outList;
    }

    /// <summary>
    /// App-side scorer: gap + ground in [0,1]. Does not change specialist output.
    ///
    /// LaunchDarkly: Library tool key score-question-gap (attached for Monitoring).
    /// https://launchdarkly.com/docs/home/agentcontrol/tools
    /// </summary>
    private static async Task<(double Gap, double Ground)> ScoreQuestionGapAsync(
        string question, string headlines, string model, CancellationToken ct)
    {
        var user =
            "Score this follow-up question against the headlines.\n" +
            "Return JSON only: {\"gap\":0.0,\"ground\":0.0}\n" +
            "- gap: how poorly the headlines answer it (1.0 = large information gap).\n" +
            "- ground: how well the question fits this headline domain (1.0 = on-topic).\n" +
            "Use decimals in [0,1].\n\n" +
            $"QUESTION:\n{question}\n\n" +
            $"HEADLINES:\n{headlines}\n";
        var messages = new List<Dictionary<string, string>>
        {
            new() { ["role"] = "system", ["content"] = "You are a strict scoring tool. Output JSON only." },
            new() { ["role"] = "user", ["content"] = user },
        };
        var raw = await OllamaCompleteAsync(model, messages, 0.0, ct);
        var obj = ParseJsonObject(raw);
        return (Clamp01(GetProp(obj, "gap"), 0.5), Clamp01(GetProp(obj, "ground"), 0.5));
    }

    /// <summary>App-side easter-egg scorer: corniness in [0,1].</summary>
    private static async Task<double> ScoreJokeCornyAsync(string joke, string model, CancellationToken ct)
    {
        var user =
            "Score how corny this joke is.\n" +
            "Return JSON only: {\"corny\":0.0}\n" +
            "0.0 = dry/subtle; 1.0 = very corny dad-joke energy. Decimal in [0,1].\n\n" +
            $"JOKE:\n{joke}\n";
        var messages = new List<Dictionary<string, string>>
        {
            new() { ["role"] = "system", ["content"] = "You are a whimsical scoring tool. Output JSON only." },
            new() { ["role"] = "user", ["content"] = user },
        };
        var raw = await OllamaCompleteAsync(model, messages, 0.0, ct);
        return Clamp01(GetProp(ParseJsonObject(raw), "corny"), 0.5);
    }

    /// <summary>Trace display: score lives in the tool name (teaching visibility).</summary>
    private static string FormatToolNameWithScore(string baseName, double score) => $"{baseName}:{score:F2}";

    /// <summary>Return (specialist, reason). Invalid/unknown → report.</summary>
    private static (string Specialist, string Reason) ParseAssessJson(string raw, string actionHint)
    {
        var specialist = ValidSpecialists.Contains(actionHint) ? actionHint : "report";
        var reason = "fallback";
        var obj = ParseJsonObject(raw);
        if (obj != null)
        {
            var candEl = GetProp(obj, "specialist");
            var cand = (candEl is { ValueKind: JsonValueKind.String } ? candEl.Value.GetString() : null)
                ?.Trim().ToLowerInvariant() ?? "";
            if (ValidSpecialists.Contains(cand)) specialist = cand;
            var reasonEl = GetProp(obj, "reason");
            var reasonText = (reasonEl is { ValueKind: JsonValueKind.String } ? reasonEl.Value.GetString() : null)
                ?.Trim();
            if (!string.IsNullOrEmpty(reasonText)) reason = reasonText;
            return (specialist, reason);
        }
        if (ValidSpecialists.Contains(actionHint))
        {
            return (actionHint, "assess parse failed; used UI action hint");
        }
        return ("report", "assess parse failed; fall through to report");
    }

    // ---------------------------------------------------------------------
    // Agent graph edge validation
    //
    // LaunchDarkly: AgentGraphDefinition.GetChildNodes walks the evaluated graph's
    // outgoing edges. See docs link in the module prelude above.
    // ---------------------------------------------------------------------

    private static List<string> GraphOutgoingTargets(AgentGraphDefinition? graph, string sourceKey)
    {
        if (graph == null || !graph.Enabled) return new List<string>();
        var children = graph.GetChildNodes(sourceKey);
        var outList = new List<string>();
        foreach (var node in children)
        {
            if (!string.IsNullOrEmpty(node.Key)) outList.Add(node.Key);
        }
        return outList;
    }

    /// <summary>
    /// Validate preferred specialist against assess → * edges on the LD graph.
    /// Returns (specialist, note, edgeValidated). If the graph is disabled, keeps
    /// preferred and sets edgeValidated=false.
    /// </summary>
    private static (string Specialist, string Note, bool EdgeValidated) ResolveSpecialistAgainstEdges(
        AgentGraphDefinition? graph, string preferred, AiGraphTracker tracker)
    {
        var pref = ValidSpecialists.Contains(preferred) ? preferred : "report";
        var assessKey = NodeKey("assess");
        var preferredKey = NodeKey(pref);

        if (graph == null || !graph.Enabled)
        {
            return (pref, "graph disabled — skip edge validation", false);
        }

        var children = GraphOutgoingTargets(graph, assessKey);
        if (children.Count == 0)
        {
            return (pref, "assess has no outgoing edges — using preferred", false);
        }

        if (children.Contains(preferredKey))
        {
            return (pref, $"edge ok: assess → {pref}", true);
        }

        // Invalid handoff — prefer report if that edge exists, else first child.
        TryTrackHandoffFailure(tracker, assessKey, preferredKey);

        var reportKey = NodeKey("report");
        if (children.Contains(reportKey))
        {
            TryTrackRedirect(tracker, assessKey, reportKey);
            return ("report", $"no edge assess → {pref}; redirected to report", true);
        }

        var fallbackKey = children[0];
        var fallbackRole = RoleFromNodeKey(fallbackKey) ?? "report";
        if (!ValidSpecialists.Contains(fallbackRole)) fallbackRole = "report";
        TryTrackRedirect(tracker, assessKey, fallbackKey);
        return (fallbackRole, $"no edge assess → {pref}; redirected to {fallbackRole}", true);
    }

    /// <summary>Check specialist → finalize edge when the graph is enabled.</summary>
    private static (bool Ok, string Note) FinalizeEdgeOk(AgentGraphDefinition? graph, string specialistKey)
    {
        var finalizeKey = NodeKey("finalize");
        if (graph == null || !graph.Enabled)
        {
            return (true, "graph disabled — skip finalize edge check");
        }
        var children = GraphOutgoingTargets(graph, specialistKey);
        if (children.Contains(finalizeKey))
        {
            return (true, $"edge ok: {specialistKey} → finalize");
        }
        return (false, $"no edge {specialistKey} → finalize");
    }

    private static void TryTrackInvocationSuccess(AiGraphTracker? tracker)
    {
        if (tracker == null) return;
        try { tracker.TrackInvocationSuccess(); } catch { /* best-effort */ }
    }

    private static void TryTrackInvocationFailure(AiGraphTracker? tracker)
    {
        if (tracker == null) return;
        try { tracker.TrackInvocationFailure(); } catch { /* best-effort */ }
    }

    private static void TryTrackHandoffSuccess(AiGraphTracker? tracker, string from, string to)
    {
        if (tracker == null) return;
        try { tracker.TrackHandoffSuccess(from, to); } catch { /* best-effort */ }
    }

    private static void TryTrackHandoffFailure(AiGraphTracker? tracker, string from, string to)
    {
        if (tracker == null) return;
        try { tracker.TrackHandoffFailure(from, to); } catch { /* best-effort */ }
    }

    private static void TryTrackRedirect(AiGraphTracker? tracker, string from, string to)
    {
        if (tracker == null) return;
        try { tracker.TrackRedirect(from, to); } catch { /* best-effort */ }
    }

    private static void TryTrackPath(AiGraphTracker? tracker, List<string> path)
    {
        if (tracker == null) return;
        try { tracker.TrackPath(path); } catch { /* best-effort */ }
    }

    private static void TryTrackDuration(AiGraphTracker? tracker, double durationMs)
    {
        if (tracker == null) return;
        try { tracker.TrackDuration(durationMs); } catch { /* best-effort */ }
    }

    // ---------------------------------------------------------------------
    // Ollama (local provider — LaunchDarkly does not call the model)
    // ---------------------------------------------------------------------

    private static List<Dictionary<string, string>> MessagesForNode(string? instructions, string userContent) => new()
    {
        new() { ["role"] = "system", ["content"] = string.IsNullOrEmpty(instructions) ? "You are a helpful assistant." : instructions },
        new() { ["role"] = "user", ["content"] = userContent },
    };

    /// <summary>Non-streaming completion (assess / buffered specialist / scorers).</summary>
    private static async Task<string> OllamaCompleteAsync(
        string model, List<Dictionary<string, string>> messages, double temperature, CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var url = $"{host}/api/chat";

        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { model, stream = false, messages, options = new { temperature } }),
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
                $"Ollama request failed ({host}, model={model}): {exc.Message}. " +
                "Is Ollama running, and does `ollama list` include the model?", exc);
        }

        var body = await response.Content.ReadAsStringAsync(ct);
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}, model={model}): HTTP {(int)response.StatusCode}. " +
                "Is Ollama running, and does `ollama list` include the model?");
        }

        using var doc = JsonDocument.Parse(body);
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
        return content;
    }

    private static async IAsyncEnumerable<string> OllamaStreamAsync(
        string model, List<Dictionary<string, string>> messages, double temperature,
        [EnumeratorCancellation] CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        var url = $"{host}/api/chat";

        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(new { model, stream = true, messages, options = new { temperature } }),
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
                $"Ollama stream failed ({host}, model={model}): {exc.Message}. " +
                "Is Ollama running, and does `ollama list` include the model?", exc);
        }

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama stream failed ({host}, model={model}): HTTP {(int)response.StatusCode}. " +
                "Is Ollama running, and does `ollama list` include the model?");
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

    /// <summary>
    /// Stream Ollama tokens for finalize. Kept as its own async iterator because C#
    /// disallows <c>yield return</c> inside a try block that has a catch clause.
    /// </summary>
    private static async IAsyncEnumerable<(Dictionary<string, object?> Evt, string? Text)> FinalizeStreamAsync(
        string model, List<Dictionary<string, string>> messages, Stopwatch sw, Metrics metrics,
        [EnumeratorCancellation] CancellationToken ct)
    {
        var textParts = new StringBuilder();
        var first = true;
        var enumerator = OllamaStreamAsync(model, messages, 0.0, ct).GetAsyncEnumerator(ct);
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
                yield return (new Dictionary<string, object?> { ["type"] = "token", ["text"] = chunk }, null);
            }
        }
        finally
        {
            await enumerator.DisposeAsync();
        }

        metrics.FinishReason = "stop";
        yield return (new Dictionary<string, object?> { ["type"] = "_complete" }, textParts.ToString());
    }

    // ---------------------------------------------------------------------
    // Generation — assess → specialist → (optional scorers) → finalize
    // ---------------------------------------------------------------------

    /// <summary>
    /// Run assess → specialist → finalize.
    ///
    /// SSE event types: run, status, info, assess, route, specialist, tool, model,
    /// token, finalize, metrics, error, done — mirrors ../python/agent_core.py exactly
    /// so the shared wwwroot/index.html Trace UI works unmodified across ports.
    /// </summary>
    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        string action,
        List<Dictionary<string, object?>>? tickerResults,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        action = (action ?? "report").Trim().ToLowerInvariant();
        if (!ValidSpecialists.Contains(action)) action = "report";

        var storiesText = FormatStories(tickerResults);
        var hasRealStories = (tickerResults ?? new()).Any(b =>
            JsonUtil.AsDictList(b.GetValueOrDefault("stories")).Count > 0);

        if (ActionsNeedingStories.Contains(action) && !hasRealStories)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = "Load stories first (Get Stories), then try this action again.",
            };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();
        var context = BuildContext(persona, action);

        // --- Graph evaluate (topology + tracker) -----------------------------
        // LaunchDarkly: AgentGraph — see docs link in module prelude.
        AgentGraphDefinition? graph = null;
        Exception? graphError = null;
        try
        {
            graph = AiClient().AgentGraph(GraphKey(), context);
        }
        catch (Exception exc)
        {
            graphError = exc;
        }

        if (graphError != null)
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"LaunchDarkly agent_graph failed: {graphError.Message}",
            };
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var graphTracker = graph!.CreateTracker();
        var graphEnabled = graph.Enabled;

        yield return new Dictionary<string, object?>
        {
            ["type"] = "run",
            ["action"] = action,
            ["personaId"] = persona.Id,
            ["personaName"] = persona.Name,
            ["graphKey"] = GraphKey(),
            ["graphEnabled"] = graphEnabled,
        };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "status",
            ["message"] = $"Graph {GraphKey()} " +
                (graphEnabled ? "enabled" : "disabled/missing — using node configs + local walk"),
        };

        var path = new List<string> { NodeKey("assess") };

        // --- Humor easter egg (joke path only) --------------------------------
        if (action == "joke")
        {
            var level = HumorLevelFor(persona);
            yield return new Dictionary<string, object?>
            {
                ["type"] = "info",
                ["message"] = $"Setting humor level to {level}%",
                ["kind"] = "humor",
            };
        }

        // --- Step 1: assess -----------------------------------------------------
        yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "assess — choosing specialist…" };

        LdAiAgentConfig? assessCfg = null;
        Exception? assessCfgError = null;
        try
        {
            assessCfg = EvaluateAgent("assess", context, new Dictionary<string, object>
            {
                ["action"] = action,
                ["stories"] = hasRealStories ? storiesText : "(none)",
            });
        }
        catch (Exception exc)
        {
            assessCfgError = exc;
        }

        if (assessCfgError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = $"assess agent_config failed: {assessCfgError.Message}" };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var (_, assessModel) = ResolveRuntime(assessCfg!);
        var assessUser =
            $"UI action hint: {action}\n" +
            $"Headlines present: {(hasRealStories ? "yes" : "no")}\n\n" +
            $"HEADLINES:\n{(hasRealStories ? storiesText : "(none)")}\n\n" +
            "Return JSON only.";

        string? assessRaw = null;
        Exception? assessRawError = null;
        try
        {
            assessRaw = await OllamaCompleteAsync(assessModel, MessagesForNode(assessCfg!.Instructions, assessUser), 0.0, ct);
        }
        catch (Exception exc)
        {
            assessRawError = exc;
        }

        if (assessRawError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = assessRawError.Message };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var (parsedSpecialist, parsedReason) = ParseAssessJson(assessRaw!, action);
        var specialist = parsedSpecialist;
        var reason = parsedReason;
        // Prefer UI action when valid (teaching: button intent wins if assess drifts).
        if (ValidSpecialists.Contains(action) && specialist != action)
        {
            reason = $"{reason} (UI hint={action}; using hint)";
            specialist = action;
        }

        // LaunchDarkly: validate assess → specialist against graph edges.
        var (resolvedSpecialist, edgeNote, edgeOk) = ResolveSpecialistAgainstEdges(graph, specialist, graphTracker);
        specialist = resolvedSpecialist;
        if (!string.IsNullOrEmpty(edgeNote))
        {
            if (!reason.Contains(edgeNote, StringComparison.Ordinal)) reason = $"{reason}; {edgeNote}";
            yield return new Dictionary<string, object?>
            {
                ["type"] = "info",
                ["message"] = edgeNote,
                ["kind"] = "edge",
                ["validated"] = edgeOk,
            };
        }

        var specialistKey = NodeKey(specialist);
        path.Add(specialistKey);
        TryTrackHandoffSuccess(graphTracker, NodeKey("assess"), specialistKey);

        yield return new Dictionary<string, object?>
        {
            ["type"] = "assess",
            ["specialist"] = specialist,
            ["reason"] = reason,
            ["clip"] = Clip($"{specialist}: {reason}"),
            ["model"] = assessModel,
            ["configKey"] = NodeKey("assess"),
            ["edgeValidated"] = edgeOk,
        };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "route",
            ["specialist"] = specialist,
            ["reason"] = reason,
            ["message"] = $"Selected specialist: {specialist}",
            ["edgeValidated"] = edgeOk,
        };

        // --- Step 2: specialist ---------------------------------------------------
        yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = $"{specialist} — running specialist…" };

        var variables = new Dictionary<string, object>
        {
            ["action"] = action,
            ["stories"] = hasRealStories ? storiesText : "(none)",
            ["specialist"] = specialist,
        };
        string? questionsList = null;
        if (specialist == "questions")
        {
            questionsList = LoadQuestionsList();
            variables["questions"] = questionsList;
        }

        LdAiAgentConfig? specCfg = null;
        Exception? specCfgError = null;
        try
        {
            // report uses persona targeting on the same key; other nodes are single-variation.
            specCfg = EvaluateAgent(specialist, context, variables);
        }
        catch (Exception exc)
        {
            specCfgError = exc;
        }

        if (specCfgError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = $"{specialist} agent_config failed: {specCfgError.Message}" };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var (_, specModel) = ResolveRuntime(specCfg!);

        string specUser;
        double specTemperature;
        if (specialist == "questions")
        {
            specUser =
                $"CANDIDATE QUESTIONS:\n{questionsList}\n\n" +
                $"HEADLINES:\n{storiesText}\n\n" +
                "Return the top 2–3 gap-priority questions with a short why each.";
            specTemperature = 0.0;
        }
        else if (specialist == "good")
        {
            specUser =
                $"HEADLINES:\n{storiesText}\n\n" +
                "Produce ## Good and ## Bad sections now (both required).";
            specTemperature = 0.0;
        }
        else if (specialist == "joke")
        {
            var tickers = new List<string>();
            foreach (var row in tickerResults ?? new List<Dictionary<string, object?>>())
            {
                var tk = (row.GetValueOrDefault("ticker") as string ?? "").Trim();
                if (tk.Length > 0) tickers.Add(tk);
            }
            // Tickers / headlines are optional upside — joke works with none.
            var extras = new List<string>();
            if (tickers.Count > 0)
            {
                extras.Add($"Optional tickers (use lightly if you want): {string.Join(", ", tickers)}");
            }
            if (hasRealStories)
            {
                extras.Add("Optional headlines (use lightly if you want):\n" + Clip(storiesText, 400));
            }
            var angle = JokeAngleHints[Random.Shared.Next(JokeAngleHints.Length)];
            extras.Add(
                $"Variety nudge (optional inspiration, not a script): lean toward \u201c{angle}\u201d " +
                "or another fresh angle — prefer a different setup than the most common one.");
            var bonus = extras.Count > 0 ? "\n\n" + string.Join("\n\n", extras) : "";
            specUser =
                "Tell a short market/investing joke now. " +
                "Aim for variety across runs. Do not require tickers or headlines." +
                bonus;
            specTemperature = JokeTemperature();
            yield return new Dictionary<string, object?>
            {
                ["type"] = "info",
                ["message"] = $"Joke sampling temperature={specTemperature:F2}; angle hint \u201c{angle}\u201d",
                ["kind"] = "joke-variety",
            };
        }
        else
        {
            specUser = $"HEADLINES:\n{storiesText}\n\nProduce the {specialist} output now.";
            specTemperature = 0.0;
        }

        string? specialistDraft = null;
        Exception? specDraftError = null;
        try
        {
            specialistDraft = await OllamaCompleteAsync(specModel, MessagesForNode(specCfg!.Instructions, specUser), specTemperature, ct);
        }
        catch (Exception exc)
        {
            specDraftError = exc;
        }

        if (specDraftError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = specDraftError.Message };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        yield return new Dictionary<string, object?>
        {
            ["type"] = "specialist",
            ["specialist"] = specialist,
            ["clip"] = Clip(specialistDraft),
            ["model"] = specModel,
            ["configKey"] = specialistKey,
        };

        // --- Optional scorers (Trace visibility; outcomes unchanged) --------------
        // LaunchDarkly: Library tools + TrackToolCall
        // https://launchdarkly.com/docs/home/agentcontrol/tools
        ILdAiConfigTracker? nodeTracker = null;
        try { nodeTracker = specCfg!.CreateTracker(); } catch { /* best-effort */ }

        if (specialist == "questions")
        {
            yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "Scoring questions (gap / ground)…" };
            var questions = ExtractQuestionsFromDraft(specialistDraft);
            if (questions.Count == 0)
            {
                yield return new Dictionary<string, object?>
                {
                    ["type"] = "info",
                    ["message"] = "No questions parsed for scoring — Trace skips tool scores.",
                    ["kind"] = "tool",
                };
            }
            var callIndex = 0;
            var scoreModel = string.IsNullOrEmpty(specModel) ? DefaultOllamaModel() : specModel;
            foreach (var q in questions)
            {
                var (gap, ground) = await ScoreQuestionGapAsync(q, storiesText, scoreModel, ct);
                var gapName = FormatToolNameWithScore(ToolQuestionGap, gap);
                var groundName = FormatToolNameWithScore("score-question-ground", ground);
                callIndex++;
                if (nodeTracker != null) { try { nodeTracker.TrackToolCall(ToolQuestionGap); } catch { /* best-effort */ } }
                yield return new Dictionary<string, object?>
                {
                    ["type"] = "tool",
                    ["name"] = gapName,
                    ["toolKey"] = ToolQuestionGap,
                    ["score"] = gap,
                    ["scores"] = new Dictionary<string, object?> { ["gap"] = gap, ["ground"] = ground },
                    ["args"] = new Dictionary<string, object?> { ["question"] = q },
                    ["result"] = new Dictionary<string, object?> { ["gap"] = gap, ["ground"] = ground },
                    ["callIndex"] = callIndex,
                    ["clip"] = Clip(q, 40),
                };
                callIndex++;
                yield return new Dictionary<string, object?>
                {
                    ["type"] = "tool",
                    ["name"] = groundName,
                    ["toolKey"] = "score-question-ground",
                    ["score"] = ground,
                    ["args"] = new Dictionary<string, object?> { ["question"] = q },
                    ["result"] = new Dictionary<string, object?> { ["ground"] = ground },
                    ["callIndex"] = callIndex,
                    ["clip"] = Clip(q, 40),
                };
            }
        }
        else if (specialist == "joke")
        {
            yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "Scoring joke corniness…" };
            var scoreModel = string.IsNullOrEmpty(specModel) ? DefaultOllamaModel() : specModel;
            var corny = await ScoreJokeCornyAsync(specialistDraft!, scoreModel, ct);
            var cornyName = FormatToolNameWithScore(ToolJokeCorny, corny);
            if (nodeTracker != null) { try { nodeTracker.TrackToolCall(ToolJokeCorny); } catch { /* best-effort */ } }
            yield return new Dictionary<string, object?>
            {
                ["type"] = "tool",
                ["name"] = cornyName,
                ["toolKey"] = ToolJokeCorny,
                ["score"] = corny,
                ["args"] = new Dictionary<string, object?> { ["joke"] = Clip(specialistDraft, 120) },
                ["result"] = new Dictionary<string, object?> { ["corny"] = corny },
                ["callIndex"] = 1,
                ["clip"] = Clip(specialistDraft, 40),
            };
            var high = CornyHighThreshold();
            var low = CornyLowThreshold();
            var level = HumorLevelFor(persona);
            if (corny >= high)
            {
                var tip = $"Corny {corny:F2} \u2265 {high:F2} — recommend lowering humor setting (currently {level}%).";
                yield return new Dictionary<string, object?> { ["type"] = "info", ["message"] = tip, ["kind"] = "humor-tip" };
            }
            else if (corny <= low)
            {
                var tip = $"Corny {corny:F2} \u2264 {low:F2} — recommend raising humor setting (currently {level}%).";
                yield return new Dictionary<string, object?> { ["type"] = "info", ["message"] = tip, ["kind"] = "humor-tip" };
            }
        }

        var finalizeKey = NodeKey("finalize");
        var (finOk, finEdgeNote) = FinalizeEdgeOk(graph, specialistKey);
        yield return new Dictionary<string, object?>
        {
            ["type"] = "info",
            ["message"] = finEdgeNote,
            ["kind"] = "edge",
            ["validated"] = finOk,
        };
        if (!finOk)
        {
            TryTrackHandoffFailure(graphTracker, specialistKey, finalizeKey);
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] = $"Graph has no edge from {specialistKey} to {finalizeKey}. " +
                    "Fix the Agent Graph topology in LaunchDarkly.",
            };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done", ["specialist"] = specialist, ["action"] = action };
            yield break;
        }

        path.Add(finalizeKey);
        TryTrackHandoffSuccess(graphTracker, specialistKey, finalizeKey);

        // --- Step 3: finalize (stream to Response) -------------------------------
        // Joke drafts: pass through (still evaluate finalize + track the edge).
        // Small models otherwise invent a "market briefing" after the punchline when
        // headlines are in context (often from a prior Get Stories / localStorage).
        yield return new Dictionary<string, object?> { ["type"] = "status", ["message"] = "finalize — polishing…" };

        LdAiAgentConfig? finCfg = null;
        Exception? finCfgError = null;
        try
        {
            finCfg = EvaluateAgent("finalize", context, new Dictionary<string, object>
            {
                ["action"] = action,
                ["specialist"] = specialist,
                ["draft"] = specialistDraft!,
                ["stories"] = specialist == "joke"
                    ? "(omitted for joke)"
                    : (hasRealStories ? storiesText : "(none)"),
            });
        }
        catch (Exception exc)
        {
            finCfgError = exc;
        }

        if (finCfgError != null)
        {
            yield return new Dictionary<string, object?> { ["type"] = "error", ["message"] = $"finalize agent_config failed: {finCfgError.Message}" };
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var (_, finModel) = ResolveRuntime(finCfg!);

        // Drawer messages: joke streams the specialist draft; otherwise finalize polish.
        List<Dictionary<string, string>> drawerMessages;
        string drawerModel;
        if (specialist == "joke")
        {
            drawerMessages = MessagesForNode(specCfg!.Instructions, specUser);
            drawerModel = specModel;
        }
        else
        {
            var finUser =
                $"Original action: {action}\n" +
                $"Specialist: {specialist}\n\n" +
                $"SPECIALIST DRAFT:\n{specialistDraft}\n\n" +
                "Return the final polished text only.";
            drawerMessages = MessagesForNode(finCfg!.Instructions, finUser);
            drawerModel = finModel;
        }

        var ldTx = BuildLdTransaction(
            persona,
            action,
            hasRealStories ? storiesText : "(none)",
            specialist,
            graphEnabled,
            "ollama",
            drawerModel,
            drawerMessages,
            graph);

        yield return new Dictionary<string, object?>
        {
            ["type"] = "model",
            ["provider"] = "ollama",
            ["model"] = finModel,
            ["configKey"] = finalizeKey,
            ["phase"] = "finalize",
            ["ldTransaction"] = ldTx,
        };

        var finalParts = new StringBuilder();
        var finalizeFailed = false;

        if (specialist == "joke")
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "info",
                ["message"] = "joke finalize: pass-through specialist draft (avoids small-model expansion into briefings)",
                ["kind"] = "finalize-passthrough",
            };
            var draft = specialistDraft ?? "";
            const int step = 48;
            var first = true;
            for (var i = 0; i < Math.Max(draft.Length, 1); i += step)
            {
                if (i >= draft.Length) break;
                var len = Math.Min(step, draft.Length - i);
                var chunk = draft.Substring(i, len);
                if (first)
                {
                    first = false;
                    metrics.TtftMs = (long)sw.Elapsed.TotalMilliseconds;
                }
                finalParts.Append(chunk);
                yield return new Dictionary<string, object?> { ["type"] = "token", ["text"] = chunk };
            }
        }
        else
        {
            await foreach (var (evt, text) in FinalizeStreamAsync(finModel, drawerMessages, sw, metrics, ct))
            {
                if (evt.GetValueOrDefault("type") as string == "_complete")
                {
                    if (text != null) finalParts.Clear().Append(text);
                    continue;
                }
                if (evt.GetValueOrDefault("type") as string == "error")
                {
                    finalizeFailed = true;
                }
                yield return evt;
            }
        }

        if (finalizeFailed || metrics.FinishReason == "error")
        {
            TryTrackInvocationFailure(graphTracker);
            yield return new Dictionary<string, object?> { ["type"] = "done" };
            yield break;
        }

        var finalText = finalParts.ToString();
        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        if (string.IsNullOrEmpty(metrics.FinishReason))
        {
            metrics.FinishReason = "stop";
        }

        yield return new Dictionary<string, object?>
        {
            ["type"] = "finalize",
            ["clip"] = Clip(finalText),
            ["model"] = finModel,
            ["configKey"] = finalizeKey,
        };

        TryTrackPath(graphTracker, path);
        TryTrackDuration(graphTracker, metrics.LatencyMs ?? 0);
        TryTrackInvocationSuccess(graphTracker);

        // Per-node success trackers (best-effort)
        try { assessCfg!.CreateTracker().TrackSuccess(); } catch { /* best-effort */ }
        try
        {
            if (nodeTracker != null) nodeTracker.TrackSuccess();
            else specCfg!.CreateTracker().TrackSuccess();
        }
        catch { /* best-effort */ }
        try { finCfg!.CreateTracker().TrackSuccess(); } catch { /* best-effort */ }

        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?>
        {
            ["type"] = "done",
            ["path"] = path,
            ["specialist"] = specialist,
            ["action"] = action,
            ["ldTransaction"] = ldTx,
        };
    }
}
