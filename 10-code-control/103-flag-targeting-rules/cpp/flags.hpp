#pragma once

#include <string>

// LaunchDarkly targeting rules evaluate the public team context attribute.
// https://launchdarkly.com/docs/home/flags/target-rules
struct FlagValues {
    std::string teamLabel = "No team";
    std::string style = "plain";
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username, const std::string& team);
