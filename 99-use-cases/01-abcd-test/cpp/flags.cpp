#include "flags.hpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>

#if defined(HAS_LAUNCHDARKLY)
extern "C" {
#include <launchdarkly/client.h>
}
#endif

namespace {

#if defined(HAS_LAUNCHDARKLY)
constexpr const char* kFlagCountLabel = "configure-navigation-count-label";
LDClient* g_client = nullptr;
#endif

#ifndef EVALUATE_LABEL_SCRIPT
#define EVALUATE_LABEL_SCRIPT "evaluate_label.py"
#endif

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

FlagValues defaults() {
    return FlagValues{};
}

void warn_evaluation_failure(const std::string& output) {
    static bool warned = false;
    if (warned) {
        return;
    }
    warned = true;
    std::cerr << "Warning: flag evaluation via Python failed — flags default to off.\n";
    if (output.find("ModuleNotFoundError") != std::string::npos ||
        output.find("ldclient") != std::string::npos) {
        std::cerr << "  Activate the repository .venv or set PYTHON to a Python with launchdarkly-server-sdk.\n";
    } else if (!output.empty()) {
        std::cerr << "  " << output.substr(0, output.find('\n')) << "\n";
    }
}

#if !defined(HAS_LAUNCHDARKLY)
FlagValues evaluate_via_python(const std::string& username) {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        return defaults();
    }
    std::ostringstream cmd;
    cmd << python_executable() << " \"" << EVALUATE_LABEL_SCRIPT << "\" ";
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
    if (output.find("Traceback") != std::string::npos ||
        output.find("ModuleNotFoundError") != std::string::npos) {
        warn_evaluation_failure(output);
        return defaults();
    }
    while (!output.empty() && (output.back() == '\n' || output.back() == '\r')) {
        output.pop_back();
    }
    FlagValues values;
    values.countLabel = output.empty() ? "Count" : output;
    return values;
}
#endif

}  // namespace

void init_launchdarkly() {
#if defined(HAS_LAUNCHDARKLY)
    const char* sdk_key = std::getenv("LD_SDK_KEY");
    if (sdk_key == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — flags default to off.\n";
        return;
    }
    g_client = LDClientInitFromSDKKey(sdk_key, 5000, nullptr);
    if (g_client == nullptr) {
        std::cerr << "Warning: LaunchDarkly SDK did not initialize — flags default to off.\n";
    }
#else
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — flags default to off.\n";
    }
#endif
}

void close_launchdarkly() {
#if defined(HAS_LAUNCHDARKLY)
    if (g_client != nullptr) {
        LDClientClose(g_client);
        g_client = nullptr;
    }
#endif
}

FlagValues evaluate_flags(const std::string& username) {
#if defined(HAS_LAUNCHDARKLY)
    if (g_client == nullptr || username.empty()) {
        return defaults();
    }
    const std::string user_context_json =
        "{\"kind\":\"user\",\"key\":\"" + username + "\"}";
    LDJSON* user_context = LDNewContextFromString(user_context_json.c_str());
    if (user_context == nullptr) {
        return defaults();
    }
    const char* count_label =
        LDStringVariation(g_client, kFlagCountLabel, user_context, "Count");
    FlagValues values;
    values.countLabel = count_label != nullptr ? count_label : "Count";
    LDJSONFree(user_context);
    return values;
#else
    return evaluate_via_python(username);
#endif
}
