import com.launchdarkly.sdk.LDContext;
import com.launchdarkly.sdk.LDValue;
import com.launchdarkly.sdk.server.LDClient;
import com.launchdarkly.sdk.server.LDConfig;

import java.io.IOException;

/**
 * LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
 * See: https://launchdarkly.com/docs/sdk/features/flag-types
 * See: https://launchdarkly.com/docs/sdk/features/anonymous
 */
public final class FlagEvaluator {
    private static final String FLAG_COUNT_LABEL = "configure-navigation-count-label";
    private static final String FLAG_LUCKY_NUMBER = "configure-lucky-number";
    private static final String FLAG_MAX_MOVES = "configure-max-navigation-moves";
    private static final String DEFAULT_COUNT_LABEL = "Count";
    private static final int DEFAULT_LUCKY_NUMBER = 0;
    private static final int DEFAULT_MAX_MOVES = 100;

    private static final String HOST_OS = HostOs.detectHostOs();
    private static LDClient client;

    private FlagEvaluator() {
    }

    static synchronized void init() {
        if (client != null) {
            return;
        }
        String sdkKey = System.getenv("LD_SDK_KEY");
        if (sdkKey == null || sdkKey.isBlank()) {
            System.err.println("Warning: LD_SDK_KEY not set — flags use defaults.");
            return;
        }
        LDConfig config = new LDConfig.Builder()
                .events(com.launchdarkly.sdk.server.Components.sendEvents()
                        .privateAttributes(HostOs.HOST_OS_ATTR))
                .build();
        client = new LDClient(sdkKey, config);
        if (!client.isInitialized()) {
            System.err.println("Warning: LaunchDarkly SDK did not initialize — flags use defaults.");
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
        if (client == null || username == null || username.isBlank()) {
            return FlagValues.defaults();
        }
        LDContext anonContext = HostOs.buildAnonymousContext(HOST_OS);
        LDContext userContext = HostOs.buildUserContext(username);

        boolean showEmoji = client.boolVariation(HostOs.FLAG_ANON_OS_EMOJI, anonContext, false);
        String countLabel = client.stringVariation(FLAG_COUNT_LABEL, userContext, DEFAULT_COUNT_LABEL);
        int luckyNumber = client.intVariation(FLAG_LUCKY_NUMBER, userContext, DEFAULT_LUCKY_NUMBER);
        LDValue maxMovesRaw = client.jsonValueVariation(
                FLAG_MAX_MOVES,
                userContext,
                LDValue.buildObject().put("maxMoves", DEFAULT_MAX_MOVES).build());
        int maxMoves = parseMaxMoves(maxMovesRaw);
        String osEmoji = HostOs.osEmojiFor(HOST_OS, showEmoji);

        return new FlagValues(
                countLabel == null || countLabel.isBlank() ? DEFAULT_COUNT_LABEL : countLabel,
                luckyNumber,
                maxMoves,
                osEmoji);
    }

    private static int parseMaxMoves(LDValue raw) {
        if (raw == null || raw.isNull()) {
            return DEFAULT_MAX_MOVES;
        }
        return raw.get("maxMoves").intValue();
    }

    record FlagValues(String countLabel, int luckyNumber, int maxMoves, String osEmoji) {
        static FlagValues defaults() {
            return new FlagValues(DEFAULT_COUNT_LABEL, DEFAULT_LUCKY_NUMBER, DEFAULT_MAX_MOVES, "");
        }

        String toJson() {
            return "{\"countLabel\":\"" + escapeJson(countLabel) + "\""
                    + ",\"luckyNumber\":" + luckyNumber
                    + ",\"maxMoves\":" + maxMoves
                    + ",\"osEmoji\":\"" + escapeJson(osEmoji) + "\"}";
        }

        private static String escapeJson(String value) {
            if (value == null) {
                return "";
            }
            return value.replace("\\", "\\\\").replace("\"", "\\\"");
        }
    }
}
