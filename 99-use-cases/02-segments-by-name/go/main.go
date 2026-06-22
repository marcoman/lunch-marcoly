// Console grid navigator with LaunchDarkly segment-by-name highlight (string flag).
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"time"
	"unicode"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"golang.org/x/term"
)

// LaunchDarkly capability: String flag variation from segment targeting
// See: https://launchdarkly.com/docs/home/flags/segments

const (
	flagHighlight    = "configure-grid-selection-green-highlight"
	defaultHighlight = "none"
)

var (
	rows       = [3]string{"t", "m", "b"}
	cols       = [3]string{"l", "m", "r"}
	colorNames = map[string]struct{}{
		"yellow": {}, "red": {}, "blue": {}, "green": {}, "purple": {},
	}
	validColors = colorNames
)

const (
	segmentGeneric    = "generic"
	segmentNamedColor = "named-color"
	segmentHuman      = "human"
	segmentRobot      = "robot"
	segmentHumanBeta  = "human-beta"
	segmentRobotBeta  = "robot-beta"
)

var ldClient *ld.LDClient

type segmentInfo struct {
	segmentType string
	namedColor  string
}

type flagValues struct {
	highlightColor string
	segmentLabel   string
	segmentType    string
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

func letterCount(username string) int {
	count := 0
	for _, ch := range username {
		if unicode.IsLetter(ch) {
			count++
		}
	}
	return count
}

func resolveSegmentInfo(username string) segmentInfo {
	lower := strings.ToLower(username)

	if lower == "generic" {
		return segmentInfo{segmentType: segmentGeneric}
	}
	if _, ok := colorNames[lower]; ok {
		return segmentInfo{segmentType: segmentNamedColor, namedColor: lower}
	}

	isHuman := letterCount(username)%2 == 0
	isBeta := strings.Contains(lower, "beta")

	if isHuman && isBeta {
		return segmentInfo{segmentType: segmentHumanBeta}
	}
	if isHuman {
		return segmentInfo{segmentType: segmentHuman}
	}
	if isBeta {
		return segmentInfo{segmentType: segmentRobotBeta}
	}
	return segmentInfo{segmentType: segmentRobot}
}

func buildSegmentContext(username string) (ldcontext.Context, segmentInfo) {
	info := resolveSegmentInfo(username)
	builder := ldcontext.NewBuilder(username).SetString("segmentType", info.segmentType)

	switch info.segmentType {
	case segmentGeneric:
		builder.SetBool("generic", true)
	case segmentNamedColor:
		builder.SetString("namedColor", info.namedColor)
	default:
		userKind := "human"
		if strings.HasPrefix(info.segmentType, "robot") {
			userKind = "robot"
		}
		builder.SetString("userKind", userKind)
		builder.SetBool("beta", strings.HasSuffix(info.segmentType, "beta"))
	}

	return builder.Build(), info
}

func colorLabelName(highlightColor string) string {
	if highlightColor == "none" {
		return "no-color"
	}
	return highlightColor
}

func formatSegmentLabel(info segmentInfo, highlightColor string) string {
	colorName := colorLabelName(highlightColor)
	switch info.segmentType {
	case segmentGeneric:
		return "(generic)"
	case segmentNamedColor:
		return fmt.Sprintf("(%s)", colorName)
	case segmentHuman, segmentRobot, segmentHumanBeta, segmentRobotBeta:
		return fmt.Sprintf("(%s-%s)", info.segmentType, colorName)
	default:
		return fmt.Sprintf("(%s)", colorName)
	}
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

func buildFlagResponse(highlightColor string, info segmentInfo) flagValues {
	color := normalizeHighlightColor(highlightColor)
	return flagValues{
		highlightColor: color,
		segmentLabel:   formatSegmentLabel(info, color),
		segmentType:    info.segmentType,
	}
}

func evaluateHighlight(username string) flagValues {
	_, info := buildSegmentContext(username)
	if ldClient == nil {
		return buildFlagResponse(defaultHighlight, info)
	}
	context, _ := buildSegmentContext(username)
	raw, _ := ldClient.StringVariation(flagHighlight, context, defaultHighlight)
	return buildFlagResponse(raw, info)
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

const (
	bgReset = "\033[48;5;236m"
	reset   = "\033[0m"
)

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

	nameLine := fmt.Sprintf(
		"Name: %s%s",
		colorize(username, flags.highlightColor),
		colorize(" "+flags.segmentLabel, flags.highlightColor),
	)
	writeLine(&out, nameLine+reset+bgReset)
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (L to logout, Q to quit).")
	writeLine(&out, "")

	cellColor := flags.highlightColor
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
	flags := evaluateHighlight(username)

	for {
		render(username, row, col, previous, flags)

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
