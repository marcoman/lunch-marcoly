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
	"strings"
	"time"
)

const (
	defaultTicker1 = "NVDA"
	defaultTicker2 = "SPCX"
	userAgent     = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
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
	Published string `json:"published"`
	Link      string `json:"link"`
	UUID      string `json:"uuid"`
}

type tickerBlock struct {
	Ticker    string  `json:"ticker"`
	Name      string  `json:"name"`
	Stories   []story `json:"stories"`
	Source    string  `json:"source,omitempty"`
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

func exampleRoot() string {
	return filepath.Clean(filepath.Join(".."))
}

func cachePath() string {
	return filepath.Join(exampleRoot(), "stories", "stories_cache.json")
}

func storiesDir() string {
	return filepath.Join(exampleRoot(), "stories")
}

func normalizeTicker(raw string) string {
	s := strings.ToUpper(strings.TrimSpace(raw))
	return tickerCleaner.ReplaceAllString(s, "")
}

func nowISO() string {
	return time.Now().UTC().Format("2006-01-02T15:04:05Z")
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
		Source:    "cache",
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

func envKey(name string) string {
	return strings.TrimSpace(os.Getenv(name))
}

func commonStory(title, publisher, published, link, uuid string) *story {
	title = strings.TrimSpace(title)
	if title == "" {
		return nil
	}
	return &story{
		Title:     title,
		Publisher: strings.TrimSpace(publisher),
		Published: strings.TrimSpace(published),
		Link:      strings.TrimSpace(link),
		UUID:      strings.TrimSpace(uuid),
	}
}

func tickerOk(symbol, name string, stories []story, source string) tickerBlock {
	if name == "" {
		name = symbol
	}
	return tickerBlock{Ticker: symbol, Name: name, Stories: stories, Source: source}
}

func getJSON(rawURL string, extraHeaders map[string]string, sleepBefore time.Duration) (any, error) {
	if sleepBefore > 0 {
		time.Sleep(sleepBefore)
	}
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
		for k, v := range extraHeaders {
			req.Header.Set(k, v)
		}
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
		if res.StatusCode == 429 {
			return nil, fmt.Errorf("HTTP %d", res.StatusCode)
		}
		if res.StatusCode == 503 {
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
		var payload any
		if err := json.Unmarshal(body, &payload); err != nil {
			return nil, err
		}
		return payload, nil
	}
	if lastErr == nil {
		lastErr = fmt.Errorf("news request failed")
	}
	return nil, lastErr
}

func httpFail(label, symbol string, err error) string {
	msg := err.Error()
	if strings.HasPrefix(msg, "HTTP ") {
		return fmt.Sprintf("%s %s for %s.", label, msg, symbol)
	}
	return fmt.Sprintf("%s request failed for %s: %v", label, symbol, err)
}

func unixToISO(v any) string {
	switch t := v.(type) {
	case float64:
		if t <= 0 {
			return ""
		}
		return time.Unix(int64(t), 0).UTC().Format("2006-01-02T15:04:05Z")
	case json.Number:
		n, err := t.Int64()
		if err != nil || n <= 0 {
			return ""
		}
		return time.Unix(n, 0).UTC().Format("2006-01-02T15:04:05Z")
	default:
		s := strings.TrimSpace(asString(v))
		if s == "" {
			return ""
		}
		if ts, err := time.Parse(time.RFC3339, s); err == nil {
			return ts.UTC().Format("2006-01-02T15:04:05Z")
		}
		if ts, err := time.Parse("2006-01-02T15:04:05Z", s); err == nil {
			return ts.UTC().Format("2006-01-02T15:04:05Z")
		}
		return s
	}
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
		s := commonStory(asString(m["title"]), asString(m["publisher"]), unixToISO(m["providerPublishTime"]), asString(m["link"]), asString(m["uuid"]))
		if s != nil {
			stories = append(stories, *s)
		}
	}
	if len(stories) == 0 {
		return nil
	}
	block := tickerOk(symbol, name, stories, "yahoo")
	return &block
}

func fetchFinnhub(symbol string, count int) (tickerBlock, string, bool) {
	token := envKey("FINNHUB_API_KEY")
	if token == "" {
		return tickerBlock{}, "", false
	}
	end := time.Now().UTC()
	start := end.AddDate(0, 0, -7)
	q := url.Values{
		"symbol": {symbol},
		"from":   {start.Format("2006-01-02")},
		"to":     {end.Format("2006-01-02")},
		"token":  {token},
	}
	payload, err := getJSON("https://finnhub.io/api/v1/company-news?"+q.Encode(), nil, 0)
	if err != nil {
		return tickerBlock{}, httpFail("Finnhub", symbol, err), false
	}
	items, ok := payload.([]any)
	if !ok {
		return tickerBlock{}, fmt.Sprintf("Finnhub returned no stories for %s.", symbol), false
	}
	stories := make([]story, 0, count)
	for _, item := range items {
		if len(stories) >= count {
			break
		}
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		s := commonStory(asString(m["headline"]), asString(m["source"]), unixToISO(m["datetime"]), asString(m["url"]), asString(m["id"]))
		if s != nil {
			stories = append(stories, *s)
		}
	}
	if len(stories) == 0 {
		return tickerBlock{}, fmt.Sprintf("No recent stories found for %s.", symbol), false
	}
	return tickerOk(symbol, symbol, stories, "finnhub"), "", true
}

func fetchMassive(symbol string, count int) (tickerBlock, string, bool) {
	token := envKey("MASSIVE_API_KEY")
	if token == "" {
		return tickerBlock{}, "", false
	}
	q := url.Values{
		"ticker": {symbol},
		"limit":  {fmt.Sprintf("%d", count)},
		"sort":   {"published_utc"},
		"order":  {"desc"},
	}
	payload, err := getJSON("https://api.massive.com/v2/reference/news?"+q.Encode(), map[string]string{
		"Authorization": "Bearer " + token,
	}, 0)
	if err != nil {
		return tickerBlock{}, httpFail("Massive", symbol, err), false
	}
	root, ok := payload.(map[string]any)
	if !ok {
		return tickerBlock{}, fmt.Sprintf("Massive returned no stories for %s.", symbol), false
	}
	results, _ := root["results"].([]any)
	stories := make([]story, 0, count)
	for _, item := range results {
		if len(stories) >= count {
			break
		}
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		publisher := ""
		if pub, ok := m["publisher"].(map[string]any); ok {
			publisher = asString(pub["name"])
		} else {
			publisher = asString(m["publisher"])
		}
		link := asString(m["article_url"])
		if link == "" {
			link = asString(m["url"])
		}
		s := commonStory(asString(m["title"]), publisher, unixToISO(m["published_utc"]), link, asString(m["id"]))
		if s != nil {
			stories = append(stories, *s)
		}
	}
	if len(stories) == 0 {
		return tickerBlock{}, fmt.Sprintf("No recent stories found for %s.", symbol), false
	}
	return tickerOk(symbol, symbol, stories, "massive"), "", true
}

func fetchYahoo(symbol string, count int) (tickerBlock, string, bool) {
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
			payload, err := getJSON(rawURL, nil, time.Second)
			if err != nil {
				msg := err.Error()
				if strings.HasPrefix(msg, "HTTP ") {
					lastError = fmt.Sprintf("Yahoo Finance %s for %s.", msg, symbol)
					if msg == "HTTP 429" {
						return tickerBlock{}, lastError, false
					}
				} else {
					lastError = fmt.Sprintf("Yahoo Finance request failed for %s: %v", symbol, err)
				}
				continue
			}
			root, ok := payload.(map[string]any)
			if !ok {
				lastError = fmt.Sprintf("No recent stories found for %s.", symbol)
				continue
			}
			parsed := parseSearchPayload(symbol, root, count)
			if parsed == nil {
				lastError = fmt.Sprintf("No recent stories found for %s.", symbol)
				continue
			}
			return *parsed, "", true
		}
	}
	return tickerBlock{}, lastError, false
}

func fetchStoriesForTicker(ticker string, count int) tickerBlock {
	symbol := normalizeTicker(ticker)
	if symbol == "" {
		return tickerBlock{Error: "Ticker is empty."}
	}
	if count < 1 {
		count = 1
	}
	lastError := fmt.Sprintf("No recent stories found for %s.", symbol)
	if envKey("FINNHUB_API_KEY") != "" {
		if block, err, ok := fetchFinnhub(symbol, count); ok {
			rememberTicker(symbol, block.Name, block.Stories)
			return block
		} else if err != "" {
			lastError = err
		}
	}
	if envKey("MASSIVE_API_KEY") != "" {
		if block, err, ok := fetchMassive(symbol, count); ok {
			rememberTicker(symbol, block.Name, block.Stories)
			return block
		} else if err != "" {
			lastError = err
		}
	}
	if block, err, ok := fetchYahoo(symbol, count); ok {
		rememberTicker(symbol, block.Name, block.Stories)
		return block
	} else if err != "" {
		lastError = err
	}
	if cached := getCachedTicker(symbol); cached != nil {
		cached.Error = lastError + " Showing last saved headlines."
		return *cached
	}
	return tickerBlock{Ticker: symbol, Name: symbol, Error: lastError}
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
	if first.Source == "yahoo" || len(first.Stories) == 0 {
		time.Sleep(500 * time.Millisecond)
	}
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

func formatStoriesForPrompt(tickerResults []tickerBlock) string {
	var b strings.Builder
	b.WriteString("Using only the recent headlines below, write a short ")
	b.WriteString("market briefing that compares the two tickers. Cite story titles ")
	b.WriteString("where helpful. Do not invent facts beyond what the headlines imply.\n\n")
	for _, block := range tickerResults {
		ticker := block.Ticker
		if ticker == "" {
			ticker = "?"
		}
		name := block.Name
		if name == "" {
			name = ticker
		}
		b.WriteString(fmt.Sprintf("## %s (%s)\n", ticker, name))
		if len(block.Stories) == 0 {
			b.WriteString("- (no stories available)\n")
			if block.Error != "" {
				b.WriteString(fmt.Sprintf("- note: %s\n", block.Error))
			}
		} else {
			for i, s := range block.Stories {
				title := s.Title
				if title == "" {
					title = "(untitled)"
				}
				publisher := s.Publisher
				if publisher == "" {
					publisher = "unknown"
				}
				b.WriteString(fmt.Sprintf("%d. %s — %s\n", i+1, title, publisher))
			}
		}
		b.WriteString("\n")
	}
	return strings.TrimSpace(b.String())
}
