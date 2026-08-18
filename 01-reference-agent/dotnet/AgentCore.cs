using System.Diagnostics;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;

namespace ReferenceAgent;

/// <summary>
/// Domain logic for 01-reference-agent (no HTTP here, no LaunchDarkly).
///
/// =============================================================================
/// HOW TO READ THIS FILE
/// =============================================================================
///
/// This is the **baseline** the 20-agent-config/2x .NET ports build on. Everything
/// that later becomes a LaunchDarkly AgentControl evaluation is, here, just a file
/// read and an environment variable:
///
///   1. Data          Personas (UI labels only — no LD context needed yet)
///   2. Config        Resolve provider mode + model labels from env vars
///   3. Prompting     Build chat messages (system = ../prompts/system_prompt.txt,
///                    user = stories)
///   4. Generation    GenerateStreamAsync() — the main orchestration loop
///   5. Providers     Stub (default), Ollama (local) — Bedrock is a documented
///                    "not wired" error here, matching the Node.js port
///
/// Where LaunchDarkly goes next: compare this file to
/// 20-agent-config/21-agent-completion-config/dotnet/AgentCore.cs — that port
/// replaces steps 2/3 with an `LdAiClient.CompletionConfig(...)` evaluation
/// (AgentControl). See https://launchdarkly.com/docs/home/agentcontrol for the
/// capability this baseline is standing in for.
///
/// Event contract (mirrors agentCore.js): GenerateStreamAsync yields, in order:
///   meta     — once at start: persona, input, provider, model, mode, stories
///   token    — zero or more times: streamed text fragments
///   error    — optional: human-readable failure for the Status panel
///   metrics  — once near the end: latency, tokens, finish_reason, … (snake_case)
///   done     — once at the very end: stream complete
/// </summary>
public static class AgentCore
{
    /// <summary>Selectable demo identity — a UI label only in this baseline.</summary>
    public sealed record Persona(string Id, string Name, string Profile);

    public static readonly IReadOnlyList<Persona> Personas = new List<Persona>
    {
        new("conservative-charlie", "Conservative Charlie", "conservative"),
        new("neutral-nancy", "Neutral Nancy", "neutral"),
        new("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
    };

    private const string CannedInput =
        "No ticker stories loaded yet. Ask the user to click Get Stories, " +
        "then produce a brief placeholder note that you are waiting for headlines.";

    // Sensible Bedrock defaults when env vars are incomplete (kept for label parity
    // with the Node/Python ports even though Bedrock generation is not wired here).
    private const string DefaultBedrockModelId = "us.amazon.nova-lite-v1:0";
    private const string DefaultAwsRegion = "us-east-1";
    private const string DefaultAwsProfile = "Administrator";

    private static readonly string[] KnownModes = { "stub", "ollama", "bedrock", "anthropic" };

    private static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(120) };

    public static Persona? PersonaById(string id) => Personas.FirstOrDefault(p => p.Id == id);

    private static string SystemPromptPath() => Path.Combine(YahooNews.ExampleRoot(), "prompts", "system_prompt.txt");

    /// <summary>
    /// Read the shared system prompt from the repository prompt file.
    /// Re-reads on each call so prompt edits apply without restarting the server.
    /// </summary>
    public static string LoadSystemPrompt()
    {
        var path = SystemPromptPath();
        string text;
        try
        {
            text = File.ReadAllText(path).Trim();
        }
        catch (Exception exc)
        {
            throw new InvalidOperationException($"Could not read system prompt at {path}: {exc.Message}", exc);
        }
        if (text.Length == 0)
        {
            throw new InvalidOperationException($"System prompt file is empty: {path}");
        }
        return text;
    }

    /// <summary>
    /// AGENT_LLM_MODE, defaulting to stub for zero-credential demos.
    /// Supported today: stub, ollama. bedrock is a documented "not wired" error;
    /// anthropic is reserved for later wiring (matches the Node.js port).
    /// </summary>
    public static string ResolveMode()
    {
        var mode = (Environment.GetEnvironmentVariable("AGENT_LLM_MODE") ?? "stub").Trim().ToLowerInvariant();
        return KnownModes.Contains(mode) ? mode : "stub";
    }

    public static string ResolveAwsRegion()
        => (Environment.GetEnvironmentVariable("AWS_REGION") ?? "").Trim() is { Length: > 0 } r ? r
            : (Environment.GetEnvironmentVariable("AWS_DEFAULT_REGION") ?? "").Trim() is { Length: > 0 } d ? d
            : DefaultAwsRegion;

    public static string ResolveAwsProfile()
        => (Environment.GetEnvironmentVariable("AWS_PROFILE") ?? "").Trim() is { Length: > 0 } p ? p : DefaultAwsProfile;

    /// <summary>Short provider name shown next to the model in the UI.</summary>
    public static string ProviderLabel(string mode) => mode switch
    {
        "stub" => "stub",
        "ollama" => "ollama",
        "bedrock" => "bedrock",
        "anthropic" => "anthropic",
        _ => mode,
    };

    public static string DefaultOllamaModel()
        => (Environment.GetEnvironmentVariable("OLLAMA_MODEL") ?? "").Trim() is { Length: > 0 } m ? m : "llama3.2:3b";

    /// <summary>
    /// Model id / display name for the Provider / model panel.
    /// Precedence: AGENT_LLM_MODEL override (any mode) → mode-specific defaults / env vars.
    /// </summary>
    public static string ModelLabel(string mode)
    {
        var override_ = (Environment.GetEnvironmentVariable("AGENT_LLM_MODEL") ?? "").Trim();
        if (override_.Length > 0) return override_;
        return mode switch
        {
            "stub" => "default-no-llm",
            "ollama" => DefaultOllamaModel(),
            "bedrock" => (Environment.GetEnvironmentVariable("AGENT_BEDROCK_MODEL_ID") ?? "").Trim() is { Length: > 0 } b
                ? b
                : DefaultBedrockModelId,
            "anthropic" => (Environment.GetEnvironmentVariable("ANTHROPIC_MODEL") ?? "").Trim() is { Length: > 0 } a
                ? a
                : "claude-3-haiku-20240307",
            _ => "(unknown)",
        };
    }

    private static string BuildUserInput(List<Dictionary<string, object?>>? tickerResults)
        => tickerResults is { Count: > 0 } ? YahooNews.FormatStoriesForPrompt(tickerResults) : CannedInput;

    /// <summary>
    /// Chat messages sent to real LLM providers.
    /// system ← ../prompts/system_prompt.txt (shared; LaunchDarkly later)
    /// user   ← story-based briefing prompt (same story set for every persona)
    /// </summary>
    private static List<Dictionary<string, string>> BuildMessages(List<Dictionary<string, object?>>? tickerResults) => new()
    {
        new() { ["role"] = "system", ["content"] = LoadSystemPrompt() },
        new() { ["role"] = "user", ["content"] = BuildUserInput(tickerResults) },
    };

    private static int EstimateTokens(string? text) => Math.Max(1, (text ?? "").Length / 4);

    private static Dictionary<string, object?> PersonaMap(Persona persona) => new()
    {
        ["id"] = persona.Id,
        ["name"] = persona.Name,
        ["profile"] = persona.Profile,
    };

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

    private static void FillTokenEstimates(string completionText, Metrics metrics, string userInput)
    {
        metrics.PromptTokens = EstimateTokens(LoadSystemPrompt() + userInput);
        metrics.CompletionTokens = EstimateTokens(completionText);
        metrics.TotalTokens = (metrics.PromptTokens ?? 0) + (metrics.CompletionTokens ?? 0);
    }

    private static IEnumerable<string> ChunkText(string text, int size = 12)
    {
        for (var i = 0; i < text.Length; i += size)
        {
            yield return text.Substring(i, Math.Min(size, text.Length - i));
        }
    }

    /// <summary>Boilerplate text for AGENT_LLM_MODE=stub (default-no-llm).</summary>
    private static string StubResponse(Persona persona, List<Dictionary<string, object?>>? tickerResults)
    {
        var lines = new List<string>
        {
            "[stub / default-no-llm]",
            $"Persona: {persona.Name} ({persona.Profile})",
            "",
            "Headline briefing (stub):",
        };
        if (tickerResults is not { Count: > 0 })
        {
            lines.Add("- (no stories loaded — click Get Stories)");
        }
        else
        {
            foreach (var block in tickerResults)
            {
                var ticker = block.GetValueOrDefault("ticker") as string ?? "?";
                lines.Add($"- {ticker}:");
                var stories = block.GetValueOrDefault("stories") as List<Dictionary<string, object?>> ?? new();
                if (stories.Count == 0) lines.Add("  (no stories)");
                foreach (var story in stories)
                {
                    lines.Add($"  \u2022 {story.GetValueOrDefault("title") as string ?? "(untitled)"}");
                }
            }
        }
        lines.Add("");
        lines.Add(
            $"As a {persona.Profile} analyst, this is boilerplate report text for UI testing. " +
            "Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.");
        return string.Join("\n", lines);
    }

    private static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStubAsync(
        Persona persona, Stopwatch sw, Metrics metrics, string userInput,
        List<Dictionary<string, object?>>? tickerResults, [EnumeratorCancellation] CancellationToken ct)
    {
        var text = StubResponse(persona, tickerResults);
        var first = true;
        foreach (var chunk in ChunkText(text, 12))
        {
            if (first)
            {
                metrics.TtftMs = (long)sw.Elapsed.TotalMilliseconds;
                first = false;
            }
            yield return new Dictionary<string, object?> { ["type"] = "token", ["text"] = chunk };
            await Task.Delay(20, ct);
        }
        metrics.FinishReason = "stop";
        FillTokenEstimates(text, metrics, userInput);
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
                $"Ollama request failed ({host}): {exc.Message}. " +
                "Is Ollama running, and is OLLAMA_MODEL pulled?", exc);
        }

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Ollama request failed ({host}): HTTP {(int)response.StatusCode}. " +
                "Is Ollama running, and is OLLAMA_MODEL pulled?");
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
        string userInput, [EnumeratorCancellation] CancellationToken ct)
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
        FillTokenEstimates(textParts.ToString(), metrics, userInput);
    }

    /// <summary>
    /// Run one generation and yield UI events in order (meta → token* → error? → metrics → done).
    ///
    /// This is the seam later .NET ports (20-agent-config/2x) replace with a LaunchDarkly
    /// AgentControl evaluation — everything above "Step 2" here becomes a config lookup there.
    /// </summary>
    public static async IAsyncEnumerable<Dictionary<string, object?>> GenerateStreamAsync(
        Persona persona,
        List<Dictionary<string, object?>>? tickerResults,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        var mode = ResolveMode();
        var provider = ProviderLabel(mode);
        var model = ModelLabel(mode);
        var userInput = BuildUserInput(tickerResults);
        var stories = tickerResults ?? new List<Dictionary<string, object?>>();

        // Step 1 — describe the run up front.
        yield return new Dictionary<string, object?>
        {
            ["type"] = "meta",
            ["persona"] = PersonaMap(persona),
            ["input"] = userInput,
            ["provider"] = provider,
            ["model"] = model,
            ["mode"] = mode,
            ["stories"] = stories,
        };

        var sw = Stopwatch.StartNew();
        var metrics = new Metrics();

        // Step 2 — call the provider and stream tokens (or surface an error).
        if (mode == "stub")
        {
            await foreach (var evt in GenerateStubAsync(persona, sw, metrics, userInput, tickerResults, ct))
            {
                yield return evt;
            }
        }
        else if (mode == "ollama")
        {
            var messages = BuildMessages(tickerResults);
            await foreach (var evt in GenerateOllamaAsync(model, messages, sw, metrics, userInput, ct))
            {
                yield return evt;
            }
        }
        else if (mode == "bedrock")
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] =
                    "Mode 'bedrock' is not wired in the .NET example yet. " +
                    "Use AGENT_LLM_MODE=stub or ollama here, or run the Python web app for Bedrock.",
            };
            metrics.FinishReason = "error";
        }
        else
        {
            yield return new Dictionary<string, object?>
            {
                ["type"] = "error",
                ["message"] =
                    $"Mode '{mode}' is configured but not implemented in this reference yet. " +
                    "Use AGENT_LLM_MODE=stub or ollama.",
            };
            metrics.FinishReason = "error";
        }

        // Step 3 — always close with metrics + done so the UI can re-enable buttons.
        metrics.LatencyMs = (long)sw.Elapsed.TotalMilliseconds;
        yield return new Dictionary<string, object?> { ["type"] = "metrics", ["metrics"] = metrics.ToMap() };
        yield return new Dictionary<string, object?> { ["type"] = "done" };
    }
}
