// agent.go — domain logic for 21-agent-completion-config[go] (no TUI code here).
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
// Same product flow as 01-reference-agent, but at generate time LaunchDarkly
// AgentControl supplies **model**, **system** message, and **user** message.
//
//  1. Data          Personas (UI labels + LD context key/name)
//  2. LaunchDarkly  Init server SDK + AI SDK; CompletionConfig evaluation
//  3. Providers     Route by served provider/model (Ollama Custom, …)
//  4. Generation    generateStream() — evaluate config, then stream LLM tokens
//
// LaunchDarkly insertion point (read this first):
//
//	generateStream() → aiClient.CompletionConfig(...)
//	Docs: https://launchdarkly.com/docs/sdk/ai/go
//	Keywords: AgentControl · completion config · AI SDK · message variables
//
// Variables: the config user message includes {{ stories }}; we pass
// {"stories": <formatted headlines>} so LaunchDarkly substitutes at evaluate time.
//
// API note (Go AI SDK is pre-1.0): the module is a *separate* Go module,
// github.com/launchdarkly/go-server-sdk-ai (package ldai), distinct from the
// older ldai subpackage bundled inside go-server-sdk/v7. Only the separate
// module exposes CompletionConfig; the bundled one only has a generic Config.
// See 20-agent-config/21-agent-completion-config/go/README.md for details.
package main

import (
	"bufio"
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

	// LaunchDarkly: ai-config key=equity-briefing-completion name="Equity briefing completion" mode=completion
	// https://app.launchdarkly.com/projects/lunch-marcoly/ai-configs/equity-briefing-completion
	defaultConfigKey       = "equity-briefing-completion"
	defaultOllamaModelName = "llama3.2:3b"
)

// persona is the selectable demo identity — also the LaunchDarkly evaluation context.
type persona struct {
	ID        string
	Name      string
	Profile   string
	Anonymous bool
}

var personas = []persona{
	{ID: "conservative-charlie", Name: "Conservative Charlie", Profile: "conservative"},
	{ID: "neutral-nancy", Name: "Neutral Nancy", Profile: "neutral"},
	{ID: "thoughtless-toby", Name: "Thoughtless Toby", Profile: "risk-taker"},
	// No name targeting — anonymous context falls through to baseline-analyst.
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
	Type         string
	Persona      persona
	Input        string
	Provider     string
	Model        string
	Mode         string
	ConfigKey    string
	VariationKey string
	Fallback     bool
	Text         string
	Message      string
	Metrics      metrics
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
	for _, m := range messages {
		if m.Role == datamodel.User {
			return m.Content
		}
	}
	return ""
}

// ---------------------------------------------------------------------------
// 2. LaunchDarkly — server SDK + AI SDK (AgentControl)
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
// Named personas: user key + name (name targeting matches Charlie/Nancy/Toby).
// Anonymous Amelia: fixed key, anonymous=true — not indexed as a known user;
// name rules do not match → fallthrough (baseline-analyst).
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

// resolveRuntime maps served provider/model to a local caller (ollama | bedrock).
//
// Custom / Ollama models from rest/create-model-config.sh use provider Custom
// and a model id like llama3.2:3b → call local Ollama.
func resolveRuntime(model, providerName string) (provider, resolvedModel string, err error) {
	pl := strings.ToLower(strings.TrimSpace(providerName))

	switch {
	case pl == "custom" || pl == "ollama" || strings.Contains(model, ":"):
		return "ollama", model, nil
	case pl == "bedrock" || strings.HasPrefix(model, "us.") || strings.HasPrefix(model, "amazon.") ||
		strings.HasPrefix(model, "anthropic.") || strings.HasPrefix(model, "meta."):
		return "bedrock", model, nil
	case model == "":
		return "", "", fmt.Errorf("AgentControl variation has no model name. " +
			"Check modelConfigKey on the served variation in LaunchDarkly")
	default:
		// Unknown provider: try Ollama with the model id (classroom default).
		return "ollama", model, nil
	}
}

// ---------------------------------------------------------------------------
// 3. Providers — call whatever model AgentControl named
// ---------------------------------------------------------------------------

func estimateTokens(text string) int {
	n := len(text) / 4
	if n < 1 {
		return 1
	}
	return n
}

func fillTokenEstimates(messages []datamodel.Message, completion string, m *metrics) {
	var prompt strings.Builder
	for _, msg := range messages {
		prompt.WriteString(msg.Content)
	}
	pt := estimateTokens(prompt.String())
	ct := estimateTokens(completion)
	total := pt + ct
	m.PromptTokens = &pt
	m.CompletionTokens = &ct
	m.TotalTokens = &total
}

func ollamaStream(model string, messages []datamodel.Message, out chan<- string) error {
	payload := map[string]any{
		"model":    model,
		"stream":   true,
		"messages": messages,
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	host := ollamaHost()
	client := &http.Client{Timeout: 120 * time.Second}
	res, err := client.Post(host+"/api/chat", "application/json", bytes.NewReader(raw))
	if err != nil {
		return fmt.Errorf("ollama request failed (%s, model=%s): %w. "+
			"Is Ollama running, and does the AgentControl model id match `ollama list`?", host, model, err)
	}
	defer res.Body.Close()
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return fmt.Errorf("ollama request failed (%s, model=%s): HTTP %d. "+
			"Is Ollama running, and does the AgentControl model id match `ollama list`?", host, model, res.StatusCode)
	}

	scanner := bufio.NewScanner(res.Body)
	// Ollama chunks can be larger than default buffer.
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var data map[string]any
		if err := json.Unmarshal([]byte(line), &data); err != nil {
			continue
		}
		if errMsg, ok := data["error"]; ok && errMsg != nil {
			return fmt.Errorf("%v", errMsg)
		}
		if msg, ok := data["message"].(map[string]any); ok {
			if content := asString(msg["content"]); content != "" {
				out <- content
			}
		}
		if done, ok := data["done"].(bool); ok && done {
			return nil
		}
	}
	if err := scanner.Err(); err != nil && err != io.EOF {
		return err
	}
	return nil
}

func generateOllama(model string, messages []datamodel.Message, started time.Time, m *metrics, out chan<- streamEvent) error {
	chunks := make(chan string, 16)
	errCh := make(chan error, 1)
	go func() {
		errCh <- ollamaStream(model, messages, chunks)
		close(chunks)
	}()

	var parts []string
	first := true
	for chunk := range chunks {
		if first {
			ttft := int(time.Since(started).Milliseconds())
			m.TTFTMS = &ttft
			first = false
		}
		parts = append(parts, chunk)
		out <- streamEvent{Type: "token", Text: chunk}
	}
	if err := <-errCh; err != nil {
		return err
	}
	m.FinishReason = "stop"
	fillTokenEstimates(messages, strings.Join(parts, ""), m)
	return nil
}

// ---------------------------------------------------------------------------
// 4. Generation
// ---------------------------------------------------------------------------

func intOr(v *int, def int) int {
	if v == nil {
		return def
	}
	return *v
}

// generateStream evaluates AgentControl, then streams tokens from the served model.
//
// Event contract matches 01-reference-agent (meta / token / error / metrics / done),
// plus a "status" event used for the fallback notice.
//
// When the AgentControl config is **disabled**, unreachable, or the served
// variation carries no variation key (LD unreachable / config key missing —
// the Go AI SDK silently returns the caller-supplied default in that case),
// fall back to the in-code baseline-analyst prompts + local Ollama model —
// same text as rest/messages/baseline-*.txt.
func generateStream(p persona, tickerResults []tickerBlock) <-chan streamEvent {
	out := make(chan streamEvent, 32)
	go func() {
		defer close(out)
		storiesText := formatStories(tickerResults)
		started := time.Now()
		m := metrics{}

		emitDone := func() {
			lat := int(time.Since(started).Milliseconds())
			m.LatencyMS = &lat
			out <- streamEvent{Type: "metrics", Metrics: m}
			out <- streamEvent{Type: "done"}
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
					"AgentControl config '%s' is off / enabled=false; using code baseline-analyst.", configKey())
			}
		}

		if usingFallback {
			messages := baselineMessages(storiesText)
			provider, model, mode := "ollama", defaultOllamaModel(), "baseline-fallback"
			fmt.Printf("[generate] %s: variation='code-baseline' reason='FALLBACK'\n", p.Name)

			promptPreview := userMessageText(messages)
			if promptPreview == "" {
				promptPreview = storiesText
			}
			out <- streamEvent{
				Type: "meta", Persona: p, Input: promptPreview,
				Provider: provider, Model: model + " (code baseline)", Mode: mode,
				ConfigKey: configKey(), Fallback: true,
			}
			if fallbackReason != "" {
				out <- streamEvent{Type: "status", Message: fallbackReason}
			}
			if err := generateOllama(model, messages, started, &m, out); err != nil {
				out <- streamEvent{Type: "error", Message: err.Error()}
				m.FinishReason = "error"
			}
			emitDone()
			return
		}

		provider, model, err := resolveRuntime(config.Model().Name, config.Provider().Name)
		messages := config.Messages()
		tracker := config.CreateTracker()
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
			emitDone()
			return
		}

		fmt.Printf("[generate] %s: variation=%q\n", p.Name, config.VariationKey())
		promptPreview := userMessageText(messages)
		if promptPreview == "" {
			promptPreview = storiesText
		}
		out <- streamEvent{
			Type: "meta", Persona: p, Input: promptPreview,
			Provider: provider, Model: model, Mode: "launchdarkly",
			ConfigKey: configKey(), VariationKey: config.VariationKey(), Fallback: false,
		}

		switch provider {
		case "ollama":
			if err := generateOllama(model, messages, started, &m, out); err != nil {
				out <- streamEvent{Type: "error", Message: err.Error()}
				m.FinishReason = "error"
			}
		case "bedrock":
			out <- streamEvent{Type: "error", Message: "Bedrock is not wired in the Go example. " +
				"Retarget the variation to an Ollama / Custom model, or run the Python/Node/.NET web app for Bedrock."}
			m.FinishReason = "error"
		default:
			out <- streamEvent{Type: "error", Message: fmt.Sprintf("Unsupported runtime provider '%s'.", provider)}
			m.FinishReason = "error"
		}

		lat := int(time.Since(started).Milliseconds())
		m.LatencyMS = &lat

		// LaunchDarkly: report generation metrics for this run (tokens, latency, success/error).
		// https://launchdarkly.com/docs/sdk/features/ai-metrics
		if tracker != nil {
			if m.FinishReason == "error" {
				_ = tracker.TrackError()
			} else {
				_ = tracker.TrackSuccess()
				_ = tracker.TrackDuration(time.Duration(lat) * time.Millisecond)
				if m.TTFTMS != nil {
					_ = tracker.TrackTimeToFirstToken(time.Duration(*m.TTFTMS) * time.Millisecond)
				}
				if m.TotalTokens != nil || m.PromptTokens != nil || m.CompletionTokens != nil {
					_ = tracker.TrackTokens(ld.TokenUsage{
						Total:  intOr(m.TotalTokens, 0),
						Input:  intOr(m.PromptTokens, 0),
						Output: intOr(m.CompletionTokens, 0),
					})
				}
			}
		}

		out <- streamEvent{Type: "metrics", Metrics: m}
		out <- streamEvent{Type: "done"}
	}()
	return out
}
