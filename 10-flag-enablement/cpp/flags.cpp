#include "flags.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
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
LDClient* g_client = nullptr;
#endif

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

FlagValues apply_highlight_style(const std::string& username, bool highlight_enabled,
                                 bool context_highlight, bool show_move_count) {
    const std::string color = resolve_highlight_color(username, highlight_enabled, context_highlight);
    const std::string label = format_cohort_label(username, color, context_highlight);
    return FlagValues{highlight_enabled, context_highlight, show_move_count, color, label};
}

FlagValues defaults(const std::string& username) {
    return apply_highlight_style(username, false, false, false);
}

bool json_bool(const std::string& json, const std::string& key) {
    const std::string quoted = "\"" + key + "\": true";
    const std::string compact = "\"" + key + "\":true";
    return json.find(quoted) != std::string::npos ||
           json.find(compact) != std::string::npos;
}

std::string json_string(const std::string& json, const std::string& key) {
    const std::string marker = "\"" + key + "\":\"";
    const auto start = json.find(marker);
    if (start == std::string::npos) {
        return "";
    }
    const auto value_start = start + marker.size();
    const auto end = json.find('"', value_start);
    if (end == std::string::npos) {
        return "";
    }
    return json.substr(value_start, end - value_start);
}

#if !defined(HAS_LAUNCHDARKLY)
FlagValues evaluate_via_python(const std::string& username) {
    if (std::getenv("LD_SDK_KEY") == nullptr) {
        return defaults(username);
    }
    std::ostringstream cmd;
    cmd << "python3 evaluate_flags.py ";
    for (char ch : username) {
        if (std::isalnum(static_cast<unsigned char>(ch)) || ch == '-' || ch == '_') {
            cmd << ch;
        }
    }
    FILE* pipe = popen(cmd.str().c_str(), "r");
    if (pipe == nullptr) {
        return defaults(username);
    }
    std::string output;
    char buffer[256];
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        output += buffer;
    }
    pclose(pipe);
    FlagValues values;
    values.highlightEnabled = json_bool(output, "highlightEnabled");
    values.contextHighlight = json_bool(output, "contextHighlight");
    values.showMoveCount = json_bool(output, "showMoveCount");
    values.highlightColor = json_string(output, "highlightColor");
    values.cohortLabel = json_string(output, "cohortLabel");
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
    LDJSON* context = LDNewContextFromString(
        ("{\"kind\":\"user\",\"key\":\"" + username + "\"}").c_str());
    if (context == nullptr) {
        return defaults(username);
    }
    const bool highlight =
        LDBoolVariation(g_client, kFlagHighlight, context, false);
    const bool context_highlight =
        LDBoolVariation(g_client, kFlagContext, context, false);
    const bool show_count = LDBoolVariation(g_client, kFlagCount, context, false);
    LDJSONFree(context);
    return apply_highlight_style(username, highlight, context_highlight, show_count);
#else
    return evaluate_via_python(username);
#endif
}
