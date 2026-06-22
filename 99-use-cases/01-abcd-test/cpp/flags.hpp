#pragma once

#include <string>

// LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
// See: https://launchdarkly.com/docs/sdk/features/flag-types

struct FlagValues {
    std::string countLabel = "Count";
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
