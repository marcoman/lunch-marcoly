#include "flags.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>
#include <vector>

#if defined(HAS_LAUNCHDARKLY)
extern "C" {
#include <launchdarkly/client.h>
}
#endif

namespace {

#if defined(HAS_LAUNCHDARKLY)
constexpr const char* kFlagHighlight = "configure-grid-selection-green-highlight";
constexpr const char* kFlagContext = "configure-grid-selection-context-highlight";
constexpr const char* kFlagCount = "show-navigation-move-count";
constexpr const char* kFlagOsEmoji = "show-host-os-emoji";
constexpr const char* kHostOsAttr = "hostOs";
LDClient* g_client = nullptr;
#endif

#ifndef EVALUATE_FLAGS_SCRIPT
#define EVALUATE_FLAGS_SCRIPT "evaluate_flags.py"
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
    std::cerr << "Warning: flag evaluation via Python failed — flags default to off.\n";
    if (output.find("ModuleNotFoundError") != std::string::npos ||
        output.find("ldclient") != std::string::npos) {
        std::cerr << "  Activate the repository .venv or set PYTHON to a Python with launchdarkly-server-sdk.\n";
    } else if (!output.empty()) {
        std::cerr << "  " << output.substr(0, output.find('\n')) << "\n";
    }
}

struct Cohorts {
    bool human = false;
    bool robot = false;
    bool beta = false;
};

std::string to_lower(const std::string& value) {
    std::string lower = value;
    std::transform(lower.begin(), lower.end(), lower.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return lower;
}

Cohorts parse_cohorts(const std::string& username) {
    const std::string lower = to_lower(username);
    return {lower.find("human") != std::string::npos,
            lower.find("robot") != std::string::npos,
            lower.find("beta") != std::string::npos};
}

std::string color_label_name(const std::string& highlight_color) {
    return highlight_color == "none" ? "no-color" : highlight_color;
}

std::string format_cohort_label(const std::string& username,
                                const std::string& highlight_color,
                                bool context_highlight) {
    const std::string color_name = color_label_name(highlight_color);
    std::vector<std::string> parts;
    if (context_highlight) {
        const Cohorts cohorts = parse_cohorts(username);
        if (cohorts.human) {
            parts.push_back("human");
        }
        if (cohorts.robot) {
            parts.push_back("robot");
        }
        if (cohorts.beta) {
            parts.push_back("beta");
        }
    }
    if (parts.empty()) {
        return "(" + color_name + ")";
    }
    std::string label = "(";
    for (size_t i = 0; i < parts.size(); ++i) {
        if (i > 0) {
            label += "-";
        }
        label += parts[i];
    }
    label += "-" + color_name + ")";
    return label;
}

std::string resolve_highlight_color(const std::string& username, bool highlight_enabled,
                                    bool context_highlight) {
    if (!highlight_enabled) {
        return "none";
    }
    if (!context_highlight) {
        return "pink";
    }
    const Cohorts cohorts = parse_cohorts(username);
    if (cohorts.human && cohorts.beta) {
        return "green";
    }
    if (cohorts.robot && cohorts.beta) {
        return "purple";
    }
    if (cohorts.human) {
        return "yellow";
    }
    if (cohorts.robot) {
        return "red";
    }
    if (cohorts.beta) {
        return "blue";
    }
    return "pink";
}

std::string detect_host_os() {
#if defined(__linux__)
    return "linux";
#elif defined(_WIN32)
    return "windows";
#elif defined(__APPLE__)
    return "macos";
#else
    return "other";
#endif
}

std::string os_emoji_for(const std::string& host_os, bool show_os_emoji) {
    if (!show_os_emoji) {
        return "";
    }
    if (host_os == "linux") {
        return "🐧";
    }
    if (host_os == "macos") {
        return "🍎";
    }
    if (host_os == "windows") {
        return "🪟";
    }
    return "😊";
}

FlagValues apply_highlight_style(const std::string& username, bool highlight_enabled,
                                 bool context_highlight, bool show_move_count,
                                 bool show_os_emoji, const std::string& host_os) {
    const std::string color = resolve_highlight_color(username, highlight_enabled, context_highlight);
    const std::string label = format_cohort_label(username, color, context_highlight);
    FlagValues values{highlight_enabled, context_highlight, show_move_count, color, label,
                      os_emoji_for(host_os, show_os_emoji)};
    return values;
}

FlagValues defaults(const std::string& username) {
    return apply_highlight_style(username, false, false, false, false, detect_host_os());
}

bool json_bool(const std::string& json, const std::string& key) {
    const std::string spaced = "\"" + key + "\": true";
    const std::string compact = "\"" + key + "\":true";
    return json.find(spaced) != std::string::npos ||
           json.find(compact) != std::string::npos;
}

int hex_digit(char ch) {
    if (ch >= '0' && ch <= '9') {
        return ch - '0';
    }
    if (ch >= 'a' && ch <= 'f') {
        return ch - 'a' + 10;
    }
    if (ch >= 'A' && ch <= 'F') {
        return ch - 'A' + 10;
    }
    return -1;
}

void append_utf8(std::string& out, char32_t code) {
    if (code <= 0x7F) {
        out.push_back(static_cast<char>(code));
    } else if (code <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | (code >> 6)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
    } else if (code <= 0xFFFF) {
        out.push_back(static_cast<char>(0xE0 | (code >> 12)));
        out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (code >> 18)));
        out.push_back(static_cast<char>(0x80 | ((code >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((code >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (code & 0x3F)));
    }
}

bool parse_json_unicode_escape(const std::string& raw, std::size_t& index, char32_t& code) {
    if (index + 5 >= raw.size() || raw[index] != '\\' || raw[index + 1] != 'u') {
        return false;
    }
    const int h1 = hex_digit(raw[index + 2]);
    const int h2 = hex_digit(raw[index + 3]);
    const int h3 = hex_digit(raw[index + 4]);
    const int h4 = hex_digit(raw[index + 5]);
    if (h1 < 0 || h2 < 0 || h3 < 0 || h4 < 0) {
        return false;
    }
    code = static_cast<char32_t>((h1 << 12) | (h2 << 8) | (h3 << 4) | h4);
    index += 5;

    if (code >= 0xD800 && code <= 0xDBFF && index + 6 < raw.size() &&
        raw[index + 1] == '\\' && raw[index + 2] == 'u') {
        const int l1 = hex_digit(raw[index + 3]);
        const int l2 = hex_digit(raw[index + 4]);
        const int l3 = hex_digit(raw[index + 5]);
        const int l4 = hex_digit(raw[index + 6]);
        if (l1 >= 0 && l2 >= 0 && l3 >= 0 && l4 >= 0) {
            const char32_t low =
                static_cast<char32_t>((l1 << 12) | (l2 << 8) | (l3 << 4) | l4);
            if (low >= 0xDC00 && low <= 0xDFFF) {
                code = 0x10000 + (((code - 0xD800) << 10) | (low - 0xDC00));
                index += 6;
            }
        }
    }
    return true;
}

std::string decode_json_string_value(const std::string& raw) {
    std::string out;
    out.reserve(raw.size());
    for (std::size_t i = 0; i < raw.size(); ++i) {
        if (raw[i] != '\\' || i + 1 >= raw.size()) {
            out.push_back(raw[i]);
            continue;
        }
        const char esc = raw[i + 1];
        if (esc == 'u') {
            char32_t code = 0;
            if (parse_json_unicode_escape(raw, i, code)) {
                append_utf8(out, code);
                continue;
            }
        }
        switch (esc) {
            case '"':
            case '\\':
            case '/':
                out.push_back(esc);
                i += 1;
                break;
            case 'b':
                out.push_back('\b');
                i += 1;
                break;
            case 'f':
                out.push_back('\f');
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
        return defaults(username);
    }
    std::string output;
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    pclose(pipe);
    if (!evaluation_output_valid(output)) {
        warn_evaluation_failure(output);
        return defaults(username);
    }
    FlagValues values;
    values.highlightEnabled = json_bool(output, "highlightEnabled");
    values.contextHighlight = json_bool(output, "contextHighlight");
    values.showMoveCount = json_bool(output, "showMoveCount");
    values.highlightColor = json_string(output, "highlightColor");
    values.cohortLabel = json_string(output, "cohortLabel");
    values.osEmoji = json_string(output, "osEmoji");
    if (values.highlightColor.empty()) {
        values.highlightColor = "none";
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
    const std::string host_os = detect_host_os();
    const std::string context_json =
        "{\"kind\":\"user\",\"key\":\"" + username +
        "\",\"hostOs\":\"" + host_os +
        "\",\"_meta\":{\"privateAttributes\":[\"hostOs\"]}}";
    LDJSON* context = LDNewContextFromString(context_json.c_str());
    if (context == nullptr) {
        return defaults(username);
    }
    const bool highlight =
        LDBoolVariation(g_client, kFlagHighlight, context, false);
    const bool context_highlight =
        LDBoolVariation(g_client, kFlagContext, context, false);
    const bool show_count = LDBoolVariation(g_client, kFlagCount, context, false);
    const bool show_os_emoji =
        LDBoolVariation(g_client, kFlagOsEmoji, context, false);
    LDJSONFree(context);
    return apply_highlight_style(
        username, highlight, context_highlight, show_count, show_os_emoji, host_os);
#else
    return evaluate_via_python(username);
#endif
}
