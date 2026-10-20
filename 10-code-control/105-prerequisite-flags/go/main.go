// Console grid navigator demonstrating LaunchDarkly flag prerequisites.
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	"github.com/launchdarkly/go-sdk-common/v3/ldreason"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"golang.org/x/term"
)

// LaunchDarkly: evaluate the dependent flag even when its prerequisite fails.
// https://launchdarkly.com/docs/home/flags/prereqs
const (
	flagHighlight = "enable-grid-selection-highlight-prereq"
	flagCount     = "show-navigation-move-count-prereq"
	appBanner     = "15-prerequisite-flags[go]"
	bgANSI        = "\033[48;5;236m"
	resetANSI     = "\033[0m"
)

var (
	rows     = [3]string{"t", "m", "b"}
	cols     = [3]string{"l", "m", "r"}
	ldClient *ld.LDClient
)

type flagValues struct {
	username       string
	highlightColor string
	showMoveCount  bool
	parentValue    string
	parentReason   string
	childValue     bool
	childReason    string
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
}

type sessionAction int

const (
	actionQuit sessionAction = iota
	actionLogout
)

func initLaunchDarkly() {
	sdkKey := os.Getenv("LD_SDK_KEY")
	if sdkKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — flags use safe defaults.")
		return
	}
	client, err := ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize.")
		return
	}
	ldClient = client
}

func formatReason(reason ldreason.EvaluationReason) string {
	kind := string(reason.GetKind())
	if reason.GetKind() == ldreason.EvalReasonPrerequisiteFailed {
		if key := reason.GetPrerequisiteKey(); key != "" {
			return kind + " (" + key + ")"
		}
	}
	return kind
}

func highlightColor(value string) string {
	switch value {
	case "green", "yellow", "red", "blue", "purple", "pink":
		return value
	default:
		return "none"
	}
}

func evaluateFlags(username string) flagValues {
	userKey := strings.ToLower(strings.TrimSpace(username))
	if ldClient == nil {
		return flagValues{
			username:       userKey,
			highlightColor: "none",
			parentValue:    "none",
			parentReason:   "OFFLINE",
			childReason:    "OFFLINE",
		}
	}
	ctx := ldcontext.NewBuilder(userKey).Kind("user").Build()
	parentValue, parentDetail, _ := ldClient.StringVariationDetail(flagHighlight, ctx, "none")
	childValue, childDetail, _ := ldClient.BoolVariationDetail(flagCount, ctx, false)
	return flagValues{
		username:       userKey,
		highlightColor: highlightColor(parentValue),
		showMoveCount:  childValue,
		parentValue:    parentValue,
		parentReason:   formatReason(parentDetail.Reason),
		childValue:     childValue,
		childReason:    formatReason(childDetail.Reason),
	}
}

func ansiColor(color string) string {
	switch color {
	case "pink":
		return "\033[95m"
	case "yellow":
		return "\033[93m"
	case "red":
		return "\033[91m"
	case "blue":
		return "\033[94m"
	case "green":
		return "\033[92m"
	case "purple":
		return "\033[35m"
	default:
		return ""
	}
}

func colorize(text, color string) string {
	code := ansiColor(color)
	if code == "" {
		return text
	}
	return code + text + resetANSI + bgANSI
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
		if color != "none" {
			return colorize(text, color)
		}
		return text
	}
	return [3]string{"┌───┐", "│   │", "└───┘"}[line]
}

func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\033[K\r\n")
}

func render(username string, row, col int, previous *position, moveCount int, flags flagValues) {
	var out strings.Builder
	out.WriteString(bgANSI)
	out.WriteString("\033[H\033[2J")
	previousText := "—"
	if previous != nil {
		previousText = formatPos(previous.row, previous.col)
	}
	writeLine(&out, appBanner)
	writeLine(&out, "Name: "+colorize(username, flags.highlightColor))
	writeLine(&out, "Current position: "+formatPos(row, col))
	writeLine(&out, "Previous position: "+previousText)
	if flags.showMoveCount {
		writeLine(&out, fmt.Sprintf("Count: %d", moveCount))
	}
	writeLine(&out, "")
	writeLine(&out, fmt.Sprintf("Parent: %v  %s", flags.parentValue, flags.parentReason))
	writeLine(&out, fmt.Sprintf("Child:  %v  %s", flags.childValue, flags.childReason))
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (L to logout, Q to quit).")
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

func runGrid(username string, stream *keyStream) sessionAction {
	row, col := 1, 1
	var previous *position
	moveCount := 0
	for {
		flags := evaluateFlags(username)
		render(flags.username, row, col, previous, moveCount, flags)
		event := readKeyEvent(stream, 500*time.Millisecond)
		if event.endsSession {
			return event.action
		}
		if !event.hasMove {
			continue
		}
		result := tryMove(row, col, event.dr, event.dc)
		if result.moved {
			old := position{row, col}
			previous = &old
			row, col = result.row, result.col
			moveCount++
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
