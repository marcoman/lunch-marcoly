import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Guardrail metrics for the guarded environment release.
 *
 * LaunchDarkly: custom metrics
 * https://launchdarkly.com/docs/home/metrics/custom-metrics
 */
public final class Metrics {
    static final int LATENCY_THRESHOLD_MS = 200;
    static final double HEALTHY_LATENCY_MS = 50;
    static final int SAMPLE_COUNT = 24;
    static final String EVENT_LATENCY = "grid-navigation-latency";
    static final String EVENT_MOVEMENT = "grid-navigation-count";

    private Metrics() {
    }

    static List<JsonObject> definitions() {
        List<JsonObject> items = new ArrayList<>();
        items.add(metric(
                "grid-nav-latency",
                "Grid navigation latency",
                "Milliseconds reported for one grid move. Lower is better. "
                        + "Above 200 ms is the latency guardrail. "
                        + "In 23-api-guarded-rollout, contexts receiving green send the slider value "
                        + "and contexts still on none send 50 ms, so a high slider makes the new variation look slower. "
                        + "In 15-guarded-rollout a harness draws a random delay.",
                EVENT_LATENCY,
                true,
                "milliseconds",
                "average",
                "mean",
                "violation",
                "latency"));
        items.add(metric(
                "grid-highlight-error-rate",
                "Grid highlight error rate",
                "One event means the selected cell showed the wrong highlight color. "
                        + "Lower is better. The guardrail is 0% errors. "
                        + "23-api-guarded-rollout sends no events, so this guardrail stays normal "
                        + "while you watch latency.",
                "grid-highlight-color-error",
                false,
                null,
                null,
                null,
                "normal",
                "error-rate"));
        items.add(metric(
                "grid-nav-movement",
                "Grid navigation movement",
                "How many times the user moved on the grid. Higher is better. "
                        + "The guardrail is at least one navigation. "
                        + "23-api-guarded-rollout sends 1 on each move and each automatic report, "
                        + "so this guardrail stays normal.",
                EVENT_MOVEMENT,
                true,
                "navigations",
                "sum",
                "mean",
                "normal",
                "movement"));
        return items;
    }

    static JsonArray views() {
        JsonArray views = new JsonArray();
        for (JsonObject item : definitions()) {
            JsonObject view = new JsonObject();
            view.addProperty("key", item.get("key").getAsString());
            view.addProperty("name", item.get("name").getAsString());
            view.addProperty("eventKey", item.get("eventKey").getAsString());
            view.addProperty("description", item.get("description").getAsString());
            view.addProperty("role", item.get("role").getAsString());
            views.add(view);
        }
        return views;
    }

    static JsonObject createBody(JsonObject definition) {
        JsonObject body = definition.deepCopy();
        body.remove("role");
        return body;
    }

    static List<String> sampleUsernames(String username) {
        List<String> names = new ArrayList<>();
        names.add(username);
        for (int index = 1; index < SAMPLE_COUNT; index += 1) {
            names.add(username + "-" + index);
        }
        return names;
    }

    private static JsonObject metric(
            String key,
            String name,
            String description,
            String eventKey,
            boolean numeric,
            String unit,
            String unitAggregationType,
            String analysisType,
            String role,
            String tag) {
        JsonObject body = new JsonObject();
        body.addProperty("key", key);
        body.addProperty("name", name);
        body.addProperty("description", description);
        body.addProperty("kind", "custom");
        body.addProperty("isNumeric", numeric);
        body.addProperty("eventKey", eventKey);
        if (numeric) {
            body.addProperty("unit", unit);
            body.addProperty("unitAggregationType", unitAggregationType);
            body.addProperty("analysisType", analysisType);
            body.addProperty("successCriteria", "sum".equals(unitAggregationType) ? "HigherThanBaseline" : "LowerThanBaseline");
        } else {
            body.addProperty("successCriteria", "LowerThanBaseline");
        }
        JsonArray units = new JsonArray();
        units.add("user");
        body.add("analysisUnits", units);
        JsonArray tags = new JsonArray();
        tags.add("grid-navigator");
        tags.add("use-case");
        tags.add("guarded-rollout");
        tags.add(tag);
        body.add("tags", tags);
        body.addProperty("role", role);
        return body;
    }
}
