#pragma once

#include <string>

struct FlagValues {
    std::string username;
    std::string flagValue = "none";
    std::string highlightColor = "none";
    std::string colorLabel = "(no-color)";
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
