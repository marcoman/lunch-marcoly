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

bool json_bool(const std::string& json, const std::string& key) {
    const std::string spaced_true = "\"" + key + "\": true";
    const std::string compact_true = "\"" + key + "\":true";
    return json.find(spaced_true) != std::string::npos ||
           json.find(compact_true) != std::string::npos;
}

FlagValues defaults(const std::string& username, const std::string& org) {
    FlagValues values;
    values.username = username;
    values.org = org;
    values.orgLabel = org == "globex" ? "Globex" : "Acme";
    values.partner = false;
    return values;
}

void warn_evaluation_failure(const std::string& output) {
    static bool warned = false;
    if (warned) {
        return;
    }
    warned = true;
    std::cerr << "Warning: flag evaluation via Python failed — partner badge stays false.\n";
    if (output.find("ModuleNotFoundError") != std::string::npos ||
        output.find("ldclient") != std::string::npos) {
        std::cerr << "  Activate the repository .venv or set PYTHON to a Python with launchdarkly-server-sdk.\n";
    }
}

}  // namespace

void init_launchdarkly() {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — partner badge stays false.\n";
    }
}

void close_launchdarkly() {
}

// Delegate evaluation to the shared Python helper so C++ uses the same
// user + organization multi-context as the Python lab.
// https://launchdarkly.com/docs/home/flags/multi-contexts
FlagValues evaluate_flags(const std::string& username, const std::string& org) {
    FlagValues fallback = defaults(username, org);
    if (std::getenv("LD_SDK_KEY") == nullptr || username.empty()) {
        return fallback;
    }

    std::ostringstream command;
    command << '"' << python_executable() << "\" \"" << EVALUATE_FLAGS_SCRIPT << "\" "
            << safe_argument(username) << ' ' << safe_argument(org) << " 2>&1";
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

    FlagValues values = fallback;
    const std::string parsed_user = json_string(output, "username");
    const std::string parsed_org = json_string(output, "org");
    const std::string parsed_label = json_string(output, "orgLabel");
    if (!parsed_user.empty()) values.username = parsed_user;
    if (!parsed_org.empty()) values.org = parsed_org;
    if (!parsed_label.empty()) values.orgLabel = parsed_label;
    values.partner = json_bool(output, "partner");
    return values;
}
