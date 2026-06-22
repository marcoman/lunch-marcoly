import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Map segment types and flag variations to UI highlight styling.
 */
public final class SegmentStyle {
    static final String FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";

    private static final Set<String> VALID_COLORS =
            Set.of("yellow", "red", "blue", "green", "purple");

    private static LDClient client;

    private SegmentStyle() {
    }

    record FlagValues(String highlightColor, String segmentLabel, String segmentType) {
        static FlagValues fromSegment(SegmentContext.SegmentInfo info) {
            return buildResponse("none", info);
        }
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags default to off.");
            return;
        }
        client = new LDClient(sdkKey, new LDConfig.Builder().build());
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flags default to off.");
            try {
                client.close();
            } catch (IOException ignored) {
            }
            client = null;
        }
    }

    static synchronized void close() {
        if (client != null) {
            try {
                client.close();
            } catch (IOException ignored) {
            }
            client = null;
        }
    }

    static FlagValues evaluate(String username) {
        SegmentContext.SegmentInfo info = SegmentContext.resolveSegmentInfo(username);
        if (client == null || username == null || username.isBlank()) {
            return buildResponse("none", info);
        }
        String raw = client.stringVariation(
                FLAG_HIGHLIGHT, SegmentContext.buildContext(username), "none");
        return buildResponse(normalizeHighlightColor(raw), info);
    }

    static String colorLabelName(String highlightColor) {
        return "none".equals(highlightColor) ? "no-color" : highlightColor;
    }

    static String formatSegmentLabel(SegmentContext.SegmentInfo info, String highlightColor) {
        String colorName = colorLabelName(highlightColor);
        return switch (info.segmentType()) {
            case SegmentContext.SEGMENT_GENERIC -> "(generic)";
            case SegmentContext.SEGMENT_NAMED_COLOR -> "(" + colorName + ")";
            case SegmentContext.SEGMENT_HUMAN, SegmentContext.SEGMENT_ROBOT ->
                    "(" + info.segmentType() + "-" + colorName + ")";
            case SegmentContext.SEGMENT_HUMAN_BETA, SegmentContext.SEGMENT_ROBOT_BETA ->
                    "(" + info.segmentType() + "-" + colorName + ")";
            default -> "(" + colorName + ")";
        };
    }

    private static String normalizeHighlightColor(Object raw) {
        String color = String.valueOf(raw == null ? "none" : raw).trim().toLowerCase(Locale.ROOT);
        return VALID_COLORS.contains(color) ? color : "none";
    }

    private static FlagValues buildResponse(String highlightColor, SegmentContext.SegmentInfo info) {
        return new FlagValues(
                highlightColor,
                formatSegmentLabel(info, highlightColor),
                info.segmentType());
    }
}
