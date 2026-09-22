// Console grid navigator for a static LaunchDarkly percentage rollout.
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"golang.org/x/term"
)

// LaunchDarkly: percentage rollout — sticky assignment by context key.
// https://launchdarkly.com/docs/home/flags/rollouts
const (
	flagKey              = "enable-grid-selection-highlight-pct"
	defaultValue         = "none"
	appBanner            = "16-percentage-rollout[go]"
	configuredGreenPct   = 30
	historyLimit         = 8
	bgANSI               = "\033[48;5;236m"
	resetANSI            = "\033[0m"
	greenANSI            = "\033[92m"
)

var (
	rows     = [3]string{"t", "m", "b"}
	cols     = [3]string{"l", "m", "r"}
	ldClient *ld.LDClient
)

type flagValues struct {
	flagValue       string
	highlightColor  string
	variationIndex  *int
	reasonKind      string
}

type historyItem struct {
	username string
	value    string
	reason   string
}

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
}

type keyEvent struct {
	dr, dc      int
	action      sessionAction
	endsSession bool
	hasMove     bool
	indexDelta  int
}

type sessionAction int

const (
	actionQuit sessionAction = iota
	actionLogout
)

func initLaunchDarkly() {
	sdkKey := strings.TrimSpace(os.Getenv("LD_SDK_KEY"))
	if sdkKey == "" {
		return
	}
	client, err := ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		return
	}
	ldClient = client
}

func generatedUsername(base string, index int) string {
	if index <= 0 {
		return base
	}
	return fmt.Sprintf("%s%d", base, index)
}

func evaluateRollout(username string) flagValues {
	if ldClient == nil {
		return flagValues{
			flagValue:      defaultValue,
			highlightColor: defaultValue,
			reasonKind:     "ERROR",
		}
	}
	ctx := ldcontext.NewBuilder(username).Kind("user").Name(username).Build()
	value, detail, _ := ldClient.StringVariationDetail(flagKey, ctx, defaultValue)
	if value != "none" && value != "green" {
		value = defaultValue
	}
	var variation *int
	if index, ok := detail.VariationIndex.Get(); ok {
		value := index
		variation = &value
	}
	return flagValues{
		flagValue:      value,
		highlightColor: value,
		variationIndex: variation,
		reasonKind:     string(detail.Reason.GetKind()),
	}
}

func variationText(flags flagValues) string {
	if flags.variationIndex == nil {
		return "default"
	}
	return fmt.Sprintf("%d", *flags.variationIndex)
}

func colorize(text, color string) string {
	if color != "green" {
		return text
	}
	return greenANSI + text + resetANSI + bgANSI
}

func formatPos(row, col int) string {
	return rows[row] + "/" + cols[col]
}

func tryMove(row, col, dr, dc int) moveResult {
	nr := clamp(row+dr, 0, 2)
	nc := clamp(col+dc, 0, 2)
	return moveResult{nr, nc, nr != row || nc != col}
}

func clamp(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}

type readState int

const (
	keyReady readState = iota
	keyTimeout
	keyClosed
)

type keyStream struct {
	keys chan byte
}

func newKeyStream() *keyStream {
	stream := &keyStream{keys: make(chan byte, 64)}
	go func() {
		defer close(stream.keys)
		reader := bufio.NewReader(os.Stdin)
		for {
			key, err := reader.ReadByte()
			if err != nil {
				return
			}
			stream.keys <- key
		}
	}()
	return stream
}

func (stream *keyStream) next(timeout time.Duration) (byte, readState) {
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	select {
	case key, open := <-stream.keys:
		if !open {
			return 0, keyClosed
		}
		return key, keyReady
	case <-timer.C:
		return 0, keyTimeout
	}
}

func (stream *keyStream) readLine() (string, bool) {
	var line strings.Builder
	for key := range stream.keys {
		if key == '\n' || key == '\r' {
			return strings.TrimSpace(line.String()), true
		}
		line.WriteByte(key)
	}
	return "", false
}

func readUsername(stream *keyStream) (string, error) {
	fmt.Println(appBanner)
	fmt.Println("Login")
	fmt.Println("Username becomes the LaunchDarkly user context key.")
	fmt.Println()
	for {
		fmt.Print("Username: ")
		line, ok := stream.readLine()
		if !ok {
			return "", fmt.Errorf("stdin closed")
		}
		if line != "" {
			return line, nil
		}
		fmt.Println("Username is required.")
	}
}

func drawCell(selected bool, color string, line int) string {
	var text string
	if selected {
		text = [3]string{"┏━━━┓", "┃ X ┃", "┗━━━┛"}[line]
		return colorize(text, color)
	}
	return [3]string{"┌───┐", "│   │", "└───┘"}[line]
}

func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\033[K\r\n")
}

func observedLine(seen map[string]string) string {
	total := len(seen)
	if total == 0 {
		return "Observed: no unique keys yet."
	}
	greenCount := 0
	for _, value := range seen {
		if value == "green" {
			greenCount++
		}
	}
	noneCount := total - greenCount
	pct := float64(int(float64(greenCount)/float64(total)*1000+0.5)) / 10
	return fmt.Sprintf(
		"Observed: %d green / %d none of %d unique → %g%% (configured %d%%)",
		greenCount, noneCount, total, pct, configuredGreenPct,
	)
}

func remember(username string, flags flagValues, seen map[string]string, history *[]historyItem) {
	seen[username] = flags.flagValue
	next := make([]historyItem, 0, historyLimit)
	next = append(next, historyItem{username, flags.flagValue, flags.reasonKind})
	for _, item := range *history {
		if item.username != username {
			next = append(next, item)
		}
	}
	if len(next) > historyLimit {
		next = next[:historyLimit]
	}
	*history = next
}

func render(
	username, base string,
	index, row, col int,
	previous *position,
	flags flagValues,
	seen map[string]string,
	history []historyItem,
) {
	var out strings.Builder
	out.WriteString(bgANSI)
	out.WriteString("\033[H\033[2J")
	prevText := "—"
	if previous != nil {
		prevText = formatPos(previous.row, previous.col)
	}
	prevName := "—"
	if index > 0 {
		prevName = generatedUsername(base, index-1)
	}
	writeLine(&out, appBanner)
	writeLine(&out, "Name: "+colorize(username, flags.highlightColor))
	writeLine(&out, fmt.Sprintf("Current: %s   Previous: %s", formatPos(row, col), prevText))
	writeLine(&out, fmt.Sprintf("Flag value: %s   reason: %s   idx: %s", flags.flagValue, flags.reasonKind, variationText(flags)))
	writeLine(&out, observedLine(seen))
	writeLine(&out, fmt.Sprintf(
		"Arrows/WASD move.  N next (%s)  P prev (%s)  L logout  Q quit",
		generatedUsername(base, index+1), prevName,
	))
	writeLine(&out, "")
	for r := 0; r < 3; r++ {
		for line := 0; line < 3; line++ {
			cells := make([]string, 3)
			for c := 0; c < 3; c++ {
				color := "none"
				if r == row && c == col {
					color = flags.highlightColor
				}
				cells[c] = drawCell(r == row && c == col, color, line)
			}
			writeLine(&out, strings.Join(cells, " "))
		}
	}
	writeLine(&out, "")
	writeLine(&out, "Recent evaluations")
	if len(history) == 0 {
		writeLine(&out, "(none yet)")
	}
	for _, item := range history {
		writeLine(&out, colorize(item.username+"  "+item.value+"  "+item.reason, item.value))
	}
	fmt.Print(out.String())
}

func readKeyEvent(stream *keyStream, timeout time.Duration) keyEvent {
	key, state := stream.next(timeout)
	switch state {
	case keyTimeout:
		return keyEvent{}
	case keyClosed:
		return keyEvent{action: actionQuit, endsSession: true}
	}
	switch key {
	case 3, 'q', 'Q':
		return keyEvent{action: actionQuit, endsSession: true}
	case 'l', 'L':
		return keyEvent{action: actionLogout, endsSession: true}
	case 'n', 'N':
		return keyEvent{indexDelta: 1}
	case 'p', 'P':
		return keyEvent{indexDelta: -1}
	case 'w', 'W':
		return keyEvent{dr: -1, hasMove: true}
	case 's', 'S':
		return keyEvent{dr: 1, hasMove: true}
	case 'a', 'A':
		return keyEvent{dc: -1, hasMove: true}
	case 'd', 'D':
		return keyEvent{dc: 1, hasMove: true}
	case 27:
		second, state := stream.next(50 * time.Millisecond)
		if state != keyReady || second != '[' {
			return keyEvent{}
		}
		third, state := stream.next(50 * time.Millisecond)
		if state != keyReady {
			return keyEvent{}
		}
		switch third {
		case 'A':
			return keyEvent{dr: -1, hasMove: true}
		case 'B':
			return keyEvent{dr: 1, hasMove: true}
		case 'C':
			return keyEvent{dc: 1, hasMove: true}
		case 'D':
			return keyEvent{dc: -1, hasMove: true}
		}
	}
	return keyEvent{}
}

func runGrid(base string, stream *keyStream) sessionAction {
	index := 0
	username := generatedUsername(base, index)
	row, col := 1, 1
	var previous *position
	seen := map[string]string{}
	history := []historyItem{}
	for {
		flags := evaluateRollout(username)
		remember(username, flags, seen, &history)
		render(username, base, index, row, col, previous, flags, seen, history)
		event := readKeyEvent(stream, 500*time.Millisecond)
		if event.endsSession {
			return event.action
		}
		if event.indexDelta != 0 {
			next := index + event.indexDelta
			if next < 0 {
				continue
			}
			index = next
			username = generatedUsername(base, index)
			row, col = 1, 1
			previous = nil
			continue
		}
		if !event.hasMove {
			continue
		}
		result := tryMove(row, col, event.dr, event.dc)
		if result.moved {
			old := position{row, col}
			previous = &old
			row, col = result.row, result.col
		}
	}
}

func main() {
	initLaunchDarkly()
	defer func() {
		if ldClient != nil {
			ldClient.Close()
		}
		fmt.Print(resetANSI)
	}()

	stream := newKeyStream()
	fd := int(os.Stdin.Fd())
	for {
		username, err := readUsername(stream)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		oldState, err := term.MakeRaw(fd)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		action := runGrid(username, stream)
		_ = term.Restore(fd, oldState)
		fmt.Print(resetANSI)
		if action == actionQuit {
			return
		}
	}
}
