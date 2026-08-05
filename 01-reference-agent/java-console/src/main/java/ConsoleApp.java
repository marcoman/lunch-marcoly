import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 01-reference-agent[java-console] — terminal UI matching the Python / Node consoles.
 * Reuses AgentCore + YahooNews from the sibling java/ web sources.
 */
public class ConsoleApp {
    private static final String APP_BANNER = "01-reference-agent[java-console]";
    private static final int CHROME_ROWS = 3;
    private static final int FOOTER_ROWS = 1;
    private static final int PAD_MAX = 4000;
    private static final String[] MENU_LEFT = {
            "(t)ickers", "st(o)ries", "(s)tatus", "(g)enerate report", "(m)ode", "(q)uit"
    };
    private static final String MENU_RIGHT = "(n)ext user";
    private static final String[] LLM_MODES = {"stub", "ollama", "bedrock"};

    private static final String RESET = "\u001b[0m";
    private static final String BOLD = "\u001b[1m";
    private static final String DIM = "\u001b[2m";
    private static final String CYAN = "\u001b[36m";
    private static final String YELLOW = "\u001b[33m";
    private static final String GREEN = "\u001b[32m";
    private static final String MAGENTA = "\u001b[35m";
    private static final String BLUE = "\u001b[34m";
    private static final String RED = "\u001b[31m";
    private static final String WHITE = "\u001b[37m";

    private int personaIndex = 0;
    private String ticker1 = YahooNews.DEFAULT_TICKER_1;
    private String ticker2 = YahooNews.DEFAULT_TICKER_2;
    private List<Map<String, Object>> stories = new ArrayList<>();
    private final List<PadLine> padLines = new ArrayList<>();
    private int scroll = 0;
    private String footer = "Ready.";
    private String footerKind = "info";
    private boolean busy = false;
    private int cachedRows = -1;
    private int cachedCols = -1;

    private record PadLine(String text, String kind) {
    }

    public static void main(String[] args) throws Exception {
        if (System.console() == null && System.getenv("AGENT_ALLOW_NON_TTY") == null) {
            // Still allow CI-ish runs, but prefer a real TTY.
        }
        Runtime.getRuntime().addShutdownHook(new Thread(ConsoleApp::disableRawMode));
        ConsoleApp app = new ConsoleApp();
        String mode = app.ensureLlmMode();
        if (!("ok".equals(app.footerKind) && !app.stories.isEmpty())) {
            app.setFooter(
                    "Ready (" + mode + "/" + AgentCore.modelLabel(mode)
                            + "). Arrow keys scroll. (m)ode cycles LLM.",
                    "info");
        }
        enableRawMode();
        app.loop();
        disableRawMode();
        System.out.print(RESET + "\n");
    }

    private void loop() throws Exception {
        while (true) {
            render();
            int key = readKey();
            if (key == 3) { // Ctrl+C
                break;
            }
            if (key == 27) { // ESC sequences
                int n1 = System.in.read();
                if (n1 == '[') {
                    int n2 = System.in.read();
                    if (n2 == 'A') {
                        scrollBy(-1);
                        continue;
                    }
                    if (n2 == 'B') {
                        scrollBy(1);
                        continue;
                    }
                    if (n2 == '5') {
                        System.in.read();
                        scrollBy(-outputHeight());
                        continue;
                    }
                    if (n2 == '6') {
                        System.in.read();
                        scrollBy(outputHeight());
                        continue;
                    }
                }
                continue;
            }
            if (busy) {
                continue;
            }
            char ch = Character.toLowerCase((char) key);
            if (ch == 'q') {
                break;
            }
            switch (ch) {
                case 's' -> cmdStatus();
                case 't' -> cmdTickers();
                case 'o' -> cmdStories();
                case 'g' -> cmdGenerate();
                case 'm' -> cmdMode();
                case 'n' -> cmdNextUser();
                case 'h', '?' -> setFooter(String.join("  ", MENU_LEFT) + "   " + MENU_RIGHT, "info");
                default -> {
                    if (ch >= 32) {
                        setFooter("Unknown key. Use menu hotkeys (t o s g m q n).", "warn");
                    }
                }
            }
        }
    }

    private ConsoleApp() {
        restoreCache();
    }

    private void restoreCache() {
        Map<String, Object> cached = YahooNews.getLastPairCached();
        if (cached == null) {
            return;
        }
        ticker1 = String.valueOf(cached.getOrDefault("ticker1", ticker1));
        ticker2 = String.valueOf(cached.getOrDefault("ticker2", ticker2));
        Object blocks = cached.get("tickers");
        if (blocks instanceof List<?> list && !list.isEmpty()) {
            stories = new ArrayList<>();
            for (Object item : list) {
                if (item instanceof Map<?, ?> map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> cast = (Map<String, Object>) map;
                    stories.add(cast);
                }
            }
            footer = "Restored saved stories from disk cache.";
            footerKind = "ok";
        }
    }

    private AgentCore.Persona persona() {
        return AgentCore.PERSONAS.get(personaIndex);
    }

    private static String paint(String text, String kind) {
        String style = switch (kind) {
            case "hotkey", "busy" -> BOLD + CYAN;
            case "name", "warn" -> BOLD + YELLOW;
            case "ok", "ticker1", "story1" -> BOLD + GREEN;
            case "ticker2", "story2" -> BOLD + MAGENTA;
            case "error" -> BOLD + RED;
            case "muted" -> DIM + WHITE;
            case "prompt" -> BLUE;
            case "response" -> CYAN;
            default -> "";
        };
        return style.isEmpty() ? text : style + text + RESET;
    }

    private static String styleHotkeys(String text) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < text.length(); i++) {
            if (i + 2 < text.length() && text.charAt(i) == '('
                    && text.charAt(i + 2) == ')'
                    && Character.isLetter(text.charAt(i + 1))) {
                out.append('(').append(paint(String.valueOf(text.charAt(i + 1)), "hotkey")).append(')');
                i += 2;
            } else {
                out.append(text.charAt(i));
            }
        }
        return out.toString();
    }

    private static String clip(String text, int width) {
        if (width <= 0) {
            return "";
        }
        if (text.length() <= width) {
            return text;
        }
        return width <= 1 ? text.substring(0, width) : text.substring(0, width - 1) + "…";
    }

    private static String alignPair(String left, String right, int width) {
        int gap = 2;
        if (left.length() + gap + right.length() > width) {
            int room = Math.max(0, width - gap - left.length());
            right = clip(right, room);
            room = Math.max(0, width - gap - right.length());
            left = clip(left, room);
        }
        int pad = Math.max(gap, width - left.length() - right.length());
        return clip(left + " ".repeat(pad) + right, width);
    }

    private static Integer parsePositiveInt(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            int n = Integer.parseInt(value.trim());
            return n > 0 ? n : null;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    /**
     * Resolve terminal size. Prefer exported COLUMNS/LINES; otherwise probe the
     * real TTY via {@code stty size}. Note: shell {@code $COLUMNS} is often not
     * exported, so {@code System.getenv("COLUMNS")} is commonly null.
     *
     * @return {@code int[]{rows, cols}}
     */
    private int[] termSize() {
        if (cachedRows > 0 && cachedCols > 0) {
            return new int[]{cachedRows, cachedCols};
        }

        Integer envCols = parsePositiveInt(System.getenv("COLUMNS"));
        Integer envRows = parsePositiveInt(System.getenv("LINES"));
        Integer sttyRows = null;
        Integer sttyCols = null;

        File tty = new File("/dev/tty");
        if (tty.exists()) {
            try {
                Process p = new ProcessBuilder("stty", "size")
                        .redirectInput(ProcessBuilder.Redirect.from(tty))
                        .redirectError(ProcessBuilder.Redirect.DISCARD)
                        .start();
                String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
                p.waitFor();
                String[] parts = out.split("\\s+");
                if (parts.length >= 2) {
                    sttyRows = parsePositiveInt(parts[0]);
                    sttyCols = parsePositiveInt(parts[1]);
                }
            } catch (Exception ignored) {
                // fall through to env / defaults
            }
        }

        cachedRows = Math.max(12, envRows != null ? envRows : (sttyRows != null ? sttyRows : 32));
        cachedCols = Math.max(40, envCols != null ? envCols : (sttyCols != null ? sttyCols : 100));
        return new int[]{cachedRows, cachedCols};
    }

    private int cols() {
        return termSize()[1];
    }

    private int rows() {
        return termSize()[0];
    }

    private int outputHeight() {
        return Math.max(1, rows() - CHROME_ROWS - FOOTER_ROWS);
    }

    private void append(String text, String kind) {
        int width = Math.max(20, cols() - 1);
        String[] chunks = (text == null ? "" : text).split("\n", -1);
        for (String chunk : chunks) {
            if (chunk.isEmpty()) {
                padLines.add(new PadLine("", kind));
                continue;
            }
            String rest = chunk;
            while (rest.length() > width) {
                padLines.add(new PadLine(rest.substring(0, width), kind));
                rest = rest.substring(width);
            }
            padLines.add(new PadLine(rest, kind));
        }
        trimPad();
        scrollToBottom();
    }

    private void appendToken(String token, String kind) {
        if (token == null || token.isEmpty()) {
            return;
        }
        int width = Math.max(20, cols() - 1);
        String[] parts = token.split("\n", -1);
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) {
                padLines.add(new PadLine("", kind));
            }
            String part = parts[i];
            if (part.isEmpty()) {
                continue;
            }
            if (padLines.isEmpty()) {
                padLines.add(new PadLine("", kind));
            }
            PadLine last = padLines.get(padLines.size() - 1);
            String current = last.text();
            if (!last.kind().equals(kind) && !current.isEmpty()) {
                padLines.add(new PadLine("", kind));
                current = "";
            }
            String combined = current + part;
            if (combined.length() <= width) {
                padLines.set(padLines.size() - 1, new PadLine(combined, kind));
            } else {
                int space = width - current.length();
                if (space > 0) {
                    padLines.set(padLines.size() - 1, new PadLine(current + part.substring(0, space), kind));
                    String rest = part.substring(space);
                    while (!rest.isEmpty()) {
                        padLines.add(new PadLine(rest.substring(0, Math.min(width, rest.length())), kind));
                        rest = rest.length() > width ? rest.substring(width) : "";
                    }
                } else {
                    String rest = part;
                    while (!rest.isEmpty()) {
                        padLines.add(new PadLine(rest.substring(0, Math.min(width, rest.length())), kind));
                        rest = rest.length() > width ? rest.substring(width) : "";
                    }
                }
            }
        }
        trimPad();
        scrollToBottom();
    }

    private void trimPad() {
        if (padLines.size() > PAD_MAX) {
            padLines.subList(0, padLines.size() - PAD_MAX).clear();
        }
    }

    private void scrollToBottom() {
        scroll = Math.max(0, padLines.size() - outputHeight());
    }

    private void scrollBy(int delta) {
        int maxScroll = Math.max(0, padLines.size() - outputHeight());
        scroll = Math.max(0, Math.min(maxScroll, scroll + delta));
    }

    private void setFooter(String text, String kind) {
        footer = text;
        footerKind = kind;
    }

    private void render() {
        cachedRows = -1;
        cachedCols = -1;
        int width = Math.max(1, cols() - 1);
        String mode = AgentCore.resolveMode();
        String model = AgentCore.modelLabel(mode);
        String right0 = formatTickersLabel();
        String left1 = "AGENT_LLM_MODE=" + mode + "  model=" + model;
        String nameLabel = "Name: " + persona().name() + ".";
        String leftMenu = String.join("  ", MENU_LEFT);

        String chrome0 = alignPair(APP_BANNER, right0, width);
        String chrome1 = alignPair(left1, nameLabel, width);
        String chrome2 = alignPair(leftMenu, MENU_RIGHT, width);

        System.out.print("\u001b[H\u001b[2J");

        int c0 = Math.max(0, chrome0.lastIndexOf(right0));
        writeRaw(paint(APP_BANNER, "muted")
                + " ".repeat(Math.max(0, c0 - APP_BANNER.length()))
                + clip(right0, width - c0)
                + "\u001b[K\r\n");

        int c1 = Math.max(0, chrome1.lastIndexOf(nameLabel));
        writeRaw(clip(left1, c1)
                + " ".repeat(Math.max(0, c1 - left1.length()))
                + "Name: " + paint(persona().name(), "name") + "."
                + "\u001b[K\r\n");

        int c2 = Math.max(0, chrome2.lastIndexOf(MENU_RIGHT));
        writeRaw(styleHotkeys(clip(leftMenu, c2))
                + " ".repeat(Math.max(0, c2 - leftMenu.length()))
                + styleHotkeys(MENU_RIGHT)
                + "\u001b[K\r\n");

        int viewH = outputHeight();
        for (int i = 0; i < viewH; i++) {
            int idx = scroll + i;
            if (idx >= padLines.size()) {
                writeRaw("\u001b[K\r\n");
                continue;
            }
            PadLine line = padLines.get(idx);
            writeRaw(paint(clip(line.text(), width), line.kind()) + "\u001b[K\r\n");
        }
        writeRaw(paint(clip(footer, width), footerKind) + "\u001b[K");
        System.out.flush();
    }

    private static void writeRaw(String text) {
        System.out.print(text);
    }

    private String formatTickersLabel() {
        return "Tickers: " + ticker1 + " (" + storyCount(ticker1) + " stories) "
                + ticker2 + " (" + storyCount(ticker2) + " stories)";
    }

    private int storyCount(String ticker) {
        String symbol = YahooNews.normalizeTicker(ticker);
        for (Map<String, Object> block : stories) {
            if (YahooNews.normalizeTicker(String.valueOf(block.getOrDefault("ticker", ""))).equals(symbol)) {
                Object s = block.get("stories");
                if (s instanceof List<?> list) {
                    return list.size();
                }
            }
        }
        return 0;
    }

    private void appendStories() {
        if (stories.isEmpty()) {
            append("  (no stories loaded — press o)", "muted");
            return;
        }
        for (int index = 0; index < stories.size(); index++) {
            Map<String, Object> block = stories.get(index);
            int slot = index == 0 ? 1 : 2;
            String ticker = String.valueOf(block.getOrDefault("ticker", "?"));
            String name = String.valueOf(block.getOrDefault("name", ticker));
            String cache = Boolean.TRUE.equals(block.get("from_cache")) ? " [cached]" : "";
            append("  " + ticker + " (" + name + ")" + cache, "ticker" + slot);
            Object storiesObj = block.get("stories");
            if (!(storiesObj instanceof List<?> items) || items.isEmpty()) {
                append("    · " + String.valueOf(block.getOrDefault("error", "no stories")), "muted");
                continue;
            }
            for (Object item : items) {
                if (!(item instanceof Map<?, ?> story)) {
                    continue;
                }
                Object titleObj = story.get("title");
                Object publisherObj = story.get("publisher");
                String title = titleObj == null ? "(untitled)" : String.valueOf(titleObj);
                String publisher = publisherObj == null ? "" : String.valueOf(publisherObj);
                String line = "    · " + title;
                if (!publisher.isBlank() && !"null".equals(publisher)) {
                    line += " — " + publisher;
                }
                append(line, "story" + slot);
            }
            if (block.get("error") != null) {
                append("    note: " + block.get("error"), "warn");
            }
        }
    }

    private void cmdStatus() {
        String mode = AgentCore.resolveMode();
        append("— status —", "muted");
        append("User:     " + persona().name() + " (" + persona().profile() + ")", "name");
        append("Tickers:  " + ticker1, "ticker1");
        append("          " + ticker2, "ticker2");
        append("Provider: " + mode + " / " + AgentCore.modelLabel(mode), "muted");
        append("Stories:", "muted");
        appendStories();
        setFooter("Status shown.", "ok");
    }

    private void cmdTickers() throws Exception {
        disableRawMode();
        String t1 = promptLine("Ticker 1: ");
        String t2 = promptLine("Ticker 2: ");
        enableRawMode();
        if (t1 != null && !t1.isBlank()) {
            ticker1 = YahooNews.normalizeTicker(t1);
            if (ticker1.isEmpty()) {
                ticker1 = YahooNews.DEFAULT_TICKER_1;
            }
        }
        if (t2 != null && !t2.isBlank()) {
            ticker2 = YahooNews.normalizeTicker(t2);
            if (ticker2.isEmpty()) {
                ticker2 = YahooNews.DEFAULT_TICKER_2;
            }
        }
        append("Tickers set to " + ticker1 + "  " + ticker2, "ok");
        setFooter("Tickers: " + ticker1 + "  " + ticker2, "ok");
    }

    private String promptLine(String label) throws IOException {
        System.out.print(RESET + "\n" + label);
        System.out.flush();
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line = reader.readLine();
        return line == null ? "" : line.trim();
    }

    private void cmdStories() throws Exception {
        busy = true;
        setFooter("Fetching Yahoo stories for " + ticker1 + " and " + ticker2 + "…", "busy");
        render();
        try {
            Map<String, Object> result = YahooNews.fetchStoriesForTickers(ticker1, ticker2, 2);
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> blocks = (List<Map<String, Object>>) result.get("tickers");
            stories = blocks == null ? List.of() : blocks;
            append("— stories (" + ticker1 + " / " + ticker2 + ") —", "muted");
            appendStories();
            Object errorsObj = result.get("errors");
            if (errorsObj instanceof List<?> errors && !errors.isEmpty()) {
                setFooter(String.join(" · ", errors.stream().map(String::valueOf).toList()), "warn");
            } else {
                setFooter("Stories loaded. Press g to generate.", "ok");
            }
        } catch (Exception exc) {
            append("Error fetching stories: " + exc.getMessage(), "error");
            setFooter(String.valueOf(exc.getMessage()), "error");
        } finally {
            busy = false;
        }
    }

    private void cmdNextUser() {
        personaIndex = (personaIndex + 1) % AgentCore.PERSONAS.size();
        append("User: " + persona().name() + " (" + persona().profile() + ")", "name");
        setFooter("User: " + persona().name(), "ok");
    }

    private void cmdMode() {
        String current = AgentCore.resolveMode();
        int idx = 0;
        for (int i = 0; i < LLM_MODES.length; i++) {
            if (LLM_MODES[i].equals(current)) {
                idx = i;
                break;
            }
        }
        String nxt = LLM_MODES[(idx + 1) % LLM_MODES.length];
        if ("ollama".equals(nxt) && !probeOllama()) {
            append("Ollama not reachable at " + ollamaHost()
                    + ". Start Ollama and pull a model.", "warn");
            setFooter("Ollama not reachable — mode left unchanged.", "warn");
            return;
        }
        AgentCore.setModeOverride(nxt);
        String mode = AgentCore.resolveMode();
        String model = AgentCore.modelLabel(mode);
        append("Mode set to AGENT_LLM_MODE=" + mode + "  model=" + model, "ok");
        if ("ollama".equals(mode)) {
            append("Using Ollama at " + ollamaHost() + " with model " + model + ".", "muted");
        }
        setFooter("AGENT_LLM_MODE=" + mode + "  model=" + model, "ok");
    }

    private void cmdGenerate() {
        boolean usable = stories.stream().anyMatch(b -> {
            Object s = b.get("stories");
            return s instanceof List<?> list && !list.isEmpty();
        });
        if (!usable) {
            setFooter("Load stories first (press o), then g.", "warn");
            return;
        }
        busy = true;
        setFooter("Generating AI report for " + persona().name() + "…", "busy");
        append("— generate (" + persona().name() + ") —", "muted");
        render();
        boolean[] sawToken = {false};
        try {
            AgentCore.generateStream(persona(), stories, event -> {
                String type = String.valueOf(event.get("type"));
                switch (type) {
                    case "meta" -> {
                        append("Provider: " + event.get("provider") + " / " + event.get("model"), "muted");
                        append("Prompt:", "muted");
                        append(String.valueOf(event.getOrDefault("input", "")), "prompt");
                        append("Response:", "muted");
                    }
                    case "token" -> {
                        appendToken(String.valueOf(event.getOrDefault("text", "")), "response");
                        sawToken[0] = true;
                        setFooter("Streaming… " + persona().name(), "busy");
                    }
                    case "error" -> {
                        if (sawToken[0]) {
                            append("", "normal");
                        }
                        append("Error: " + event.getOrDefault("message", "Generation error"), "error");
                        setFooter(String.valueOf(event.getOrDefault("message", "Generation error")), "error");
                    }
                    case "metrics" -> {
                        if (sawToken[0]) {
                            append("", "normal");
                        }
                        @SuppressWarnings("unchecked")
                        Map<String, Object> m = (Map<String, Object>) event.getOrDefault("metrics", Map.of());
                        append("Metrics: latency_ms=" + m.get("latency_ms")
                                + "  ttft_ms=" + m.get("ttft_ms")
                                + "  prompt_tokens=" + m.get("prompt_tokens")
                                + "  completion_tokens=" + m.get("completion_tokens")
                                + "  total_tokens=" + m.get("total_tokens")
                                + "  finish_reason=" + m.get("finish_reason"), "muted");
                    }
                    case "done" -> setFooter("Done — report complete for " + persona().name() + ".", "ok");
                    default -> {
                    }
                }
                render();
            });
        } catch (Exception exc) {
            append("Error: " + exc.getMessage(), "error");
            setFooter(String.valueOf(exc.getMessage()), "error");
        } finally {
            busy = false;
        }
    }

    private String ensureLlmMode() {
        String explicit = System.getenv("AGENT_LLM_MODE");
        if (explicit != null && !explicit.isBlank()) {
            return AgentCore.resolveMode();
        }
        if (probeOllama()) {
            AgentCore.setModeOverride("ollama");
        } else {
            AgentCore.setModeOverride("stub");
        }
        return AgentCore.resolveMode();
    }

    private static String ollamaHost() {
        String host = System.getenv("OLLAMA_HOST");
        if (host == null || host.isBlank()) {
            host = "http://127.0.0.1:11434";
        }
        return host.replaceAll("/$", "");
    }

    private static boolean probeOllama() {
        try {
            HttpRequest req = HttpRequest.newBuilder(URI.create(ollamaHost() + "/api/tags"))
                    .timeout(Duration.ofMillis(600))
                    .GET()
                    .build();
            HttpResponse<Void> res = HttpClient.newHttpClient()
                    .send(req, HttpResponse.BodyHandlers.discarding());
            return res.statusCode() >= 200 && res.statusCode() < 300;
        } catch (Exception exc) {
            return false;
        }
    }

    private static int readKey() throws IOException {
        return System.in.read();
    }

    private static void enableRawMode() throws IOException, InterruptedException {
        new ProcessBuilder("stty", "-icanon", "-echo").inheritIO().start().waitFor();
    }

    private static void disableRawMode() {
        try {
            new ProcessBuilder("stty", "icanon", "echo").inheritIO().start().waitFor();
        } catch (Exception ignored) {
        }
    }
}
