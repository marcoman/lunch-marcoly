/**
 * Resolve grid selection highlight color and cohort label from username context.
 */
public final class HighlightStyle {
    static final String FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";
    static final String FLAG_CONTEXT = "configure-grid-selection-context-highlight";
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

    static String resolveHighlightColor(String username, boolean highlightEnabled, boolean contextHighlight) {
        if (!highlightEnabled) {
            return "none";
        }
        if (!contextHighlight) {
            return "pink";
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
        return "pink";
    }

    static Style resolve(String username, boolean highlightEnabled, boolean contextHighlight) {
        String color = resolveHighlightColor(username, highlightEnabled, contextHighlight);
        String label = formatCohortLabel(username, color, contextHighlight);
        return new Style(color, label);
    }
}
