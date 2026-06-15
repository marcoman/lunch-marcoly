// Console grid navigator: username login and 3×3 keyboard navigation.

#include <algorithm>
#include <array>
#include <iostream>
#include <optional>
#include <string>
#include <termios.h>
#include <unistd.h>

namespace {

constexpr std::array<const char*, 3> kRows = {"t", "m", "b"};
constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};

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
    raw.c_cc[VMIN] = 1;
    raw.c_cc[VTIME] = 0;
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

std::string cell_line(bool selected, int line) {
    if (selected) {
        switch (line) {
            case 0:
                return "┏━━━┓";
            case 1:
                return "┃ X ┃";
            default:
                return "┗━━━┛";
        }
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
            const std::optional<Position>& previous) {
    std::cout << "\033[H\033[2J";
    const std::string prev_text =
        previous ? format_pos(previous->row, previous->col) : "—";
    write_line("Name: " + username);
    write_line("Current position: " + format_pos(row, col));
    write_line("Previous position: " + prev_text);
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
            top += cell_line(selected, 0);
            mid += cell_line(selected, 1);
            bot += cell_line(selected, 2);
        }
        write_line(top);
        write_line(mid);
        write_line(bot);
    }
}

bool read_direction(int& dr, int& dc) {
    const int key = std::cin.get();
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

    render(username, row, col, previous);

    while (true) {
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
        }
        render(username, row, col, previous);
    }
}

}  // namespace

int main() {
    const std::string username = read_username();
    enable_raw_mode();
    run_grid(username);
    disable_raw_mode();
    return 0;
}
