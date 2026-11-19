import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

/** Read the move-count flag. The default is hidden.
 *
 * LaunchDarkly: server-side Java SDK · boolean variation
 * https://launchdarkly.com/docs/sdk/server-side/java
 * https://launchdarkly.com/docs/home/flags/boolean
 */
final class FlagCount {
    static final String FLAG_KEY = "show-navigation-move-count-approval";
    private static LDClient client;

    private FlagCount() {
    }

    static synchronized void init() {
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — the count stays hidden.");
            return;
        }
        client = new LDClient(sdkKey.trim());
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize.");
        }
    }

    static synchronized void close() {
        if (client == null) return;
        try {
            client.close();
        } catch (IOException ignored) {
        }
        client = null;
    }

    static Map<String, Object> evaluate(String rawUsername) {
        String username = rawUsername == null ? "" : rawUsername.trim();
        if (username.isEmpty()) throw new IllegalArgumentException("Username is required");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("username", username);
        result.put("flagKey", FLAG_KEY);
        if (client == null || !client.isInitialized()) {
            result.put("showMoveCount", false);
            result.put("reason", "DEFAULT");
            result.put("sdk", false);
            return result;
        }
        LDContext context = LDContext.builder(username).kind("user").name(username).build();
        var detail = client.boolVariationDetail(FLAG_KEY, context, false);
        result.put("showMoveCount", Boolean.TRUE.equals(detail.getValue()));
        result.put("reason", detail.getReason().getKind().name());
        result.put("sdk", true);
        return result;
    }
}
