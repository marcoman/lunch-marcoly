// Console grid navigator demonstrating LaunchDarkly targeting rules.
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
constexpr const char* kAppBanner = "13-flag-targeting-rules[cpp]";
constexpr const char* kBg = "\033[48;5;236m";
constexpr const char* kReset = "\033[0m";
termios g_original_termios{};

struct Login {
    std::string username;
    std::string team;
};

struct Position {
    int row;
    int col;
};

enum class SessionAction { kQuit, kLogout };

std::string format_pos(int row, int col) {
    return std::string(kRows[row]) + "/" + kCols[col];
}

std::string colored_team(const FlagValues& flags) {
    std::string color;
    if (flags.style == "colored-red") {
        color = "\033[31m";
    } else if (flags.style == "colored-blue") {
        color = "\033[34m";
    } else if (flags.style == "colored-yellow") {
        color = "\033[33m";
    }
    return color.empty() ? flags.teamLabel : color + flags.teamLabel + kReset + kBg;
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
    std::cout << kReset << "\033[?1049l" << std::flush;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &g_original_termios);
}

// Prompt for the user key and public team attribute used by targeting rules.
Login read_login() {
    std::cout << kAppBanner << "\nLogin\n\n";
    std::string username;
    while (username.empty()) {
        std::cout << "Username: ";
        std::getline(std::cin, username);
        if (username.empty()) {
            std::cout << "Username is required.\n";
        }
    }
    while (true) {
        std::cout << "Team [1=None 2=Red 3=Blue 4=Yellow]: ";
        std::string choice;
        std::getline(std::cin, choice);
        if (choice == "1") return {username, ""};
        if (choice == "2") return {username, "red"};
        if (choice == "3") return {username, "blue"};
        if (choice == "4") return {username, "yellow"};
        std::cout << "Choose 1, 2, 3, or 4.\n";
    }
}

std::string cell_line(bool selected, int line) {
    if (selected) {
        return std::array<std::string, 3>{"┏━━━┓", "┃ X ┃", "┗━━━┛"}[line];
    }
    return std::array<std::string, 3>{"┌───┐", "│   │", "└───┘"}[line];
}

void write_line(const std::string& line) {
    std::cout << line << "\033[K\r\n";
}

void render(const Login& login, int row, int col,
            const std::optional<Position>& previous, const FlagValues& flags) {
    std::cout << kBg << "\033[2J\033[H";
    write_line(kAppBanner);
    write_line("Name: " + login.username);
    write_line("Team: " + colored_team(flags));
    write_line("Current position: " + format_pos(row, col));
    write_line("Previous position: " +
               (previous ? format_pos(previous->row, previous->col) : "—"));
    write_line("");
    write_line("Use arrow keys or WASD to move (L to logout, Q to quit).");
    write_line("");
    for (int r = 0; r < 3; ++r) {
        for (int line = 0; line < 3; ++line) {
            std::string text;
            for (int c = 0; c < 3; ++c) {
                if (c > 0) text += ' ';
                text += cell_line(r == row && c == col, line);
            }
            write_line(text);
        }
    }
    std::cout << std::flush;
}

bool read_direction(int& dr, int& dc, SessionAction& action) {
    const int key = std::cin.get();
    if (key == std::char_traits<char>::eof() || key == 'q' || key == 'Q' || key == 3) {
        action = SessionAction::kQuit;
        return false;
    }
    if (key == 'l' || key == 'L') {
        action = SessionAction::kLogout;
        return false;
    }
    if (key == 27) {
        if (std::cin.get() != '[') return true;
        const int arrow = std::cin.get();
        if (arrow == 'A') dr = -1;
        else if (arrow == 'B') dr = 1;
        else if (arrow == 'C') dc = 1;
        else if (arrow == 'D') dc = -1;
        return true;
    }
    if (key == 'w' || key == 'W') dr = -1;
    else if (key == 's' || key == 'S') dr = 1;
    else if (key == 'a' || key == 'A') dc = -1;
    else if (key == 'd' || key == 'D') dc = 1;
    return true;
}

// Re-evaluate the team style every 500 ms while navigating.
SessionAction run_grid(const Login& login) {
    int row = 1;
    int col = 1;
    std::optional<Position> previous;
    while (true) {
        const FlagValues flags = evaluate_flags(login.username, login.team);
        render(login, row, col, previous, flags);

        fd_set set;
        FD_ZERO(&set);
        FD_SET(STDIN_FILENO, &set);
        timeval timeout{0, 500000};
        if (select(STDIN_FILENO + 1, &set, nullptr, nullptr, &timeout) <= 0) {
            continue;
        }

        int dr = 0;
        int dc = 0;
        SessionAction action = SessionAction::kQuit;
        if (!read_direction(dr, dc, action)) {
            return action;
        }
        const int next_row = std::clamp(row + dr, 0, 2);
        const int next_col = std::clamp(col + dc, 0, 2);
        if (next_row != row || next_col != col) {
            previous = Position{row, col};
            row = next_row;
            col = next_col;
        }
    }
}

}  // namespace

int main() {
    init_launchdarkly();
    while (true) {
        const Login login = read_login();
        enable_raw_mode();
        const SessionAction action = run_grid(login);
        disable_raw_mode();
        if (action == SessionAction::kQuit) {
            break;
        }
    }
    close_launchdarkly();
    return 0;
}
