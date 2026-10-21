// agent.go — domain logic for 23-agent-tools[go] (no TUI code here).
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
// Same equity-briefing product as 21-agent-completion-config, but the served
// completion variation also carries LaunchDarkly **Library tools**. Instead of
// one model call, generate runs a **model-driven tool loop**: the model must
// call analyze-ticker-stories once per ticker, then compare-ticker-analyses,
// before writing the briefing — grounding claims in headline evidence instead
// of letting the model invent them.
//
//  1. Data          Personas — LOCAL provider/model choice, not LD name targeting
//  2. LaunchDarkly  CompletionConfig (tool schemas ride on the variation)
//  3. Tools         Deterministic handlers + schema conversion (Anthropic / OpenAI shapes)
//  4. Providers     Anthropic (cloud) or Ollama (local) tool-calling loops
//  5. Generation    generateStream() — evaluate config, run the tool loop, stream the briefing
//
// LaunchDarkly insertion points (read these first):
//
//	evaluateCompletion()      → aiClient.CompletionConfig(...)   — model + messages + tools
//	runAnthropicToolLoop() /
//	runOllamaToolLoop()       → tracker.TrackToolCall(name)       — one event per dispatched tool
//	                          → ldai.TrackMetricsOf(tracker, ...) — request latency + token usage
//
// Docs: https://launchdarkly.com/docs/home/agentcontrol/tools · https://launchdarkly.com/docs/sdk/ai/go
// Keywords: AgentControl · Library tools · CompletionConfig · TrackToolCall · TrackMetricsOf
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk-ai/ldai"
	"github.com/launchdarkly/go-server-sdk-ai/ldai/datamodel"
	ldclient "github.com/launchdarkly/go-server-sdk/v7"
)

// ---------------------------------------------------------------------------
// 1. Data — demo personas (LOCAL provider/model choice; not LD name targeting)
// ---------------------------------------------------------------------------

const (
	cannedStories = "No ticker stories loaded yet. Ask the user to click Get Stories."

	// LaunchDarkly: ai-config key=equity-briefing-tools name="Equity briefing tools" mode=completion
	// Tools: analyze-ticker-stories · compare-ticker-analyses
	// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tools
	defaultConfigKey          = "equity-briefing-tools"
	defaultAnthropicModelName = "claude-sonnet-5"
	// Tool-capable local default (1b is too weak for reliable tool loops).
	defaultOllamaModelName = "llama3.2:3b"

	toolAnalyze  = "analyze-ticker-stories"
	toolCompare  = "compare-ticker-analyses"
	maxToolSteps = 6
)

// ollamaToolSuffix is extra system guidance for small local models (Ollama personas).
const ollamaToolSuffix = "Local-model rules (Ollama):\n" +
	"- You MUST call tools before writing any briefing.\n" +
	"- One tool call per turn when possible: analyze ticker 1, then analyze ticker 2, " +
	"then compare-ticker-analyses.\n" +
	"- Never call compare in the same turn as analyze.\n" +
	"- Pass the exact analyze JSON as analysis_a / analysis_b — do not invent fields.\n" +
	"- Do not skip compare-ticker-analyses after two analyzes."

var positiveWords = boolSet(
	"surge", "soar", "gain", "gains", "rise", "rises", "jump", "jumps", "beat", "beats",
	"record", "growth", "upgrade", "bullish", "profit", "profits", "strong", "rally",
)

var negativeWords = boolSet(
	"fall", "falls", "drop", "drops", "plunge", "cut", "cuts", "miss", "misses", "loss",
	"losses", "downgrade", "bearish", "weak", "lawsuit", "probe", "decline", "risk", "risks",
)

func boolSet(words ...string) map[string]bool {
	set := make(map[string]bool, len(words))
	for _, w := range words {
		set[w] = true
	}
	return set
}

var wordPattern = regexp.MustCompile(`[a-zA-Z]+`)

// persona is the selectable demo identity. Profile/Model are a LOCAL app
// routing choice (Anthropic vs. Ollama, which Ollama tag) — LaunchDarkly does
// not target on persona name here; every persona evaluates the same variation.
type persona struct {
	ID        string
	Name      string
	Profile   string // "anthropic" or "ollama"
	Model     string // pinned Ollama tag; empty for Claude
	Anonymous bool
}

var personas = []persona{
	{ID: "analyst-claude", Name: "Analyst Claude", Profile: "anthropic"},
	{ID: "analyst-llama", Name: "Analyst Llama", Profile: "ollama", Model: "llama3.2:3b"},
	// Smaller sibling — expect more skips; Ollama guardrails still apply.
	{ID: "analyst-gwen", Name: "Analyst Gwen", Profile: "ollama", Model: "llama3.2:1b"},
}

type metrics struct {
	LatencyMS        *int
	TTFTMS           *int
	PromptTokens     *int
	CompletionTokens *int
	TotalTokens      *int
	FinishReason     string
}

func (m *metrics) addTokens(prompt, completion int) {
	p := intOrZero(m.PromptTokens) + prompt
	c := intOrZero(m.CompletionTokens) + completion
	t := p + c
	m.PromptTokens = &p
	m.CompletionTokens = &c
	m.TotalTokens = &t
}

func intOrZero(v *int) int {
	if v == nil {
		return 0
	}
	return *v
}

// toolTrace is the payload of a "tool" streamEvent — one per dispatched tool call.
type toolTrace struct {
	Name      string
	Args      map[string]any
	Result    map[string]any
	CallIndex int
	Round     string // "1".."MAX_TOOL_STEPS", or "guardrail"
}

type streamEvent struct {
	Type      string
	Persona   persona
	Input     string
	Provider  string
	Model     string
	Mode      string
	ConfigKey string
	Fallback  bool
	Tools     []string
	Text      string
	Message   string
	Metrics   metrics
	Tool      toolTrace
}

func configKey() string {
	if v := strings.TrimSpace(os.Getenv("LD_AGENT_CONFIG_KEY")); v != "" {
		return v
	}
	return defaultConfigKey
}

func defaultAnthropicModel() string {
	if v := strings.TrimSpace(os.Getenv("ANTHROPIC_MODEL")); v != "" {
		return v
	}
	return defaultAnthropicModelName
}

func defaultOllamaModel() string {
	if v := strings.TrimSpace(os.Getenv("OLLAMA_MODEL")); v != "" {
		return v
	}
	return defaultOllamaModelName
}

func ollamaHost() string {
	host := strings.TrimSpace(os.Getenv("OLLAMA_HOST"))
	if host == "" {
		host = "http://127.0.0.1:11434"
	}
	return strings.TrimRight(host, "/")
}

// personaRuntime is the preferred LLM runtime for this UI persona (local app choice).
func personaRuntime(p persona) string {
	switch strings.ToLower(strings.TrimSpace(p.Profile)) {
	case "ollama", "local", "gwen", "llama":
		return "ollama"
	default:
		return "anthropic"
	}
}

// personaModelName resolves (provider, model) for this persona. LaunchDarkly
// supplies the Anthropic model on the variation; Ollama personas use the
// pinned persona.Model (or OLLAMA_MODEL / default).
func personaModelName(p persona, ldModel string) (provider, model string) {
	if personaRuntime(p) == "ollama" {
		pinned := strings.TrimSpace(p.Model)
		if pinned == "" {
			pinned = defaultOllamaModel()
		}
		return "ollama", pinned
	}
	if strings.HasPrefix(ldModel, "claude") {
		return "anthropic", ldModel
	}
	return "anthropic", defaultAnthropicModel()
}

func baselineMessagesDir() string {
	return filepath.Join(exampleRoot(), "rest", "messages")
}

func readMessageFile(name string) (string, error) {
	path := filepath.Join(baselineMessagesDir(), name)
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("could not read baseline message file %s: %w", path, err)
	}
	return string(raw), nil
}

func baselineSystemPrompt() string {
	text, err := readMessageFile("baseline-system.txt")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

func baselineUserTemplate() string {
	text, err := readMessageFile("baseline-user.txt")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

// storiesAsPromptText is plain-text headlines for {{ stories }} — avoids
// Mustache HTML-escaping of JSON quotes (see go-server-sdk-ai's client.go).
func storiesAsPromptText(blocks []tickerBlock) string {
	if len(blocks) == 0 {
		return cannedStories
	}
	var lines []string
	for _, block := range blocks {
		ticker := strings.ToUpper(strings.TrimSpace(block.Ticker))
		if ticker == "" {
			ticker = "?"
		}
		name := strings.TrimSpace(block.Name)
		if name == "" {
			name = ticker
		}
		lines = append(lines, fmt.Sprintf("%s (%s)", ticker, name))
		if len(block.Stories) == 0 {
			lines = append(lines, "  - (no stories available)")
			if block.Error != "" {
				lines = append(lines, "  - note: "+block.Error)
			}
		} else {
			for i, s := range block.Stories {
				title := strings.TrimSpace(s.Title)
				if title == "" {
					title = "(untitled)"
				}
				source := formatStorySource(s)
				if source == "" {
					source = "unknown"
				}
				lines = append(lines, fmt.Sprintf("  %d. %s — %s", i+1, title, source))
			}
		}
		lines = append(lines, "")
	}
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

// ---------------------------------------------------------------------------
// 2. LaunchDarkly — server SDK + AI SDK (AgentControl completion + tools)
// ---------------------------------------------------------------------------

var (
	sdkClient *ldclient.LDClient
	aiClient  *ld.Client
)

// initLaunchDarkly initializes the shared LaunchDarkly clients once at process start.
//
// LaunchDarkly: server-side SDK + AI SDK for AgentControl completion configs.
// https://launchdarkly.com/docs/sdk/ai/go
func initLaunchDarkly() error {
	if aiClient != nil {
		return nil
	}

	sdkKey := strings.TrimSpace(os.Getenv("LD_SDK_KEY"))
	if sdkKey == "" {
		return fmt.Errorf(
			"LD_SDK_KEY is required. Export a server-side SDK key for the environment that targets %s",
			configKey(),
		)
	}

	client, err := ldclient.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		return fmt.Errorf("LaunchDarkly client failed to initialize within 5s: %w. "+
			"Check LD_SDK_KEY and network access to LaunchDarkly", err)
	}
	if !client.Initialized() {
		return fmt.Errorf("LaunchDarkly client failed to initialize within 5s. " +
			"Check LD_SDK_KEY and network access to LaunchDarkly")
	}

	aic, err := ld.NewClient(client)
	if err != nil {
		_ = client.Close()
		return fmt.Errorf("could not create LaunchDarkly AI client: %w", err)
	}

	sdkClient = client
	aiClient = aic
	return nil
}

// buildContext builds the LD evaluation context for this persona. Every
// persona evaluates the same equity-briefing-tools variation — this context
// exists for Tracker attribution on the Monitoring tab, not for targeting.
func buildContext(p persona) ldcontext.Context {
	builder := ldcontext.NewBuilder(p.ID).Name(p.Name)
	if p.Anonymous {
		builder.Anonymous(true)
	}
	return builder.Build()
}

// baselineCompletionDefault is the SDK default when the config key is missing,
// unreachable, or turned off. It carries no tools — the tool loop requires a
// live AgentControl config (see generateStream()'s fallback branch).
func baselineCompletionDefault() ld.AICompletionConfigDefault {
	return ld.NewAICompletionConfigDefault().
		WithEnabled(true).
		WithModelName(defaultAnthropicModel()).
		WithProviderName("anthropic").
		WithMessage(baselineSystemPrompt(), datamodel.System).
		WithMessage(baselineUserTemplate(), datamodel.User)
}

// evaluateCompletion fetches model + messages + attached Library tools from
// AgentControl (completion mode).
//
// LaunchDarkly capability: CompletionConfig evaluation with Library tools.
// https://launchdarkly.com/docs/home/agentcontrol/tools
func evaluateCompletion(p persona, storiesText string) ld.AICompletionConfig {
	variables := map[string]interface{}{"stories": storiesText}
	return aiClient.CompletionConfig(configKey(), buildContext(p), baselineCompletionDefault(), variables)
}

func messagesAsMaps(messages []datamodel.Message) []map[string]string {
	out := make([]map[string]string, 0, len(messages))
	for _, m := range messages {
		out = append(out, map[string]string{"role": string(m.Role), "content": m.Content})
	}
	return out
}

func userMessageText(messages []map[string]string) string {
	for i := len(messages) - 1; i >= 0; i-- {
		if messages[i]["role"] == "user" {
			return messages[i]["content"]
		}
	}
	return ""
}

// ---------------------------------------------------------------------------
// 3. Tools — schema conversion + deterministic handlers
// ---------------------------------------------------------------------------

// toolParameters converts a Library tool's JSON-schema parameters (a
// map[string]ldvalue.Value of top-level schema keys) into plain JSON.
func toolParameters(t ld.ToolConfig) map[string]any {
	obj := map[string]any{}
	for k, v := range t.Parameters() {
		obj[k] = v.AsArbitraryValue()
	}
	if _, ok := obj["type"]; !ok {
		obj["type"] = "object"
	}
	if _, ok := obj["properties"]; !ok {
		obj["properties"] = map[string]any{}
	}
	return obj
}

// ldToolsToAnthropic converts config.Tools() to Anthropic tools= shape.
// Sorted by name for deterministic ordering (Go map iteration is randomized).
func ldToolsToAnthropic(tools map[string]ld.ToolConfig) []map[string]any {
	out := make([]map[string]any, 0, len(tools))
	for key, tool := range tools {
		name := tool.Name()
		if name == "" {
			name = key
		}
		out = append(out, map[string]any{
			"name":         name,
			"description":  tool.Description(),
			"input_schema": toolParameters(tool),
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i]["name"].(string) < out[j]["name"].(string) })
	return out
}

// ldToolsToOpenAI converts config.Tools() to OpenAI/Ollama Chat Completions tools= shape.
func ldToolsToOpenAI(tools map[string]ld.ToolConfig) []map[string]any {
	out := make([]map[string]any, 0, len(tools))
	for key, tool := range tools {
		name := tool.Name()
		if name == "" {
			name = key
		}
		out = append(out, map[string]any{
			"type": "function",
			"function": map[string]any{
				"name":        name,
				"description": tool.Description(),
				"parameters":  toolParameters(tool),
			},
		})
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i]["function"].(map[string]any)["name"].(string) <
			out[j]["function"].(map[string]any)["name"].(string)
	})
	return out
}

func dispatchTool(name string, args map[string]any) map[string]any {
	switch name {
	case toolAnalyze:
		return handleAnalyzeTickerStories(args)
	case toolCompare:
		return handleCompareTickerAnalyses(args)
	default:
		return map[string]any{"error": fmt.Sprintf("Unknown tool: %s", name)}
	}
}

// looksLikeAnalyzeResult reports whether obj resembles handleAnalyzeTickerStories output.
func looksLikeAnalyzeResult(obj map[string]any) bool {
	_, hasTicker := obj["ticker"]
	_, hasTone := obj["tone_score"]
	_, hasClaims := obj["claims"]
	return hasTicker && (hasTone || hasClaims)
}

// normalizeCompareArgs prefers real analyze tool results over model-invented
// compare args. Small local models often call compare in parallel with
// inventing analysis_a/b. Returns (args, rewritten).
func normalizeCompareArgs(rawInput map[string]any, analyzeResults []map[string]any) (map[string]any, bool) {
	a := asObj(rawInput["analysis_a"])
	b := asObj(rawInput["analysis_b"])
	if looksLikeAnalyzeResult(a) && looksLikeAnalyzeResult(b) {
		return map[string]any{"analysis_a": a, "analysis_b": b}, false
	}
	if len(analyzeResults) >= 2 {
		return map[string]any{
			"analysis_a": analyzeResults[len(analyzeResults)-2],
			"analysis_b": analyzeResults[len(analyzeResults)-1],
		}, true
	}
	return map[string]any{"analysis_a": a, "analysis_b": b}, false
}

func ollamaToolName(call map[string]any) string {
	fn, ok := call["function"].(map[string]any)
	if !ok {
		return ""
	}
	return asStr(fn["name"])
}

// sortOllamaToolCalls runs analyzes before compare within the same model turn.
func sortOllamaToolCalls(calls []map[string]any) []map[string]any {
	order := func(call map[string]any) int {
		switch ollamaToolName(call) {
		case toolAnalyze:
			return 0
		case toolCompare:
			return 1
		default:
			return 2
		}
	}
	sorted := make([]map[string]any, len(calls))
	copy(sorted, calls)
	sort.SliceStable(sorted, func(i, j int) bool { return order(sorted[i]) < order(sorted[j]) })
	return sorted
}

func sentimentScore(text string) int {
	score := 0
	for _, tok := range wordPattern.FindAllString(strings.ToLower(text), -1) {
		if positiveWords[tok] {
			score++
		} else if negativeWords[tok] {
			score--
		}
	}
	return score
}

// handleAnalyzeTickerStories is a deterministic single-ticker analysis
// grounded in headline titles. LaunchDarkly supplies the schema; this app
// code is the handler the model's tool call ultimately runs.
func handleAnalyzeTickerStories(args map[string]any) map[string]any {
	ticker := strings.ToUpper(strings.TrimSpace(asStr(args["ticker"])))
	if ticker == "" {
		ticker = "?"
	}
	rawStories, _ := args["stories"].([]any)
	claims := []any{}
	score := 0
	for _, item := range rawStories {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		title := strings.TrimSpace(asStr(m["title"]))
		if title == "" {
			continue
		}
		tone := sentimentScore(title)
		score += tone
		var claim string
		switch {
		case tone > 0:
			claim = fmt.Sprintf("Positive headline signal for %s: %s", ticker, title)
		case tone < 0:
			claim = fmt.Sprintf("Negative headline signal for %s: %s", ticker, title)
		default:
			claim = fmt.Sprintf("Neutral headline for %s: %s", ticker, title)
		}
		claims = append(claims, map[string]any{"claim": claim, "evidence_title": title})
	}
	var summary string
	switch {
	case len(claims) == 0:
		summary = fmt.Sprintf("No usable headlines provided for %s.", ticker)
	case score > 0:
		summary = fmt.Sprintf("%s: net positive headline tone (%d stories).", ticker, len(claims))
	case score < 0:
		summary = fmt.Sprintf("%s: net negative headline tone (%d stories).", ticker, len(claims))
	default:
		summary = fmt.Sprintf("%s: mixed/neutral headline tone (%d stories).", ticker, len(claims))
	}
	return map[string]any{
		"ticker":     ticker,
		"claims":     claims,
		"summary":    summary,
		"tone_score": score,
	}
}

func stance(score int) string {
	switch {
	case score > 0:
		return "constructive"
	case score < 0:
		return "cautious"
	default:
		return "neutral"
	}
}

func evidenceTitles(analysis map[string]any) []any {
	out := []any{}
	claims, _ := analysis["claims"].([]any)
	for _, c := range claims {
		cm, ok := c.(map[string]any)
		if !ok {
			continue
		}
		title := strings.TrimSpace(asStr(cm["evidence_title"]))
		if title != "" {
			out = append(out, title)
		}
	}
	return out
}

// handleCompareTickerAnalyses compares two analyze-ticker-stories results;
// an optional preferred ticker falls out of whichever has the higher tone score.
func handleCompareTickerAnalyses(args map[string]any) map[string]any {
	a := asObj(args["analysis_a"])
	b := asObj(args["analysis_b"])
	ta := strings.ToUpper(firstNonEmpty(asStr(a["ticker"]), "A"))
	tb := strings.ToUpper(firstNonEmpty(asStr(b["ticker"]), "B"))
	sa := asInt(a["tone_score"])
	sb := asInt(b["tone_score"])

	var preferred any
	switch {
	case sa > sb:
		preferred = ta
	case sb > sa:
		preferred = tb
	}

	rationale := fmt.Sprintf("%s tone_score=%d (%s); %s tone_score=%d (%s).", ta, sa, stance(sa), tb, sb, stance(sb))
	if preferred != nil {
		rationale += fmt.Sprintf(" %s is the better option on headline tone alone.", preferred)
	} else {
		rationale += " No clear preferred ticker on headline tone."
	}

	return map[string]any{
		"ticker1":          map[string]any{"ticker": ta, "recommendation": stance(sa), "evidence": evidenceTitles(a)},
		"ticker2":          map[string]any{"ticker": tb, "recommendation": stance(sb), "evidence": evidenceTitles(b)},
		"preferred_ticker": preferred,
		"rationale":        rationale,
	}
}

// ---------------------------------------------------------------------------
// small JSON-ish helpers (args/results flow through the loop as map[string]any)
// ---------------------------------------------------------------------------

func asStr(v any) string {
	s, _ := v.(string)
	return s
}

func asObj(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return map[string]any{}
}

func asInt(v any) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case int:
		return t
	case json.Number:
		n, _ := t.Int64()
		return int(n)
	default:
		return 0
	}
}

func firstNonEmpty(a, b string) string {
	if strings.TrimSpace(a) != "" {
		return a
	}
	return b
}

// ---------------------------------------------------------------------------
// 4. Providers — Anthropic (cloud) and Ollama (local) tool-calling loops
// ---------------------------------------------------------------------------

var httpClient = &http.Client{Timeout: 120 * time.Second}

// ollamaChat is a non-streaming Ollama /api/chat call with tools (OpenAI-compatible shape).
func ollamaChat(model string, messages []map[string]any, tools []map[string]any) (map[string]any, error) {
	payload := map[string]any{"model": model, "stream": false, "messages": messages}
	if len(tools) > 0 {
		payload["tools"] = tools
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	host := ollamaHost()
	res, err := httpClient.Post(host+"/api/chat", "application/json", bytes.NewReader(raw))
	if err != nil {
		return nil, fmt.Errorf("Ollama request failed (%s, model=%s): %w. "+
			"Is Ollama running, and does `ollama list` include %s?", host, model, err, model)
	}
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		return nil, err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return nil, fmt.Errorf("Ollama request failed (%s, model=%s): HTTP %d %s. "+
			"Is Ollama running, and does `ollama list` include %s?", host, model, res.StatusCode, string(body), model)
	}
	var data map[string]any
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func ollamaMetricsExtract(data map[string]any) ld.AIMetrics {
	prompt := asInt(data["prompt_eval_count"])
	completion := asInt(data["eval_count"])
	return ld.AIMetrics{Success: true, Tokens: &ld.TokenUsage{Total: prompt + completion, Input: prompt, Output: completion}}
}

// anthropicChat calls the Anthropic Messages API with tools=.
func anthropicChat(apiKey, model, system string, chat, tools []map[string]any) (map[string]any, error) {
	payload := map[string]any{"model": model, "max_tokens": 1024, "messages": chat}
	if system != "" {
		payload["system"] = system
	}
	if len(tools) > 0 {
		payload["tools"] = tools
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(http.MethodPost, "https://api.anthropic.com/v1/messages", bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")

	res, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		return nil, err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		truncated := body
		if len(truncated) > 300 {
			truncated = truncated[:300]
		}
		return nil, fmt.Errorf("Anthropic request failed: HTTP %d %s", res.StatusCode, string(truncated))
	}
	var data map[string]any
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}
	return data, nil
}

func anthropicMetricsExtract(response map[string]any) ld.AIMetrics {
	usage, _ := response["usage"].(map[string]any)
	input := asInt(usage["input_tokens"])
	output := asInt(usage["output_tokens"])
	return ld.AIMetrics{Success: true, Tokens: &ld.TokenUsage{Total: input + output, Input: input, Output: output}}
}

func anthropicText(response map[string]any) string {
	var sb strings.Builder
	content, _ := response["content"].([]any)
	for _, blockAny := range content {
		block, ok := blockAny.(map[string]any)
		if !ok {
			continue
		}
		if asStr(block["type"]) == "text" {
			sb.WriteString(asStr(block["text"]))
		}
	}
	return sb.String()
}

// runOllamaToolLoop drives the tool-calling loop against a local Ollama model,
// with guardrails for small models: a suffix telling it to call tools, a
// one-shot nudge if it skips tools entirely, sorting analyze-before-compare
// within a turn, rewriting invented compare args from real analyze results,
// and forcing compare-ticker-analyses if the model never calls it.
func runOllamaToolLoop(
	p persona,
	modelName string,
	system string,
	chat []map[string]any,
	openaiTools []map[string]any,
	toolNames []string,
	tracker *ld.Tracker,
	m *metrics,
	toolCallIndex *int,
	out chan<- streamEvent,
) (string, error) {
	ollamaMessages := make([]map[string]any, 0, len(chat)+1)
	ollamaSystem := ollamaToolSuffix
	if system != "" {
		ollamaSystem = strings.TrimSpace(system + "\n\n" + ollamaToolSuffix)
	}
	if ollamaSystem != "" {
		ollamaMessages = append(ollamaMessages, map[string]any{"role": "system", "content": ollamaSystem})
	}
	ollamaMessages = append(ollamaMessages, chat...)

	var analyzeResults []map[string]any
	var calledTools []string
	nudgedForTools := false
	finalText := ""
	hitMaxSteps := true

	for step := 0; step < maxToolSteps; step++ {
		data, err := ld.TrackMetricsOf(tracker, ollamaMetricsExtract, func() (map[string]any, error) {
			return ollamaChat(modelName, ollamaMessages, openaiTools)
		})
		if err != nil {
			return "", err
		}
		m.addTokens(asInt(data["prompt_eval_count"]), asInt(data["eval_count"]))

		message := asObj(data["message"])
		toolCallsRaw, _ := message["tool_calls"].([]any)
		content := asStr(message["content"])

		if len(toolCallsRaw) == 0 {
			// Small models sometimes skip tools entirely — nudge once.
			if !nudgedForTools && len(toolNames) > 0 && len(analyzeResults) == 0 && step < maxToolSteps-1 {
				nudgedForTools = true
				out <- streamEvent{Type: "status", Message: fmt.Sprintf(
					"%s skipped tools on the first turn — nudging once to run analyze → analyze → compare.", p.Name)}
				ollamaMessages = append(ollamaMessages, message)
				ollamaMessages = append(ollamaMessages, map[string]any{
					"role": "user",
					"content": fmt.Sprintf(
						"Stop writing the briefing. Call tools now: %s once per ticker, then "+
							"%s with the exact analyze JSON results, then write the briefing.",
						toolAnalyze, toolCompare),
				})
				continue
			}
			finalText = content
			hitMaxSteps = false
			break
		}

		ollamaMessages = append(ollamaMessages, message)
		calls := make([]map[string]any, 0, len(toolCallsRaw))
		for _, c := range toolCallsRaw {
			if cm, ok := c.(map[string]any); ok {
				calls = append(calls, cm)
			}
		}
		for _, call := range sortOllamaToolCalls(calls) {
			fn, ok := call["function"].(map[string]any)
			if !ok {
				continue
			}
			name := asStr(fn["name"])
			rawInput := toolCallArguments(fn["arguments"])

			rewritten := false
			if name == toolCompare {
				rawInput, rewritten = normalizeCompareArgs(rawInput, analyzeResults)
				if rewritten {
					out <- streamEvent{Type: "status", Message: "Rewrote compare args from prior analyze results " +
						"(local model invented or parallel-called compare)."}
				}
			}

			result := dispatchTool(name, rawInput)
			_ = tracker.TrackToolCall(name)
			calledTools = append(calledTools, name)
			if name == toolAnalyze && looksLikeAnalyzeResult(result) {
				analyzeResults = append(analyzeResults, result)
			}
			*toolCallIndex++
			out <- streamEvent{Type: "tool", Tool: toolTrace{
				Name: name, Args: rawInput, Result: result, CallIndex: *toolCallIndex, Round: strconv.Itoa(step + 1),
			}}
			resultJSON, _ := json.Marshal(result)
			ollamaMessages = append(ollamaMessages, map[string]any{"role": "tool", "content": string(resultJSON)})
		}
	}

	if hitMaxSteps {
		out <- streamEvent{Type: "status", Message: fmt.Sprintf("Hit MAX_TOOL_STEPS=%d; using last model text if any.", maxToolSteps)}
		if finalText == "" {
			finalText = "(No final text after tool loop.)"
		}
	}

	// Guardrail: if the local model analyzed twice but never compared, run compare once.
	hasCompare := false
	for _, t := range calledTools {
		if t == toolCompare {
			hasCompare = true
			break
		}
	}
	if !hasCompare && len(analyzeResults) >= 2 && len(toolNames) > 0 {
		out <- streamEvent{Type: "status", Message: fmt.Sprintf(
			"%s skipped compare-ticker-analyses — running it from prior analyze results, then asking for a final briefing.",
			p.Name)}
		compareArgs := map[string]any{
			"analysis_a": analyzeResults[len(analyzeResults)-2],
			"analysis_b": analyzeResults[len(analyzeResults)-1],
		}
		result := dispatchTool(toolCompare, compareArgs)
		_ = tracker.TrackToolCall(toolCompare)
		*toolCallIndex++
		out <- streamEvent{Type: "tool", Tool: toolTrace{
			Name: toolCompare, Args: compareArgs, Result: result, CallIndex: *toolCallIndex, Round: "guardrail",
		}}
		resultJSON, _ := json.Marshal(result)
		ollamaMessages = append(ollamaMessages, map[string]any{
			"role": "user",
			"content": fmt.Sprintf(
				"%s returned:\n%s\n\nWrite the short equity briefing now using ONLY the tool "+
					"results (analyze + compare). Cite evidence titles.",
				toolCompare, string(resultJSON)),
		})
		data, err := ld.TrackMetricsOf(tracker, ollamaMetricsExtract, func() (map[string]any, error) {
			return ollamaChat(modelName, ollamaMessages, nil)
		})
		if err != nil {
			out <- streamEvent{Type: "status", Message: fmt.Sprintf("Post-compare briefing call failed: %s", err)}
		} else {
			m.addTokens(asInt(data["prompt_eval_count"]), asInt(data["eval_count"]))
			brief := asStr(asObj(data["message"])["content"])
			if brief != "" {
				finalText = brief
			}
		}
	}

	return finalText, nil
}

// toolCallArguments normalizes an Ollama tool call's function.arguments,
// which may arrive as a parsed object or as a JSON-encoded string.
func toolCallArguments(v any) map[string]any {
	switch t := v.(type) {
	case map[string]any:
		return t
	case string:
		var parsed map[string]any
		if err := json.Unmarshal([]byte(t), &parsed); err == nil {
			return parsed
		}
	}
	return map[string]any{}
}

// runAnthropicToolLoop drives the tool-calling loop against Anthropic's Messages API.
func runAnthropicToolLoop(
	modelName string,
	system string,
	chat []map[string]any,
	anthropicTools []map[string]any,
	tracker *ld.Tracker,
	m *metrics,
	toolCallIndex *int,
	out chan<- streamEvent,
) (string, error) {
	apiKey := strings.TrimSpace(os.Getenv("ANTHROPIC_API_KEY"))
	if apiKey == "" {
		return "", fmt.Errorf("ANTHROPIC_API_KEY is required for Analyst Claude. " +
			"Switch to Analyst Llama or Analyst Gwen for local Ollama, or export your Claude key")
	}

	finalText := ""
	hitMaxSteps := true

	for step := 0; step < maxToolSteps; step++ {
		response, err := ld.TrackMetricsOf(tracker, anthropicMetricsExtract, func() (map[string]any, error) {
			return anthropicChat(apiKey, modelName, system, chat, anthropicTools)
		})
		if err != nil {
			return "", err
		}
		usage, _ := response["usage"].(map[string]any)
		m.addTokens(asInt(usage["input_tokens"]), asInt(usage["output_tokens"]))

		if asStr(response["stop_reason"]) != "tool_use" {
			finalText = anthropicText(response)
			hitMaxSteps = false
			break
		}

		assistantContent := []map[string]any{}
		toolResults := []map[string]any{}
		content, _ := response["content"].([]any)
		for _, blockAny := range content {
			block, ok := blockAny.(map[string]any)
			if !ok {
				continue
			}
			switch asStr(block["type"]) {
			case "text":
				assistantContent = append(assistantContent, map[string]any{"type": "text", "text": asStr(block["text"])})
			case "tool_use":
				name := asStr(block["name"])
				toolID := asStr(block["id"])
				rawInput := asObj(block["input"])

				result := dispatchTool(name, rawInput)
				_ = tracker.TrackToolCall(name)
				*toolCallIndex++
				out <- streamEvent{Type: "tool", Tool: toolTrace{
					Name: name, Args: rawInput, Result: result, CallIndex: *toolCallIndex, Round: strconv.Itoa(step + 1),
				}}

				assistantContent = append(assistantContent, map[string]any{
					"type": "tool_use", "id": toolID, "name": name, "input": rawInput,
				})
				resultJSON, _ := json.Marshal(result)
				toolResults = append(toolResults, map[string]any{
					"type": "tool_result", "tool_use_id": toolID, "content": string(resultJSON),
				})
			}
		}
		chat = append(chat, map[string]any{"role": "assistant", "content": assistantContent})
		chat = append(chat, map[string]any{"role": "user", "content": toolResults})
	}

	if hitMaxSteps {
		out <- streamEvent{Type: "status", Message: fmt.Sprintf("Hit MAX_TOOL_STEPS=%d; using last model text if any.", maxToolSteps)}
		if finalText == "" {
			finalText = "(No final text after tool loop.)"
		}
	}
	return finalText, nil
}

// ---------------------------------------------------------------------------
// 5. Generation
// ---------------------------------------------------------------------------

func chunkYield(text string, m *metrics, started time.Time, out chan<- streamEvent) {
	if text == "" {
		m.FinishReason = "stop"
		return
	}
	ttft := int(time.Since(started).Milliseconds())
	m.TTFTMS = &ttft
	const size = 24
	runes := []rune(text)
	for i := 0; i < len(runes); i += size {
		end := i + size
		if end > len(runes) {
			end = len(runes)
		}
		out <- streamEvent{Type: "token", Text: string(runes[i:end])}
	}
	m.FinishReason = "stop"
}

// generateStream evaluates AgentControl, runs the tool loop (Anthropic or
// Ollama), and streams the final briefing tokens.
//
// Event contract: meta, status, tool, token, error, metrics, done.
//
// Unlike 21-agent-completion-config, the fallback path does not call a model
// at all — Library tools only exist on a live AgentControl config, so a
// disabled/unreachable config is a hard stop with guidance to provision it.
func generateStream(p persona, tickerResults []tickerBlock) <-chan streamEvent {
	out := make(chan streamEvent, 64)
	go func() {
		defer close(out)
		storiesText := storiesAsPromptText(tickerResults)
		started := time.Now()
		m := metrics{}

		emitDone := func() {
			lat := int(time.Since(started).Milliseconds())
			m.LatencyMS = &lat
			out <- streamEvent{Type: "metrics", Metrics: m}
			out <- streamEvent{Type: "done"}
		}

		fallbackMeta := func() {
			out <- streamEvent{
				Type: "meta", Persona: p, Input: storiesText,
				Provider: "anthropic", Model: defaultAnthropicModel() + " (code baseline)",
				Mode: "baseline-fallback", ConfigKey: configKey(), Fallback: true,
			}
		}

		var config ld.AICompletionConfig
		usingFallback := false
		isOff := false
		var fallbackReason string

		if err := initLaunchDarkly(); err != nil {
			usingFallback = true
			fallbackReason = fmt.Sprintf("LaunchDarkly evaluation failed (%s); using code baseline.", err)
		} else {
			// LaunchDarkly: evaluate completion config (model + messages + Library tools).
			config = evaluateCompletion(p, storiesText)
			switch {
			case !config.Enabled():
				usingFallback = true
				isOff = true
				fallbackReason = fmt.Sprintf("AgentControl config '%s' is off; tools path disabled.", configKey())
			case config.VariationKey() == "":
				usingFallback = true
				fallbackReason = fmt.Sprintf(
					"AgentControl config '%s' is unreachable or missing; using code baseline.", configKey())
			}
		}

		if usingFallback {
			fallbackMeta()
			out <- streamEvent{Type: "status", Message: fallbackReason}
			if isOff {
				out <- streamEvent{Type: "error", Message: "Enable the AgentControl config and attach Library tools to generate."}
			} else {
				out <- streamEvent{Type: "error", Message: fmt.Sprintf(
					"Tool loop requires a live AgentControl config. "+
						"Provision with rest/create-tools.sh && rest/create-config.sh. (%s)", fallbackReason)}
			}
			m.FinishReason = "error"
			emitDone()
			return
		}

		ldModel := config.Model().Name
		if ldModel == "" {
			ldModel = defaultAnthropicModel()
		}
		provider, modelName := personaModelName(p, ldModel)

		messages := messagesAsMaps(config.Messages())
		toolsMap := config.Tools()
		anthropicTools := ldToolsToAnthropic(toolsMap)
		openaiTools := ldToolsToOpenAI(toolsMap)
		toolNames := make([]string, len(anthropicTools))
		for i, t := range anthropicTools {
			toolNames[i] = t["name"].(string)
		}
		tracker := config.CreateTracker()

		promptPreview := userMessageText(messages)
		if promptPreview == "" {
			promptPreview = storiesText
		}
		out <- streamEvent{
			Type: "meta", Persona: p, Input: promptPreview,
			Provider: provider, Model: modelName, Mode: "launchdarkly",
			ConfigKey: configKey(), Fallback: false, Tools: toolNames,
		}

		if len(toolNames) == 0 {
			out <- streamEvent{Type: "status", Message: "No tools attached on this variation. Run rest/attach-tools.sh."}
		}

		system := ""
		chat := make([]map[string]any, 0, len(messages))
		for _, msg := range messages {
			if msg["role"] == "system" {
				if system == "" {
					system = msg["content"]
				} else {
					system = system + "\n\n" + msg["content"]
				}
			} else {
				chat = append(chat, map[string]any{"role": msg["role"], "content": msg["content"]})
			}
		}

		var finalText string
		var loopErr error
		toolCallIndex := 0

		if provider == "ollama" {
			finalText, loopErr = runOllamaToolLoop(p, modelName, system, chat, openaiTools, toolNames, tracker, &m, &toolCallIndex, out)
		} else {
			finalText, loopErr = runAnthropicToolLoop(modelName, system, chat, anthropicTools, tracker, &m, &toolCallIndex, out)
		}

		if loopErr != nil {
			out <- streamEvent{Type: "error", Message: loopErr.Error()}
			m.FinishReason = "error"
			emitDone()
			return
		}

		chunkYield(finalText, &m, started, out)
		emitDone()
	}()
	return out
}
