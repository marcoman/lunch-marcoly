#include "flags.hpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>

#ifndef SCHEDULED_FLAGS_SCRIPT
#define SCHEDULED_FLAGS_SCRIPT "scheduled_flags.py"
#endif

namespace {

std::string python_executable() {
    if (const char* venv = std::getenv("VIRTUAL_ENV")) return std::string(venv) + "/bin/python3";
    if (const char* python = std::getenv("PYTHON")) return python;
#ifdef DEFAULT_VENV_PYTHON
    if (access(DEFAULT_VENV_PYTHON, X_OK) == 0) return DEFAULT_VENV_PYTHON;
#endif
    return "python3";
}

std::string run_helper(const std::string& command, const std::string& argument = "") {
    std::ostringstream shell;
    shell << python_executable() << " \"" << SCHEDULED_FLAGS_SCRIPT << "\" " << command;
    if (!argument.empty()) {
        shell << ' ';
        for (char ch : argument) {
            if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') shell << ch;
        }
    }
    shell << " 2>&1";
    FILE* pipe = popen(shell.str().c_str(), "r");
    if (pipe == nullptr) return R"({"ok":false,"error":"could not start Python helper"})";
    std::string output;
    char buffer[512];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) output += buffer;
    pclose(pipe);
    return output;
}

std::string json_string(const std::string& json, const std::string& key) {
    const std::string marker = "\"" + key + "\":";
    auto start = json.find(marker);
    if (start == std::string::npos) return "";
    start = json.find('"', start + marker.size());
    if (start == std::string::npos) return "";
    const auto end = json.find('"', start + 1);
    return end == std::string::npos ? "" : json.substr(start + 1, end - start - 1);
}

std::int64_t json_int(const std::string& json, const std::string& key) {
    const std::string marker = "\"" + key + "\":";
    auto start = json.find(marker);
    if (start == std::string::npos) return 0;
    start += marker.size();
    while (start < json.size() && std::isspace(static_cast<unsigned char>(json[start]))) ++start;
    try { return std::stoll(json.substr(start)); } catch (...) { return 0; }
}

bool json_bool(const std::string& json, const std::string& key, bool fallback = false) {
    const std::string marker = "\"" + key + "\":";
    const auto start = json.find(marker);
    if (start == std::string::npos) return fallback;
    const auto value = json.find_first_not_of(" \t", start + marker.size());
    return value != std::string::npos && json.compare(value, 4, "true") == 0;
}

ScheduleState parse_state(const std::string& json) {
    ScheduleState state;
    state.ok = json_bool(json, "ok");
    state.configured = json_bool(json, "configured");
    state.pending = json_bool(json, "pending");
    state.startedAt = json_int(json, "startedAt");
    state.executionDate = json_int(json, "executionDate");
    state.stoppedAt = json_int(json, "stoppedAt");
    state.missing = json_string(json, "missing");
    state.error = json_string(json, "error");
    if (!state.ok && state.error.empty()) state.error = "Python helper failed";
    return state;
}

}  // namespace

void init_launchdarkly() {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — highlight defaults to none.\n";
    }
}

FlagValues evaluate_flags(const std::string& username) {
    const std::string json = run_helper("evaluate", username);
    FlagValues values;
    values.flagValue = json_string(json, "flagValue");
    values.reasonKind = json_string(json, "reasonKind");
    values.variationIndex = json_string(json, "variationIndex");
    if (values.flagValue != "green") values.flagValue = "none";
    if (values.reasonKind.empty()) values.reasonKind = "ERROR";
    if (values.variationIndex.empty()) values.variationIndex = "default";
    return values;
}

ScheduleState list_schedule() { return parse_state(run_helper("list")); }
ScheduleState start_schedule(int minutes) { return parse_state(run_helper("start", std::to_string(minutes))); }
ScheduleState stop_schedule() { return parse_state(run_helper("stop")); }
