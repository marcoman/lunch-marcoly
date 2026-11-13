#pragma once

#include <string>

// LaunchDarkly: evaluate parent and child independently.
// https://launchdarkly.com/docs/home/flags/prereqs

struct FlagValues {
    bool showMoveCount = false;
    bool showHostEmoji = false;
    std::string hostEmoji;
    std::string highlightColor = "none";
    std::string parentValue = "none";
    std::string parentReason = "OFFLINE";
    bool childValue = false;
    std::string childReason = "OFFLINE";
    bool emojiValue = false;
    std::string emojiReason = "OFFLINE";
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
