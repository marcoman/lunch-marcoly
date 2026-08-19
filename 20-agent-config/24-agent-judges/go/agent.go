// agent.go — domain logic for 24-agent-judges[go] (no TUI code here).
//
// =============================================================================
// HOW TO READ THIS FILE
// =============================================================================
//
// Same equity-briefing product as 21, plus a **runtime judge gate**:
//
//	draft → JudgeConfig (×2) + Ollama JSON → optional one Charlie rewrite
//
//  1. Data          Personas (Toby + Charlie only)
//  2. LaunchDarkly  Init server SDK + AI SDK; CompletionConfig + JudgeConfig
//  3. Providers     Ollama stream for drafts; Ollama non-streaming JSON for judges
//  4. Generation    generateStream() — draft → both judges → optional rewrite
//
// LaunchDarkly insertion point (read this first):
//
//	generateStream() → aiClient.CompletionConfig(...) then JudgeConfig(...) per judge
//	Docs: https://launchdarkly.com/docs/home/agentcontrol/judges
//	Keywords: Judges · custom judges · JudgeConfig · TrackJudgeResponse · runtime gate
//
// Go AI SDK note: JudgeConfig returns prompts/model from LaunchDarkly; this example
// runs the gate via Ollama format=json (score + reasoning), then reports scores with
// tracker.TrackJudgeResponse — same teaching gate as Node 24.
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
	"strconv"
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

	// LaunchDarkly: completion + two custom judges for the runtime gate.
	// https://launchdarkly.com/docs/home/agentcontrol/judges
	defaultConfigKey          = "equity-briefing-judged"
	defaultJudgeFidelityKey   = "equity-briefing-source-fidelity"
	defaultJudgeDisciplineKey = "equity-briefing-recommendation-discipline"
	defaultOllamaModelName    = "llama3.2:3b"
	defaultPassThreshold      = 0.70

	judgeJSONSuffix = `Respond with JSON {"score":0.0-1.0,"reasoning":"..."}.`
)

// persona is the selectable demo identity — also the LaunchDarkly evaluation context.
type persona struct {
	ID      string
	Name    string
	Profile string
}

// Only two personas: Toby (fail fixture) and Charlie (rewrite voice).
var personas = []persona{
	{ID: "thoughtless-toby", Name: "Thoughtless Toby", Profile: "risk-taker"},
	{ID: "conservative-charlie", Name: "Conservative Charlie", Profile: "conservative"},
}

// charlie is the rewrite target when either judge fails.
var charlie = personas[1]

type metrics struct {
	LatencyMS        *int
	TTFTMS           *int
	PromptTokens     *int
	CompletionTokens *int
	TotalTokens      *int
	FinishReason     string
}

// judgeResult is one custom-judge evaluation (score + pass against threshold).
type judgeResult struct {
	Key       string
	Success   bool
	Error     string
	Score     *float64
	Reasoning string
	MetricKey string
	Sampled   bool
	Passed    bool
}

type streamEvent struct {
	Type           string
	Persona        persona
	Input          string
	Provider       string
	Model          string
	Mode           string
	ConfigKey      string
	VariationKey   string
	Fallback       bool
	JudgeKeys      []string
	PassThreshold  float64
	Text           string
	Message        string
	Metrics        metrics
	SectionTitle   string
	SectionKind    string
	JudgesPassed   bool
	JudgeThreshold float64
	JudgeResults   []judgeResult
	RewritePersona persona
}

func configKey() string {
	if v := strings.TrimSpace(os.Getenv("LD_AGENT_CONFIG_KEY")); v != "" {
		return v
	}
	return defaultConfigKey
}

func judgeFidelityKey() string {
	if v := strings.TrimSpace(os.Getenv("LD_JUDGE_FIDELITY_KEY")); v != "" {
		return v
	}
	return defaultJudgeFidelityKey
}

func judgeDisciplineKey() string {
	if v := strings.TrimSpace(os.Getenv("LD_JUDGE_DISCIPLINE_KEY")); v != "" {
		return v
	}
	return defaultJudgeDisciplineKey
}

func passThreshold() float64 {
	raw := strings.TrimSpace(os.Getenv("JUDGE_PASS_THRESHOLD"))
	if raw == "" {
		return defaultPassThreshold
	}
	n, err := strconv.ParseFloat(raw, 64)
	if err != nil {
		return defaultPassThreshold
	}
	return n
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

func mustMessageFile(name string) string {
	text, err := readMessageFile(name)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

func userMessageText(messages []datamodel.Message) string {
	for _, m := range messages {
		if m.Role == datamodel.User {
			return m.Content
		}
	}
	return ""
}

func extractTickers(tickerResults []tickerBlock) []string {
	out := make([]string, 0, len(tickerResults))
	for _, r := range tickerResults {
		t := strings.TrimSpace(r.Ticker)
		if t != "" {
			out = append(out, t)
		}
	}
	return out
}

func judgeInputText(storiesText string, tickers []string) string {
	tickerLine := ""
	if len(tickers) > 0 {
		tickerLine = "Tickers: " + strings.Join(tickers, ", ") + "\n\n"
	}
	return tickerLine +
		"Task: Write a short equity briefing comparing the tickers using only the headlines below.\n\n" +
		"HEADLINES:\n" + storiesText
}

func defaultMetricForJudgeKey(key string) string {
	if strings.Contains(key, "fidelity") {
		return "$ld:ai:judge:source-fidelity"
	}
	if strings.Contains(key, "discipline") {
		return "$ld:ai:judge:recommendation-discipline"
	}
	suffix := strings.TrimPrefix(key, "equity-briefing-")
	if suffix == "" || suffix == key {
		suffix = "custom"
	}
	return "$ld:ai:judge:" + suffix
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
// LaunchDarkly: server-side SDK + AI SDK for AgentControl completion + judges.
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
func buildContext(p persona) ldcontext.Context {
	return ldcontext.NewBuilder(p.ID).Name(p.Name).Build()
}

// skepticCompletionDefault is the SDK default when the completion config is missing
// (concise-skeptic / Charlie shape from rest/messages/skeptic-*.txt).
//
// LaunchDarkly: CompletionConfig default for AgentControl evaluation.
// https://launchdarkly.com/docs/sdk/features/agentcontrol-config
func skepticCompletionDefault() ld.AICompletionConfigDefault {
	return ld.NewAICompletionConfigDefault().
		WithEnabled(true).
		WithModelName(defaultOllamaModel()).
		WithProviderName("Custom").
		WithMessage(mustMessageFile("skeptic-system.txt"), datamodel.System).
		WithMessage(mustMessageFile("skeptic-user.txt"), datamodel.User)
}

// judgeDefault is the SDK default for a custom judge config key.
//
// LaunchDarkly: JudgeConfig default — evaluationMetricKey + system prompt.
// https://launchdarkly.com/docs/home/agentcontrol/judges
func judgeDefault(systemFile, metricKey string) ld.AIJudgeConfigDefault {
	return ld.NewAIJudgeConfigDefault().
		WithEnabled(true).
		WithModelName(defaultOllamaModel()).
		WithProviderName("Custom").
		WithEvaluationMetricKey(metricKey).
		WithMessage(mustMessageFile(systemFile), datamodel.System)
}

// evaluateCompletion fetches model + messages from AgentControl (completion mode).
func evaluateCompletion(p persona, storiesText string) ld.AICompletionConfig {
	variables := map[string]interface{}{"stories": storiesText}
	return aiClient.CompletionConfig(configKey(), buildContext(p), skepticCompletionDefault(), variables)
}

// resolveRuntime maps served provider/model to a local caller (ollama).
func resolveRuntime(model, providerName string) (provider, resolvedModel string, err error) {
	pl := strings.ToLower(strings.TrimSpace(providerName))

	switch {
	case pl == "custom" || pl == "ollama" || strings.Contains(model, ":"):
		return "ollama", model, nil
	case model == "":
		return "", "", fmt.Errorf("AgentControl variation has no model name. " +
			"Check modelConfigKey on the served variation in LaunchDarkly")
	default:
		return "ollama", model, nil
	}
}

// ---------------------------------------------------------------------------
// 3. Providers — Ollama stream (draft/rewrite) + Ollama JSON (judges)
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

// ollamaJudgeJSON runs a non-streaming Ollama chat with format=json for judge scores.
func ollamaJudgeJSON(model string, messages []datamodel.Message) (map[string]any, error) {
	payload := map[string]any{
		"model":    model,
		"stream":   false,
		"format":   "json",
		"messages": messages,
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	host := ollamaHost()
	client := &http.Client{Timeout: 120 * time.Second}
	res, err := client.Post(host+"/api/chat", "application/json", bytes.NewReader(raw))
	if err != nil {
		return nil, fmt.Errorf("ollama judge failed (%s, model=%s): %w", host, model, err)
	}
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		return nil, err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return nil, fmt.Errorf("ollama judge failed (%s, model=%s): HTTP %d %s", host, model, res.StatusCode, string(body))
	}
	var data map[string]any
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, err
	}
	if errMsg, ok := data["error"]; ok && errMsg != nil {
		return nil, fmt.Errorf("%v", errMsg)
	}
	msg, _ := data["message"].(map[string]any)
	content := strings.TrimSpace(asString(msg["content"]))
	if content == "" {
		return nil, fmt.Errorf("ollama judge returned empty content")
	}
	var parsed map[string]any
	if err := json.Unmarshal([]byte(content), &parsed); err != nil {
		return nil, fmt.Errorf("ollama judge JSON parse failed: %w", err)
	}
	return parsed, nil
}

func intOr(v *int, def int) int {
	if v == nil {
		return def
	}
	return *v
}

func trackGeneration(tracker *ld.Tracker, m *metrics, latMS int) {
	if tracker == nil {
		return
	}
	if m.FinishReason == "error" {
		_ = tracker.TrackError()
		return
	}
	_ = tracker.TrackSuccess()
	_ = tracker.TrackDuration(time.Duration(latMS) * time.Millisecond)
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

// runOneJudge evaluates one custom judge via JudgeConfig + Ollama JSON.
//
// LaunchDarkly: JudgeConfig for prompts/model; TrackJudgeResponse for scores.
// https://launchdarkly.com/docs/home/agentcontrol/judges
func runOneJudge(key string, p persona, inputText, outputText string) judgeResult {
	metricDefault := defaultMetricForJudgeKey(key)
	systemFile := "judge-recommendation-discipline-system.txt"
	if strings.Contains(key, "fidelity") {
		systemFile = "judge-source-fidelity-system.txt"
	}

	config := aiClient.JudgeConfig(key, buildContext(p), judgeDefault(systemFile, metricDefault), nil)
	metric := config.EvaluationMetricKey()
	if metric == "" {
		metric = metricDefault
	}

	if !config.Enabled() {
		return judgeResult{
			Key: key, Success: false,
			Error: "judge config disabled or unsupported (enabled=false)",
			MetricKey: metric, Sampled: true, Passed: false,
		}
	}

	model := config.Model().Name
	if model == "" {
		model = defaultOllamaModel()
	}
	if resolved, rm, err := resolveRuntime(model, config.Provider().Name); err == nil && resolved == "ollama" {
		model = rm
	}
	if model == "" {
		model = defaultOllamaModel()
	}

	var systemParts []string
	for _, m := range config.Messages() {
		if m.Role == datamodel.System && strings.TrimSpace(m.Content) != "" {
			systemParts = append(systemParts, strings.TrimSpace(m.Content))
		}
	}
	system := strings.TrimSpace(strings.Join(systemParts, "\n"))
	if system == "" {
		system = mustMessageFile(systemFile)
	}
	if !strings.Contains(system, "Respond with JSON") {
		system = system + "\n\n" + judgeJSONSuffix
	}

	user := "MESSAGE HISTORY:\n" + inputText + "\n\nRESPONSE TO EVALUATE:\n" + outputText
	messages := []datamodel.Message{
		{Role: datamodel.System, Content: system},
		{Role: datamodel.User, Content: user},
	}

	parsed, err := ollamaJudgeJSON(model, messages)
	if err != nil {
		return judgeResult{
			Key: key, Success: false, Error: err.Error(),
			MetricKey: metric, Sampled: true, Passed: false,
		}
	}

	var scorePtr *float64
	if raw, ok := parsed["score"]; ok && raw != nil {
		switch v := raw.(type) {
		case float64:
			scorePtr = &v
		case json.Number:
			if f, err := v.Float64(); err == nil {
				scorePtr = &f
			}
		case string:
			if f, err := strconv.ParseFloat(strings.TrimSpace(v), 64); err == nil {
				scorePtr = &f
			}
		}
	}
	reasoning := ""
	if r, ok := parsed["reasoning"]; ok && r != nil {
		reasoning = asString(r)
	}
	threshold := passThreshold()
	passed := scorePtr != nil && *scorePtr >= threshold

	// LaunchDarkly: report judge score for this metric key.
	// https://launchdarkly.com/docs/sdk/features/ai-metrics
	if tracker := config.CreateTracker(); tracker != nil && scorePtr != nil {
		_ = tracker.TrackJudgeResponse(datamodel.JudgeResponse{
			Success:        true,
			JudgeConfigKey: key,
			Evals: map[string]datamodel.EvalScore{
				metric: {Score: *scorePtr, Reasoning: reasoning},
			},
		})
	}

	return judgeResult{
		Key: key, Success: true, Score: scorePtr, Reasoning: reasoning,
		MetricKey: metric, Sampled: true, Passed: passed,
	}
}

func runJudges(p persona, inputText, draft string) []judgeResult {
	return []judgeResult{
		runOneJudge(judgeFidelityKey(), p, inputText, draft),
		runOneJudge(judgeDisciplineKey(), p, inputText, draft),
	}
}

func judgesPassed(results []judgeResult) bool {
	for _, r := range results {
		if !r.Passed {
			return false
		}
	}
	return true
}

// ---------------------------------------------------------------------------
// 4. Generation — draft → judges → optional Charlie rewrite
// ---------------------------------------------------------------------------

// generateStream evaluates AgentControl, streams a draft, runs both judges, and
// optionally rewrites once with Conservative Charlie.
//
// Event contract: meta / section / token / status / judges / rewrite_meta /
// metrics / error / done (same shape as Node/Python 24 SSE extras).
func generateStream(p persona, tickerResults []tickerBlock) <-chan streamEvent {
	out := make(chan streamEvent, 32)
	go func() {
		defer close(out)
		storiesText := formatStories(tickerResults)
		tickers := extractTickers(tickerResults)
		started := time.Now()
		m := metrics{}
		threshold := passThreshold()

		emitDone := func() {
			lat := int(time.Since(started).Milliseconds())
			m.LatencyMS = &lat
			out <- streamEvent{Type: "metrics", Metrics: m}
			out <- streamEvent{Type: "done"}
		}

		if err := initLaunchDarkly(); err != nil {
			out <- streamEvent{Type: "error", Message: fmt.Sprintf("LaunchDarkly completionConfig failed: %v", err)}
			out <- streamEvent{Type: "done"}
			return
		}

		config := evaluateCompletion(p, storiesText)
		if !config.Enabled() {
			out <- streamEvent{
				Type: "error",
				Message: fmt.Sprintf(
					"AgentControl config '%s' is off / enabled=false. Run rest/create-config.sh.",
					configKey()),
			}
			out <- streamEvent{Type: "done"}
			return
		}

		provider, model, err := resolveRuntime(config.Model().Name, config.Provider().Name)
		messages := config.Messages()
		tracker := config.CreateTracker()
		if err == nil && len(messages) == 0 {
			err = fmt.Errorf("served variation has no messages")
		}
		if err != nil {
			out <- streamEvent{Type: "error", Message: err.Error()}
			out <- streamEvent{Type: "done"}
			return
		}

		promptPreview := userMessageText(messages)
		if promptPreview == "" {
			promptPreview = storiesText
		}
		out <- streamEvent{
			Type: "meta", Persona: p, Input: promptPreview,
			Provider: provider, Model: model, Mode: "launchdarkly",
			ConfigKey: configKey(), VariationKey: config.VariationKey(),
			JudgeKeys:     []string{judgeFidelityKey(), judgeDisciplineKey()},
			PassThreshold: threshold,
		}

		out <- streamEvent{
			Type: "section", SectionTitle: fmt.Sprintf("Draft (%s)", p.Name), SectionKind: "draft",
		}

		draftParts := make([]string, 0, 32)
		tokenSink := make(chan streamEvent, 16)
		errCh := make(chan error, 1)
		go func() {
			errCh <- generateOllama(model, messages, started, &m, tokenSink)
			close(tokenSink)
		}()
		for ev := range tokenSink {
			if ev.Type == "token" {
				draftParts = append(draftParts, ev.Text)
			}
			out <- ev
		}
		if err := <-errCh; err != nil {
			out <- streamEvent{Type: "error", Message: err.Error()}
			m.FinishReason = "error"
			lat := int(time.Since(started).Milliseconds())
			m.LatencyMS = &lat
			trackGeneration(tracker, &m, lat)
			out <- streamEvent{Type: "metrics", Metrics: m}
			out <- streamEvent{Type: "done"}
			return
		}

		lat := int(time.Since(started).Milliseconds())
		m.LatencyMS = &lat
		trackGeneration(tracker, &m, lat)

		draft := strings.TrimSpace(strings.Join(draftParts, ""))
		out <- streamEvent{
			Type:    "status",
			Message: "Running judges (Source Fidelity + Recommendation Discipline)…",
		}

		judgeResults := runJudges(p, judgeInputText(storiesText, tickers), draft)
		passed := judgesPassed(judgeResults)
		out <- streamEvent{Type: "section", SectionTitle: "Judge scores", SectionKind: "judges"}
		out <- streamEvent{
			Type: "judges", JudgesPassed: passed, JudgeThreshold: threshold, JudgeResults: judgeResults,
		}

		if passed {
			out <- streamEvent{
				Type:    "status",
				Message: fmt.Sprintf("Both judges ≥ %.2f — no rewrite.", threshold),
			}
			emitDone()
			return
		}

		out <- streamEvent{
			Type:    "status",
			Message: "Gate failed — rewriting once with Conservative Charlie…",
		}
		out <- streamEvent{
			Type: "section", SectionTitle: "Rewrite (Conservative Charlie)", SectionKind: "rewrite",
		}

		rewriteMetrics := metrics{}
		rewriteStarted := time.Now()
		charlieConfig := evaluateCompletion(charlie, storiesText)
		if !charlieConfig.Enabled() {
			out <- streamEvent{Type: "error", Message: "Charlie variation enabled=false; check targeting."}
			emitDone()
			return
		}
		cProvider, cModel, cErr := resolveRuntime(charlieConfig.Model().Name, charlieConfig.Provider().Name)
		cMessages := charlieConfig.Messages()
		cTracker := charlieConfig.CreateTracker()
		if cErr == nil && len(cMessages) == 0 {
			cErr = fmt.Errorf("Charlie variation has no messages")
		}
		if cErr != nil {
			out <- streamEvent{Type: "error", Message: fmt.Sprintf("Charlie rewrite failed: %v", cErr)}
			emitDone()
			return
		}

		out <- streamEvent{
			Type: "rewrite_meta", RewritePersona: charlie,
			Provider: cProvider, Model: cModel, Persona: charlie,
		}

		if err := generateOllama(cModel, cMessages, rewriteStarted, &rewriteMetrics, out); err != nil {
			out <- streamEvent{Type: "error", Message: fmt.Sprintf("Charlie rewrite failed: %v", err)}
			rewriteMetrics.FinishReason = "error"
		}
		cLat := int(time.Since(rewriteStarted).Milliseconds())
		rewriteMetrics.LatencyMS = &cLat
		trackGeneration(cTracker, &rewriteMetrics, cLat)

		out <- streamEvent{
			Type:    "status",
			Message: "Rewrite complete (one rewrite max; scores above are for the draft).",
		}
		emitDone()
	}()
	return out
}
