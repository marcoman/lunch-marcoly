// 01-reference-agent[cpp] — terminal UI matching the other language consoles.

#include "agent.hpp"
#include "yahoo.hpp"

#include <curl/curl.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>

#include <algorithm>
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr const char* kAppBanner = "01-reference-agent[cpp]";
constexpr int kChromeRows = 3;
constexpr int kFooterRows = 1;
constexpr size_t kPadMax = 4000;
constexpr const char* kMenuRight = "(n)ext user";
constexpr const char* kMenuLeft[] = {"(t)ickers", "st(o)ries", "(s)tatus",
                                     "(g)enerate report", "(m)ode", "(q)uit"};
constexpr const char* kLlmModes[] = {"stub", "ollama", "bedrock"};

constexpr const char* kReset = "\033[0m";
constexpr const char* kBold = "\033[1m";
constexpr const char* kDim = "\033[2m";
constexpr const char* kCyan = "\033[36m";
constexpr const char* kYellow = "\033[33m";
constexpr const char* kGreen = "\033[32m";
constexpr const char* kMagenta = "\033[35m";
constexpr const char* kBlue = "\033[34m";
constexpr const char* kRed = "\033[31m";
constexpr const char* kWhite = "\033[37m";

termios g_original_termios{};
bool g_raw = false;

struct PadLine {
    std::string text;
    std::string kind;
};

struct TermSize {
    int cols;
    int rows;
};

TermSize term_size() {
    winsize ws{};
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0 && ws.ws_col > 0 &&
        ws.ws_row > 0) {
        return {static_cast<int>(ws.ws_col), static_cast<int>(ws.ws_row)};
    }
    return {100, 32};
}

void enable_raw_mode() {
    tcgetattr(STDIN_FILENO, &g_original_termios);
    termios raw = g_original_termios;
    raw.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
    raw.c_cc[VMIN] = 1;
    raw.c_cc[VTIME] = 0;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
    g_raw = true;
}

void disable_raw_mode() {
    if (g_raw) {
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &g_original_termios);
        g_raw = false;
    }
}

std::string paint(const std::string& text, const std::string& kind) {
    const char* style = "";
    if (kind == "hotkey") {
        style = "\033[1m\033[36m";
    } else if (kind == "name") {
        style = "\033[1m\033[33m";
    } else if (kind == "ok") {
        style = "\033[1m\033[32m";
    } else if (kind == "error") {
        style = "\033[1m\033[31m";
    } else if (kind == "busy") {
        style = "\033[1m\033[36m";
    } else if (kind == "warn") {
        style = "\033[1m\033[33m";
    } else if (kind == "muted") {
        style = "\033[2m\033[37m";
    } else if (kind == "ticker1" || kind == "story1") {
        style = "\033[1m\033[32m";
    } else if (kind == "ticker2" || kind == "story2") {
        style = "\033[1m\033[35m";
    } else if (kind == "prompt") {
        style = kBlue;
    } else if (kind == "response") {
        style = kCyan;
    } else {
        return text;
    }
    return std::string(style) + text + kReset;
}

std::string clip(const std::string& text, int width) {
    if (width <= 0) {
        return "";
    }
    // Approximate display width as UTF-8 code units for ASCII-heavy UI.
    if (static_cast<int>(text.size()) <= width) {
        return text;
    }
    if (width <= 1) {
        return text.substr(0, static_cast<size_t>(width));
    }
    return text.substr(0, static_cast<size_t>(width - 1)) + "…";
}

std::string align_pair(std::string left, std::string right, int width, int gap = 2) {
    if (width <= 0) {
        return "";
    }
    gap = std::max(2, gap);
    if (static_cast<int>(left.size()) + gap + static_cast<int>(right.size()) > width) {
        int room = std::max(0, width - gap - static_cast<int>(left.size()));
        right = clip(right, room);
        room = std::max(0, width - gap - static_cast<int>(right.size()));
        left = clip(left, room);
    }
    const int pad =
        std::max(gap, width - static_cast<int>(left.size()) - static_cast<int>(right.size()));
    return clip(left + std::string(static_cast<size_t>(pad), ' ') + right, width);
}

std::string style_hotkeys(const std::string& text) {
    std::string out;
    for (size_t i = 0; i < text.size(); ++i) {
        if (text[i] == '(' && i + 2 < text.size() && text[i + 2] == ')' &&
            std::isalpha(static_cast<unsigned char>(text[i + 1]))) {
            out.push_back('(');
            out += paint(std::string(1, text[i + 1]), "hotkey");
            out.push_back(')');
            i += 2;
        } else {
            out.push_back(text[i]);
        }
    }
    return out;
}

std::vector<std::string> wrap_text(const std::string& text, int width) {
    std::vector<std::string> out;
    std::istringstream iss(text);
    std::string raw;
    bool first = true;
    // Preserve empty lines via manual split
    size_t start = 0;
    while (true) {
        const size_t nl = text.find('\n', start);
        raw = nl == std::string::npos ? text.substr(start) : text.substr(start, nl - start);
        if (raw.empty()) {
            out.push_back("");
        } else {
            std::string rest = raw;
            while (static_cast<int>(rest.size()) > width) {
                out.push_back(rest.substr(0, static_cast<size_t>(width)));
                rest = rest.substr(static_cast<size_t>(width));
            }
            out.push_back(rest);
        }
        if (nl == std::string::npos) {
            break;
        }
        start = nl + 1;
        first = false;
    }
    (void)first;
    if (out.empty()) {
        out.push_back("");
    }
    return out;
}

int story_count(const std::vector<TickerBlock>& stories, const std::string& ticker) {
    const std::string symbol = normalize_ticker(ticker);
    for (const auto& block : stories) {
        if (normalize_ticker(block.ticker) == symbol) {
            return static_cast<int>(block.stories.size());
        }
    }
    return 0;
}

std::string tickers_label(const std::string& t1, const std::string& t2,
                          const std::vector<TickerBlock>& stories) {
    const std::string a = t1.empty() ? "(not set)" : t1;
    const std::string b = t2.empty() ? "(not set)" : t2;
    return "Tickers: " + a + " (" + std::to_string(story_count(stories, t1)) +
           " stories) " + b + " (" + std::to_string(story_count(stories, t2)) +
           " stories)";
}

std::string opt_num(const std::optional<long long>& v) {
    return v ? std::to_string(*v) : "—";
}
std::string opt_num(const std::optional<int>& v) {
    return v ? std::to_string(*v) : "—";
}

struct App {
    size_t persona_index = 0;
    std::string ticker1 = kDefaultTicker1;
    std::string ticker2 = kDefaultTicker2;
    std::vector<TickerBlock> stories;
    std::vector<PadLine> pad_lines;
    int scroll = 0;
    std::string footer = "Ready.";
    std::string footer_kind = "info";
    bool busy = false;

    const Persona& persona() const { return kPersonas[persona_index]; }

    void restore_cache() {
        if (auto cached = get_last_pair_cached()) {
            ticker1 = std::get<0>(*cached);
            ticker2 = std::get<1>(*cached);
            stories = std::get<2>(*cached);
            footer = "Restored saved stories from disk cache.";
            footer_kind = "ok";
        }
    }

    void set_footer(const std::string& text, const std::string& kind) {
        footer = text;
        footer_kind = kind;
    }

    int output_height() const {
        return std::max(1, term_size().rows - kChromeRows - kFooterRows);
    }

    void scroll_to_bottom() {
        scroll = std::max(0, static_cast<int>(pad_lines.size()) - output_height());
    }

    void scroll_by(int delta) {
        const int max_scroll =
            std::max(0, static_cast<int>(pad_lines.size()) - output_height());
        scroll = std::clamp(scroll + delta, 0, max_scroll);
    }

    void append(const std::string& text, const std::string& kind) {
        const int width = std::max(20, term_size().cols - 1);
        for (const auto& line : wrap_text(text, width)) {
            pad_lines.push_back({line, kind});
        }
        if (pad_lines.size() > kPadMax) {
            pad_lines.erase(pad_lines.begin(),
                            pad_lines.begin() +
                                static_cast<long>(pad_lines.size() - kPadMax));
        }
        scroll_to_bottom();
    }

    void append_token(const std::string& token, const std::string& kind) {
        if (token.empty()) {
            return;
        }
        const int width = std::max(20, term_size().cols - 1);
        size_t start = 0;
        bool first_part = true;
        while (true) {
            const size_t nl = token.find('\n', start);
            const std::string part =
                nl == std::string::npos ? token.substr(start)
                                        : token.substr(start, nl - start);
            if (!first_part) {
                pad_lines.push_back({"", kind});
            }
            first_part = false;
            if (!part.empty()) {
                if (pad_lines.empty()) {
                    pad_lines.push_back({"", kind});
                }
                if (pad_lines.back().kind != kind && !pad_lines.back().text.empty()) {
                    pad_lines.push_back({"", kind});
                }
                std::string current = pad_lines.back().text;
                std::string combined = current + part;
                if (static_cast<int>(combined.size()) <= width) {
                    pad_lines.back() = {combined, kind};
                } else {
                    const int space = width - static_cast<int>(current.size());
                    if (space > 0) {
                        pad_lines.back() = {current + part.substr(0, static_cast<size_t>(space)),
                                            kind};
                        std::string rest = part.substr(static_cast<size_t>(space));
                        while (!rest.empty()) {
                            pad_lines.push_back(
                                {rest.substr(0, static_cast<size_t>(width)), kind});
                            if (static_cast<int>(rest.size()) <= width) {
                                rest.clear();
                            } else {
                                rest = rest.substr(static_cast<size_t>(width));
                            }
                        }
                    } else {
                        std::string rest = part;
                        while (!rest.empty()) {
                            pad_lines.push_back(
                                {rest.substr(0, static_cast<size_t>(width)), kind});
                            if (static_cast<int>(rest.size()) <= width) {
                                rest.clear();
                            } else {
                                rest = rest.substr(static_cast<size_t>(width));
                            }
                        }
                    }
                }
            }
            if (nl == std::string::npos) {
                break;
            }
            start = nl + 1;
        }
        if (pad_lines.size() > kPadMax) {
            pad_lines.erase(pad_lines.begin(),
                            pad_lines.begin() +
                                static_cast<long>(pad_lines.size() - kPadMax));
        }
        scroll_to_bottom();
    }

    void render() const {
        const int width = std::max(1, term_size().cols - 1);
        const std::string mode = resolve_mode();
        const std::string model = model_label(mode);
        const std::string right0 = tickers_label(ticker1, ticker2, stories);
        const std::string left1 = "AGENT_LLM_MODE=" + mode + "  model=" + model;
        const std::string name_label = std::string("Name: ") + persona().name + ".";
        std::string left_menu;
        for (size_t i = 0; i < 6; ++i) {
            if (i) {
                left_menu += "  ";
            }
            left_menu += kMenuLeft[i];
        }

        const std::string chrome0 = align_pair(kAppBanner, right0, width);
        const std::string chrome1 = align_pair(left1, name_label, width);
        const std::string chrome2 = align_pair(left_menu, kMenuRight, width);

        std::cout << "\033[H\033[2J";

        auto rfind_or0 = [](const std::string& hay, const std::string& needle) {
            const auto p = hay.rfind(needle);
            return p == std::string::npos ? 0 : static_cast<int>(p);
        };

        const int c0 = rfind_or0(chrome0, right0);
        std::cout << paint(kAppBanner, "muted")
                  << std::string(std::max(0, c0 - static_cast<int>(std::string(kAppBanner).size())),
                                 ' ')
                  << clip(right0, width - c0) << "\033[K\r\n";

        const int c1 = rfind_or0(chrome1, name_label);
        std::cout << clip(left1, c1)
                  << std::string(std::max(0, c1 - static_cast<int>(left1.size())), ' ')
                  << "Name: " << paint(persona().name, "name") << ".\033[K\r\n";

        const int c2 = rfind_or0(chrome2, kMenuRight);
        std::cout << style_hotkeys(clip(left_menu, c2))
                  << std::string(std::max(0, c2 - static_cast<int>(left_menu.size())), ' ')
                  << style_hotkeys(kMenuRight) << "\033[K\r\n";

        const int view_h = output_height();
        const int end =
            std::min(static_cast<int>(pad_lines.size()), scroll + view_h);
        for (int i = 0; i < view_h; ++i) {
            const int idx = scroll + i;
            if (idx >= end) {
                std::cout << "\033[K\r\n";
                continue;
            }
            std::cout << paint(clip(pad_lines[static_cast<size_t>(idx)].text, width),
                               pad_lines[static_cast<size_t>(idx)].kind)
                      << "\033[K\r\n";
        }
        std::cout << paint(clip(footer, width), footer_kind) << "\033[K" << std::flush;
    }

    void append_stories() {
        if (stories.empty()) {
            append("  (no stories loaded — press o)", "muted");
            return;
        }
        for (size_t index = 0; index < stories.size(); ++index) {
            const auto& block = stories[index];
            const int slot = index == 0 ? 1 : 2;
            const std::string ticker = block.ticker.empty() ? "?" : block.ticker;
            const std::string name = block.name.empty() ? ticker : block.name;
            const std::string cache = block.from_cache ? " [cached]" : "";
            append("  " + ticker + " (" + name + ")" + cache,
                   "ticker" + std::to_string(slot));
            if (block.stories.empty()) {
                append("    · " + (block.error.empty() ? "no stories" : block.error),
                       "muted");
                continue;
            }
            for (const auto& s : block.stories) {
                std::string line =
                    "    · " + (s.title.empty() ? std::string("(untitled)") : s.title);
                if (!s.publisher.empty()) {
                    line += " — " + s.publisher;
                }
                append(line, "story" + std::to_string(slot));
            }
            if (!block.error.empty()) {
                append("    note: " + block.error, "warn");
            }
        }
    }

    void cmd_status() {
        const std::string mode = resolve_mode();
        append("— status —", "muted");
        append(std::string("User:     ") + persona().name + " (" + persona().profile + ")",
               "name");
        append("Tickers:  " + ticker1, "ticker1");
        append("          " + ticker2, "ticker2");
        append("Provider: " + mode + " / " + model_label(mode), "muted");
        append("Stories:", "muted");
        append_stories();
        set_footer("Status shown.", "ok");
    }

    std::string prompt_line(const std::string& label) {
        set_footer(label, "busy");
        render();
        disable_raw_mode();
        std::cout << label << std::flush;
        std::string line;
        std::getline(std::cin, line);
        enable_raw_mode();
        return line;
    }

    void cmd_tickers() {
        const std::string t1 = prompt_line("Ticker 1: ");
        const std::string t2 = prompt_line("Ticker 2: ");
        if (!t1.empty()) {
            const std::string n = normalize_ticker(t1);
            ticker1 = n.empty() ? kDefaultTicker1 : n;
        }
        if (!t2.empty()) {
            const std::string n = normalize_ticker(t2);
            ticker2 = n.empty() ? kDefaultTicker2 : n;
        }
        append("Tickers set to " + ticker1 + "  " + ticker2, "ok");
        set_footer("Tickers: " + ticker1 + "  " + ticker2, "ok");
    }

    void cmd_stories() {
        busy = true;
        set_footer("Fetching Yahoo stories for " + ticker1 + " and " + ticker2 + "…",
                   "busy");
        render();
        auto result = fetch_stories_for_tickers(ticker1, ticker2, 2);
        stories = std::move(result.tickers);
        append("— stories (" + ticker1 + " / " + ticker2 + ") —", "muted");
        append_stories();
        if (result.errors.empty()) {
            set_footer("Stories loaded. Press g to generate.", "ok");
        } else {
            std::string joined;
            for (size_t i = 0; i < result.errors.size(); ++i) {
                if (i) {
                    joined += " · ";
                }
                joined += result.errors[i];
            }
            set_footer(joined, "warn");
        }
        busy = false;
    }

    void cmd_next_user() {
        persona_index = (persona_index + 1) % kPersonaCount;
        append(std::string("User: ") + persona().name + " (" + persona().profile + ")",
               "name");
        set_footer(std::string("User: ") + persona().name, "ok");
    }

    void cmd_mode() {
        const std::string current = resolve_mode();
        int idx = 0;
        for (int i = 0; i < 3; ++i) {
            if (current == kLlmModes[i]) {
                idx = i;
                break;
            }
        }
        const std::string nxt = kLlmModes[(idx + 1) % 3];
        if (nxt == "ollama" && !probe_ollama(600)) {
            append("Ollama not reachable at " + ollama_host() +
                       ". Start Ollama and pull a model.",
                   "warn");
            set_footer("Ollama not reachable — mode left unchanged.", "warn");
            return;
        }
        set_mode_override(nxt);
        setenv("AGENT_LLM_MODE", nxt.c_str(), 1);
        const std::string mode = resolve_mode();
        const std::string model = model_label(mode);
        append("Mode set to AGENT_LLM_MODE=" + mode + "  model=" + model, "ok");
        if (mode == "ollama") {
            append("Using Ollama at " + ollama_host() + " with model " + model + ".",
                   "muted");
        }
        set_footer("AGENT_LLM_MODE=" + mode + "  model=" + model, "ok");
    }

    void cmd_generate() {
        bool usable = false;
        for (const auto& b : stories) {
            if (!b.stories.empty()) {
                usable = true;
                break;
            }
        }
        if (!usable) {
            set_footer("Load stories first (press o), then g.", "warn");
            return;
        }
        busy = true;
        const std::string persona_name = persona().name;
        set_footer("Generating AI report for " + persona_name + "…", "busy");
        append("— generate (" + persona_name + ") —", "muted");
        render();
        bool saw_token = false;
        generate_stream(persona(), stories, [&](const StreamEvent& event) {
            switch (event.type) {
                case StreamEvent::Type::Meta:
                    append("Provider: " + event.provider + " / " + event.model, "muted");
                    append("Prompt:", "muted");
                    append(event.input, "prompt");
                    append("Response:", "muted");
                    break;
                case StreamEvent::Type::Token:
                    append_token(event.text, "response");
                    saw_token = true;
                    set_footer("Streaming… " + persona_name, "busy");
                    break;
                case StreamEvent::Type::Error: {
                    if (saw_token) {
                        append("", "normal");
                    }
                    const std::string msg =
                        event.message.empty() ? "Generation error" : event.message;
                    append("Error: " + msg, "error");
                    set_footer(msg, "error");
                    break;
                }
                case StreamEvent::Type::Metrics: {
                    if (saw_token) {
                        append("", "normal");
                    }
                    const auto& m = event.metrics;
                    append("Metrics: latency_ms=" + opt_num(m.latency_ms) +
                               "  ttft_ms=" + opt_num(m.ttft_ms) +
                               "  prompt_tokens=" + opt_num(m.prompt_tokens) +
                               "  completion_tokens=" + opt_num(m.completion_tokens) +
                               "  total_tokens=" + opt_num(m.total_tokens) +
                               "  finish_reason=" +
                               (m.finish_reason.empty() ? "—" : m.finish_reason),
                           "muted");
                    break;
                }
                case StreamEvent::Type::Done:
                    set_footer("Done — report complete for " + persona_name + ".", "ok");
                    break;
            }
            render();
        });
        busy = false;
    }
};

struct KeyEvent {
    char ch = 0;
    const char* name = "";  // up/down/pageup/pagedown/quit
    bool ctrl_c = false;
};

KeyEvent read_key() {
    char b = 0;
    if (read(STDIN_FILENO, &b, 1) != 1) {
        return {0, "quit", false};
    }
    if (b == 3) {
        return {0, "quit", true};
    }
    if (b == 'q' || b == 'Q') {
        return {'q', "quit", false};
    }
    if (b == 27) {
        char b2 = 0;
        if (read(STDIN_FILENO, &b2, 1) != 1 || b2 != '[') {
            return {};
        }
        char b3 = 0;
        if (read(STDIN_FILENO, &b3, 1) != 1) {
            return {};
        }
        if (b3 == 'A') {
            return {0, "up"};
        }
        if (b3 == 'B') {
            return {0, "down"};
        }
        if (b3 == '5' || b3 == '6') {
            char b4 = 0;
            if (read(STDIN_FILENO, &b4, 1) == 1 && b4 == '~') {
                return {0, b3 == '5' ? "pageup" : "pagedown"};
            }
        }
        return {};
    }
    if (b >= 32 && b < 127) {
        return {b, ""};
    }
    return {};
}

}  // namespace

int main() {
    if (!isatty(STDIN_FILENO)) {
        std::cerr << "cpp console requires an interactive TTY.\n";
        return 1;
    }

    curl_global_init(CURL_GLOBAL_DEFAULT);
    const std::string mode = ensure_llm_mode();
    App app;
    app.restore_cache();
    if (!(app.footer_kind == "ok" && !app.stories.empty())) {
        app.set_footer("Ready (" + mode + "/" + model_label(mode) +
                           "). Arrow keys scroll. (m)ode cycles LLM.",
                       "info");
    }

    enable_raw_mode();
    while (true) {
        app.render();
        const KeyEvent key = read_key();
        if (key.ctrl_c || std::string(key.name) == "quit") {
            break;
        }
        if (std::string(key.name) == "up") {
            app.scroll_by(-1);
            continue;
        }
        if (std::string(key.name) == "down") {
            app.scroll_by(1);
            continue;
        }
        if (std::string(key.name) == "pageup") {
            app.scroll_by(-app.output_height());
            continue;
        }
        if (std::string(key.name) == "pagedown") {
            app.scroll_by(app.output_height());
            continue;
        }
        if (app.busy) {
            continue;
        }
        char ch = key.ch;
        if (ch >= 'A' && ch <= 'Z') {
            ch = static_cast<char>(ch - 'A' + 'a');
        }
        switch (ch) {
            case 's':
                app.cmd_status();
                break;
            case 't':
                app.cmd_tickers();
                break;
            case 'o':
                app.cmd_stories();
                break;
            case 'g':
                app.cmd_generate();
                break;
            case 'm':
                app.cmd_mode();
                break;
            case 'n':
                app.cmd_next_user();
                break;
            case 'h':
            case '?': {
                std::string menu;
                for (size_t i = 0; i < 6; ++i) {
                    if (i) {
                        menu += "  ";
                    }
                    menu += kMenuLeft[i];
                }
                app.set_footer(menu + "   " + kMenuRight, "info");
                break;
            }
            case 0:
                break;
            default:
                app.set_footer("Unknown key. Use menu hotkeys (t o s g m q n).", "warn");
                break;
        }
    }

    disable_raw_mode();
    std::cout << kReset << "\r\n";
    curl_global_cleanup();
    (void)kBold;
    (void)kDim;
    (void)kYellow;
    (void)kGreen;
    (void)kMagenta;
    (void)kRed;
    (void)kWhite;
    return 0;
}
