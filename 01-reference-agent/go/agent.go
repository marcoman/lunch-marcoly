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
)

const (
	cannedInput = "No ticker stories loaded yet. Ask the user to click Get Stories, " +
		"then produce a brief placeholder note that you are waiting for headlines."
	defaultBedrockModelID = "us.amazon.nova-lite-v1:0"
)

type persona struct {
	ID      string
	Name    string
	Profile string
}

var personas = []persona{
	{ID: "conservative-charlie", Name: "Conservative Charlie", Profile: "conservative"},
	{ID: "neutral-nancy", Name: "Neutral Nancy", Profile: "neutral"},
	{ID: "thoughtless-toby", Name: "Thoughtless Toby", Profile: "risk-taker"},
}

type metrics struct {
	LatencyMS         *int   `json:"latency_ms"`
	TTFTMS            *int   `json:"ttft_ms"`
	PromptTokens      *int   `json:"prompt_tokens"`
	CompletionTokens  *int   `json:"completion_tokens"`
	TotalTokens       *int   `json:"total_tokens"`
	FinishReason      string `json:"finish_reason"`
}

type streamEvent struct {
	Type     string
	Persona  persona
	Input    string
	Provider string
	Model    string
	Mode     string
	Text     string
	Message  string
	Metrics  metrics
}

var modeOverride string

func setModeOverride(mode string) {
	mode = strings.ToLower(strings.TrimSpace(mode))
	switch mode {
	case "", "stub", "ollama", "bedrock", "anthropic":
		modeOverride = mode
	default:
		modeOverride = "stub"
	}
}

func resolveMode() string {
	mode := modeOverride
	if mode == "" {
		mode = strings.ToLower(strings.TrimSpace(os.Getenv("AGENT_LLM_MODE")))
	}
	if mode == "" {
		mode = "stub"
	}
	switch mode {
	case "stub", "ollama", "bedrock", "anthropic":
		return mode
	default:
		return "stub"
	}
}

func providerLabel(mode string) string {
	return mode
}

func modelLabel(mode string) string {
	if override := strings.TrimSpace(os.Getenv("AGENT_LLM_MODEL")); override != "" {
		return override
	}
	switch mode {
	case "stub":
		return "default-no-llm"
	case "ollama":
		m := strings.TrimSpace(os.Getenv("OLLAMA_MODEL"))
		if m == "" {
			return "llama3.2:3b"
		}
		return m
	case "bedrock":
		m := strings.TrimSpace(os.Getenv("AGENT_BEDROCK_MODEL_ID"))
		if m == "" {
			return defaultBedrockModelID
		}
		return m
	case "anthropic":
		m := strings.TrimSpace(os.Getenv("ANTHROPIC_MODEL"))
		if m == "" {
			return "claude-3-haiku-20240307"
		}
		return m
	default:
		return "(unknown)"
	}
}

func ollamaHost() string {
	host := strings.TrimSpace(os.Getenv("OLLAMA_HOST"))
	if host == "" {
		host = "http://127.0.0.1:11434"
	}
	return strings.TrimRight(host, "/")
}

func loadSystemPrompt() (string, error) {
	path := filepath.Join(exampleRoot(), "prompts", "system_prompt.txt")
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("could not read system prompt at %s: %w", path, err)
	}
	text := strings.TrimSpace(string(raw))
	if text == "" {
		return "", fmt.Errorf("system prompt file is empty: %s", path)
	}
	return text, nil
}

func buildUserInput(tickerResults []tickerBlock) string {
	if len(tickerResults) == 0 {
		return cannedInput
	}
	return formatStoriesForPrompt(tickerResults)
}

func estimateTokens(text string) int {
	n := len(text) / 4
	if n < 1 {
		return 1
	}
	return n
}

func fillTokenEstimates(completionText string, m *metrics, userInput string) {
	sys, _ := loadSystemPrompt()
	pt := estimateTokens(sys + userInput)
	ct := estimateTokens(completionText)
	total := pt + ct
	m.PromptTokens = &pt
	m.CompletionTokens = &ct
	m.TotalTokens = &total
}

func stubResponse(p persona, tickerResults []tickerBlock) string {
	var lines []string
	lines = append(lines,
		"[stub / default-no-llm]",
		fmt.Sprintf("Persona: %s (%s)", p.Name, p.Profile),
		"",
		"Headline briefing (stub):",
	)
	if len(tickerResults) == 0 {
		lines = append(lines, "- (no stories loaded — click Get Stories)")
	} else {
		for _, block := range tickerResults {
			ticker := block.Ticker
			if ticker == "" {
				ticker = "?"
			}
			lines = append(lines, fmt.Sprintf("- %s:", ticker))
			if len(block.Stories) == 0 {
				lines = append(lines, "  (no stories)")
			}
			for _, s := range block.Stories {
				title := s.Title
				if title == "" {
					title = "(untitled)"
				}
				lines = append(lines, "  • "+title)
			}
		}
	}
	lines = append(lines, "",
		fmt.Sprintf("As a %s analyst, this is boilerplate report text for UI testing. "+
			"Switch AGENT_LLM_MODE to ollama or bedrock for a real model response.", p.Profile),
	)
	return strings.Join(lines, "\n")
}

func probeOllama(timeout time.Duration) bool {
	client := &http.Client{Timeout: timeout}
	res, err := client.Get(ollamaHost() + "/api/tags")
	if err != nil {
		return false
	}
	defer res.Body.Close()
	return res.StatusCode >= 200 && res.StatusCode < 300
}

func ensureLLMMode() string {
	if strings.TrimSpace(os.Getenv("AGENT_LLM_MODE")) != "" {
		return resolveMode()
	}
	if probeOllama(600 * time.Millisecond) {
		_ = os.Setenv("AGENT_LLM_MODE", "ollama")
	} else if os.Getenv("AGENT_LLM_MODE") == "" {
		_ = os.Setenv("AGENT_LLM_MODE", "stub")
	}
	return resolveMode()
}

func chunkText(text string, size int) []string {
	if size < 1 {
		size = 12
	}
	out := make([]string, 0, (len(text)/size)+1)
	for i := 0; i < len(text); i += size {
		end := i + size
		if end > len(text) {
			end = len(text)
		}
		out = append(out, text[i:end])
	}
	return out
}

func generateStub(p persona, started time.Time, m *metrics, userInput string, tickerResults []tickerBlock, out chan<- streamEvent) {
	text := stubResponse(p, tickerResults)
	first := true
	for _, chunk := range chunkText(text, 12) {
		if first {
			ttft := int(time.Since(started).Milliseconds())
			m.TTFTMS = &ttft
			first = false
		}
		out <- streamEvent{Type: "token", Text: chunk}
		time.Sleep(20 * time.Millisecond)
	}
	m.FinishReason = "stop"
	fillTokenEstimates(text, m, userInput)
}

func ollamaStream(p persona, model string, tickerResults []tickerBlock, out chan<- string) error {
	sys, err := loadSystemPrompt()
	if err != nil {
		return err
	}
	payload := map[string]any{
		"model":  model,
		"stream": true,
		"messages": []map[string]string{
			{"role": "system", "content": sys},
			{"role": "user", "content": buildUserInput(tickerResults)},
		},
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	host := ollamaHost()
	client := &http.Client{Timeout: 120 * time.Second}
	res, err := client.Post(host+"/api/chat", "application/json", bytes.NewReader(raw))
	if err != nil {
		return fmt.Errorf("ollama request failed (%s): %w. Is Ollama running, and is OLLAMA_MODEL pulled?", host, err)
	}
	defer res.Body.Close()
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return fmt.Errorf("ollama request failed (%s): HTTP %d. Is Ollama running, and is OLLAMA_MODEL pulled?", host, res.StatusCode)
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

func generateOllama(p persona, model string, started time.Time, m *metrics, tickerResults []tickerBlock, userInput string, out chan<- streamEvent) error {
	chunks := make(chan string, 16)
	errCh := make(chan error, 1)
	go func() {
		errCh <- ollamaStream(p, model, tickerResults, chunks)
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
	fillTokenEstimates(strings.Join(parts, ""), m, userInput)
	return nil
}

// generateStream yields meta/token/error/metrics/done events on the returned channel.
func generateStream(p persona, tickerResults []tickerBlock) <-chan streamEvent {
	out := make(chan streamEvent, 32)
	go func() {
		defer close(out)
		mode := resolveMode()
		provider := providerLabel(mode)
		model := modelLabel(mode)
		userInput := buildUserInput(tickerResults)

		out <- streamEvent{
			Type:     "meta",
			Persona:  p,
			Input:    userInput,
			Provider: provider,
			Model:    model,
			Mode:     mode,
		}

		started := time.Now()
		m := metrics{}

		switch mode {
		case "stub":
			generateStub(p, started, &m, userInput, tickerResults, out)
		case "ollama":
			if err := generateOllama(p, model, started, &m, tickerResults, userInput, out); err != nil {
				out <- streamEvent{Type: "error", Message: err.Error()}
				m.FinishReason = "error"
			}
		case "bedrock":
			out <- streamEvent{
				Type: "error",
				Message: "Mode 'bedrock' is not wired in the Go example yet. " +
					"Use AGENT_LLM_MODE=stub or ollama here, or run the Python web app for Bedrock.",
			}
			m.FinishReason = "error"
		default:
			out <- streamEvent{
				Type: "error",
				Message: fmt.Sprintf("Mode '%s' is configured but not implemented in this reference yet. "+
					"Use AGENT_LLM_MODE=stub or ollama.", mode),
			}
			m.FinishReason = "error"
		}

		lat := int(time.Since(started).Milliseconds())
		m.LatencyMS = &lat
		out <- streamEvent{Type: "metrics", Metrics: m}
		out <- streamEvent{Type: "done"}
	}()
	return out
}
