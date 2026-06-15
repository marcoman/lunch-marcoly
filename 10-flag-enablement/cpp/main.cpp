// Console grid navigator with LaunchDarkly flag evaluation.

#include "flags.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <iostream>
#include <optional>
#include <string>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

namespace {

constexpr std::array<const char*, 3> kRows = {"t", "m", "b"};
constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};
constexpr const char* kBg = "\033[48;5;236m";
constexpr const char* kReset = "\033[0m";

std::string ansi_color(const std::string& color) {
    if (color == "pink") return "\033[95m";
    if (color == "yellow") return "\033[93m";
    if (color == "red") return "\033[91m";
    if (color == "blue") return "\033[94m";
    if (color == "green") return "\033[92m";
    if (color == "purple") return "\033[35m";
    return "";
}

std::string display_name(const std::string& username, const std::string& os_emoji) {
    if (os_emoji.empty()) {
        return username;
    }
    return os_emoji + " " + username;
}

std::string colorize(const std::string& text, const std::string& color) {
    if (color.empty() || color == "none") {
        return text;
    }
    const std::string ansi = ansi_color(color);
    if (ansi.empty()) {
        return text;
    }
    return ansi + text + kReset + kBg;
}

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
}

void disable_raw_mode() {
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

constexpr const char* kEol = "\r\n";

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
        if (!color.empty() && color != "none") {
            return colorize(plain, color);
        }
        return plain;
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
    std::cout << line << kEol;
}

void render(const std::string& username, int row, int col,
            const std::optional<Position>& previous, int move_count,
            const FlagValues& flags) {
    std::cout << kBg << "\033[H\033[2J";
    const std::string prev_text =
        previous ? format_pos(previous->row, previous->col) : "—";
    const std::string cohort = " " + flags.cohortLabel;
    write_line("Name: " + colorize(display_name(username, flags.osEmoji), flags.highlightColor) +
               colorize(cohort, flags.highlightColor) + kReset + kBg);
    write_line("Current position: " + format_pos(row, col));
    write_line("Previous position: " + prev_text);
    if (flags.showMoveCount) {
        write_line("Count: " + std::to_string(move_count));
    }
    write_line("");
    write_line("Use arrow keys or WASD to move (q to quit).");
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
            top += cell_line(selected, flags.highlightColor, 0);
            mid += cell_line(selected, flags.highlightColor, 1);
            bot += cell_line(selected, flags.highlightColor, 2);
        }
        write_line(top);
        write_line(mid);
        write_line(bot);
    }
}

bool read_direction(int& dr, int& dc) {
    const int key = std::cin.get();
    if (key == std::char_traits<char>::eof()) {
        return true;
    }
    if (key == 'q' || key == 'Q') {
        return false;
    }
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

void run_grid(const std::string& username) {
    int row = 1;
    int col = 1;
    std::optional<Position> previous;
    int move_count = 0;

    while (true) {
        const FlagValues flags = evaluate_flags(username);
        render(username, row, col, previous, move_count, flags);

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
        if (!read_direction(dr, dc)) {
            break;
        }
        if (dr == 0 && dc == 0) {
            continue;
        }
        const MoveResult result = try_move(row, col, dr, dc);
        if (result.moved) {
            previous = Position{row, col};
            row = result.row;
            col = result.col;
            move_count += 1;
        }
    }
}

}  // namespace

int main() {
    init_launchdarkly();
    const std::string username = read_username();
    enable_raw_mode();
    run_grid(username);
    disable_raw_mode();
    close_launchdarkly();
    return 0;
}
