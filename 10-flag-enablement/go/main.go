// Console grid navigator with LaunchDarkly flag evaluation.
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

// LaunchDarkly capability: Boolean flag evaluation (server-side SDK)
// See: https://launchdarkly.com/docs/sdk/features/evaluating

const (
	flagHighlight = "configure-grid-selection-green-highlight"
	flagContext   = "configure-grid-selection-context-highlight"
	flagCount     = "show-navigation-move-count"
)

var rows = [3]string{"t", "m", "b"}
var cols = [3]string{"l", "m", "r"}

const bgANSI = "\033[48;5;236m"
const resetANSI = "\033[0m"

var ldClient *ld.LDClient

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
}

type flagValues struct {
	highlightEnabled  bool
	contextHighlight  bool
	showMoveCount     bool
	highlightColor    string
	cohortLabel       string
}

type cohorts struct {
	human bool
	robot bool
	beta  bool
}

func parseCohorts(username string) cohorts {
	lower := strings.ToLower(username)
	return cohorts{
		human: strings.Contains(lower, "human"),
		robot: strings.Contains(lower, "robot"),
		beta:  strings.Contains(lower, "beta"),
	}
}

func colorLabelName(highlightColor string) string {
	if highlightColor == "none" {
		return "no-color"
	}
	return highlightColor
}

func formatCohortLabel(username, highlightColor string, contextHighlight bool) string {
	colorName := colorLabelName(highlightColor)
	var parts []string
	if contextHighlight {
		c := parseCohorts(username)
		if c.human {
			parts = append(parts, "human")
		}
		if c.robot {
			parts = append(parts, "robot")
		}
		if c.beta {
			parts = append(parts, "beta")
		}
	}
	if len(parts) > 0 {
		return "(" + strings.Join(parts, "-") + "-" + colorName + ")"
	}
	return "(" + colorName + ")"
}

func resolveHighlightColor(username string, highlightEnabled, contextHighlight bool) string {
	if !highlightEnabled {
		return "none"
	}
	if !contextHighlight {
		return "pink"
	}
	c := parseCohorts(username)
	switch {
	case c.human && c.beta:
		return "green"
	case c.robot && c.beta:
		return "purple"
	case c.human:
		return "yellow"
	case c.robot:
		return "red"
	case c.beta:
		return "blue"
	default:
		return "pink"
	}
}

func buildFlagResponse(username string, highlightEnabled, contextHighlight, showMoveCount bool) flagValues {
	color := resolveHighlightColor(username, highlightEnabled, contextHighlight)
	label := formatCohortLabel(username, color, contextHighlight)
	return flagValues{
		highlightEnabled: highlightEnabled,
		contextHighlight: contextHighlight,
		showMoveCount:    showMoveCount,
		highlightColor:   color,
		cohortLabel:      label,
	}
}

func initLaunchDarkly() {
	sdkKey := os.Getenv("LD_SDK_KEY")
	if sdkKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — flags default to off.")
		return
	}
	client, err := ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize — flags default to off.")
		return
	}
	ldClient = client
}

func evaluateFlags(username string) flagValues {
	if ldClient == nil {
		return buildFlagResponse(username, false, false, false)
	}
	context := ldcontext.NewBuilder(username).Build()
	highlight, _ := ldClient.BoolVariation(flagHighlight, context, false)
	contextHighlight, _ := ldClient.BoolVariation(flagContext, context, false)
	showCount, _ := ldClient.BoolVariation(flagCount, context, false)
	return buildFlagResponse(username, highlight, contextHighlight, showCount)
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
	if color == "" || color == "none" {
		return text
	}
	ansi := ansiColor(color)
	if ansi == "" {
		return text
	}
	return ansi + text + resetANSI + bgANSI
}

func formatPos(row, col int) string {
	return rows[row] + "/" + cols[col]
}

func tryMove(row, col, dr, dc int) moveResult {
	nr := clamp(row+dr, 0, 2)
	nc := clamp(col+dc, 0, 2)
	if nr == row && nc == col {
		return moveResult{row, col, false}
	}
	return moveResult{nr, nc, true}
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

func readUsername(reader *bufio.Reader) (string, error) {
	fmt.Println("Login\n")
	for {
		fmt.Print("Username: ")
		line, err := reader.ReadString('\n')
		if err != nil {
			return "", err
		}
		name := strings.TrimSpace(line)
		if name != "" {
			return name, nil
		}
		fmt.Println("Username is required.")
	}
}

func drawCell(selected bool, color string, line int) string {
	if selected {
		var cell string
		switch line {
		case 0:
			cell = "┏━━━┓"
		case 1:
			cell = "┃ X ┃"
		default:
			cell = "┗━━━┛"
		}
		if color != "" && color != "none" {
			return colorize(cell, color)
		}
		return cell
	}
	switch line {
	case 0:
		return "┌───┐"
	case 1:
		return "│   │"
	default:
		return "└───┘"
	}
}

func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\r\n")
}

func render(username string, row, col int, previous *position, moveCount int, flags flagValues) {
	var out strings.Builder
	out.WriteString(bgANSI)
	out.WriteString("\033[H\033[2J")

	prevText := "—"
	if previous != nil {
		prevText = formatPos(previous.row, previous.col)
	}

	cohort := " " + flags.cohortLabel
	writeLine(&out, fmt.Sprintf("Name: %s%s", colorize(username, flags.highlightColor), colorize(cohort, flags.highlightColor))+resetANSI+bgANSI)
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	if flags.showMoveCount {
		writeLine(&out, fmt.Sprintf("Count: %d", moveCount))
	}
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (q to quit).")
	writeLine(&out, "")

	for r := 0; r < 3; r++ {
		top := make([]string, 3)
		mid := make([]string, 3)
		bot := make([]string, 3)
		for c := 0; c < 3; c++ {
			selected := r == row && c == col
			cellColor := flags.highlightColor
			if !selected {
				cellColor = "none"
			}
			top[c] = drawCell(selected, cellColor, 0)
			mid[c] = drawCell(selected, cellColor, 1)
			bot[c] = drawCell(selected, cellColor, 2)
		}
		writeLine(&out, strings.Join(top, " "))
		writeLine(&out, strings.Join(mid, " "))
		writeLine(&out, strings.Join(bot, " "))
	}

	fmt.Print(out.String())
}

func readKeyWithTimeout(reader *bufio.Reader, timeout time.Duration) (dr, dc int, quit, ok, timedOut bool) {
	if err := os.Stdin.SetReadDeadline(time.Now().Add(timeout)); err != nil {
		return 0, 0, false, false, true
	}
	defer os.Stdin.SetReadDeadline(time.Time{})

	b, err := reader.ReadByte()
	if err != nil {
		if ne, ok := err.(interface{ Timeout() bool }); ok && ne.Timeout() {
			return 0, 0, false, false, true
		}
		return 0, 0, true, false, false
	}

	switch b {
	case 3, 'q', 'Q':
		return 0, 0, true, true, false
	case 'w', 'W':
		return -1, 0, false, true, false
	case 's', 'S':
		return 1, 0, false, true, false
	case 'a', 'A':
		return 0, -1, false, true, false
	case 'd', 'D':
		return 0, 1, false, true, false
	case 27:
		b2, err := reader.ReadByte()
		if err != nil || b2 != '[' {
			return 0, 0, false, false, false
		}
		b3, err := reader.ReadByte()
		if err != nil {
			return 0, 0, false, false, false
		}
		switch b3 {
		case 'A':
			return -1, 0, false, true, false
		case 'B':
			return 1, 0, false, true, false
		case 'C':
			return 0, 1, false, true, false
		case 'D':
			return 0, -1, false, true, false
		}
	}
	return 0, 0, false, false, false
}

func runGrid(username string, reader *bufio.Reader) {
	row, col := 1, 1
	var previous *position
	moveCount := 0

	for {
		flags := evaluateFlags(username)
		render(username, row, col, previous, moveCount, flags)

		dr, dc, quit, ok, timedOut := readKeyWithTimeout(reader, 500*time.Millisecond)
		if timedOut {
			continue
		}
		if quit {
			return
		}
		if !ok {
			continue
		}

		result := tryMove(row, col, dr, dc)
		if result.moved {
			prev := position{row, col}
			previous = &prev
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
	}()

	reader := bufio.NewReader(os.Stdin)
	username, err := readUsername(reader)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	fd := int(os.Stdin.Fd())
	oldState, err := term.MakeRaw(fd)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer term.Restore(fd, oldState)

	runGrid(username, reader)
}
