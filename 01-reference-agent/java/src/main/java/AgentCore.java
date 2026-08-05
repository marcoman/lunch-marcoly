import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Domain logic for 01-reference-agent (no HTTP here).
 * Emits event maps: meta | token | error | metrics | done.
 */
public final class AgentCore {
    public static final List<Persona> PERSONAS = List.of(
            new Persona("conservative-charlie", "Conservative Charlie", "conservative"),
            new Persona("neutral-nancy", "Neutral Nancy", "neutral"),
            new Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker")
    );

    private static final String CANNED_INPUT =
            "No ticker stories loaded yet. Ask the user to click Get Stories, "
                    + "then produce a brief placeholder note that you are waiting for headlines.";

    private static final String DEFAULT_BEDROCK_MODEL_ID = "us.amazon.nova-lite-v1:0";
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private AgentCore() {
    }

    public record Persona(String id, String name, String profile) {
    }

    public static Persona personaById(String personaId) {
        for (Persona p : PERSONAS) {
            if (p.id().equals(personaId)) {
                return p;
            }
        }
        return null;
    }

    private static volatile String modeOverride = null;

    /** Runtime mode override for console (m)ode cycling; null clears. */
    public static void setModeOverride(String mode) {
        if (mode == null || mode.isBlank()) {
            modeOverride = null;
            return;
        }
        String cleaned = mode.trim().toLowerCase();
        modeOverride = List.of("stub", "ollama", "bedrock", "anthropic").contains(cleaned)
                ? cleaned
                : "stub";
    }

    public static String resolveMode() {
        String mode = (modeOverride != null ? modeOverride : env("AGENT_LLM_MODE", "stub"))
                .trim()
                .toLowerCase();
        if (List.of("stub", "ollama", "bedrock", "anthropic").contains(mode)) {
            return mode;
        }
        return "stub";
    }

    public static String providerLabel(String mode) {
        return switch (mode) {
            case "stub" -> "stub";
            case "ollama" -> "ollama";
            case "bedrock" -> "bedrock";
            case "anthropic" -> "anthropic";
            default -> mode;
        };
    }

    public static String modelLabel(String mode) {
        String override = env("AGENT_LLM_MODEL", "").trim();
        if (!override.isEmpty()) {
            return override;
        }
        return switch (mode) {
            case "stub" -> "default-no-llm";
            case "ollama" -> {
                String m = env("OLLAMA_MODEL", "llama3.2:3b").trim();
                yield m.isEmpty() ? "llama3.2:3b" : m;
            }
            case "bedrock" -> {
                String m = env("AGENT_BEDROCK_MODEL_ID", "").trim();
                yield m.isEmpty() ? DEFAULT_BEDROCK_MODEL_ID : m;
            }
            case "anthropic" -> env("ANTHROPIC_MODEL", "claude-3-haiku-20240307").trim();
            default -> "(unknown)";
        };
    }

    public static void generateStream(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String mode = resolveMode();
        String provider = providerLabel(mode);
        String model = modelLabel(mode);
        String userInput = buildUserInput(tickerResults);

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("type", "meta");
        meta.put("persona", Map.of(
                "id", persona.id(),
                "name", persona.name(),
                "profile", persona.profile()
        ));
        meta.put("input", userInput);
        meta.put("provider", provider);
        meta.put("model", model);
        meta.put("mode", mode);
        meta.put("stories", tickerResults == null ? List.of() : tickerResults);
        emit.accept(meta);

        long started = System.nanoTime();
        Map<String, Object> metrics = emptyMetrics();

        try {
            switch (mode) {
                case "stub" -> generateStub(persona, started, metrics, userInput, tickerResults, emit);
                case "ollama" -> generateOllama(
                        persona, model, started, metrics, tickerResults, userInput, emit);
                case "bedrock" -> {
                    emit.accept(Map.of(
                            "type", "error",
                            "message",
                            "Mode 'bedrock' is not wired in the Java example yet. "
                                    + "Use AGENT_LLM_MODE=stub or ollama here, "
                                    + "or run the Python web app for Bedrock."
                    ));
                    metrics.put("finish_reason", "error");
                }
                default -> {
                    emit.accept(Map.of(
                            "type", "error",
                            "message",
                            "Mode '" + mode + "' is configured but not implemented yet. "
                                    + "Use AGENT_LLM_MODE=stub or ollama."
                    ));
                    metrics.put("finish_reason", "error");
                }
            }
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
        }

        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        emit.accept(Map.of("type", "done"));
    }

    private static void generateStub(
            Persona persona,
            long started,
            Map<String, Object> metrics,
            String userInput,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) throws InterruptedException {
        String text = stubResponse(persona, tickerResults);
        boolean first = true;
        for (String chunk : chunkText(text, 12)) {
            if (first) {
                metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);
                first = false;
            }
            emit.accept(Map.of("type", "token", "text", chunk));
            Thread.sleep(20);
        }
        metrics.put("finish_reason", "stop");
        fillTokenEstimates(text, metrics, userInput);
    }

    private static void generateOllama(
            Persona persona,
            String model,
            long started,
            Map<String, Object> metrics,
            List<Map<String, Object>> tickerResults,
            String userInput,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        String url = host + "/api/chat";

        List<Map<String, String>> messages = buildMessages(persona, tickerResults);
        Map<String, Object> payload = Map.of(
                "model", model,
                "stream", true,
                "messages", messages
        );
        String body = new com.google.gson.Gson().toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<java.io.InputStream> response;
        try {
            response = HTTP.send(request, HttpResponse.BodyHandlers.ofInputStream());
        } catch (IOException | InterruptedException exc) {
            throw new IOException(
                    "Ollama request failed (" + host + "): " + exc.getMessage()
                            + ". Is Ollama running, and is OLLAMA_MODEL pulled?",
                    exc
            );
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama request failed (" + host + "): HTTP " + response.statusCode()
                            + ". Is Ollama running, and is OLLAMA_MODEL pulled?"
            );
        }

        StringBuilder textParts = new StringBuilder();
        boolean first = true;
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) {
                    continue;
                }
                JsonObject data = JsonParser.parseString(line).getAsJsonObject();
                if (data.has("error")) {
                    throw new IOException(String.valueOf(data.get("error")));
                }
                String content = "";
                if (data.has("message") && data.get("message").isJsonObject()) {
                    JsonObject message = data.getAsJsonObject("message");
                    if (message.has("content") && !message.get("content").isJsonNull()) {
                        content = message.get("content").getAsString();
                    }
                }
                if (!content.isEmpty()) {
                    if (first) {
                        metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);
                        first = false;
                    }
                    textParts.append(content);
                    emit.accept(Map.of("type", "token", "text", content));
                }
                if (data.has("done") && data.get("done").getAsBoolean()) {
                    break;
                }
            }
        }

        metrics.put("finish_reason", "stop");
        fillTokenEstimates(textParts.toString(), metrics, userInput);
    }

    private static List<Map<String, String>> buildMessages(
            Persona persona,
            List<Map<String, Object>> tickerResults
    ) {
        // persona reserved for later LaunchDarkly prompt variation
        voidUnused(persona);
        return List.of(
                Map.of("role", "system", "content", loadSystemPrompt()),
                Map.of("role", "user", "content", buildUserInput(tickerResults))
        );
    }

    private static String buildUserInput(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) {
            return CANNED_INPUT;
        }
        return YahooNews.formatStoriesForPrompt(tickerResults);
    }

    private static String loadSystemPrompt() {
        Path path = resolveSystemPromptPath();
        try {
            String text = Files.readString(path, StandardCharsets.UTF_8).trim();
            if (text.isEmpty()) {
                throw new IllegalStateException("System prompt file is empty: " + path);
            }
            return text;
        } catch (IOException exc) {
            throw new IllegalStateException(
                    "Could not read system prompt at " + path + ": " + exc.getMessage(), exc);
        }
    }

    private static Path resolveSystemPromptPath() {
        Path cwd = Path.of("").toAbsolutePath().normalize();
        Path candidate = cwd.resolve("../prompts/system_prompt.txt").normalize();
        if (Files.isRegularFile(candidate)) {
            return candidate;
        }
        candidate = cwd.resolve("prompts/system_prompt.txt").normalize();
        if (Files.isRegularFile(candidate)) {
            return candidate;
        }
        // Running from repo root: 01-reference-agent/prompts/...
        candidate = cwd.resolve("01-reference-agent/prompts/system_prompt.txt").normalize();
        if (Files.isRegularFile(candidate)) {
            return candidate;
        }
        return cwd.resolve("../prompts/system_prompt.txt").normalize();
    }

    private static String stubResponse(Persona persona, List<Map<String, Object>> tickerResults) {
        StringBuilder lines = new StringBuilder();
        lines.append("[stub / default-no-llm]\n");
        lines.append("Persona: ").append(persona.name()).append(" (").append(persona.profile()).append(")\n\n");
        lines.append("Headline briefing (stub):\n");
        if (tickerResults == null || tickerResults.isEmpty()) {
            lines.append("- (no stories loaded — click Get Stories)\n");
        } else {
            for (Map<String, Object> block : tickerResults) {
                String ticker = String.valueOf(block.getOrDefault("ticker", "?"));
                lines.append("- ").append(ticker).append(":\n");
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> stories = (List<Map<String, Object>>) block.get("stories");
                if (stories == null || stories.isEmpty()) {
                    lines.append("  (no stories)\n");
                } else {
                    for (Map<String, Object> story : stories) {
                        lines.append("  • ")
                                .append(String.valueOf(story.getOrDefault("title", "(untitled)")))
                                .append("\n");
                    }
                }
            }
        }
        lines.append("\nAs a ").append(persona.profile())
                .append(" analyst, this is boilerplate report text for UI testing. ")
                .append("Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.");
        return lines.toString();
    }

    private static List<String> chunkText(String text, int size) {
        List<String> chunks = new ArrayList<>();
        for (int i = 0; i < text.length(); i += size) {
            chunks.add(text.substring(i, Math.min(text.length(), i + size)));
        }
        return chunks;
    }

    private static Map<String, Object> emptyMetrics() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("latency_ms", null);
        m.put("ttft_ms", null);
        m.put("prompt_tokens", null);
        m.put("completion_tokens", null);
        m.put("total_tokens", null);
        m.put("finish_reason", null);
        return m;
    }

    private static void fillTokenEstimates(String completionText, Map<String, Object> metrics, String userInput) {
        int prompt = estimateTokens(loadSystemPrompt() + userInput);
        int completion = estimateTokens(completionText);
        metrics.put("prompt_tokens", prompt);
        metrics.put("completion_tokens", completion);
        metrics.put("total_tokens", prompt + completion);
    }

    private static int estimateTokens(String text) {
        if (text == null || text.isEmpty()) {
            return 1;
        }
        return Math.max(1, text.length() / 4);
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null ? fallback : value;
    }

    private static void voidUnused(Object ignored) {
        // reserved for future per-persona / LD prompt selection
    }
}
