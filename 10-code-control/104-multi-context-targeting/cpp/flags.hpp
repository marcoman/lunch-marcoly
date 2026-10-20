#pragma once

#include <string>

// LaunchDarkly multi-context evaluation: user + organization.
// https://launchdarkly.com/docs/home/flags/multi-contexts
struct FlagValues {
    std::string username;
    std::string org;
    std::string orgLabel = "Acme";
    bool partner = false;
};

void init_launchdarkly();
void close_launchdarkly();
FlagValues evaluate_flags(const std::string& username, const std::string& org);
