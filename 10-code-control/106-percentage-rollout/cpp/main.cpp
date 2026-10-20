// Console grid navigator for a static LaunchDarkly percentage rollout.

#include "flags.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>
#include <vector>

namespace {

constexpr std::array<const char*, 3> kRows = {"t", "m", "b"};
constexpr const char* kAppBanner = "16-percentage-rollout[cpp]";
constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};
constexpr const char* kBg = "\033[48;5;236m";
constexpr const char* kReset = "\033[0m";
constexpr const char* kGreen = "\033[92m";
constexpr int kConfiguredGreenPct = 30;
constexpr std::size_t kHistoryLimit = 8;

struct Position {
    int row;
    int col;
};

struct MoveResult {
    int row;
    int col;
    bool moved;
};

struct HistoryItem {
    std::string username;
    std::string value;
    std::string reason;
};

termios g_original_termios{};

std::string generated_username(const std::string& base, int index) {
    if (index <= 0) {
        return base;
    }
    return base + std::to_string(index);
}

std::string format_pos(int row, int col) {
    return std::string(kRows[row]) + "/" + kCols[col];
}

MoveResult try_move(int row, int col, int dr, int dc) {
    const int nr = std::clamp(row + dr, 0, 2);
    const int nc = std::clamp(col + dc, 0, 2);
    return {nr, nc, nr != row || nc != col};
}

void enable_raw_mode() {
    tcgetattr(STDIN_FILENO, &g_original_termios);
    termios raw = g_original_termios;
    raw.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 5;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
    std::cout << "\033[?1049h\033[2J\033[H" << std::flush;
}

void disable_raw_mode() {
    std::cout << "\033[?1049l" << std::flush;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &g_original_termios);
}

std::string read_username() {
    std::cout << kAppBanner << "\nLogin\n";
    std::cout << "Username becomes the LaunchDarkly user context key.\n\nUsername: ";
    std::string name;
    std::getline(std::cin, name);
    while (name.empty()) {
        std::cout << "Username is required.\nUsername: ";
        std::getline(std::cin, name);
    }
    return name;
}

std::string colorize(const std::string& text, const std::string& color) {
    if (color != "green") {
        return text;
    }
    return std::string(kGreen) + text + kReset + kBg;
}

std::string cell_line(bool selected, const std::string& color, int line) {
    std::string plain;
    if (selected) {
        switch (line) {
            case 0:
                plain = "┏━━━┓";
                break;
            case 1:
                plain = "┃ X ┃";
                break;
            default:
                plain = "┗━━━┛";
                break;
        }
        return colorize(plain, color);
    }
    switch (line) {
        case 0:
            return "┌───┐";
        case 1:
            return "│   │";
        default:
            return "└───┘";
    }
}

void write_line(const std::string& line) {
    std::cout << line << "\033[K\r\n";
}

std::string observed_line(const std::map<std::string, std::string>& seen) {
    const int total = static_cast<int>(seen.size());
    if (total == 0) {
        return "Observed: no unique keys yet.";
    }
    int green_count = 0;
    for (const auto& [_, value] : seen) {
        if (value == "green") {
            green_count += 1;
        }
    }
    const int none_count = total - green_count;
    const double pct = std::round((green_count / static_cast<double>(total)) * 1000.0) / 10.0;
    return "Observed: " + std::to_string(green_count) + " green / " + std::to_string(none_count)
           + " none of " + std::to_string(total) + " unique → " + std::to_string(pct)
           + "% (configured " + std::to_string(kConfiguredGreenPct) + "%)";
}

void remember(
        const std::string& username,
        const FlagValues& flags,
        std::map<std::string, std::string>& seen,
        std::vector<HistoryItem>& history
) {
    seen[username] = flags.flagValue;
    history.erase(
            std::remove_if(
                    history.begin(),
                    history.end(),
                    [&](const HistoryItem& item) { return item.username == username; }),
            history.end());
    history.insert(history.begin(), HistoryItem{username, flags.flagValue, flags.reasonKind});
    if (history.size() > kHistoryLimit) {
        history.resize(kHistoryLimit);
    }
}

void render(
        const std::string& username,
        const std::string& base,
        int index,
        int row,
        int col,
        const std::optional<Position>& previous,
        const FlagValues& flags,
        const std::map<std::string, std::string>& seen,
        const std::vector<HistoryItem>& history
) {
    std::cout << kBg << "\033[2J\033[H" << std::flush;
    const std::string prev_text = previous ? format_pos(previous->row, previous->col) : "—";
    const std::string prev_name = index == 0 ? "—" : generated_username(base, index - 1);
    write_line(kAppBanner);
    write_line("Name: " + colorize(username, flags.highlightColor) + kReset + kBg);
    write_line("Current: " + format_pos(row, col) + "   Previous: " + prev_text);
    write_line("Flag value: " + flags.flagValue + "   reason: " + flags.reasonKind
               + "   idx: " + flags.variationIndex);
    write_line(observed_line(seen));
    write_line(
            "Arrows/WASD move.  N next (" + generated_username(base, index + 1) + ")  P prev ("
            + prev_name + ")  L logout  Q quit");
    write_line("");
    for (int r = 0; r < 3; ++r) {
        std::string top;
        std::string mid;
        std::string bot;
        for (int c = 0; c < 3; ++c) {
            const bool selected = r == row && c == col;
            if (c > 0) {
                top += ' ';
                mid += ' ';
                bot += ' ';
            }
            const std::string color = selected ? flags.highlightColor : "none";
            top += cell_line(selected, color, 0);
            mid += cell_line(selected, color, 1);
            bot += cell_line(selected, color, 2);
        }
        write_line(top);
        write_line(mid);
        write_line(bot);
    }
    write_line("");
    write_line("Recent evaluations");
    if (history.empty()) {
        write_line("(none yet)");
    }
    for (const auto& item : history) {
        write_line(colorize(item.username + "  " + item.value + "  " + item.reason, item.value));
    }
    std::cout << std::flush;
}

enum class SessionAction { kQuit, kLogout };
enum class Command { kNone, kMove, kNext, kPrev, kQuit, kLogout };

Command read_command(int& dr, int& dc) {
    const int key = std::cin.get();
    if (key == std::char_traits<char>::eof()) {
        return Command::kNone;
    }
    if (key == 'q' || key == 'Q') return Command::kQuit;
    if (key == 'l' || key == 'L') return Command::kLogout;
    if (key == 'n' || key == 'N') return Command::kNext;
    if (key == 'p' || key == 'P') return Command::kPrev;
    if (key == 27) {
        if (std::cin.get() != 91) return Command::kNone;
        const int arrow = std::cin.get();
        if (arrow == 65) dr = -1;
        else if (arrow == 66) dr = 1;
        else if (arrow == 68) dc = -1;
        else if (arrow == 67) dc = 1;
        else return Command::kNone;
        return Command::kMove;
    }
    if (key == 'w' || key == 'W') dr = -1;
    else if (key == 's' || key == 'S') dr = 1;
    else if (key == 'a' || key == 'A') dc = -1;
    else if (key == 'd' || key == 'D') dc = 1;
    else return Command::kNone;
    return Command::kMove;
}

SessionAction run_grid(const std::string& base) {
    int index = 0;
    std::string username = generated_username(base, index);
    int row = 1;
    int col = 1;
    std::optional<Position> previous;
    std::map<std::string, std::string> seen;
    std::vector<HistoryItem> history;

    while (true) {
        const FlagValues flags = evaluate_flags(username);
        remember(username, flags, seen, history);
        render(username, base, index, row, col, previous, flags, seen, history);

        fd_set set;
        FD_ZERO(&set);
        FD_SET(STDIN_FILENO, &set);
        timeval timeout{};
        timeout.tv_sec = 0;
        timeout.tv_usec = 500000;
        const int ready = select(STDIN_FILENO + 1, &set, nullptr, nullptr, &timeout);
        if (ready <= 0) {
            continue;
        }

        int dr = 0;
        int dc = 0;
        switch (read_command(dr, dc)) {
            case Command::kQuit:
                return SessionAction::kQuit;
            case Command::kLogout:
                return SessionAction::kLogout;
            case Command::kNext:
                index += 1;
                username = generated_username(base, index);
                row = 1;
                col = 1;
                previous.reset();
                break;
            case Command::kPrev:
                if (index > 0) {
                    index -= 1;
                    username = generated_username(base, index);
                    row = 1;
                    col = 1;
                    previous.reset();
                }
                break;
            case Command::kMove: {
                const MoveResult result = try_move(row, col, dr, dc);
                if (result.moved) {
                    previous = Position{row, col};
                    row = result.row;
                    col = result.col;
                }
                break;
            }
            case Command::kNone:
                break;
        }
    }
}

}  // namespace

int main() {
    init_launchdarkly();
    while (true) {
        const std::string username = read_username();
        enable_raw_mode();
        const SessionAction action = run_grid(username);
        disable_raw_mode();
        if (action == SessionAction::kQuit) {
            break;
        }
    }
    close_launchdarkly();
    return 0;
}
