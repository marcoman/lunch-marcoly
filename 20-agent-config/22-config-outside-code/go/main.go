// 22-config-outside-code[go] — terminal UI matching 21-agent-completion-config/go chrome/hotkeys.
//
// Same screen chrome and key bindings as 21, plus two new keys: (+) and (-)
// send thumbs feedback for the last **tracked** generate via a resumption
// token. See agent.go for the LaunchDarkly insertion points (generateStream →
// CompletionConfig + TrackMetricsOf; submitFeedback → CreateTracker + TrackFeedback).
package main

import (
	"bufio"
	"fmt"
	"os"
	"regexp"
	"strings"
	"unicode/utf8"

	"golang.org/x/term"
)

const (
	appBanner  = "22-config-outside-code[go]"
	chromeRows = 3
	footerRows = 1
	padMax     = 4000
	menuRight  = "(n)ext user"
)

var menuLeft = []string{
	"(t)ickers", "st(o)ries", "(s)tatus", "(g)enerate", "(+)up", "(-)down", "(q)uit",
}

const (
	ansiReset   = "\033[0m"
	ansiBold    = "\033[1m"
	ansiDim     = "\033[2m"
	ansiCyan    = "\033[36m"
	ansiYellow  = "\033[33m"
	ansiGreen   = "\033[32m"
	ansiMagenta = "\033[35m"
	ansiBlue    = "\033[34m"
	ansiRed     = "\033[31m"
	ansiWhite   = "\033[37m"
)

var kindStyle = map[string]string{
	"hotkey":   ansiBold + ansiCyan,
	"name":     ansiBold + ansiYellow,
	"ok":       ansiBold + ansiGreen,
	"error":    ansiBold + ansiRed,
	"busy":     ansiBold + ansiCyan,
	"warn":     ansiBold + ansiYellow,
	"muted":    ansiDim + ansiWhite,
	"ticker1":  ansiBold + ansiGreen,
	"ticker2":  ansiBold + ansiMagenta,
	"story1":   ansiBold + ansiGreen,
	"story2":   ansiBold + ansiMagenta,
	"prompt":   ansiBlue,
	"response": ansiCyan,
}

// Includes + and - so the thumbs hotkeys ((+) / (-)) get the same bold-cyan
// hotkey styling as the letter hotkeys.
var hotkeyRe = regexp.MustCompile(`\(([A-Za-z+\-])\)`)

type padLine struct {
	text string
	kind string
}

type app struct {
	personaIndex int
	ticker1      string
	ticker2      string
	stories      []tickerBlock
	padLines     []padLine
	scroll       int
	footer       string
	footerKind   string
	busy         bool
	stdinFD      int
	reader       *bufio.Reader

	// Last served AgentControl evaluation — drives chrome row 1 + (s)tatus.
	lastProvider     string
	lastModel        string
	lastVariationKey string
	lastFallback     bool

	// Feedback state — set once a tracked (non-fallback) generate completes.
	// (+) / (-) replay against the persona that produced this exact run, even
	// if the user has since pressed (n) to switch personas.
	lastResumptionToken string
	lastTrackedPersona  persona
	lastFeedbackLabel   string
}

func paint(text, kind string) string {
	style := kindStyle[kind]
	if style == "" {
		return text
	}
	return style + text + ansiReset
}

func clip(text string, width int) string {
	if width <= 0 {
		return ""
	}
	if utf8.RuneCountInString(text) <= width {
		return text
	}
	runes := []rune(text)
	if width <= 1 {
		return string(runes[:width])
	}
	return string(runes[:width-1]) + "…"
}

func alignPair(left, right string, width, gap int) string {
	if width <= 0 {
		return ""
	}
	if gap < 1 {
		gap = 2
	}
	if utf8.RuneCountInString(left)+gap+utf8.RuneCountInString(right) > width {
		room := max(0, width-gap-utf8.RuneCountInString(left))
		right = clip(right, room)
		room = max(0, width-gap-utf8.RuneCountInString(right))
		left = clip(left, room)
	}
	pad := max(gap, width-utf8.RuneCountInString(left)-utf8.RuneCountInString(right))
	return clip(left+strings.Repeat(" ", pad)+right, width)
}

func termSize() (cols, rows int) {
	cols, rows, err := term.GetSize(int(os.Stdout.Fd()))
	if err != nil || cols < 1 || rows < 1 {
		return 100, 32
	}
	return cols, rows
}

func styleHotkeys(text string) string {
	return hotkeyRe.ReplaceAllStringFunc(text, func(m string) string {
		ch := m[1 : len(m)-1]
		return "(" + paint(ch, "hotkey") + ")"
	})
}

func wrapText(text string, width int) []string {
	if text == "" {
		return []string{""}
	}
	out := make([]string, 0)
	for _, raw := range strings.Split(text, "\n") {
		if raw == "" {
			out = append(out, "")
			continue
		}
		rest := raw
		for utf8.RuneCountInString(rest) > width {
			runes := []rune(rest)
			out = append(out, string(runes[:width]))
			rest = string(runes[width:])
		}
		out = append(out, rest)
	}
	if len(out) == 0 {
		return []string{""}
	}
	return out
}

func storyCount(stories []tickerBlock, ticker string) int {
	symbol := normalizeTicker(ticker)
	for _, block := range stories {
		if normalizeTicker(block.Ticker) == symbol {
			return len(block.Stories)
		}
	}
	return 0
}

func tickersLabel(t1, t2 string, stories []tickerBlock) string {
	a, b := t1, t2
	if a == "" {
		a = "(not set)"
	}
	if b == "" {
		b = "(not set)"
	}
	return fmt.Sprintf("Tickers: %s (%d stories) %s (%d stories)",
		a, storyCount(stories, t1), b, storyCount(stories, t2))
}

func newApp(fd int, reader *bufio.Reader) *app {
	a := &app{
		ticker1:    defaultTicker1,
		ticker2:    defaultTicker2,
		footer:     "Ready.",
		footerKind: "info",
		stdinFD:    fd,
		reader:     reader,
	}
	a.restoreCache()
	return a
}

func (a *app) persona() persona {
	return personas[a.personaIndex]
}

func (a *app) restoreCache() {
	t1, t2, blocks, ok := getLastPairCached()
	if !ok {
		return
	}
	a.ticker1 = t1
	a.ticker2 = t2
	a.stories = blocks
	a.footer = "Restored saved stories from disk cache."
	a.footerKind = "ok"
}

func (a *app) append(text, kind string) {
	cols, _ := termSize()
	width := max(20, cols-1)
	for _, line := range wrapText(text, width) {
		a.padLines = append(a.padLines, padLine{text: line, kind: kind})
	}
	if len(a.padLines) > padMax {
		a.padLines = a.padLines[len(a.padLines)-padMax:]
	}
	a.scrollToBottom()
}

func (a *app) appendToken(token, kind string) {
	if token == "" {
		return
	}
	cols, _ := termSize()
	width := max(20, cols-1)
	parts := strings.Split(token, "\n")
	for i, part := range parts {
		if i > 0 {
			a.padLines = append(a.padLines, padLine{text: "", kind: kind})
		}
		if part == "" {
			continue
		}
		if len(a.padLines) == 0 {
			a.padLines = append(a.padLines, padLine{text: "", kind: kind})
		}
		last := &a.padLines[len(a.padLines)-1]
		if last.kind != kind && last.text != "" {
			a.padLines = append(a.padLines, padLine{text: "", kind: kind})
			last = &a.padLines[len(a.padLines)-1]
		}
		combined := last.text + part
		if utf8.RuneCountInString(combined) <= width {
			last.text = combined
			last.kind = kind
			continue
		}
		curRunes := []rune(last.text)
		partRunes := []rune(part)
		space := width - len(curRunes)
		if space > 0 {
			last.text = string(curRunes) + string(partRunes[:space])
			last.kind = kind
			rest := partRunes[space:]
			for len(rest) > 0 {
				n := width
				if n > len(rest) {
					n = len(rest)
				}
				a.padLines = append(a.padLines, padLine{text: string(rest[:n]), kind: kind})
				rest = rest[n:]
			}
		} else {
			rest := partRunes
			for len(rest) > 0 {
				n := width
				if n > len(rest) {
					n = len(rest)
				}
				a.padLines = append(a.padLines, padLine{text: string(rest[:n]), kind: kind})
				rest = rest[n:]
			}
		}
	}
	if len(a.padLines) > padMax {
		a.padLines = a.padLines[len(a.padLines)-padMax:]
	}
	a.scrollToBottom()
}

func (a *app) outputHeight() int {
	_, rows := termSize()
	return max(1, rows-chromeRows-footerRows)
}

func (a *app) scrollToBottom() {
	a.scroll = max(0, len(a.padLines)-a.outputHeight())
}

func (a *app) scrollBy(delta int) {
	maxScroll := max(0, len(a.padLines)-a.outputHeight())
	a.scroll = clamp(a.scroll+delta, 0, maxScroll)
}

func (a *app) setFooter(text, kind string) {
	a.footer = text
	a.footerKind = kind
}

// chromeProviderModel is the row-1 left label: served model after a generate,
// otherwise the AgentControl config key we're about to evaluate.
func (a *app) chromeProviderModel() string {
	if a.lastProvider != "" && a.lastModel != "" {
		return fmt.Sprintf("%s / %s", a.lastProvider, a.lastModel)
	}
	return "config:" + configKey()
}

func (a *app) render() {
	cols, _ := termSize()
	width := max(1, cols-1)
	right0 := tickersLabel(a.ticker1, a.ticker2, a.stories)
	left1 := a.chromeProviderModel()
	nameLabel := "Name: " + a.persona().Name + "."
	leftMenu := strings.Join(menuLeft, "  ")

	chrome0 := alignPair(appBanner, right0, width, 2)
	chrome1 := alignPair(left1, nameLabel, width, 2)
	chrome2 := alignPair(leftMenu, menuRight, width, 2)

	var out strings.Builder
	out.WriteString("\033[H\033[2J")

	c0Right := strings.LastIndex(chrome0, right0)
	if c0Right < 0 {
		c0Right = 0
	}
	out.WriteString(paint(appBanner, "muted"))
	out.WriteString(strings.Repeat(" ", max(0, c0Right-utf8.RuneCountInString(appBanner))))
	out.WriteString(clip(right0, width-c0Right))
	out.WriteString("\033[K\r\n")

	c1Right := strings.LastIndex(chrome1, nameLabel)
	if c1Right < 0 {
		c1Right = 0
	}
	out.WriteString(clip(left1, c1Right))
	out.WriteString(strings.Repeat(" ", max(0, c1Right-utf8.RuneCountInString(left1))))
	out.WriteString("Name: " + paint(a.persona().Name, "name") + ".")
	out.WriteString("\033[K\r\n")

	c2Right := strings.LastIndex(chrome2, menuRight)
	if c2Right < 0 {
		c2Right = 0
	}
	out.WriteString(styleHotkeys(clip(leftMenu, c2Right)))
	out.WriteString(strings.Repeat(" ", max(0, c2Right-utf8.RuneCountInString(leftMenu))))
	out.WriteString(styleHotkeys(menuRight))
	out.WriteString("\033[K\r\n")

	viewH := a.outputHeight()
	end := a.scroll + viewH
	if end > len(a.padLines) {
		end = len(a.padLines)
	}
	slice := a.padLines[a.scroll:end]
	for i := 0; i < viewH; i++ {
		if i >= len(slice) {
			out.WriteString("\033[K\r\n")
			continue
		}
		out.WriteString(paint(clip(slice[i].text, width), slice[i].kind))
		out.WriteString("\033[K\r\n")
	}
	out.WriteString(paint(clip(a.footer, width), a.footerKind))
	out.WriteString("\033[K")
	fmt.Print(out.String())
}

func (a *app) appendStories() {
	if len(a.stories) == 0 {
		a.append("  (no stories loaded — press o)", "muted")
		return
	}
	for index, block := range a.stories {
		slot := 2
		if index == 0 {
			slot = 1
		}
		ticker := block.Ticker
		if ticker == "" {
			ticker = "?"
		}
		name := block.Name
		if name == "" {
			name = ticker
		}
		cache := ""
		if block.FromCache {
			cache = " [cached]"
		}
		a.append(fmt.Sprintf("  %s (%s)%s", ticker, name, cache), fmt.Sprintf("ticker%d", slot))
		if len(block.Stories) == 0 {
			msg := block.Error
			if msg == "" {
				msg = "no stories"
			}
			a.append("    · "+msg, "muted")
			continue
		}
		for _, s := range block.Stories {
			line := "    · " + s.Title
			if s.Title == "" {
				line = "    · (untitled)"
			}
			if s.Publisher != "" {
				line += " — " + s.Publisher
			}
			a.append(line, fmt.Sprintf("story%d", slot))
		}
		if block.Error != "" {
			a.append("    note: "+block.Error, "warn")
		}
	}
}

func (a *app) cmdStatus() {
	p := a.persona()
	a.append("— status —", "muted")
	a.append(fmt.Sprintf("User:     %s (%s)", p.Name, p.Profile), "name")
	a.append("Tickers:  "+a.ticker1, "ticker1")
	a.append("          "+a.ticker2, "ticker2")
	a.append("Config:   "+configKey(), "muted")
	if a.lastProvider != "" && a.lastModel != "" {
		a.append(fmt.Sprintf("Provider: %s / %s", a.lastProvider, a.lastModel), "muted")
	} else {
		a.append("Provider: (generate once to see served model)", "muted")
	}
	if a.lastVariationKey != "" || a.lastFallback {
		variation := a.lastVariationKey
		if variation == "" {
			variation = "code-baseline"
		}
		a.append(fmt.Sprintf("Last LD:  variation=%s  fallback=%v", variation, a.lastFallback), "ok")
	} else {
		a.append("Last LD:  (none yet — press g)", "muted")
	}
	if a.lastResumptionToken != "" {
		a.append(fmt.Sprintf("Feedback: ready for %s — press + (up) or - (down)", a.lastTrackedPersona.Name), "ok")
	} else {
		a.append("Feedback: (none yet — a tracked generate mints a resumption token)", "muted")
	}
	if a.lastFeedbackLabel != "" {
		a.append("Last sent: "+a.lastFeedbackLabel, "muted")
	}
	a.append("Stories:", "muted")
	a.appendStories()
	a.setFooter("Status shown.", "ok")
}

// cookedState is the terminal state before MakeRaw (set in main).
var cookedState *term.State

func (a *app) promptLineCooked(label string) (string, error) {
	a.setFooter(label, "busy")
	a.render()
	if cookedState != nil {
		_ = term.Restore(a.stdinFD, cookedState)
	}
	fmt.Print(label)
	line, err := a.reader.ReadString('\n')
	if err != nil {
		return "", err
	}
	if _, err := term.MakeRaw(a.stdinFD); err != nil {
		return "", err
	}
	// Discard leftover from cooked line read transition.
	a.reader.Reset(os.Stdin)
	return strings.TrimSpace(line), nil
}

func (a *app) cmdTickers() {
	t1, err := a.promptLineCooked("Ticker 1: ")
	if err != nil {
		a.setFooter(err.Error(), "error")
		return
	}
	t2, err := a.promptLineCooked("Ticker 2: ")
	if err != nil {
		a.setFooter(err.Error(), "error")
		return
	}
	if t1 != "" {
		if n := normalizeTicker(t1); n != "" {
			a.ticker1 = n
		} else {
			a.ticker1 = defaultTicker1
		}
	}
	if t2 != "" {
		if n := normalizeTicker(t2); n != "" {
			a.ticker2 = n
		} else {
			a.ticker2 = defaultTicker2
		}
	}
	a.append(fmt.Sprintf("Tickers set to %s  %s", a.ticker1, a.ticker2), "ok")
	a.setFooter(fmt.Sprintf("Tickers: %s  %s", a.ticker1, a.ticker2), "ok")
}

func (a *app) cmdStories() {
	a.busy = true
	a.setFooter(fmt.Sprintf("Fetching Yahoo stories for %s and %s…", a.ticker1, a.ticker2), "busy")
	a.render()
	result := fetchStoriesForTickers(a.ticker1, a.ticker2, 2)
	a.stories = result.Tickers
	a.append(fmt.Sprintf("— stories (%s / %s) —", a.ticker1, a.ticker2), "muted")
	a.appendStories()
	if len(result.Errors) > 0 {
		a.setFooter(strings.Join(result.Errors, " · "), "warn")
	} else {
		a.setFooter("Stories loaded. Press g to generate.", "ok")
	}
	a.busy = false
}

func (a *app) cmdNextUser() {
	a.personaIndex = (a.personaIndex + 1) % len(personas)
	p := a.persona()
	a.append(fmt.Sprintf("User: %s (%s)", p.Name, p.Profile), "name")
	a.setFooter("User: "+p.Name, "ok")
}

func (a *app) cmdGenerate() {
	usable := false
	for _, b := range a.stories {
		if len(b.Stories) > 0 {
			usable = true
			break
		}
	}
	if !usable {
		a.setFooter("Load stories first (press o), then g.", "warn")
		return
	}
	a.busy = true
	p := a.persona()
	// Reset feedback state for this run — only a successful tracked (non-fallback)
	// generate below will populate a fresh resumption token.
	a.lastResumptionToken = ""
	a.lastFeedbackLabel = ""
	a.setFooter(fmt.Sprintf("Generating AI report for %s…", p.Name), "busy")
	a.append(fmt.Sprintf("— generate (%s) —", p.Name), "muted")
	a.render()
	sawToken := false
	for event := range generateStream(p, a.stories) {
		switch event.Type {
		case "meta":
			a.lastProvider = event.Provider
			a.lastModel = event.Model
			a.lastFallback = event.Fallback
			a.lastVariationKey = event.VariationKey
			variation := event.VariationKey
			if variation == "" {
				if event.Fallback {
					variation = "code-baseline"
				} else {
					variation = "(unknown)"
				}
			}
			a.append(fmt.Sprintf("LD: %s  config=%s", variation, event.ConfigKey), "muted")
			a.append(fmt.Sprintf("Provider: %s / %s", event.Provider, event.Model), "muted")
			a.append("Prompt:", "muted")
			a.append(event.Input, "prompt")
			a.append("Response:", "muted")
		case "status":
			a.append(event.Message, "warn")
		case "token":
			a.appendToken(event.Text, "response")
			sawToken = true
			a.setFooter("Streaming… "+p.Name, "busy")
		case "error":
			if sawToken {
				a.append("", "normal")
			}
			msg := event.Message
			if msg == "" {
				msg = "Generation error"
			}
			a.append("Error: "+msg, "error")
			a.setFooter(msg, "error")
		case "metrics":
			if sawToken {
				a.append("", "normal")
			}
			m := event.Metrics
			a.append(fmt.Sprintf(
				"Metrics: latency_ms=%s  ttft_ms=%s  prompt_tokens=%s  completion_tokens=%s  total_tokens=%s  finish_reason=%s",
				fmtOptInt(m.LatencyMS), fmtOptInt(m.TTFTMS), fmtOptInt(m.PromptTokens),
				fmtOptInt(m.CompletionTokens), fmtOptInt(m.TotalTokens), dash(m.FinishReason),
			), "muted")
		case "done":
			if event.ResumptionToken != "" {
				a.lastResumptionToken = event.ResumptionToken
				a.lastTrackedPersona = p
				a.append("Tracked: press + (up) or - (down) to send feedback for this run.", "ok")
				a.setFooter(fmt.Sprintf("Done — tracked report complete for %s. Try + / -.", p.Name), "ok")
			} else {
				a.setFooter(fmt.Sprintf("Done — report complete for %s (untracked fallback).", p.Name), "ok")
			}
		}
		a.render()
	}
	a.busy = false
}

func (a *app) cmdFeedback(kind string) {
	if a.lastResumptionToken == "" {
		a.setFooter("No tracked report yet — press g, then + or -.", "warn")
		return
	}
	a.busy = true
	a.setFooter("Sending feedback…", "busy")
	a.render()
	label, err := submitFeedback(a.lastTrackedPersona, a.lastResumptionToken, kind)
	a.busy = false
	if err != nil {
		a.append("Feedback error: "+err.Error(), "error")
		a.setFooter(err.Error(), "error")
		return
	}
	a.lastFeedbackLabel = label
	a.append(fmt.Sprintf("Feedback: %s (persona=%s)", label, a.lastTrackedPersona.Name), "ok")
	a.setFooter(fmt.Sprintf("Thumbs %s sent for %s.", label, a.lastTrackedPersona.Name), "ok")
}

func fmtOptInt(v *int) string {
	if v == nil {
		return "—"
	}
	return fmt.Sprintf("%d", *v)
}

func dash(s string) string {
	if s == "" {
		return "—"
	}
	return s
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

type keyEvent struct {
	ch    rune
	name  string // up, down, pageup, pagedown, quit
	ctrlC bool
}

func readKey(reader *bufio.Reader) keyEvent {
	b, err := reader.ReadByte()
	if err != nil {
		return keyEvent{name: "quit"}
	}
	switch b {
	case 3:
		return keyEvent{ctrlC: true, name: "quit"}
	case 'q', 'Q':
		return keyEvent{ch: 'q', name: "quit"}
	case 27:
		b2, err := reader.ReadByte()
		if err != nil || b2 != '[' {
			return keyEvent{}
		}
		b3, err := reader.ReadByte()
		if err != nil {
			return keyEvent{}
		}
		switch b3 {
		case 'A':
			return keyEvent{name: "up"}
		case 'B':
			return keyEvent{name: "down"}
		case '5':
			if b4, err := reader.ReadByte(); err == nil && b4 == '~' {
				return keyEvent{name: "pageup"}
			}
		case '6':
			if b4, err := reader.ReadByte(); err == nil && b4 == '~' {
				return keyEvent{name: "pagedown"}
			}
		}
		return keyEvent{}
	default:
		if b >= 32 && b < 127 {
			return keyEvent{ch: rune(b)}
		}
		return keyEvent{}
	}
}

func main() {
	if !term.IsTerminal(int(os.Stdin.Fd())) {
		fmt.Fprintln(os.Stderr, "go console requires an interactive TTY.")
		os.Exit(1)
	}

	fd := int(os.Stdin.Fd())
	var err error
	cookedState, err = term.GetState(fd)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	reader := bufio.NewReader(os.Stdin)
	a := newApp(fd, reader)

	// LaunchDarkly: warm up the server SDK + AI SDK before entering raw mode so the
	// first (g)enerate doesn't pay SDK-init latency. A failure here is not fatal —
	// generateStream() falls back to the code baseline (see agent.go).
	ldHint := fmt.Sprintf("Ready (config:%s). o → g → +/- to compare & rate personas.", configKey())
	ldKind := "info"
	if err := initLaunchDarkly(); err != nil {
		ldHint = fmt.Sprintf("LD init failed: %s (generate will use code baseline).", err)
		ldKind = "warn"
	}
	if !(a.footerKind == "ok" && len(a.stories) > 0) {
		a.setFooter(ldHint, ldKind)
	}

	oldState, err := term.MakeRaw(fd)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	// Prefer the pre-raw state for cooked prompts.
	if cookedState == nil {
		cookedState = oldState
	}

	cleanup := func() {
		_ = term.Restore(fd, oldState)
		fmt.Print(ansiReset + "\r\n")
	}
	defer cleanup()

	for {
		a.render()
		key := readKey(reader)
		if key.name == "quit" || key.ctrlC {
			break
		}
		switch key.name {
		case "up":
			a.scrollBy(-1)
			continue
		case "down":
			a.scrollBy(1)
			continue
		case "pageup":
			a.scrollBy(-a.outputHeight())
			continue
		case "pagedown":
			a.scrollBy(a.outputHeight())
			continue
		}
		if a.busy {
			continue
		}
		ch := key.ch
		if ch >= 'A' && ch <= 'Z' {
			ch += 'a' - 'A'
		}
		switch ch {
		case 's':
			a.cmdStatus()
		case 't':
			a.cmdTickers()
		case 'o':
			a.cmdStories()
		case 'g':
			a.cmdGenerate()
		case 'n':
			a.cmdNextUser()
		case '+':
			a.cmdFeedback("positive")
		case '-':
			a.cmdFeedback("negative")
		case 'h', '?':
			a.setFooter(strings.Join(menuLeft, "  ")+"   "+menuRight, "info")
		case 0:
			// ignore
		default:
			a.setFooter("Unknown key. Use menu hotkeys (t o s g n + - q).", "warn")
		}
	}
}
