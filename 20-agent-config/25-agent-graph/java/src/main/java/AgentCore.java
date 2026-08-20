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
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Domain logic for 25-agent-graph (no HTTP here).
 *
 * =============================================================================
 * HOW TO READ THIS FILE
 * =============================================================================
 *
 * Equity briefing UI with LaunchDarkly **Agent Graphs**:
 *
 *   1. Data          Charlie / Amelia (anonymous) / Toby + humor easter egg
 *   2. LaunchDarkly  agent graph JSON (root + edges) + per-node agent JSON
 *   3. Providers     Local Ollama per node (LD does not call the model)
 *   4. Generation    assess -&gt; specialist -&gt; (optional scorers) -&gt; finalize
 *
 * LaunchDarkly insertion point (read this first):
 *   generateStream() -&gt; evaluateGraph() then evaluateAgent() per node
 *   Docs: https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
 *   Keywords: AgentControl · Agent graphs · Agents · handoffs · edges
 *
 * There is no official Java AI SDK, so no {@code agent_graph()} /
 * {@code create_agent_graph()} helpers. The Python/JS AI SDKs' {@code agent_graph}
 * evaluates the graph key as JSON shaped {@code { root, edges }} (edges keyed by
 * source config -&gt; array of {@code {key, handoff}} targets) and each agent node
 * key as JSON shaped {@code { instructions, model, provider, _ldMeta } } — see
 * ldai/client.py `agent_graph()` in the Python AI SDK for the reference shape.
 * Here we read that same JSON with {@link LDClient#jsonValueVariationDetail},
 * walk the graph by hand, and validate handoffs against the evaluated edges —
 * emitting the same {@code $ld:ai:graph:*} Monitoring events the AI SDK's
 * AIGraphTracker would (best-effort; Java has no AIGraphTracker class).
 * https://launchdarkly.com/docs/sdk/server-side/java
 */
public final class AgentCore {

    // -------------------------------------------------------------------
    // Personas
    // -------------------------------------------------------------------

    public static final List<Persona> PERSONAS = List.of(
            new Persona("conservative-charlie", "Conservative Charlie", "conservative", false),
            // No name targeting — anonymous context falls through to the default report variation.
            new Persona("anonymous-amelia", "Anonymous Amelia", "anonymous", true),
            new Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker", false)
    );

    private static final Map<String, Integer> HUMOR_LEVEL = Map.of(
            "conservative-charlie", 25,
            "anonymous-amelia", 50,
            "thoughtless-toby", 90
    );

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

    private static int humorLevelFor(Persona persona) {
        return HUMOR_LEVEL.getOrDefault(persona.id(), 50);
    }

    // -------------------------------------------------------------------
    // Keys / constants
    // -------------------------------------------------------------------

    private static final String CANNED_STORIES =
            "No ticker stories loaded yet. Ask the user to click Get Stories.";

    // LaunchDarkly: Agent graph key=equity-briefing-graph; nodes=equity-briefing-graph-<role>
    // https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
    private static final String DEFAULT_GRAPH_KEY = "equity-briefing-graph";
    private static final String DEFAULT_NODE_ASSESS = "equity-briefing-graph-assess";
    private static final String DEFAULT_NODE_REPORT = "equity-briefing-graph-report";
    private static final String DEFAULT_NODE_QUESTIONS = "equity-briefing-graph-questions";
    private static final String DEFAULT_NODE_GOOD = "equity-briefing-graph-good";
    private static final String DEFAULT_NODE_JOKE = "equity-briefing-graph-joke";
    private static final String DEFAULT_NODE_FINALIZE = "equity-briefing-graph-finalize";
    private static final String DEFAULT_OLLAMA_MODEL = "llama3.2:3b";

    private static final double DEFAULT_JOKE_TEMPERATURE = 0.95;
    private static final double DEFAULT_CORNY_HIGH = 0.80;
    private static final double DEFAULT_CORNY_LOW = 0.20;

    private static final String TOOL_QUESTION_GAP = "score-question-gap";
    private static final String TOOL_JOKE_CORNY = "score-joke-corny";

    private static final Set<String> VALID_SPECIALISTS = Set.of("report", "questions", "good", "joke");
    private static final Set<String> ACTIONS_NEEDING_STORIES = Set.of("report", "questions", "good");

    // Soft angle hints — nudge variety without banning prior jokes.
    private static final List<String> JOKE_ANGLE_HINTS = List.of(
            "bulls vs bears",
            "earnings season nerves",
            "index funds vs stock picking",
            "coffee and candlesticks",
            "diversification as a lifestyle",
            "the eternally loading chart",
            "hot takes cooling overnight",
            "FOMO meeting patience"
    );

    // LaunchDarkly Monitoring events an AIGraphTracker would emit (ldai/tracker.py AIGraphTracker).
    private static final String EVT_GRAPH_INVOCATION_SUCCESS = "$ld:ai:graph:invocation_success";
    private static final String EVT_GRAPH_INVOCATION_FAILURE = "$ld:ai:graph:invocation_failure";
    private static final String EVT_GRAPH_DURATION_TOTAL = "$ld:ai:graph:duration:total";
    private static final String EVT_GRAPH_PATH = "$ld:ai:graph:path";
    private static final String EVT_GRAPH_REDIRECT = "$ld:ai:graph:redirect";
    private static final String EVT_GRAPH_HANDOFF_SUCCESS = "$ld:ai:graph:handoff_success";
    private static final String EVT_GRAPH_HANDOFF_FAILURE = "$ld:ai:graph:handoff_failure";
    private static final String EVT_NODE_GENERATION_SUCCESS = "$ld:ai:generation:success";
    private static final String EVT_NODE_TOOL_CALL = "$ld:ai:tool_call";

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    private static volatile LDClient ldClient;

    private AgentCore() {
    }

    public static String graphKey() {
        String key = env("LD_GRAPH_KEY", DEFAULT_GRAPH_KEY).trim();
        return key.isEmpty() ? DEFAULT_GRAPH_KEY : key;
    }

    public static String nodeKey(String role) {
        String envName = switch (role) {
            case "assess" -> "LD_NODE_ASSESS";
            case "report" -> "LD_NODE_REPORT";
            case "questions" -> "LD_NODE_QUESTIONS";
            case "good" -> "LD_NODE_GOOD";
            case "joke" -> "LD_NODE_JOKE";
            case "finalize" -> "LD_NODE_FINALIZE";
            default -> "";
        };
        String defaultValue = switch (role) {
            case "assess" -> DEFAULT_NODE_ASSESS;
            case "report" -> DEFAULT_NODE_REPORT;
            case "questions" -> DEFAULT_NODE_QUESTIONS;
            case "good" -> DEFAULT_NODE_GOOD;
            case "joke" -> DEFAULT_NODE_JOKE;
            case "finalize" -> DEFAULT_NODE_FINALIZE;
            default -> throw new IllegalArgumentException("Unknown role: " + role);
        };
        if (!envName.isEmpty()) {
            String raw = env(envName, "").trim();
            if (!raw.isEmpty()) {
                return raw;
            }
        }
        return defaultValue;
    }

    /** Map a graph config key back to a specialist/role name. */
    private static String roleFromNodeKey(String configKey) {
        for (String role : List.of("assess", "report", "questions", "good", "joke", "finalize")) {
            if (configKey.equals(nodeKey(role))) {
                return role;
            }
        }
        String marker = "equity-briefing-graph-";
        if (configKey.startsWith(marker)) {
            String suffix = configKey.substring(marker.length());
            if (VALID_SPECIALISTS.contains(suffix) || suffix.equals("assess") || suffix.equals("finalize")) {
                return suffix;
            }
        }
        return null;
    }

    private static String defaultInstructionsFile(String role) {
        return switch (role) {
            case "assess" -> "assess-instructions.txt";
            case "report" -> "report-baseline-instructions.txt";
            case "questions" -> "questions-instructions.txt";
            case "good" -> "good-instructions.txt";
            case "joke" -> "joke-instructions.txt";
            case "finalize" -> "finalize-instructions.txt";
            default -> throw new IllegalArgumentException("Unknown role: " + role);
        };
    }

    public static String defaultOllamaModel() {
        String model = env("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).trim();
        return model.isEmpty() ? DEFAULT_OLLAMA_MODEL : model;
    }

    private static double jokeTemperature() {
        String raw = env("JOKE_TEMPERATURE", "").trim();
        if (raw.isEmpty()) {
            return DEFAULT_JOKE_TEMPERATURE;
        }
        try {
            return Math.max(0.0, Math.min(1.5, Double.parseDouble(raw)));
        } catch (NumberFormatException exc) {
            return DEFAULT_JOKE_TEMPERATURE;
        }
    }

    private static double cornyHighThreshold() {
        return parseDoubleOr(env("JOKE_CORNY_HIGH", "").trim(), DEFAULT_CORNY_HIGH);
    }

    private static double cornyLowThreshold() {
        return parseDoubleOr(env("JOKE_CORNY_LOW", "").trim(), DEFAULT_CORNY_LOW);
    }

    private static double parseDoubleOr(String raw, double fallback) {
        if (raw.isEmpty()) {
            return fallback;
        }
        try {
            return Double.parseDouble(raw);
        } catch (NumberFormatException exc) {
            return fallback;
        }
    }

    // -------------------------------------------------------------------
    // LaunchDarkly init
    // -------------------------------------------------------------------

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
                            + "environment that targets equity-briefing-graph.");
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
     * Build the LD evaluation context for this persona + action.
     *
     * Named personas: user key + name (name targeting matches Charlie/Toby on the
     * report node). Anonymous Amelia: anonymous=true — falls through to the
     * default report variation. https://launchdarkly.com/docs/sdk/features/anonymous
     */
    public static LDContext buildContext(Persona persona, String action) {
        ContextBuilder builder = LDContext.builder(persona.id()).name(persona.name());
        if (persona.anonymous()) {
            builder.anonymous(true);
        }
        builder.set("action", action);
        builder.set("profile", persona.profile());
        return builder.build();
    }

    // -------------------------------------------------------------------
    // Message files (rest/messages)
    // -------------------------------------------------------------------

    private static Path messagesDir() {
        return YahooNews.exampleRoot().resolve("rest").resolve("messages");
    }

    private static String readMessageFile(String name) {
        Path path = messagesDir().resolve(name);
        try {
            return Files.readString(path, StandardCharsets.UTF_8).trim();
        } catch (IOException exc) {
            throw new IllegalStateException(
                    "Could not read message file " + path + ": " + exc.getMessage(), exc);
        }
    }

    private static String loadQuestionsList() {
        Path path = messagesDir().resolve("questions.txt");
        try {
            List<String> lines = Files.readAllLines(path, StandardCharsets.UTF_8);
            List<String> out = new ArrayList<>();
            for (String line : lines) {
                String s = line.strip();
                if (s.isEmpty() || s.startsWith("#")) {
                    continue;
                }
                out.add("- " + s);
            }
            return String.join("\n", out);
        } catch (IOException exc) {
            throw new IllegalStateException(
                    "Could not read questions list " + path + ": " + exc.getMessage(), exc);
        }
    }

    private static String formatStories(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) {
            return CANNED_STORIES;
        }
        return YahooNews.formatStoriesForPrompt(tickerResults);
    }

    // -------------------------------------------------------------------
    // Agent-mode node evaluation (JSON variation — no Java AI SDK)
    // -------------------------------------------------------------------

    /** Evaluated shape of one agent-mode node (mode=agent: instructions + model). */
    private record AgentEval(
            boolean enabled,
            String instructions,
            String modelName,
            String providerName,
            String variationKey,
            int version
    ) {
    }

    private static LDValue agentDefault(String instructionsFile) {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject()
                        .put("name", defaultOllamaModel())
                        .put("parameters", LDValue.buildObject().put("temperature", 0).build())
                        .build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("instructions", readMessageFile(instructionsFile))
                .build();
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

    private static String modelName(LDValue value) {
        LDValue model = value.get("model");
        if (model.isNull()) {
            return "";
        }
        String name = ldString(model.get("name"));
        if (!name.isEmpty()) {
            return name;
        }
        // AI Config REST create shape uses model.modelName; served JSON may echo either.
        return ldString(model.get("modelName"));
    }

    private static String providerName(LDValue value) {
        LDValue provider = value.get("provider");
        if (provider.isNull()) {
            return "";
        }
        return ldString(provider.get("name"));
    }

    /**
     * Interpolate the small mustache-style placeholders the AI SDK would render
     * server-side for instructions ({{ var }} / {{var}} plus {{ ldctx.name }}).
     * The shipped instruction files use none of these, but LD console edits may.
     */
    private static String interpolate(String content, Map<String, String> variables, Persona persona) {
        if (content == null) {
            return "";
        }
        String out = content;
        if (variables != null) {
            for (Map.Entry<String, String> e : variables.entrySet()) {
                out = out.replace("{{ " + e.getKey() + " }}", e.getValue());
                out = out.replace("{{" + e.getKey() + "}}", e.getValue());
            }
        }
        out = out.replace("{{ ldctx.name }}", persona.name()).replace("{{ldctx.name}}", persona.name());
        return out;
    }

    /**
     * Evaluate one agent-mode node.
     *
     * LaunchDarkly: {@code jsonValueVariationDetail} on the node's AI config key
     * (same underlying evaluation the AI SDK's {@code agent_config} performs).
     * https://launchdarkly.com/docs/sdk/server-side/java
     * https://launchdarkly.com/docs/home/agentcontrol/agents
     */
    private static AgentEval evaluateAgent(
            String key, LDContext context, String instructionsFile, Map<String, String> variables, Persona persona) {
        EvaluationDetail<LDValue> detail =
                requireClient().jsonValueVariationDetail(key, context, agentDefault(instructionsFile));
        LDValue value = detail.getValue();
        if (value == null || value.isNull()) {
            value = agentDefault(instructionsFile);
        }
        LDValue meta = value.get("_ldMeta");
        String variationKey = meta.isNull() ? "" : ldString(meta.get("variationKey"));
        int version = meta.isNull() || meta.get("version").isNull() ? 1 : meta.get("version").intValue();
        LDValue instructionsVal = value.get("instructions");
        String rawInstructions = instructionsVal.isString() ? instructionsVal.stringValue() : "";
        String instructions = interpolate(rawInstructions, variables, persona);
        return new AgentEval(
                isEnabled(value), instructions, modelName(value), providerName(value), variationKey, version);
    }

    /** Always "ollama" here — matches the Python example's resolve_runtime shape. */
    private static String resolveModel(String modelName) {
        if (modelName != null && !modelName.isBlank()) {
            return modelName;
        }
        return defaultOllamaModel();
    }

    // -------------------------------------------------------------------
    // Agent graph evaluation (JSON variation — no Java AI SDK)
    // -------------------------------------------------------------------

    private record Edge(String sourceConfig, String targetConfig) {
    }

    /**
     * Manually-walked mirror of the AI SDK's {@code AgentGraphDefinition}: root
     * config key, edges (source -&gt; targets), and whether every referenced node
     * is enabled (the AI SDK disables the whole graph otherwise).
     */
    private static final class GraphInfo {
        final boolean enabled;
        final String root;
        final Map<String, List<String>> outgoing;
        final String variationKey;
        final int version;

        GraphInfo(boolean enabled, String root, Map<String, List<String>> outgoing,
                  String variationKey, int version) {
            this.enabled = enabled;
            this.root = root;
            this.outgoing = outgoing;
            this.variationKey = variationKey;
            this.version = version;
        }

        List<String> outgoingTargets(String sourceKey) {
            if (!enabled) {
                return List.of();
            }
            return outgoing.getOrDefault(sourceKey, List.of());
        }
    }

    /**
     * Evaluate the agent graph flag as JSON, then evaluate every node it
     * references so we can mirror the AI SDK's "all nodes must be enabled"
     * rule for the whole graph.
     *
     * LaunchDarkly: {@code jsonValueVariationDetail} on the graph key. The
     * served JSON is {@code { root: "<configKey>", edges: { "<source>": [
     * {"key": "<target>", "handoff": {...}}, ... ] } }} — see
     * ldai/client.py `agent_graph()` in the Python AI SDK for the reference
     * parsing this mirrors.
     * https://launchdarkly.com/docs/home/agentcontrol/agent-graphs
     */
    private static GraphInfo evaluateGraph(LDContext context) {
        EvaluationDetail<LDValue> detail =
                requireClient().jsonValueVariationDetail(graphKey(), context, LDValue.buildObject().build());
        LDValue variation = detail.getValue();
        if (variation == null || variation.isNull()) {
            variation = LDValue.ofNull();
        }
        LDValue meta = variation.isNull() ? LDValue.ofNull() : variation.get("_ldMeta");
        String variationKey = meta.isNull() ? "" : ldString(meta.get("variationKey"));
        int version = meta.isNull() || meta.get("version").isNull() ? 1 : meta.get("version").intValue();

        LDValue rootVal = variation.isNull() ? LDValue.ofNull() : variation.get("root");
        String root = rootVal.isString() ? rootVal.stringValue() : "";
        if (root.isEmpty()) {
            return new GraphInfo(false, "", Map.of(), variationKey, version);
        }

        LDValue edgesVal = variation.get("edges");
        Map<String, List<String>> outgoing = new LinkedHashMap<>();
        Set<String> allAgentKeys = new LinkedHashSet<>();
        allAgentKeys.add(root);
        if (!edgesVal.isNull()) {
            for (String sourceKey : edgesVal.keys()) {
                LDValue targets = edgesVal.get(sourceKey);
                List<String> targetKeys = new ArrayList<>();
                if (!targets.isNull()) {
                    for (LDValue edgeObj : targets.values()) {
                        LDValue keyVal = edgeObj.get("key");
                        String targetKey = keyVal.isString() ? keyVal.stringValue() : "";
                        if (!targetKey.isEmpty()) {
                            targetKeys.add(targetKey);
                            allAgentKeys.add(targetKey);
                        }
                    }
                }
                outgoing.put(sourceKey, targetKeys);
            }
        }

        // AI SDK rule: the whole graph is disabled unless every referenced node is enabled.
        for (String agentKey : allAgentKeys) {
            String role = roleFromNodeKey(agentKey);
            String instructionsFile = role != null ? defaultInstructionsFile(role) : "finalize-instructions.txt";
            AgentEval eval = evaluateAgent(agentKey, context, instructionsFile, Map.of(), PERSONAS.get(0));
            if (!eval.enabled()) {
                return new GraphInfo(false, "", Map.of(), variationKey, version);
            }
        }

        return new GraphInfo(true, root, outgoing, variationKey, version);
    }

    // -------------------------------------------------------------------
    // Graph / node Monitoring trackers (best-effort — no AIGraphTracker in Java)
    // -------------------------------------------------------------------

    /**
     * Best-effort mirror of the AI SDK's {@code AIGraphTracker}. Java has no
     * AI SDK graph tracker class, so we fire the same {@code $ld:ai:graph:*}
     * custom metric events directly via {@link LDClient#trackMetric}.
     */
    private static final class GraphTracker {
        private final LDClient client;
        private final LDContext context;
        private final String graphKeyValue;
        private final String variationKey;
        private final int version;

        GraphTracker(LDClient client, LDContext context, String graphKeyValue, String variationKey, int version) {
            this.client = client;
            this.context = context;
            this.graphKeyValue = graphKeyValue;
            this.variationKey = variationKey;
            this.version = version;
        }

        private LDValue baseData() {
            ObjectBuilder b = LDValue.buildObject()
                    .put("graphKey", graphKeyValue)
                    .put("version", version);
            if (variationKey != null && !variationKey.isEmpty()) {
                b.put("variationKey", variationKey);
            }
            return b.build();
        }

        private LDValue dataWith(String... kv) {
            ObjectBuilder b = LDValue.buildObject()
                    .put("graphKey", graphKeyValue)
                    .put("version", version);
            if (variationKey != null && !variationKey.isEmpty()) {
                b.put("variationKey", variationKey);
            }
            for (int i = 0; i + 1 < kv.length; i += 2) {
                b.put(kv[i], kv[i + 1]);
            }
            return b.build();
        }

        void trackHandoffSuccess(String sourceKey, String targetKey) {
            safeTrack(EVT_GRAPH_HANDOFF_SUCCESS, dataWith("sourceKey", sourceKey, "targetKey", targetKey), 1.0);
        }

        void trackHandoffFailure(String sourceKey, String targetKey) {
            safeTrack(EVT_GRAPH_HANDOFF_FAILURE, dataWith("sourceKey", sourceKey, "targetKey", targetKey), 1.0);
        }

        void trackRedirect(String sourceKey, String redirectedTarget) {
            safeTrack(EVT_GRAPH_REDIRECT,
                    dataWith("sourceKey", sourceKey, "redirectedTarget", redirectedTarget), 1.0);
        }

        void trackPath(List<String> path) {
            ArrayBuilder arr = LDValue.buildArray();
            for (String p : path) {
                arr.add(p);
            }
            ObjectBuilder b = LDValue.buildObject()
                    .put("graphKey", graphKeyValue)
                    .put("version", version)
                    .put("path", arr.build());
            if (variationKey != null && !variationKey.isEmpty()) {
                b.put("variationKey", variationKey);
            }
            safeTrack(EVT_GRAPH_PATH, b.build(), 1.0);
        }

        void trackDuration(long durationMs) {
            safeTrack(EVT_GRAPH_DURATION_TOTAL, baseData(), (double) durationMs);
        }

        void trackInvocationSuccess() {
            safeTrack(EVT_GRAPH_INVOCATION_SUCCESS, baseData(), 1.0);
        }

        void trackInvocationFailure() {
            safeTrack(EVT_GRAPH_INVOCATION_FAILURE, baseData(), 1.0);
        }

        private void safeTrack(String event, LDValue data, double metricValue) {
            try {
                client.trackMetric(event, context, data, metricValue);
            } catch (Exception ignored) {
                // Best-effort Monitoring hook — demos should not fail on track.
            }
        }
    }

    /** Best-effort per-node tracker mirroring LDAIConfigTracker's tool-call/success events. */
    private static final class NodeTracker {
        private final LDClient client;
        private final LDContext context;
        private final String configKey;
        private final String variationKey;
        private final int version;
        private final String modelNameValue;
        private final String graphKeyValue;

        NodeTracker(LDClient client, LDContext context, String configKey, String variationKey,
                    int version, String modelNameValue, String graphKeyValue) {
            this.client = client;
            this.context = context;
            this.configKey = configKey;
            this.variationKey = variationKey;
            this.version = version;
            this.modelNameValue = modelNameValue;
            this.graphKeyValue = graphKeyValue;
        }

        private ObjectBuilder baseBuilder() {
            ObjectBuilder b = LDValue.buildObject()
                    .put("configKey", configKey)
                    .put("version", version)
                    .put("modelName", modelNameValue)
                    .put("providerName", "ollama")
                    .put("graphKey", graphKeyValue);
            if (variationKey != null && !variationKey.isEmpty()) {
                b.put("variationKey", variationKey);
            }
            return b;
        }

        void trackSuccess() {
            safeTrack(EVT_NODE_GENERATION_SUCCESS, baseBuilder().build(), 1.0);
        }

        void trackToolCall(String toolKey) {
            LDValue data = baseBuilder().put("toolKey", toolKey).build();
            safeTrack(EVT_NODE_TOOL_CALL, data, 1.0);
        }

        private void safeTrack(String event, LDValue data, double metricValue) {
            try {
                client.trackMetric(event, context, data, metricValue);
            } catch (Exception ignored) {
                // Best-effort Monitoring hook.
            }
        }
    }

    // -------------------------------------------------------------------
    // Edge validation (manual walk — mirrors python resolve_specialist_against_edges)
    // -------------------------------------------------------------------

    private record RouteResult(String specialist, String note, boolean edgeValidated) {
    }

    private static RouteResult resolveSpecialistAgainstEdges(
            GraphInfo graph, String preferred, GraphTracker tracker) {
        String pref = VALID_SPECIALISTS.contains(preferred) ? preferred : "report";
        String assessKey = nodeKey("assess");
        String preferredKey = nodeKey(pref);

        if (!graph.enabled) {
            return new RouteResult(pref, "graph disabled — skip edge validation", false);
        }

        List<String> children = graph.outgoingTargets(assessKey);
        if (children.isEmpty()) {
            return new RouteResult(pref, "assess has no outgoing edges — using preferred", false);
        }

        if (children.contains(preferredKey)) {
            return new RouteResult(pref, "edge ok: assess -> " + pref, true);
        }

        // Invalid handoff — prefer report if that edge exists, else first child.
        String reportKey = nodeKey("report");
        tracker.trackHandoffFailure(assessKey, preferredKey);

        if (children.contains(reportKey)) {
            tracker.trackRedirect(assessKey, reportKey);
            return new RouteResult(
                    "report", "no edge assess -> " + pref + "; redirected to report", true);
        }

        String fallbackKey = children.get(0);
        String fallbackRole = roleFromNodeKey(fallbackKey);
        if (fallbackRole == null || !VALID_SPECIALISTS.contains(fallbackRole)) {
            fallbackRole = "report";
        }
        tracker.trackRedirect(assessKey, fallbackKey);
        return new RouteResult(
                fallbackRole, "no edge assess -> " + pref + "; redirected to " + fallbackRole, true);
    }

    private record FinalizeCheck(boolean ok, String note) {
    }

    private static FinalizeCheck finalizeEdgeOk(GraphInfo graph, String specialistKey) {
        String finalizeKey = nodeKey("finalize");
        if (!graph.enabled) {
            return new FinalizeCheck(true, "graph disabled — skip finalize edge check");
        }
        List<String> children = graph.outgoingTargets(specialistKey);
        if (children.contains(finalizeKey)) {
            return new FinalizeCheck(true, "edge ok: " + specialistKey + " -> finalize");
        }
        return new FinalizeCheck(false, "no edge " + specialistKey + " -> finalize");
    }

    // -------------------------------------------------------------------
    // Assess / scorer parsing helpers
    // -------------------------------------------------------------------

    private static final Pattern JSON_OBJECT_PATTERN = Pattern.compile("\\{[\\s\\S]*}");

    private static String clip(String text) {
        return clip(text, 55);
    }

    private static String clip(String text, int maxLen) {
        String s = (text == null ? "" : text).replaceAll("\\s+", " ").trim();
        if (s.length() <= maxLen) {
            return s;
        }
        return s.substring(0, Math.max(0, maxLen - 1)) + "…";
    }

    private static JsonObject parseJsonObject(String raw) {
        if (raw == null) {
            return null;
        }
        Matcher m = JSON_OBJECT_PATTERN.matcher(raw.strip());
        if (!m.find()) {
            return null;
        }
        try {
            return JsonParser.parseString(m.group()).getAsJsonObject();
        } catch (Exception exc) {
            return null;
        }
    }

    private static double clamp01(JsonObject obj, String field, double fallback) {
        if (obj == null || !obj.has(field) || obj.get(field).isJsonNull()) {
            return fallback;
        }
        try {
            double n = obj.get(field).getAsDouble();
            return Math.max(0.0, Math.min(1.0, n));
        } catch (Exception exc) {
            return fallback;
        }
    }

    private record AssessResult(String specialist, String reason) {
    }

    private static AssessResult parseAssessJson(String raw, String actionHint) {
        String specialist = VALID_SPECIALISTS.contains(actionHint) ? actionHint : "report";
        String reason = "fallback";
        JsonObject obj = parseJsonObject(raw);
        if (obj != null) {
            String cand = obj.has("specialist") && !obj.get("specialist").isJsonNull()
                    ? obj.get("specialist").getAsString().strip().toLowerCase(Locale.ROOT)
                    : "";
            if (VALID_SPECIALISTS.contains(cand)) {
                specialist = cand;
            }
            String r = obj.has("reason") && !obj.get("reason").isJsonNull()
                    ? obj.get("reason").getAsString().strip()
                    : "";
            reason = r.isEmpty() ? reason : r;
            return new AssessResult(specialist, reason);
        }
        if (VALID_SPECIALISTS.contains(actionHint)) {
            return new AssessResult(actionHint, "assess parse failed; used UI action hint");
        }
        return new AssessResult("report", "assess parse failed; fall through to report");
    }

    private static List<String> extractQuestionsFromDraft(String draft) {
        List<String> out = new ArrayList<>();
        if (draft == null) {
            return out;
        }
        for (String line : draft.split("\\R")) {
            String s = line.strip();
            if (s.isEmpty()) {
                continue;
            }
            s = s.replaceFirst("^[-*•]+\\s*", "");
            s = s.replaceFirst("^\\d+[.)]\\s*", "");
            if (!s.contains("?") || s.length() < 12) {
                continue;
            }
            out.add(s);
            if (out.size() >= 5) {
                break;
            }
        }
        return out;
    }

    /**
     * App-side scorer: gap + ground in [0,1]. Does not change specialist output.
     *
     * LaunchDarkly: Library tool key score-question-gap (attached for Monitoring).
     * https://launchdarkly.com/docs/home/agentcontrol/tools
     */
    private static Map<String, Double> scoreQuestionGap(String question, String headlines, String model)
            throws IOException, InterruptedException {
        String user = "Score this follow-up question against the headlines.\n"
                + "Return JSON only: {\"gap\":0.0,\"ground\":0.0}\n"
                + "- gap: how poorly the headlines answer it (1.0 = large information gap).\n"
                + "- ground: how well the question fits this headline domain (1.0 = on-topic).\n"
                + "Use decimals in [0,1].\n\n"
                + "QUESTION:\n" + question + "\n\n"
                + "HEADLINES:\n" + headlines + "\n";
        List<Map<String, String>> messages = List.of(
                Map.of("role", "system", "content", "You are a strict scoring tool. Output JSON only."),
                Map.of("role", "user", "content", user)
        );
        String raw = ollamaComplete(model, messages, 0.0);
        JsonObject obj = parseJsonObject(raw);
        Map<String, Double> out = new LinkedHashMap<>();
        out.put("gap", clamp01(obj, "gap", 0.5));
        out.put("ground", clamp01(obj, "ground", 0.5));
        return out;
    }

    /** App-side easter-egg scorer: corniness in [0,1]. */
    private static double scoreJokeCorny(String joke, String model) throws IOException, InterruptedException {
        String user = "Score how corny this joke is.\n"
                + "Return JSON only: {\"corny\":0.0}\n"
                + "0.0 = dry/subtle; 1.0 = very corny dad-joke energy. Decimal in [0,1].\n\n"
                + "JOKE:\n" + joke + "\n";
        List<Map<String, String>> messages = List.of(
                Map.of("role", "system", "content", "You are a whimsical scoring tool. Output JSON only."),
                Map.of("role", "user", "content", user)
        );
        String raw = ollamaComplete(model, messages, 0.0);
        JsonObject obj = parseJsonObject(raw);
        return clamp01(obj, "corny", 0.5);
    }

    private static String formatToolNameWithScore(String base, double score) {
        return String.format(Locale.US, "%s:%.2f", base, score);
    }

    // -------------------------------------------------------------------
    // Generation
    // -------------------------------------------------------------------

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

    private static int estimateTokens(String text) {
        if (text == null || text.isEmpty()) {
            return 1;
        }
        return Math.max(1, text.length() / 4);
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

    /**
     * Run assess -&gt; specialist -&gt; finalize, emitting SSE-style events.
     *
     * Event types: run, status, info, assess, route, specialist, tool, model,
     * token, finalize, metrics, error, done — same shapes as the Python example.
     */
    public static void generateStream(
            Persona persona,
            String action,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String normalizedAction = (action == null ? "report" : action).strip().toLowerCase(Locale.ROOT);
        if (!VALID_SPECIALISTS.contains(normalizedAction)) {
            normalizedAction = "report";
        }
        final String uiAction = normalizedAction;

        String storiesText = formatStories(tickerResults);
        boolean hasRealStories = tickerResults != null && !tickerResults.isEmpty()
                && !CANNED_STORIES.equals(storiesText);

        if (ACTIONS_NEEDING_STORIES.contains(uiAction) && !hasRealStories) {
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Load stories first (Get Stories), then try this action again."));
            emit.accept(Map.of("type", "done"));
            return;
        }

        long started = System.nanoTime();
        Map<String, Object> metrics = emptyMetrics();
        LDContext context = buildContext(persona, uiAction);

        // --- Graph evaluate (topology + tracker) -------------------------------
        // LaunchDarkly: agent graph JSON — see class prelude for the shape.
        GraphInfo graph;
        try {
            graph = evaluateGraph(context);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", "LaunchDarkly agent graph failed: " + exc.getMessage()));
            emit.accept(Map.of("type", "done"));
            return;
        }

        GraphTracker graphTracker =
                new GraphTracker(requireClient(), context, graphKey(), graph.variationKey, graph.version);

        Map<String, Object> runEvent = new LinkedHashMap<>();
        runEvent.put("type", "run");
        runEvent.put("action", uiAction);
        runEvent.put("personaId", persona.id());
        runEvent.put("personaName", persona.name());
        runEvent.put("graphKey", graphKey());
        runEvent.put("graphEnabled", graph.enabled);
        emit.accept(runEvent);

        emit.accept(Map.of(
                "type", "status",
                "message", "Graph " + graphKey() + " "
                        + (graph.enabled ? "enabled" : "disabled/missing — using node configs + local walk")));

        List<String> path = new ArrayList<>();
        path.add(nodeKey("assess"));

        if (uiAction.equals("joke")) {
            int level = humorLevelFor(persona);
            emit.accept(Map.of(
                    "type", "info", "message", "Setting humor level to " + level + "%", "kind", "humor"));
        }

        // --- Step 1: assess ------------------------------------------------------
        emit.accept(Map.of("type", "status", "message", "assess — choosing specialist…"));
        AgentEval assessCfg;
        try {
            Map<String, String> assessVars = new LinkedHashMap<>();
            assessVars.put("action", uiAction);
            assessVars.put("stories", hasRealStories ? storiesText : "(none)");
            assessCfg = evaluateAgent(nodeKey("assess"), context, defaultInstructionsFile("assess"), assessVars, persona);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", "assess agent_config failed: " + exc.getMessage()));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        String assessModel = resolveModel(assessCfg.modelName());
        String assessUser = "UI action hint: " + uiAction + "\n"
                + "Headlines present: " + (hasRealStories ? "yes" : "no") + "\n\n"
                + "HEADLINES:\n" + (hasRealStories ? storiesText : "(none)") + "\n\n"
                + "Return JSON only.";
        String assessRaw;
        try {
            assessRaw = ollamaComplete(assessModel, messagesForNode(assessCfg.instructions(), assessUser), 0.0);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        AssessResult assessResult = parseAssessJson(assessRaw, uiAction);
        String specialist = assessResult.specialist();
        String reason = assessResult.reason();
        // Prefer UI action when valid (teaching: button intent wins if assess drifts).
        if (VALID_SPECIALISTS.contains(uiAction) && !specialist.equals(uiAction)) {
            reason = reason + " (UI hint=" + uiAction + "; using hint)";
            specialist = uiAction;
        }

        // LaunchDarkly: validate assess -> specialist against graph edges.
        RouteResult route = resolveSpecialistAgainstEdges(graph, specialist, graphTracker);
        specialist = route.specialist();
        boolean edgeOk = route.edgeValidated();
        if (route.note() != null && !route.note().isEmpty()) {
            if (!reason.contains(route.note())) {
                reason = reason + "; " + route.note();
            }
            emit.accept(Map.of(
                    "type", "info", "message", route.note(), "kind", "edge", "validated", edgeOk));
        }

        String specialistKey = nodeKey(specialist);
        path.add(specialistKey);
        graphTracker.trackHandoffSuccess(nodeKey("assess"), specialistKey);

        Map<String, Object> assessEvent = new LinkedHashMap<>();
        assessEvent.put("type", "assess");
        assessEvent.put("specialist", specialist);
        assessEvent.put("reason", reason);
        assessEvent.put("clip", clip(specialist + ": " + reason));
        assessEvent.put("model", assessModel);
        assessEvent.put("configKey", nodeKey("assess"));
        assessEvent.put("edgeValidated", edgeOk);
        emit.accept(assessEvent);

        Map<String, Object> routeEvent = new LinkedHashMap<>();
        routeEvent.put("type", "route");
        routeEvent.put("specialist", specialist);
        routeEvent.put("reason", reason);
        routeEvent.put("message", "Selected specialist: " + specialist);
        routeEvent.put("edgeValidated", edgeOk);
        emit.accept(routeEvent);

        // --- Step 2: specialist --------------------------------------------------
        emit.accept(Map.of("type", "status", "message", specialist + " — running specialist…"));
        Map<String, String> variables = new LinkedHashMap<>();
        variables.put("action", uiAction);
        variables.put("stories", hasRealStories ? storiesText : "(none)");
        variables.put("specialist", specialist);
        if (specialist.equals("questions")) {
            variables.put("questions", loadQuestionsList());
        }

        AgentEval specCfg;
        try {
            specCfg = evaluateAgent(specialistKey, context, defaultInstructionsFile(specialist), variables, persona);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", specialist + " agent_config failed: " + exc.getMessage()));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        String specModel = resolveModel(specCfg.modelName());
        String variationKey = specCfg.variationKey() == null ? "" : specCfg.variationKey();

        String specUser;
        double specTemperature;
        if (specialist.equals("questions")) {
            specUser = "CANDIDATE QUESTIONS:\n" + variables.get("questions") + "\n\n"
                    + "HEADLINES:\n" + storiesText + "\n\n"
                    + "Return the top 2–3 gap-priority questions with a short why each.";
            specTemperature = 0.0;
        } else if (specialist.equals("good")) {
            specUser = "HEADLINES:\n" + storiesText + "\n\n"
                    + "Produce ## Good and ## Bad sections now (both required).";
            specTemperature = 0.0;
        } else if (specialist.equals("joke")) {
            List<String> tickers = new ArrayList<>();
            if (tickerResults != null) {
                for (Map<String, Object> row : tickerResults) {
                    Object t = row.get("ticker");
                    if (t != null && !String.valueOf(t).isBlank()) {
                        tickers.add(String.valueOf(t).strip());
                    }
                }
            }
            List<String> extras = new ArrayList<>();
            if (!tickers.isEmpty()) {
                extras.add("Optional tickers (use lightly if you want): " + String.join(", ", tickers));
            }
            if (hasRealStories) {
                extras.add("Optional headlines (use lightly if you want):\n" + clip(storiesText, 400));
            }
            String angle = JOKE_ANGLE_HINTS.get((int) (Math.random() * JOKE_ANGLE_HINTS.size()));
            extras.add("Variety nudge (optional inspiration, not a script): lean toward \u201c" + angle
                    + "\u201d or another fresh angle — prefer a different setup than the most common one.");
            String bonus = extras.isEmpty() ? "" : "\n\n" + String.join("\n\n", extras);
            specUser = "Tell a short market/investing joke now. "
                    + "Aim for variety across runs. Do not require tickers or headlines." + bonus;
            specTemperature = jokeTemperature();
            emit.accept(Map.of(
                    "type", "info",
                    "message", String.format(
                            Locale.US, "Joke sampling temperature=%.2f; angle hint \u201c%s\u201d", specTemperature, angle),
                    "kind", "joke-variety"));
        } else {
            specUser = "HEADLINES:\n" + storiesText + "\n\n" + "Produce the " + specialist + " output now.";
            specTemperature = 0.0;
        }

        String specialistDraft;
        try {
            specialistDraft = ollamaComplete(
                    specModel, messagesForNode(specCfg.instructions(), specUser), specTemperature);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        Map<String, Object> specialistEvent = new LinkedHashMap<>();
        specialistEvent.put("type", "specialist");
        specialistEvent.put("specialist", specialist);
        specialistEvent.put("clip", clip(specialistDraft));
        specialistEvent.put("model", specModel);
        specialistEvent.put("configKey", specialistKey);
        specialistEvent.put("variationKey", variationKey);
        emit.accept(specialistEvent);

        // --- Optional scorers (Trace visibility; outcomes unchanged) --------------
        // LaunchDarkly: Library tools + track_tool_call
        // https://launchdarkly.com/docs/home/agentcontrol/tools
        NodeTracker nodeTracker = new NodeTracker(
                requireClient(), context, specialistKey, variationKey, specCfg.version(), specModel, graphKey());

        if (specialist.equals("questions")) {
            emit.accept(Map.of("type", "status", "message", "Scoring questions (gap / ground)…"));
            List<String> questions = extractQuestionsFromDraft(specialistDraft);
            if (questions.isEmpty()) {
                emit.accept(Map.of(
                        "type", "info",
                        "message", "No questions parsed for scoring — Trace skips tool scores.",
                        "kind", "tool"));
            }
            int callIndex = 0;
            for (String q : questions) {
                Map<String, Double> scores;
                try {
                    scores = scoreQuestionGap(q, storiesText, specModel);
                } catch (Exception exc) {
                    continue;
                }
                double gap = scores.get("gap");
                double ground = scores.get("ground");
                String gapName = formatToolNameWithScore(TOOL_QUESTION_GAP, gap);
                String groundName = formatToolNameWithScore("score-question-ground", ground);
                callIndex++;
                nodeTracker.trackToolCall(TOOL_QUESTION_GAP);
                Map<String, Object> gapEvent = new LinkedHashMap<>();
                gapEvent.put("type", "tool");
                gapEvent.put("name", gapName);
                gapEvent.put("toolKey", TOOL_QUESTION_GAP);
                gapEvent.put("score", gap);
                gapEvent.put("scores", Map.of("gap", gap, "ground", ground));
                gapEvent.put("args", Map.of("question", q));
                gapEvent.put("result", Map.of("gap", gap, "ground", ground));
                gapEvent.put("callIndex", callIndex);
                gapEvent.put("clip", clip(q, 40));
                emit.accept(gapEvent);

                callIndex++;
                Map<String, Object> groundEvent = new LinkedHashMap<>();
                groundEvent.put("type", "tool");
                groundEvent.put("name", groundName);
                groundEvent.put("toolKey", "score-question-ground");
                groundEvent.put("score", ground);
                groundEvent.put("args", Map.of("question", q));
                groundEvent.put("result", Map.of("ground", ground));
                groundEvent.put("callIndex", callIndex);
                groundEvent.put("clip", clip(q, 40));
                emit.accept(groundEvent);
            }
        } else if (specialist.equals("joke")) {
            emit.accept(Map.of("type", "status", "message", "Scoring joke corniness…"));
            double corny;
            try {
                corny = scoreJokeCorny(specialistDraft, specModel);
            } catch (Exception exc) {
                corny = 0.5;
            }
            String cornyName = formatToolNameWithScore(TOOL_JOKE_CORNY, corny);
            nodeTracker.trackToolCall(TOOL_JOKE_CORNY);
            Map<String, Object> cornyEvent = new LinkedHashMap<>();
            cornyEvent.put("type", "tool");
            cornyEvent.put("name", cornyName);
            cornyEvent.put("toolKey", TOOL_JOKE_CORNY);
            cornyEvent.put("score", corny);
            cornyEvent.put("args", Map.of("joke", clip(specialistDraft, 120)));
            cornyEvent.put("result", Map.of("corny", corny));
            cornyEvent.put("callIndex", 1);
            cornyEvent.put("clip", clip(specialistDraft, 40));
            emit.accept(cornyEvent);

            double high = cornyHighThreshold();
            double low = cornyLowThreshold();
            int level = humorLevelFor(persona);
            if (corny >= high) {
                emit.accept(Map.of(
                        "type", "info",
                        "message", String.format(Locale.US,
                                "Corny %.2f \u2265 %.2f — recommend lowering humor setting (currently %d%%).",
                                corny, high, level),
                        "kind", "humor-tip"));
            } else if (corny <= low) {
                emit.accept(Map.of(
                        "type", "info",
                        "message", String.format(Locale.US,
                                "Corny %.2f \u2264 %.2f — recommend raising humor setting (currently %d%%).",
                                corny, low, level),
                        "kind", "humor-tip"));
            }
        }

        String finalizeKey = nodeKey("finalize");
        FinalizeCheck finCheck = finalizeEdgeOk(graph, specialistKey);
        emit.accept(Map.of(
                "type", "info", "message", finCheck.note(), "kind", "edge", "validated", finCheck.ok()));
        if (!finCheck.ok()) {
            graphTracker.trackHandoffFailure(specialistKey, finalizeKey);
            emit.accept(Map.of(
                    "type", "error",
                    "message", "Graph has no edge from " + specialistKey + " to " + finalizeKey
                            + ". Fix the Agent Graph topology in LaunchDarkly."));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done", "specialist", specialist, "action", uiAction));
            return;
        }

        path.add(finalizeKey);
        graphTracker.trackHandoffSuccess(specialistKey, finalizeKey);

        // --- Step 3: finalize (stream to Response) -------------------------------
        // Joke drafts: pass through (still evaluate finalize + track the edge).
        // Small models otherwise invent a "market briefing" after the punchline when
        // headlines are in context (often from a prior Get Stories / localStorage).
        emit.accept(Map.of("type", "status", "message", "finalize — polishing…"));
        AgentEval finCfg;
        try {
            Map<String, String> finVars = new LinkedHashMap<>();
            finVars.put("action", uiAction);
            finVars.put("specialist", specialist);
            finVars.put("draft", specialistDraft);
            finVars.put(
                    "stories",
                    specialist.equals("joke")
                            ? "(omitted for joke)"
                            : (hasRealStories ? storiesText : "(none)"));
            finCfg = evaluateAgent(finalizeKey, context, defaultInstructionsFile("finalize"), finVars, persona);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", "finalize agent_config failed: " + exc.getMessage()));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        String finModel = resolveModel(finCfg.modelName());

        Map<String, Object> modelEvent = new LinkedHashMap<>();
        modelEvent.put("type", "model");
        modelEvent.put("provider", "ollama");
        modelEvent.put("model", finModel);
        modelEvent.put("configKey", finalizeKey);
        modelEvent.put("phase", "finalize");
        emit.accept(modelEvent);

        StringBuilder finalText = new StringBuilder();
        boolean[] firstToken = {true};
        try {
            if (specialist.equals("joke")) {
                emit.accept(Map.of(
                        "type", "info",
                        "message",
                        "joke finalize: pass-through specialist draft "
                                + "(avoids small-model expansion into briefings)",
                        "kind", "finalize-passthrough"));
                String draft = specialistDraft == null ? "" : specialistDraft;
                final int step = 48;
                for (int i = 0; i < Math.max(draft.length(), 1); i += step) {
                    int end = Math.min(i + step, draft.length());
                    if (i >= end) {
                        break;
                    }
                    String chunk = draft.substring(i, end);
                    if (firstToken[0]) {
                        firstToken[0] = false;
                        metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);
                    }
                    finalText.append(chunk);
                    emit.accept(Map.of("type", "token", "text", chunk));
                }
            } else {
                String finUser = "Original action: " + uiAction + "\n"
                        + "Specialist: " + specialist + "\n\n"
                        + "SPECIALIST DRAFT:\n" + specialistDraft + "\n\n"
                        + "Return the final polished text only.";
                List<Map<String, String>> finMessages = messagesForNode(finCfg.instructions(), finUser);
                ollamaStream(finModel, finMessages, 0.0, chunk -> {
                    if (firstToken[0]) {
                        firstToken[0] = false;
                        metrics.put("ttft_ms", (System.nanoTime() - started) / 1_000_000L);
                    }
                    finalText.append(chunk);
                    emit.accept(Map.of("type", "token", "text", chunk));
                });
            }
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            graphTracker.trackInvocationFailure();
            emit.accept(Map.of("type", "done"));
            return;
        }

        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        metrics.put("finish_reason", "stop");
        if (!specialist.equals("joke")) {
            List<Map<String, String>> estimateMsgs = messagesForNode(
                    finCfg.instructions(),
                    "Original action: " + uiAction + "\nSpecialist: " + specialist + "\n\n"
                            + "SPECIALIST DRAFT:\n" + specialistDraft + "\n\n"
                            + "Return the final polished text only.");
            fillTokenEstimates(estimateMsgs, finalText.toString(), metrics);
        } else {
            fillTokenEstimates(
                    List.of(Map.of("role", "user", "content", specialistDraft == null ? "" : specialistDraft)),
                    finalText.toString(),
                    metrics);
        }

        Map<String, Object> finalizeEvent = new LinkedHashMap<>();
        finalizeEvent.put("type", "finalize");
        finalizeEvent.put("clip", clip(finalText.toString()));
        finalizeEvent.put("model", finModel);
        finalizeEvent.put("configKey", finalizeKey);
        emit.accept(finalizeEvent);

        graphTracker.trackPath(path);
        graphTracker.trackDuration((Long) metrics.get("latency_ms"));
        graphTracker.trackInvocationSuccess();

        // Per-node success trackers (best-effort).
        new NodeTracker(requireClient(), context, nodeKey("assess"), assessCfg.variationKey(),
                assessCfg.version(), assessModel, graphKey()).trackSuccess();
        nodeTracker.trackSuccess();
        new NodeTracker(requireClient(), context, finalizeKey, finCfg.variationKey(),
                finCfg.version(), finModel, graphKey()).trackSuccess();

        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        Map<String, Object> doneEvent = new LinkedHashMap<>();
        doneEvent.put("type", "done");
        doneEvent.put("path", path);
        doneEvent.put("specialist", specialist);
        doneEvent.put("action", uiAction);
        emit.accept(doneEvent);
    }

    private static List<Map<String, String>> messagesForNode(String instructions, String userContent) {
        return List.of(
                Map.of("role", "system", "content",
                        instructions == null || instructions.isBlank() ? "You are a helpful assistant." : instructions),
                Map.of("role", "user", "content", userContent)
        );
    }

    // -------------------------------------------------------------------
    // Ollama HTTP
    // -------------------------------------------------------------------

    /** Non-streaming completion (assess / scorers). */
    private static String ollamaComplete(String model, List<Map<String, String>> messages, double temperature)
            throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        String url = host + "/api/chat";

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("messages", messages);
        payload.put("stream", false);
        payload.put("options", Map.of("temperature", temperature));
        String body = GSON.toJson(payload);

        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
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
                            + ". Is Ollama running, and does `ollama list` include " + model + "?", exc);
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama request failed (" + host + ", model=" + model + "): HTTP " + response.statusCode()
                            + ". Is Ollama running, and does `ollama list` include " + model + "?");
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
        return content;
    }

    /** Streaming completion (finalize). */
    private static void ollamaStream(
            String model, List<Map<String, String>> messages, double temperature, Consumer<String> onChunk)
            throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        String url = host + "/api/chat";

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("messages", messages);
        payload.put("stream", true);
        payload.put("options", Map.of("temperature", temperature));
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
                    "Ollama stream failed (" + host + ", model=" + model + "): " + exc.getMessage()
                            + ". Is Ollama running, and does `ollama list` include " + model + "?", exc);
        }
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException(
                    "Ollama stream failed (" + host + ", model=" + model + "): HTTP " + response.statusCode()
                            + ". Is Ollama running, and does `ollama list` include " + model + "?");
        }

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
                    onChunk.accept(content);
                }
                if (data.has("done") && data.get("done").getAsBoolean()) {
                    break;
                }
            }
        }
    }

    // -------------------------------------------------------------------
    // Small helpers
    // -------------------------------------------------------------------

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
