import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
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
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;

/**
 * Domain logic for 22-config-outside-code (no HTTP here).
 *
 * =============================================================================
 * HOW TO READ THIS FILE
 * =============================================================================
 *
 * Teaching focus: AgentControl completion **outside code**, with Monitoring
 * metrics + thumbs feedback as the headline (same product as Python/Node 22).
 *
 *   1. Data          Best Betty → Anthropic; Anonymous Amelia → Ollama
 *   2. LaunchDarkly  JSON variation evaluation of the AI config key
 *   3. Providers     Ollama (default) or Anthropic (Best Betty)
 *   4. Generation    generateStream() — evaluate, call LLM, mint feedback token
 *
 * LaunchDarkly insertion point:
 *   generateStream() → LDClient.jsonValueVariationDetail(configKey, context, default)
 *
 * Java AI SDK is not published on Maven yet (unlike Python/Node). This example
 * still evaluates the config with the server SDK, calls Anthropic/Ollama, and
 * records thumbs via LDClient.track on $ld:ai:feedback:* event keys. Full
 * trackMetricsOf / official resumption-token parity lives in Python/Node.
 *
 * Keywords: AgentControl · completion config · AI metrics · feedback
 * Docs:
 *   https://launchdarkly.com/docs/sdk/server-side/java
 *   https://launchdarkly.com/docs/home/agentcontrol/quickstart
 *   https://launchdarkly.com/docs/guides/agentcontrol/config-outside-code-nodejs
 */
public final class AgentCore {
    public static final List<Persona> PERSONAS = List.of(
            // Best Betty → tracked-anthropic (Claude). Anonymous Amelia → tracked-ollama.
            new Persona("best-betty", "Best Betty", "best", false),
            new Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", true)
    );

    private static final String CANNED_STORIES =
            "No ticker stories loaded yet. Ask the user to click Get Stories.";
    // LaunchDarkly: ai-config key=equity-briefing-tracked-completion name="Equity briefing tracked completion" mode=completion
    // https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tracked-completion

    private static final String DEFAULT_CONFIG_KEY = "equity-briefing-tracked-completion";
    private static final String DEFAULT_OLLAMA_MODEL = "llama3.2:1b";
    private static final String DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5";
    private static final String EVENT_FEEDBACK_POSITIVE = "$ld:ai:feedback:user:positive";
    private static final String EVENT_FEEDBACK_NEGATIVE = "$ld:ai:feedback:user:negative";

    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private static volatile LDClient ldClient;
    /** Synthetic feedback tokens → persona id (Java AI SDK resumption tokens N/A). */
    private static final ConcurrentHashMap<String, String> FEEDBACK_TOKENS =
            new ConcurrentHashMap<>();

    private AgentCore() {
    }

    /** Selectable demo identity — also the LaunchDarkly user context. */
    public record Persona(String id, String name, String profile, boolean anonymous) {
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
                            + "environment that targets equity-briefing-tracked-completion.");
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

    /**
     * Build the LD evaluation context for this persona.
     *
     * Best Betty: named user (name targeting → tracked-anthropic).
     * Anonymous Amelia: fixed key + anonymous=true — not indexed as a known user;
     * name rules do not match → fallthrough (tracked-ollama).
     * https://launchdarkly.com/docs/sdk/features/anonymous
     */
    public static LDContext buildContext(Persona persona) {
        // Always set anonymous explicitly so event payloads match Python/Node
        // (omitting the attribute serializes as anonymous=false).
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
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException exc) {
            throw new IllegalStateException(
                    "Could not read baseline message file " + path + ": " + exc.getMessage(), exc);
        }
    }

    /** In-code baseline system prompt (same text as rest/messages/baseline-system.txt). */
    public static String baselineSystemPrompt() {
        return readMessageFile("baseline-system.txt").trim();
    }

    /** User prompt template with {{ stories }} (rest/messages/baseline-user.txt). */
    public static String baselineUserTemplate() {
        return readMessageFile("baseline-user.txt").trim();
    }

    /** Fill {{ stories }} locally when using the code baseline fallback. */
    public static String renderBaselineUser(String storiesText) {
        return baselineUserTemplate()
                .replace("{{ stories }}", storiesText)
                .replace("{{stories}}", storiesText);
    }

    /** Chat messages for the in-code baseline-analyst fallback. */
    public static List<Map<String, String>> baselineMessages(String storiesText) {
        return List.of(
                Map.of("role", "system", "content", baselineSystemPrompt()),
                Map.of("role", "user", "content", renderBaselineUser(storiesText))
        );
    }

    /**
     * SDK default when the config key is missing / unreachable (baseline-analyst shape).
     *
     * When the config exists but is turned off, LaunchDarkly still returns the
     * disabled variation ({@code _ldMeta.enabled=false}) — see generateStream().
     */
    public static LDValue baselineCompletionDefault() {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
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

    /**
     * Interpolate mustache-style placeholders the AI SDK would normally fill.
     * Supports {{ stories }} / {{stories}} and optional {{ ldctx.name }}.
     */
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
        // Missing meta on a real variation is unusual; treat as enabled.
        return true;
    }

    /**
     * Evaluate AgentControl completion JSON via the server SDK.
     *
     * LaunchDarkly: {@code jsonValueVariationDetail} on the AI config key
     * (same underlying evaluation AI SDKs use via {@code client.variation}).
     * https://launchdarkly.com/docs/sdk/server-side/java
     * https://launchdarkly.com/docs/home/agentcontrol/quickstart
     */
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

    private static void logServedVariation(Persona persona, Map<String, Object> meta) {
        if (meta == null) {
            System.out.println("[generate] " + persona.name() + ": variation=(unknown)");
            return;
        }
        Object key = meta.get("variationKey");
        String keyLabel = key == null ? "(none)" : String.valueOf(key);
        Object reason = meta.get("reason");
        Object reasonKind = reason;
        if (reason instanceof Map<?, ?> reasonMap) {
            reasonKind = reasonMap.get("kind");
        }
        System.out.println(
                "[generate] " + persona.name()
                        + ": variation='" + keyLabel + "' reason='" + reasonKind + "'");
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

    private static String systemPromptPreview(List<Map<String, String>> messages) {
        String text = systemMessageText(messages).trim();
        if (text.isEmpty()) {
            return "(none)";
        }
        String firstLine = text.split("\\R", 2)[0].trim();
        if (firstLine.length() > 40) {
            return firstLine.substring(0, 39) + "…";
        }
        return firstLine;
    }

    private static void logSystemPromptSource(
            String source, List<Map<String, String>> messages, Persona persona) {
        System.out.println(
                "[generate] " + persona.name()
                        + ": system prompt from " + source + ": '"
                        + systemPromptPreview(messages) + "'");
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
                        + "(baseline-analyst shape; used if config key is missing). "
                        + "Java has no AI SDK — server SDK JSON evaluation only.");
        sdkDefault.put("enabled", true);
        sdkDefault.put("model", defaultOllamaModel());
        sdkDefault.put("provider", "Custom");
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

    private static Map<String, String> resolveRuntime(String model, String providerName) {
        String pl = providerName == null ? "" : providerName.trim().toLowerCase();
        String m = model == null ? "" : model;

        if (pl.equals("anthropic") || m.startsWith("claude-")) {
            return Map.of(
                    "provider", "anthropic",
                    "model", m.isEmpty() ? DEFAULT_ANTHROPIC_MODEL : m
            );
        }
        if (pl.equals("custom") || pl.equals("ollama") || m.contains(":")) {
            return Map.of("provider", "ollama", "model", m.isEmpty() ? defaultOllamaModel() : m);
        }
        if (m.isBlank()) {
            throw new IllegalStateException(
                    "AgentControl variation has no model name. "
                            + "Check modelConfigKey on the served variation in LaunchDarkly.");
        }
        return Map.of("provider", "ollama", "model", m);
    }

    private static String mintFeedbackToken(Persona persona) {
        String token = UUID.randomUUID().toString();
        FEEDBACK_TOKENS.put(token, persona.id());
        return token;
    }

    /**
     * Record thumbs feedback against a synthetic token from generateStream.
     *
     * Matches Node AI SDK {@code trackFeedback}: 
     * {@code track(eventKey, context, trackData, 1)} → Java {@code trackMetric}.
     * LaunchDarkly: $ld:ai:feedback:* · metric value 1
     * https://launchdarkly.com/docs/sdk/features/events
     */
    public static Map<String, Object> submitFeedback(Persona persona, String resumptionToken, String kind) {
        String token = resumptionToken == null ? "" : resumptionToken.trim();
        if (token.isEmpty()) {
            throw new IllegalArgumentException("resumptionToken is required.");
        }
        String storedPersonaId = FEEDBACK_TOKENS.get(token);
        if (storedPersonaId == null) {
            throw new IllegalArgumentException(
                    "Unknown resumptionToken (generate again, then thumbs).");
        }
        // Prefer the persona that minted the token (same run as generate).
        Persona tracked = personaById(storedPersonaId);
        if (tracked == null) {
            tracked = persona;
        }
        LDContext context = buildContext(tracked);
        String kindL = kind == null ? "" : kind.trim().toLowerCase();
        String eventKey;
        String normalized;
        if (kindL.equals("positive") || kindL.equals("up") || kindL.equals("thumbsup") || kindL.equals("+")) {
            eventKey = EVENT_FEEDBACK_POSITIVE;
            normalized = "positive";
        } else if (kindL.equals("negative") || kindL.equals("down") || kindL.equals("thumbsdown") || kindL.equals("-")) {
            eventKey = EVENT_FEEDBACK_NEGATIVE;
            normalized = "negative";
        } else {
            throw new IllegalArgumentException("kind must be positive or negative.");
        }
        // Node AI SDK: track(key, context, getTrackData(), 1)
        LDValue trackData = LDValue.buildObject()
                .put("configKey", configKey())
                .build();
        requireClient().trackMetric(eventKey, context, trackData, 1.0);
        FEEDBACK_TOKENS.remove(token);
        return Map.of(
                "ok", true,
                "kind", normalized,
                "anonymous", context.isAnonymous(),
                "trackedVia", "LDClient.trackMetric"
        );
    }

    private static Map<String, Object> personaMap(Persona persona) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", persona.id());
        m.put("name", persona.name());
        m.put("profile", persona.profile());
        m.put("anonymous", persona.anonymous());
        return m;
    }

    /**
     * Evaluate AgentControl JSON, then stream tokens from the served model.
     *
     * Event contract: meta | status | token | error | metrics | done.
     *
     * When the AgentControl config is disabled (or returns enabled=false),
     * fall back to the in-code baseline-analyst prompts + local Ollama model —
     * same text as rest/messages/baseline-*.txt.
     */
    public static void generateStream(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String storiesText = formatStories(tickerResults);
        long started = System.nanoTime();
        Map<String, Object> metrics = emptyMetrics();

        boolean usingFallback = false;
        LDValue configValue = null;
        Map<String, Object> servedMeta = null;
        String fallbackReason = null;
        Boolean enabledFlag = null;

        try {
            // LaunchDarkly: evaluate completion config JSON (model + messages).
            EvaluationDetail<LDValue> detail = evaluateCompletionDetail(persona);
            configValue = detail.getValue();
            if (configValue == null || configValue.isNull()) {
                configValue = baselineCompletionDefault();
            }
            servedMeta = evaluationMeta(detail, configValue);
            enabledFlag = isEnabled(configValue);
            if (!enabledFlag) {
                usingFallback = true;
                fallbackReason =
                        "AgentControl config '" + configKey()
                                + "' is off / enabled=false; using code baseline-analyst.";
            }
        } catch (Exception exc) {
            usingFallback = true;
            configValue = null;
            servedMeta = null;
            enabledFlag = false;
            fallbackReason =
                    "LaunchDarkly evaluation failed (" + exc.getMessage() + "); using code baseline.";
        }

        if (usingFallback) {
            List<Map<String, String>> messages = baselineMessages(storiesText);
            String provider = "ollama";
            String model = defaultOllamaModel();
            String mode = "baseline-fallback";
            System.out.println(
                    "[generate] " + persona.name()
                            + ": variation='code-baseline' reason='FALLBACK'");
            logSystemPromptSource("code baseline (AgentControl off)", messages, persona);
            String promptPreview = userMessageText(messages);
            if (promptPreview.isEmpty()) {
                promptPreview = storiesText;
            }

            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("type", "meta");
            meta.put("persona", personaMap(persona));
            meta.put("input", promptPreview);
            meta.put("provider", provider);
            meta.put("model", model + " (code baseline)");
            meta.put("mode", mode);
            meta.put("configKey", configKey());
            meta.put("fallback", true);
            meta.put("stories", tickerResults == null ? List.of() : tickerResults);
            meta.put("ldTransaction", buildLdTransaction(
                    persona,
                    storiesText,
                    configKey(),
                    true,
                    mode,
                    provider,
                    model + " (code baseline)",
                    messages,
                    servedMeta,
                    enabledFlag == null ? false : enabledFlag
            ));
            emit.accept(meta);

            if (fallbackReason != null) {
                emit.accept(Map.of("type", "status", "message", fallbackReason));
            }
            try {
                generateOllama(model, messages, started, metrics, emit);
            } catch (Exception exc) {
                emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
                metrics.put("finish_reason", "error");
            }
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            Map<String, Object> doneFb = new LinkedHashMap<>();
            doneFb.put("type", "done");
            doneFb.put("resumptionToken", null);
            emit.accept(doneFb);
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
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("type", "meta");
            meta.put("persona", personaMap(persona));
            meta.put("input", storiesText);
            meta.put("provider", "—");
            meta.put("model", "—");
            meta.put("mode", "launchdarkly");
            meta.put("configKey", configKey());
            meta.put("stories", tickerResults == null ? List.of() : tickerResults);
            emit.accept(meta);
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
            metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
            emit.accept(Map.of("type", "metrics", "metrics", metrics));
            Map<String, Object> doneErr = new LinkedHashMap<>();
            doneErr.put("type", "done");
            doneErr.put("resumptionToken", null);
            emit.accept(doneErr);
            return;
        }

        logServedVariation(persona, servedMeta);
        logSystemPromptSource("LaunchDarkly (" + configKey() + ")", messages, persona);
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
        meta.put("variationKey", servedMeta == null ? null : servedMeta.get("variationKey"));
        meta.put("fallback", false);
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
                servedMeta,
                enabledFlag == null || enabledFlag
        ));
        emit.accept(meta);

        String resumptionToken = mintFeedbackToken(persona);
        try {
            if ("ollama".equals(provider)) {
                generateOllama(model, messages, started, metrics, emit);
            } else if ("anthropic".equals(provider)) {
                generateAnthropic(model, messages, started, metrics, emit);
            } else {
                throw new IllegalStateException("Unsupported runtime provider '" + provider + "'.");
            }
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
        }

        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        Map<String, Object> done = new LinkedHashMap<>();
        done.put("type", "done");
        done.put("resumptionToken", resumptionToken);
        emit.accept(done);
    }

    /**
     * Non-streaming Anthropic Messages API, then chunk tokens to the SSE UI.
     * Best Betty → tracked-anthropic (claude-sonnet-5).
     */
    private static void generateAnthropic(
            String model,
            List<Map<String, String>> messages,
            long started,
            Map<String, Object> metrics,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        String apiKey = env("ANTHROPIC_API_KEY", "").trim();
        if (apiKey.isEmpty()) {
            throw new IllegalStateException(
                    "ANTHROPIC_API_KEY is required for Anthropic variations "
                            + "(Best Betty → tracked-anthropic)."
            );
        }

        String system = "";
        List<Map<String, String>> userAssistant = new ArrayList<>();
        for (Map<String, String> msg : messages) {
            String role = msg.getOrDefault("role", "");
            String content = msg.getOrDefault("content", "");
            if ("system".equals(role)) {
                if (!system.isEmpty()) {
                    system = system + "\n\n";
                }
                system = system + content;
            } else if ("user".equals(role) || "assistant".equals(role)) {
                userAssistant.add(Map.of("role", role, "content", content));
            }
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("max_tokens", 1024);
        payload.put("messages", userAssistant);
        if (!system.isBlank()) {
            payload.put("system", system);
        }
        String body = new com.google.gson.Gson().toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create("https://api.anthropic.com/v1/messages"))
                .timeout(Duration.ofSeconds(120))
                .header("Content-Type", "application/json")
                .header("x-api-key", apiKey)
                .header("anthropic-version", "2023-06-01")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();

        HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Anthropic request failed: HTTP " + response.statusCode()
                            + " " + response.body()
            );
        }

        JsonObject data = JsonParser.parseString(response.body()).getAsJsonObject();
        StringBuilder text = new StringBuilder();
        if (data.has("content") && data.get("content").isJsonArray()) {
            for (com.google.gson.JsonElement el : data.getAsJsonArray("content")) {
                if (!el.isJsonObject()) {
                    continue;
                }
                JsonObject block = el.getAsJsonObject();
                String type = block.has("type") ? block.get("type").getAsString() : "";
                if ("text".equals(type) && block.has("text")) {
                    text.append(block.get("text").getAsString());
                }
            }
        }

        int promptTokens = 0;
        int completionTokens = 0;
        if (data.has("usage") && data.get("usage").isJsonObject()) {
            JsonObject usage = data.getAsJsonObject("usage");
            if (usage.has("input_tokens")) {
                promptTokens = usage.get("input_tokens").getAsInt();
            }
            if (usage.has("output_tokens")) {
                completionTokens = usage.get("output_tokens").getAsInt();
            }
        }
        metrics.put("prompt_tokens", promptTokens);
        metrics.put("completion_tokens", completionTokens);
        metrics.put("total_tokens", promptTokens + completionTokens);
        metrics.put("finish_reason", "stop");
        metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);

        String full = text.toString();
        int size = 24;
        for (int i = 0; i < full.length(); i += size) {
            emit.accept(Map.of(
                    "type", "token",
                    "text", full.substring(i, Math.min(i + size, full.length()))
            ));
        }
    }

    private static void generateOllama(
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
                    "Ollama request failed (" + host + ", model=" + model + "): "
                            + exc.getMessage()
                            + ". Is Ollama running, and does the AgentControl model id match `ollama list`?",
                    exc
            );
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): HTTP "
                            + response.statusCode()
                            + ". Is Ollama running, and does the AgentControl model id match `ollama list`?"
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

    private static String nullIfEmpty(String value) {
        return value == null || value.isEmpty() ? null : value;
    }

    private static String env(String key, String fallback) {
        String value = System.getenv(key);
        return value == null ? fallback : value;
    }
}
