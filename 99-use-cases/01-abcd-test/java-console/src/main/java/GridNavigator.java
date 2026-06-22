import java.io.IOException;
import java.util.Scanner;

/**
 * Console grid navigator with ABCD navigation count label (LaunchDarkly string flag).
 */
public class GridNavigator {
    private static final String[] ROWS = {"t", "m", "b"};
    private static final String[] COLS = {"l", "m", "r"};
    private static final String BG = "\u001B[48;5;236m";

    private static final class Position {
        final int row;
        final int col;

        Position(int row, int col) {
            this.row = row;
            this.col = col;
        }
    }

    private static final class MoveResult {
        final int row;
        final int col;
        final boolean moved;

        MoveResult(int row, int col, boolean moved) {
            this.row = row;
            this.col = col;
            this.moved = moved;
        }
    }

    private enum GridExit {
        QUIT,
        LOGOUT
    }

    public static void main(String[] args) throws Exception {
        if (args.length >= 2 && "--evaluate-once".equals(args[0])) {
            CountLabelEvaluator.init();
            try {
                System.out.println(CountLabelEvaluator.evaluate(args[1]));
            } finally {
                CountLabelEvaluator.close();
            }
            return;
        }

        CountLabelEvaluator.init();
        Runtime.getRuntime().addShutdownHook(new Thread(CountLabelEvaluator::close));

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
        System.out.println("Login\n");
        while (true) {
            System.out.print("Username: ");
            String name = scanner.nextLine().trim();
            if (!name.isEmpty()) {
                return name;
            }
            System.out.println("Username is required.");
        }
    }

    private static GridExit runGrid(String username) throws IOException, InterruptedException {
        int row = 1;
        int col = 1;
        Position previous = null;
        int moveCount = 0;
        String countLabel = CountLabelEvaluator.evaluate(username);

        while (true) {
            render(username, row, col, previous, moveCount, countLabel);

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
                moveCount += 1;
            }
        }
    }

    private static MoveResult tryMove(int row, int col, int dr, int dc) {
        int nr = Math.max(0, Math.min(2, row + dr));
        int nc = Math.max(0, Math.min(2, col + dc));
        if (nr == row && nc == col) {
            return new MoveResult(row, col, false);
        }
        return new MoveResult(nr, nc, true);
    }

    private static String formatPos(int row, int col) {
        return ROWS[row] + "/" + COLS[col];
    }

    private static void writeLine(String line) {
        System.out.print(line + "\r\n");
    }

    private static void render(
            String username,
            int row,
            int col,
            Position previous,
            int moveCount,
            String countLabel
    ) {
        System.out.print(BG + "\033[H\033[2J");
        System.out.flush();
        String prevText = previous == null ? "—" : formatPos(previous.row, previous.col);
        writeLine("Name: " + username);
        writeLine("Current position: " + formatPos(row, col));
        writeLine("Previous position: " + prevText);
        writeLine(countLabel + ": " + moveCount);
        writeLine("");
        writeLine("Use arrow keys or WASD to move (L to logout, Q to quit).");
        writeLine("");

        for (int r = 0; r < 3; r++) {
            String[] top = new String[3];
            String[] mid = new String[3];
            String[] bot = new String[3];
            for (int c = 0; c < 3; c++) {
                String[] cell = drawCell(r == row && c == col);
                top[c] = cell[0];
                mid[c] = cell[1];
                bot[c] = cell[2];
            }
            writeLine(String.join(" ", top));
            writeLine(String.join(" ", mid));
            writeLine(String.join(" ", bot));
        }
    }

    private static String[] drawCell(boolean selected) {
        if (selected) {
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
