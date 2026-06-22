import com.launchdarkly.sdk.LDContext;

import java.util.Locale;
import java.util.Set;

/**
 * Build LaunchDarkly user contexts for segment-by-name targeting.
 */
public final class SegmentContext {
    static final String SEGMENT_GENERIC = "generic";
    static final String SEGMENT_NAMED_COLOR = "named-color";
    static final String SEGMENT_HUMAN = "human";
    static final String SEGMENT_ROBOT = "robot";
    static final String SEGMENT_HUMAN_BETA = "human-beta";
    static final String SEGMENT_ROBOT_BETA = "robot-beta";

    private static final Set<String> COLOR_NAMES =
            Set.of("yellow", "red", "blue", "green", "purple");

    private SegmentContext() {
    }

    record SegmentInfo(String segmentType, String namedColor) {
    }

    static int letterCount(String username) {
        int count = 0;
        for (int i = 0; i < username.length(); i++) {
            if (Character.isLetter(username.charAt(i))) {
                count += 1;
            }
        }
        return count;
    }

    static SegmentInfo resolveSegmentInfo(String username) {
        String lower = username.toLowerCase(Locale.ROOT);

        if ("generic".equals(lower)) {
            return new SegmentInfo(SEGMENT_GENERIC, null);
        }
        if (COLOR_NAMES.contains(lower)) {
            return new SegmentInfo(SEGMENT_NAMED_COLOR, lower);
        }

        boolean isHuman = letterCount(username) % 2 == 0;
        boolean isBeta = lower.contains("beta");

        if (isHuman && isBeta) {
            return new SegmentInfo(SEGMENT_HUMAN_BETA, null);
        }
        if (isHuman) {
            return new SegmentInfo(SEGMENT_HUMAN, null);
        }
        if (isBeta) {
            return new SegmentInfo(SEGMENT_ROBOT_BETA, null);
        }
        return new SegmentInfo(SEGMENT_ROBOT, null);
    }

    static LDContext buildContext(String username) {
        SegmentInfo info = resolveSegmentInfo(username);
        var builder = LDContext.builder(username).set("segmentType", info.segmentType());

        if (SEGMENT_GENERIC.equals(info.segmentType())) {
            builder.set("generic", true);
        } else if (SEGMENT_NAMED_COLOR.equals(info.segmentType()) && info.namedColor() != null) {
            builder.set("namedColor", info.namedColor());
        } else {
            String userKind = info.segmentType().startsWith("human") ? "human" : "robot";
            builder.set("userKind", userKind);
            builder.set("beta", info.segmentType().endsWith("beta"));
        }

        return builder.build();
    }
}
