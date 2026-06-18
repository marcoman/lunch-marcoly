/**
 * Host OS detection and anonymous-context evaluation for flag variations.
 * LaunchDarkly capability: Anonymous contexts + private attributes
 * See: https://launchdarkly.com/docs/sdk/features/anonymous
 * See: https://launchdarkly.com/docs/sdk/features/private-attributes
 */
public final class HostOs {
    static final String HOST_OS_ATTR = "hostOs";
    static final String ANONYMOUS_CONTEXT_KEY = "anonymous";
    static final String FLAG_ANON_OS_EMOJI = "show-anonymous-host-os-emoji";

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

    static com.launchdarkly.sdk.LDContext buildAnonymousContext(String hostOs) {
        return com.launchdarkly.sdk.LDContext.builder(ANONYMOUS_CONTEXT_KEY)
                .anonymous(true)
                .set("hostOs", hostOs)
                .privateAttributes("hostOs")
                .build();
    }

    static com.launchdarkly.sdk.LDContext buildUserContext(String username) {
        return com.launchdarkly.sdk.LDContext.builder(username).build();
    }
}
