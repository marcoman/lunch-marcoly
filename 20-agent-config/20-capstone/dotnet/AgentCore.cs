using System.Net.Http.Json;
using System.Text.Json;
using System.Text.RegularExpressions;
using LaunchDarkly.Sdk;
using LaunchDarkly.Sdk.Server;
using LaunchDarkly.Sdk.Server.Ai;
using LaunchDarkly.Sdk.Server.Ai.Adapters;
using LaunchDarkly.Sdk.Server.Ai.Config;
using LaunchDarkly.Sdk.Server.Ai.Graph;
using LaunchDarkly.Sdk.Server.Ai.Interfaces;
using LaunchDarkly.Sdk.Server.Ai.Tracking;

namespace Capstone;

/// <summary>
/// Capstone walk: assess → specialist → judges → tools → finalize.
///
/// LaunchDarkly insertion (read first):
///   GenerateStreamAsync() → AgentGraph + AgentConfig per node
///   then JudgeConfig on the specialist draft
///   then TrackToolCall for each checked tool
///   thumbs use the specialist tracker's resumption token
/// Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
/// Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
/// Docs: https://launchdarkly.com/docs/home/agentcontrol/tools
/// Keywords: AgentControl · agent graphs · Library tools · judges · feedback
/// </summary>
public static class AgentCore
{
    private const string DefaultGraphKey = "equity-briefing-capstone";
    private static readonly string[] ToolOrder = ["pig-latin", "rot13", "joke-tagline"];
    private static readonly HashSet<string> ValidSpecialists = ["report", "questions", "good"];
    private static readonly Dictionary<string, int> HumorLevel = new()
    {
        ["conservative-charlie"] = 25,
        ["anonymous-amelia"] = 50,
        ["thoughtless-toby"] = 90,
    };
    private static readonly HashSet<string> EnglishWords = new(
        "the and for that this with from have are was were not but its has will can you your their they been into over after more than also about would could should which there these those them then when what where while stock stocks market shares price prices growth revenue earnings company companies investor investors today according said says".Split(' '));
    private static readonly Dictionary<string, Dictionary<string, string>> Jokes = new()
    {
        ["en"] = new()
        {
            ["conservative-charlie"] = "The market can stay irrational longer than a footnote.",
            ["anonymous-amelia"] = "Diversification is the joke that still pays rent.",
            ["thoughtless-toby"] = "Buy high, sell higher, and call the difference research.",
        },
        ["es"] = new()
        {
            ["conservative-charlie"] = "El mercado puede seguir irracional más que una nota al pie.",
            ["anonymous-amelia"] = "Diversificar es el chiste que igual paga el alquiler.",
            ["thoughtless-toby"] = "Compra caro, vende más caro, y llama investigación a la diferencia.",
        },
    };

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(180) };
    private static LdClient? _ldClient;
    private static LdAiClient? _aiClient;

    public sealed record Persona(string Id, string Name, string Profile, bool Anonymous);

    public static readonly Persona[] Personas =
    [
        new("conservative-charlie", "Conservative Charlie", "conservative", false),
        new("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker", false),
    ];

    public static IReadOnlyList<string> Tools => ToolOrder;

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    public static string GraphKey()
    {
        var raw = Environment.GetEnvironmentVariable("LD_GRAPH_KEY")?.Trim();
        return string.IsNullOrEmpty(raw) ? DefaultGraphKey : raw;
    }

    public static string NodeKey(string role)
    {
        var envName = role switch
        {
            "assess" => "LD_NODE_ASSESS",
            "report" => "LD_NODE_REPORT",
            "questions" => "LD_NODE_QUESTIONS",
            "good" => "LD_NODE_GOOD",
            "finalize" => "LD_NODE_FINALIZE",
            _ => "",
        };
        var raw = string.IsNullOrEmpty(envName) ? "" : Environment.GetEnvironmentVariable(envName)?.Trim();
        if (!string.IsNullOrEmpty(raw)) return raw;
        return $"equity-briefing-capstone-{role}";
    }

    public static string JudgeKey(string which) => which == "fidelity"
        ? EnvOr("LD_JUDGE_FIDELITY_KEY", "equity-briefing-capstone-source-fidelity")
        : EnvOr("LD_JUDGE_DISCIPLINE_KEY", "equity-briefing-capstone-recommendation-discipline");

    public static void InitLaunchDarkly()
    {
        if (_aiClient != null) return;
        var sdkKey = Environment.GetEnvironmentVariable("LD_SDK_KEY")?.Trim() ?? "";
        if (sdkKey.Length == 0)
        {
            throw new InvalidOperationException("LD_SDK_KEY is required. Export a server-side SDK key before starting the capstone.");
        }
        var client = new LdClient(Configuration.Builder(sdkKey).StartWaitTime(TimeSpan.FromSeconds(5)).Build());
        if (!client.Initialized)
        {
            throw new InvalidOperationException("LaunchDarkly client failed to initialize within 5s.");
        }
        _ldClient = client;
        _aiClient = new LdAiClient(new LdClientAdapter(client));
    }

    private static LdAiClient Ai() => _aiClient ?? throw new InvalidOperationException("Call InitLaunchDarkly first.");

    private static string EnvOr(string name, string fallback)
    {
        var raw = Environment.GetEnvironmentVariable(name)?.Trim();
        return string.IsNullOrEmpty(raw) ? fallback : raw;
    }

    private static string DefaultModel() => EnvOr("OLLAMA_MODEL", "llama3.2:3b");

    private static double PassThreshold()
    {
        var raw = Environment.GetEnvironmentVariable("JUDGE_PASS_THRESHOLD")?.Trim();
        return double.TryParse(raw, out var value) ? value : 0.65;
    }

    private static string ReadMessage(string name)
    {
        var path = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "rest", "messages", name);
        var dev = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "..", "rest", "messages", name));
        var chosen = File.Exists(dev) ? dev : path;
        if (!File.Exists(chosen))
        {
            chosen = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "rest", "messages", name));
        }
        return File.ReadAllText(chosen);
    }

    private static string InstructionsFile(string role) => role switch
    {
        "assess" => "assess-instructions.txt",
        "report" => "report-baseline-instructions.txt",
        "questions" => "questions-instructions.txt",
        "good" => "good-instructions.txt",
        _ => "finalize-instructions.txt",
    };

    /// <summary>
    /// User context for graph, node, and judge evaluation. Locale selects Spanish variations.
    /// LaunchDarkly: contexts — https://launchdarkly.com/docs/home/contexts
    /// </summary>
    private static Context BuildContext(Persona persona, string action, string locale)
    {
        var builder = Context.Builder(persona.Id)
            .Name(persona.Name)
            .Set("action", action)
            .Set("locale", locale == "es" ? "es" : "en")
            .Set("profile", persona.Profile);
        if (persona.Anonymous) builder.Anonymous(true);
        return builder.Build();
    }

    private static LdAiAgentConfigDefault AgentDefault(string file) =>
        LdAiAgentConfigDefault.New()
            .Enable()
            .SetModelName(DefaultModel())
            .SetModelProviderName("Custom")
            .SetInstructions(ReadMessage(file).Trim())
            .Build();

    /// <summary>Evaluate one agent-mode node. LaunchDarkly: AgentConfig + instructions.</summary>
    private static LdAiAgentConfig EvaluateAgent(string role, Context context, Dictionary<string, object> variables) =>
        Ai().AgentConfig(NodeKey(role), context, AgentDefault(InstructionsFile(role)), variables);

    private static string ResolveModel(LdAiAgentConfig config)
    {
        var name = config.Model.Name ?? "";
        return name.Length == 0 ? DefaultModel() : name;
    }

    private static string Clip(string? text)
    {
        var cleaned = Regex.Replace(text ?? "", @"\s+", " ").Trim();
        return cleaned.Length <= 80 ? cleaned : cleaned[..79] + "…";
    }

    private static async Task<string> OllamaCompleteAsync(string model, List<Dictionary<string, string>> messages, CancellationToken ct)
    {
        var host = (Environment.GetEnvironmentVariable("OLLAMA_HOST") ?? "http://127.0.0.1:11434").TrimEnd('/');
        using var response = await Http.PostAsJsonAsync($"{host}/api/chat", new
        {
            model,
            messages,
            stream = false,
            options = new { temperature = 0 },
        }, ct);
        var body = await response.Content.ReadAsStringAsync(ct);
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException($"Ollama request failed (HTTP {(int)response.StatusCode} {body}).");
        }
        using var doc = JsonDocument.Parse(body);
        if (doc.RootElement.TryGetProperty("message", out var message) &&
            message.TryGetProperty("content", out var content))
        {
            return content.GetString() ?? "";
        }
        return "";
    }

    private static List<Dictionary<string, string>> Messages(string system, string user) =>
    [
        new() { ["role"] = "system", ["content"] = system },
        new() { ["role"] = "user", ["content"] = user },
    ];

    private static (string Specialist, string Reason) ParseAssess(string raw, string actionHint)
    {
        var match = Regex.Match(raw ?? "", @"\{[\s\S]*\}");
        if (match.Success)
        {
            try
            {
                using var doc = JsonDocument.Parse(match.Value);
                var cand = doc.RootElement.TryGetProperty("specialist", out var s) ? s.GetString()?.Trim().ToLowerInvariant() : "";
                var reason = doc.RootElement.TryGetProperty("reason", out var r) ? r.GetString()?.Trim() : "assess";
                if (string.IsNullOrEmpty(reason)) reason = "assess";
                if (!string.IsNullOrEmpty(cand) && ValidSpecialists.Contains(cand)) return (cand, reason);
            }
            catch (JsonException) { /* use the hint */ }
        }
        return ValidSpecialists.Contains(actionHint)
            ? (actionHint, "assess parse failed; used the action")
            : ("report", "assess parse failed; fall through to report");
    }

    private static List<string> Outgoing(AgentGraphDefinition? graph, string sourceKey)
    {
        if (graph == null || !graph.Enabled) return [];
        return graph.GetChildNodes(sourceKey).Select(node => node.Key).Where(key => !string.IsNullOrEmpty(key)).ToList();
    }

    public static string ToPigLatin(string text)
    {
        return Regex.Replace(text ?? "", "[A-Za-z]+", match =>
        {
            var word = match.Value;
            var lower = word.ToLowerInvariant();
            string converted;
            if (Regex.IsMatch(lower, "^[aeiou]")) converted = lower + "yay";
            else
            {
                var split = Regex.Match(lower, "^([^aeiouy]+)(.*)$");
                converted = split.Success && split.Groups[2].Value.Length > 0
                    ? split.Groups[2].Value + split.Groups[1].Value + "ay"
                    : lower + "ay";
            }
            if (char.IsUpper(word[0])) converted = char.ToUpperInvariant(converted[0]) + converted[1..];
            return converted;
        });
    }

    public static string ToRot13(string text)
    {
        var chars = (text ?? "").ToCharArray();
        for (var i = 0; i < chars.Length; i++)
        {
            var ch = chars[i];
            if (ch is >= 'A' and <= 'Z') chars[i] = (char)((ch - 'A' + 13) % 26 + 'A');
            else if (ch is >= 'a' and <= 'z') chars[i] = (char)((ch - 'a' + 13) % 26 + 'a');
        }
        return new string(chars);
    }

    private static string ApplyTool(string key, string text, Persona persona, string locale)
    {
        if (key == "pig-latin") return ToPigLatin(text);
        if (key == "rot13") return ToRot13(text);
        var pack = Jokes.GetValueOrDefault(locale) ?? Jokes["en"];
        var line = pack.GetValueOrDefault(persona.Id) ?? pack["anonymous-amelia"];
        return text.TrimEnd() + "\n\nTagline: " + line;
    }

    private static double PigLatinRatio(string text)
    {
        var words = Regex.Matches(text ?? "", "[A-Za-z]{3,}").Select(m => m.Value).ToList();
        if (words.Count == 0) return 0;
        return words.Count(word => word.EndsWith("ay", StringComparison.OrdinalIgnoreCase)) / (double)words.Count;
    }

    private static double EnglishScore(string text)
    {
        var words = Regex.Matches(text ?? "", "[A-Za-z]{3,}").Select(m => m.Value.ToLowerInvariant()).ToList();
        if (words.Count == 0) return 0;
        return words.Count(EnglishWords.Contains) / (double)words.Count;
    }

    public static (string Text, List<string> Notes) GuardFinalize(string finalText, string transformed, IReadOnlyList<string> tools)
    {
        var ran = tools.ToHashSet();
        var notes = new List<string>();
        var text = (finalText ?? "").Trim();
        if (text.Length == 0) return (transformed, ["finalize returned nothing; kept tool output"]);
        if (ran.Contains("rot13") && EnglishScore(text) - EnglishScore(transformed) > 0.08)
            return (transformed, ["finalize decoded ROT13; kept tool output"]);
        if (ran.Contains("pig-latin") && PigLatinRatio(transformed) - PigLatinRatio(text) > 0.15)
            return (transformed, ["finalize removed Pig Latin; kept tool output"]);
        if (!ran.Contains("pig-latin") && PigLatinRatio(text) - PigLatinRatio(transformed) > 0.15)
            return (transformed, ["finalize added Pig Latin that was not checked; kept tool output"]);
        if (!ran.Contains("rot13") && EnglishScore(ToRot13(text)) - EnglishScore(text) > 0.08)
            return (transformed, ["finalize added ROT13 that was not checked; kept tool output"]);
        var tagline = Regex.Match(transformed ?? "", "^Tagline: .*$", RegexOptions.Multiline).Value;
        if (ran.Contains("joke-tagline"))
        {
            if (tagline.Length > 0 && !text.Contains(tagline, StringComparison.Ordinal))
            {
                text = Regex.Replace(text, "^Tagline:.*$", "", RegexOptions.Multiline).TrimEnd() + "\n\n" + tagline;
                notes.Add("finalize changed the tagline; restored the tool's tagline");
            }
        }
        else if (Regex.IsMatch(text, "^Tagline:", RegexOptions.Multiline) &&
                 !Regex.IsMatch(transformed ?? "", "^Tagline:", RegexOptions.Multiline))
        {
            text = Regex.Replace(text, "^Tagline:.*$", "", RegexOptions.Multiline).TrimEnd();
            notes.Add("finalize added a tagline that was not checked; removed it");
        }
        return (text, notes);
    }

    private static string LanguageLine(string locale) =>
        locale == "es" ? "Write the answer in Spanish." : "Write the answer in English.";

    private static string FinalizeUser(string locale, string specialist, IReadOnlyList<string> tools, string transformed)
    {
        var cipher = tools.Contains("rot13") || tools.Contains("pig-latin");
        var lang = cipher
            ? "A cipher already ran. Copy the draft's wording. Do not translate it back to plain language."
            : LanguageLine(locale);
        string Line(string key, string on, string off) => tools.Contains(key) ? on : off;
        return lang + "\nSpecialist: " + specialist + "\n\nTOOLS THAT RAN:\n"
            + "Pig Latin: " + Line("pig-latin", "applied — keep it", "NOT applied — do not convert any words to Pig Latin") + ".\n"
            + "ROT13: " + Line("rot13", "applied — the draft is already ROT13. Copy every letter. Do not decode it", "NOT applied — do not encode any text") + ".\n"
            + "Joke tagline: " + Line("joke-tagline", "applied — keep the Tagline line exactly as written", "NOT applied — do not add a tagline") + ".\n\n"
            + "DRAFT:\n" + transformed + "\n\nReturn the final text only.";
    }

    private static async Task<Dictionary<string, object?>> RunOneJudgeAsync(
        string key, Persona persona, string locale, string input, string output, CancellationToken ct)
    {
        var metricDefault = key.Contains("fidelity", StringComparison.Ordinal)
            ? "$ld:ai:judge:capstone-source-fidelity"
            : "$ld:ai:judge:capstone-recommendation-discipline";
        var file = key.Contains("fidelity", StringComparison.Ordinal)
            ? "judge-source-fidelity-system.txt"
            : "judge-recommendation-discipline-system.txt";
        try
        {
            // Judges — https://launchdarkly.com/docs/home/agentcontrol/judges
            var config = Ai().JudgeConfig(
                key,
                BuildContext(persona, "judge", locale),
                LdAiJudgeConfigDefault.New()
                    .Enable()
                    .SetModelName(DefaultModel())
                    .SetModelProviderName("Custom")
                    .SetEvaluationMetricKey(metricDefault)
                    .AddMessage(ReadMessage(file).Trim(), LdAiConfigTypes.Role.System)
                    .Build());
            var model = string.IsNullOrWhiteSpace(config.Model.Name) ? DefaultModel() : config.Model.Name;
            var raw = await OllamaCompleteAsync(model, Messages(
                ReadMessage(file).Trim() + "\n\nRespond with JSON: {\"score\":0.0,\"reasoning\":\"...\"}",
                "MESSAGE HISTORY:\n" + input + "\n\nRESPONSE TO EVALUATE:\n" + output
            ), ct);
            var match = Regex.Match(raw, @"\{[\s\S]*\}");
            if (!match.Success) throw new InvalidOperationException("Judge reply was not JSON.");
            using var doc = JsonDocument.Parse(match.Value);
            double? score = doc.RootElement.TryGetProperty("score", out var scoreEl) && scoreEl.ValueKind == JsonValueKind.Number
                ? scoreEl.GetDouble()
                : null;
            var reasoning = doc.RootElement.TryGetProperty("reasoning", out var reasonEl) ? reasonEl.GetString() ?? "" : "";
            var ok = score != null;
            try
            {
                config.CreateTracker().TrackJudgeResult(new JudgeResult(
                    string.IsNullOrWhiteSpace(config.EvaluationMetricKey) ? metricDefault : config.EvaluationMetricKey,
                    score ?? 0,
                    sampled: true,
                    success: ok,
                    judgeConfigKey: key));
            }
            catch { /* monitoring is best-effort */ }
            return new Dictionary<string, object?>
            {
                ["key"] = key,
                ["success"] = ok,
                ["score"] = score,
                ["reasoning"] = reasoning,
                ["passed"] = ok && score >= PassThreshold(),
                ["threshold"] = PassThreshold(),
            };
        }
        catch (Exception exc)
        {
            return new Dictionary<string, object?>
            {
                ["key"] = key,
                ["success"] = false,
                ["score"] = null,
                ["reasoning"] = "",
                ["passed"] = false,
                ["error"] = exc.Message,
                ["threshold"] = PassThreshold(),
            };
        }
    }

    private static Dictionary<string, object?> Summary(string key, LdAiAgentConfig config) => new()
    {
        ["key"] = key,
        ["enabled"] = config.Enabled,
        ["provider"] = config.Provider.Name,
        ["model"] = ResolveModel(config),
    };

    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        string action,
        List<Dictionary<string, object?>> tickerResults,
        List<string> selectedTools,
        string locale,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        if (!ValidSpecialists.Contains(action)) action = "report";
        if (locale != "es") locale = "en";
        var tools = ToolOrder.Where(selectedTools.Contains).ToList();
        var hasStories = tickerResults.Any(block => JsonUtil.AsDictList(block.GetValueOrDefault("stories")).Count > 0);
        if (!hasStories)
        {
            yield return new() { ["type"] = "error", ["message"] = "Load stories first, then generate." };
            yield return new() { ["type"] = "done" };
            yield break;
        }
        var storiesText = YahooNews.FormatStoriesForPrompt(tickerResults);
        var context = BuildContext(persona, action, locale);
        AgentGraphDefinition? graph = null;
        string? graphError = null;
        try
        {
            // Agent graphs — https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
            graph = Ai().AgentGraph(GraphKey(), context);
        }
        catch (Exception exc)
        {
            graphError = exc.Message;
        }
        if (graphError != null || graph == null)
        {
            yield return new() { ["type"] = "error", ["message"] = "agentGraph failed: " + (graphError ?? "no graph") };
            yield return new() { ["type"] = "done" };
            yield break;
        }
        AiGraphTracker? graphTracker = null;
        try { graphTracker = graph!.CreateTracker(); } catch { /* best-effort */ }
        yield return new()
        {
            ["type"] = "run", ["action"] = action, ["locale"] = locale,
            ["personaId"] = persona.Id, ["personaName"] = persona.Name,
            ["graphKey"] = GraphKey(), ["tools"] = tools,
        };

        yield return new() { ["type"] = "status", ["message"] = "assess" };
        var assessCfg = EvaluateAgent("assess", context, new() { ["action"] = action, ["locale"] = locale, ["stories"] = storiesText });
        var assessRaw = await OllamaCompleteAsync(ResolveModel(assessCfg), Messages(
            assessCfg.Instructions ?? "",
            $"UI action hint: {action}\n{LanguageLine(locale)}\n\nHEADLINES:\n{storiesText}\n\nReturn JSON only."
        ), ct);
        var (specialist, reason) = ParseAssess(assessRaw, action);
        if (specialist != action)
        {
            specialist = action;
            reason += " (using the action)";
        }
        if (graph!.Enabled && !Outgoing(graph, NodeKey("assess")).Contains(NodeKey(specialist)))
        {
            specialist = "report";
            reason += "; graph edge missing, fall through to report";
        }
        yield return new()
        {
            ["type"] = "node", ["role"] = "assess", ["specialist"] = specialist,
            ["reason"] = reason, ["clip"] = Clip($"{specialist}: {reason}"),
        };

        yield return new() { ["type"] = "status", ["message"] = specialist };
        var specCfg = EvaluateAgent(specialist, context, new()
        {
            ["action"] = action, ["locale"] = locale, ["stories"] = storiesText, ["specialist"] = specialist,
        });
        var specUser = specialist == "questions"
            ? $"{LanguageLine(locale)}\n\nCANDIDATE QUESTIONS:\n{ReadMessage("questions.txt")}\n\nHEADLINES:\n{storiesText}"
            : $"{LanguageLine(locale)}\n\nHEADLINES:\n{storiesText}\n\nProduce the {specialist} output now.";
        var draft = await OllamaCompleteAsync(ResolveModel(specCfg), Messages(specCfg.Instructions ?? "", specUser), ct);
        ILdAiConfigTracker? nodeTracker = null;
        try { nodeTracker = specCfg.CreateTracker(); } catch { /* best-effort */ }
        var token = nodeTracker?.ResumptionToken;
        yield return new()
        {
            ["type"] = "draft", ["specialist"] = specialist, ["text"] = draft,
            ["clip"] = Clip(draft), ["resumptionToken"] = token,
        };

        yield return new() { ["type"] = "status", ["message"] = "judges" };
        var judges = new List<Dictionary<string, object?>>
        {
            await RunOneJudgeAsync(JudgeKey("fidelity"), persona, locale, storiesText, draft, ct),
            await RunOneJudgeAsync(JudgeKey("discipline"), persona, locale, storiesText, draft, ct),
        };
        yield return new() { ["type"] = "judges", ["results"] = judges, ["draft"] = draft };

        var transformed = draft;
        foreach (var key in tools)
        {
            if (key == "joke-tagline")
            {
                yield return new() { ["type"] = "info", ["message"] = $"Setting humor level to {HumorLevel.GetValueOrDefault(persona.Id, 50)}%" };
            }
            transformed = ApplyTool(key, transformed, persona, locale);
            if (nodeTracker != null)
            {
                // Library tools — https://launchdarkly.com/docs/home/agentcontrol/tools
                try { nodeTracker.TrackToolCall(key); } catch { /* monitoring is best-effort */ }
            }
            yield return new() { ["type"] = "tool", ["key"] = key, ["text"] = transformed, ["clip"] = Clip(transformed) };
        }

        if (graph.Enabled && !Outgoing(graph, NodeKey(specialist)).Contains(NodeKey("finalize")))
        {
            yield return new() { ["type"] = "error", ["message"] = $"Graph has no edge from {NodeKey(specialist)} to {NodeKey("finalize")}." };
            yield return new() { ["type"] = "done", ["resumptionToken"] = token };
            yield break;
        }
        try { graphTracker?.TrackHandoffSuccess(NodeKey(specialist), NodeKey("finalize")); } catch { /* best-effort */ }

        yield return new() { ["type"] = "status", ["message"] = "finalize" };
        var finCfg = EvaluateAgent("finalize", context, new()
        {
            ["action"] = action, ["locale"] = locale, ["specialist"] = specialist, ["draft"] = transformed,
        });
        var rawFinal = await OllamaCompleteAsync(
            ResolveModel(finCfg),
            Messages(finCfg.Instructions ?? "", FinalizeUser(locale, specialist, tools, transformed)),
            ct);
        var (finalText, notes) = GuardFinalize(rawFinal, transformed, tools);
        foreach (var note in notes)
        {
            yield return new() { ["type"] = "info", ["message"] = note, ["kind"] = "guard" };
        }
        var path = new List<string> { NodeKey("assess"), NodeKey(specialist), NodeKey("finalize") };
        var ldTransaction = new Dictionary<string, object?>
        {
            ["sent"] = new Dictionary<string, object?>
            {
                ["graphKey"] = GraphKey(),
                ["context"] = new Dictionary<string, object?>
                {
                    ["key"] = persona.Id, ["name"] = persona.Name, ["action"] = action, ["locale"] = locale,
                },
                ["variables"] = new Dictionary<string, object?>
                {
                    ["action"] = action, ["locale"] = locale, ["stories"] = storiesText, ["selectedTools"] = tools,
                },
                ["requestedPath"] = path,
                ["sdkDefault"] = new Dictionary<string, object?>
                {
                    ["enabled"] = true, ["provider"] = "Custom", ["model"] = DefaultModel(),
                    ["description"] = "Capstone graph fallback: assess → specialist → finalize.",
                },
            },
            ["received"] = new Dictionary<string, object?>
            {
                ["graph"] = new Dictionary<string, object?>
                {
                    ["key"] = GraphKey(), ["enabled"] = graph.Enabled,
                },
                ["route"] = specialist,
                ["path"] = path,
                ["nodes"] = new List<Dictionary<string, object?>>
                {
                    Summary(NodeKey("assess"), assessCfg),
                    Summary(NodeKey(specialist), specCfg),
                    Summary(NodeKey("finalize"), finCfg),
                },
                ["tools"] = tools,
                ["judges"] = judges,
                ["transformedDraft"] = transformed,
            },
        };
        yield return new() { ["type"] = "finalize", ["text"] = finalText, ["clip"] = Clip(finalText) };
        try
        {
            graphTracker?.TrackPath(path);
            graphTracker?.TrackInvocationSuccess();
            nodeTracker?.TrackSuccess();
        }
        catch { /* best-effort */ }
        yield return new()
        {
            ["type"] = "done", ["specialist"] = specialist, ["tools"] = tools, ["path"] = path,
            ["resumptionToken"] = token, ["draft"] = draft, ["text"] = finalText, ["ldTransaction"] = ldTransaction,
        };
    }

    /// <summary>
    /// Rebuild the specialist tracker and record thumbs.
    /// LaunchDarkly: CreateTracker + TrackFeedback
    /// https://launchdarkly.com/docs/sdk/features/ai-metrics
    /// </summary>
    public static Dictionary<string, object?> SubmitFeedback(Persona persona, string locale, string resumptionToken, string kind)
    {
        var token = (resumptionToken ?? "").Trim();
        if (token.Length == 0) throw new ArgumentException("Generate first. Feedback attaches to the specialist draft.");
        var kindL = (kind ?? "").Trim().ToLowerInvariant();
        Feedback feedback;
        string normalized;
        if (kindL is "positive" or "up" or "+") { feedback = Feedback.Positive; normalized = "positive"; }
        else if (kindL is "negative" or "down" or "-") { feedback = Feedback.Negative; normalized = "negative"; }
        else throw new ArgumentException("kind must be positive or negative.");
        var tracker = Ai().CreateTracker(token, BuildContext(persona, "feedback", locale == "es" ? "es" : "en"));
        tracker.TrackFeedback(feedback);
        return new() { ["ok"] = true, ["kind"] = normalized };
    }
}
