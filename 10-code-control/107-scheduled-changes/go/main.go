// Console grid navigator for LaunchDarkly scheduled flag changes.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/launchdarkly/go-sdk-common/v3/ldcontext"
	ld "github.com/launchdarkly/go-server-sdk/v7"
	"golang.org/x/term"
)

// LaunchDarkly: scheduled changes use REST for control and SDK evaluation for observation.
// https://launchdarkly.com/docs/home/flags/scheduled-changes
const (
	flagKey   = "enable-grid-selection-highlight-sched"
	appBanner = "17-scheduled-changes[go]"
	bg        = "\033[48;5;236m"
	reset     = "\033[0m"
	green     = "\033[92m"
)

var rows = [3]string{"t", "m", "b"}
var cols = [3]string{"l", "m", "r"}
var delays = [4]int{1, 2, 5, 10}

type flagValues struct {
	value, reason, variation string
}
type position struct{ row, col int }
type scheduledChange struct {
	ID            string `json:"_id"`
	CreatedAt     int64  `json:"_creationDate"`
	ExecutionDate int64  `json:"executionDate"`
}
type listResponse struct {
	Items []scheduledChange `json:"items"`
}
type restClient struct {
	token, project, environment, host, version string
	http                                       *http.Client
}
type keyStream struct{ keys chan byte }

func newRESTClient() *restClient {
	return &restClient{
		token:       strings.TrimSpace(os.Getenv("LD_API_ACCESS_TOKEN")),
		project:     strings.TrimSpace(os.Getenv("LD_PROJECT_KEY")),
		environment: strings.TrimSpace(os.Getenv("LD_ENVIRONMENT_KEY")),
		host:        envOr("LD_API_HOST", "https://app.launchdarkly.com"),
		version:     envOr("LD_API_VERSION", "20240415"),
		http:        &http.Client{Timeout: 30 * time.Second},
	}
}
func envOr(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}
func (r *restClient) missing() []string {
	var result []string
	if r.token == "" {
		result = append(result, "LD_API_ACCESS_TOKEN")
	}
	if r.project == "" {
		result = append(result, "LD_PROJECT_KEY")
	}
	if r.environment == "" {
		result = append(result, "LD_ENVIRONMENT_KEY")
	}
	return result
}
func (r *restClient) basePath() string {
	return fmt.Sprintf("/projects/%s/flags/%s/environments/%s/scheduled-changes",
		url.PathEscape(r.project), url.PathEscape(flagKey), url.PathEscape(r.environment))
}
func (r *restClient) request(method, path string, body any, semantic bool, result any) error {
	if missing := r.missing(); len(missing) > 0 {
		return fmt.Errorf("scheduled changes need %s", strings.Join(missing, ", "))
	}
	var reader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(data)
	}
	req, err := http.NewRequest(method, strings.TrimRight(r.host, "/")+"/api/v2"+path, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", r.token)
	req.Header.Set("LD-API-Version", r.version)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		content := "application/json"
		if semantic {
			content += "; domain-model=launchdarkly.semanticpatch"
		}
		req.Header.Set("Content-Type", content)
	}
	resp, err := r.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var apiErr struct {
			Message string `json:"message"`
		}
		_ = json.Unmarshal(data, &apiErr)
		if apiErr.Message == "" {
			apiErr.Message = strings.TrimSpace(string(data))
		}
		return fmt.Errorf("LaunchDarkly API %d: %s", resp.StatusCode, apiErr.Message)
	}
	if result != nil && len(data) > 0 {
		return json.Unmarshal(data, result)
	}
	return nil
}
func (r *restClient) list() ([]scheduledChange, error) {
	var response listResponse
	err := r.request(http.MethodGet, r.basePath(), nil, false, &response)
	return response.Items, err
}
func (r *restClient) deletePending() error {
	items, err := r.list()
	if err != nil {
		return err
	}
	for _, item := range items {
		if item.ID != "" {
			if err := r.request(http.MethodDelete, r.basePath()+"/"+url.PathEscape(item.ID), nil, false, nil); err != nil {
				return err
			}
		}
	}
	return nil
}
func (r *restClient) turnOff(comment string) error {
	path := fmt.Sprintf("/flags/%s/%s", url.PathEscape(r.project), url.PathEscape(flagKey))
	body := map[string]any{"environmentKey": r.environment, "comment": comment,
		"instructions": []map[string]string{{"kind": "turnFlagOff"}}}
	return r.request(http.MethodPatch, path, body, true, nil)
}
func (r *restClient) start(minutes int) (scheduledChange, int64, error) {
	if err := r.deletePending(); err != nil {
		return scheduledChange{}, 0, err
	}
	if err := r.turnOff("17-scheduled-changes: reset off before starting demo"); err != nil {
		return scheduledChange{}, 0, err
	}
	started := time.Now().UnixMilli()
	change := scheduledChange{ExecutionDate: started + int64(minutes)*60_000}
	body := map[string]any{"executionDate": change.ExecutionDate,
		"instructions": []map[string]string{{"kind": "turnFlagOn"}},
		"comment":      fmt.Sprintf("17-scheduled-changes: turn highlight on after %d minute(s)", minutes)}
	if err := r.request(http.MethodPost, r.basePath(), body, false, &change); err != nil {
		return scheduledChange{}, 0, err
	}
	return change, started, nil
}
func (r *restClient) stop() (int64, error) {
	if err := r.deletePending(); err != nil {
		return 0, err
	}
	if err := r.turnOff("17-scheduled-changes: stop demo and turn highlight off"); err != nil {
		return 0, err
	}
	return time.Now().UnixMilli(), nil
}

func evaluate(client *ld.LDClient, username string) flagValues {
	if client == nil {
		return flagValues{"none", "ERROR", "default"}
	}
	ctx := ldcontext.NewBuilder(username).Kind("user").Name(username).Build()
	value, detail, _ := client.StringVariationDetail(flagKey, ctx, "none")
	if value != "none" && value != "green" {
		value = "none"
	}
	variation := "default"
	if index, ok := detail.VariationIndex.Get(); ok {
		variation = fmt.Sprint(index)
	}
	return flagValues{value, string(detail.Reason.GetKind()), variation}
}
func colorize(text, value string) string {
	if value == "green" {
		return green + text + reset + bg
	}
	return text
}
func formatPos(row, col int) string { return rows[row] + "/" + cols[col] }
func clock(ms int64) string {
	if ms < 0 {
		ms = 0
	}
	seconds := ms / 1000
	return fmt.Sprintf("%d:%02d", seconds/60, seconds%60)
}
func wall(ms int64) string {
	if ms == 0 {
		return "—"
	}
	return time.UnixMilli(ms).Format("15:04:05")
}
func writeLine(out *strings.Builder, text string) { out.WriteString(text + "\033[K\r\n") }
func render(username string, row, col int, previous *position, flags flagValues, delay int,
	started, stopped, observed, execution int64, pending bool, rest *restClient, errorText string) {
	var out strings.Builder
	out.WriteString(bg + "\033[H\033[2J")
	prev := "—"
	if previous != nil {
		prev = formatPos(previous.row, previous.col)
	}
	end := time.Now().UnixMilli()
	if stopped != 0 {
		end = stopped
	}
	elapsed := "0:00"
	if started != 0 {
		elapsed = clock(end - started)
	}
	status, timing := "No pending change.", "G starts a schedule. T stops it and turns the flag off."
	if pending {
		status, timing = "PENDING · LaunchDarkly will turn the flag on", "Scheduled wall time: "+wall(execution)
	} else if stopped != 0 {
		status, timing = "STOPPED · pending change cancelled, flag off", "Stopped at "+wall(stopped)
		if started != 0 {
			timing += " after " + clock(stopped-started) + " elapsed."
		}
	} else if flags.value == "green" && started != 0 {
		status, timing = "APPLIED · SDK now serves green", "Scheduled for "+wall(execution)
		if observed != 0 {
			timing += "; green first observed here at " + clock(observed-started)
		}
	}
	writeLine(&out, appBanner)
	writeLine(&out, "Name: "+colorize(username, flags.value))
	writeLine(&out, fmt.Sprintf("Current: %s   Previous: %s", formatPos(row, col), prev))
	writeLine(&out, fmt.Sprintf("Flag value: %s   reason: %s   idx: %s", flags.value, flags.reason, flags.variation))
	writeLine(&out, fmt.Sprintf("Delay: %d min   Elapsed: %s", delay, elapsed))
	writeLine(&out, status)
	writeLine(&out, timing)
	if missing := rest.missing(); len(missing) > 0 {
		writeLine(&out, "REST disabled — set "+strings.Join(missing, ", "))
	} else {
		writeLine(&out, "REST configured")
	}
	writeLine(&out, "G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit")
	writeLine(&out, "Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms.")
	if errorText != "" {
		writeLine(&out, errorText)
	}
	writeLine(&out, "")
	for r := 0; r < 3; r++ {
		for line := 0; line < 3; line++ {
			cells := make([]string, 3)
			for c := 0; c < 3; c++ {
				selected := r == row && c == col
				if selected {
					cells[c] = colorize([3]string{"┏━━━┓", "┃ X ┃", "┗━━━┛"}[line], flags.value)
				} else {
					cells[c] = [3]string{"┌───┐", "│   │", "└───┘"}[line]
				}
			}
			writeLine(&out, strings.Join(cells, " "))
		}
	}
	fmt.Print(out.String())
}

func newKeyStream() *keyStream {
	stream := &keyStream{make(chan byte, 64)}
	go func() {
		defer close(stream.keys)
		reader := bufio.NewReader(os.Stdin)
		for {
			b, e := reader.ReadByte()
			if e != nil {
				return
			}
			stream.keys <- b
		}
	}()
	return stream
}
func (s *keyStream) next(timeout time.Duration) (byte, bool) {
	select {
	case b, ok := <-s.keys:
		return b, ok
	case <-time.After(timeout):
		return 0, true
	}
}
func (s *keyStream) line() (string, bool) {
	var value strings.Builder
	for b := range s.keys {
		if b == '\n' || b == '\r' {
			return strings.TrimSpace(value.String()), true
		}
		value.WriteByte(b)
	}
	return "", false
}
func readUsername(s *keyStream) (string, error) {
	fmt.Printf("%s\nLogin\nUsername becomes the LaunchDarkly user context key.\n\n", appBanner)
	for {
		fmt.Print("Username: ")
		name, ok := s.line()
		if !ok {
			return "", fmt.Errorf("stdin closed")
		}
		if name != "" {
			return name, nil
		}
		fmt.Println("Username is required.")
	}
}
func runGrid(username string, stream *keyStream, client *ld.LDClient, rest *restClient) bool {
	row, col, delayIndex := 1, 1, 0
	var previous *position
	var started, stopped, observed, execution int64
	pending := false
	errorText := ""
	for {
		flags := evaluate(client, username)
		if started != 0 && stopped == 0 && observed == 0 && flags.value == "green" {
			observed = time.Now().UnixMilli()
		}
		if len(rest.missing()) == 0 {
			if items, err := rest.list(); err == nil {
				pending = len(items) > 0
				if pending {
					execution = items[0].ExecutionDate
					if started == 0 {
						started = items[0].CreatedAt
					}
				}
			}
		}
		render(username, row, col, previous, flags, delays[delayIndex], started, stopped, observed, execution, pending, rest, errorText)
		key, open := stream.next(500 * time.Millisecond)
		if !open {
			return true
		}
		if key == 0 {
			continue
		}
		if key == 'q' || key == 'Q' || key == 3 {
			return true
		}
		if key == 'l' || key == 'L' {
			return false
		}
		if key == 'm' || key == 'M' {
			delayIndex = (delayIndex + 1) % 4
			continue
		}
		if key == '1' {
			delayIndex = 0
			continue
		}
		if key == '2' {
			delayIndex = 1
			continue
		}
		if key == '5' {
			delayIndex = 2
			continue
		}
		if key == '0' {
			delayIndex = 3
			continue
		}
		if key == 'g' || key == 'G' {
			change, at, err := rest.start(delays[delayIndex])
			if err != nil {
				errorText = err.Error()
			} else {
				started = at
				stopped = 0
				observed = 0
				execution = change.ExecutionDate
				pending = true
				errorText = ""
			}
			continue
		}
		if key == 't' || key == 'T' {
			at, err := rest.stop()
			if err != nil {
				errorText = err.Error()
			} else {
				stopped = at
				pending = false
				errorText = ""
			}
			continue
		}
		dr, dc := 0, 0
		if key == 27 {
			second, ok := stream.next(50 * time.Millisecond)
			if !ok || second != '[' {
				continue
			}
			third, ok := stream.next(50 * time.Millisecond)
			if !ok {
				continue
			}
			if third == 'A' {
				dr = -1
			} else if third == 'B' {
				dr = 1
			} else if third == 'C' {
				dc = 1
			} else if third == 'D' {
				dc = -1
			}
		}
		if key == 'w' || key == 'W' {
			dr = -1
		}
		if key == 's' || key == 'S' {
			dr = 1
		}
		if key == 'a' || key == 'A' {
			dc = -1
		}
		if key == 'd' || key == 'D' {
			dc = 1
		}
		nr, nc := row+dr, col+dc
		if nr < 0 {
			nr = 0
		}
		if nr > 2 {
			nr = 2
		}
		if nc < 0 {
			nc = 0
		}
		if nc > 2 {
			nc = 2
		}
		if nr != row || nc != col {
			old := position{row, col}
			previous = &old
			row, col = nr, nc
		}
	}
}
func main() {
	var client *ld.LDClient
	if key := strings.TrimSpace(os.Getenv("LD_SDK_KEY")); key != "" {
		if made, err := ld.MakeClient(key, 5*time.Second); err == nil {
			client = made
			defer client.Close()
		}
	}
	stream := newKeyStream()
	rest := newRESTClient()
	fd := int(os.Stdin.Fd())
	for {
		username, err := readUsername(stream)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return
		}
		old, err := term.MakeRaw(fd)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return
		}
		quit := runGrid(username, stream, client, rest)
		_ = term.Restore(fd, old)
		fmt.Print(reset)
		if quit {
			return
		}
	}
}
