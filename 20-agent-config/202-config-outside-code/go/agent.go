// agent.go — domain logic for 22-config-outside-code[go] (no TUI code here).
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
// Same completion-config flow as 21-agent-completion-config, but the teaching
// focus shifts to **tracked completion**: every generate wraps the LLM call in
// ldai.TrackMetricsOf so tokens / success / latency land on the config's
// Monitoring tab, and each run mints a resumption token so a later thumbs
// (+)/(-) keypress can send feedback for that exact run — even after the
// persona has moved on or the process restarted.
//
//  1. Data          Personas (Best Betty → Anthropic, Anonymous Amelia → Ollama)
//  2. LaunchDarkly  Init server SDK + AI SDK; CompletionConfig evaluation
//  3. Providers     Ollama (default) or Anthropic (Best Betty)
//  4. Generation    generateStream() — evaluate, ldai.TrackMetricsOf, mint resumption token
//  5. Feedback      submitFeedback() — CreateTracker(token) → TrackFeedback
//
// LaunchDarkly insertion points (read these first):
//
//	generateStream() → aiClient.CompletionConfig(...) → config.CreateTracker() → ldai.TrackMetricsOf(...)
//	submitFeedback()  → aiClient.CreateTracker(token, ctx) → tracker.TrackFeedback(...)
//	Docs: https://launchdarkly.com/docs/sdk/features/ai-metrics
//	Keywords: AgentControl · completion config · AI metrics · TrackMetricsOf · feedback · resumption token
//
// API quirks vs Python / Node / .NET (see README.md for the full list):
//
//   - ldai.TrackMetricsOf is a free generic function, not a Tracker method —
//     Go methods cannot carry their own type parameters, so the SDK exposes
//     TrackMetricsOf[T any](t *Tracker, extract func(T) AIMetrics, operation
//     func() (T, error)) (T, error) at package scope instead.
//   - Tracker.ResumptionToken() is synchronous and local — it base64-encodes
//     the run id + config key + variation key, no network round trip needed
//     to mint it. aiClient.CreateTracker(token, ctx) decodes it back into a
//     *Tracker that shares the original run id, so feedback events correlate
//     with the generate that produced them in Monitoring.
//   - Like 21, this example calls Ollama non-streaming (stream:false) so the
//     whole response is available as the typed result TrackMetricsOf's
//     extract function inspects; tokens are then chunked to the UI for the
//     same "streaming" feel as Python/Node/.NET (which do the same).
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk-ai/ldai"
	"github.com/launchdarkly/go-server-sdk-ai/ldai/datamodel"
	ldclient "github.com/launchdarkly/go-server-sdk/v7"
)

// ---------------------------------------------------------------------------
// 1. Data — demo personas (also become the LD evaluation context)
// ---------------------------------------------------------------------------

const (
	cannedStories = "No ticker stories loaded yet. Ask the user to click Get Stories."

	// LaunchDarkly: ai-config key=equity-briefing-tracked-completion name="Equity briefing tracked completion" mode=completion
	// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-tracked-completion
	defaultConfigKey         = "equity-briefing-tracked-completion"
	defaultOllamaModelName   = "llama3.2:1b"
	defaultAnthropicModelID  = "claude-sonnet-5"
	chunkSize                = 24 // token-chunk width for the streaming-feel UI (matches Python/Node/.NET)
	anthropicMaxOutputTokens = 1024
)

// persona is the selectable demo identity — also the LaunchDarkly evaluation context.
type persona struct {
	ID        string
	Name      string
	Profile   string
	Anonymous bool
}

// Best Betty → tracked-anthropic (Claude, name targeting).
// Anonymous Amelia → tracked-ollama (fallthrough; anonymous context, no name to match).
var personas = []persona{
	{ID: "best-betty", Name: "Best Betty", Profile: "best"},
	{ID: "anonymous-amelia", Name: "Anonymous Amelia", Profile: "anonymous", Anonymous: true},
}

type metrics struct {
	LatencyMS        *int
	TTFTMS           *int
	PromptTokens     *int
	CompletionTokens *int
	TotalTokens      *int
	FinishReason     string
}

type streamEvent struct {
	Type            string
	Persona         persona
	Input           string
	Provider        string
	Model           string
	Mode            string
	ConfigKey       string
	VariationKey    string
	Fallback        bool
	Tracked         bool
	Text            string
	Message         string
	Metrics         metrics
	ResumptionToken string
}

func configKey() string {
	if v := strings.TrimSpace(os.Getenv("LD_AGENT_CONFIG_KEY")); v != "" {
		return v
	}
	return defaultConfigKey
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

func formatStories(tickerResults []tickerBlock) string {
	if len(tickerResults) == 0 {
		return cannedStories
	}
	return formatStoriesForPrompt(tickerResults)
}

// Single source of truth with REST provisioning prompts: ../rest/messages/*.
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

// baselineSystemPrompt is the in-code baseline system prompt (same text as
// rest/messages/baseline-system.txt).
func baselineSystemPrompt() string {
	text, err := readMessageFile("baseline-system.txt")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

// baselineUserTemplate is the user prompt template with {{ stories }}
// (rest/messages/baseline-user.txt).
func baselineUserTemplate() string {
	text, err := readMessageFile("baseline-user.txt")
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

// renderBaselineUser fills {{ stories }} locally when using the code baseline fallback.
func renderBaselineUser(storiesText string) string {
	out := strings.ReplaceAll(baselineUserTemplate(), "{{ stories }}", storiesText)
	return strings.ReplaceAll(out, "{{stories}}", storiesText)
}

// baselineMessages are the chat messages for the in-code baseline-analyst fallback.
func baselineMessages(storiesText string) []datamodel.Message {
	return []datamodel.Message{
		{Role: datamodel.System, Content: baselineSystemPrompt()},
		{Role: datamodel.User, Content: renderBaselineUser(storiesText)},
	}
}

func userMessageText(messages []datamodel.Message) string {
	for i := len(messages) - 1; i >= 0; i-- {
		if messages[i].Role == datamodel.User {
			return messages[i].Content
		}
	}
	return ""
}

func firstNonEmpty(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

// ---------------------------------------------------------------------------
// 2. LaunchDarkly — server SDK + AI SDK (AgentControl, tracked completion)
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

// buildContext builds the LD evaluation context for this persona.
//
// Best Betty: named user (name targeting matches → tracked-anthropic).
// Anonymous Amelia: fixed key + anonymous=true — not indexed as a known user;
// name rules do not match → fallthrough (tracked-ollama).
// https://launchdarkly.com/docs/sdk/features/anonymous
func buildContext(p persona) ldcontext.Context {
	builder := ldcontext.NewBuilder(p.ID).Name(p.Name)
	if p.Anonymous {
		builder.Anonymous(true)
	}
	return builder.Build()
}

// baselineCompletionDefault is the SDK default when the config key is missing /
// unreachable. Also documents the intended offline shape. When the config exists
// but is turned **off**, LaunchDarkly still returns the disabled variation
// (enabled=false) — see generateStream() for the app-level fallback.
// https://launchdarkly.com/docs/sdk/ai/go
func baselineCompletionDefault() ld.AICompletionConfigDefault {
	return ld.NewAICompletionConfigDefault().
		WithEnabled(true).
		WithModelName(defaultOllamaModel()).
		WithProviderName("Custom").
		WithMessage(baselineSystemPrompt(), datamodel.System).
		WithMessage(baselineUserTemplate(), datamodel.User)
}

// evaluateCompletion fetches model + messages from AgentControl (completion mode).
//
// LaunchDarkly capability: CompletionConfig evaluation with message variables.
// https://launchdarkly.com/docs/sdk/features/agentcontrol-config
func evaluateCompletion(p persona, storiesText string) ld.AICompletionConfig {
	variables := map[string]interface{}{"stories": storiesText}
	return aiClient.CompletionConfig(configKey(), buildContext(p), baselineCompletionDefault(), variables)
}

// resolveRuntime maps served provider/model to a local caller (ollama | anthropic).
//
// Best Betty's tracked-anthropic variation carries provider=Anthropic and a
// claude-* model id. Everything else (tracked-ollama, the baseline fallback)
// is a Custom/Ollama model id like llama3.2:1b → call local Ollama.
func resolveRuntime(model, providerName string) (provider, resolvedModel string, err error) {
	pl := strings.ToLower(strings.TrimSpace(providerName))

	switch {
	case pl == "anthropic" || strings.HasPrefix(model, "claude-"):
		return "anthropic", firstNonEmpty(model, defaultAnthropicModelID), nil
	case pl == "custom" || pl == "ollama" || strings.Contains(model, ":"):
		return "ollama", firstNonEmpty(model, defaultOllamaModel()), nil
	case model == "":
		return "", "", fmt.Errorf("AgentControl variation has no model name. " +
			"Check modelConfigKey on the served variation in LaunchDarkly")
	default:
		return "ollama", model, nil
	}
}

// ---------------------------------------------------------------------------
// 3. Providers — call whatever model AgentControl named
// ---------------------------------------------------------------------------

// genResult is the typed operation result passed to ldai.TrackMetricsOf's
// extract function — the shape it needs to build ldai.AIMetrics.
type genResult struct {
	Text             string
	PromptTokens     int
	CompletionTokens int
}

func estimateTokens(text string) int {
	n := len(text) / 4
	if n < 1 {
		return 1
	}
	return n
}

func messagesPromptText(messages []datamodel.Message) string {
	var b strings.Builder
	for _, m := range messages {
		b.WriteString(m.Content)
	}
	return b.String()
}

// ollamaComplete calls Ollama non-streaming (stream:false) so the full
// response is available as one typed result for TrackMetricsOf's extractor.
func ollamaComplete(model string, messages []datamodel.Message) (genResult, error) {
	payload := map[string]any{
		"model":    model,
		"stream":   false,
		"messages": messages,
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return genResult{}, err
	}
	host := ollamaHost()
	client := &http.Client{Timeout: 120 * time.Second}
	res, err := client.Post(host+"/api/chat", "application/json", bytes.NewReader(raw))
	if err != nil {
		return genResult{}, fmt.Errorf("ollama request failed (%s, model=%s): %w. "+
			"Is Ollama running, and does the AgentControl model id match `ollama list`?", host, model, err)
	}
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		return genResult{}, err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return genResult{}, fmt.Errorf("ollama request failed (%s, model=%s): HTTP %d. "+
			"Is Ollama running, and does the AgentControl model id match `ollama list`?", host, model, res.StatusCode)
	}
	var data map[string]any
	if err := json.Unmarshal(body, &data); err != nil {
		return genResult{}, err
	}
	if errMsg, ok := data["error"]; ok && errMsg != nil {
		return genResult{}, fmt.Errorf("%v", errMsg)
	}
	text := ""
	if msg, ok := data["message"].(map[string]any); ok {
		text = asString(msg["content"])
	}
	prompt := messagesPromptText(messages)
	return genResult{
		Text:             text,
		PromptTokens:     estimateTokens(prompt),
		CompletionTokens: estimateTokens(text),
	}, nil
}

type anthropicMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type anthropicRequest struct {
	Model     string             `json:"model"`
	MaxTokens int                `json:"max_tokens"`
	System    string             `json:"system,omitempty"`
	Messages  []anthropicMessage `json:"messages"`
}

type anthropicContentBlock struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type anthropicUsage struct {
	InputTokens  int `json:"input_tokens"`
	OutputTokens int `json:"output_tokens"`
}

type anthropicResponse struct {
	Content []anthropicContentBlock `json:"content"`
	Usage   anthropicUsage          `json:"usage"`
}

// anthropicComplete calls the Anthropic Messages API for Best Betty's
// tracked-anthropic variation. Requires ANTHROPIC_API_KEY.
func anthropicComplete(model string, messages []datamodel.Message) (genResult, error) {
	apiKey := strings.TrimSpace(os.Getenv("ANTHROPIC_API_KEY"))
	if apiKey == "" {
		return genResult{}, fmt.Errorf(
			"ANTHROPIC_API_KEY is required for Anthropic variations (Best Betty → tracked-anthropic)")
	}

	var systemParts []string
	var chat []anthropicMessage
	for _, m := range messages {
		switch m.Role {
		case datamodel.System:
			systemParts = append(systemParts, m.Content)
		case datamodel.User, datamodel.Assistant:
			chat = append(chat, anthropicMessage{Role: string(m.Role), Content: m.Content})
		}
	}
	if len(chat) == 0 {
		chat = append(chat, anthropicMessage{Role: "user", Content: "Summarize the stories."})
	}

	body := anthropicRequest{
		Model:     model,
		MaxTokens: anthropicMaxOutputTokens,
		System:    strings.Join(systemParts, "\n\n"),
		Messages:  chat,
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return genResult{}, err
	}

	req, err := http.NewRequest(http.MethodPost, "https://api.anthropic.com/v1/messages", bytes.NewReader(raw))
	if err != nil {
		return genResult{}, err
	}
	req.Header.Set("content-type", "application/json")
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")

	client := &http.Client{Timeout: 120 * time.Second}
	res, err := client.Do(req)
	if err != nil {
		return genResult{}, fmt.Errorf("anthropic request failed: %w", err)
	}
	defer res.Body.Close()
	respBody, err := io.ReadAll(res.Body)
	if err != nil {
		return genResult{}, err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return genResult{}, fmt.Errorf("anthropic HTTP %d: %s", res.StatusCode, clipRunes(string(respBody), 300))
	}

	var parsed anthropicResponse
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return genResult{}, err
	}
	var text strings.Builder
	for _, block := range parsed.Content {
		if block.Type == "text" {
			text.WriteString(block.Text)
		}
	}
	return genResult{
		Text:             text.String(),
		PromptTokens:     parsed.Usage.InputTokens,
		CompletionTokens: parsed.Usage.OutputTokens,
	}, nil
}

func clipRunes(s string, max int) string {
	r := []rune(s)
	if len(r) <= max {
		return s
	}
	return string(r[:max])
}

// ---------------------------------------------------------------------------
// 4. Generation — LaunchDarkly-tracked completion
// ---------------------------------------------------------------------------

// emitChunks pushes text to out in fixed-size chunks, giving the console the
// same streaming feel as the other language ports even though the underlying
// provider calls are non-streaming (required so TrackMetricsOf's extractor
// sees the whole typed result at once).
func emitChunks(text string, m *metrics, started time.Time, out chan<- streamEvent) {
	if text == "" {
		m.FinishReason = "stop"
		return
	}
	ttft := int(time.Since(started).Milliseconds())
	m.TTFTMS = &ttft
	runes := []rune(text)
	for i := 0; i < len(runes); i += chunkSize {
		end := i + chunkSize
		if end > len(runes) {
			end = len(runes)
		}
		out <- streamEvent{Type: "token", Text: string(runes[i:end])}
	}
	m.FinishReason = "stop"
}

func fillMetricsFromResult(r genResult, m *metrics) {
	m.PromptTokens = &r.PromptTokens
	m.CompletionTokens = &r.CompletionTokens
	total := r.PromptTokens + r.CompletionTokens
	m.TotalTokens = &total
}

// generateStream evaluates AgentControl, then runs the served model inside
// ldai.TrackMetricsOf so success/duration/tokens land on the config's
// Monitoring tab. Event contract matches 21-agent-completion-config (meta /
// status / token / error / metrics / done), plus "done" now carries a
// resumptionToken for thumbs feedback.
//
// When the AgentControl config is **disabled**, unreachable, or the served
// variation carries no variation key, fall back to the in-code
// baseline-analyst prompts + local Ollama model (untracked — no Monitoring
// events, no resumption token) — same text as rest/messages/baseline-*.txt.
func generateStream(p persona, tickerResults []tickerBlock) <-chan streamEvent {
	out := make(chan streamEvent, 32)
	go func() {
		defer close(out)
		storiesText := formatStories(tickerResults)
		started := time.Now()
		m := metrics{}

		emitDone := func(resumptionToken string) {
			lat := int(time.Since(started).Milliseconds())
			m.LatencyMS = &lat
			out <- streamEvent{Type: "metrics", Metrics: m}
			out <- streamEvent{Type: "done", ResumptionToken: resumptionToken}
		}

		usingFallback := false
		var config ld.AICompletionConfig
		var fallbackReason string

		if err := initLaunchDarkly(); err != nil {
			usingFallback = true
			fallbackReason = fmt.Sprintf("LaunchDarkly evaluation failed (%s); using code baseline.", err)
		} else {
			// LaunchDarkly: evaluate completion config (model + messages).
			config = evaluateCompletion(p, storiesText)
			if !config.Enabled() || config.VariationKey() == "" {
				usingFallback = true
				fallbackReason = fmt.Sprintf(
					"AgentControl config '%s' is off / enabled=false; using code baseline.", configKey())
			}
		}

		if usingFallback {
			messages := baselineMessages(storiesText)
			model := defaultOllamaModel()
			promptPreview := firstNonEmpty(userMessageText(messages), storiesText)

			out <- streamEvent{
				Type: "meta", Persona: p, Input: promptPreview,
				Provider: "ollama", Model: model + " (code baseline)", Mode: "baseline-fallback",
				ConfigKey: configKey(), Fallback: true,
			}
			if fallbackReason != "" {
				out <- streamEvent{Type: "status", Message: fallbackReason}
			}
			result, err := ollamaComplete(model, messages)
			if err != nil {
				out <- streamEvent{Type: "error", Message: err.Error()}
				m.FinishReason = "error"
			} else {
				fillMetricsFromResult(result, &m)
				emitChunks(result.Text, &m, started, out)
			}
			emitDone("")
			return
		}

		provider, model, err := resolveRuntime(config.Model().Name, config.Provider().Name)
		messages := config.Messages()
		if err == nil && len(messages) == 0 {
			err = fmt.Errorf("served variation has no messages")
		}
		if err != nil {
			out <- streamEvent{
				Type: "meta", Persona: p, Input: storiesText,
				Provider: "—", Model: "—", Mode: "launchdarkly", ConfigKey: configKey(),
			}
			out <- streamEvent{Type: "error", Message: err.Error()}
			m.FinishReason = "error"
			emitDone("")
			return
		}

		// LaunchDarkly: CreateTracker starts a new run (fresh runId). The
		// resumption token is captured up front so thumbs can reconstruct
		// this exact tracker later — even if the persona changes or the
		// process restarts before feedback is given.
		tracker := config.CreateTracker()
		resumptionToken := ""
		if tracker != nil {
			resumptionToken = tracker.ResumptionToken()
		}

		fmt.Printf("[generate] %s: provider=%s model=%s config=%s\n", p.Name, provider, model, configKey())
		promptPreview := firstNonEmpty(userMessageText(messages), storiesText)
		out <- streamEvent{
			Type: "meta", Persona: p, Input: promptPreview,
			Provider: provider, Model: model, Mode: "launchdarkly",
			ConfigKey: configKey(), VariationKey: config.VariationKey(), Fallback: false, Tracked: true,
		}

		var result genResult
		var genErr error

		// LaunchDarkly: ldai.TrackMetricsOf wraps the provider call — tracks
		// success/error, duration, and tokens on the tracker's run in one
		// shot. https://launchdarkly.com/docs/sdk/features/ai-metrics
		extract := func(r genResult) ld.AIMetrics {
			total := r.PromptTokens + r.CompletionTokens
			return ld.AIMetrics{
				Success: true,
				Tokens:  &ld.TokenUsage{Total: total, Input: r.PromptTokens, Output: r.CompletionTokens},
			}
		}
		switch provider {
		case "anthropic":
			result, genErr = ld.TrackMetricsOf(tracker, extract, func() (genResult, error) {
				return anthropicComplete(model, messages)
			})
		case "ollama":
			result, genErr = ld.TrackMetricsOf(tracker, extract, func() (genResult, error) {
				return ollamaComplete(model, messages)
			})
		default:
			genErr = fmt.Errorf("unsupported runtime provider '%s'", provider)
		}

		if genErr != nil {
			out <- streamEvent{Type: "error", Message: genErr.Error()}
			m.FinishReason = "error"
		} else {
			fillMetricsFromResult(result, &m)
			emitChunks(result.Text, &m, started, out)
		}

		emitDone(resumptionToken)
	}()
	return out
}

// ---------------------------------------------------------------------------
// 5. Feedback — reconstruct the tracker from its resumption token
// ---------------------------------------------------------------------------

// submitFeedback records thumbs feedback against the run that produced
// resumptionToken, even if that run happened for a different persona or in a
// previous process (the token is a self-contained, base64-encoded run id).
//
// LaunchDarkly: aiClient.CreateTracker(token, ctx) → Tracker.TrackFeedback
// https://launchdarkly.com/docs/sdk/features/ai-metrics
func submitFeedback(p persona, resumptionToken, kind string) (string, error) {
	token := strings.TrimSpace(resumptionToken)
	if token == "" {
		return "", fmt.Errorf("no resumption token yet — generate a tracked report first (press g)")
	}

	var feedback ld.Feedback
	var label string
	switch strings.ToLower(strings.TrimSpace(kind)) {
	case "positive", "up", "thumbsup", "+":
		feedback, label = ld.FeedbackPositive, "positive"
	case "negative", "down", "thumbsdown", "-":
		feedback, label = ld.FeedbackNegative, "negative"
	default:
		return "", fmt.Errorf("kind must be positive or negative")
	}

	if err := initLaunchDarkly(); err != nil {
		return "", err
	}
	tracker, err := aiClient.CreateTracker(token, buildContext(p))
	if err != nil {
		return "", fmt.Errorf("could not rebuild tracker from resumption token: %w", err)
	}
	if err := tracker.TrackFeedback(feedback); err != nil {
		return "", err
	}
	return label, nil
}
