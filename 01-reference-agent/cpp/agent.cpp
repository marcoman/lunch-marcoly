#include "agent.hpp"

#include <nlohmann/json.hpp>

#include <cctype>
#include <chrono>
#include <cstdlib>
#include <curl/curl.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <thread>

using json = nlohmann::json;
namespace fs = std::filesystem;

namespace {

constexpr const char* kCannedInput =
    "No ticker stories loaded yet. Ask the user to click Get Stories, "
    "then produce a brief placeholder note that you are waiting for headlines.";
constexpr const char* kDefaultBedrockModelId = "us.amazon.nova-lite-v1:0";

std::string g_mode_override;

std::string trim_copy(std::string s) {
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) {
        s.erase(s.begin());
    }
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) {
        s.pop_back();
    }
    return s;
}

std::string lower_copy(std::string s) {
    for (char& ch : s) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return s;
}

std::string env_or(const char* key, const char* fallback) {
    if (const char* v = std::getenv(key)) {
        std::string s = trim_copy(v);
        if (!s.empty()) {
            return s;
        }
    }
    return fallback ? fallback : "";
}

std::string load_system_prompt() {
    const fs::path path = fs::path(example_root()) / "prompts" / "system_prompt.txt";
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("could not read system prompt at " + path.string());
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    std::string text = trim_copy(ss.str());
    if (text.empty()) {
        throw std::runtime_error("system prompt file is empty: " + path.string());
    }
    return text;
}

std::string build_user_input(const std::vector<TickerBlock>& ticker_results) {
    if (ticker_results.empty()) {
        return kCannedInput;
    }
    return format_stories_for_prompt(ticker_results);
}

int estimate_tokens(const std::string& text) {
    return std::max(1, static_cast<int>(text.size() / 4));
}

void fill_token_estimates(const std::string& completion, Metrics& m,
                          const std::string& user_input) {
    std::string sys;
    try {
        sys = load_system_prompt();
    } catch (...) {
    }
    m.prompt_tokens = estimate_tokens(sys + user_input);
    m.completion_tokens = estimate_tokens(completion);
    m.total_tokens = *m.prompt_tokens + *m.completion_tokens;
}

std::string stub_response(const Persona& persona,
                          const std::vector<TickerBlock>& ticker_results) {
    std::ostringstream b;
    b << "[stub / default-no-llm]\n";
    b << "Persona: " << persona.name << " (" << persona.profile << ")\n\n";
    b << "Headline briefing (stub):\n";
    if (ticker_results.empty()) {
        b << "- (no stories loaded — click Get Stories)\n";
    } else {
        for (const auto& block : ticker_results) {
            const std::string ticker = block.ticker.empty() ? "?" : block.ticker;
            b << "- " << ticker << ":\n";
            if (block.stories.empty()) {
                b << "  (no stories)\n";
            }
            for (const auto& s : block.stories) {
                b << "  • " << (s.title.empty() ? "(untitled)" : s.title) << "\n";
            }
        }
    }
    b << "\nAs a " << persona.profile
      << " analyst, this is boilerplate report text for UI testing. "
         "Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.";
    return b.str();
}

size_t write_cb(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* out = static_cast<std::string*>(userdata);
    out->append(ptr, size * nmemb);
    return size * nmemb;
}

struct StreamBuf {
    std::string buffer;
    std::function<void(const std::string&)> on_chunk;
    std::string error;
};

size_t stream_write_cb(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* sb = static_cast<StreamBuf*>(userdata);
    sb->buffer.append(ptr, size * nmemb);
    size_t pos = 0;
    while (true) {
        const auto nl = sb->buffer.find('\n', pos);
        if (nl == std::string::npos) {
            break;
        }
        std::string line = sb->buffer.substr(pos, nl - pos);
        pos = nl + 1;
        while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {
            line.pop_back();
        }
        if (line.empty()) {
            continue;
        }
        try {
            const json data = json::parse(line);
            if (data.contains("error") && !data["error"].is_null()) {
                sb->error = data["error"].dump();
                continue;
            }
            if (data.contains("message") && data["message"].is_object()) {
                const std::string content = data["message"].value("content", "");
                if (!content.empty() && sb->on_chunk) {
                    sb->on_chunk(content);
                }
            }
        } catch (...) {
            // skip malformed line
        }
    }
    if (pos > 0) {
        sb->buffer.erase(0, pos);
    }
    return size * nmemb;
}

void ollama_stream(const std::string& model,
                   const std::vector<TickerBlock>& ticker_results,
                   const std::function<void(const std::string&)>& on_chunk) {
    const std::string sys = load_system_prompt();
    json body = {{"model", model},
                 {"stream", true},
                 {"messages",
                  json::array({{{"role", "system"}, {"content", sys}},
                               {{"role", "user"},
                                {"content", build_user_input(ticker_results)}}})}};
    const std::string payload = body.dump();
    const std::string host = ollama_host();
    const std::string url = host + "/api/chat";

    StreamBuf sb;
    sb.on_chunk = on_chunk;
    CURL* curl = curl_easy_init();
    if (!curl) {
        throw std::runtime_error("curl_easy_init failed");
    }
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 120L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, stream_write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &sb);
    const CURLcode rc = curl_easy_perform(curl);
    long status = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    if (rc != CURLE_OK) {
        throw std::runtime_error("Ollama request failed (" + host + "): " +
                                 curl_easy_strerror(rc) +
                                 ". Is Ollama running, and is OLLAMA_MODEL pulled?");
    }
    if (status < 200 || status >= 300) {
        throw std::runtime_error("Ollama request failed (" + host + "): HTTP " +
                                 std::to_string(status) +
                                 ". Is Ollama running, and is OLLAMA_MODEL pulled?");
    }
    if (!sb.error.empty()) {
        throw std::runtime_error(sb.error);
    }
}

}  // namespace

void set_mode_override(const std::string& mode) {
    const std::string cleaned = lower_copy(trim_copy(mode));
    if (cleaned.empty()) {
        g_mode_override.clear();
        return;
    }
    if (cleaned == "stub" || cleaned == "ollama" || cleaned == "bedrock" ||
        cleaned == "anthropic") {
        g_mode_override = cleaned;
    } else {
        g_mode_override = "stub";
    }
}

std::string resolve_mode() {
    std::string mode = g_mode_override;
    if (mode.empty()) {
        mode = lower_copy(trim_copy(env_or("AGENT_LLM_MODE", "stub")));
    }
    if (mode == "stub" || mode == "ollama" || mode == "bedrock" ||
        mode == "anthropic") {
        return mode;
    }
    return "stub";
}

std::string model_label(const std::string& mode) {
    const std::string override_model = env_or("AGENT_LLM_MODEL", "");
    if (!override_model.empty()) {
        return override_model;
    }
    if (mode == "stub") {
        return "default-no-llm";
    }
    if (mode == "ollama") {
        return env_or("OLLAMA_MODEL", "llama3.2:3b");
    }
    if (mode == "bedrock") {
        return env_or("AGENT_BEDROCK_MODEL_ID", kDefaultBedrockModelId);
    }
    if (mode == "anthropic") {
        return env_or("ANTHROPIC_MODEL", "claude-3-haiku-20240307");
    }
    return "(unknown)";
}

std::string ollama_host() {
    std::string host = env_or("OLLAMA_HOST", "http://127.0.0.1:11434");
    while (!host.empty() && host.back() == '/') {
        host.pop_back();
    }
    return host;
}

bool probe_ollama(int timeout_ms) {
    const std::string url = ollama_host() + "/api/tags";
    std::string body;
    CURL* curl = curl_easy_init();
    if (!curl) {
        return false;
    }
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, static_cast<long>(timeout_ms));
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
    const CURLcode rc = curl_easy_perform(curl);
    long status = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);
    curl_easy_cleanup(curl);
    return rc == CURLE_OK && status >= 200 && status < 300;
}

std::string ensure_llm_mode() {
    if (const char* v = std::getenv("AGENT_LLM_MODE")) {
        if (!trim_copy(v).empty()) {
            return resolve_mode();
        }
    }
    if (probe_ollama(600)) {
        setenv("AGENT_LLM_MODE", "ollama", 1);
    } else {
        setenv("AGENT_LLM_MODE", "stub", 1);
    }
    return resolve_mode();
}

void generate_stream(const Persona& persona,
                     const std::vector<TickerBlock>& ticker_results,
                     const std::function<void(const StreamEvent&)>& on_event) {
    const std::string mode = resolve_mode();
    const std::string model = model_label(mode);
    const std::string user_input = build_user_input(ticker_results);

    StreamEvent meta;
    meta.type = StreamEvent::Type::Meta;
    meta.provider = mode;
    meta.model = model;
    meta.mode = mode;
    meta.input = user_input;
    on_event(meta);

    const auto started = std::chrono::steady_clock::now();
    Metrics metrics;

    auto elapsed_ms = [&]() -> long long {
        return std::chrono::duration_cast<std::chrono::milliseconds>(
                   std::chrono::steady_clock::now() - started)
            .count();
    };

    try {
        if (mode == "stub") {
            const std::string text = stub_response(persona, ticker_results);
            bool first = true;
            for (size_t i = 0; i < text.size(); i += 12) {
                if (first) {
                    metrics.ttft_ms = elapsed_ms();
                    first = false;
                }
                StreamEvent ev;
                ev.type = StreamEvent::Type::Token;
                ev.text = text.substr(i, 12);
                on_event(ev);
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
            }
            metrics.finish_reason = "stop";
            fill_token_estimates(text, metrics, user_input);
        } else if (mode == "ollama") {
            std::string parts;
            bool first = true;
            ollama_stream(model, ticker_results, [&](const std::string& chunk) {
                if (first) {
                    metrics.ttft_ms = elapsed_ms();
                    first = false;
                }
                parts += chunk;
                StreamEvent ev;
                ev.type = StreamEvent::Type::Token;
                ev.text = chunk;
                on_event(ev);
            });
            metrics.finish_reason = "stop";
            fill_token_estimates(parts, metrics, user_input);
        } else if (mode == "bedrock") {
            StreamEvent ev;
            ev.type = StreamEvent::Type::Error;
            ev.message =
                "Mode 'bedrock' is not wired in the C++ example yet. "
                "Use AGENT_LLM_MODE=stub or ollama here, or run the Python web app "
                "for Bedrock.";
            on_event(ev);
            metrics.finish_reason = "error";
        } else {
            StreamEvent ev;
            ev.type = StreamEvent::Type::Error;
            ev.message = "Mode '" + mode +
                         "' is configured but not implemented in this reference yet. "
                         "Use AGENT_LLM_MODE=stub or ollama.";
            on_event(ev);
            metrics.finish_reason = "error";
        }
    } catch (const std::exception& ex) {
        StreamEvent ev;
        ev.type = StreamEvent::Type::Error;
        ev.message = ex.what();
        on_event(ev);
        metrics.finish_reason = "error";
    }

    metrics.latency_ms = elapsed_ms();
    StreamEvent m_ev;
    m_ev.type = StreamEvent::Type::Metrics;
    m_ev.metrics = metrics;
    on_event(m_ev);
    StreamEvent done;
    done.type = StreamEvent::Type::Done;
    on_event(done);
}
