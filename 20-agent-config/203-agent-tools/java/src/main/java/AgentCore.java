import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.LDValueType;
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
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Domain logic for 23-agent-tools (no HTTP here).
 *
 * Teaching focus: AgentControl Library tools attached to a completion variation;
 * the app runs a model-driven tool loop and records tool-call events for Monitoring.
 *
 *   1. Data          Personas (Claude → Anthropic; Llama/Gwen → Ollama)
 *   2. LaunchDarkly  jsonValueVariationDetail on equity-briefing-tools
 *   3. Providers     Anthropic (cloud) or Ollama (local offline path)
 *   4. Generation    tool loop: analyze each ticker → compare → final briefing
 *
 * LaunchDarkly insertion point:
 *   generateStream() → LDClient.jsonValueVariationDetail(configKey, context, default)
 *
 * Java AI SDK is not published on Maven yet. Tool calls and generation metrics use
 * best-effort LDClient.trackMetric (see README for parity notes).
 *
 * Keywords: AgentControl · Library tools · tool loop · track_tool_call (best-effort)
 * Docs:
 *   https://launchdarkly.com/docs/home/agentcontrol/tools
 *   https://launchdarkly.com/docs/sdk/server-side/java
 */
public final class AgentCore {
    public static final List<Persona> PERSONAS = List.of(
            new Persona("analyst-claude", "Analyst Claude", "anthropic", null, false),
            new Persona("analyst-llama", "Analyst Llama", "ollama", "llama3.2:3b", false),
            new Persona("analyst-gwen", "Analyst Gwen", "ollama", "llama3.2:1b", false)
    );

    private static final String CANNED_STORIES =
            "No ticker stories loaded yet. Ask the user to click Get Stories.";
    // LaunchDarkly: ai-config key=equity-briefing-tools name="Equity briefing tools" mode=completion
    // https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tools

    private static final String DEFAULT_CONFIG_KEY = "equity-briefing-tools";
    private static final String DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5";
    private static final String DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
    private static final String TOOL_ANALYZE = "analyze-ticker-stories";
    private static final String TOOL_COMPARE = "compare-ticker-analyses";
    private static final int MAX_TOOL_STEPS = 6;
    private static final String OLLAMA_TOOL_SUFFIX =
            "Local-model rules (Ollama):\n"
                    + "- You MUST call tools before writing any briefing.\n"
                    + "- One tool call per turn when possible: analyze ticker 1, then analyze ticker 2, "
                    + "then compare-ticker-analyses.\n"
                    + "- Never call compare in the same turn as analyze.\n"
                    + "- Pass the exact analyze JSON as analysis_a / analysis_b — do not invent fields.\n"
                    + "- Do not skip compare-ticker-analyses after two analyzes.";

    /** Best-effort tool-call event (Python/Node: tracker.track_tool_call). */
    private static final String EVENT_TOOL_CALL = "$ld:ai:tool:call";
    private static final String EVENT_GENERATION_SUCCESS = "$ld:ai:generation:success";
    private static final String EVENT_GENERATION_ERROR = "$ld:ai:generation:error";

    private static final Set<String> POSITIVE_WORDS = Set.of(
            "surge", "soar", "gain", "gains", "rise", "rises", "jump", "jumps", "beat", "beats",
            "record", "growth", "upgrade", "bullish", "profit", "profits", "strong", "rally"
    );
    private static final Set<String> NEGATIVE_WORDS = Set.of(
            "fall", "falls", "drop", "drops", "plunge", "cut", "cuts", "miss", "misses", "loss",
            "losses", "downgrade", "bearish", "weak", "lawsuit", "probe", "decline", "risk", "risks"
    );
    private static final Pattern WORD_PATTERN = Pattern.compile("[a-zA-Z]+");

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private static volatile LDClient ldClient;

    private AgentCore() {
    }

    /** Selectable demo identity — also the LaunchDarkly user context. */
    public record Persona(String id, String name, String profile, String model, boolean anonymous) {
    }

    /** Parsed Library tool from the served variation JSON. */
    private record ToolDef(String name, String description, JsonObject parameters) {
    }

    public static Persona personaById(String personaId) {
        for (Persona p : PERSONAS) {
            if (p.id().equals(personaId)) {
                return p;
            }
        }
        return null;
    }

    public static String configKey() {
        String key = env("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).trim();
        return key.isEmpty() ? DEFAULT_CONFIG_KEY : key;
    }

    public static String defaultAnthropicModel() {
        String model = env("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL).trim();
        return model.isEmpty() ? DEFAULT_ANTHROPIC_MODEL : model;
    }

    public static String defaultOllamaModel() {
        String model = env("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).trim();
        return model.isEmpty() ? DEFAULT_OLLAMA_MODEL : model;
    }

    public static String personaRuntime(Persona persona) {
        String profile = persona.profile() == null ? "" : persona.profile().trim().toLowerCase();
        if (Set.of("ollama", "local", "gwen", "llama").contains(profile)) {
            return "ollama";
        }
        return "anthropic";
    }

    public static Map<String, String> personaModelName(Persona persona, String ldModel) {
        if ("ollama".equals(personaRuntime(persona))) {
            String pinned = persona.model() == null ? "" : persona.model().trim();
            return Map.of("provider", "ollama", "model", pinned.isEmpty() ? defaultOllamaModel() : pinned);
        }
        String model = ldModel != null && ldModel.startsWith("claude") ? ldModel : defaultAnthropicModel();
        return Map.of("provider", "anthropic", "model", model);
    }

    /**
     * Initialize the shared LaunchDarkly server SDK once at process start.
     *
     * LaunchDarkly: server-side Java SDK (no AI SDK for Java).
     * https://launchdarkly.com/docs/sdk/server-side/java
     */
    public static synchronized void initLaunchDarkly() {
        if (ldClient != null) {
            return;
        }
        String sdkKey = env("LD_SDK_KEY", "").trim();
        if (sdkKey.isEmpty()) {
            throw new IllegalStateException(
                    "LD_SDK_KEY is required. Export a server-side SDK key for the "
                            + "environment that targets " + DEFAULT_CONFIG_KEY + ".");
        }
        LDConfig config = new LDConfig.Builder().build();
        ldClient = new LDClient(sdkKey, config);
        if (!ldClient.isInitialized()) {
            try {
                ldClient.close();
            } catch (IOException ignored) {
            }
            ldClient = null;
            throw new IllegalStateException(
                    "LaunchDarkly client failed to initialize. Check LD_SDK_KEY and network.");
        }
    }

    private static LDClient requireClient() {
        if (ldClient == null) {
            initLaunchDarkly();
        }
        return ldClient;
    }

    public static LDContext buildContext(Persona persona) {
        return LDContext.builder(persona.id())
                .name(persona.name())
                .anonymous(persona.anonymous())
                .build();
    }

    public static Map<String, Object> contextAsMap(Persona persona) {
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("kind", "user");
        ctx.put("key", persona.id());
        ctx.put("name", persona.name());
        if (persona.anonymous()) {
            ctx.put("anonymous", true);
        }
        return ctx;
    }

    private static Path baselineMessagesDir() {
        return YahooNews.exampleRoot().resolve("rest").resolve("messages");
    }

    private static String readMessageFile(String name) {
        Path path = baselineMessagesDir().resolve(name);
        try {
            return Files.readString(path, StandardCharsets.UTF_8).trim();
        } catch (IOException exc) {
            throw new IllegalStateException("Could not read " + path + ": " + exc.getMessage(), exc);
        }
    }

    public static String baselineSystemPrompt() {
        return readMessageFile("baseline-system.txt");
    }

    public static String baselineUserTemplate() {
        return readMessageFile("baseline-user.txt");
    }

    public static LDValue baselineCompletionDefault() {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultAnthropicModel()).build())
                .put("provider", LDValue.buildObject().put("name", "anthropic").build())
                .put("messages", LDValue.buildArray()
                        .add(LDValue.buildObject()
                                .put("role", "system")
                                .put("content", baselineSystemPrompt())
                                .build())
                        .add(LDValue.buildObject()
                                .put("role", "user")
                                .put("content", baselineUserTemplate())
                                .build())
                        .build())
                .build();
    }

    private static String formatStories(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) {
            return CANNED_STORIES;
        }
        return YahooNews.formatStoriesForPrompt(tickerResults);
    }

    public static List<Map<String, String>> promptDisplaySections(String storiesText) {
        return List.of(
                Map.of("kind", "heading", "text", "Task"),
                Map.of("kind", "body", "text",
                        "Write an equity briefing for these tickers using the required tools."),
                Map.of("kind", "heading", "text", "Stories"),
                Map.of("kind", "code", "text", storiesText),
                Map.of("kind", "heading", "text", "Reminder"),
                Map.of("kind", "body", "text",
                        "Call analyze-ticker-stories once per ticker (pass that ticker's headlines), "
                                + "then compare-ticker-analyses, then write the briefing from tool results only.")
        );
    }

    private static String interpolate(String content, String storiesText, Persona persona) {
        if (content == null) {
            return "";
        }
        return content
                .replace("{{ stories }}", storiesText)
                .replace("{{stories}}", storiesText)
                .replace("{{ ldctx.name }}", persona.name())
                .replace("{{ldctx.name}}", persona.name());
    }

    private static List<Map<String, String>> parseMessages(
            LDValue value, String storiesText, Persona persona) {
        List<Map<String, String>> out = new ArrayList<>();
        LDValue messages = value.get("messages");
        if (messages.isNull() || messages.size() == 0) {
            return out;
        }
        for (LDValue msg : messages.values()) {
            String role = ldString(msg.get("role"));
            String content = interpolate(ldString(msg.get("content")), storiesText, persona);
            Map<String, String> row = new LinkedHashMap<>();
            row.put("role", role);
            row.put("content", content);
            out.add(row);
        }
        return out;
    }

    private static String modelName(LDValue value) {
        LDValue model = value.get("model");
        if (model.isNull()) {
            return "";
        }
        String name = ldString(model.get("name"));
        if (!name.isEmpty()) {
            return name;
        }
        return ldString(model.get("modelName"));
    }

    private static String providerName(LDValue value) {
        LDValue provider = value.get("provider");
        if (provider.isNull()) {
            return "";
        }
        return ldString(provider.get("name"));
    }

    private static boolean isEnabled(LDValue value) {
        LDValue meta = value.get("_ldMeta");
        if (!meta.isNull()) {
            LDValue enabled = meta.get("enabled");
            if (!enabled.isNull()) {
                return enabled.booleanValue();
            }
        }
        LDValue top = value.get("enabled");
        if (!top.isNull()) {
            return top.booleanValue();
        }
        return true;
    }

    private static JsonObject defaultToolSchema() {
        JsonObject schema = new JsonObject();
        schema.addProperty("type", "object");
        schema.add("properties", new JsonObject());
        return schema;
    }

    private static JsonObject ldValueToJsonObject(LDValue value) {
        if (value == null || value.isNull()) {
            return new JsonObject();
        }
        return JsonParser.parseString(value.toJsonString()).getAsJsonObject();
    }

    private static JsonObject toolParameters(LDValue tool) {
        for (String key : List.of("parameters", "schema", "input_schema")) {
            LDValue params = tool.get(key);
            if (!params.isNull()) {
                return ldValueToJsonObject(params);
            }
        }
        return defaultToolSchema();
    }

    private static List<ToolDef> parseTools(LDValue value) {
        List<ToolDef> out = new ArrayList<>();
        LDValue toolsVal = value.get("tools");
        if (toolsVal.isNull()) {
            return out;
        }
        if (toolsVal.getType() == LDValueType.ARRAY) {
            for (LDValue tool : toolsVal.values()) {
                String name = ldString(tool.get("name"));
                if (name.isEmpty()) {
                    name = ldString(tool.get("key"));
                }
                if (name.isEmpty()) {
                    continue;
                }
                out.add(new ToolDef(
                        name,
                        ldString(tool.get("description")),
                        toolParameters(tool)
                ));
            }
        } else {
            for (String key : toolsVal.keys()) {
                LDValue tool = toolsVal.get(key);
                String name = ldString(tool.get("name"));
                if (name.isEmpty()) {
                    name = key;
                }
                out.add(new ToolDef(
                        name,
                        ldString(tool.get("description")),
                        toolParameters(tool)
                ));
            }
        }
        return out;
    }

    private static List<Map<String, Object>> toolsToAnthropic(List<ToolDef> tools) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (ToolDef tool : tools) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("name", tool.name());
            row.put("description", tool.description());
            row.put("input_schema", GSON.fromJson(tool.parameters(), Map.class));
            out.add(row);
        }
        return out;
    }

    private static List<Map<String, Object>> toolsToOpenAi(List<ToolDef> tools) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (ToolDef tool : tools) {
            Map<String, Object> fn = new LinkedHashMap<>();
            fn.put("name", tool.name());
            fn.put("description", tool.description());
            fn.put("parameters", GSON.fromJson(tool.parameters(), Map.class));
            out.add(Map.of("type", "function", "function", fn));
        }
        return out;
    }

    private static EvaluationDetail<LDValue> evaluateCompletionDetail(Persona persona) {
        return requireClient().jsonValueVariationDetail(
                configKey(),
                buildContext(persona),
                baselineCompletionDefault());
    }

    private static Map<String, Object> evaluationMeta(
            EvaluationDetail<LDValue> detail, LDValue value) {
        LDValue meta = value == null || value.isNull() ? LDValue.ofNull() : value.get("_ldMeta");
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("variationKey", meta.isNull() ? null : nullIfEmpty(ldString(meta.get("variationKey"))));
        out.put("version", meta.isNull() || meta.get("version").isNull() ? null : meta.get("version").intValue());
        out.put("versionKey", meta.isNull() ? null : nullIfEmpty(ldString(meta.get("versionKey"))));
        out.put("mode", meta.isNull() ? null : nullIfEmpty(ldString(meta.get("mode"))));
        out.put("modelKey", meta.isNull() ? null : nullIfEmpty(ldString(meta.get("modelKey"))));
        out.put("modelVersion", meta.isNull() ? null : nullIfEmpty(ldString(meta.get("modelVersion"))));
        out.put("enabledMeta", meta.isNull() || meta.get("enabled").isNull()
                ? null
                : meta.get("enabled").booleanValue());
        out.put("variationIndex",
                detail.getVariationIndex() == EvaluationDetail.NO_VARIATION
                        ? null
                        : detail.getVariationIndex());
        out.put("reason", reasonAsMap(detail.getReason()));
        return out;
    }

    private static Map<String, Object> reasonAsMap(EvaluationReason reason) {
        if (reason == null) {
            return null;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("kind", reason.getKind() == null ? null : reason.getKind().name());
        if (reason.getKind() == EvaluationReason.Kind.RULE_MATCH) {
            out.put("ruleIndex", reason.getRuleIndex());
            out.put("ruleId", reason.getRuleId());
        }
        if (reason.getKind() == EvaluationReason.Kind.PREREQUISITE_FAILED) {
            out.put("prerequisiteKey", reason.getPrerequisiteKey());
        }
        if (reason.getKind() == EvaluationReason.Kind.ERROR && reason.getErrorKind() != null) {
            out.put("errorKind", reason.getErrorKind().name());
        }
        if (reason.isInExperiment()) {
            out.put("inExperiment", true);
        }
        return out;
    }

    private static Map<String, Object> buildLdTransaction(
            Persona persona,
            String storiesText,
            String configKeyValue,
            boolean fallback,
            String mode,
            String provider,
            String model,
            List<Map<String, String>> messages,
            Map<String, Object> servedMeta,
            Boolean enabled
    ) {
        Map<String, Object> sdkDefault = new LinkedHashMap<>();
        sdkDefault.put(
                "description",
                "LDValue default passed to jsonValueVariationDetail "
                        + "(baseline shape; used if config key is missing). "
                        + "Java has no AI SDK — server SDK JSON evaluation only.");
        sdkDefault.put("enabled", true);
        sdkDefault.put("model", defaultAnthropicModel());
        sdkDefault.put("provider", "anthropic");
        sdkDefault.put("messages", List.of(
                Map.of("role", "system", "content", baselineSystemPrompt()),
                Map.of("role", "user", "content", baselineUserTemplate())
        ));

        Map<String, Object> sent = new LinkedHashMap<>();
        sent.put("configKey", configKeyValue);
        sent.put("context", contextAsMap(persona));
        sent.put("variables", Map.of("stories", storiesText));
        sent.put("sdkDefault", sdkDefault);

        Map<String, Object> received = new LinkedHashMap<>();
        received.put("fallback", fallback);
        received.put("mode", mode);
        received.put("enabled", enabled);
        received.put("configKey", configKeyValue);
        received.put("variationKey", servedMeta == null ? null : servedMeta.get("variationKey"));
        received.put("variationIndex", servedMeta == null ? null : servedMeta.get("variationIndex"));
        received.put("reason", servedMeta == null ? null : servedMeta.get("reason"));
        received.put("version", servedMeta == null ? null : servedMeta.get("version"));
        received.put("versionKey", servedMeta == null ? null : servedMeta.get("versionKey"));
        received.put("ldMode", servedMeta == null ? null : servedMeta.get("mode"));
        received.put("modelKey", servedMeta == null ? null : servedMeta.get("modelKey"));
        received.put("modelVersion", servedMeta == null ? null : servedMeta.get("modelVersion"));
        received.put("provider", provider);
        received.put("model", model);
        received.put("messages", messages);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("sent", sent);
        out.put("received", received);
        return out;
    }

    private static String userMessageText(List<Map<String, String>> messages) {
        for (int i = messages.size() - 1; i >= 0; i--) {
            Map<String, String> msg = messages.get(i);
            if ("user".equals(msg.get("role"))) {
                return msg.getOrDefault("content", "");
            }
        }
        return "";
    }

    private static Map<String, Object> personaMap(Persona persona) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", persona.id());
        m.put("name", persona.name());
        m.put("profile", persona.profile());
        if (persona.model() != null) {
            m.put("model", persona.model());
        }
        m.put("anonymous", persona.anonymous());
        return m;
    }

    /**
     * Best-effort tool-call tracking (Python/Node: tracker.track_tool_call).
     *
     * LaunchDarkly: custom metric on $ld:ai:tool:call with toolName + configKey.
     * https://launchdarkly.com/docs/sdk/features/events
     */
    private static void trackToolCall(Persona persona, String toolName) {
        LDValue trackData = LDValue.buildObject()
                .put("configKey", configKey())
                .put("toolName", toolName)
                .build();
        requireClient().trackMetric(EVENT_TOOL_CALL, buildContext(persona), trackData, 1.0);
    }

    /** Best-effort generation success metric (Python/Node: trackMetricsOf). */
    private static void trackGenerationSuccess(Persona persona) {
        LDValue trackData = LDValue.buildObject().put("configKey", configKey()).build();
        requireClient().trackMetric(EVENT_GENERATION_SUCCESS, buildContext(persona), trackData, 1.0);
    }

    /** Best-effort generation error metric. */
    private static void trackGenerationError(Persona persona) {
        LDValue trackData = LDValue.buildObject().put("configKey", configKey()).build();
        requireClient().trackMetric(EVENT_GENERATION_ERROR, buildContext(persona), trackData, 1.0);
    }

    private static int sentimentScore(String text) {
        Matcher matcher = WORD_PATTERN.matcher(text.toLowerCase());
        int score = 0;
        while (matcher.find()) {
            String tok = matcher.group();
            if (POSITIVE_WORDS.contains(tok)) {
                score++;
            } else if (NEGATIVE_WORDS.contains(tok)) {
                score--;
            }
        }
        return score;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> handleAnalyzeTickerStories(Map<String, Object> args) {
        String ticker = stringOr(args.get("ticker"), "").trim().toUpperCase();
        if (ticker.isEmpty()) {
            ticker = "?";
        }
        Object rawStories = args.get("stories");
        List<Map<String, Object>> claims = new ArrayList<>();
        int score = 0;
        if (rawStories instanceof List<?> list) {
            for (Object item : list) {
                if (!(item instanceof Map<?, ?> storyMap)) {
                    continue;
                }
                Map<String, Object> story = (Map<String, Object>) storyMap;
                String title = stringOr(story.get("title"), "").trim();
                if (title.isEmpty()) {
                    continue;
                }
                int tone = sentimentScore(title);
                score += tone;
                String claim;
                if (tone > 0) {
                    claim = "Positive headline signal for " + ticker + ": " + title;
                } else if (tone < 0) {
                    claim = "Negative headline signal for " + ticker + ": " + title;
                } else {
                    claim = "Neutral headline for " + ticker + ": " + title;
                }
                claims.add(Map.of("claim", claim, "evidence_title", title));
            }
        }
        String summary;
        if (claims.isEmpty()) {
            summary = "No usable headlines provided for " + ticker + ".";
        } else if (score > 0) {
            summary = ticker + ": net positive headline tone (" + claims.size() + " stories).";
        } else if (score < 0) {
            summary = ticker + ": net negative headline tone (" + claims.size() + " stories).";
        } else {
            summary = ticker + ": mixed/neutral headline tone (" + claims.size() + " stories).";
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker", ticker);
        out.put("claims", claims);
        out.put("summary", summary);
        out.put("tone_score", score);
        return out;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> handleCompareTickerAnalyses(Map<String, Object> args) {
        Map<String, Object> a = args.get("analysis_a") instanceof Map<?, ?> ma
                ? (Map<String, Object>) ma
                : Map.of();
        Map<String, Object> b = args.get("analysis_b") instanceof Map<?, ?> mb
                ? (Map<String, Object>) mb
                : Map.of();
        String ta = stringOr(a.get("ticker"), "A").toUpperCase();
        String tb = stringOr(b.get("ticker"), "B").toUpperCase();
        int sa = intOr(a.get("tone_score"), 0);
        int sb = intOr(b.get("tone_score"), 0);

        String preferred = null;
        if (sa > sb) {
            preferred = ta;
        } else if (sb > sa) {
            preferred = tb;
        }

        List<String> evidenceA = evidenceTitles(a);
        List<String> evidenceB = evidenceTitles(b);

        List<String> rationaleParts = new ArrayList<>();
        rationaleParts.add(ta + " tone_score=" + sa + " (" + stance(sa) + "); "
                + tb + " tone_score=" + sb + " (" + stance(sb) + ").");
        if (preferred != null) {
            rationaleParts.add(preferred + " is the better option on headline tone alone.");
        } else {
            rationaleParts.add("No clear preferred ticker on headline tone.");
        }

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("ticker1", Map.of(
                "ticker", ta,
                "recommendation", stance(sa),
                "evidence", evidenceA
        ));
        out.put("ticker2", Map.of(
                "ticker", tb,
                "recommendation", stance(sb),
                "evidence", evidenceB
        ));
        out.put("preferred_ticker", preferred);
        out.put("rationale", String.join(" ", rationaleParts));
        return out;
    }

    @SuppressWarnings("unchecked")
    private static List<String> evidenceTitles(Map<String, Object> analysis) {
        List<String> out = new ArrayList<>();
        Object claimsObj = analysis.get("claims");
        if (claimsObj instanceof List<?> claims) {
            for (Object c : claims) {
                if (c instanceof Map<?, ?> claimMap) {
                    Object title = ((Map<String, Object>) claimMap).get("evidence_title");
                    if (title != null) {
                        String s = String.valueOf(title).trim();
                        if (!s.isEmpty()) {
                            out.add(s);
                        }
                    }
                }
            }
        }
        return out;
    }

    private static String stance(int score) {
        if (score > 0) {
            return "constructive";
        }
        if (score < 0) {
            return "cautious";
        }
        return "neutral";
    }

    private static Map<String, Object> dispatchTool(String name, Map<String, Object> rawInput) {
        if (TOOL_ANALYZE.equals(name)) {
            return handleAnalyzeTickerStories(rawInput);
        }
        if (TOOL_COMPARE.equals(name)) {
            return handleCompareTickerAnalyses(rawInput);
        }
        return Map.of("error", "Unknown tool: " + name);
    }

    private static boolean looksLikeAnalyzeResult(Object obj) {
        if (!(obj instanceof Map<?, ?> map)) {
            return false;
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> m = (Map<String, Object>) map;
        return m.containsKey("ticker") && (m.containsKey("tone_score") || m.containsKey("claims"));
    }

    private static Map<String, Object> normalizeCompareArgs(
            Map<String, Object> rawInput,
            List<Map<String, Object>> analyzeResults
    ) {
        Map<String, Object> a = rawInput.get("analysis_a") instanceof Map<?, ?> ma
                ? castMap(ma)
                : Map.of();
        Map<String, Object> b = rawInput.get("analysis_b") instanceof Map<?, ?> mb
                ? castMap(mb)
                : Map.of();
        if (looksLikeAnalyzeResult(a) && looksLikeAnalyzeResult(b)) {
            return Map.of("analysis_a", a, "analysis_b", b, "_rewritten", false);
        }
        if (analyzeResults.size() >= 2) {
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("analysis_a", analyzeResults.get(analyzeResults.size() - 2));
            out.put("analysis_b", analyzeResults.get(analyzeResults.size() - 1));
            out.put("_rewritten", true);
            return out;
        }
        return Map.of("analysis_a", a, "analysis_b", b, "_rewritten", false);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> castMap(Map<?, ?> map) {
        return (Map<String, Object>) map;
    }

    private static String ollamaToolName(Map<String, Object> call) {
        Object fn = call.get("function");
        if (!(fn instanceof Map<?, ?> fnMap)) {
            return "";
        }
        return stringOr(((Map<?, ?>) fnMap).get("name"), "");
    }

    private static List<Map<String, Object>> sortOllamaToolCalls(List<Map<String, Object>> calls) {
        List<Map<String, Object>> sorted = new ArrayList<>(calls);
        sorted.sort(Comparator.comparingInt(call -> {
            String name = ollamaToolName(call);
            if (TOOL_ANALYZE.equals(name)) {
                return 0;
            }
            if (TOOL_COMPARE.equals(name)) {
                return 1;
            }
            return 2;
        }));
        return sorted;
    }

    /**
     * Evaluate AgentControl JSON, run the tool loop, stream final briefing tokens.
     *
     * Event contract: meta | status | tool | token | error | metrics | done.
     */
    public static void generateStream(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String storiesText = formatStories(tickerResults);
        long started = System.nanoTime();
        Map<String, Object> metrics = emptyMetrics();
        List<Map<String, String>> inputSections = promptDisplaySections(storiesText);

        LDValue configValue;
        Map<String, Object> servedMeta;
        boolean enabledFlag;

        try {
            EvaluationDetail<LDValue> detail = evaluateCompletionDetail(persona);
            configValue = detail.getValue();
            if (configValue == null || configValue.isNull()) {
                configValue = baselineCompletionDefault();
            }
            servedMeta = evaluationMeta(detail, configValue);
            enabledFlag = isEnabled(configValue);
        } catch (Exception exc) {
            emitFallbackMeta(persona, storiesText, inputSections, tickerResults, null, false, emit);
            emit.accept(Map.of(
                    "type", "status",
                    "message", "LaunchDarkly evaluation failed (" + exc.getMessage() + "); using code baseline."
            ));
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Tool loop requires a live AgentControl config. "
                            + "Provision with rest/create-tools.sh && rest/create-config.sh. (" + exc + ")"
            ));
            metrics.put("finish_reason", "error");
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            trackGenerationError(persona);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        if (!enabledFlag) {
            emitFallbackMeta(persona, storiesText, inputSections, tickerResults, servedMeta, false, emit);
            emit.accept(Map.of(
                    "type", "status",
                    "message", "AgentControl config '" + configKey() + "' is off; tools path disabled."
            ));
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Enable the AgentControl config and attach Library tools to generate."
            ));
            metrics.put("finish_reason", "error");
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            trackGenerationError(persona);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        String ldModel = modelName(configValue);
        if (ldModel.isEmpty()) {
            ldModel = defaultAnthropicModel();
        }
        Map<String, String> runtime = personaModelName(persona, ldModel);
        String provider = runtime.get("provider");
        String modelName = runtime.get("model");

        List<Map<String, String>> messages = parseMessages(configValue, storiesText, persona);
        List<ToolDef> toolDefs = parseTools(configValue);
        List<Map<String, Object>> anthropicTools = toolsToAnthropic(toolDefs);
        List<Map<String, Object>> openaiTools = toolsToOpenAi(toolDefs);
        List<String> toolNames = toolDefs.stream().map(ToolDef::name).toList();

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("type", "meta");
        meta.put("persona", personaMap(persona));
        meta.put("input", userMessageText(messages).isEmpty() ? storiesText : userMessageText(messages));
        meta.put("inputSections", inputSections);
        meta.put("provider", provider);
        meta.put("model", modelName);
        meta.put("mode", "launchdarkly");
        meta.put("configKey", configKey());
        meta.put("fallback", false);
        meta.put("stories", tickerResults == null ? List.of() : tickerResults);
        meta.put("tools", toolNames);
        meta.put("tracked", true);
        meta.put("ldTransaction", buildLdTransaction(
                persona,
                storiesText,
                configKey(),
                false,
                "launchdarkly",
                provider,
                modelName,
                messages,
                servedMeta,
                true
        ));
        emit.accept(meta);

        if (toolNames.isEmpty()) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "No tools attached on this variation. Run rest/attach-tools.sh."
            ));
        }

        String system = "";
        List<Map<String, Object>> chat = new ArrayList<>();
        for (Map<String, String> msg : messages) {
            if ("system".equals(msg.get("role"))) {
                system = system.isEmpty() ? msg.get("content") : system + "\n\n" + msg.get("content");
            } else {
                chat.add(new LinkedHashMap<>(msg));
            }
        }

        String finalText;

        try {
            if ("ollama".equals(provider)) {
                finalText = runOllamaToolLoop(
                        persona, modelName, system, chat, openaiTools, toolNames,
                        metrics, emit
                );
            } else {
                String apiKey = env("ANTHROPIC_API_KEY", "").trim();
                if (apiKey.isEmpty()) {
                    emit.accept(Map.of(
                            "type", "error",
                            "message", "ANTHROPIC_API_KEY is required for Analyst Claude. "
                                    + "Switch to Analyst Llama or Analyst Gwen for local Ollama, "
                                    + "or export your Claude key."
                    ));
                    metrics.put("finish_reason", "error");
                    metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
                    trackGenerationError(persona);
                    emit.accept(Map.of("type", "metrics", "metrics", metrics));
                    emit.accept(Map.of("type", "done"));
                    return;
                }
                finalText = runAnthropicToolLoop(
                        persona, modelName, apiKey, system, chat, anthropicTools,
                        metrics, emit
                );
            }
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            trackGenerationError(persona);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        chunkYield(finalText, metrics, started, emit);
        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        trackGenerationSuccess(persona);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        emit.accept(Map.of("type", "done"));
    }

    private static void emitFallbackMeta(
            Persona persona,
            String storiesText,
            List<Map<String, String>> inputSections,
            List<Map<String, Object>> tickerResults,
            Map<String, Object> servedMeta,
            Boolean enabledFlag,
            Consumer<Map<String, Object>> emit
    ) {
        List<Map<String, String>> messages = List.of(
                Map.of("role", "system", "content", baselineSystemPrompt()),
                Map.of("role", "user", "content", baselineUserTemplate())
        );
        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("type", "meta");
        meta.put("persona", personaMap(persona));
        meta.put("input", storiesText);
        meta.put("inputSections", inputSections);
        meta.put("provider", "anthropic");
        meta.put("model", defaultAnthropicModel() + " (code baseline)");
        meta.put("mode", "baseline-fallback");
        meta.put("configKey", configKey());
        meta.put("fallback", true);
        meta.put("stories", tickerResults == null ? List.of() : tickerResults);
        meta.put("ldTransaction", buildLdTransaction(
                persona,
                storiesText,
                configKey(),
                true,
                "baseline-fallback",
                "anthropic",
                defaultAnthropicModel() + " (code baseline)",
                messages,
                servedMeta,
                enabledFlag == null ? false : enabledFlag
        ));
        emit.accept(meta);
    }

    @SuppressWarnings("unchecked")
    private static String runOllamaToolLoop(
            Persona persona,
            String modelName,
            String system,
            List<Map<String, Object>> chat,
            List<Map<String, Object>> openaiTools,
            List<String> toolNames,
            Map<String, Object> metrics,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        List<Map<String, Object>> ollamaMessages = new ArrayList<>();
        String ollamaSystem = system.isBlank()
                ? OLLAMA_TOOL_SUFFIX
                : (system + "\n\n" + OLLAMA_TOOL_SUFFIX).trim();
        if (!ollamaSystem.isBlank()) {
            ollamaMessages.add(Map.of("role", "system", "content", ollamaSystem));
        }
        ollamaMessages.addAll(chat);

        List<Map<String, Object>> analyzeResults = new ArrayList<>();
        List<String> calledTools = new ArrayList<>();
        boolean nudgedForTools = false;
        int toolCallIndex = 0;
        String finalText = "";
        boolean brokeEarly = false;

        for (int step = 0; step < MAX_TOOL_STEPS; step++) {
            JsonObject data = ollamaChat(modelName, ollamaMessages, openaiTools);
            addOllamaTokenMetrics(data, metrics);

            JsonObject message = data.has("message") && data.get("message").isJsonObject()
                    ? data.getAsJsonObject("message")
                    : new JsonObject();
            JsonArray toolCallsArr = message.has("tool_calls") && message.get("tool_calls").isJsonArray()
                    ? message.getAsJsonArray("tool_calls")
                    : new JsonArray();
            String content = message.has("content") && !message.get("content").isJsonNull()
                    ? message.get("content").getAsString()
                    : "";

            if (toolCallsArr.isEmpty()) {
                if (!nudgedForTools && !toolNames.isEmpty() && analyzeResults.isEmpty()
                        && step < MAX_TOOL_STEPS - 1) {
                    nudgedForTools = true;
                    emit.accept(Map.of(
                            "type", "status",
                            "message", persona.name() + " skipped tools on the first turn — nudging once "
                                    + "to run analyze → analyze → compare."
                    ));
                    ollamaMessages.add(GSON.fromJson(message, Map.class));
                    ollamaMessages.add(Map.of(
                            "role", "user",
                            "content", "Stop writing the briefing. Call tools now: "
                                    + TOOL_ANALYZE + " once per ticker, then "
                                    + TOOL_COMPARE + " with the exact analyze JSON results, "
                                    + "then write the briefing."
                    ));
                    continue;
                }
                finalText = content;
                brokeEarly = true;
                break;
            }

            ollamaMessages.add(GSON.fromJson(message, Map.class));
            List<Map<String, Object>> toolCalls = new ArrayList<>();
            for (JsonElement el : toolCallsArr) {
                if (el.isJsonObject()) {
                    toolCalls.add(GSON.fromJson(el, Map.class));
                }
            }

            for (Map<String, Object> call : sortOllamaToolCalls(toolCalls)) {
                Object fnObj = call.get("function");
                if (!(fnObj instanceof Map<?, ?> fnMap)) {
                    continue;
                }
                Map<String, Object> fn = castMap(fnMap);
                String name = stringOr(fn.get("name"), "");
                Object rawInput = fn.get("arguments");
                Map<String, Object> args = parseToolArgs(rawInput);

                boolean rewritten = false;
                if (TOOL_COMPARE.equals(name)) {
                    Map<String, Object> normalized = normalizeCompareArgs(args, analyzeResults);
                    rewritten = Boolean.TRUE.equals(normalized.get("_rewritten"));
                    args = new LinkedHashMap<>(normalized);
                    args.remove("_rewritten");
                    if (rewritten) {
                        emit.accept(Map.of(
                                "type", "status",
                                "message", "Rewrote compare args from prior analyze results "
                                        + "(local model invented or parallel-called compare)."
                        ));
                    }
                }

                Map<String, Object> result = dispatchTool(name, args);
                trackToolCall(persona, name);
                calledTools.add(name);
                if (TOOL_ANALYZE.equals(name) && looksLikeAnalyzeResult(result)) {
                    analyzeResults.add(result);
                }
                toolCallIndex++;
                emit.accept(toolEvent(name, args, result, toolCallIndex, step + 1));
                ollamaMessages.add(Map.of("role", "tool", "content", GSON.toJson(result)));
            }
        }

        if (!brokeEarly) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "Hit MAX_TOOL_STEPS=" + MAX_TOOL_STEPS + "; using last model text if any."
            ));
            if (finalText.isEmpty()) {
                finalText = "(No final text after tool loop.)";
            }
        }

        if (!calledTools.contains(TOOL_COMPARE) && analyzeResults.size() >= 2 && !toolNames.isEmpty()) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", persona.name() + " skipped compare-ticker-analyses — running it from prior "
                            + "analyze results, then asking for a final briefing."
            ));
            Map<String, Object> compareArgs = Map.of(
                    "analysis_a", analyzeResults.get(analyzeResults.size() - 2),
                    "analysis_b", analyzeResults.get(analyzeResults.size() - 1)
            );
            Map<String, Object> result = dispatchTool(TOOL_COMPARE, compareArgs);
            trackToolCall(persona, TOOL_COMPARE);
            toolCallIndex++;
            emit.accept(toolEvent(TOOL_COMPARE, compareArgs, result, toolCallIndex, "guardrail"));
            ollamaMessages.add(Map.of(
                    "role", "user",
                    "content", TOOL_COMPARE + " returned:\n" + GSON.toJson(result) + "\n\n"
                            + "Write the short equity briefing now using ONLY the tool "
                            + "results (analyze + compare). Cite evidence titles."
            ));
            try {
                JsonObject data = ollamaChat(modelName, ollamaMessages, List.of());
                addOllamaTokenMetrics(data, metrics);
                JsonObject message = data.has("message") && data.get("message").isJsonObject()
                        ? data.getAsJsonObject("message")
                        : new JsonObject();
                String brief = message.has("content") && !message.get("content").isJsonNull()
                        ? message.get("content").getAsString()
                        : "";
                if (!brief.isBlank()) {
                    finalText = brief;
                }
            } catch (Exception exc) {
                emit.accept(Map.of("type", "status", "message", "Post-compare briefing call failed: " + exc));
            }
        }

        return finalText;
    }

    @SuppressWarnings("unchecked")
    private static String runAnthropicToolLoop(
            Persona persona,
            String modelName,
            String apiKey,
            String system,
            List<Map<String, Object>> chat,
            List<Map<String, Object>> anthropicTools,
            Map<String, Object> metrics,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        String finalText = "";
        int toolCallIndex = 0;
        boolean brokeEarly = false;
        for (int step = 0; step < MAX_TOOL_STEPS; step++) {
            JsonObject response = anthropicMessages(modelName, apiKey, system, chat, anthropicTools);
            addAnthropicTokenMetrics(response, metrics);

            String stop = response.has("stop_reason") ? response.get("stop_reason").getAsString() : "";
            if (!"tool_use".equals(stop)) {
                finalText = anthropicText(response);
                brokeEarly = true;
                break;
            }

            List<Map<String, Object>> assistantContent = new ArrayList<>();
            List<Map<String, Object>> toolResults = new ArrayList<>();
            JsonArray contentArr = response.has("content") && response.get("content").isJsonArray()
                    ? response.getAsJsonArray("content")
                    : new JsonArray();

            for (JsonElement el : contentArr) {
                if (!el.isJsonObject()) {
                    continue;
                }
                JsonObject block = el.getAsJsonObject();
                String btype = block.has("type") ? block.get("type").getAsString() : "";
                if ("text".equals(btype)) {
                    assistantContent.add(Map.of(
                            "type", "text",
                            "text", block.has("text") ? block.get("text").getAsString() : ""
                    ));
                } else if ("tool_use".equals(btype)) {
                    String name = block.has("name") ? block.get("name").getAsString() : "";
                    String toolId = block.has("id") ? block.get("id").getAsString() : "";
                    Map<String, Object> rawInput = block.has("input") && block.get("input").isJsonObject()
                            ? GSON.fromJson(block.getAsJsonObject("input"), Map.class)
                            : Map.of();
                    Map<String, Object> result = dispatchTool(name, rawInput);
                    trackToolCall(persona, name);
                    toolCallIndex++;
                    emit.accept(toolEvent(name, rawInput, result, toolCallIndex, step + 1));
                    Map<String, Object> toolUse = new LinkedHashMap<>();
                    toolUse.put("type", "tool_use");
                    toolUse.put("id", toolId);
                    toolUse.put("name", name);
                    toolUse.put("input", rawInput);
                    assistantContent.add(toolUse);
                    toolResults.add(Map.of(
                            "type", "tool_result",
                            "tool_use_id", toolId,
                            "content", GSON.toJson(result)
                    ));
                }
            }
            chat.add(Map.of("role", "assistant", "content", assistantContent));
            chat.add(Map.of("role", "user", "content", toolResults));
        }

        if (!brokeEarly) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "Hit MAX_TOOL_STEPS=" + MAX_TOOL_STEPS + "; using last model text if any."
            ));
            if (finalText.isEmpty()) {
                finalText = "(No final text after tool loop.)";
            }
        }
        return finalText;
    }

    private static Map<String, Object> toolEvent(
            String name,
            Map<String, Object> args,
            Map<String, Object> result,
            int callIndex,
            Object round
    ) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("type", "tool");
        event.put("name", name);
        event.put("args", args);
        event.put("result", result);
        event.put("callIndex", callIndex);
        event.put("round", round);
        return event;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> parseToolArgs(Object rawInput) {
        if (rawInput instanceof Map<?, ?> map) {
            return castMap(map);
        }
        if (rawInput instanceof String s) {
            try {
                return GSON.fromJson(s.isBlank() ? "{}" : s, Map.class);
            } catch (Exception ignored) {
                return new LinkedHashMap<>();
            }
        }
        return new LinkedHashMap<>();
    }

    private static JsonObject ollamaChat(
            String model,
            List<Map<String, Object>> messages,
            List<Map<String, Object>> tools
    ) throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("stream", false);
        payload.put("messages", messages);
        if (tools != null && !tools.isEmpty()) {
            payload.put("tools", tools);
        }
        String body = GSON.toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create(host + "/api/chat"))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<String> response;
        try {
            response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (IOException | InterruptedException exc) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): " + exc.getMessage()
                            + ". Is Ollama running, and does `ollama list` include " + model + "?",
                    exc
            );
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): HTTP "
                            + response.statusCode() + " " + response.body()
                            + ". Is Ollama running, and does `ollama list` include " + model + "?"
            );
        }
        return JsonParser.parseString(response.body()).getAsJsonObject();
    }

    @SuppressWarnings("unchecked")
    private static JsonObject anthropicMessages(
            String model,
            String apiKey,
            String system,
            List<Map<String, Object>> chat,
            List<Map<String, Object>> tools
    ) throws IOException, InterruptedException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("max_tokens", 1024);
        payload.put("messages", chat);
        if (system != null && !system.isBlank()) {
            payload.put("system", system);
        }
        if (tools != null && !tools.isEmpty()) {
            payload.put("tools", tools);
        }

        HttpRequest request = HttpRequest.newBuilder(URI.create("https://api.anthropic.com/v1/messages"))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .header("x-api-key", apiKey)
                .header("anthropic-version", "2023-06-01")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(payload)))
                .build();

        HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Anthropic request failed: HTTP " + response.statusCode() + " " + response.body()
            );
        }
        return JsonParser.parseString(response.body()).getAsJsonObject();
    }

    private static String anthropicText(JsonObject response) {
        StringBuilder parts = new StringBuilder();
        if (response.has("content") && response.get("content").isJsonArray()) {
            for (JsonElement el : response.getAsJsonArray("content")) {
                if (!el.isJsonObject()) {
                    continue;
                }
                JsonObject block = el.getAsJsonObject();
                if ("text".equals(block.has("type") ? block.get("type").getAsString() : "")
                        && block.has("text")) {
                    parts.append(block.get("text").getAsString());
                }
            }
        }
        return parts.toString();
    }

    private static void addOllamaTokenMetrics(JsonObject data, Map<String, Object> metrics) {
        int prompt = data.has("prompt_eval_count") ? data.get("prompt_eval_count").getAsInt() : 0;
        int completion = data.has("eval_count") ? data.get("eval_count").getAsInt() : 0;
        metrics.put("prompt_tokens", intOr(metrics.get("prompt_tokens"), 0) + prompt);
        metrics.put("completion_tokens", intOr(metrics.get("completion_tokens"), 0) + completion);
        metrics.put("total_tokens", intOr(metrics.get("prompt_tokens"), 0) + intOr(metrics.get("completion_tokens"), 0));
    }

    private static void addAnthropicTokenMetrics(JsonObject response, Map<String, Object> metrics) {
        if (!response.has("usage") || !response.get("usage").isJsonObject()) {
            return;
        }
        JsonObject usage = response.getAsJsonObject("usage");
        int prompt = usage.has("input_tokens") ? usage.get("input_tokens").getAsInt() : 0;
        int completion = usage.has("output_tokens") ? usage.get("output_tokens").getAsInt() : 0;
        metrics.put("prompt_tokens", intOr(metrics.get("prompt_tokens"), 0) + prompt);
        metrics.put("completion_tokens", intOr(metrics.get("completion_tokens"), 0) + completion);
        metrics.put("total_tokens", intOr(metrics.get("prompt_tokens"), 0) + intOr(metrics.get("completion_tokens"), 0));
    }

    private static void chunkYield(
            String text,
            Map<String, Object> metrics,
            long started,
            Consumer<Map<String, Object>> emit
    ) {
        if (text == null || text.isEmpty()) {
            metrics.put("finish_reason", "stop");
            return;
        }
        metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);
        int size = 24;
        for (int i = 0; i < text.length(); i += size) {
            emit.accept(Map.of(
                    "type", "token",
                    "text", text.substring(i, Math.min(i + size, text.length()))
            ));
        }
        metrics.put("finish_reason", "stop");
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

    private static String ldString(LDValue value) {
        if (value == null || value.isNull()) {
            return "";
        }
        if (value.isString()) {
            return value.stringValue();
        }
        return value.toJsonString();
    }

    private static String nullIfEmpty(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static String stringOr(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String s = String.valueOf(value);
        return s.isEmpty() ? fallback : s;
    }

    private static int intOr(Object value, int fallback) {
        if (value instanceof Number n) {
            return n.intValue();
        }
        if (value == null) {
            return fallback;
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException exc) {
            return fallback;
        }
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null ? fallback : value;
    }
}
