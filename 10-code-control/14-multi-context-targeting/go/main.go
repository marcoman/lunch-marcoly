// Console grid navigator demonstrating LaunchDarkly multi-context targeting.
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

// LaunchDarkly: one variation call with kind multi (user + organization).
// https://launchdarkly.com/docs/home/flags/multi-contexts
const (
	flagPartnerBadge = "show-partner-org-badge"
	appBanner        = "14-multi-context-targeting[go]"
	bgANSI           = "\033[48;5;236m"
	resetANSI        = "\033[0m"
	greenANSI        = "\033[32m"
)

var (
	rows     = [3]string{"t", "m", "b"}
	cols     = [3]string{"l", "m", "r"}
	ldClient *ld.LDClient
)

type login struct {
	username string
	org      string
}

type flagValues struct {
	username string
	org      string
	orgLabel string
	partner  bool
}

type position struct {
	row, col int
}

type moveResult struct {
	row, col int
	moved    bool
}

// One keystroke, decoded into everything the grid loop needs to know.
type keyEvent struct {
	dr, dc      int
	action      sessionAction
	endsSession bool
	hasMove     bool
	nextUser    string
	nextOrg     string
}

type sessionAction int

const (
	actionQuit sessionAction = iota
	actionLogout
)

func initLaunchDarkly() {
	sdkKey := os.Getenv("LD_SDK_KEY")
	if sdkKey == "" {
		fmt.Fprintln(os.Stderr, "Warning: LD_SDK_KEY not set — partner badge stays false.")
		return
	}
	client, err := ld.MakeClient(sdkKey, 5*time.Second)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warning: LaunchDarkly SDK did not initialize — partner badge stays false.")
		return
	}
	ldClient = client
}

func orgLabel(org string) string {
	if org == "globex" {
		return "Globex"
	}
	return "Acme"
}

// Evaluate show-partner-org-badge. Org is a separate context kind, not a user attribute.
func evaluateFlags(username, org string) flagValues {
	user := ldcontext.NewBuilder(username).Kind("user").Build()
	organization := ldcontext.NewBuilder(org).Kind("organization").SetString("name", orgLabel(org)).Build()
	context := ldcontext.NewMulti(user, organization)

	partner := false
	if ldClient != nil {
		value, err := ldClient.BoolVariation(flagPartnerBadge, context, false)
		if err == nil {
			partner = value
		}
	}
	return flagValues{
		username: username,
		org:      org,
		orgLabel: orgLabel(org),
		partner:  partner,
	}
}

func nameLine(username string, flags flagValues) string {
	if !flags.partner {
		return "Name: " + username
	}
	return "Name: " + username + "  " + greenANSI + "partner" + resetANSI + bgANSI
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

// A terminal fd does not support read deadlines, so a dedicated goroutine owns
// stdin and hands bytes to the render loop over a channel. That keeps the
// 500 ms flag refresh from blocking on input, and vice versa.
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

// Read a whole line while the terminal is still in cooked mode (it echoes).
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

// Prompt for Alice/Bob and Acme/Globex — the two multi-context keys.
func readLogin(stream *keyStream) (login, error) {
	fmt.Println(appBanner)
	fmt.Println("Login")
	fmt.Println()
	var username string
	for username == "" {
		fmt.Print("User [1=Alice 2=Bob]: ")
		line, ok := stream.readLine()
		if !ok {
			return login{}, fmt.Errorf("stdin closed")
		}
		switch line {
		case "1":
			username = "alice"
		case "2":
			username = "bob"
		default:
			fmt.Println("Choose 1 or 2.")
		}
	}
	for {
		fmt.Print("Org  [1=Acme 2=Globex]: ")
		line, ok := stream.readLine()
		if !ok {
			return login{}, fmt.Errorf("stdin closed")
		}
		switch line {
		case "1":
			return login{username: username, org: "acme"}, nil
		case "2":
			return login{username: username, org: "globex"}, nil
		default:
			fmt.Println("Choose 1 or 2.")
		}
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
	writeLine(&out, nameLine(session.username, flags))
	writeLine(&out, "Org: "+flags.orgLabel)
	writeLine(&out, "Current position: "+formatPos(row, col))
	writeLine(&out, "Previous position: "+previousText)
	writeLine(&out, "")
	writeLine(&out, "1/2 user Alice/Bob, 3/4 org Acme/Globex. Arrows or WASD. L logout, Q quit.")
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
	case '1':
		return keyEvent{nextUser: "alice"}
	case '2':
		return keyEvent{nextUser: "bob"}
	case '3':
		return keyEvent{nextOrg: "acme"}
	case '4':
		return keyEvent{nextOrg: "globex"}
	case 'w', 'W':
		return keyEvent{dr: -1, hasMove: true}
	case 's', 'S':
		return keyEvent{dr: 1, hasMove: true}
	case 'a', 'A':
		return keyEvent{dc: -1, hasMove: true}
	case 'd', 'D':
		return keyEvent{dc: 1, hasMove: true}
	case 27:
		// An arrow key arrives as ESC [ A-D; a bare ESC times out here.
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

// Re-evaluate the partner badge every 500 ms; 1–4 walk the 2×2 without logout.
func runGrid(session login, stream *keyStream) sessionAction {
	row, col := 1, 1
	var previous *position
	for {
		flags := evaluateFlags(session.username, session.org)
		render(session, row, col, previous, flags)
		event := readKeyEvent(stream, 500*time.Millisecond)
		if event.endsSession {
			return event.action
		}
		if event.nextUser != "" {
			session.username = event.nextUser
			continue
		}
		if event.nextOrg != "" {
			session.org = event.nextOrg
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
		session, err := readLogin(stream)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		oldState, err := term.MakeRaw(fd)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		action := runGrid(session, stream)
		_ = term.Restore(fd, oldState)
		fmt.Print(resetANSI)
		if action == actionQuit {
			return
		}
	}
}
