// Console grid navigator with LaunchDarkly flag variation evaluation.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	"github.com/launchdarkly/go-sdk-common/v3/ldvalue"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"github.com/launchdarkly/go-server-sdk/v7/ldcomponents"
	"golang.org/x/term"
)

// LaunchDarkly capability: Multivariate flag evaluation + anonymous contexts
// See: https://launchdarkly.com/docs/sdk/features/flag-types
// See: https://launchdarkly.com/docs/sdk/features/anonymous

const (
	flagAnonOsEmoji = "show-anonymous-host-os-emoji"
	flagCountLabel  = "configure-navigation-count-label"
	flagLuckyNumber = "configure-lucky-number"
	flagMaxMoves    = "configure-max-navigation-moves"
	hostOsAttr      = "hostOs"
	anonymousKey    = "anonymous"

	defaultCountLabel  = "Count"
	defaultLuckyNumber = 0
	defaultMaxMoves    = 100
)

var rows = [3]string{"t", "m", "b"}
var cols = [3]string{"l", "m", "r"}

const bgANSI = "\033[48;5;236m"

var ldClient *ld.LDClient
var hostOS = detectHostOS()

type flagValues struct {
	countLabel  string
	luckyNumber int
	maxMoves    int
	osEmoji     string
}

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
}

func detectHostOS() string {
	switch runtime.GOOS {
	case "linux":
		return "linux"
	case "windows":
		return "windows"
	case "darwin":
		return "macos"
	default:
		return "other"
	}
}

func osEmojiFor(hostOs string, showOsEmoji bool) string {
	if !showOsEmoji {
		return ""
	}
	switch hostOs {
	case "linux":
		return "🐧"
	case "macos":
		return "🍎"
	case "windows":
		return "🪟"
	default:
		return "😊"
	}
}

func displayName(username, osEmoji string) string {
	if osEmoji == "" {
		return username
	}
	return osEmoji + " " + username
}

func parseMaxMoves(raw ldvalue.Value) int {
	if raw.IsNull() {
		return defaultMaxMoves
	}
	if raw.Type() == ldvalue.ObjectType {
		if v := raw.GetByKey("maxMoves"); v.IsNumber() {
			return int(v.IntValue())
		}
	}
	if raw.IsString() {
		var parsed map[string]interface{}
		if err := json.Unmarshal([]byte(raw.StringValue()), &parsed); err == nil {
			if v, ok := parsed["maxMoves"].(float64); ok {
				return int(v)
			}
		}
	}
	return defaultMaxMoves
}

func buildFlagResponse(countLabel string, luckyNumber, maxMoves int, osEmoji string) flagValues {
	if countLabel == "" {
		countLabel = defaultCountLabel
	}
	return flagValues{
		countLabel:  countLabel,
		luckyNumber: luckyNumber,
		maxMoves:    maxMoves,
		osEmoji:     osEmoji,
	}
}

func defaults() flagValues {
	return buildFlagResponse(defaultCountLabel, defaultLuckyNumber, defaultMaxMoves, "")
}

func initLaunchDarkly() {
	sdkKey := os.Getenv("LD_SDK_KEY")
	if sdkKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — flags default to off.")
		return
	}
	config := ld.Config{
		Events: ldcomponents.SendEvents().PrivateAttributes(hostOsAttr),
	}
	client, err := ld.MakeCustomClient(sdkKey, config, 5*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize — flags default to off.")
		return
	}
	ldClient = client
}

func evaluateFlags(username string) flagValues {
	if ldClient == nil {
		return defaults()
	}
	anonContext := ldcontext.NewBuilder(anonymousKey).
		Anonymous(true).
		SetString(hostOsAttr, hostOS).
		Private(hostOsAttr).
		Build()
	userContext := ldcontext.NewBuilder(username).Build()

	showEmoji, _ := ldClient.BoolVariation(flagAnonOsEmoji, anonContext, false)
	countLabel, _ := ldClient.StringVariation(flagCountLabel, userContext, defaultCountLabel)
	luckyNumber, _ := ldClient.IntVariation(flagLuckyNumber, userContext, defaultLuckyNumber)
	maxMovesRaw, _ := ldClient.JSONVariation(
		flagMaxMoves,
		userContext,
		ldvalue.ObjectBuild().Set("maxMoves", ldvalue.Int(defaultMaxMoves)).Build(),
	)

	return buildFlagResponse(
		countLabel,
		luckyNumber,
		parseMaxMoves(maxMovesRaw),
		osEmojiFor(hostOS, showEmoji),
	)
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

func drawCell(selected bool, line int) string {
	if selected {
		switch line {
		case 0:
			return "┏━━━┓"
		case 1:
			return "┃ X ┃"
		default:
			return "┗━━━┛"
		}
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

	writeLine(&out, fmt.Sprintf("Name: %s", displayName(username, flags.osEmoji)))
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	writeLine(&out, fmt.Sprintf("%s: %d", flags.countLabel, moveCount))
	writeLine(&out, fmt.Sprintf("Lucky Number is: %d", flags.luckyNumber))
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (L to logout, Q to quit).")
	writeLine(&out, "")

	for r := 0; r < 3; r++ {
		top := make([]string, 3)
		mid := make([]string, 3)
		bot := make([]string, 3)
		for c := 0; c < 3; c++ {
			selected := r == row && c == col
			top[c] = drawCell(selected, 0)
			mid[c] = drawCell(selected, 1)
			bot[c] = drawCell(selected, 2)
		}
		writeLine(&out, strings.Join(top, " "))
		writeLine(&out, strings.Join(mid, " "))
		writeLine(&out, strings.Join(bot, " "))
	}

	fmt.Print(out.String())
}

type sessionAction int

const (
	actionQuit sessionAction = iota
	actionLogout
)

func readKeyWithTimeout(reader *bufio.Reader, timeout time.Duration) (dr, dc int, action sessionAction, endSession, ok, timedOut bool) {
	if err := os.Stdin.SetReadDeadline(time.Now().Add(timeout)); err != nil {
		return 0, 0, actionQuit, false, false, true
	}
	defer os.Stdin.SetReadDeadline(time.Time{})

	b, err := reader.ReadByte()
	if err != nil {
		if ne, ok := err.(interface{ Timeout() bool }); ok && ne.Timeout() {
			return 0, 0, actionQuit, false, false, true
		}
		return 0, 0, actionQuit, true, false, false
	}

	switch b {
	case 3, 'q', 'Q':
		return 0, 0, actionQuit, true, true, false
	case 'l', 'L':
		return 0, 0, actionLogout, true, true, false
	case 'w', 'W':
		return -1, 0, 0, false, true, false
	case 's', 'S':
		return 1, 0, 0, false, true, false
	case 'a', 'A':
		return 0, -1, 0, false, true, false
	case 'd', 'D':
		return 0, 1, 0, false, true, false
	case 27:
		b2, err := reader.ReadByte()
		if err != nil || b2 != '[' {
			return 0, 0, 0, false, false, false
		}
		b3, err := reader.ReadByte()
		if err != nil {
			return 0, 0, 0, false, false, false
		}
		switch b3 {
		case 'A':
			return -1, 0, 0, false, true, false
		case 'B':
			return 1, 0, 0, false, true, false
		case 'C':
			return 0, 1, 0, false, true, false
		case 'D':
			return 0, -1, 0, false, true, false
		}
	}
	return 0, 0, 0, false, false, false
}

func runGrid(username string, reader *bufio.Reader) sessionAction {
	row, col := 1, 1
	var previous *position
	moveCount := 0

	for {
		flags := evaluateFlags(username)
		render(username, row, col, previous, moveCount, flags)

		dr, dc, action, endSession, ok, timedOut := readKeyWithTimeout(reader, 500*time.Millisecond)
		if timedOut {
			continue
		}
		if endSession {
			return action
		}
		if !ok {
			continue
		}

		if moveCount >= flags.maxMoves {
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
