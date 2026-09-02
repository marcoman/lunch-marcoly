import java.io.IOException;
import java.util.Map;
import java.util.Scanner;

/** Console grid navigator demonstrating LaunchDarkly multi-context targeting. */
public class GridNavigator {
    private static final String[] ROWS = {"t", "m", "b"};
    private static final String[] COLS = {"l", "m", "r"};
    private static final Map<String, String> USERS = Map.of("1", "alice", "2", "bob");
    private static final Map<String, String> ORGS = Map.of("1", "acme", "2", "globex");
    private static final String APP_BANNER = "14-multi-context-targeting[java-console]";
    private static final String BG = "\u001B[48;5;236m";
    private static final String RESET = "\u001B[0m";
    private static final String GREEN = "\u001B[32m";

    private record Login(String username, String org) {
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
            GridExit exit = runGrid(login.username(), login.org());
            disableRawMode();
            if (exit == GridExit.QUIT) break;
        }
    }

    /** Prompt for Alice/Bob and Acme/Globex — the two multi-context keys. */
    private static Login readLogin(Scanner scanner) {
        System.out.println(APP_BANNER);
        System.out.println("Login\n");
        String username;
        while (true) {
            System.out.print("User [1=Alice 2=Bob]: ");
            String choice = scanner.nextLine().trim();
            if (USERS.containsKey(choice)) {
                username = USERS.get(choice);
                break;
            }
            System.out.println("Choose 1 or 2.");
        }
        while (true) {
            System.out.print("Org  [1=Acme 2=Globex]: ");
            String choice = scanner.nextLine().trim();
            if (ORGS.containsKey(choice)) {
                return new Login(username, ORGS.get(choice));
            }
            System.out.println("Choose 1 or 2.");
        }
    }

    /** Re-evaluate the partner badge every 500 ms; 1–4 walk the 2×2 without logout. */
    private static GridExit runGrid(String username, String org)
            throws IOException, InterruptedException {
        int row = 1;
        int col = 1;
        Position previous = null;

        while (true) {
            FlagEvaluator.PartnerFlags flags = FlagEvaluator.evaluate(username, org);
            username = flags.username();
            org = flags.org();
            render(username, org, row, col, previous, flags);

            if (System.in.available() == 0) {
                Thread.sleep(500);
                continue;
            }

            int key = System.in.read();
            if (key == 'q' || key == 'Q' || key == 3) return GridExit.QUIT;
            if (key == 'l' || key == 'L') return GridExit.LOGOUT;
            if (key == '1') {
                username = "alice";
                continue;
            }
            if (key == '2') {
                username = "bob";
                continue;
            }
            if (key == '3') {
                org = "acme";
                continue;
            }
            if (key == '4') {
                org = "globex";
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

    private static String nameLine(String username, FlagEvaluator.PartnerFlags flags) {
        if (!flags.partner()) return "Name: " + username;
        return "Name: " + username + "  " + GREEN + "partner" + RESET + BG;
    }

    private static void render(
            String username,
            String org,
            int row,
            int col,
            Position previous,
            FlagEvaluator.PartnerFlags flags
    ) {
        System.out.print(BG + "\033[H\033[2J");
        System.out.flush();
        writeLine(APP_BANNER);
        writeLine(nameLine(username, flags));
        writeLine("Org: " + flags.orgLabel());
        writeLine("Current position: " + formatPos(row, col));
        writeLine("Previous position: "
                + (previous == null ? "—" : formatPos(previous.row(), previous.col())));
        writeLine("");
        writeLine("1/2 user Alice/Bob, 3/4 org Acme/Globex. Arrows or WASD. L logout, Q quit.");
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
