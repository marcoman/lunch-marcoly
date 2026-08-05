#include "yahoo.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cctype>
#include <curl/curl.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <thread>

using json = nlohmann::json;
namespace fs = std::filesystem;

namespace {

constexpr const char* kUserAgent =
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

const char* kYahooHosts[] = {
    "https://query1.finance.yahoo.com/v1/finance/search",
    "https://query2.finance.yahoo.com/v1/finance/search",
};

size_t write_cb(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* out = static_cast<std::string*>(userdata);
    out->append(ptr, size * nmemb);
    return size * nmemb;
}

std::string now_iso() {
    using namespace std::chrono;
    const auto secs =
        duration_cast<seconds>(system_clock::now().time_since_epoch()).count();
    return std::to_string(secs);
}

fs::path cache_path() {
    return fs::path(example_root()) / "stories" / "stories_cache.json";
}

fs::path stories_dir() {
    return fs::path(example_root()) / "stories";
}

json load_cache() {
    std::ifstream in(cache_path());
    if (!in) {
        return json{{"updated_at", nullptr}, {"tickers", json::object()}, {"last_pair", nullptr}};
    }
    try {
        json data;
        in >> data;
        if (!data.is_object()) {
            throw std::runtime_error("bad cache");
        }
        if (!data.contains("tickers") || !data["tickers"].is_object()) {
            data["tickers"] = json::object();
        }
        return data;
    } catch (...) {
        return json{{"updated_at", nullptr}, {"tickers", json::object()}, {"last_pair", nullptr}};
    }
}

void save_cache(json cache) {
    cache["updated_at"] = now_iso();
    fs::create_directories(stories_dir());
    std::ofstream out(cache_path());
    out << cache.dump(2) << '\n';
}

std::optional<TickerBlock> get_cached_ticker(const std::string& ticker) {
    const std::string symbol = normalize_ticker(ticker);
    if (symbol.empty()) {
        return std::nullopt;
    }
    auto cache = load_cache();
    if (!cache["tickers"].contains(symbol)) {
        return std::nullopt;
    }
    const auto& entry = cache["tickers"][symbol];
    if (!entry.contains("stories") || !entry["stories"].is_array() ||
        entry["stories"].empty()) {
        return std::nullopt;
    }
    TickerBlock block;
    block.ticker = symbol;
    block.name = entry.value("name", symbol);
    if (block.name.empty()) {
        block.name = symbol;
    }
    block.from_cache = true;
    int n = 0;
    for (const auto& s : entry["stories"]) {
        if (n >= 2) {
            break;
        }
        Story story;
        story.title = s.value("title", "");
        story.publisher = s.value("publisher", "");
        story.link = s.value("link", "");
        story.uuid = s.value("uuid", "");
        if (!story.title.empty()) {
            block.stories.push_back(std::move(story));
            ++n;
        }
    }
    if (block.stories.empty()) {
        return std::nullopt;
    }
    return block;
}

void remember_ticker(const std::string& symbol, const std::string& name,
                     const std::vector<Story>& stories) {
    if (stories.empty()) {
        return;
    }
    auto cache = load_cache();
    json arr = json::array();
    for (size_t i = 0; i < stories.size() && i < 2; ++i) {
        arr.push_back({{"title", stories[i].title},
                       {"publisher", stories[i].publisher},
                       {"link", stories[i].link},
                       {"uuid", stories[i].uuid}});
    }
    cache["tickers"][symbol] = {{"name", name.empty() ? symbol : name},
                                {"stories", arr},
                                {"cached_at", now_iso()}};
    save_cache(std::move(cache));
}

void remember_pair(const std::string& t1, const std::string& t2,
                   const std::vector<TickerBlock>& results) {
    if (results.size() != 2) {
        return;
    }
    for (const auto& r : results) {
        if (r.stories.empty()) {
            return;
        }
    }
    auto cache = load_cache();
    cache["last_pair"] = {{"ticker1", normalize_ticker(t1)},
                          {"ticker2", normalize_ticker(t2)}};
    for (const auto& block : results) {
        if (block.stories.empty() || block.from_cache) {
            continue;
        }
        const std::string symbol = normalize_ticker(block.ticker);
        if (symbol.empty()) {
            continue;
        }
        json arr = json::array();
        for (size_t i = 0; i < block.stories.size() && i < 2; ++i) {
            arr.push_back({{"title", block.stories[i].title},
                           {"publisher", block.stories[i].publisher},
                           {"link", block.stories[i].link},
                           {"uuid", block.stories[i].uuid}});
        }
        cache["tickers"][symbol] = {
            {"name", block.name.empty() ? symbol : block.name},
            {"stories", arr},
            {"cached_at", now_iso()}};
    }
    save_cache(std::move(cache));
}

std::string http_get(const std::string& url, long* status_out) {
    std::string body;
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw std::runtime_error("curl_easy_init failed");
    }
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_USERAGENT, kUserAgent);
    curl_easy_setopt(curl, CURLOPT_ACCEPT_ENCODING, "");
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 20L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Accept: application/json");
    headers = curl_slist_append(headers, "Accept-Language: en-US,en;q=0.9");
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    const CURLcode rc = curl_easy_perform(curl);
    long status = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    if (status_out) {
        *status_out = status;
    }
    if (rc != CURLE_OK) {
        throw std::runtime_error(curl_easy_strerror(rc));
    }
    return body;
}

json yahoo_get_json(const std::string& url) {
    std::string last_err = "Yahoo request failed";
    for (int attempt = 0; attempt < 3; ++attempt) {
        try {
            long status = 0;
            const std::string body = http_get(url, &status);
            if (status == 429 || status == 503) {
                last_err = "HTTP " + std::to_string(status);
                if (attempt < 2) {
                    std::this_thread::sleep_for(
                        std::chrono::milliseconds(1500 * (attempt + 1)));
                    continue;
                }
                throw std::runtime_error(last_err);
            }
            if (status < 200 || status >= 300) {
                throw std::runtime_error("HTTP " + std::to_string(status));
            }
            return json::parse(body);
        } catch (const std::exception& ex) {
            last_err = ex.what();
            if (attempt < 2) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                continue;
            }
        }
    }
    throw std::runtime_error(last_err);
}

std::optional<TickerBlock> parse_search_payload(const std::string& symbol,
                                                const json& payload, int count) {
    std::string name;
    if (payload.contains("quotes") && payload["quotes"].is_array() &&
        !payload["quotes"].empty()) {
        const auto& q0 = payload["quotes"][0];
        name = q0.value("shortname", "");
        if (name.empty()) {
            name = q0.value("longname", "");
        }
    }
    TickerBlock block;
    block.ticker = symbol;
    block.from_cache = false;
    if (payload.contains("news") && payload["news"].is_array()) {
        int n = 0;
        for (const auto& item : payload["news"]) {
            if (n >= count) {
                break;
            }
            Story s;
            s.title = item.value("title", "");
            // trim
            while (!s.title.empty() && std::isspace(static_cast<unsigned char>(s.title.front()))) {
                s.title.erase(s.title.begin());
            }
            while (!s.title.empty() && std::isspace(static_cast<unsigned char>(s.title.back()))) {
                s.title.pop_back();
            }
            if (s.title.empty()) {
                continue;
            }
            s.publisher = item.value("publisher", "");
            s.link = item.value("link", "");
            s.uuid = item.value("uuid", "");
            block.stories.push_back(std::move(s));
            ++n;
        }
    }
    if (block.stories.empty()) {
        return std::nullopt;
    }
    block.name = name.empty() ? symbol : name;
    return block;
}

TickerBlock fetch_stories_for_ticker(const std::string& ticker, int count) {
    const std::string symbol = normalize_ticker(ticker);
    if (symbol.empty()) {
        return {"", "", {}, "Ticker is empty.", false};
    }
    count = std::max(1, count);
    const std::string variants[] = {
        "q=" + symbol + "&quotesCount=1&newsCount=" + std::to_string(count) +
            "&enableFuzzyQuery=false&newsQueryId=news_cie_vespa&lang=en-US&region=US",
        "q=" + symbol + "&quotesCount=1&newsCount=" + std::to_string(count) +
            "&lang=en-US&region=US",
    };
    std::string last_error = "No recent stories found for " + symbol + ".";
    for (const char* host : kYahooHosts) {
        for (const auto& params : variants) {
            const std::string url = std::string(host) + "?" + params;
            try {
                const json payload = yahoo_get_json(url);
                auto parsed = parse_search_payload(symbol, payload, count);
                if (!parsed) {
                    last_error = "No recent stories found for " + symbol + ".";
                    continue;
                }
                remember_ticker(symbol, parsed->name, parsed->stories);
                return *parsed;
            } catch (const std::exception& ex) {
                const std::string msg = ex.what();
                if (msg.rfind("HTTP ", 0) == 0) {
                    last_error = "Yahoo Finance " + msg + " for " + symbol + ".";
                } else {
                    last_error = "Yahoo Finance request failed for " + symbol + ": " + msg;
                }
            }
        }
    }
    if (auto cached = get_cached_ticker(symbol)) {
        cached->error = last_error + " Showing last saved headlines.";
        return *cached;
    }
    return {symbol, symbol, {}, last_error, false};
}

}  // namespace

std::string example_root() {
    return (fs::current_path() / "..").lexically_normal().string();
}

std::string normalize_ticker(const std::string& raw) {
    std::string out;
    for (unsigned char ch : raw) {
        if (std::isspace(ch)) {
            continue;
        }
        ch = static_cast<unsigned char>(std::toupper(ch));
        if ((ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9') || ch == '.' ||
            ch == '-') {
            out.push_back(static_cast<char>(ch));
        }
    }
    return out;
}

std::optional<std::tuple<std::string, std::string, std::vector<TickerBlock>>>
get_last_pair_cached() {
    auto cache = load_cache();
    if (!cache.contains("last_pair") || cache["last_pair"].is_null() ||
        !cache["last_pair"].is_object()) {
        return std::nullopt;
    }
    const std::string t1 = normalize_ticker(cache["last_pair"].value("ticker1", ""));
    const std::string t2 = normalize_ticker(cache["last_pair"].value("ticker2", ""));
    if (t1.empty() || t2.empty()) {
        return std::nullopt;
    }
    std::vector<TickerBlock> blocks;
    for (const auto& symbol : {t1, t2}) {
        auto cached = get_cached_ticker(symbol);
        if (!cached) {
            return std::nullopt;
        }
        blocks.push_back(*cached);
    }
    return std::make_tuple(t1, t2, blocks);
}

FetchPairResult fetch_stories_for_tickers(const std::string& ticker1,
                                          const std::string& ticker2, int count) {
    std::string t1 = normalize_ticker(ticker1);
    if (t1.empty()) {
        t1 = kDefaultTicker1;
    }
    std::string t2 = normalize_ticker(ticker2);
    if (t2.empty()) {
        t2 = kDefaultTicker2;
    }
    auto first = fetch_stories_for_ticker(t1, count);
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    auto second = fetch_stories_for_ticker(t2, count);
    std::vector<TickerBlock> results{std::move(first), std::move(second)};
    remember_pair(t1, t2, results);
    FetchPairResult out;
    out.ticker1 = t1;
    out.ticker2 = t2;
    out.tickers = std::move(results);
    for (const auto& r : out.tickers) {
        if (!r.error.empty()) {
            out.errors.push_back(r.error);
        }
    }
    return out;
}

std::string format_stories_for_prompt(const std::vector<TickerBlock>& ticker_results) {
    std::ostringstream b;
    b << "Using only the recent Yahoo Finance headlines below, write a short "
         "market briefing that compares the two tickers. Cite story titles "
         "where helpful. Do not invent facts beyond what the headlines imply.\n\n";
    for (const auto& block : ticker_results) {
        const std::string ticker = block.ticker.empty() ? "?" : block.ticker;
        const std::string name = block.name.empty() ? ticker : block.name;
        b << "## " << ticker << " (" << name << ")\n";
        if (block.stories.empty()) {
            b << "- (no stories available)\n";
            if (!block.error.empty()) {
                b << "- note: " << block.error << "\n";
            }
        } else {
            for (size_t i = 0; i < block.stories.size(); ++i) {
                const auto& s = block.stories[i];
                const std::string title = s.title.empty() ? "(untitled)" : s.title;
                const std::string publisher =
                    s.publisher.empty() ? "unknown" : s.publisher;
                b << (i + 1) << ". " << title << " — " << publisher << "\n";
            }
        }
        b << "\n";
    }
    std::string text = b.str();
    while (!text.empty() && (text.back() == '\n' || text.back() == ' ')) {
        text.pop_back();
    }
    return text;
}
