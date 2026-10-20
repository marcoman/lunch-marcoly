// Console grid navigator for LaunchDarkly scheduled flag changes.

#include "flags.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

namespace {

constexpr std::array<const char*, 3> kRows = {"t", "m", "b"};
constexpr std::array<const char*, 3> kCols = {"l", "m", "r"};
constexpr std::array<int, 4> kDelays = {1, 2, 5, 10};
constexpr const char* kBanner = "17-scheduled-changes[cpp]";
constexpr const char* kBg = "\033[48;5;236m";
constexpr const char* kReset = "\033[0m";
constexpr const char* kGreen = "\033[92m";

struct Position { int row; int col; };
enum class Action { kQuit, kLogout };
termios g_original{};

std::int64_t now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
}
std::string format_pos(int row, int col) { return std::string(kRows[row]) + "/" + kCols[col]; }
std::string clock_text(std::int64_t ms) {
    const auto seconds = std::max<std::int64_t>(0, ms) / 1000;
    std::ostringstream out; out << seconds / 60 << ':' << std::setfill('0') << std::setw(2) << seconds % 60;
    return out.str();
}
std::string wall(std::int64_t ms) {
    if (ms == 0) return "—";
    const std::time_t seconds = ms / 1000;
    std::tm local{}; localtime_r(&seconds, &local);
    std::ostringstream out; out << std::put_time(&local, "%H:%M:%S"); return out.str();
}
std::string colorize(const std::string& text, const std::string& value) {
    return value == "green" ? std::string(kGreen) + text + kReset + kBg : text;
}
void line(const std::string& text) { std::cout << text << "\033[K\r\n"; }

void enable_raw_mode() {
    tcgetattr(STDIN_FILENO, &g_original);
    termios raw = g_original;
    raw.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
    raw.c_cc[VMIN] = 0; raw.c_cc[VTIME] = 5;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
    std::cout << "\033[?1049h\033[2J\033[H" << std::flush;
}
void disable_raw_mode() {
    std::cout << "\033[?1049l" << kReset << std::flush;
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &g_original);
}
std::string read_username() {
    std::cout << kBanner << "\nLogin\nUsername becomes the LaunchDarkly user context key.\n\n";
    std::string value;
    do { std::cout << "Username: "; std::getline(std::cin, value); if (value.empty()) std::cout << "Username is required.\n"; }
    while (value.empty());
    return value;
}
std::string cell(bool selected, const std::string& value, int part) {
    if (selected) return colorize(std::array<const char*,3>{"┏━━━┓","┃ X ┃","┗━━━┛"}[part], value);
    return std::array<const char*,3>{"┌───┐","│   │","└───┘"}[part];
}

void render(const std::string& username, int row, int col, const std::optional<Position>& previous,
        const FlagValues& flags, int delay, std::int64_t started, std::int64_t stopped,
        std::int64_t observed, std::int64_t execution, bool pending,
        const ScheduleState& rest, const std::string& error) {
    std::cout << kBg << "\033[2J\033[H";
    const std::int64_t end = stopped != 0 ? stopped : now_ms();
    const std::string elapsed = started != 0 ? clock_text(end - started) : "0:00";
    std::string status = "No pending change.";
    std::string timing = "G starts a schedule. T stops it and turns the flag off.";
    if (pending) {
        status = "PENDING · LaunchDarkly will turn the flag on";
        timing = "Scheduled wall time: " + wall(execution);
    } else if (stopped != 0) {
        status = "STOPPED · pending change cancelled, flag off";
        timing = "Stopped at " + wall(stopped);
        if (started != 0) timing += " after " + clock_text(stopped - started) + " elapsed.";
    } else if (flags.flagValue == "green" && started != 0) {
        status = "APPLIED · SDK now serves green";
        timing = "Scheduled for " + wall(execution);
        if (observed != 0) timing += "; green first observed here at " + clock_text(observed - started);
    }
    line(kBanner);
    line("Name: " + colorize(username, flags.flagValue));
    line("Current: " + format_pos(row,col) + "   Previous: "
         + (previous ? format_pos(previous->row,previous->col) : "—"));
    line("Flag value: " + flags.flagValue + "   reason: " + flags.reasonKind + "   idx: " + flags.variationIndex);
    line("Delay: " + std::to_string(delay) + " min   Elapsed: " + elapsed);
    line(status); line(timing);
    line(rest.configured ? "REST configured" : "REST disabled — set " + rest.missing);
    line("G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit");
    line("Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms.");
    if (!error.empty()) line(error);
    line("");
    for (int r=0;r<3;++r) for (int part=0;part<3;++part) {
        std::string cells;
        for (int c=0;c<3;++c) { if(c>0)cells+=' '; cells += cell(r==row&&c==col,flags.flagValue,part); }
        line(cells);
    }
    std::cout << std::flush;
}

int read_key() {
    fd_set set; FD_ZERO(&set); FD_SET(STDIN_FILENO,&set);
    timeval timeout{0,500000};
    if (select(STDIN_FILENO+1,&set,nullptr,nullptr,&timeout)<=0) return -1;
    return std::cin.get();
}
void move(int& row,int& col,std::optional<Position>& previous,int dr,int dc) {
    const int nr=std::clamp(row+dr,0,2),nc=std::clamp(col+dc,0,2);
    if(nr!=row||nc!=col){previous=Position{row,col};row=nr;col=nc;}
}

Action run_grid(const std::string& username) {
    int row=1,col=1,delay_index=0; std::optional<Position> previous;
    std::int64_t started=0,stopped=0,observed=0,execution=0;
    bool pending=false; std::string error;
    ScheduleState rest = list_schedule();
    while(true) {
        const FlagValues flags=evaluate_flags(username);
        if(started!=0&&stopped==0&&observed==0&&flags.flagValue=="green") observed=now_ms();
        const ScheduleState listed=list_schedule();
        if(listed.ok) {
            rest=listed; pending=listed.pending;
            if(pending){execution=listed.executionDate;if(started==0)started=listed.startedAt;}
        }
        render(username,row,col,previous,flags,kDelays[delay_index],started,stopped,observed,execution,pending,rest,error);
        int key=read_key(); if(key<0)continue;
        if(key=='q'||key=='Q'||key==3)return Action::kQuit;
        if(key=='l'||key=='L')return Action::kLogout;
        if(key=='m'||key=='M'){delay_index=(delay_index+1)%4;continue;}
        if(key=='1'){delay_index=0;continue;} if(key=='2'){delay_index=1;continue;}
        if(key=='5'){delay_index=2;continue;} if(key=='0'){delay_index=3;continue;}
        if(key=='g'||key=='G'){
            const auto result=start_schedule(kDelays[delay_index]);
            if(result.ok){started=result.startedAt;stopped=0;observed=0;execution=result.executionDate;pending=true;error.clear();}
            else error=result.error;
            continue;
        }
        if(key=='t'||key=='T'){
            const auto result=stop_schedule();
            if(result.ok){stopped=result.stoppedAt;pending=false;error.clear();}else error=result.error;
            continue;
        }
        int dr=0,dc=0;
        if(key==27){if(std::cin.get()!=91)continue;const int arrow=std::cin.get();
            if(arrow==65)dr=-1;else if(arrow==66)dr=1;else if(arrow==67)dc=1;else if(arrow==68)dc=-1;else continue;}
        else if(key=='w'||key=='W')dr=-1;else if(key=='s'||key=='S')dr=1;
        else if(key=='a'||key=='A')dc=-1;else if(key=='d'||key=='D')dc=1;else continue;
        move(row,col,previous,dr,dc);
    }
}

}  // namespace

int main() {
    init_launchdarkly();
    while(true){const auto username=read_username();enable_raw_mode();const auto action=run_grid(username);disable_raw_mode();if(action==Action::kQuit)break;}
    return 0;
}
