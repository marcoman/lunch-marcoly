#pragma once

#include <cstdint>
#include <string>

// LaunchDarkly: scheduled changes are controlled by REST and observed by SDK evaluation.
// https://launchdarkly.com/docs/home/flags/scheduled-changes

struct FlagValues {
    std::string flagValue = "none";
    std::string reasonKind = "ERROR";
    std::string variationIndex = "default";
};

struct ScheduleState {
    bool ok = true;
    bool configured = false;
    bool pending = false;
    std::int64_t startedAt = 0;
    std::int64_t executionDate = 0;
    std::int64_t stoppedAt = 0;
    std::string missing;
    std::string error;
};

void init_launchdarkly();
FlagValues evaluate_flags(const std::string& username);
ScheduleState list_schedule();
ScheduleState start_schedule(int minutes);
ScheduleState stop_schedule();
