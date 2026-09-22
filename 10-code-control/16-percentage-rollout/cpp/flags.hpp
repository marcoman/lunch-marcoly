#pragma once

#include <string>

// LaunchDarkly: percentage rollout — sticky assignment by context key.
// https://launchdarkly.com/docs/home/flags/rollouts

struct FlagValues {
    std::string flagValue = "none";
    std::string highlightColor = "none";
    std::string reasonKind = "ERROR";
    std::string variationIndex = "default";
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
