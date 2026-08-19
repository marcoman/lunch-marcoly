// yahoo.go — Yahoo Finance headlines + series ../../stories/ cache.
//
// Same fetch/cache shape as 21-agent-completion-config/go/yahoo.go, plus a
// "published" timestamp per story and formatStorySource() so the plain-text
// {{ stories }} block the tool loop sees (agent.go: storiesAsPromptText)
// reads "Publisher · Aug 4, 2026 3:25 PM" — matching the Python/.NET ports.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

const (
	defaultTicker1 = "NVDA"
	defaultTicker2 = "SPCX"
	userAgent      = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
		"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

var yahooSearchHosts = []string{
	"https://query1.finance.yahoo.com/v1/finance/search",
	"https://query2.finance.yahoo.com/v1/finance/search",
}

var tickerCleaner = regexp.MustCompile(`[^A-Z0-9.\-]`)

type story struct {
	Title     string `json:"title"`
	Publisher string `json:"publisher"`
	Published string `json:"published,omitempty"`
	Link      string `json:"link"`
	UUID      string `json:"uuid"`
}

type tickerBlock struct {
	Ticker    string  `json:"ticker"`
	Name      string  `json:"name"`
	Stories   []story `json:"stories"`
	Error     string  `json:"error,omitempty"`
	FromCache bool    `json:"from_cache"`
	CachedAt  string  `json:"cached_at,omitempty"`
}

type cacheTickerEntry struct {
	Name     string  `json:"name"`
	Stories  []story `json:"stories"`
	CachedAt string  `json:"cached_at"`
}

type storiesCache struct {
	UpdatedAt *string                     `json:"updated_at"`
	Tickers   map[string]cacheTickerEntry `json:"tickers"`
	LastPair  *struct {
		Ticker1 string `json:"ticker1"`
		Ticker2 string `json:"ticker2"`
	} `json:"last_pair"`
}

type fetchPairResult struct {
	Tickers []tickerBlock
	OK      bool
	Errors  []string
	Ticker1 string
	Ticker2 string
}

// exampleRoot is 23-agent-tools/ — this binary is expected to run from go/.
func exampleRoot() string {
	return filepath.Clean(filepath.Join(".."))
}

// seriesRoot is 20-agent-config/ (parent of the example folder).
func seriesRoot() string {
	return filepath.Clean(filepath.Join(exampleRoot(), ".."))
}

func cachePath() string {
	return filepath.Join(seriesRoot(), "stories", "stories_cache.json")
}

func storiesDir() string {
	return filepath.Join(seriesRoot(), "stories")
}

func normalizeTicker(raw string) string {
	s := strings.ToUpper(strings.TrimSpace(raw))
	return tickerCleaner.ReplaceAllString(s, "")
}

func nowISO() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05Z")
}

// unixToISO converts Yahoo's providerPublishTime (unix seconds, decoded as
// float64 from JSON) into a local ISO-8601 timestamp with offset.
func unixToISO(v any) string {
	var ts int64
	switch t := v.(type) {
	case float64:
		ts = int64(t)
	case int64:
		ts = t
	case string:
		n, err := strconv.ParseInt(t, 10, 64)
		if err != nil {
			return ""
		}
		ts = n
	default:
		return ""
	}
	if ts <= 0 {
		return ""
	}
	return time.Unix(ts, 0).Format(time.RFC3339)
}

// formatPublishedDisplay renders a human date+time for the UI, e.g. "Aug 4, 2026 3:25 PM".
func formatPublishedDisplay(published string) string {
	text := strings.TrimSpace(published)
	if text == "" {
		return ""
	}
	t, err := time.Parse(time.RFC3339, text)
	if err != nil {
		return text
	}
	return t.Format("Jan 2, 2006 3:04 PM")
}

// formatStorySource is "Publisher · Aug 4, 2026 3:25 PM" (either half optional).
func formatStorySource(s story) string {
	publisher := strings.TrimSpace(s.Publisher)
	when := formatPublishedDisplay(s.Published)
	switch {
	case publisher != "" && when != "":
		return publisher + " · " + when
	case publisher != "":
		return publisher
	default:
		return when
	}
}

func loadCache() storiesCache {
	empty := storiesCache{Tickers: map[string]cacheTickerEntry{}}
	data, err := os.ReadFile(cachePath())
	if err != nil {
		return empty
	}
	var c storiesCache
	if err := json.Unmarshal(data, &c); err != nil {
		return empty
	}
	if c.Tickers == nil {
		c.Tickers = map[string]cacheTickerEntry{}
	}
	return c
}

func saveCache(c storiesCache) error {
	ts := nowISO()
	c.UpdatedAt = &ts
	if err := os.MkdirAll(storiesDir(), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(cachePath(), append(raw, '\n'), 0o644)
}

func getCachedTicker(ticker string) *tickerBlock {
	symbol := normalizeTicker(ticker)
	if symbol == "" {
		return nil
	}
	entry, ok := loadCache().Tickers[symbol]
	if !ok || len(entry.Stories) == 0 {
		return nil
	}
	stories := entry.Stories
	if len(stories) > 2 {
		stories = stories[:2]
	}
	name := entry.Name
	if name == "" {
		name = symbol
	}
	return &tickerBlock{
		Ticker:    symbol,
		Name:      name,
		Stories:   append([]story(nil), stories...),
		FromCache: true,
		CachedAt:  entry.CachedAt,
	}
}

func getLastPairCached() (t1, t2 string, blocks []tickerBlock, ok bool) {
	c := loadCache()
	if c.LastPair == nil {
		return "", "", nil, false
	}
	t1 = normalizeTicker(c.LastPair.Ticker1)
	t2 = normalizeTicker(c.LastPair.Ticker2)
	if t1 == "" || t2 == "" {
		return "", "", nil, false
	}
	blocks = make([]tickerBlock, 0, 2)
	for _, symbol := range []string{t1, t2} {
		cached := getCachedTicker(symbol)
		if cached == nil {
			return "", "", nil, false
		}
		blocks = append(blocks, *cached)
	}
	return t1, t2, blocks, true
}

func rememberTicker(symbol, name string, stories []story) {
	if len(stories) == 0 {
		return
	}
	if len(stories) > 2 {
		stories = stories[:2]
	}
	c := loadCache()
	if name == "" {
		name = symbol
	}
	c.Tickers[symbol] = cacheTickerEntry{
		Name:     name,
		Stories:  append([]story(nil), stories...),
		CachedAt: nowISO(),
	}
	_ = saveCache(c)
}

func rememberPair(ticker1, ticker2 string, results []tickerBlock) {
	if len(results) != 2 {
		return
	}
	for _, r := range results {
		if len(r.Stories) == 0 {
			return
		}
	}
	c := loadCache()
	c.LastPair = &struct {
		Ticker1 string `json:"ticker1"`
		Ticker2 string `json:"ticker2"`
	}{Ticker1: normalizeTicker(ticker1), Ticker2: normalizeTicker(ticker2)}
	for _, block := range results {
		if len(block.Stories) == 0 || block.FromCache {
			continue
		}
		symbol := normalizeTicker(block.Ticker)
		if symbol == "" {
			continue
		}
		stories := block.Stories
		if len(stories) > 2 {
			stories = stories[:2]
		}
		name := block.Name
		if name == "" {
			name = symbol
		}
		c.Tickers[symbol] = cacheTickerEntry{
			Name:     name,
			Stories:  append([]story(nil), stories...),
			CachedAt: nowISO(),
		}
	}
	_ = saveCache(c)
}

func yahooGetJSON(rawURL string) (map[string]any, error) {
	client := &http.Client{Timeout: 20 * time.Second}
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		req, err := http.NewRequest(http.MethodGet, rawURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("User-Agent", userAgent)
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Accept-Language", "en-US,en;q=0.9")

		res, err := client.Do(req)
		if err != nil {
			lastErr = err
			time.Sleep(time.Second)
			continue
		}
		body, readErr := io.ReadAll(res.Body)
		res.Body.Close()
		if readErr != nil {
			lastErr = readErr
			continue
		}
		if res.StatusCode == 429 || res.StatusCode == 503 {
			lastErr = fmt.Errorf("HTTP %d", res.StatusCode)
			if attempt < 2 {
				time.Sleep(time.Duration(1500*(attempt+1)) * time.Millisecond)
				continue
			}
			return nil, lastErr
		}
		if res.StatusCode < 200 || res.StatusCode >= 300 {
			return nil, fmt.Errorf("HTTP %d", res.StatusCode)
		}
		var payload map[string]any
		if err := json.Unmarshal(body, &payload); err != nil {
			return nil, err
		}
		return payload, nil
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("Yahoo request failed")
	}
	return nil, lastErr
}

func asString(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	default:
		return fmt.Sprint(t)
	}
}

func parseSearchPayload(symbol string, payload map[string]any, count int) *tickerBlock {
	name := ""
	if quotes, ok := payload["quotes"].([]any); ok && len(quotes) > 0 {
		if q0, ok := quotes[0].(map[string]any); ok {
			name = strings.TrimSpace(asString(q0["shortname"]))
			if name == "" {
				name = strings.TrimSpace(asString(q0["longname"]))
			}
		}
	}
	stories := make([]story, 0, count)
	news, _ := payload["news"].([]any)
	for i, item := range news {
		if i >= count {
			break
		}
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		title := strings.TrimSpace(asString(m["title"]))
		if title == "" {
			continue
		}
		stories = append(stories, story{
			Title:     title,
			Publisher: strings.TrimSpace(asString(m["publisher"])),
			Published: unixToISO(m["providerPublishTime"]),
			Link:      strings.TrimSpace(asString(m["link"])),
			UUID:      strings.TrimSpace(asString(m["uuid"])),
		})
	}
	if len(stories) == 0 {
		return nil
	}
	if name == "" {
		name = symbol
	}
	return &tickerBlock{
		Ticker:    symbol,
		Name:      name,
		Stories:   stories,
		FromCache: false,
	}
}

func fetchStoriesForTicker(ticker string, count int) tickerBlock {
	symbol := normalizeTicker(ticker)
	if symbol == "" {
		return tickerBlock{Error: "Ticker is empty."}
	}
	if count < 1 {
		count = 1
	}

	variants := []url.Values{
		{
			"q":                {symbol},
			"quotesCount":      {"1"},
			"newsCount":        {fmt.Sprintf("%d", count)},
			"enableFuzzyQuery": {"false"},
			"newsQueryId":      {"news_cie_vespa"},
			"lang":             {"en-US"},
			"region":           {"US"},
		},
		{
			"q":           {symbol},
			"quotesCount": {"1"},
			"newsCount":   {fmt.Sprintf("%d", count)},
			"lang":        {"en-US"},
			"region":      {"US"},
		},
	}

	lastError := fmt.Sprintf("No recent stories found for %s.", symbol)
	for _, host := range yahooSearchHosts {
		for _, params := range variants {
			rawURL := host + "?" + params.Encode()
			payload, err := yahooGetJSON(rawURL)
			if err != nil {
				msg := err.Error()
				if strings.HasPrefix(msg, "HTTP ") {
					lastError = fmt.Sprintf("Yahoo Finance %s for %s.", msg, symbol)
				} else {
					lastError = fmt.Sprintf("Yahoo Finance request failed for %s: %v", symbol, err)
				}
				continue
			}
			parsed := parseSearchPayload(symbol, payload, count)
			if parsed == nil {
				lastError = fmt.Sprintf("No recent stories found for %s.", symbol)
				continue
			}
			rememberTicker(symbol, parsed.Name, parsed.Stories)
			return *parsed
		}
	}

	if cached := getCachedTicker(symbol); cached != nil {
		cached.Error = lastError + " Showing last saved headlines."
		return *cached
	}
	return tickerBlock{
		Ticker: symbol,
		Name:   symbol,
		Error:  lastError,
	}
}

func fetchStoriesForTickers(ticker1, ticker2 string, count int) fetchPairResult {
	t1 := normalizeTicker(ticker1)
	if t1 == "" {
		t1 = defaultTicker1
	}
	t2 := normalizeTicker(ticker2)
	if t2 == "" {
		t2 = defaultTicker2
	}
	first := fetchStoriesForTicker(t1, count)
	time.Sleep(500 * time.Millisecond)
	second := fetchStoriesForTicker(t2, count)
	results := []tickerBlock{first, second}
	rememberPair(t1, t2, results)
	errors := make([]string, 0, 2)
	for _, r := range results {
		if r.Error != "" {
			errors = append(errors, r.Error)
		}
	}
	return fetchPairResult{
		Tickers: results,
		OK:      len(errors) == 0,
		Errors:  errors,
		Ticker1: t1,
		Ticker2: t2,
	}
}
