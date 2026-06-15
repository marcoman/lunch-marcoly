// Console grid navigator: username login and 3×3 keyboard navigation.
package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"golang.org/x/term"
)

var rows = [3]string{"t", "m", "b"}
var cols = [3]string{"l", "m", "r"}

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
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
			return "\033[92m┏━━━┓\033[0m"
		case 1:
			return "\033[92m┃ X ┃\033[0m"
		default:
			return "\033[92m┗━━━┛\033[0m"
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

// writeLine prints a full line in raw mode (\n alone does not return to column 0).
func writeLine(out *strings.Builder, line string) {
	out.WriteString(line)
	out.WriteString("\r\n")
}

func render(username string, row, col int, previous *position) {
	var out strings.Builder
	out.WriteString("\033[H\033[2J")

	prevText := "—"
	if previous != nil {
		prevText = formatPos(previous.row, previous.col)
	}

	writeLine(&out, fmt.Sprintf("Name: %s", username))
	writeLine(&out, fmt.Sprintf("Current position: %s", formatPos(row, col)))
	writeLine(&out, fmt.Sprintf("Previous position: %s", prevText))
	writeLine(&out, "")
	writeLine(&out, "Use arrow keys or WASD to move (q to quit).")
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

func readKey(reader *bufio.Reader) (dr, dc int, quit bool, ok bool) {
	b, err := reader.ReadByte()
	if err != nil {
		return 0, 0, true, false
	}
	switch b {
	case 3, 'q', 'Q':
		return 0, 0, true, true
	case 'w', 'W':
		return -1, 0, false, true
	case 's', 'S':
		return 1, 0, false, true
	case 'a', 'A':
		return 0, -1, false, true
	case 'd', 'D':
		return 0, 1, false, true
	case 27:
		b2, err := reader.ReadByte()
		if err != nil || b2 != '[' {
			return 0, 0, false, false
		}
		b3, err := reader.ReadByte()
		if err != nil {
			return 0, 0, false, false
		}
		switch b3 {
		case 'A':
			return -1, 0, false, true
		case 'B':
			return 1, 0, false, true
		case 'C':
			return 0, 1, false, true
		case 'D':
			return 0, -1, false, true
		}
	}
	return 0, 0, false, false
}

func runGrid(username string, reader *bufio.Reader) {
	row, col := 1, 1
	var previous *position
	render(username, row, col, previous)

	for {
		dr, dc, quit, ok := readKey(reader)
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
		}
		render(username, row, col, previous)
	}
}

func main() {
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
