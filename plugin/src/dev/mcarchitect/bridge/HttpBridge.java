package dev.mcarchitect.bridge;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static dev.mcarchitect.core.Json.map;

/**
 * The agent's way into the game: a small JSON-over-HTTP API behind a bearer token (plugins/MCBridge/token).
 * Features add their own routes; handlers that touch the world wrap their work in sync() so it runs on the
 * main thread. An IllegalArgumentException becomes a 400 (the caller's mistake), anything else a 500.
 */
public final class HttpBridge {
    public interface Handler {
        Object handle(JsonObject body) throws Exception;
    }

    private final Plugin plugin;
    private final Gson gson = new Gson();
    private final HttpServer http;
    private final byte[] token;

    public HttpBridge(Plugin plugin) throws IOException {
        this.plugin = plugin;
        this.token = loadToken(plugin.getDataFolder().toPath().resolve("token")).getBytes(StandardCharsets.UTF_8);
        int port = Integer.parseInt(System.getenv().getOrDefault("MC_BRIDGE_PORT", "8765"));
        http = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);
        http.setExecutor(Executors.newFixedThreadPool(6));  // a long-polling inbox holds one thread
        plugin.getLogger().info("bridge on port " + port);
    }

    public void start() {
        http.start();
    }

    public void stop() {
        http.stop(0);
    }

    public void route(String path, Handler handler) {
        http.createContext(path, ex -> {
            int status = 200;
            Object result;
            try {
                if (!authorized(ex)) {
                    status = 401;
                    result = map("error", "unauthorized");
                } else {
                    String raw = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                    JsonObject body = raw.isBlank() ? new JsonObject() : JsonParser.parseString(raw).getAsJsonObject();
                    result = handler.handle(body);
                }
            } catch (Exception e) {
                Throwable cause = e.getCause() != null ? e.getCause() : e;
                status = cause instanceof IllegalArgumentException ? 400 : 500;
                result = map("error", String.valueOf(cause.getMessage()), "type", cause.getClass().getSimpleName());
            }
            send(ex, status, gson.toJson(result));
        });
    }

    /** Run on the server's main thread and wait for the answer. */
    public <T> T sync(Callable<T> task) throws Exception {
        return Bukkit.getScheduler().callSyncMethod(plugin, task).get(120, TimeUnit.SECONDS);
    }

    private boolean authorized(HttpExchange ex) {
        String h = ex.getRequestHeaders().getFirst("Authorization");
        if (h == null || !h.startsWith("Bearer ")) return false;
        return MessageDigest.isEqual(h.substring(7).trim().getBytes(StandardCharsets.UTF_8), token);
    }

    private static void send(HttpExchange ex, int status, String json) throws IOException {
        byte[] out = json.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(status, out.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(out);
        }
    }

    private static String loadToken(Path file) throws IOException {
        if (Files.exists(file)) return Files.readString(file).trim();
        Files.createDirectories(file.getParent());
        byte[] raw = new byte[32];
        new SecureRandom().nextBytes(raw);
        String t = HexFormat.of().formatHex(raw);
        Files.writeString(file, t + "\n");
        return t;
    }
}
