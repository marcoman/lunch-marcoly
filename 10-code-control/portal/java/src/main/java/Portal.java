/**
 * Portal — series shell for 10-code-control (Java web examples 11–14).
 *
 * One process for the user:
 *   - Serves this folder's index.html on :8102 (PORTAL_PORT)
 *   - Spawns each example's shaded jar as a child (builds with ./mvnw if missing)
 *   - Embeds those pages in iframes (see index.html)
 *
 * Twin of ../python (:8100) and ../node (:8101).
 * Standalone entrypoints under each example's java/ still work alone.
 * Ctrl+C / SIGTERM stops the portal and all children.
 */

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class Portal {

    private static final Path HERE = Path.of(System.getProperty("user.dir")).toAbsolutePath().normalize();
    private static final Path SERIES_ROOT = HERE.getParent().getParent();
    private static final int PORTAL_PORT =
            Integer.parseInt(System.getenv().getOrDefault("PORTAL_PORT", "8102"));
    private static final String APP_BANNER = "10-code-control[portal-java]";

    private record Child(String id, String label, Path cwd, String jarName, int port) {
    }

    private static final List<Child> CHILDREN = List.of(
            new Child("11", "Flag enablement",
                    SERIES_ROOT.resolve("11-flag-enablement/java"),
                    "11-flag-enablement.jar", 8112),
            new Child("12", "Flag variations",
                    SERIES_ROOT.resolve("12-flag-variations/java"),
                    "12-flag-variations.jar", 8122),
            new Child("13", "Flag targeting rules",
                    SERIES_ROOT.resolve("13-flag-targeting-rules/java"),
                    "13-flag-targeting-rules.jar", 8132),
            new Child("14", "Multi-context targeting",
                    SERIES_ROOT.resolve("14-multi-context-targeting/java"),
                    "14-multi-context-targeting.jar", 8142)
    );

    private static final Map<String, Process> PROCS = new ConcurrentHashMap<>();
    private static final AtomicBoolean SHUTTING_DOWN = new AtomicBoolean(false);

    private Portal() {
    }

    public static void main(String[] args) throws Exception {
        if (System.getenv("LD_SDK_KEY") == null || System.getenv("LD_SDK_KEY").isBlank()) {
            System.out.println(
                    "WARNING: LD_SDK_KEY is unset. Child examples will fail to init "
                            + "LaunchDarkly until you export a server-side SDK key.");
        }

        Runtime.getRuntime().addShutdownHook(new Thread(Portal::stopChildren));
        startChildren();

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", PORTAL_PORT), 0);
        server.createContext("/", Portal::handle);
        server.setExecutor(null);
        server.start();

        System.out.println(APP_BANNER);
        System.out.println("Open http://127.0.0.1:" + PORTAL_PORT + "/");
        System.out.println("Tabs embed Java examples on 8112 / 8122 / 8132 / 8142.");
        System.out.println("Ctrl+C stops the portal and all children.");
    }

    private static void handle(HttpExchange ex) throws IOException {
        if (!"GET".equalsIgnoreCase(ex.getRequestMethod())) {
            send(ex, 405, "Method not allowed", "text/plain; charset=utf-8");
            return;
        }
        String path = ex.getRequestURI().getPath();
        if ("/".equals(path) || "/index.html".equals(path)) {
            Path index = HERE.resolve("index.html");
            if (!Files.isRegularFile(index)) {
                send(ex, 404, "Not found", "text/plain; charset=utf-8");
                return;
            }
            byte[] body = Files.readAllBytes(index);
            sendBytes(ex, 200, body, "text/html; charset=utf-8");
            return;
        }
        if ("/api/status".equals(path)) {
            send(ex, 200, statusJson(), "application/json; charset=utf-8");
            return;
        }
        send(ex, 404, "Not found", "text/plain; charset=utf-8");
    }

    private static void send(HttpExchange ex, int status, String body, String contentType)
            throws IOException {
        sendBytes(ex, status, body.getBytes(StandardCharsets.UTF_8), contentType);
    }

    private static void sendBytes(HttpExchange ex, int status, byte[] body, String contentType)
            throws IOException {
        ex.getResponseHeaders().set("Content-Type", contentType);
        ex.getResponseHeaders().set("Cache-Control", "no-store");
        ex.sendResponseHeaders(status, body.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(body);
        }
    }

    private static boolean portOpen(int port) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", port), 350);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private static boolean waitForPort(int port, long timeoutMs) {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (portOpen(port)) {
                return true;
            }
            try {
                Thread.sleep(200);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    private static void pipePrefix(String childId, InputStream stream) {
        Thread t = new Thread(() -> {
            try (BufferedReader reader =
                         new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    System.out.println("[" + childId + "] " + line);
                }
            } catch (IOException ignored) {
                // child closed
            }
        }, "portal-pipe-" + childId);
        t.setDaemon(true);
        t.start();
    }

    private static Path resolveMvnw(Path cwd) {
        Path unix = cwd.resolve("mvnw");
        if (Files.isRegularFile(unix)) {
            return unix;
        }
        Path win = cwd.resolve("mvnw.cmd");
        if (Files.isRegularFile(win)) {
            return win;
        }
        return null;
    }

    private static boolean ensureJar(Child child) {
        Path jar = child.cwd().resolve("target").resolve(child.jarName());
        if (Files.isRegularFile(jar)) {
            return true;
        }
        Path mvnw = resolveMvnw(child.cwd());
        if (mvnw == null) {
            System.err.println("[" + child.id() + "] ERROR: missing jar " + jar
                    + " and no ./mvnw in " + child.cwd());
            return false;
        }
        System.out.println("[" + child.id() + "] Building jar (missing " + child.jarName() + ") …");
        try {
            ProcessBuilder pb = new ProcessBuilder(mvnw.toString(), "-q", "-DskipTests", "package");
            pb.directory(child.cwd().toFile());
            pb.redirectErrorStream(true);
            Map<String, String> env = pb.environment();
            env.putAll(System.getenv());
            Process build = pb.start();
            pipePrefix(child.id() + "-build", build.getInputStream());
            boolean finished = build.waitFor(10, TimeUnit.MINUTES);
            if (!finished) {
                build.destroyForcibly();
                System.err.println("[" + child.id() + "] ERROR: mvnw package timed out");
                return false;
            }
            if (build.exitValue() != 0 || !Files.isRegularFile(jar)) {
                System.err.println("[" + child.id() + "] ERROR: mvnw package failed (exit="
                        + build.exitValue() + ")");
                return false;
            }
            return true;
        } catch (Exception exc) {
            System.err.println("[" + child.id() + "] ERROR: build failed: " + exc.getMessage());
            return false;
        }
    }

    private static void startChildren() {
        for (Child child : CHILDREN) {
            String cid = child.id();
            int port = child.port();

            if (!Files.isDirectory(child.cwd())) {
                System.err.println("[" + cid + "] ERROR: missing cwd " + child.cwd());
                continue;
            }

            if (portOpen(port)) {
                System.out.println("[" + cid + "] WARNING: port " + port
                        + " already in use — assuming an existing server; not spawning.");
                continue;
            }

            if (!ensureJar(child)) {
                continue;
            }

            Path jar = child.cwd().resolve("target").resolve(child.jarName());
            System.out.println("[" + cid + "] Starting " + child.jarName() + " on :" + port + " …");
            try {
                ProcessBuilder pb = new ProcessBuilder("java", "-jar", jar.toString());
                pb.directory(child.cwd().toFile());
                pb.redirectErrorStream(true);
                Map<String, String> env = pb.environment();
                env.putAll(System.getenv());
                env.put("PORT", Integer.toString(port));
                Process proc = pb.start();
                PROCS.put(cid, proc);
                pipePrefix(cid, proc.getInputStream());
                if (waitForPort(port, 90_000)) {
                    System.out.println("[" + cid + "] Ready http://127.0.0.1:" + port + "/");
                } else {
                    System.err.println("[" + cid + "] ERROR: port " + port
                            + " not ready (exit=" + (proc.isAlive() ? "running" : proc.exitValue())
                            + "). Check LD_SDK_KEY and logs above.");
                }
            } catch (Exception exc) {
                System.err.println("[" + cid + "] ERROR: spawn failed: " + exc.getMessage());
            }
        }
    }

    private static void stopChildren() {
        if (!SHUTTING_DOWN.compareAndSet(false, true)) {
            return;
        }
        List<Map.Entry<String, Process>> items = new ArrayList<>(PROCS.entrySet());
        PROCS.clear();
        for (Map.Entry<String, Process> e : items) {
            Process proc = e.getValue();
            if (!proc.isAlive()) {
                continue;
            }
            System.out.println("[" + e.getKey() + "] Stopping …");
            proc.destroy();
        }
        long deadline = System.currentTimeMillis() + 5000;
        for (Map.Entry<String, Process> e : items) {
            Process proc = e.getValue();
            long remaining = Math.max(50, deadline - System.currentTimeMillis());
            try {
                if (!proc.waitFor(remaining, TimeUnit.MILLISECONDS)) {
                    System.out.println("[" + e.getKey() + "] Kill (still running)");
                    proc.destroyForcibly();
                    proc.waitFor(2, TimeUnit.SECONDS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
                proc.destroyForcibly();
            }
        }
        System.out.println(APP_BANNER + ": stopped.");
    }

    private static String statusJson() {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"appBanner\":").append(jsonString(APP_BANNER));
        sb.append(",\"portalPort\":").append(PORTAL_PORT);
        sb.append(",\"language\":\"java\"");
        sb.append(",\"children\":[");
        boolean first = true;
        for (Child child : CHILDREN) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            Process proc = PROCS.get(child.id());
            boolean spawned = proc != null;
            boolean alive = proc != null && proc.isAlive();
            boolean up = portOpen(child.port());
            sb.append('{');
            sb.append("\"id\":").append(jsonString(child.id())).append(',');
            sb.append("\"label\":").append(jsonString(child.label())).append(',');
            sb.append("\"port\":").append(child.port()).append(',');
            sb.append("\"url\":").append(jsonString("http://127.0.0.1:" + child.port() + "/")).append(',');
            sb.append("\"spawned\":").append(spawned).append(',');
            sb.append("\"alive\":").append(alive).append(',');
            sb.append("\"up\":").append(up);
            sb.append('}');
        }
        sb.append("]}");
        return sb.toString();
    }

    private static String jsonString(String s) {
        if (s == null) {
            return "null";
        }
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\' -> out.append("\\\\");
                case '"' -> out.append("\\\"");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
        return out.toString();
    }
}
