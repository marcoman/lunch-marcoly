#pragma once

#include "yahoo.hpp"

#include <functional>
#include <optional>
#include <string>
#include <vector>

struct Persona {
    const char* id;
    const char* name;
    const char* profile;
};

struct Metrics {
    std::optional<long long> latency_ms;
    std::optional<long long> ttft_ms;
    std::optional<int> prompt_tokens;
    std::optional<int> completion_tokens;
    std::optional<int> total_tokens;
    std::string finish_reason;
};

struct StreamEvent {
    enum class Type { Meta, Token, Error, Metrics, Done } type;
    std::string provider;
    std::string model;
    std::string mode;
    std::string input;
    std::string text;
    std::string message;
    Metrics metrics;
};

inline const Persona kPersonas[] = {
    {"conservative-charlie", "Conservative Charlie", "conservative"},
    {"neutral-nancy", "Neutral Nancy", "neutral"},
    {"thoughtless-toby", "Thoughtless Toby", "risk-taker"},
};
inline constexpr size_t kPersonaCount = 3;

void set_mode_override(const std::string& mode);
std::string resolve_mode();
std::string model_label(const std::string& mode);
std::string ollama_host();
bool probe_ollama(int timeout_ms = 600);
std::string ensure_llm_mode();
void generate_stream(const Persona& persona,
                     const std::vector<TickerBlock>& ticker_results,
                     const std::function<void(const StreamEvent&)>& on_event);
