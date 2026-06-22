// Console grid navigator with ABCD navigation count label (LaunchDarkly string flag).
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

// LaunchDarkly capability: String flag evaluation for multivariate A/B/C/D test
// See: https://launchdarkly.com/docs/sdk/features/flag-types

const (
	flagCountLabel     = "configure-navigation-count-label"
	defaultCountLabel  = "Count"
)

var rows = [3]string{"t", "m", "b"}
var cols = [3]string{"l", "m", "r"}

var ldClient *ld.LDClient

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
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

func evaluateCountLabel(username string) string {
	if ldClient == nil {
		return defaultCountLabel
	}
	userContext := ldcontext.NewBuilder(username).Build()
	label, _ := ldClient.StringVariation(flagCountLabel, userContext, defaultCountLabel)
	if label == "" {
		return defaultCountLabel
	}
	return label
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

func render(username string, row, col int, previous *position, moveCount int, countLabel string) {
	var out strings.Builder
	out.WriteString("\033[H\033[2J")

	prevText := "—"
	if previous != nil {
		prevText = formatPos(previous.row, previous.col)
	}

	writeLine(&out, fmt.Sprintf("Name: %s", username))
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	writeLine(&out, fmt.Sprintf("%s: %d", countLabel, moveCount))
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
	moveCount := 0
	countLabel := evaluateCountLabel(username)

	for {
		render(username, row, col, previous, moveCount, countLabel)

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

	if len(os.Args) >= 3 && os.Args[1] == "--evaluate-once" {
		fmt.Println(evaluateCountLabel(os.Args[2]))
		return
	}

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
