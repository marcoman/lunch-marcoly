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
constexpr const char* kFlagAnonOsEmoji = "show-anonymous-host-os-emoji";
constexpr const char* kFlagCountLabel = "configure-navigation-count-label";
constexpr const char* kFlagLuckyNumber = "configure-lucky-number";
constexpr const char* kFlagMaxMoves = "configure-max-navigation-moves";
constexpr const char* kHostOsAttr = "hostOs";
constexpr const char* kAnonymousKey = "anonymous";
constexpr int kDefaultMaxMoves = 100;
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

#if defined(HAS_LAUNCHDARKLY)
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
#endif

FlagValues defaults() {
    return FlagValues{};
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

int json_int(const std::string& json, const std::string& key, int fallback) {
    const std::string spaced = "\"" + key + "\": ";
    const std::string compact = "\"" + key + "\":";
    std::size_t start = json.find(spaced);
    std::size_t value_start = 0;
    if (start != std::string::npos) {
        value_start = start + spaced.size();
    } else {
        start = json.find(compact);
        if (start == std::string::npos) {
            return fallback;
        }
        value_start = start + compact.size();
    }
    while (value_start < json.size() && std::isspace(static_cast<unsigned char>(json[value_start]))) {
        value_start++;
    }
    std::size_t end = value_start;
    while (end < json.size() && (std::isdigit(static_cast<unsigned char>(json[end])) || json[end] == '-')) {
        end++;
    }
    if (end == value_start) {
        return fallback;
    }
    try {
        return std::stoi(json.substr(value_start, end - value_start));
    } catch (...) {
        return fallback;
    }
}

#if !defined(HAS_LAUNCHDARKLY)
FlagValues evaluate_via_python(const std::string& username) {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
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
    values.countLabel = json_string(output, "countLabel");
    values.luckyNumber = json_int(output, "luckyNumber", 0);
    values.maxMoves = json_int(output, "maxMoves", 100);
    values.osEmoji = json_string(output, "osEmoji");
    if (values.countLabel.empty()) {
        values.countLabel = "Count";
    }
    return values;
}
#endif

#if defined(HAS_LAUNCHDARKLY)
int parse_max_moves_from_json(LDJSON* value) {
    if (value == nullptr) {
        return kDefaultMaxMoves;
    }
    LDJSON* max_moves = LDObjectLookup(value, "maxMoves");
    if (max_moves == nullptr) {
        return kDefaultMaxMoves;
    }
    return static_cast<int>(LDJSONGetNumber(max_moves));
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
    const std::string host_os = detect_host_os();
    const std::string anon_context_json =
        "{\"kind\":\"user\",\"key\":\"" + std::string(kAnonymousKey) +
        "\",\"anonymous\":true,\"hostOs\":\"" + host_os +
        "\",\"_meta\":{\"privateAttributes\":[\"hostOs\"]}}";
    const std::string user_context_json =
        "{\"kind\":\"user\",\"key\":\"" + username + "\"}";

    LDJSON* anon_context = LDNewContextFromString(anon_context_json.c_str());
    LDJSON* user_context = LDNewContextFromString(user_context_json.c_str());
    if (anon_context == nullptr || user_context == nullptr) {
        if (anon_context != nullptr) {
            LDJSONFree(anon_context);
        }
        if (user_context != nullptr) {
            LDJSONFree(user_context);
        }
        return defaults();
    }

    const bool show_emoji =
        LDBoolVariation(g_client, kFlagAnonOsEmoji, anon_context, false);
    const char* count_label =
        LDStringVariation(g_client, kFlagCountLabel, user_context, "Count");
    const int lucky_number =
        LDIntVariation(g_client, kFlagLuckyNumber, user_context, 0);
    LDJSON* max_moves_json = LDJSONVariation(
        g_client, kFlagMaxMoves, user_context,
        LDNewObjectFromString("{\"maxMoves\":100}"));
    const int max_moves = parse_max_moves_from_json(max_moves_json);

    FlagValues values;
    values.countLabel = count_label != nullptr ? count_label : "Count";
    values.luckyNumber = lucky_number;
    values.maxMoves = max_moves;
    values.osEmoji = os_emoji_for(host_os, show_emoji);

    LDJSONFree(anon_context);
    LDJSONFree(user_context);
    if (max_moves_json != nullptr) {
        LDJSONFree(max_moves_json);
    }
    return values;
#else
    return evaluate_via_python(username);
#endif
}
