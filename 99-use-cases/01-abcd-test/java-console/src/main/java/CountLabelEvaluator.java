import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;

/**
 * LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
 */
public final class CountLabelEvaluator {
    private static final String FLAG_COUNT_LABEL = "configure-navigation-count-label";
    private static final String DEFAULT_COUNT_LABEL = "Count";

    private static LDClient client;

    private CountLabelEvaluator() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flag defaults to off.");
            return;
        }
        LDConfig config = new LDConfig.Builder().build();
        client = new LDClient(sdkKey, config);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flag defaults to off.");
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

    static String evaluate(String username) {
        if (client == null || username == null || username.isBlank()) {
            return DEFAULT_COUNT_LABEL;
        }
        LDContext userContext = LDContext.builder(username).build();
        String countLabel = client.stringVariation(FLAG_COUNT_LABEL, userContext, DEFAULT_COUNT_LABEL);
        return countLabel == null || countLabel.isBlank() ? DEFAULT_COUNT_LABEL : countLabel;
    }
}
