import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.launchdarkly.sdk.EvaluationDetail;
import com.launchdarkly.sdk.EvaluationReason;
import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.LDValueType;
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
import java.util.function.Consumer;
import java.util.regex.Pattern;

/**
 * Domain logic for 26-flags-vs-agent-control (no HTTP here).
 *
 * There is no official Java AI SDK. Completion configs, the judge config, and
 * feature flags are evaluated with the server SDK. The app interpolates
 * {{ stories }} itself. The guardrail score is an Ollama JSON call using the
 * judge config's system prompt. Python uses create_judge. Node uses judgeConfig.
 *
 * LaunchDarkly: jsonValueVariationDetail · variation reasons · Library tools
 * https://launchdarkly.com/docs/sdk/server-side/java
 * https://launchdarkly.com/docs/sdk/features/evaluation-reasons
 * https://launchdarkly.com/docs/home/agentcontrol/judges
 * https://launchdarkly.com/docs/home/agentcontrol/tools
 */
public final class AgentCore {
    public record Persona(String id, String name, String profile) {}

    private static final String CANNED_STORIES =
            "No ticker stories loaded yet. Ask the user to click Get Stories.";
    private static final String DEFAULT_CONFIG_KEY = "equity-briefing-flag-compare";
    private static final String DEFAULT_JUDGE_KEY = "equity-briefing-flag-compare-judge";
    private static final String DEFAULT_JUDGE_METRIC = "$ld:ai:judge:flag-compare";
    private static final double DEFAULT_PASS_THRESHOLD = 0.65;
    private static final String REPAIR_TOOL_KEY = "reduce-briefing-uncertainty";
    private static final String DEFAULT_OLLAMA_MODEL = "llama3.2:3b";
    private static final String JUDGE_JSON_SUFFIX =
            "Respond with JSON only: {\"score\": <number from 0 to 1>, \"reasoning\": \"<short text>\"}";
    private static final String EVENT_TOOL_CALL = "$ld:ai:tool:call";

    private static final String FLAG_MODEL_KEY = "configure-briefing-model";
    private static final String FLAG_SYSTEM_KEY = "configure-briefing-system-prompt";
    private static final String FLAG_USER_KEY = "configure-briefing-user-prompt";
    private static final String FLAG_JUDGE_KEY = "enable-briefing-judge";
    private static final String FLAG_JSON_KEY = "configure-briefing-json";

    private static final List<Persona> PERSONAS = List.of(
            new Persona("conservative-charlie", "Conservative Charlie", "conservative"),
            new Persona("thoughtless-toby", "Thoughtless Toby", "risk-taker")
    );

    private static final Gson GSON = new Gson();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private static LDClient ldClient;

    private AgentCore() {}

    public static List<Persona> demoPersonas() {
        return PERSONAS.stream().filter(p -> "thoughtless-toby".equals(p.id())).toList();
    }

    public static Persona personaById(String id) {
        for (Persona persona : PERSONAS) {
            if (persona.id().equals(id)) {
                return persona;
            }
        }
        return null;
    }

    public static String configKey() {
        String key = env("LD_AGENT_CONFIG_KEY", DEFAULT_CONFIG_KEY).trim();
        return key.isEmpty() ? DEFAULT_CONFIG_KEY : key;
    }

    public static String judgeKey() {
        String key = env("LD_JUDGE_KEY", DEFAULT_JUDGE_KEY).trim();
        return key.isEmpty() ? DEFAULT_JUDGE_KEY : key;
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

    public static synchronized void initLaunchDarkly() {
        if (ldClient != null) {
            return;
        }
        String sdkKey = env("LD_SDK_KEY", "").trim();
        if (sdkKey.isEmpty()) {
            throw new IllegalStateException(
                    "LD_SDK_KEY is required. Export a server-side SDK key for the "
                            + "environment that targets equity-briefing-flag-compare.");
        }
        ldClient = new LDClient(sdkKey, new LDConfig.Builder().build());
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

    public static void generateStream(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            String source,
            Consumer<Map<String, Object>> emit
    ) {
        if ("flags".equals(source) || "json".equals(source)) {
            generateFromFlags(persona, tickerResults, source, emit);
            return;
        }
        generateFromAgentControl(persona, tickerResults, emit);
    }

    private static void generateFromFlags(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            String source,
            Consumer<Map<String, Object>> emit
    ) {
        Prompts defaults = personaPrompts(persona);
        List<Map<String, Object>> records = new ArrayList<>();
        List<String> missing = new ArrayList<>();
        String model = defaults.model;
        String system = defaults.system;
        String user = defaults.user;
        boolean judgeOn = true;
        int evaluations = "flags".equals(source) ? 4 : 1;

        if ("flags".equals(source)) {
            EvaluationDetail<String> modelDetail = readString(persona, FLAG_MODEL_KEY, defaults.model, emit, records, missing);
            EvaluationDetail<String> systemDetail = readString(persona, FLAG_SYSTEM_KEY, defaults.system, emit, records, missing);
            EvaluationDetail<String> userDetail = readString(persona, FLAG_USER_KEY, defaults.user, emit, records, missing);
            EvaluationDetail<Boolean> judgeDetail = readBool(persona, FLAG_JUDGE_KEY, true, emit, records, missing);
            model = blank(modelDetail.getValue()) ? defaults.model : modelDetail.getValue();
            system = blank(systemDetail.getValue()) ? defaults.system : systemDetail.getValue();
            user = blank(userDetail.getValue()) ? defaults.user : userDetail.getValue();
            judgeOn = Boolean.TRUE.equals(judgeDetail.getValue());
        } else {
            LDValue fallback = LDValue.buildObject()
                    .put("model", defaults.model)
                    .put("systemPrompt", defaults.system)
                    .put("userPrompt", defaults.user)
                    .put("judge", true)
                    .build();
            emit.accept(evalEvent("flag", FLAG_JSON_KEY));
            EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(
                    FLAG_JSON_KEY, context(persona), fallback);
            records.add(detailRecord(FLAG_JSON_KEY, detail.getValue(), detail));
            if (isMissing(detail.getReason())) {
                missing.add(FLAG_JSON_KEY);
            }
            LDValue body = detail.getValue() == null || detail.getValue().isNull() ? fallback : detail.getValue();
            model = ldString(body.get("model"));
            if (model.isEmpty()) model = defaults.model;
            system = ldString(body.get("systemPrompt"));
            if (system.isEmpty()) system = defaults.system;
            user = ldString(body.get("userPrompt"));
            if (user.isEmpty()) user = defaults.user;
            judgeOn = body.get("judge").isNull() || body.get("judge").booleanValue();
        }

        String storiesText = formatStories(tickerResults);
        long started = System.nanoTime();
        Map<String, Object> metrics = new LinkedHashMap<>();
        List<Map<String, String>> messages = List.of(
                Map.of("role", "system", "content", system.trim()),
                Map.of("role", "user", "content", fillStories(user, storiesText))
        );

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("type", "meta");
        meta.put("persona", personaMap(persona));
        meta.put("input", messages.get(1).get("content"));
        meta.put("userTemplate", user.trim());
        meta.put("provider", "ollama");
        meta.put("model", model);
        meta.put("mode", source);
        meta.put("configKey", "json".equals(source) ? FLAG_JSON_KEY : FLAG_MODEL_KEY);
        meta.put("fallback", !missing.isEmpty());
        meta.put("stories", tickerResults == null ? List.of() : tickerResults);
        meta.put("source", source);
        meta.put("systemPrompt", system.trim());
        meta.put("judgeOn", judgeOn);
        meta.put("judgeSurface", judgeOn ? ("flags".equals(source) ? "boolean-flag" : "json-flag") : "off");
        meta.put("evaluations", evaluations);
        meta.put("ldTransaction", flagTransaction(persona, source, model, system, user, judgeOn, evaluations, records));
        emit.accept(meta);

        if (!missing.isEmpty()) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "Flag not found: " + String.join(", ", missing)
                            + ". Using in-code defaults. Provision with rest/create-flags.sh."
            ));
        }

        String draft = "";
        try {
            draft = generateOllama(model, messages, started, metrics, emit);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            metrics.put("finish_reason", "error");
        }
        if (judgeOn) {
            emit.accept(Map.of("type", "status", "message", "Scoring the draft…"));
            emit.accept(evalEvent("judge", judgeKey()));
            emit.accept(scoreDraft(persona, storiesText, draft, source, evaluations + 1));
        } else {
            Map<String, Object> off = new LinkedHashMap<>();
            off.put("type", "judge");
            off.put("source", source);
            off.put("on", false);
            off.put("passed", null);
            off.put("score", null);
            off.put("evaluations", evaluations);
            emit.accept(off);
        }
        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        emit.accept(Map.of("type", "done"));
    }

    private static void generateFromAgentControl(
            Persona persona,
            List<Map<String, Object>> tickerResults,
            Consumer<Map<String, Object>> emit
    ) {
        String storiesText = formatStories(tickerResults);
        long started = System.nanoTime();
        Map<String, Object> metrics = new LinkedHashMap<>();
        emit.accept(evalEvent("agent config", configKey()));

        EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(
                configKey(), context(persona), completionDefault());
        LDValue value = detail.getValue() == null ? LDValue.ofNull() : detail.getValue();
        Map<String, Object> reason = reasonMap(detail.getReason());
        LDValue meta = value.get("_ldMeta");
        boolean enabled = isEnabled(value);
        if (!enabled) {
            emit.accept(Map.of(
                    "type", "error",
                    "message", "AgentControl config '" + configKey()
                            + "' is off / enabled=false. Run rest/create-original.sh."
            ));
            emit.accept(Map.of("type", "done"));
            return;
        }

        String model = modelName(value);
        if (model.isEmpty()) model = defaultOllamaModel();
        List<Map<String, String>> messages = parseMessages(value, storiesText, persona);
        List<String> tools = toolNames(value);
        String variationKey = ldString(meta.get("variationKey"));
        System.out.println("[generate] " + persona.name()
                + ": variation='" + variationKey + "' reason='" + reason.get("kind") + "'");

        Map<String, Object> event = new LinkedHashMap<>();
        event.put("type", "meta");
        event.put("persona", personaMap(persona));
        event.put("input", userText(messages).isEmpty() ? storiesText : userText(messages));
        event.put("provider", "ollama");
        event.put("model", model);
        event.put("mode", "launchdarkly");
        event.put("configKey", configKey());
        event.put("variationKey", variationKey);
        event.put("fallback", false);
        event.put("stories", tickerResults == null ? List.of() : tickerResults);
        event.put("source", "original");
        event.put("systemPrompt", systemText(messages));
        event.put("judgeOn", true);
        event.put("judgeSurface", "judge-config");
        event.put("evaluations", 1);
        event.put("ldTransaction", agentTransaction(
                persona, storiesText, model, messages, tools, detail, reason, enabled));
        emit.accept(event);

        if ("FLAG_NOT_FOUND".equals(String.valueOf(reason.get("errorKind")))) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "Completion config '" + configKey()
                            + "' was not found. Using the in-code concise-skeptic default. "
                            + "Provision with rest/create-original.sh."
            ));
        }

        String draft = "";
        try {
            draft = generateOllama(model, messages, started, metrics, emit);
            trackGeneration(persona, true);
        } catch (Exception exc) {
            emit.accept(Map.of("type", "error", "message", String.valueOf(exc.getMessage())));
            trackGeneration(persona, false);
        }

        emit.accept(Map.of("type", "status", "message", "Scoring the draft…"));
        emit.accept(evalEvent("judge", judgeKey()));
        Map<String, Object> scored = scoreDraft(persona, storiesText, draft, "original", 2);
        emit.accept(scored);
        repairIfFailed(persona, tools, draft, scored, emit);
        metrics.put("latency_ms", (System.nanoTime() - started) / 1_000_000L);
        emit.accept(Map.of("type", "metrics", "metrics", metrics));
        emit.accept(Map.of("type", "done"));
    }

    private static EvaluationDetail<String> readString(
            Persona persona,
            String key,
            String fallback,
            Consumer<Map<String, Object>> emit,
            List<Map<String, Object>> records,
            List<String> missing
    ) {
        emit.accept(evalEvent("flag", key));
        EvaluationDetail<String> detail = requireClient().stringVariationDetail(key, context(persona), fallback);
        records.add(detailRecord(key, LDValue.of(detail.getValue() == null ? "" : detail.getValue()), detail));
        if (isMissing(detail.getReason())) {
            missing.add(key);
        }
        return detail;
    }

    private static EvaluationDetail<Boolean> readBool(
            Persona persona,
            String key,
            boolean fallback,
            Consumer<Map<String, Object>> emit,
            List<Map<String, Object>> records,
            List<String> missing
    ) {
        emit.accept(evalEvent("flag", key));
        EvaluationDetail<Boolean> detail = requireClient().boolVariationDetail(key, context(persona), fallback);
        boolean value = Boolean.TRUE.equals(detail.getValue());
        records.add(detailRecord(key, LDValue.of(value), detail));
        if (isMissing(detail.getReason())) {
            missing.add(key);
        }
        return detail;
    }

    private static Map<String, Object> scoreDraft(
            Persona persona, String storiesText, String draft, String source, int evaluations) {
        Map<String, Object> base = new LinkedHashMap<>();
        base.put("type", "judge");
        base.put("source", source);
        base.put("on", true);
        base.put("judgeKey", judgeKey());
        base.put("threshold", passThreshold());
        base.put("evaluations", evaluations);
        if (draft == null || draft.isBlank()) {
            base.put("success", false);
            base.put("passed", false);
            base.put("score", null);
            base.put("reasoning", null);
            base.put("error", "No draft to score.");
            return base;
        }
        try {
            EvaluationDetail<LDValue> detail = requireClient().jsonValueVariationDetail(
                    judgeKey(), context(persona), judgeDefault());
            LDValue value = detail.getValue();
            String model = modelName(value);
            if (model.isEmpty()) model = "llama3.2:3b";
            String system = systemText(parseMessages(value, "", persona));
            if (system.isBlank()) system = readMessage("judge-system.txt").trim();
            if (!system.contains("Respond with JSON")) {
                system = system + "\n\n" + JUDGE_JSON_SUFFIX;
            }
            String user = "MESSAGE HISTORY:\nTask: Write a short equity briefing comparing the tickers "
                    + "using only the headlines below.\n\nHEADLINES:\n" + storiesText
                    + "\n\nRESPONSE TO EVALUATE:\n" + draft;
            JsonObject parsed = ollamaJudgeJson(model, List.of(
                    Map.of("role", "system", "content", system),
                    Map.of("role", "user", "content", user)
            ));
            Double score = parsed.has("score") && parsed.get("score").isJsonPrimitive()
                    ? parsed.get("score").getAsDouble() : null;
            String reasoning = parsed.has("reasoning") && !parsed.get("reasoning").isJsonNull()
                    ? parsed.get("reasoning").getAsString() : null;
            base.put("success", true);
            base.put("error", null);
            base.put("score", score);
            base.put("reasoning", reasoning);
            base.put("metricKey", DEFAULT_JUDGE_METRIC);
            base.put("passed", score != null && score >= passThreshold());
            return base;
        } catch (Exception exc) {
            base.put("success", false);
            base.put("passed", false);
            base.put("score", null);
            base.put("reasoning", null);
            base.put("error", String.valueOf(exc.getMessage()));
            return base;
        }
    }

    private static void repairIfFailed(
            Persona persona,
            List<String> tools,
            String draft,
            Map<String, Object> scored,
            Consumer<Map<String, Object>> emit
    ) {
        if (!Boolean.FALSE.equals(scored.get("passed")) || Boolean.FALSE.equals(scored.get("on"))) {
            return;
        }
        if (!tools.contains(REPAIR_TOOL_KEY)) {
            emit.accept(Map.of(
                    "type", "status",
                    "message", "Judge failed. This variation has no repair tool attached. "
                            + "Provision with rest/attach-repair-tool.sh."
            ));
            return;
        }
        emit.accept(evalEvent("tool", REPAIR_TOOL_KEY));
        try {
            LDValue trackData = LDValue.buildObject()
                    .put("configKey", configKey())
                    .put("toolKey", REPAIR_TOOL_KEY)
                    .build();
            requireClient().trackMetric(EVENT_TOOL_CALL, context(persona), trackData, 1.0);
        } catch (Exception ignored) {
        }
        emit.accept(Map.of(
                "type", "repair",
                "tool", REPAIR_TOOL_KEY,
                "repaired", reduceBriefingUncertainty(draft)
        ));
    }

    private static String reduceBriefingUncertainty(String draft) {
        String text = draft == null ? "" : draft;
        text = Pattern.compile("\\b100\\s*%", Pattern.CASE_INSENSITIVE).matcher(text).replaceAll("low");
        text = Pattern.compile("\\b9[5-9]\\s*%", Pattern.CASE_INSENSITIVE).matcher(text).replaceAll("limited");
        text = Pattern.compile(
                "\\b(?:buy hard|strong buy|all-in|moonshot|to the moon|can't lose|cannot lose|no-brainer)\\b",
                Pattern.CASE_INSENSITIVE).matcher(text).replaceAll("no firm trade");
        text = Pattern.compile(
                "\\b(?:will soar|will double|can't miss|cannot miss)\\b",
                Pattern.CASE_INSENSITIVE).matcher(text).replaceAll("may not move");
        if (!text.contains("Uncertainty:")) {
            text = text.strip() + "\n\nUncertainty: these headlines do not support a firm recommendation. "
                    + "Confidence stays low, and missing information is left missing.";
        }
        return text;
    }

    private static String generateOllama(
            String model,
            List<Map<String, String>> messages,
            long started,
            Map<String, Object> metrics,
            Consumer<Map<String, Object>> emit
    ) throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        Map<String, Object> payload = Map.of("model", model, "stream", true, "messages", messages);
        HttpRequest request = HttpRequest.newBuilder(URI.create(host + "/api/chat"))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(payload)))
                .build();
        HttpResponse<java.io.InputStream> response = HTTP.send(request, HttpResponse.BodyHandlers.ofInputStream());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("Ollama request failed (" + host + ", model=" + model
                    + "): HTTP " + response.statusCode());
        }
        StringBuilder text = new StringBuilder();
        boolean first = true;
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(response.body(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) continue;
                JsonObject data = JsonParser.parseString(line).getAsJsonObject();
                if (data.has("error")) throw new IOException(String.valueOf(data.get("error")));
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
                    text.append(content);
                    emit.accept(Map.of("type", "token", "text", content));
                }
                if (data.has("done") && data.get("done").getAsBoolean()) break;
            }
        }
        metrics.put("finish_reason", "stop");
        fillTokenEstimates(messages, text.toString(), metrics);
        return text.toString();
    }

    private static JsonObject ollamaJudgeJson(String model, List<Map<String, String>> messages)
            throws IOException, InterruptedException {
        String host = env("OLLAMA_HOST", "http://127.0.0.1:11434").replaceAll("/$", "");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("model", model);
        payload.put("stream", false);
        payload.put("format", "json");
        payload.put("options", Map.of("temperature", 0));
        payload.put("messages", messages);
        HttpRequest request = HttpRequest.newBuilder(URI.create(host + "/api/chat"))
                .timeout(Duration.ofSeconds(180))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(payload)))
                .build();
        HttpResponse<String> response = HTTP.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("Ollama judge failed (" + host + ", model=" + model
                    + "): HTTP " + response.statusCode());
        }
        JsonObject data = JsonParser.parseString(response.body()).getAsJsonObject();
        if (data.has("error")) throw new IOException(String.valueOf(data.get("error")));
        String content = "";
        if (data.has("message") && data.get("message").isJsonObject()) {
            JsonObject message = data.getAsJsonObject("message");
            if (message.has("content") && !message.get("content").isJsonNull()) {
                content = message.get("content").getAsString();
            }
        }
        if (content.isBlank()) throw new IOException("Ollama judge returned empty content");
        return JsonParser.parseString(content).getAsJsonObject();
    }

    private static void fillTokenEstimates(
            List<Map<String, String>> messages, String completion, Map<String, Object> metrics) {
        int prompt = 0;
        for (Map<String, String> message : messages) {
            prompt += Math.max(1, message.getOrDefault("content", "").length() / 4);
        }
        int output = Math.max(1, completion.length() / 4);
        metrics.put("prompt_tokens", prompt);
        metrics.put("completion_tokens", output);
        metrics.put("total_tokens", prompt + output);
    }

    private static Map<String, Object> flagTransaction(
            Persona persona,
            String source,
            String model,
            String system,
            String user,
            boolean judgeOn,
            int evaluations,
            List<Map<String, Object>> records
    ) {
        Map<String, Object> sent = new LinkedHashMap<>();
        sent.put("source", source);
        sent.put("context", contextMap(persona));
        sent.put("evaluations", evaluations);
        Map<String, Object> received = new LinkedHashMap<>();
        received.put("source", source);
        received.put("model", model);
        received.put("judgeOn", judgeOn);
        received.put("flagEvaluations", records);
        received.put("appWork", flagAppWork(source, judgeOn));
        received.put("messages", List.of(
                Map.of("role", "system", "content", system.trim()),
                Map.of("role", "user", "content", user.trim())
        ));
        return Map.of("sent", sent, "received", received);
    }

    private static Map<String, Object> agentTransaction(
            Persona persona,
            String storiesText,
            String model,
            List<Map<String, String>> messages,
            List<String> tools,
            EvaluationDetail<LDValue> detail,
            Map<String, Object> reason,
            boolean enabled
    ) {
        LDValue meta = detail.getValue().get("_ldMeta");
        Map<String, Object> sent = new LinkedHashMap<>();
        sent.put("configKey", configKey());
        sent.put("context", contextMap(persona));
        sent.put("variables", Map.of("stories", storiesText));
        Map<String, Object> received = new LinkedHashMap<>();
        received.put("fallback", false);
        received.put("mode", "launchdarkly");
        received.put("enabled", enabled);
        received.put("configKey", configKey());
        received.put("variationKey", ldString(meta.get("variationKey")));
        received.put("variationIndex", detail.getVariationIndex());
        received.put("reason", reason);
        received.put("version", meta.get("version").isNull() ? null : meta.get("version").intValue());
        received.put("versionKey", ldString(meta.get("versionKey")));
        received.put("ldMode", ldString(meta.get("mode")));
        received.put("modelKey", ldString(meta.get("modelKey")));
        received.put("modelVersion", ldString(meta.get("modelVersion")));
        received.put("provider", "ollama");
        received.put("model", model);
        received.put("messages", messages);
        received.put("tools", tools);
        received.put("appWork", List.of(
                "Evaluated one completion config for the model, both messages, and any attached tools.",
                "The Java server SDK returns the template. This app substitutes {{ stories }}.",
                "Called the model named on that variation.",
                "Evaluated one judge config. On a fail, the app runs reduce-briefing-uncertainty if that tool is attached.",
                "Separate flags and the JSON flag do not return a tool, so a failed draft stays failed."
        ));
        return Map.of("sent", sent, "received", received);
    }

    private static List<String> flagAppWork(String source, boolean judgeOn) {
        List<String> steps = new ArrayList<>();
        if ("json".equals(source)) {
            steps.add("Evaluated one JSON flag. The value is an object the app defined.");
            steps.add("Read model, systemPrompt, userPrompt, and judge out of that object.");
            steps.add("Substituted {{ stories }} in the user prompt.");
            steps.add("Built the message list and picked a provider from the model id.");
        } else {
            steps.add("Evaluated four flags. Each one repeated the Charlie name rule.");
            steps.add("Substituted {{ stories }} in the user-prompt flag.");
            steps.add("Built the message list from two string flags and picked a provider from the model id.");
        }
        steps.add(judgeOn
                ? "The flag said to score. The score itself still comes from the AgentControl judge config."
                : "The flag said not to score, so the draft stays plain.");
        return steps;
    }

    private static List<Map<String, String>> parseMessages(LDValue value, String storiesText, Persona persona) {
        List<Map<String, String>> out = new ArrayList<>();
        LDValue messages = value.get("messages");
        if (messages.getType() == LDValueType.ARRAY) {
            for (LDValue msg : messages.values()) {
                String role = ldString(msg.get("role"));
                String content = fillStories(ldString(msg.get("content")), storiesText)
                        .replace("{{ ldctx.name }}", persona.name())
                        .replace("{{ldctx.name}}", persona.name());
                if (!role.isEmpty()) {
                    out.add(Map.of("role", role, "content", content));
                }
            }
        }
        return out;
    }

    private static List<String> toolNames(LDValue value) {
        List<String> names = new ArrayList<>();
        LDValue tools = value.get("tools");
        if (tools.isNull()) return names;
        if (tools.getType() == LDValueType.ARRAY) {
            for (LDValue tool : tools.values()) {
                String name = ldString(tool.get("name"));
                if (name.isEmpty()) name = ldString(tool.get("key"));
                if (!name.isEmpty()) names.add(name);
            }
        } else {
            for (String key : tools.keys()) {
                String name = ldString(tools.get(key).get("name"));
                names.add(name.isEmpty() ? key : name);
            }
        }
        return names;
    }

    private static <T> Map<String, Object> detailRecord(String key, LDValue value, EvaluationDetail<T> detail) {
        Map<String, Object> reason = reasonMap(detail.getReason());
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("key", key);
        row.put("variationIndex", detail.getVariationIndex() < 0 ? null : detail.getVariationIndex());
        row.put("reason", reason);
        row.put("reasonKind", reason.get("kind"));
        row.put("valuePreview", preview(value));
        return row;
    }

    private static Map<String, Object> reasonMap(EvaluationReason reason) {
        Map<String, Object> out = new LinkedHashMap<>();
        if (reason == null) return out;
        out.put("kind", reason.getKind() == null ? null : reason.getKind().name());
        if (reason.getErrorKind() != null) out.put("errorKind", reason.getErrorKind().name());
        if (reason.getKind() == EvaluationReason.Kind.RULE_MATCH) {
            out.put("ruleIndex", reason.getRuleIndex());
            out.put("ruleId", reason.getRuleId());
        }
        return out;
    }

    private static boolean isMissing(EvaluationReason reason) {
        return reason != null
                && reason.getKind() == EvaluationReason.Kind.ERROR
                && reason.getErrorKind() == EvaluationReason.ErrorKind.FLAG_NOT_FOUND;
    }

    private static String preview(LDValue value) {
        String text;
        if (value == null || value.isNull()) text = "";
        else if (value.getType() == LDValueType.BOOLEAN) text = value.booleanValue() ? "true" : "false";
        else if (value.getType() == LDValueType.STRING) text = value.stringValue();
        else text = value.toJsonString();
        text = text.replaceAll("\\s+", " ").trim();
        return text.length() <= 180 ? text : text.substring(0, 179) + "…";
    }

    private static boolean isEnabled(LDValue value) {
        LDValue meta = value.get("_ldMeta");
        if (!meta.get("enabled").isNull()) return meta.get("enabled").booleanValue();
        if (!value.get("enabled").isNull()) return value.get("enabled").booleanValue();
        return true;
    }

    private static String modelName(LDValue value) {
        LDValue model = value.get("model");
        String name = ldString(model.get("name"));
        if (!name.isEmpty()) return name;
        name = ldString(model.get("modelName"));
        if (!name.isEmpty()) return name;
        return ldString(value.get("modelName"));
    }

    private static LDValue completionDefault() {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", defaultOllamaModel()).build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("messages", LDValue.buildArray()
                        .add(LDValue.buildObject()
                                .put("role", "system")
                                .put("content", readMessage("skeptic-system.txt").trim())
                                .build())
                        .add(LDValue.buildObject()
                                .put("role", "user")
                                .put("content", readMessage("skeptic-user.txt").trim())
                                .build())
                        .build())
                .build();
    }

    private static LDValue judgeDefault() {
        return LDValue.buildObject()
                .put("enabled", true)
                .put("model", LDValue.buildObject().put("name", "llama3.2:3b").build())
                .put("provider", LDValue.buildObject().put("name", "Custom").build())
                .put("evaluationMetricKey", DEFAULT_JUDGE_METRIC)
                .put("messages", LDValue.buildArray()
                        .add(LDValue.buildObject()
                                .put("role", "system")
                                .put("content", readMessage("judge-system.txt").trim())
                                .build())
                        .build())
                .build();
    }

    private static Prompts personaPrompts(Persona persona) {
        if ("thoughtless-toby".equals(persona.id())) {
            return new Prompts(
                    "llama3.2:1b",
                    readMessage("reckless-system.txt").trim(),
                    readMessage("reckless-user.txt").trim());
        }
        return new Prompts(
                "llama3.2:3b",
                readMessage("skeptic-system.txt").trim(),
                readMessage("skeptic-user.txt").trim());
    }

    private static String formatStories(List<Map<String, Object>> tickerResults) {
        if (tickerResults == null || tickerResults.isEmpty()) return CANNED_STORIES;
        return YahooNews.formatStoriesForPrompt(tickerResults);
    }

    private static String fillStories(String template, String storiesText) {
        return String.valueOf(template == null ? "" : template)
                .replace("{{ stories }}", storiesText)
                .replace("{{stories}}", storiesText);
    }

    private static String readMessage(String name) {
        Path file = YahooNews.exampleRoot().resolve("rest").resolve("messages").resolve(name);
        try {
            return Files.readString(file);
        } catch (IOException exc) {
            throw new IllegalStateException("Could not read " + file + ": " + exc.getMessage(), exc);
        }
    }

    private static LDContext context(Persona persona) {
        return LDContext.builder(persona.id()).name(persona.name()).build();
    }

    private static Map<String, Object> contextMap(Persona persona) {
        Map<String, Object> ctx = new LinkedHashMap<>();
        ctx.put("kind", "user");
        ctx.put("key", persona.id());
        ctx.put("name", persona.name());
        return ctx;
    }

    private static Map<String, Object> personaMap(Persona persona) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", persona.id());
        row.put("name", persona.name());
        row.put("profile", persona.profile());
        return row;
    }

    private static Map<String, Object> evalEvent(String surface, String key) {
        return Map.of("type", "eval", "surface", surface, "key", key);
    }

    private static void trackGeneration(Persona persona, boolean success) {
        try {
            requireClient().trackMetric(
                    success ? "$ld:ai:generation:success" : "$ld:ai:generation:error",
                    context(persona),
                    LDValue.buildObject().put("configKey", configKey()).build(),
                    1.0);
        } catch (Exception ignored) {
        }
    }

    private static String userText(List<Map<String, String>> messages) {
        for (Map<String, String> message : messages) {
            if ("user".equals(message.get("role"))) return message.getOrDefault("content", "");
        }
        return "";
    }

    private static String systemText(List<Map<String, String>> messages) {
        for (Map<String, String> message : messages) {
            if ("system".equals(message.get("role"))) return message.getOrDefault("content", "");
        }
        return "";
    }

    private static String ldString(LDValue value) {
        if (value == null || value.isNull()) return "";
        if (value.getType() == LDValueType.STRING) return value.stringValue();
        return "";
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private static String defaultOllamaModel() {
        String model = env("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).trim();
        return model.isEmpty() ? DEFAULT_OLLAMA_MODEL : model;
    }

    private static String env(String name, String fallback) {
        String value = System.getenv(name);
        return value == null ? fallback : value;
    }

    private static LDClient requireClient() {
        if (ldClient == null) initLaunchDarkly();
        return ldClient;
    }

    private record Prompts(String model, String system, String user) {}
}
