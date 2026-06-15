#pragma once

#include <string>

// LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/evaluating

struct FlagValues {
    bool highlightEnabled = false;
    bool contextHighlight = false;
    bool showMoveCount = false;
    std::string highlightColor = "none";
    std::string cohortLabel;
    std::string osEmoji;
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
