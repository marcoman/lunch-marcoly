/**
 * Resolve grid selection highlight color and cohort label from username context.
 */
public final class HighlightStyle {
    // LaunchDarkly: flag key=enable-grid-selection-highlight name="Enable: grid selection highlight" kind=string
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-selection-highlight

    static final String FLAG_HIGHLIGHT = "enable-grid-selection-highlight";
    // LaunchDarkly: flag key=enable-grid-highlight-color-override name="Enable: grid highlight color override" kind=boolean
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/enable-grid-highlight-color-override

    static final String FLAG_CONTEXT = "enable-grid-highlight-color-override";
    // LaunchDarkly: flag key=show-navigation-move-count name="Show: navigation move count" kind=boolean
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/show-navigation-move-count

    static final String FLAG_COUNT = "show-navigation-move-count";

    private HighlightStyle() {
    }

    record Cohorts(boolean human, boolean robot, boolean beta) {
    }

    record Style(String highlightColor, String cohortLabel) {
    }

    static Cohorts parseCohorts(String username) {
        String lower = username.toLowerCase();
        return new Cohorts(
                lower.contains("human"),
                lower.contains("robot"),
                lower.contains("beta"));
    }

    static String colorLabelName(String highlightColor) {
        return "none".equals(highlightColor) ? "no-color" : highlightColor;
    }

    static String formatCohortLabel(String username, String highlightColor, boolean contextHighlight) {
        String colorName = colorLabelName(highlightColor);
        StringBuilder parts = new StringBuilder();
        if (contextHighlight) {
            Cohorts cohorts = parseCohorts(username);
            if (cohorts.human()) {
                parts.append("human");
            }
            if (cohorts.robot()) {
                if (!parts.isEmpty()) {
                    parts.append("-");
                }
                parts.append("robot");
            }
            if (cohorts.beta()) {
                if (!parts.isEmpty()) {
                    parts.append("-");
                }
                parts.append("beta");
            }
        }
        if (!parts.isEmpty()) {
            return "(" + parts + "-" + colorName + ")";
        }
        return "(" + colorName + ")";
    }

    static boolean isHighlightOff(String raw) {
        if (raw == null) {
            return true;
        }
        String v = raw.trim().toLowerCase();
        return v.isEmpty() || "none".equals(v) || "false".equals(v) || "off".equals(v);
    }

    static String resolveHighlightColor(
            String username,
            boolean highlightEnabled,
            boolean contextHighlight,
            String servedColor) {
        if (!highlightEnabled) {
            return "none";
        }
        if (!contextHighlight) {
            if (servedColor != null && !isHighlightOff(servedColor)) {
                return servedColor;
            }
            return "green";
        }
        Cohorts cohorts = parseCohorts(username);
        if (cohorts.human() && cohorts.beta()) {
            return "green";
        }
        if (cohorts.robot() && cohorts.beta()) {
            return "purple";
        }
        if (cohorts.human()) {
            return "yellow";
        }
        if (cohorts.robot()) {
            return "red";
        }
        if (cohorts.beta()) {
            return "blue";
        }
        if (servedColor != null && !isHighlightOff(servedColor)) {
            return servedColor;
        }
        return "green";
    }

    static Style resolve(String username, boolean highlightEnabled, boolean contextHighlight) {
        return resolve(username, highlightEnabled, contextHighlight, null);
    }

    static Style resolve(
            String username,
            boolean highlightEnabled,
            boolean contextHighlight,
            String servedColor) {
        String color = resolveHighlightColor(username, highlightEnabled, contextHighlight, servedColor);
        String label = formatCohortLabel(username, color, contextHighlight);
        return new Style(color, label);
    }
}
