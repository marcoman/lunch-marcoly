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
constexpr const char* kFlagHighlight = "configure-grid-selection-green-highlight";
LDClient* g_client = nullptr;
#endif

#ifndef EVALUATE_HIGHLIGHT_SCRIPT
#define EVALUATE_HIGHLIGHT_SCRIPT "evaluate_highlight.py"
#endif

struct SegmentInfo {
    std::string segmentType;
    std::string namedColor;
};

int letter_count(const std::string& username) {
    int count = 0;
    for (unsigned char ch : username) {
        if (std::isalpha(ch)) {
            count += 1;
        }
    }
    return count;
}

bool is_color_name(const std::string& lower) {
    return lower == "yellow" || lower == "red" || lower == "blue" || lower == "green" ||
           lower == "purple";
}

SegmentInfo resolve_segment_info(const std::string& username) {
    std::string lower = username;
    for (char& ch : lower) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }

    if (lower == "generic") {
        return {"generic", ""};
    }
    if (is_color_name(lower)) {
        return {"named-color", lower};
    }

    const bool is_human = letter_count(username) % 2 == 0;
    const bool is_beta = lower.find("beta") != std::string::npos;

    if (is_human && is_beta) {
        return {"human-beta", ""};
    }
    if (is_human) {
        return {"human", ""};
    }
    if (is_beta) {
        return {"robot-beta", ""};
    }
    return {"robot", ""};
}

std::string escape_json(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    for (char ch : value) {
        if (ch == '\\' || ch == '"') {
            out.push_back('\\');
        }
        out.push_back(ch);
    }
    return out;
}

std::string build_context_json(const std::string& username, const SegmentInfo& info) {
    std::ostringstream json;
    json << "{\"kind\":\"user\",\"key\":\"" << escape_json(username) << "\",\"segmentType\":\""
         << escape_json(info.segmentType) << "\"";

    if (info.segmentType == "generic") {
        json << ",\"generic\":true";
    } else if (info.segmentType == "named-color") {
        json << ",\"namedColor\":\"" << escape_json(info.namedColor) << "\"";
    } else {
        const std::string user_kind = info.segmentType.rfind("human", 0) == 0 ? "human" : "robot";
        const bool beta = info.segmentType.size() >= 5 &&
                          info.segmentType.compare(info.segmentType.size() - 5, 5, "-beta") == 0;
        json << ",\"userKind\":\"" << user_kind << "\",\"beta\":" << (beta ? "true" : "false");
    }

    json << "}";
    return json.str();
}

std::string color_label_name(const std::string& highlight_color) {
    return highlight_color == "none" ? "no-color" : highlight_color;
}

std::string normalize_highlight_color(const std::string& raw) {
    std::string color = raw;
    for (char& ch : color) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    if (is_color_name(color)) {
        return color;
    }
    return "none";
}

std::string format_segment_label(const SegmentInfo& info, const std::string& highlight_color) {
    const std::string color_name = color_label_name(highlight_color);
    if (info.segmentType == "generic") {
        return "(generic)";
    }
    if (info.segmentType == "named-color") {
        return "(" + color_name + ")";
    }
    if (info.segmentType == "human" || info.segmentType == "robot" ||
        info.segmentType == "human-beta" || info.segmentType == "robot-beta") {
        return "(" + info.segmentType + "-" + color_name + ")";
    }
    return "(" + color_name + ")";
}

FlagValues build_response(const std::string& highlight_color, const SegmentInfo& info) {
    const std::string color = normalize_highlight_color(highlight_color);
    FlagValues values;
    values.highlightColor = color;
    values.segmentLabel = format_segment_label(info, color);
    values.segmentType = info.segmentType;
    return values;
}

FlagValues defaults(const std::string& username) {
    return build_response("none", resolve_segment_info(username));
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
    std::cerr << "Warning: flag evaluation via Python failed — flags default to off.\n";
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
            case 'n':
                out.push_back('\n');
                i += 1;
                break;
            case 'r':
                out.push_back('\r');
                i += 1;
                break;
            case 't':
                out.push_back('\t');
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
    values.highlightColor = json_string(output, "highlightColor");
    values.segmentLabel = json_string(output, "segmentLabel");
    values.segmentType = json_string(output, "segmentType");
    if (values.highlightColor.empty()) {
        values.highlightColor = "none";
    }
    if (values.segmentType.empty()) {
        return defaults(username);
    }
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
        return defaults(username);
    }
    const SegmentInfo info = resolve_segment_info(username);
    const std::string context_json = build_context_json(username, info);
    LDJSON* context = LDNewContextFromString(context_json.c_str());
    if (context == nullptr) {
        return defaults(username);
    }
    const char* raw = LDStringVariation(g_client, kFlagHighlight, context, "none");
    LDJSONFree(context);
    return build_response(raw != nullptr ? raw : "none", info);
#else
    return evaluate_via_python(username);
#endif
}
