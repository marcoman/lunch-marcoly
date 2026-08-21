// Console grid navigator demonstrating LaunchDarkly targeting rules.
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

// LaunchDarkly targeting rules inspect the public team context attribute.
// No team intentionally omits the attribute so evaluation reaches fallthrough.
// https://launchdarkly.com/docs/home/flags/target-rules
const (
	flagTeamStyle = "configure-team-label-style"
	appBanner     = "13-flag-targeting-rules[go]"
	bgANSI        = "\033[48;5;236m"
	resetANSI     = "\033[0m"
)

var (
	rows     = [3]string{"t", "m", "b"}
	cols     = [3]string{"l", "m", "r"}
	ldClient *ld.LDClient
)

type login struct {
	username string
	team     string
}

type flagValues struct {
	teamLabel string
	style     string
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
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — flag uses plain default.")
		return
	}
	client, err := ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize — flag uses plain default.")
		return
	}
	ldClient = client
}

// Evaluate the string variation with team as a public context attribute.
// https://launchdarkly.com/docs/home/flags/context-attributes
func evaluateFlags(username, team string) flagValues {
	builder := ldcontext.NewBuilder(username)
	if team != "" {
		builder.SetString("team", team)
	}
	context := builder.Build()

	style := "plain"
	if ldClient != nil {
		candidate, err := ldClient.StringVariation(flagTeamStyle, context, "plain")
		if err == nil {
			switch candidate {
			case "plain", "colored-red", "colored-blue", "colored-yellow":
				style = candidate
			}
		}
	}
	return flagValues{teamLabel: teamLabel(team), style: style}
}

func teamLabel(team string) string {
	switch team {
	case "red":
		return "Team Red"
	case "blue":
		return "Team Blue"
	case "yellow":
		return "Team Yellow"
	default:
		return "No team"
	}
}

func coloredTeam(flags flagValues) string {
	color := ""
	switch flags.style {
	case "colored-red":
		color = "\033[31m"
	case "colored-blue":
		color = "\033[34m"
	case "colored-yellow":
		color = "\033[33m"
	}
	if color == "" {
		return flags.teamLabel
	}
	return color + flags.teamLabel + resetANSI + bgANSI
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

// Prompt for the user key and public team attribute used by targeting rules.
func readLogin(reader *bufio.Reader) (login, error) {
	fmt.Println(appBanner)
	fmt.Println("Login")
	fmt.Println()
	var username string
	for username == "" {
		fmt.Print("Username: ")
		line, err := reader.ReadString('\n')
		if err != nil {
			return login{}, err
		}
		username = strings.TrimSpace(line)
		if username == "" {
			fmt.Println("Username is required.")
		}
	}

	teams := map[string]string{"1": "", "2": "red", "3": "blue", "4": "yellow"}
	for {
		fmt.Print("Team [1=None 2=Red 3=Blue 4=Yellow]: ")
		line, err := reader.ReadString('\n')
		if err != nil {
			return login{}, err
		}
		if team, ok := teams[strings.TrimSpace(line)]; ok {
			return login{username: username, team: team}, nil
		}
		fmt.Println("Choose 1, 2, 3, or 4.")
	}
}

func drawCell(selected bool, line int) string {
	if selected {
		return [3]string{"┏━━━┓", "┃ X ┃", "┗━━━┛"}[line]
	}
	return [3]string{"┌───┐", "│   │", "└───┘"}[line]
}

func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\033[K\r\n")
}

func render(session login, row, col int, previous *position, flags flagValues) {
	var out strings.Builder
	out.WriteString(bgANSI)
	out.WriteString("\033[H\033[2J")

	previousText := "—"
	if previous != nil {
		previousText = formatPos(previous.row, previous.col)
	}
	writeLine(&out, appBanner)
	writeLine(&out, "Name: "+session.username)
	writeLine(&out, "Team: "+coloredTeam(flags))
	writeLine(&out, "Current position: "+formatPos(row, col))
	writeLine(&out, "Previous position: "+previousText)
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (L to logout, Q to quit).")
	writeLine(&out, "")

	for r := 0; r < 3; r++ {
		for line := 0; line < 3; line++ {
			cells := make([]string, 3)
			for c := 0; c < 3; c++ {
				cells[c] = drawCell(r == row && c == col, line)
			}
			writeLine(&out, strings.Join(cells, " "))
		}
	}
	fmt.Print(out.String())
}

func readKeyWithTimeout(reader *bufio.Reader, timeout time.Duration) (int, int, sessionAction, bool, bool) {
	if err := os.Stdin.SetReadDeadline(time.Now().Add(timeout)); err != nil {
		return 0, 0, actionQuit, false, true
	}
	defer os.Stdin.SetReadDeadline(time.Time{})

	key, err := reader.ReadByte()
	if err != nil {
		if timeoutError, ok := err.(interface{ Timeout() bool }); ok && timeoutError.Timeout() {
			return 0, 0, actionQuit, false, false
		}
		return 0, 0, actionQuit, true, true
	}
	switch key {
	case 3, 'q', 'Q':
		return 0, 0, actionQuit, true, true
	case 'l', 'L':
		return 0, 0, actionLogout, true, true
	case 'w', 'W':
		return -1, 0, actionQuit, false, true
	case 's', 'S':
		return 1, 0, actionQuit, false, true
	case 'a', 'A':
		return 0, -1, actionQuit, false, true
	case 'd', 'D':
		return 0, 1, actionQuit, false, true
	case 27:
		second, err := reader.ReadByte()
		if err != nil || second != '[' {
			return 0, 0, actionQuit, false, false
		}
		third, err := reader.ReadByte()
		if err != nil {
			return 0, 0, actionQuit, false, false
		}
		switch third {
		case 'A':
			return -1, 0, actionQuit, false, true
		case 'B':
			return 1, 0, actionQuit, false, true
		case 'C':
			return 0, 1, actionQuit, false, true
		case 'D':
			return 0, -1, actionQuit, false, true
		}
	}
	return 0, 0, actionQuit, false, false
}

// Re-evaluate the team style every 500 ms while navigating.
func runGrid(session login, reader *bufio.Reader) sessionAction {
	row, col := 1, 1
	var previous *position
	for {
		flags := evaluateFlags(session.username, session.team)
		render(session, row, col, previous, flags)
		dr, dc, action, endSession, hasMove := readKeyWithTimeout(reader, 500*time.Millisecond)
		if endSession {
			return action
		}
		if !hasMove {
			continue
		}
		result := tryMove(row, col, dr, dc)
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

	reader := bufio.NewReader(os.Stdin)
	fd := int(os.Stdin.Fd())
	for {
		session, err := readLogin(reader)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		oldState, err := term.MakeRaw(fd)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		action := runGrid(session, reader)
		_ = term.Restore(fd, oldState)
		fmt.Print(resetANSI)
		if action == actionQuit {
			return
		}
	}
}
