import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

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
import java.util.Locale;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Domain logic for 24-agent-judges (no HTTP here).
 *
 * =============================================================================
 * HOW TO READ THIS FILE
 * =============================================================================
 *
 * Same equity-briefing product as 21, plus a **runtime judge gate**:
 *
 *   1. Data          Toby + Charlie personas
 *   2. LaunchDarkly  JSON variation for completion + both judge configs
 *   3. Providers     Ollama for drafts; Ollama non-streaming JSON for judges
 *   4. Generation    draft → both judges → optional one Charlie rewrite
 *
 * LaunchDarkly insertion (read first):
 *   generateStream() → LDClient.jsonValueVariationDetail(completion key)
 *   then jsonValueVariationDetail(each judge key) + local Ollama judge call
 *   Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
 *   Keywords: Judges · custom judges · JSON variation · runtime gate
 *
 * There is no official Java AI SDK. Completion and judge configs are ordinary
 * flag/config JSON — evaluate with the server SDK, interpolate {{ stories }}
 * locally, and for judges call Ollama with format=json (score + reasoning).
 * Note: Java AI SDK N/A — no create_judge; Ollama JSON is the judge workaround.
 */
public final class AgentCore {
    public static final List<Persona> PERSONAS = List.of(
            new Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker"),
            new Persona("conservative-charlie", "Conservative Charlie", "conservative")
    );

    public static final Persona CHARLIE = PERSONAS.get(1);

    private static final String CANNED_STORIES =
            "No ticker stories loaded yet. Ask the user to click Get Stories.";

    private static final String DEFAULT_CONFIG_KEY = "equity-briefing-judged";
    private static final String DEFAULT_JUDGE_FIDELITY_KEY = "equity-briefing-source-fidelity";
    private static final String DEFAULT_JUDGE_DISCIPLINE_KEY =
            "equity-briefing-recommendation-discipline";
    private static final String DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
    private static final double DEFAULT_PASS_THRESHOLD = 0.65;

    private static final String EVENT_GENERATION_SUCCESS = "$ld:ai:generation:success";
    private static final String JUDGE_JSON_SUFFIX =
            "Respond with JSON {\"score\":0.0-1.0,\"reasoning\":\"...\"}.";

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private static volatile LDClient ldClient;

    private AgentCore() {
    }

    /** Selectable demo identity — also the LaunchDarkly user context. */
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

    public static String configKey() {
        String key = env("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).trim();
        return key.isEmpty() ? DEFAULT_CONFIG_KEY : key;
    }

    public static String judgeFidelityKey() {
        String key = env("LD_JUDGE_FIDELITY_KEY", DEFAULT_JUDGE_FIDELITY_KEY).trim();
        return key.isEmpty() ? DEFAULT_JUDGE_FIDELITY_KEY : key;
    }

    public static String judgeDisciplineKey() {
        String key = env("LD_JUDGE_DISCIPLINE_KEY", DEFAULT_JUDGE_DISCIPLINE_KEY).trim();
        return key.isEmpty() ? DEFAULT_JUDGE_DISCIPLINE_KEY : key;
    }

    public static double passThreshold() {
        String raw = env("JUDGE_PASS_THRESHOLD", "").trim();
        if (raw.isEmpty()) {
            return DEFAULT_PASS_THRESHOLD;
        }
        try {
            return Double.parseDouble(raw);
        } catch (NumberFormatException exc) {
            return DEFAULT_PASS_THRESHOLD;
        }
    }

    public static String defaultOllamaModel() {
        String model = env("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).trim();
        return model.isEmpty() ? DEFAULT_OLLAMA_MODEL : model;
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
                            + "environment that targets equity-briefing-judged.");
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
                    "LaunchDarkly client failed to initialize within start wait. "
                            + "Check LD_SDK_KEY and network access to LaunchDarkly.");
        }
    }

    private static LDClient requireClient() {
        if (ldClient == null) {
            initLaunchDarkly();
        }
        return ldClient;
    }

    public static LDContext buildContext(Persona persona) {
        return LDContext.builder(persona.id()).name(persona.name()).build();
    }

    private static Map<String, Object> contextAsMap(Persona persona) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("kind", "user");
        m.put("key", persona.id());
        m.put("name", persona.name());
        return m;
    }

    private static Path messagesDir() {
        return YahooNews.exampleRoot().resolve("rest").resolve("messages");
    }

    private static String readMessageFile(String name) {
        Path path = messagesDir().resolve(name);
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException exc) {
            throw new IllegalStateException(
                    "Could not read message file " + path + ": " + exc.getMessage(), exc);
        }
    }

    private static String formatStories(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) {
            return CANNED_STORIES;
        }
        return YahooNews.formatStoriesForPrompt(tickerResults);
    }

    /**
     * SDK default when the completion config key is missing / unreachable
     * (concise-skeptic / Charlie shape from rest/messages/skeptic-*.txt).
     *
     * LaunchDarkly: JSON variation default for completion config evaluation.
     * https://launchdarkly.com/docs/sdk/server-side/java
     */
    public static LDValue skepticCompletionDefault() {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("messages", LDValue.buildArray()
                        .add(LDValue.buildObject()
                                .put("role", "system")
                                .put("content", readMessageFile("skeptic-system.txt").trim())
                                .build())
                        .add(LDValue.buildObject()
                                .put("role", "user")
                                .put("content", readMessageFile("skeptic-user.txt").trim())
                                .build())
                        .build())
                .build();
    }

    /**
     * SDK default for a judge config key (system message + evaluation metric).
     *
     * LaunchDarkly: JSON variation default for judge config evaluation.
     * https://launchdarkly.com/docs/home/agentcontrol/judges
     */
    public static LDValue judgeDefault(String systemFile, String metricKey) {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("evaluationMetricKey", metricKey)
                .put("messages", LDValue.buildArray()
                        .add(LDValue.buildObject()
                                .put("role", "system")
                                .put("content", readMessageFile(systemFile).trim())
                                .build())
                        .build())
                .build();
    }

    private static String defaultMetricForJudgeKey(String key) {
        if (key.contains("fidelity")) {
            return "$ld:ai:judge:source-fidelity";
        }
        if (key.contains("discipline")) {
            return "$ld:ai:judge:recommendation-discipline";
        }
        String suffix = key.replace("equity-briefing-", "");
        if (suffix.isEmpty()) {
            suffix = "custom";
        }
        return "$ld:ai:judge:" + suffix;
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

    /**
     * Evaluate AgentControl completion JSON via the server SDK.
     *
     * LaunchDarkly: {@code jsonValueVariationDetail} on the completion config key.
     * https://launchdarkly.com/docs/sdk/server-side/java
     * https://launchdarkly.com/docs/home/agentcontrol/quickstart
     */
    private static EvaluationDetail<LDValue> evaluateCompletionDetail(Persona persona) {
        return requireClient().jsonValueVariationDetail(
                configKey(),
                buildContext(persona),
                skepticCompletionDefault());
    }

    /**
     * Evaluate a judge config JSON via the server SDK (no Java AI SDK create_judge).
     *
     * LaunchDarkly: {@code jsonValueVariationDetail} on the judge config key.
     * https://launchdarkly.com/docs/home/agentcontrol/judges
     */
    private static EvaluationDetail<LDValue> evaluateJudgeDetail(String key, Persona persona) {
        String metric = defaultMetricForJudgeKey(key);
        String systemFile = key.contains("fidelity")
                ? "judge-source-fidelity-system.txt"
                : "judge-recommendation-discipline-system.txt";
        return requireClient().jsonValueVariationDetail(
                key,
                buildContext(persona),
                judgeDefault(systemFile, metric));
    }

    private static String userMessageText(List<Map<String, String>> messages) {
        for (Map<String, String> msg : messages) {
            if ("user".equals(msg.get("role"))) {
                return msg.getOrDefault("content", "");
            }
        }
        return "";
    }

    private static String systemMessageText(List<Map<String, String>> messages) {
        for (Map<String, String> msg : messages) {
            if ("system".equals(msg.get("role"))) {
                return msg.getOrDefault("content", "");
            }
        }
        return "";
    }

    private static Map<String, String> resolveRuntime(String model, String providerName) {
        String pl = providerName == null ? "" : providerName.trim().toLowerCase(Locale.ROOT);
        if (pl.equals("custom") || pl.equals("ollama") || (model != null && model.contains(":"))) {
            return Map.of("provider", "ollama", "model", model == null ? "" : model);
        }
        if (model == null || model.isBlank()) {
            throw new IllegalStateException(
                    "AgentControl variation has no model name. "
                            + "Check modelConfigKey on the served variation in LaunchDarkly.");
        }
        return Map.of("provider", "ollama", "model", model);
    }

    private static Map<String, Object> personaMap(Persona persona) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", persona.id());
        m.put("name", persona.name());
        m.put("profile", persona.profile());
        return m;
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
                        + "(concise-skeptic / Charlie shape; used if config key is missing). "
                        + "Judges gate the draft via judge config evaluation. "
                        + "Java has no AI SDK — server SDK JSON evaluation only.");
        sdkDefault.put("enabled", true);
        sdkDefault.put("model", defaultOllamaModel());
        sdkDefault.put("provider", "Custom");
        sdkDefault.put("messages", List.of(
                Map.of("role", "system", "content", readMessageFile("skeptic-system.txt").trim()),
                Map.of("role", "user", "content", readMessageFile("skeptic-user.txt").trim())
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

    private static String judgeInputText(String storiesText, List<String> tickers) {
        String tickerLine = "";
        if (tickers != null && !tickers.isEmpty()) {
            tickerLine = "Tickers: " + String.join(", ", tickers) + "\n\n";
        }
        return tickerLine
                + "Task: Write a short equity briefing comparing the tickers using only "
                + "the headlines below.\n\nHEADLINES:\n"
                + storiesText;
    }

    private static List<String> extractTickers(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null) {
            return List.of();
        }
        List<String> out = new ArrayList<>();
        for (Map<String, Object> row : tickerResults) {
            Object t = row.get("ticker");
            if (t == null) {
                continue;
            }
            String s = String.valueOf(t).trim();
            if (!s.isEmpty()) {
                out.add(s);
            }
        }
        return out;
    }

    private static boolean judgesPassed(List<Map<String, Object>> results) {
        for (Map<String, Object> r : results) {
            if (!Boolean.TRUE.equals(r.get("passed"))) {
                return false;
            }
        }
        return true;
    }

    private static void trackGenerationSuccess(Persona persona) {
        try {
            requireClient().trackMetric(
                    EVENT_GENERATION_SUCCESS,
                    buildContext(persona),
                    LDValue.ofNull(),
                    1.0);
        } catch (Exception ignored) {
            // Best-effort Monitoring hook — demos should not fail on track.
        }
    }

    private static void trackJudgeScore(Persona persona, String metricKey, double score) {
        try {
            requireClient().trackMetric(
                    metricKey,
                    buildContext(persona),
                    LDValue.ofNull(),
                    score);
        } catch (Exception ignored) {
            // Best-effort judge metric.
        }
    }

    /**
     * Run one judge: evaluate judge config JSON, then Ollama non-streaming JSON.
     *
     * Matches Python SDK judge input shape:
     *   system = judge messages + JSON instruction
     *   user   = MESSAGE HISTORY + RESPONSE TO EVALUATE
     */
    private static Map<String, Object> runOneJudge(
            String key, Persona persona, String inputText, String outputText) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("key", key);
        String metric = defaultMetricForJudgeKey(key);

        try {
            EvaluationDetail<LDValue> detail = evaluateJudgeDetail(key, persona);
            LDValue value = detail.getValue();
            if (value == null || value.isNull()) {
                value = judgeDefault(
                        key.contains("fidelity")
                                ? "judge-source-fidelity-system.txt"
                                : "judge-recommendation-discipline-system.txt",
                        metric);
            }

            LDValue metricVal = value.get("evaluationMetricKey");
            if (!metricVal.isNull() && metricVal.isString() && !metricVal.stringValue().isBlank()) {
                metric = metricVal.stringValue().trim();
            }

            if (!isEnabled(value)) {
                out.put("success", false);
                out.put("error", "judge config disabled or unsupported (enabled=false)");
                out.put("score", null);
                out.put("reasoning", null);
                out.put("metricKey", metric);
                out.put("sampled", true);
                out.put("passed", false);
                return out;
            }

            Map<String, String> runtime = resolveRuntime(modelName(value), providerName(value));
            String model = runtime.get("model");
            if (model == null || model.isBlank()) {
                model = defaultOllamaModel();
            }

            List<Map<String, String>> servedMessages = parseMessages(value, "", persona);
            String system = systemMessageText(servedMessages).trim();
            if (system.isEmpty()) {
                system = readMessageFile(
                        key.contains("fidelity")
                                ? "judge-source-fidelity-system.txt"
                                : "judge-recommendation-discipline-system.txt"
                ).trim();
            }
            if (!system.contains("Respond with JSON")) {
                system = system + "\n\n" + JUDGE_JSON_SUFFIX;
            }

            String user =
                    "MESSAGE HISTORY:\n"
                            + inputText
                            + "\n\nRESPONSE TO EVALUATE:\n"
                            + outputText;

            List<Map<String, String>> messages = List.of(
                    Map.of("role", "system", "content", system),
                    Map.of("role", "user", "content", user)
            );

            JsonObject parsed = ollamaJudgeJson(model, messages);
            Double score = null;
            String reasoning = null;
            if (parsed.has("score") && !parsed.get("score").isJsonNull()) {
                try {
                    score = parsed.get("score").getAsDouble();
                } catch (Exception ignored) {
                    score = null;
                }
            }
            if (parsed.has("reasoning") && !parsed.get("reasoning").isJsonNull()) {
                reasoning = parsed.get("reasoning").getAsString();
            }

            boolean passed = score != null && score >= passThreshold();
            out.put("success", true);
            out.put("error", null);
            out.put("score", score);
            out.put("reasoning", reasoning);
            out.put("metricKey", metric);
            out.put("sampled", true);
            out.put("passed", passed);

            if (score != null) {
                trackJudgeScore(persona, metric, score);
            }
            return out;
        } catch (Exception exc) {
            out.put("success", false);
            out.put("error", String.valueOf(exc.getMessage()));
            out.put("score", null);
            out.put("reasoning", null);
            out.put("metricKey", metric);
            out.put("sampled", true);
            out.put("passed", false);
            return out;
        }
    }

    private static List<Map<String, Object>> runJudges(
            Persona persona, String inputText, String draft) {
        return List.of(
                runOneJudge(judgeFidelityKey(), persona, inputText, draft),
                runOneJudge(judgeDisciplineKey(), persona, inputText, draft)
        );
    }

    /**
     * Draft → decorate → judge → optional one Charlie rewrite.
     *
     * Event contract: meta | section | token | judges | rewrite_meta | status |
     * error | metrics | done.
     */
    public static void generateStream(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String storiesText = formatStories(tickerResults);
        List<String> tickers = extractTickers(tickerResults);
        long started = System.nanoTime();
        Map<String, Object> metrics = emptyMetrics();
        double threshold = passThreshold();

        LDValue configValue;
        try {
            // LaunchDarkly: evaluate completion config JSON (model + messages).
            EvaluationDetail<LDValue> detail = evaluateCompletionDetail(persona);
            configValue = detail.getValue();
            if (configValue == null || configValue.isNull()) {
                configValue = skepticCompletionDefault();
            }
        } catch (Exception exc) {
            emit.accept(Map.of(
                    "type", "error",
                    "message", "LaunchDarkly completion_config failed: " + exc.getMessage()
            ));
            emit.accept(Map.of("type", "done"));
            return;
        }

        if (!isEnabled(configValue)) {
            emit.accept(Map.of(
                    "type", "error",
                    "message",
                    "AgentControl config '" + configKey()
                            + "' is off / enabled=false. Run rest/create-config.sh and update targeting."
            ));
            emit.accept(Map.of("type", "done"));
            return;
        }

        String provider;
        String model;
        List<Map<String, String>> messages;
        try {
            Map<String, String> runtime = resolveRuntime(
                    modelName(configValue), providerName(configValue));
            provider = runtime.get("provider");
            model = runtime.get("model");
            messages = parseMessages(configValue, storiesText, persona);
            if (messages.isEmpty()) {
                throw new IllegalStateException("Served variation has no messages.");
            }
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            emit.accept(Map.of("type", "done"));
            return;
        }

        String promptPreview = userMessageText(messages);
        if (promptPreview.isEmpty()) {
            promptPreview = storiesText;
        }

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("type", "meta");
        meta.put("persona", personaMap(persona));
        meta.put("input", promptPreview);
        meta.put("provider", provider);
        meta.put("model", model);
        meta.put("mode", "launchdarkly");
        meta.put("configKey", configKey());
        meta.put("judgeKeys", List.of(judgeFidelityKey(), judgeDisciplineKey()));
        meta.put("passThreshold", threshold);
        meta.put("stories", tickerResults == null ? List.of() : tickerResults);
        meta.put("ldTransaction", buildLdTransaction(
                persona,
                storiesText,
                configKey(),
                false,
                "launchdarkly",
                provider,
                model,
                messages,
                null,
                true
        ));
        emit.accept(meta);

        Map<String, Object> draftSection = new LinkedHashMap<>();
        draftSection.put("type", "section");
        draftSection.put("title", "Draft (" + persona.name() + ")");
        draftSection.put("kind", "draft");
        emit.accept(draftSection);

        String draft;
        try {
            draft = generateOllama(model, messages, started, metrics, emit).trim();
            trackGenerationSuccess(persona);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        emit.accept(Map.of(
                "type", "status",
                "message", "Running judges (Source Fidelity + Recommendation Discipline)…"
        ));

        List<Map<String, Object>> judgeResults;
        try {
            judgeResults = runJudges(persona, judgeInputText(storiesText, tickers), draft);
        } catch (Exception exc) {
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Judge evaluation failed: " + exc.getMessage()
            ));
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        boolean passed = judgesPassed(judgeResults);
        Map<String, Object> judgesSection = new LinkedHashMap<>();
        judgesSection.put("type", "section");
        judgesSection.put("title", "Judge scores");
        judgesSection.put("kind", "judges");
        emit.accept(judgesSection);

        Map<String, Object> judgesEvent = new LinkedHashMap<>();
        judgesEvent.put("type", "judges");
        judgesEvent.put("passed", passed);
        judgesEvent.put("threshold", threshold);
        judgesEvent.put("results", judgeResults);
        emit.accept(judgesEvent);

        if (passed) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", String.format(Locale.US, "Both judges ≥ %.2f — no rewrite.", threshold)
            ));
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            emit.accept(Map.of("type", "done"));
            return;
        }

        emit.accept(Map.of(
                "type", "status",
                "message", "Gate failed — rewriting once with Conservative Charlie…"
        ));
        Map<String, Object> rewriteSection = new LinkedHashMap<>();
        rewriteSection.put("type", "section");
        rewriteSection.put("title", "Rewrite (Conservative Charlie)");
        rewriteSection.put("kind", "rewrite");
        emit.accept(rewriteSection);

        Map<String, Object> rewriteMetrics = emptyMetrics();
        long rewriteStarted = System.nanoTime();
        try {
            EvaluationDetail<LDValue> charlieDetail = evaluateCompletionDetail(CHARLIE);
            LDValue charlieValue = charlieDetail.getValue();
            if (charlieValue == null || charlieValue.isNull()) {
                charlieValue = skepticCompletionDefault();
            }
            if (!isEnabled(charlieValue)) {
                throw new IllegalStateException("Charlie variation enabled=false; check targeting.");
            }
            Map<String, String> cRuntime = resolveRuntime(
                    modelName(charlieValue), providerName(charlieValue));
            List<Map<String, String>> cMessages = parseMessages(charlieValue, storiesText, CHARLIE);

            Map<String, Object> rewriteMeta = new LinkedHashMap<>();
            rewriteMeta.put("type", "rewrite_meta");
            rewriteMeta.put("persona", personaMap(CHARLIE));
            rewriteMeta.put("provider", cRuntime.get("provider"));
            rewriteMeta.put("model", cRuntime.get("model"));
            emit.accept(rewriteMeta);

            generateOllama(
                    cRuntime.get("model"), cMessages, rewriteStarted, rewriteMetrics, emit);
            trackGenerationSuccess(CHARLIE);
        } catch (Exception exc) {
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Charlie rewrite failed: " + exc.getMessage()
            ));
        }

        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        emit.accept(Map.of(
                "type", "status",
                "message", "Rewrite complete (one rewrite max; scores above are for the draft)."
        ));
        emit.accept(Map.of("type", "done"));
    }

    /**
     * Stream Ollama chat tokens; return the full completion text.
     */
    private static String generateOllama(
            String model,
            List<Map<String, String>> messages,
            long started,
            Map<String, Object> metrics,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        String url = host + "/api/chat";

        Map<String, Object> payload = Map.of(
                "model", model,
                "stream", true,
                "messages", messages
        );
        String body = GSON.toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<java.io.InputStream> response;
        try {
            response = HTTP.send(request, HttpResponse.BodyHandlers.ofInputStream());
        } catch (IOException | InterruptedException exc) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): "
                            + exc.getMessage()
                            + ". Is Ollama running, and does the model id match `ollama list`?",
                    exc
            );
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): HTTP "
                            + response.statusCode()
                            + ". Is Ollama running, and does the model id match `ollama list`?"
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
        fillTokenEstimates(messages, textParts.toString(), metrics);
        return textParts.toString();
    }

    /**
     * Non-streaming Ollama chat with {@code format: "json"} for judge score+reasoning.
     * Workaround for missing Java AI SDK create_judge / evaluate.
     */
    private static JsonObject ollamaJudgeJson(String model, List<Map<String, String>> messages)
            throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        String url = host + "/api/chat";

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("stream", false);
        payload.put("format", "json");
        payload.put("options", Map.of("temperature", 0));
        payload.put("messages", messages);
        String body = GSON.toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<String> response;
        try {
            response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (IOException | InterruptedException exc) {
            throw new IOException(
                    "Ollama judge request failed (" + host + ", model=" + model + "): "
                            + exc.getMessage(),
                    exc
            );
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama judge request failed (" + host + ", model=" + model + "): HTTP "
                            + response.statusCode());
        }

        JsonObject data = JsonParser.parseString(response.body()).getAsJsonObject();
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
        if (content.isBlank()) {
            throw new IOException("Judge Ollama response had empty content.");
        }
        try {
            return JsonParser.parseString(content).getAsJsonObject();
        } catch (Exception exc) {
            throw new IOException("Judge response was not JSON: " + content, exc);
        }
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

    private static void fillTokenEstimates(
            List<Map<String, String>> messages, String completion, Map<String, Object> metrics) {
        StringBuilder prompt = new StringBuilder();
        for (Map<String, String> m : messages) {
            prompt.append(m.getOrDefault("content", ""));
        }
        int promptTokens = estimateTokens(prompt.toString());
        int completionTokens = estimateTokens(completion);
        metrics.put("prompt_tokens", promptTokens);
        metrics.put("completion_tokens", completionTokens);
        metrics.put("total_tokens", promptTokens + completionTokens);
    }

    private static int estimateTokens(String text) {
        if (text == null || text.isEmpty()) {
            return 1;
        }
        return Math.max(1, text.length() / 4);
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

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null ? fallback : value;
    }
}
