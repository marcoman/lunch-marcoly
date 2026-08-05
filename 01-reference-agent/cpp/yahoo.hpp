#pragma once

#include <optional>
#include <string>
#include <tuple>
#include <vector>

struct Story {
    std::string title;
    std::string publisher;
    std::string link;
    std::string uuid;
};

struct TickerBlock {
    std::string ticker;
    std::string name;
    std::vector<Story> stories;
    std::string error;  // empty if none
    bool from_cache = false;
};

struct FetchPairResult {
    std::vector<TickerBlock> tickers;
    std::vector<std::string> errors;
    std::string ticker1;
    std::string ticker2;
};

inline constexpr const char* kDefaultTicker1 = "NVDA";
inline constexpr const char* kDefaultTicker2 = "SPCX";

std::string example_root();
std::string normalize_ticker(const std::string& raw);
std::optional<std::tuple<std::string, std::string, std::vector<TickerBlock>>>
get_last_pair_cached();
FetchPairResult fetch_stories_for_tickers(const std::string& ticker1,
                                          const std::string& ticker2,
                                          int count = 2);
std::string format_stories_for_prompt(const std::vector<TickerBlock>& ticker_results);
