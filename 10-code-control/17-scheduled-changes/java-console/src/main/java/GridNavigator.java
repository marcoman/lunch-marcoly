import java.io.IOException;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.Scanner;

/** Console grid navigator for LaunchDarkly scheduled flag changes. */
public class GridNavigator {
    private static final String[] ROWS = {"t", "m", "b"};
    private static final String[] COLS = {"l", "m", "r"};
    private static final int[] DELAYS = {1, 2, 5, 10};
    private static final String APP_BANNER = "17-scheduled-changes[java-console]";
    private static final String BG = "\u001B[48;5;236m";
    private static final String RESET = "\u001B[0m";
    private static final String GREEN = "\u001B[92m";
    private static final String DIM = "\u001B[2m";
    private static final String BOLD = "\u001B[1m";
    private static final DateTimeFormatter WALL = DateTimeFormatter.ofPattern("HH:mm:ss");

    private record Position(int row, int col) {
    }

    private record MoveResult(int row, int col, boolean moved) {
    }

    private record StatusPair(String status, String when) {
    }

    private enum GridExit {
        QUIT,
        LOGOUT
    }

    public static void main(String[] args) throws Exception {
        ScheduledChange.init();
        Runtime.getRuntime().addShutdownHook(new Thread(ScheduledChange::close));
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

    /**
     * Navigate and drive the scheduled-change lab from the keyboard.
     * LaunchDarkly scheduled flag changes: https://launchdarkly.com/docs/home/flags/scheduled-changes
     */
    private static GridExit runGrid(String username) throws IOException, InterruptedException {
        int row = 1;
        int col = 1;
        Position previous = null;
        int delayIndex = 0;
        Long startedAt = null;
        Long stoppedAt = null;
        Long observedAt = null;
        Long executionDate = null;
        Map<String, Object> pending = null;
        String error = "";
        while (true) {
            Map<String, Object> flags = ScheduledChange.evaluate(username);
            if (startedAt != null
                    && stoppedAt == null
                    && observedAt == null
                    && "green".equals(String.valueOf(flags.get("highlightColor")))) {
                observedAt = nowMs();
            }
            Map<String, Object> rest = ScheduleControls.apiConfig();
            try {
                Map<String, Object> listed = ScheduleControls.listScheduledChanges();
                pending = firstItem(listed.get("items"));
                if (pending != null) {
                    Long listedDate = asLong(pending.get("executionDate"));
                    if (listedDate != null) {
                        executionDate = listedDate;
                    }
                    if (startedAt == null) {
                        startedAt = asLong(pending.get("createdAt"));
                    }
                }
            } catch (RuntimeException ignored) {
                pending = null;
            }
            render(
                    username,
                    row,
                    col,
                    previous,
                    flags,
                    DELAYS[delayIndex],
                    startedAt,
                    stoppedAt,
                    observedAt,
                    executionDate,
                    pending,
                    Boolean.TRUE.equals(rest.get("configured")),
                    error);
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
            if (key == 'm' || key == 'M') {
                delayIndex = (delayIndex + 1) % DELAYS.length;
                continue;
            }
            if (key == '1') {
                delayIndex = 0;
                continue;
            }
            if (key == '2') {
                delayIndex = 1;
                continue;
            }
            if (key == '5') {
                delayIndex = 2;
                continue;
            }
            if (key == '0') {
                delayIndex = 3;
                continue;
            }
            if (key == 'g' || key == 'G') {
                try {
                    Map<String, Object> result = ScheduleControls.start(DELAYS[delayIndex]);
                    startedAt = asLong(result.get("startedAt"));
                    @SuppressWarnings("unchecked")
                    Map<String, Object> scheduled = (Map<String, Object>) result.get("scheduledChange");
                    executionDate = scheduled == null ? null : asLong(scheduled.get("executionDate"));
                    stoppedAt = null;
                    observedAt = null;
                    pending = scheduled;
                    error = "";
                } catch (RuntimeException exception) {
                    error = exception.getMessage() == null ? exception.toString() : exception.getMessage();
                }
                continue;
            }
            if (key == 't' || key == 'T') {
                try {
                    Map<String, Object> result = ScheduleControls.stop();
                    stoppedAt = asLong(result.get("stoppedAt"));
                    pending = null;
                    error = "";
                } catch (RuntimeException exception) {
                    error = exception.getMessage() == null ? exception.toString() : exception.getMessage();
                }
                continue;
            }
            int dr = 0;
            int dc = 0;
            if (key == 27) {
                if (System.in.read() != 91) {
                    continue;
                }
                int arrow = System.in.read();
                if (arrow == 65) {
                    dr = -1;
                } else if (arrow == 66) {
                    dr = 1;
                } else if (arrow == 68) {
                    dc = -1;
                } else if (arrow == 67) {
                    dc = 1;
                } else {
                    continue;
                }
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

    @SuppressWarnings("unchecked")
    private static Map<String, Object> firstItem(Object items) {
        if (!(items instanceof List<?> list) || list.isEmpty()) {
            return null;
        }
        Object first = list.get(0);
        return first instanceof Map<?, ?> ? (Map<String, Object>) first : null;
    }

    private static Long asLong(Object value) {
        return value instanceof Number number ? number.longValue() : null;
    }

    private static long nowMs() {
        return System.currentTimeMillis();
    }

    private static String clockMs(long ms) {
        long seconds = Math.max(0, ms) / 1000;
        return (seconds / 60) + ":" + String.format("%02d", seconds % 60);
    }

    private static String wall(Long ms) {
        if (ms == null || ms == 0) {
            return "—";
        }
        return LocalDateTime.ofInstant(Instant.ofEpochMilli(ms), ZoneId.systemDefault()).format(WALL);
    }

    private static StatusPair statusLine(
            Map<String, Object> pending,
            Long startedAt,
            Long stoppedAt,
            Long observedAt,
            Long executionDate,
            boolean green
    ) {
        if (pending != null) {
            return new StatusPair(
                    "PENDING · LaunchDarkly will turn the flag on",
                    "Scheduled wall time: " + wall(executionDate));
        }
        if (stoppedAt != null) {
            String elapsed = startedAt != null ? " after " + clockMs(stoppedAt - startedAt) + " elapsed" : "";
            return new StatusPair(
                    "STOPPED · pending change cancelled, flag off",
                    "Stopped at " + wall(stoppedAt) + elapsed + ".");
        }
        if (green && startedAt != null) {
            String observed = observedAt != null
                    ? "; green first observed here at " + clockMs(observedAt - startedAt)
                    : "";
            return new StatusPair(
                    "APPLIED · SDK now serves green",
                    "Scheduled for " + wall(executionDate) + observed + ".");
        }
        return new StatusPair(
                "No pending change.",
                "G starts a schedule. T stops it and turns the flag off.");
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
            int row,
            int col,
            Position previous,
            Map<String, Object> flags,
            int delay,
            Long startedAt,
            Long stoppedAt,
            Long observedAt,
            Long executionDate,
            Map<String, Object> pending,
            boolean restOk,
            String error
    ) {
        System.out.print(BG + "\033[H\033[2J");
        System.out.flush();
        String color = String.valueOf(flags.getOrDefault("highlightColor", "none"));
        Object reasonObj = flags.get("reason");
        String reasonKind = "UNKNOWN";
        if (reasonObj instanceof Map<?, ?> reason) {
            Object kind = reason.get("kind");
            if (kind != null) {
                reasonKind = String.valueOf(kind);
            }
        }
        Object variation = flags.get("variationIndex");
        String variationText = variation == null ? "default" : String.valueOf(variation);
        long end = stoppedAt != null ? stoppedAt : nowMs();
        String elapsed = startedAt != null ? clockMs(end - startedAt) : "0:00";
        StatusPair status = statusLine(
                pending, startedAt, stoppedAt, observedAt, executionDate, "green".equals(color));
        String rest = restOk
                ? "REST configured"
                : "REST disabled — set LD_API_ACCESS_TOKEN, LD_PROJECT_KEY, LD_ENVIRONMENT_KEY";
        String prevPos = previous == null ? "—" : formatPos(previous.row, previous.col);

        writeLine(APP_BANNER);
        writeLine("Name: " + colorize(username, color) + RESET + BG);
        writeLine("Current: " + formatPos(row, col) + "   Previous: " + prevPos);
        writeLine("Flag value: " + flags.get("flagValue") + "   reason: " + reasonKind
                + "   idx: " + variationText);
        writeLine("Delay: " + delay + " min   Elapsed: " + elapsed);
        writeLine(status.status);
        writeLine(status.when);
        writeLine(rest);
        writeLine("G start  T stop  M delay  1/2/5/0=10 min  arrows/WASD  L logout  Q quit");
        writeLine(DIM + "Lag is normal: LD executes near the date, the SDK stream follows, this loop polls ~500ms."
                + RESET + BG);
        if (error != null && !error.isEmpty()) {
            writeLine(BOLD + error + RESET + BG);
        }
        writeLine("");
        for (int r = 0; r < 3; r++) {
            String[] top = new String[3];
            String[] mid = new String[3];
            String[] bot = new String[3];
            for (int c = 0; c < 3; c++) {
                boolean selected = r == row && c == col;
                String[] cell = drawCell(selected, selected ? color : "none");
                top[c] = cell[0];
                mid[c] = cell[1];
                bot[c] = cell[2];
            }
            writeLine(String.join(" ", top));
            writeLine(String.join(" ", mid));
            writeLine(String.join(" ", bot));
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
