import java.io.IOException;
import java.util.Map;
import java.util.Scanner;

/** Console grid navigator demonstrating LaunchDarkly targeting rules. */
public class GridNavigator {
    private static final String[] ROWS = {"t", "m", "b"};
    private static final String[] COLS = {"l", "m", "r"};
    private static final Map<String, String> TEAMS = Map.of(
            "1", "", "2", "red", "3", "blue", "4", "yellow");
    private static final String APP_BANNER = "13-flag-targeting-rules[java-console]";
    private static final String BG = "\u001B[48;5;236m";
    private static final String RESET = "\u001B[0m";
    private static final Map<String, String> STYLE_COLORS = Map.of(
            "colored-red", "\u001B[31m",
            "colored-blue", "\u001B[34m",
            "colored-yellow", "\u001B[33m");

    private record Login(String username, String team) {
    }

    private record Position(int row, int col) {
    }

    private record MoveResult(int row, int col, boolean moved) {
    }

    private enum GridExit {
        QUIT,
        LOGOUT
    }

    public static void main(String[] args) throws Exception {
        FlagEvaluator.init();
        Runtime.getRuntime().addShutdownHook(new Thread(FlagEvaluator::close));
        Runtime.getRuntime().addShutdownHook(new Thread(GridNavigator::disableRawMode));
        Scanner scanner = new Scanner(System.in);

        while (true) {
            Login login = readLogin(scanner);
            enableRawMode();
            GridExit exit = runGrid(login.username(), login.team());
            disableRawMode();
            if (exit == GridExit.QUIT) break;
        }
    }

    /** Prompt for the user key and public team attribute used by targeting rules. */
    private static Login readLogin(Scanner scanner) {
        System.out.println(APP_BANNER);
        System.out.println("Login\n");
        String username;
        while (true) {
            System.out.print("Username: ");
            username = scanner.nextLine().trim();
            if (!username.isEmpty()) break;
            System.out.println("Username is required.");
        }

        while (true) {
            System.out.print("Team [1=None 2=Red 3=Blue 4=Yellow]: ");
            String choice = scanner.nextLine().trim();
            if (TEAMS.containsKey(choice)) {
                return new Login(username, TEAMS.get(choice));
            }
            System.out.println("Choose 1, 2, 3, or 4.");
        }
    }

    /** Re-evaluate the team style every 500 ms while navigating. */
    private static GridExit runGrid(String username, String team)
            throws IOException, InterruptedException {
        int row = 1;
        int col = 1;
        Position previous = null;

        while (true) {
            FlagEvaluator.TeamStyle style = FlagEvaluator.evaluate(username, team);
            render(username, row, col, previous, style);

            if (System.in.available() == 0) {
                Thread.sleep(500);
                continue;
            }

            int key = System.in.read();
            if (key == 'q' || key == 'Q' || key == 3) return GridExit.QUIT;
            if (key == 'l' || key == 'L') return GridExit.LOGOUT;

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
            if (result.moved()) {
                previous = new Position(row, col);
                row = result.row();
                col = result.col();
            }
        }
    }

    private static MoveResult tryMove(int row, int col, int dr, int dc) {
        int nextRow = Math.max(0, Math.min(2, row + dr));
        int nextCol = Math.max(0, Math.min(2, col + dc));
        return new MoveResult(nextRow, nextCol, nextRow != row || nextCol != col);
    }

    private static String formatPos(int row, int col) {
        return ROWS[row] + "/" + COLS[col];
    }

    private static void writeLine(String line) {
        System.out.print(line + "\r\n");
    }

    private static String coloredTeam(FlagEvaluator.TeamStyle style) {
        String color = STYLE_COLORS.get(style.style());
        return color == null
                ? style.teamLabel()
                : color + style.teamLabel() + RESET + BG;
    }

    private static void render(
            String username,
            int row,
            int col,
            Position previous,
            FlagEvaluator.TeamStyle style
    ) {
        System.out.print(BG + "\033[H\033[2J");
        System.out.flush();
        writeLine(APP_BANNER);
        writeLine("Name: " + username);
        writeLine("Team: " + coloredTeam(style));
        writeLine("Current position: " + formatPos(row, col));
        writeLine("Previous position: "
                + (previous == null ? "—" : formatPos(previous.row(), previous.col())));
        writeLine("");
        writeLine("Use arrow keys or WASD to move (L to logout, Q to quit).");
        writeLine("");

        for (int r = 0; r < 3; r++) {
            String[] top = new String[3];
            String[] middle = new String[3];
            String[] bottom = new String[3];
            for (int c = 0; c < 3; c++) {
                String[] cell = drawCell(r == row && c == col);
                top[c] = cell[0];
                middle[c] = cell[1];
                bottom[c] = cell[2];
            }
            writeLine(String.join(" ", top));
            writeLine(String.join(" ", middle));
            writeLine(String.join(" ", bottom));
        }
    }

    private static String[] drawCell(boolean selected) {
        return selected
                ? new String[]{"┏━━━┓", "┃ X ┃", "┗━━━┛"}
                : new String[]{"┌───┐", "│   │", "└───┘"};
    }

    private static void enableRawMode() throws IOException, InterruptedException {
        new ProcessBuilder("stty", "-icanon", "-echo").inheritIO().start().waitFor();
    }

    private static void disableRawMode() {
        try {
            new ProcessBuilder("stty", "icanon", "echo").inheritIO().start().waitFor();
            System.out.print(RESET);
        } catch (Exception ignored) {
        }
    }
}
