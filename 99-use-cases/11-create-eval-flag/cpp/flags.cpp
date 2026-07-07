#include "flags.hpp"

#include <cctype>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <unistd.h>

#if defined(HAS_LAUNCHDARKLY)
extern "C" {
#include <launchdarkly/client.h>
}
#endif

namespace {

#if defined(HAS_LAUNCHDARKLY)
constexpr const char* kFlagHighlight = "configure-grid-selection-green-highlight";
LDClient* g_client = nullptr;
#endif

#ifndef EVALUATE_HIGHLIGHT_SCRIPT
#define EVALUATE_HIGHLIGHT_SCRIPT "evaluate_highlight.py"
#endif

FlagValues defaults(const std::string& username) {
    FlagValues values;
    values.username = username;
    return values;
}

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

void warn_evaluation_failure(const std::string& output) {
    static bool warned = false;
    if (warned) {
        return;
    }
    warned = true;
    std::cerr << "Warning: flag evaluation via Python failed — highlight defaults to none.\n";
    if (output.find("ModuleNotFoundError") != std::string::npos ||
        output.find("ldclient") != std::string::npos) {
        std::cerr << "  Activate the repository .venv or set PYTHON to a Python with launchdarkly-server-sdk.\n";
    } else if (!output.empty()) {
        std::cerr << "  " << output.substr(0, output.find('\n')) << "\n";
    }
}

std::string decode_json_string_value(const std::string& raw) {
    std::string out;
    out.reserve(raw.size());
    for (std::size_t i = 0; i < raw.size(); ++i) {
        if (raw[i] != '\\') {
            out.push_back(raw[i]);
            continue;
        }
        if (i + 1 >= raw.size()) {
            break;
        }
        switch (raw[i + 1]) {
            case '"':
                out.push_back('"');
                i += 1;
                break;
            case '\\':
                out.push_back('\\');
                i += 1;
                break;
            default:
                out.push_back(raw[i]);
                break;
        }
    }
    return out;
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
    return decode_json_string_value(json.substr(value_start, end - value_start));
}

#if !defined(HAS_LAUNCHDARKLY)
FlagValues evaluate_via_python(const std::string& username) {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        return defaults(username);
    }
    std::ostringstream cmd;
    cmd << python_executable() << " \"" << EVALUATE_HIGHLIGHT_SCRIPT << "\" ";
    for (char ch : username) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') {
            cmd << ch;
        }
    }
    cmd << " 2>&1";
    FILE* pipe = popen(cmd.str().c_str(), "r");
    if (pipe == nullptr) {
        warn_evaluation_failure("");
        return defaults(username);
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
        return defaults(username);
    }
    FlagValues values;
    values.username = json_string(output, "username");
    values.flagValue = json_string(output, "flagValue");
    values.highlightColor = json_string(output, "highlightColor");
    values.colorLabel = json_string(output, "colorLabel");
    if (values.username.empty()) {
        values.username = username;
    }
    if (values.highlightColor.empty()) {
        values.highlightColor = "none";
    }
    if (values.flagValue.empty()) {
        values.flagValue = "none";
    }
    if (values.colorLabel.empty()) {
        values.colorLabel = "(no-color)";
    }
    return values;
}
#endif

}  // namespace

void init_launchdarkly() {
#if defined(HAS_LAUNCHDARKLY)
    const char* sdk_key = std::getenv("LD_SDK_KEY");
    if (sdk_key == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — highlight defaults to none.\n";
        return;
    }
    g_client = LDClientInitFromSDKKey(sdk_key, 10000, nullptr);
    if (g_client == nullptr) {
        std::cerr << "Warning: LaunchDarkly SDK did not initialize — highlight defaults to none.\n";
    }
#else
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        std::cerr << "Warning: LD_SDK_KEY not set — highlight defaults to none.\n";
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
        return defaults(username);
    }
    const std::string context_json = "{\"kind\":\"user\",\"key\":\"" + username + "\"}";
    LDJSON* context = LDNewContextFromString(context_json.c_str());
    if (context == nullptr) {
        return defaults(username);
    }
    const char* raw = LDStringVariation(g_client, kFlagHighlight, context, "none");
    LDJSONFree(context);
    FlagValues values;
    values.username = username;
    values.flagValue = raw != nullptr ? raw : "none";
    values.highlightColor = values.flagValue;
    if (values.highlightColor != "yellow" && values.highlightColor != "red" &&
        values.highlightColor != "blue" && values.highlightColor != "green" &&
        values.highlightColor != "purple") {
        values.highlightColor = "none";
    }
    values.colorLabel =
        values.highlightColor == "none" ? "(no-color)" : "(" + values.highlightColor + ")";
    return values;
#else
    return evaluate_via_python(username);
#endif
}
