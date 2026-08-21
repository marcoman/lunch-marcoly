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
    if (const char* python = std::getenv("PYTHON")) {
        return python;
    }
#ifdef DEFAULT_VENV_PYTHON
    if (access(DEFAULT_VENV_PYTHON, X_OK) == 0) {
        return DEFAULT_VENV_PYTHON;
    }
#endif
    return "python3";
}

std::string safe_argument(const std::string& value) {
    std::string safe;
    for (char ch : value) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') {
            safe += ch;
        }
    }
    return safe;
}

std::string json_string(const std::string& json, const std::string& key) {
    const std::string spaced = "\"" + key + "\": \"";
    const std::string compact = "\"" + key + "\":\"";
    std::size_t start = json.find(spaced);
    std::size_t value_start;
    if (start != std::string::npos) {
        value_start = start + spaced.size();
    } else {
        start = json.find(compact);
        if (start == std::string::npos) {
            return "";
        }
        value_start = start + compact.size();
    }
    const std::size_t end = json.find('"', value_start);
    return end == std::string::npos ? "" : json.substr(value_start, end - value_start);
}

FlagValues defaults(const std::string& team) {
    FlagValues values;
    if (team == "red") {
        values.teamLabel = "Team Red";
    } else if (team == "blue") {
        values.teamLabel = "Team Blue";
    } else if (team == "yellow") {
        values.teamLabel = "Team Yellow";
    }
    return values;
}

void warn_evaluation_failure(const std::string& output) {
    static bool warned = false;
    if (warned) {
        return;
    }
    warned = true;
    std::cerr << "Warning: flag evaluation via Python failed — flag uses plain default.\n";
    if (output.find("ModuleNotFoundError") != std::string::npos ||
        output.find("ldclient") != std::string::npos) {
        std::cerr << "  Activate the repository .venv or set PYTHON to a Python with launchdarkly-server-sdk.\n";
    }
}

}  // namespace

void init_launchdarkly() {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — flag uses plain default.\n";
    }
}

void close_launchdarkly() {
}

// Delegate evaluation to the shared Python helper so No team omits the
// attribute and selected teams remain public context attributes.
// https://launchdarkly.com/docs/home/flags/context-attributes
FlagValues evaluate_flags(const std::string& username, const std::string& team) {
    FlagValues fallback = defaults(team);
    if (std::getenv("LD_SDK_KEY") == nullptr || username.empty()) {
        return fallback;
    }

    std::ostringstream command;
    command << '"' << python_executable() << "\" \"" << EVALUATE_FLAGS_SCRIPT << "\" "
            << safe_argument(username) << ' ' << safe_argument(team) << " 2>&1";
    FILE* pipe = popen(command.str().c_str(), "r");
    if (pipe == nullptr) {
        warn_evaluation_failure("");
        return fallback;
    }
    std::string output;
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    const int status = pclose(pipe);
    if (status != 0 || output.find('{') == std::string::npos ||
        output.find("Traceback") != std::string::npos) {
        warn_evaluation_failure(output);
        return fallback;
    }

    FlagValues values;
    values.teamLabel = json_string(output, "teamLabel");
    values.style = json_string(output, "style");
    if (values.teamLabel.empty()) {
        values.teamLabel = fallback.teamLabel;
    }
    if (values.style != "plain" && values.style != "colored-red" &&
        values.style != "colored-blue" && values.style != "colored-yellow") {
        values.style = "plain";
    }
    return values;
}
