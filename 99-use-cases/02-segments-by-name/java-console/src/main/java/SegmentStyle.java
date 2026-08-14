import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;
import java.util.Locale;
import java.util.Set;

/**
 * Map segment types and flag variations to UI highlight styling.
 */
public final class SegmentStyle {
    // LaunchDarkly: flag key=configure-grid-selection-green-highlight name="Configure: grid selection green highlight" kind=boolean
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/configure-grid-selection-green-highlight

    static final String FLAG_HIGHLIGHT = "configure-grid-selection-green-highlight";
    // LaunchDarkly: flag key=VIP name="VIP" kind=boolean
    // https://app.launchdarkly.com/projects/lunch-marcoly/features/VIP

    static final String FLAG_VIP = "VIP";
    static final String VIP_BADGE = "**VIP**";

    private static final Set<String> VALID_COLORS =
            Set.of("yellow", "red", "blue", "green", "purple");

    private static LDClient client;

    private SegmentStyle() {
    }

    record FlagValues(String highlightColor, String segmentLabel, String segmentType, boolean vip) {
        static FlagValues fromSegment(SegmentContext.SegmentInfo info) {
            return buildResponse("none", info, false);
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
            return buildResponse("none", info, false);
        }
        var context = SegmentContext.buildContext(username);
        String raw = client.stringVariation(FLAG_HIGHLIGHT, context, "none");
        boolean vip = client.boolVariation(FLAG_VIP, context, false);
        return buildResponse(normalizeHighlightColor(raw), info, vip);
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

    private static FlagValues buildResponse(
            String highlightColor, SegmentContext.SegmentInfo info, boolean vip) {
        return new FlagValues(
                highlightColor,
                formatSegmentLabel(info, highlightColor),
                info.segmentType(),
                vip);
    }
}
