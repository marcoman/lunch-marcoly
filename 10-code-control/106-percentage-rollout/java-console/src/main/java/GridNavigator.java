import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;

/** Console grid navigator for a static LaunchDarkly percentage rollout. */
public class GridNavigator {
    private static final String[] ROWS = {"t", "m", "b"};
    private static final String[] COLS = {"l", "m", "r"};
    private static final String APP_BANNER = "16-percentage-rollout[java-console]";
    private static final String BG = "\u001B[48;5;236m";
    private static final String RESET = "\u001B[0m";
    private static final String GREEN = "\u001B[92m";
    private static final int CONFIGURED_GREEN_PCT = 30;
    private static final int HISTORY_LIMIT = 8;

    private record Position(int row, int col) {
    }

    private record MoveResult(int row, int col, boolean moved) {
    }

    private record HistoryItem(String username, String value, String reason) {
    }

    private enum GridExit {
        QUIT,
        LOGOUT
    }

    public static void main(String[] args) throws Exception {
        FlagEvaluator.init();
        Runtime.getRuntime().addShutdownHook(new Thread(FlagEvaluator::close));
        Scanner scanner = new Scanner(System.in);
        Runtime.getRuntime().addShutdownHook(new Thread(GridNavigator::disableRawMode));
        while (true) {
            String username = readUsername(scanner);
            enableRawMode();
            GridExit exit = runGrid(username);
            disableRawMode();
            if (exit == GridExit.QUIT) {
                break;
            }
        }
    }

    private static String generatedUsername(String base, int index) {
        return index <= 0 ? base : base + index;
    }

    private static String readUsername(Scanner scanner) {
        System.out.println(APP_BANNER);
        System.out.println("Login");
        System.out.println("Username becomes the LaunchDarkly user context key.\n");
        while (true) {
            System.out.print("Username: ");
            String name = scanner.nextLine().trim();
            if (!name.isEmpty()) {
                return name;
            }
            System.out.println("Username is required.");
        }
    }

    private static GridExit runGrid(String base) throws IOException, InterruptedException {
        int index = 0;
        String username = generatedUsername(base, index);
        int row = 1;
        int col = 1;
        Position previous = null;
        Map<String, String> seen = new LinkedHashMap<>();
        List<HistoryItem> history = new ArrayList<>();
        while (true) {
            FlagEvaluator.FlagValues flags = FlagEvaluator.evaluate(username);
            remember(username, flags, seen, history);
            render(username, base, index, row, col, previous, flags, seen, history);
            if (System.in.available() == 0) {
                Thread.sleep(500);
                continue;
            }
            int key = System.in.read();
            if (key == 'q' || key == 'Q' || key == 3) {
                return GridExit.QUIT;
            }
            if (key == 'l' || key == 'L') {
                return GridExit.LOGOUT;
            }
            if (key == 'n' || key == 'N') {
                index += 1;
                username = generatedUsername(base, index);
                row = 1;
                col = 1;
                previous = null;
                continue;
            }
            if (key == 'p' || key == 'P') {
                if (index == 0) {
                    continue;
                }
                index -= 1;
                username = generatedUsername(base, index);
                row = 1;
                col = 1;
                previous = null;
                continue;
            }
            int dr = 0;
            int dc = 0;
            if (key == 27) {
                if (System.in.read() != 91) continue;
                int arrow = System.in.read();
                if (arrow == 65) dr = -1;
                else if (arrow == 66) dr = 1;
                else if (arrow == 68) dc = -1;
                else if (arrow == 67) dc = 1;
                else continue;
            } else if (key == 'w' || key == 'W') {
                dr = -1;
            } else if (key == 's' || key == 'S') {
                dr = 1;
            } else if (key == 'a' || key == 'A') {
                dc = -1;
            } else if (key == 'd' || key == 'D') {
                dc = 1;
            } else {
                continue;
            }
            MoveResult result = tryMove(row, col, dr, dc);
            if (result.moved) {
                previous = new Position(row, col);
                row = result.row;
                col = result.col;
            }
        }
    }

    private static void remember(
            String username,
            FlagEvaluator.FlagValues flags,
            Map<String, String> seen,
            List<HistoryItem> history
    ) {
        String value = flags.flagValue();
        String reason = flags.reasonKind();
        seen.put(username, value);
        history.removeIf(item -> item.username.equals(username));
        history.add(0, new HistoryItem(username, value, reason));
        while (history.size() > HISTORY_LIMIT) {
            history.remove(history.size() - 1);
        }
    }

    private static String observedLine(Map<String, String> seen) {
        int total = seen.size();
        if (total == 0) {
            return "Observed: no unique keys yet.";
        }
        int greenCount = 0;
        for (String value : seen.values()) {
            if ("green".equals(value)) {
                greenCount += 1;
            }
        }
        int noneCount = total - greenCount;
        double pct = Math.round((greenCount / (double) total) * 1000) / 10.0;
        return "Observed: " + greenCount + " green / " + noneCount + " none of " + total
                + " unique → " + pct + "% (configured " + CONFIGURED_GREEN_PCT + "%)";
    }

    private static MoveResult tryMove(int row, int col, int dr, int dc) {
        int nr = Math.max(0, Math.min(2, row + dr));
        int nc = Math.max(0, Math.min(2, col + dc));
        return new MoveResult(nr, nc, nr != row || nc != col);
    }

    private static String formatPos(int row, int col) {
        return ROWS[row] + "/" + COLS[col];
    }

    private static String colorize(String text, String color) {
        if (!"green".equals(color)) {
            return text;
        }
        return GREEN + text + RESET + BG;
    }

    private static void writeLine(String line) {
        System.out.print(line + "\r\n");
    }

    private static void render(
            String username,
            String base,
            int index,
            int row,
            int col,
            Position previous,
            FlagEvaluator.FlagValues flags,
            Map<String, String> seen,
            List<HistoryItem> history
    ) {
        System.out.print(BG + "\033[H\033[2J");
        System.out.flush();
        String prevPos = previous == null ? "—" : formatPos(previous.row, previous.col);
        String previousName = index == 0 ? "—" : generatedUsername(base, index - 1);
        writeLine(APP_BANNER);
        writeLine("Name: " + colorize(username, flags.highlightColor()) + RESET + BG);
        writeLine("Current: " + formatPos(row, col) + "   Previous: " + prevPos);
        writeLine("Flag value: " + flags.flagValue() + "   reason: " + flags.reasonKind()
                + "   idx: " + flags.variationText());
        writeLine(observedLine(seen));
        writeLine("Arrows/WASD move.  N next (" + generatedUsername(base, index + 1)
                + ")  P prev (" + previousName + ")  L logout  Q quit");
        writeLine("");
        for (int r = 0; r < 3; r++) {
            String[] top = new String[3];
            String[] mid = new String[3];
            String[] bot = new String[3];
            for (int c = 0; c < 3; c++) {
                boolean selected = r == row && c == col;
                String[] cell = drawCell(selected, selected ? flags.highlightColor() : "none");
                top[c] = cell[0];
                mid[c] = cell[1];
                bot[c] = cell[2];
            }
            writeLine(String.join(" ", top));
            writeLine(String.join(" ", mid));
            writeLine(String.join(" ", bot));
        }
        writeLine("");
        writeLine("Recent evaluations");
        if (history.isEmpty()) {
            writeLine("(none yet)");
        }
        for (HistoryItem item : history) {
            writeLine(colorize(item.username + "  " + item.value + "  " + item.reason, item.value));
        }
    }

    private static String[] drawCell(boolean selected, String highlightColor) {
        if (selected) {
            if ("green".equals(highlightColor)) {
                return new String[]{
                        GREEN + "┏━━━┓" + RESET + BG,
                        GREEN + "┃ X ┃" + RESET + BG,
                        GREEN + "┗━━━┛" + RESET + BG
                };
            }
            return new String[]{"┏━━━┓", "┃ X ┃", "┗━━━┛"};
        }
        return new String[]{"┌───┐", "│   │", "└───┘"};
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
