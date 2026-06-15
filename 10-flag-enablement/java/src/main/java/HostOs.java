/**
 * Host OS detection and emoji mapping for private-attribute flag evaluation.
 * LaunchDarkly capability: Private context attributes (server-side SDK)
 * See: https://launchdarkly.com/docs/sdk/features/private-attributes
 */
public final class HostOs {
    static final String HOST_OS_ATTR = "hostOs";
    static final String FLAG_OS_EMOJI = "show-host-os-emoji";

    private HostOs() {
    }

    static String detectHostOs() {
        String osName = System.getProperty("os.name", "").toLowerCase();
        if (osName.contains("linux")) {
            return "linux";
        }
        if (osName.contains("windows")) {
            return "windows";
        }
        if (osName.contains("mac") || osName.contains("darwin")) {
            return "macos";
        }
        return "other";
    }

    static String osEmojiFor(String hostOs, boolean showOsEmoji) {
        if (!showOsEmoji) {
            return "";
        }
        return switch (hostOs) {
            case "linux" -> "🐧";
            case "macos" -> "🍎";
            case "windows" -> "🪟";
            default -> "😊";
        };
    }

    static String displayName(String username, String osEmoji) {
        if (osEmoji == null || osEmoji.isEmpty()) {
            return username;
        }
        return osEmoji + " " + username;
    }

    static com.launchdarkly.sdk.LDContext buildContext(String username, String hostOs) {
        return com.launchdarkly.sdk.LDContext.builder(username)
                .set("hostOs", hostOs)
                .privateAttributes("hostOs")
                .build();
    }
}
