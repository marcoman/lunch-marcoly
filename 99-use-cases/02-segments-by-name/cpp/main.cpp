// Console grid navigator with LaunchDarkly segment-by-name highlight (string flag).

#include "flags.hpp"

#include <algorithm>
#include <array>
#include <iostream>
#include <optional>
#include <string>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

namespace {

constexpr std::array<const char*, 3> kRows = {"t", "m", "b"};
constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};
constexpr const char* kBgReset = "\033[48;5;236m";
constexpr const char* kReset = "\033[0m";

struct Position {
    int row;
    int col;
};

struct MoveResult {
    int row;
    int col;
    bool moved;
};

termios g_original_termios{};

std::string ansi_color(const std::string& color) {
    if (color == "yellow") return "\033[93m";
    if (color == "red") return "\033[91m";
    if (color == "blue") return "\033[94m";
    if (color == "green") return "\033[92m";
    if (color == "purple") return "\033[35m";
    return "";
}

std::string colorize(const std::string& text, const std::string& color) {
    if (color.empty() || color == "none") {
        return text;
    }
    const std::string ansi = ansi_color(color);
    if (ansi.empty()) {
        return text;
    }
    return ansi + text + kReset + kBgReset;
}

std::string format_pos(int row, int col) {
    return std::string(kRows[row]) + "/" + kCols[col];
}

MoveResult try_move(int row, int col, int dr, int dc) {
    const int nr = std::clamp(row + dr, 0, 2);
    const int nc = std::clamp(col + dc, 0, 2);
    if (nr == row && nc == col) {
        return {row, col, false};
    }
    return {nr, nc, true};
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
    std::cout << "Login\n\nUsername: ";
    std::string name;
    std::getline(std::cin, name);
    while (name.empty()) {
        std::cout << "Username is required.\nUsername: ";
        std::getline(std::cin, name);
    }
    return name;
}

std::string cell_line(bool selected, int line, const std::string& color) {
    std::string text;
    if (selected) {
        switch (line) {
            case 0:
                text = "┏━━━┓";
                break;
            case 1:
                text = "┃ X ┃";
                break;
            default:
                text = "┗━━━┛";
                break;
        }
        if (!color.empty() && color != "none") {
            return colorize(text, color);
        }
        return text;
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

void render(const std::string& username, int row, int col,
            const std::optional<Position>& previous, const FlagValues& flags) {
    std::cout << "\033[2J\033[H" << kBgReset << std::flush;
    const std::string prev_text =
        previous ? format_pos(previous->row, previous->col) : "—";
    const std::string name_line =
        "Name: " + colorize(username, flags.highlightColor) +
        colorize(" " + flags.segmentLabel, flags.highlightColor) + kReset + kBgReset;
    write_line(name_line);
    write_line("Current position: " + format_pos(row, col));
    write_line("Previous position: " + prev_text);
    write_line("");
    write_line("Use arrow keys or WASD to move (L to logout, Q to quit).");
    write_line("");

    const std::string cell_color =
        flags.highlightColor == "none" ? "none" : flags.highlightColor;
    for (int r = 0; r < 3; ++r) {
        for (int line = 0; line < 3; ++line) {
            std::string row_text;
            for (int c = 0; c < 3; ++c) {
                if (c > 0) {
                    row_text += ' ';
                }
                const bool selected = r == row && c == col;
                row_text += cell_line(selected, line, selected ? cell_color : "none");
            }
            write_line(row_text);
        }
    }
    std::cout << std::flush;
}

enum class SessionAction { kQuit, kLogout };

bool read_direction(int& dr, int& dc, SessionAction& action) {
    const int key = std::cin.get();
    if (key == std::char_traits<char>::eof()) {
        return true;
    }
    if (key == 'q' || key == 'Q') {
        action = SessionAction::kQuit;
        return false;
    }
    if (key == 'l' || key == 'L') {
        action = SessionAction::kLogout;
        return false;
    }
    action = SessionAction::kQuit;
    if (key == 27) {
        if (std::cin.get() != 91) {
            return true;
        }
        const int arrow = std::cin.get();
        if (arrow == 65) {
            dr = -1;
        } else if (arrow == 66) {
            dr = 1;
        } else if (arrow == 68) {
            dc = -1;
        } else if (arrow == 67) {
            dc = 1;
        }
        return true;
    }
    if (key == 'w' || key == 'W') {
        dr = -1;
    } else if (key == 's' || key == 'S') {
        dr = 1;
    } else if (key == 'a' || key == 'A') {
        dc = -1;
    } else if (key == 'd' || key == 'D') {
        dc = 1;
    }
    return true;
}

SessionAction run_grid(const std::string& username, const FlagValues& flags) {
    int row = 1;
    int col = 1;
    std::optional<Position> previous;

    while (true) {
        render(username, row, col, previous, flags);

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
        SessionAction action = SessionAction::kQuit;
        if (!read_direction(dr, dc, action)) {
            return action;
        }
        if (dr == 0 && dc == 0) {
            continue;
        }
        const MoveResult result = try_move(row, col, dr, dc);
        if (result.moved) {
            previous = Position{row, col};
            row = result.row;
            col = result.col;
        }
    }
}

}  // namespace

int main() {
    init_launchdarkly();

    while (true) {
        const std::string username = read_username();
        const FlagValues flags = evaluate_flags(username);
        enable_raw_mode();
        const SessionAction action = run_grid(username, flags);
        disable_raw_mode();
        if (action == SessionAction::kQuit) {
            break;
        }
    }

    close_launchdarkly();
    return 0;
}
