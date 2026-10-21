import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.launchdarkly.sdk.ArrayBuilder;
import com.launchdarkly.sdk.ContextBuilder;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.ObjectBuilder;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Capstone walk: assess → specialist → judges → tools → finalize.
 *
 * There is no official Java AI SDK. This class evaluates the graph and each
 * agent/judge config with {@code jsonValueVariationDetail}, calls Ollama
 * itself, and emits the same {@code $ld:ai:*} metric events the AI SDK
 * trackers send.
 *
 * LaunchDarkly insertion (read first):
 *   generateStream() → evaluateGraph() then evaluateAgent() per node
 *   then evaluateJudge() on the specialist draft
 *   then NodeTracker.trackToolCall for each checked tool
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
 * Docs: https://launchdarkly.com/docs/home/agentcontrol/tools
 * Keywords: AgentControl · agent graphs · Library tools · judges · feedback
 */
public final class AgentCore {
    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private static final Path MESSAGES_DIR = Path.of("..", "rest", "messages");
    private static final String DEFAULT_GRAPH_KEY = "equity-briefing-capstone";
    private static final Map<String, String> NODE_DEFAULTS = Map.of(
            "assess", "equity-briefing-capstone-assess",
            "report", "equity-briefing-capstone-report",
            "questions", "equity-briefing-capstone-questions",
            "good", "equity-briefing-capstone-good",
            "finalize", "equity-briefing-capstone-finalize"
    );
    public static final List<String> TOOL_ORDER = List.of("pig-latin", "rot13", "joke-tagline");
    private static final Set<String> VALID_SPECIALISTS = Set.of("report", "questions", "good");
    private static final Map<String, Integer> HUMOR_LEVEL = Map.of(
            "conservative-charlie", 25,
            "anonymous-amelia", 50,
            "thoughtless-toby", 90
    );
    private static final Set<String> ENGLISH_WORDS = Set.of(
            "the", "and", "for", "that", "this", "with", "from", "have", "are", "was", "were", "not", "but",
            "its", "has", "will", "can", "you", "your", "their", "they", "been", "into", "over", "after",
            "more", "than", "also", "about", "would", "could", "should", "which", "there", "these", "those",
            "them", "then", "when", "what", "where", "while", "stock", "stocks", "market", "shares", "price",
            "prices", "growth", "revenue", "earnings", "company", "companies", "investor", "investors",
            "today", "according", "said", "says"
    );
    private static final Map<String, Map<String, String>> JOKES = Map.of(
            "en", Map.of(
                    "conservative-charlie", "The market can stay irrational longer than a footnote.",
                    "anonymous-amelia", "Diversification is the joke that still pays rent.",
                    "thoughtless-toby", "Buy high, sell higher, and call the difference research."
            ),
            "es", Map.of(
                    "conservative-charlie", "El mercado puede seguir irracional más que una nota al pie.",
                    "anonymous-amelia", "Diversificar es el chiste que igual paga el alquiler.",
                    "thoughtless-toby", "Compra caro, vende más caro, y llama investigación a la diferencia."
            )
    );
    private static final String EVT_GRAPH_INVOCATION_SUCCESS = "$ld:ai:graph:invocation_success";
    private static final String EVT_GRAPH_PATH = "$ld:ai:graph:path";
    private static final String EVT_GRAPH_HANDOFF_SUCCESS = "$ld:ai:graph:handoff_success";
    private static final String EVT_NODE_GENERATION_SUCCESS = "$ld:ai:generation:success";
    private static final String EVT_NODE_TOOL_CALL = "$ld:ai:generation:tool_call";
    private static final String EVT_FEEDBACK_POSITIVE = "$ld:ai:feedback:user:positive";
    private static final String EVT_FEEDBACK_NEGATIVE = "$ld:ai:feedback:user:negative";

    private static LDClient client;
    private static final Map<String, Persona> FEEDBACK_TOKENS = new ConcurrentHashMap<>();

    public record Persona(String id, String name, String profile, boolean anonymous) {
    }

    public static final List<Persona> PERSONAS = List.of(
            new Persona("conservative-charlie", "Conservative Charlie", "conservative", false),
            new Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
            new Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker", false)
    );

    private record AgentEval(boolean enabled, String instructions, String modelName, String variationKey, int version) {
    }

    private static final class GraphInfo {
        final boolean enabled;
        final Map<String, List<String>> outgoing;
        final String variationKey;
        final int version;

        GraphInfo(boolean enabled, Map<String, List<String>> outgoing, String variationKey, int version) {
            this.enabled = enabled;
            this.outgoing = outgoing;
            this.variationKey = variationKey;
            this.version = version;
        }

        List<String> outgoingTargets(String sourceKey) {
            if (!enabled) return List.of();
            return outgoing.getOrDefault(sourceKey, List.of());
        }
    }

    private AgentCore() {
    }

    public static Persona personaById(String personaId) {
        for (Persona persona : PERSONAS) {
            if (persona.id().equals(personaId)) return persona;
        }
        return null;
    }

    public static String graphKey() {
        String raw = System.getenv().getOrDefault("LD_GRAPH_KEY", "").trim();
        return raw.isEmpty() ? DEFAULT_GRAPH_KEY : raw;
    }

    public static String nodeKey(String role) {
        String envName = switch (role) {
            case "assess" -> "LD_NODE_ASSESS";
            case "report" -> "LD_NODE_REPORT";
            case "questions" -> "LD_NODE_QUESTIONS";
            case "good" -> "LD_NODE_GOOD";
            case "finalize" -> "LD_NODE_FINALIZE";
            default -> "";
        };
        String raw = envName.isEmpty() ? "" : System.getenv().getOrDefault(envName, "").trim();
        return raw.isEmpty() ? NODE_DEFAULTS.get(role) : raw;
    }

    public static String judgeKey(String which) {
        if ("fidelity".equals(which)) {
            String raw = System.getenv().getOrDefault("LD_JUDGE_FIDELITY_KEY", "").trim();
            return raw.isEmpty() ? "equity-briefing-capstone-source-fidelity" : raw;
        }
        String raw = System.getenv().getOrDefault("LD_JUDGE_DISCIPLINE_KEY", "").trim();
        return raw.isEmpty() ? "equity-briefing-capstone-recommendation-discipline" : raw;
    }

    public static void initLaunchDarkly() {
        if (client != null) return;
        String sdkKey = System.getenv().getOrDefault("LD_SDK_KEY", "").trim();
        if (sdkKey.isEmpty()) {
            throw new IllegalStateException("LD_SDK_KEY is required. Export a server-side SDK key before starting the capstone.");
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().startWait(Duration.ofSeconds(5)).build());
        if (!client.isInitialized()) {
            throw new IllegalStateException("LaunchDarkly client failed to initialize within 5s.");
        }
    }

    private static LDClient requireClient() {
        if (client == null) initLaunchDarkly();
        return client;
    }

    private static double passThreshold() {
        String raw = System.getenv().getOrDefault("JUDGE_PASS_THRESHOLD", "").trim();
        if (raw.isEmpty()) return 0.65;
        try {
            return Double.parseDouble(raw);
        } catch (NumberFormatException exc) {
            return 0.65;
        }
    }

    private static String defaultOllamaModel() {
        String raw = System.getenv().getOrDefault("OLLAMA_MODEL", "").trim();
        return raw.isEmpty() ? "llama3.2:3b" : raw;
    }

    private static String readMessageFile(String name) {
        try {
            return Files.readString(MESSAGES_DIR.resolve(name));
        } catch (IOException exc) {
            throw new IllegalStateException("Could not read message file " + name + ": " + exc.getMessage(), exc);
        }
    }

    private static String instructionsFile(String role) {
        return switch (role) {
            case "assess" -> "assess-instructions.txt";
            case "report" -> "report-baseline-instructions.txt";
            case "questions" -> "questions-instructions.txt";
            case "good" -> "good-instructions.txt";
            case "finalize" -> "finalize-instructions.txt";
            default -> "finalize-instructions.txt";
        };
    }

    private static String clip(String text) {
        String cleaned = (text == null ? "" : text).replaceAll("\\s+", " ").trim();
        if (cleaned.length() <= 80) return cleaned;
        return cleaned.substring(0, 79) + "…";
    }

    /**
     * User context for graph, node, and judge evaluation.
     * LaunchDarkly: contexts — https://launchdarkly.com/docs/home/contexts
     */
    private static LDContext buildContext(Persona persona, String action, String locale) {
        ContextBuilder builder = LDContext.builder(persona.id())
                .name(persona.name())
                .set("action", action)
                .set("locale", "es".equals(locale) ? "es" : "en")
                .set("profile", persona.profile());
        if (persona.anonymous()) builder.anonymous(true);
        return builder.build();
    }

    private static LDValue agentDefault(String file) {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("instructions", readMessageFile(file).trim())
                .build();
    }

    /**
     * Evaluate one agent-mode node.
     * LaunchDarkly: jsonValueVariationDetail on the node key.
     * https://launchdarkly.com/docs/home/agentcontrol/agents
     */
    private static AgentEval evaluateAgent(String key, LDContext context, String file, Map<String, String> variables) {
        EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(key, context, agentDefault(file));
        LDValue value = detail.getValue() == null || detail.getValue().isNull() ? agentDefault(file) : detail.getValue();
        LDValue meta = value.get("_ldMeta");
        String variationKey = meta.isNull() ? "" : ldString(meta.get("variationKey"));
        int version = meta.isNull() || meta.get("version").isNull() ? 1 : meta.get("version").intValue();
        String instructions = value.get("instructions").isString() ? value.get("instructions").stringValue() : "";
        if (variables != null) {
            for (Map.Entry<String, String> entry : variables.entrySet()) {
                instructions = instructions.replace("{{ " + entry.getKey() + " }}", entry.getValue());
                instructions = instructions.replace("{{" + entry.getKey() + "}}", entry.getValue());
            }
        }
        LDValue model = value.get("model");
        String modelName = model.isNull() ? "" : ldString(model.get("name"));
        boolean enabled = value.get("enabled").isNull() || value.get("enabled").booleanValue();
        return new AgentEval(enabled, instructions, modelName.isEmpty() ? defaultOllamaModel() : modelName, variationKey, version);
    }

    /**
     * Evaluate the agent graph flag.
     * LaunchDarkly: jsonValueVariationDetail on the graph key. Served JSON is {root, edges}.
     * https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
     */
    private static GraphInfo evaluateGraph(LDContext context) {
        EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(graphKey(), context, LDValue.buildObject().build());
        LDValue variation = detail.getValue() == null ? LDValue.ofNull() : detail.getValue();
        LDValue meta = variation.isNull() ? LDValue.ofNull() : variation.get("_ldMeta");
        String variationKey = meta.isNull() ? "" : ldString(meta.get("variationKey"));
        int version = meta.isNull() || meta.get("version").isNull() ? 1 : meta.get("version").intValue();
        String root = variation.isNull() || !variation.get("root").isString() ? "" : variation.get("root").stringValue();
        if (root.isEmpty()) return new GraphInfo(false, Map.of(), variationKey, version);
        Map<String, List<String>> outgoing = new LinkedHashMap<>();
        LDValue edges = variation.get("edges");
        if (!edges.isNull()) {
            for (String source : edges.keys()) {
                List<String> targets = new ArrayList<>();
                for (LDValue edge : edges.get(source).values()) {
                    String target = ldString(edge.get("key"));
                    if (!target.isEmpty()) targets.add(target);
                }
                outgoing.put(source, targets);
            }
        }
        return new GraphInfo(true, outgoing, variationKey, version);
    }

    private static String ldString(LDValue value) {
        return value != null && value.isString() ? value.stringValue() : "";
    }

    private static String ollamaComplete(String model, List<Map<String, String>> messages) {
        String host = System.getenv().getOrDefault("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("model", model);
        body.put("messages", messages);
        body.put("stream", false);
        body.put("options", Map.of("temperature", 0));
        HttpRequest request = HttpRequest.newBuilder(URI.create(host + "/api/chat"))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(body)))
                .build();
        try {
            HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 300) {
                throw new IllegalStateException("Ollama request failed (HTTP " + response.statusCode() + " " + response.body() + ").");
            }
            JsonObject payload = JsonParser.parseString(response.body()).getAsJsonObject();
            if (!payload.has("message")) return "";
            return payload.getAsJsonObject("message").has("content")
                    ? payload.getAsJsonObject("message").get("content").getAsString()
                    : "";
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Ollama request failed (" + exc.getMessage() + ").", exc);
        } catch (IOException exc) {
            throw new IllegalStateException("Ollama request failed (" + exc.getMessage() + "). Is Ollama running with " + model + "?", exc);
        }
    }

    private static String[] parseAssess(String raw, String actionHint) {
        Matcher match = Pattern.compile("\\{[\\s\\S]*}").matcher(raw == null ? "" : raw);
        if (match.find()) {
            try {
                JsonObject data = JsonParser.parseString(match.group()).getAsJsonObject();
                String cand = data.has("specialist") ? data.get("specialist").getAsString().trim().toLowerCase() : "";
                String reason = data.has("reason") ? data.get("reason").getAsString().trim() : "assess";
                if (reason.isEmpty()) reason = "assess";
                if (VALID_SPECIALISTS.contains(cand)) return new String[]{cand, reason};
            } catch (RuntimeException ignored) {
                /* use the hint */
            }
        }
        if (VALID_SPECIALISTS.contains(actionHint)) return new String[]{actionHint, "assess parse failed; used the action"};
        return new String[]{"report", "assess parse failed; fall through to report"};
    }

    static String toPigLatin(String text) {
        Matcher matcher = Pattern.compile("[A-Za-z]+").matcher(text == null ? "" : text);
        StringBuilder out = new StringBuilder();
        while (matcher.find()) {
            String word = matcher.group();
            String lower = word.toLowerCase();
            String converted;
            if (lower.matches("^[aeiou].*")) converted = lower + "yay";
            else {
                Matcher split = Pattern.compile("^([^aeiouy]+)(.*)$").matcher(lower);
                converted = split.matches() && !split.group(2).isEmpty()
                        ? split.group(2) + split.group(1) + "ay"
                        : lower + "ay";
            }
            if (Character.isUpperCase(word.charAt(0))) {
                converted = Character.toUpperCase(converted.charAt(0)) + converted.substring(1);
            }
            matcher.appendReplacement(out, Matcher.quoteReplacement(converted));
        }
        matcher.appendTail(out);
        return out.toString();
    }

    static String toRot13(String text) {
        StringBuilder out = new StringBuilder();
        for (char ch : (text == null ? "" : text).toCharArray()) {
            if (ch >= 'A' && ch <= 'Z') out.append((char) ((ch - 'A' + 13) % 26 + 'A'));
            else if (ch >= 'a' && ch <= 'z') out.append((char) ((ch - 'a' + 13) % 26 + 'a'));
            else out.append(ch);
        }
        return out.toString();
    }

    private static String applyTool(String key, String text, Persona persona, String locale) {
        if ("pig-latin".equals(key)) return toPigLatin(text);
        if ("rot13".equals(key)) return toRot13(text);
        Map<String, String> pack = JOKES.getOrDefault(locale, JOKES.get("en"));
        String line = pack.getOrDefault(persona.id(), pack.get("anonymous-amelia"));
        return (text == null ? "" : text).replaceAll("\\s+$", "") + "\n\nTagline: " + line;
    }

    private static double pigLatinRatio(String text) {
        Matcher matcher = Pattern.compile("[A-Za-z]{3,}").matcher(text == null ? "" : text);
        int words = 0;
        int hits = 0;
        while (matcher.find()) {
            words++;
            if (matcher.group().toLowerCase().endsWith("ay")) hits++;
        }
        return words == 0 ? 0 : (double) hits / words;
    }

    private static double englishScore(String text) {
        Matcher matcher = Pattern.compile("[A-Za-z]{3,}").matcher(text == null ? "" : text);
        int words = 0;
        int hits = 0;
        while (matcher.find()) {
            words++;
            if (ENGLISH_WORDS.contains(matcher.group().toLowerCase())) hits++;
        }
        return words == 0 ? 0 : (double) hits / words;
    }

    private static final class Guard {
        final String text;
        final List<String> notes;

        Guard(String text, List<String> notes) {
            this.text = text;
            this.notes = notes;
        }
    }

    static Guard guardFinalize(String finalText, String transformed, List<String> tools) {
        Set<String> ran = new LinkedHashSet<>(tools);
        String text = finalText == null ? "" : finalText.trim();
        if (text.isEmpty()) return new Guard(transformed, List.of("finalize returned nothing; kept tool output"));
        if (ran.contains("rot13") && englishScore(text) - englishScore(transformed) > 0.08) {
            return new Guard(transformed, List.of("finalize decoded ROT13; kept tool output"));
        }
        if (ran.contains("pig-latin") && pigLatinRatio(transformed) - pigLatinRatio(text) > 0.15) {
            return new Guard(transformed, List.of("finalize removed Pig Latin; kept tool output"));
        }
        if (!ran.contains("pig-latin") && pigLatinRatio(text) - pigLatinRatio(transformed) > 0.15) {
            return new Guard(transformed, List.of("finalize added Pig Latin that was not checked; kept tool output"));
        }
        if (!ran.contains("rot13") && englishScore(toRot13(text)) - englishScore(text) > 0.08) {
            return new Guard(transformed, List.of("finalize added ROT13 that was not checked; kept tool output"));
        }
        List<String> notes = new ArrayList<>();
        Matcher tagline = Pattern.compile("(?m)^Tagline: .*$").matcher(transformed == null ? "" : transformed);
        if (ran.contains("joke-tagline")) {
            if (tagline.find() && !text.contains(tagline.group())) {
                text = text.replaceAll("(?m)^Tagline:.*$", "").replaceAll("\\s+$", "") + "\n\n" + tagline.group();
                notes.add("finalize changed the tagline; restored the tool's tagline");
            }
        } else if (Pattern.compile("(?m)^Tagline:").matcher(text).find()
                && (transformed == null || !Pattern.compile("(?m)^Tagline:").matcher(transformed).find())) {
            text = text.replaceAll("(?m)^Tagline:.*$", "").replaceAll("\\s+$", "");
            notes.add("finalize added a tagline that was not checked; removed it");
        }
        return new Guard(text, notes);
    }

    private static String languageLine(String locale) {
        return "es".equals(locale) ? "Write the answer in Spanish." : "Write the answer in English.";
    }

    private static String finalizeUser(String locale, String specialist, List<String> tools, String transformed) {
        boolean cipher = tools.contains("rot13") || tools.contains("pig-latin");
        String lang = cipher
                ? "A cipher already ran. Copy the draft's wording. Do not translate it back to plain language."
                : languageLine(locale);
        String pig = tools.contains("pig-latin") ? "applied — keep it" : "NOT applied — do not convert any words to Pig Latin";
        String rot = tools.contains("rot13")
                ? "applied — the draft is already ROT13. Copy every letter. Do not decode it"
                : "NOT applied — do not encode any text";
        String joke = tools.contains("joke-tagline")
                ? "applied — keep the Tagline line exactly as written"
                : "NOT applied — do not add a tagline";
        return lang + "\nSpecialist: " + specialist + "\n\nTOOLS THAT RAN:\n"
                + "Pig Latin: " + pig + ".\nROT13: " + rot + ".\nJoke tagline: " + joke + ".\n\nDRAFT:\n"
                + transformed + "\n\nReturn the final text only.";
    }

    private static List<Map<String, String>> messages(String system, String user) {
        List<Map<String, String>> out = new ArrayList<>();
        out.add(Map.of("role", "system", "content", system == null ? "" : system));
        out.add(Map.of("role", "user", "content", user));
        return out;
    }

    private static boolean hasStories(List<Map<String, Object>> blocks) {
        if (blocks == null) return false;
        for (Map<String, Object> block : blocks) {
            Object stories = block.get("stories");
            if (stories instanceof List<?> list && !list.isEmpty()) return true;
        }
        return false;
    }

    private static Map<String, Object> runOneJudge(String key, Persona persona, String locale, String input, String output) {
        String metric = key.contains("fidelity")
                ? "$ld:ai:judge:capstone-source-fidelity"
                : "$ld:ai:judge:capstone-recommendation-discipline";
        String file = key.contains("fidelity")
                ? "judge-source-fidelity-system.txt"
                : "judge-recommendation-discipline-system.txt";
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("key", key);
        result.put("threshold", passThreshold());
        try {
            // Judges — https://launchdarkly.com/docs/home/agentcontrol/judges
            LDValue fallback = LDValue.buildObject()
                    .put("enabled", true)
                    .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                    .put("messages", LDValue.buildArray().add(LDValue.buildObject()
                            .put("role", "system").put("content", readMessageFile(file).trim()).build()).build())
                    .put("evaluationMetricKey", metric)
                    .build();
            EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(
                    key, buildContext(persona, "judge", locale), fallback);
            LDValue value = detail.getValue() == null || detail.getValue().isNull() ? fallback : detail.getValue();
            String model = ldString(value.get("model").get("name"));
            if (model.isEmpty()) model = defaultOllamaModel();
            String raw = ollamaComplete(model, messages(
                    readMessageFile(file).trim() + "\n\nRespond with JSON: {\"score\":0.0,\"reasoning\":\"...\"}",
                    "MESSAGE HISTORY:\n" + input + "\n\nRESPONSE TO EVALUATE:\n" + output
            ));
            Matcher match = Pattern.compile("\\{[\\s\\S]*}").matcher(raw);
            if (!match.find()) throw new IllegalStateException("Judge reply was not JSON.");
            JsonObject parsed = JsonParser.parseString(match.group()).getAsJsonObject();
            boolean ok = parsed.has("score") && parsed.get("score").isJsonPrimitive() && parsed.get("score").getAsJsonPrimitive().isNumber();
            Double score = ok ? parsed.get("score").getAsDouble() : null;
            String reasoning = parsed.has("reasoning") ? parsed.get("reasoning").getAsString() : "";
            if (ok) {
                requireClient().trackMetric(metric, buildContext(persona, "judge", locale),
                        LDValue.buildObject().put("judgeConfigKey", key).build(), score);
            }
            result.put("success", ok);
            result.put("score", score);
            result.put("reasoning", reasoning);
            result.put("passed", ok && score >= passThreshold());
            return result;
        } catch (RuntimeException exc) {
            result.put("success", false);
            result.put("score", null);
            result.put("reasoning", "");
            result.put("passed", false);
            result.put("error", exc.getMessage());
            return result;
        }
    }

    private static void safeTrack(LDContext context, String event, LDValue data, double metric) {
        try {
            requireClient().trackMetric(event, context, data, metric);
        } catch (RuntimeException ignored) {
            /* monitoring is best-effort */
        }
    }

    public static Map<String, Object> submitFeedback(Persona persona, String locale, String resumptionToken, String kind) {
        String token = resumptionToken == null ? "" : resumptionToken.trim();
        Persona stored = FEEDBACK_TOKENS.get(token);
        if (token.isEmpty() || stored == null) {
            throw new IllegalArgumentException("Generate first. Feedback attaches to the specialist draft.");
        }
        String kindL = kind == null ? "" : kind.trim().toLowerCase();
        boolean positive = kindL.equals("positive") || kindL.equals("up") || kindL.equals("+");
        boolean negative = kindL.equals("negative") || kindL.equals("down") || kindL.equals("-");
        if (!positive && !negative) throw new IllegalArgumentException("kind must be positive or negative.");
        // AI metrics / feedback — https://launchdarkly.com/docs/sdk/features/ai-metrics
        // Java has no resumption-token tracker. The token minted at draft time maps back to this context.
        safeTrack(buildContext(stored, "feedback", locale),
                positive ? EVT_FEEDBACK_POSITIVE : EVT_FEEDBACK_NEGATIVE,
                LDValue.buildObject().put("configKey", nodeKey("report")).build(),
                1.0);
        return Map.of("ok", true, "kind", positive ? "positive" : "negative");
    }

    public static void generateStream(
            Persona persona,
            String action,
            List<Map<String, Object>> tickerResults,
            List<String> selectedTools,
            String locale,
            Consumer<Map<String, Object>> emit
    ) {
        if (!VALID_SPECIALISTS.contains(action)) action = "report";
        if (!"es".equals(locale)) locale = "en";
        List<String> tools = new ArrayList<>();
        Set<String> wanted = new LinkedHashSet<>(selectedTools == null ? List.of() : selectedTools);
        for (String key : TOOL_ORDER) if (wanted.contains(key)) tools.add(key);
        if (!hasStories(tickerResults)) {
            emit.accept(Map.of("type", "error", "message", "Load stories first, then generate."));
            emit.accept(Map.of("type", "done"));
            return;
        }
        String storiesText = YahooNews.formatStoriesForPrompt(tickerResults);
        LDContext context = buildContext(persona, action, locale);
        GraphInfo graph;
        try {
            graph = evaluateGraph(context);
        } catch (RuntimeException exc) {
            emit.accept(Map.of("type", "error", "message", "agent graph failed: " + exc.getMessage()));
            emit.accept(Map.of("type", "done"));
            return;
        }
        emit.accept(mapOf(
                "type", "run", "action", action, "locale", locale,
                "personaId", persona.id(), "personaName", persona.name(),
                "graphKey", graphKey(), "tools", tools
        ));

        emit.accept(Map.of("type", "status", "message", "assess"));
        AgentEval assessCfg = evaluateAgent(nodeKey("assess"), context, instructionsFile("assess"), Map.of("locale", locale, "action", action));
        String assessRaw = ollamaComplete(assessCfg.modelName(), messages(
                assessCfg.instructions(),
                "UI action hint: " + action + "\n" + languageLine(locale) + "\n\nHEADLINES:\n" + storiesText + "\n\nReturn JSON only."
        ));
        String[] parsed = parseAssess(assessRaw, action);
        String specialist = parsed[0];
        String reason = parsed[1];
        if (!specialist.equals(action)) {
            specialist = action;
            reason = reason + " (using the action)";
        }
        if (graph.enabled && !graph.outgoingTargets(nodeKey("assess")).contains(nodeKey(specialist))) {
            specialist = "report";
            reason = reason + "; graph edge missing, fall through to report";
        }
        emit.accept(mapOf("type", "node", "role", "assess", "specialist", specialist, "reason", reason, "clip", clip(specialist + ": " + reason)));

        emit.accept(Map.of("type", "status", "message", specialist));
        AgentEval specCfg = evaluateAgent(nodeKey(specialist), context, instructionsFile(specialist), Map.of("locale", locale, "specialist", specialist));
        String specUser = "questions".equals(specialist)
                ? languageLine(locale) + "\n\nCANDIDATE QUESTIONS:\n" + readMessageFile("questions.txt") + "\n\nHEADLINES:\n" + storiesText
                : languageLine(locale) + "\n\nHEADLINES:\n" + storiesText + "\n\nProduce the " + specialist + " output now.";
        String draft = ollamaComplete(specCfg.modelName(), messages(specCfg.instructions(), specUser));
        String token = UUID.randomUUID().toString();
        FEEDBACK_TOKENS.put(token, persona);
        emit.accept(mapOf("type", "draft", "specialist", specialist, "text", draft, "clip", clip(draft), "resumptionToken", token));

        emit.accept(Map.of("type", "status", "message", "judges"));
        List<Map<String, Object>> judges = List.of(
                runOneJudge(judgeKey("fidelity"), persona, locale, storiesText, draft),
                runOneJudge(judgeKey("discipline"), persona, locale, storiesText, draft)
        );
        emit.accept(mapOf("type", "judges", "results", judges, "draft", draft));

        String transformed = draft;
        LDValue toolBase = LDValue.buildObject()
                .put("configKey", nodeKey(specialist))
                .put("variationKey", specCfg.variationKey())
                .put("version", specCfg.version())
                .put("modelName", specCfg.modelName())
                .put("providerName", "ollama")
                .put("graphKey", graphKey())
                .build();
        for (String key : tools) {
            if ("joke-tagline".equals(key)) {
                emit.accept(Map.of("type", "info", "message", "Setting humor level to " + HUMOR_LEVEL.getOrDefault(persona.id(), 50) + "%"));
            }
            transformed = applyTool(key, transformed, persona, locale);
            // Library tools — https://launchdarkly.com/docs/home/agentcontrol/tools
            safeTrack(context, EVT_NODE_TOOL_CALL, LDValue.buildObject()
                    .put("configKey", nodeKey(specialist))
                    .put("variationKey", specCfg.variationKey())
                    .put("version", specCfg.version())
                    .put("modelName", specCfg.modelName())
                    .put("providerName", "ollama")
                    .put("graphKey", graphKey())
                    .put("toolKey", key)
                    .build(), 1.0);
            emit.accept(mapOf("type", "tool", "key", key, "text", transformed, "clip", clip(transformed)));
        }

        if (graph.enabled && !graph.outgoingTargets(nodeKey(specialist)).contains(nodeKey("finalize"))) {
            emit.accept(Map.of("type", "error", "message", "Graph has no edge from " + nodeKey(specialist) + " to " + nodeKey("finalize") + "."));
            emit.accept(mapOf("type", "done", "resumptionToken", token));
            return;
        }
        safeTrack(context, EVT_GRAPH_HANDOFF_SUCCESS, LDValue.buildObject()
                .put("graphKey", graphKey()).put("version", graph.version)
                .put("sourceKey", nodeKey(specialist)).put("targetKey", nodeKey("finalize")).build(), 1.0);

        emit.accept(Map.of("type", "status", "message", "finalize"));
        AgentEval finCfg = evaluateAgent(nodeKey("finalize"), context, instructionsFile("finalize"), Map.of("locale", locale, "specialist", specialist));
        String rawFinal = ollamaComplete(finCfg.modelName(), messages(finCfg.instructions(), finalizeUser(locale, specialist, tools, transformed)));
        Guard guarded = guardFinalize(rawFinal, transformed, tools);
        for (String note : guarded.notes) emit.accept(mapOf("type", "info", "message", note, "kind", "guard"));

        Map<String, Object> sent = new LinkedHashMap<>();
        sent.put("graphKey", graphKey());
        sent.put("context", Map.of("key", persona.id(), "name", persona.name(), "action", action, "locale", locale));
        sent.put("variables", Map.of("action", action, "locale", locale, "stories", storiesText, "selectedTools", tools));
        sent.put("requestedPath", List.of(nodeKey("assess"), nodeKey(specialist), nodeKey("finalize")));
        Map<String, Object> received = new LinkedHashMap<>();
        Map<String, Object> graphSummary = new LinkedHashMap<>();
        graphSummary.put("key", graphKey());
        graphSummary.put("enabled", graph.enabled);
        graphSummary.put("variationKey", emptyToNull(graph.variationKey));
        graphSummary.put("version", graph.version);
        received.put("graph", graphSummary);
        received.put("route", specialist);
        received.put("path", List.of(nodeKey("assess"), nodeKey(specialist), nodeKey("finalize")));
        received.put("nodes", List.of(summary(nodeKey("assess"), assessCfg), summary(nodeKey(specialist), specCfg), summary(nodeKey("finalize"), finCfg)));
        received.put("tools", tools);
        received.put("judges", judges);
        received.put("transformedDraft", transformed);
        emit.accept(mapOf("type", "finalize", "text", guarded.text, "clip", clip(guarded.text)));

        ArrayBuilder path = LDValue.buildArray();
        for (String part : List.of(nodeKey("assess"), nodeKey(specialist), nodeKey("finalize"))) path.add(part);
        safeTrack(context, EVT_GRAPH_PATH, LDValue.buildObject().put("graphKey", graphKey()).put("version", graph.version).put("path", path.build()).build(), 1.0);
        safeTrack(context, EVT_GRAPH_INVOCATION_SUCCESS, LDValue.buildObject().put("graphKey", graphKey()).put("version", graph.version).build(), 1.0);
        safeTrack(context, EVT_NODE_GENERATION_SUCCESS, toolBase, 1.0);

        Map<String, Object> done = new LinkedHashMap<>();
        done.put("type", "done");
        done.put("specialist", specialist);
        done.put("tools", tools);
        done.put("path", List.of(nodeKey("assess"), nodeKey(specialist), nodeKey("finalize")));
        done.put("resumptionToken", token);
        done.put("draft", draft);
        done.put("text", guarded.text);
        done.put("ldTransaction", Map.of("sent", sent, "received", received));
        emit.accept(done);
    }

    private static Map<String, Object> summary(String key, AgentEval eval) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("key", key);
        out.put("enabled", eval.enabled());
        out.put("variationKey", emptyToNull(eval.variationKey()));
        out.put("version", eval.version());
        out.put("provider", "Custom");
        out.put("model", eval.modelName());
        return out;
    }

    private static String emptyToNull(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static Map<String, Object> mapOf(Object... kv) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) out.put(String.valueOf(kv[i]), kv[i + 1]);
        return out;
    }
}
