#pragma once

#include <string>

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

struct FlagValues {
    std::string highlightColor = "none";
    std::string segmentLabel;
    std::string segmentType;
    bool vip = false;
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
