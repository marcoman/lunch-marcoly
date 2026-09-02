import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;

import java.io.IOException;
import java.util.Map;

/**
 * Evaluate show-partner-org-badge with a user + organization multi-context.
 * https://launchdarkly.com/docs/home/flags/multi-contexts
 */
public final class FlagEvaluator {
    static final String FLAG_KEY = "show-partner-org-badge";
    private static final Map<String, String> ORG_LABELS = Map.of(
            "acme", "Acme",
            "globex", "Globex");
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) return;
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — partner badge stays false.");
            return;
        }
        client = new LDClient(sdkKey);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — partner badge stays false.");
            close();
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

    /**
     * Build user + organization multi-context. Do not put org on the user.
     * https://launchdarkly.com/docs/sdk/features/user-context
     */
    static PartnerFlags evaluate(String username, String org) {
        String userKey = username.trim().toLowerCase();
        String orgKey = org.trim().toLowerCase();
        String orgLabel = ORG_LABELS.getOrDefault(orgKey, orgKey);
        LDContext user = LDContext.builder(userKey).kind("user").build();
        LDContext organization = LDContext.builder(orgKey)
                .kind("organization")
                .set("name", orgLabel)
                .build();
        LDContext context = LDContext.createMulti(user, organization);
        boolean partner = client != null && client.boolVariation(FLAG_KEY, context, false);
        return new PartnerFlags(userKey, orgKey, orgLabel, partner);
    }

    record PartnerFlags(String username, String org, String orgLabel, boolean partner) {
    }
}
