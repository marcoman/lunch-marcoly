// Console grid navigator — create and evaluate a single LaunchDarkly highlight flag.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"golang.org/x/term"
)

const (
	appBanner        = "11-create-eval-flag[go]"
	flagHighlight    = "configure-grid-selection-green-highlight"
	defaultHighlight = "none"
)

var (
	rows        = [3]string{"t", "m", "b"}
	cols        = [3]string{"l", "m", "r"}
	validColors = map[string]struct{}{
		"yellow": {}, "red": {}, "blue": {}, "green": {}, "purple": {},
	}
	ldClient *ld.LDClient
)

const (
	bgReset = "\033[48;5;236m"
	reset   = "\033[0m"
)

type flagValues struct {
	Username       string `json:"username"`
	FlagValue      string `json:"flagValue"`
	HighlightColor string `json:"highlightColor"`
	ColorLabel     string `json:"colorLabel"`
}

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
}

type sessionAction int

const (
	actionQuit sessionAction = iota
	actionLogout
)

func initLaunchDarkly() {
	sdkKey := os.Getenv("LD_SDK_KEY")
	if sdkKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — highlight defaults to none.")
		return
	}
	client, err := ld.MakeClient(sdkKey, 10*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize — highlight defaults to none.")
		return
	}
	ldClient = client
}

func normalizeHighlightColor(raw interface{}) string {
	color := strings.ToLower(strings.TrimSpace(fmt.Sprint(raw)))
	if color == "" {
		color = "none"
	}
	if _, ok := validColors[color]; ok {
		return color
	}
	return "none"
}

func colorLabel(highlightColor string) string {
	if highlightColor == "none" {
		return "(no-color)"
	}
	return fmt.Sprintf("(%s)", highlightColor)
}

func buildResponse(username string, raw interface{}) flagValues {
	color := normalizeHighlightColor(raw)
	flagValue := strings.TrimSpace(fmt.Sprint(raw))
	if flagValue == "" {
		flagValue = "none"
	}
	return flagValues{
		Username:       username,
		FlagValue:      flagValue,
		HighlightColor: color,
		ColorLabel:     colorLabel(color),
	}
}

func evaluateHighlight(username string) flagValues {
	if ldClient == nil || username == "" {
		return buildResponse(username, defaultHighlight)
	}
	context := ldcontext.NewBuilder(username).Build()
	raw, _ := ldClient.StringVariation(flagHighlight, context, defaultHighlight)
	return buildResponse(username, raw)
}

func ansiColor(color string) string {
	switch color {
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
	return ansi + text + reset + bgReset
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
	fmt.Println(appBanner)
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

func drawCell(selected bool, line int, color string) string {
	if !selected {
		switch line {
		case 0:
			return "┌───┐"
		case 1:
			return "│   │"
		default:
			return "└───┘"
		}
	}
	var text string
	switch line {
	case 0:
		text = "┏━━━┓"
	case 1:
		text = "┃ X ┃"
	default:
		text = "┗━━━┛"
	}
	if color != "" && color != "none" {
		return colorize(text, color)
	}
	return text
}

func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\r\n")
}

func render(username string, row, col int, previous *position, flags flagValues) {
	var out strings.Builder
	out.WriteString("\033[H\033[2J")
	out.WriteString(bgReset)

	prevText := "—"
	if previous != nil {
		prevText = formatPos(previous.row, previous.col)
	}

	writeLine(&out, appBanner)
	nameLine := fmt.Sprintf(
		"Name: %s%s",
		colorize(username, flags.HighlightColor),
		colorize(" "+flags.ColorLabel, flags.HighlightColor),
	)
	writeLine(&out, nameLine+reset+bgReset)
	writeLine(&out, fmt.Sprintf("Flag value: %s", flags.FlagValue))
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (L to logout, Q to quit).")
	writeLine(&out, "Toggle the flag in LaunchDarkly — changes appear within ~1s.")
	writeLine(&out, "")

	cellColor := flags.HighlightColor
	for r := 0; r < 3; r++ {
		top := make([]string, 3)
		mid := make([]string, 3)
		bot := make([]string, 3)
		for c := 0; c < 3; c++ {
			selected := r == row && c == col
			highlight := "none"
			if selected && cellColor != "none" {
				highlight = cellColor
			}
			top[c] = drawCell(selected, 0, highlight)
			mid[c] = drawCell(selected, 1, highlight)
			bot[c] = drawCell(selected, 2, highlight)
		}
		writeLine(&out, strings.Join(top, " "))
		writeLine(&out, strings.Join(mid, " "))
		writeLine(&out, strings.Join(bot, " "))
	}

	fmt.Print(out.String())
}

func readKey(reader *bufio.Reader) (dr, dc int, action sessionAction, endSession, ok bool) {
	b, err := reader.ReadByte()
	if err != nil {
		return 0, 0, actionQuit, true, false
	}
	switch b {
	case 3, 'q', 'Q':
		return 0, 0, actionQuit, true, true
	case 'l', 'L':
		return 0, 0, actionLogout, true, true
	case 'w', 'W':
		return -1, 0, 0, false, true
	case 's', 'S':
		return 1, 0, 0, false, true
	case 'a', 'A':
		return 0, -1, 0, false, true
	case 'd', 'D':
		return 0, 1, 0, false, true
	case 27:
		b2, err := reader.ReadByte()
		if err != nil || b2 != '[' {
			return 0, 0, 0, false, false
		}
		b3, err := reader.ReadByte()
		if err != nil {
			return 0, 0, 0, false, false
		}
		switch b3 {
		case 'A':
			return -1, 0, 0, false, true
		case 'B':
			return 1, 0, 0, false, true
		case 'C':
			return 0, 1, 0, false, true
		case 'D':
			return 0, -1, 0, false, true
		}
	}
	return 0, 0, 0, false, false
}

func runGrid(username string, reader *bufio.Reader) sessionAction {
	row, col := 1, 1
	var previous *position
	lastEval := time.Time{}

	for {
		flags := evaluateHighlight(username)
		render(username, row, col, previous, flags)
		lastEval = time.Now()

		for time.Since(lastEval) < 500*time.Millisecond {
			if reader.Buffered() > 0 {
				break
			}
			time.Sleep(50 * time.Millisecond)
		}
		if reader.Buffered() == 0 && time.Since(lastEval) >= 500*time.Millisecond {
			continue
		}

		dr, dc, action, endSession, ok := readKey(reader)
		if !ok {
			continue
		}
		if endSession {
			return action
		}
		result := tryMove(row, col, dr, dc)
		if result.moved {
			prev := position{row, col}
			previous = &prev
			row, col = result.row, result.col
		}
	}
}

func main() {
	if len(os.Args) >= 3 && os.Args[1] == "--evaluate-once" {
		initLaunchDarkly()
		defer func() {
			if ldClient != nil {
				ldClient.Close()
			}
		}()
		result := evaluateHighlight(os.Args[2])
		enc := json.NewEncoder(os.Stdout)
		enc.SetEscapeHTML(false)
		_ = enc.Encode(result)
		return
	}

	initLaunchDarkly()
	defer func() {
		if ldClient != nil {
			ldClient.Close()
		}
	}()

	reader := bufio.NewReader(os.Stdin)
	fd := int(os.Stdin.Fd())

	for {
		username, err := readUsername(reader)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}

		oldState, err := term.MakeRaw(fd)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}

		action := runGrid(username, reader)
		term.Restore(fd, oldState)

		if action == actionQuit {
			break
		}
	}
}
