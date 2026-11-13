#pragma once

#include <string>

// LaunchDarkly capability: Multivariate flag evaluation (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/flag-types

struct FlagValues {
    std::string countLabel = "Count";
    int luckyNumber = 0;
    int maxMoves = 100;
    std::string osEmoji;
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
