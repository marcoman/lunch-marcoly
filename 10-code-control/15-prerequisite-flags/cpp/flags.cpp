#include "flags.hpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>

#ifndef EVALUATE_FLAGS_SCRIPT
#define EVALUATE_FLAGS_SCRIPT "evaluate_flags.py"
#endif

namespace {

std::string python_executable() {
    if (const char* venv = std::getenv("VIRTUAL_ENV")) {
        return std::string(venv) + "/bin/python3";
    }
    if (const char* py = std::getenv("PYTHON")) {
        return py;
    }
#ifdef DEFAULT_VENV_PYTHON
    if (access(DEFAULT_VENV_PYTHON, X_OK) == 0) {
        return DEFAULT_VENV_PYTHON;
    }
#endif
    return "python3";
}

bool evaluation_output_valid(const std::string& output) {
    return output.find('{') != std::string::npos &&
           output.find("Traceback") == std::string::npos &&
           output.find("ModuleNotFoundError") == std::string::npos;
}

void warn_evaluation_failure(const std::string& output) {
    static bool warned = false;
    if (warned) {
        return;
    }
    warned = true;
    std::cerr << "Warning: flag evaluation via Python failed — flags use safe defaults.\n";
    if (!output.empty()) {
        std::cerr << "  " << output.substr(0, output.find('\n')) << "\n";
    }
}

bool json_bool(const std::string& json, const std::string& key) {
    const std::string spaced = "\"" + key + "\": true";
    const std::string compact = "\"" + key + "\":true";
    return json.find(spaced) != std::string::npos || json.find(compact) != std::string::npos;
}

std::string json_string(const std::string& json, const std::string& key) {
    const std::string spaced_marker = "\"" + key + "\": \"";
    const std::string compact_marker = "\"" + key + "\":\"";
    std::size_t start = json.find(spaced_marker);
    std::size_t value_start = 0;
    if (start != std::string::npos) {
        value_start = start + spaced_marker.size();
    } else {
        start = json.find(compact_marker);
        if (start == std::string::npos) {
            return "";
        }
        value_start = start + compact_marker.size();
    }
    const auto end = json.find('"', value_start);
    if (end == std::string::npos) {
        return "";
    }
    return json.substr(value_start, end - value_start);
}

FlagValues defaults() {
    return {};
}

FlagValues evaluate_via_python(const std::string& username) {
    if (std::getenv("LD_SDK_KEY") == nullptr || username.empty()) {
        return defaults();
    }
    std::ostringstream cmd;
    cmd << python_executable() << " \"" << EVALUATE_FLAGS_SCRIPT << "\" ";
    for (char ch : username) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') {
            cmd << ch;
        }
    }
    cmd << " 2>&1";
    FILE* pipe = popen(cmd.str().c_str(), "r");
    if (pipe == nullptr) {
        warn_evaluation_failure("");
        return defaults();
    }
    std::string output;
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    pclose(pipe);
    if (!evaluation_output_valid(output)) {
        warn_evaluation_failure(output);
        return defaults();
    }
    FlagValues values;
    values.showMoveCount = json_bool(output, "showMoveCount");
    values.childValue = values.showMoveCount;
    values.highlightColor = json_string(output, "highlightColor");
    values.parentValue = json_string(output, "parentValue");
    values.parentReason = json_string(output, "parentReason");
    values.childReason = json_string(output, "childReason");
    if (values.highlightColor.empty()) {
        values.highlightColor = "none";
    }
    if (values.parentValue.empty()) {
        values.parentValue = "none";
    }
    if (values.parentReason.empty()) {
        values.parentReason = "UNKNOWN";
    }
    if (values.childReason.empty()) {
        values.childReason = "UNKNOWN";
    }
    const std::string prerequisite_key = json_string(output, "prerequisiteKey");
    if (!prerequisite_key.empty()) {
        values.childReason += " (" + prerequisite_key + ")";
    }
    return values;
}

}  // namespace

void init_launchdarkly() {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — flags use safe defaults.\n";
    }
}

void close_launchdarkly() {}

FlagValues evaluate_flags(const std::string& username) {
    return evaluate_via_python(username);
}
