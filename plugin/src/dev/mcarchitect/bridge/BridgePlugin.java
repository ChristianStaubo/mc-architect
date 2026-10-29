package dev.mcarchitect.bridge;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sk89q.worldedit.EditSession;
import com.sk89q.worldedit.WorldEdit;
import com.sk89q.worldedit.bukkit.BukkitAdapter;
import com.sk89q.worldedit.math.BlockVector3;
import com.sk89q.worldedit.world.block.BlockState;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.HeightMap;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * The agent's way into the game: a small JSON-over-HTTP API (bearer token) for reading the world and
 * changing it through WorldEdit, so every change can be undone. World access always runs on the main
 * thread. Block grids are sent run-length encoded in y, z, x order (x fastest), with a palette of
 * block-data strings; a null palette entry means "leave this block alone".
 */
public final class BridgePlugin extends JavaPlugin {
    private static final int MAX_VOLUME = 4_000_000;
    private static final int MAX_HISTORY = 100;

    private final Gson gson = new Gson();
    private final Deque<Edit> history = new ArrayDeque<>();
    private int nextEditId = 1;
    private HttpServer http;
    private byte[] token;

    private record Edit(int id, String label, String world, int[] min, int[] max, int changed, long time,
                        EditSession session) {
        Map<String, Object> summary() {
            return map("id", id, "label", label, "world", world, "min", min, "max", max,
                    "changed", changed, "time", time);
        }
    }

    private interface Handler {
        Object handle(JsonObject body) throws Exception;
    }

    @Override
    public void onEnable() {
        try {
            token = loadToken().getBytes(StandardCharsets.UTF_8);
            int port = Integer.parseInt(System.getenv().getOrDefault("MC_BRIDGE_PORT", "8765"));
            http = HttpServer.create(new InetSocketAddress("0.0.0.0", port), 0);
            http.setExecutor(Executors.newFixedThreadPool(4));
            route("/status", b -> sync(this::status));
            route("/command", b -> sync(() -> command(b.get("command").getAsString())));
            route("/region", b -> sync(() -> region(b)));
            route("/heightmap", b -> sync(() -> heightmap(b)));
            route("/place", b -> sync(() -> place(b)));
            route("/undo", b -> sync(() -> undo(b)));
            route("/history", b -> sync(() -> map("edits", history.stream().map(Edit::summary).toList())));
            route("/blocks", b -> map("blocks", java.util.Arrays.stream(org.bukkit.Material.values())
                    .filter(m -> m.isBlock() && !m.isLegacy()).map(m -> m.getKey().getKey()).sorted().toList()));
            route("/validate", b -> sync(() -> validate(b)));
            route("/use", b -> sync(() -> use(b)));
            route("/kick", b -> sync(() -> map("kicked", kick(world(b), ints(b, "min", 3), ints(b, "max", 3)))));
            http.start();
            getLogger().info("bridge listening on port " + port);
        } catch (IOException e) {
            throw new RuntimeException("bridge failed to start", e);
        }
    }

    @Override
    public void onDisable() {
        if (http != null) http.stop(0);
    }

    private String loadToken() throws IOException {
        Path file = getDataFolder().toPath().resolve("token");
        if (Files.exists(file)) return Files.readString(file).trim();
        Files.createDirectories(file.getParent());
        byte[] raw = new byte[32];
        new SecureRandom().nextBytes(raw);
        String t = HexFormat.of().formatHex(raw);
        Files.writeString(file, t + "\n");
        return t;
    }

    private void route(String path, Handler handler) {
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
            } catch (IllegalArgumentException e) {
                status = 400;
                result = map("error", e.getMessage());
            } catch (Exception e) {
                Throwable cause = e.getCause() != null ? e.getCause() : e;
                status = cause instanceof IllegalArgumentException ? 400 : 500;
                result = map("error", String.valueOf(cause.getMessage()), "type", cause.getClass().getSimpleName());
            }
            send(ex, status, gson.toJson(result));
        });
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

    private <T> T sync(Callable<T> task) throws Exception {
        return Bukkit.getScheduler().callSyncMethod(this, task).get(120, TimeUnit.SECONDS);
    }

    // ---- endpoints (main thread) ----

    private Object status() {
        List<Object> players = new ArrayList<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            Location l = p.getLocation();
            players.add(map("name", p.getName(), "world", l.getWorld().getName(),
                    "pos", new double[]{l.getX(), l.getY(), l.getZ()}, "yaw", l.getYaw(),
                    "gamemode", p.getGameMode().name()));
        }
        World w = Bukkit.getWorlds().get(0);
        Location s = w.getSpawnLocation();
        return map("minecraft", Bukkit.getMinecraftVersion(), "server", Bukkit.getVersion(),
                "tps", Bukkit.getTPS()[0], "players", players,
                "worlds", Bukkit.getWorlds().stream().map(World::getName).toList(),
                "spawn", new int[]{s.getBlockX(), s.getBlockY(), s.getBlockZ()},
                "world_height", new int[]{w.getMinHeight(), w.getMaxHeight()}, "edits", history.size());
    }

    private Object command(String cmd) {
        List<String> out = new ArrayList<>();
        var sender = Bukkit.createCommandSender(c -> out.add(PlainTextComponentSerializer.plainText().serialize(c)));
        boolean ok = Bukkit.dispatchCommand(sender, cmd.startsWith("/") ? cmd.substring(1) : cmd);
        return map("ok", ok, "output", out);
    }

    private Object region(JsonObject b) {
        World w = world(b);
        int[] min = ints(b, "min", 3), max = ints(b, "max", 3);
        int[] size = box(min, max);
        Map<String, Integer> palette = new LinkedHashMap<>();
        Rle rle = new Rle();
        for (int y = min[1]; y <= max[1]; y++)
            for (int z = min[2]; z <= max[2]; z++)
                for (int x = min[0]; x <= max[0]; x++) {
                    String s = w.getBlockAt(x, y, z).getBlockData().getAsString();
                    rle.add(palette.computeIfAbsent(s, k -> palette.size()));
                }
        return map("world", w.getName(), "min", min, "max", max, "size", size,
                "palette", new ArrayList<>(palette.keySet()), "rle", rle.done());
    }

    private Object heightmap(JsonObject b) {
        World w = world(b);
        int[] min = ints(b, "min", 2), max = ints(b, "max", 2);
        if (max[0] < min[0] || max[1] < min[1]) throw new IllegalArgumentException("max must be >= min");
        long area = (long) (max[0] - min[0] + 1) * (max[1] - min[1] + 1);
        if (area > MAX_VOLUME) throw new IllegalArgumentException("area too large: " + area);
        HeightMap type = HeightMap.valueOf(b.has("type") ? b.get("type").getAsString() : "MOTION_BLOCKING_NO_LEAVES");
        Map<String, Integer> palette = new LinkedHashMap<>();
        List<Integer> heights = new ArrayList<>(), tops = new ArrayList<>();
        for (int z = min[1]; z <= max[1]; z++)
            for (int x = min[0]; x <= max[0]; x++) {
                int y = w.getHighestBlockYAt(x, z, type);
                heights.add(y);
                String top = w.getBlockAt(x, y, z).getBlockData().getAsString();
                tops.add(palette.computeIfAbsent(top, k -> palette.size()));
            }
        return map("world", w.getName(), "min", min, "max", max, "type", type.name(),
                "heights", heights, "tops", tops, "palette", new ArrayList<>(palette.keySet()));
    }

    private Object place(JsonObject b) throws Exception {
        World w = world(b);
        int[] origin = ints(b, "origin", 3), size = ints(b, "size", 3);
        long volume = (long) size[0] * size[1] * size[2];
        if (size[0] < 1 || size[1] < 1 || size[2] < 1 || volume > MAX_VOLUME)
            throw new IllegalArgumentException("bad size (max volume " + MAX_VOLUME + ")");
        if (origin[1] < w.getMinHeight() || origin[1] + size[1] > w.getMaxHeight())
            throw new IllegalArgumentException("build outside world height " + w.getMinHeight() + ".." + w.getMaxHeight());

        JsonArray pal = b.getAsJsonArray("palette");
        BlockState[] states = new BlockState[pal.size()];
        for (int i = 0; i < pal.size(); i++) {
            JsonElement e = pal.get(i);
            if (e.isJsonNull()) continue;
            try {
                states[i] = BukkitAdapter.adapt(Bukkit.createBlockData(e.getAsString()));
            } catch (IllegalArgumentException ex) {
                throw new IllegalArgumentException("unknown block: " + e.getAsString());
            }
        }
        int[] cells = Rle.decode(b.getAsJsonArray("rle"), volume, states.length);

        EditSession session = WorldEdit.getInstance().newEditSessionBuilder()
                .world(BukkitAdapter.adapt(w)).maxBlocks(-1).build();
        try (session) {
            int i = 0;
            for (int y = 0; y < size[1]; y++)
                for (int z = 0; z < size[2]; z++)
                    for (int x = 0; x < size[0]; x++, i++) {
                        BlockState s = states[cells[i]];
                        if (s != null)
                            session.setBlock(BlockVector3.at(origin[0] + x, origin[1] + y, origin[2] + z), s);
                    }
        }
        int[] max = {origin[0] + size[0] - 1, origin[1] + size[1] - 1, origin[2] + size[2] - 1};
        String label = b.has("label") ? b.get("label").getAsString() : "build";
        Edit edit = new Edit(nextEditId++, label, w.getName(), origin, max, session.getBlockChangeCount(),
                System.currentTimeMillis(), session);
        history.push(edit);
        while (history.size() > MAX_HISTORY) history.removeLast();
        return edit.summary();
    }

    /**
     * What a player's click does to a lever or button: flip / press it with block updates, so redstone
     * reacts (torches, dust, pistons, lamps). The block it's attached to gets an update too, the way
     * vanilla does it. Buttons release after `ticks` (default 20). Read the result with /region later.
     */
    private Object use(JsonObject b) {
        World w = world(b);
        int[] at = ints(b, "pos", 3);
        org.bukkit.block.Block blk = w.getBlockAt(at[0], at[1], at[2]);
        if (!(blk.getBlockData() instanceof org.bukkit.block.data.Powerable pw))
            throw new IllegalArgumentException("not a lever or button: " + blk.getBlockData().getAsString());
        boolean on = b.has("on") ? b.get("on").getAsBoolean() : !pw.isPowered();
        pw.setPowered(on);
        blk.setBlockData(pw, true);
        org.bukkit.block.Block attached = blk;
        if (pw instanceof org.bukkit.block.data.type.Switch sw) {
            org.bukkit.block.BlockFace face = switch (sw.getAttachedFace()) {
                case FLOOR -> org.bukkit.block.BlockFace.DOWN;
                case CEILING -> org.bukkit.block.BlockFace.UP;
                default -> sw.getFacing().getOppositeFace();
            };
            attached = blk.getRelative(face);
        }
        // vanilla also updates everything around the block the lever is on; Bukkit doesn't, so the
        // wires and torches next to it never notice. Re-place them so they recompute.
        Location c = attached.getLocation();
        kick(w, new int[]{c.getBlockX() - 1, c.getBlockY() - 1, c.getBlockZ() - 1},
                new int[]{c.getBlockX() + 1, c.getBlockY() + 1, c.getBlockZ() + 1});
        if (on && blk.getType().name().endsWith("_BUTTON")) {
            final org.bukkit.block.Block button = blk, base = attached;
            int ticks = b.has("ticks") ? b.get("ticks").getAsInt() : 20;
            Bukkit.getScheduler().runTaskLater(this, () -> {
                if (button.getBlockData() instanceof org.bukkit.block.data.Powerable p2) {
                    p2.setPowered(false);
                    button.setBlockData(p2, true);
                    Location bc = base.getLocation();
                    kick(w, new int[]{bc.getBlockX() - 1, bc.getBlockY() - 1, bc.getBlockZ() - 1},
                            new int[]{bc.getBlockX() + 1, bc.getBlockY() + 1, bc.getBlockZ() + 1});
                }
            }, ticks);
        }
        return map("pos", at, "block", blk.getBlockData().getAsString(), "powered", on);
    }

    private static final java.util.Set<String> REDSTONE = java.util.Set.of("redstone_wire", "redstone_torch",
            "redstone_wall_torch", "repeater", "comparator", "piston", "sticky_piston", "redstone_lamp", "observer",
            "dispenser", "dropper", "hopper", "note_block", "iron_door", "iron_trapdoor", "powered_rail", "activator_rail",
            "target", "daylight_detector");

    /**
     * Re-place every redstone component in the box (air, then its own state, with block updates), the way
     * placing it by hand would: wires recompute their power, torches react, pistons extend if powered.
     * Blocks pasted through WorldEdit skip this, so a pasted contraption sits dead until it's kicked.
     */
    private int kick(World w, int[] lo, int[] hi) {
        int n = 0;
        for (int x = lo[0]; x <= hi[0]; x++)
            for (int y = lo[1]; y <= hi[1]; y++)
                for (int z = lo[2]; z <= hi[2]; z++) {
                    org.bukkit.block.Block blk = w.getBlockAt(x, y, z);
                    if (!REDSTONE.contains(blk.getType().getKey().getKey())) continue;
                    org.bukkit.block.data.BlockData d = blk.getBlockData();
                    blk.setType(org.bukkit.Material.AIR, false);
                    blk.setBlockData(d, true);
                    n++;
                }
        return n;
    }

    /** Which block-data strings the server can't parse, and why (bad name, bad property, bad value). */
    private Object validate(JsonObject b) {
        List<Object> bad = new ArrayList<>();
        for (JsonElement e : b.getAsJsonArray("blocks")) {
            try {
                Bukkit.createBlockData(e.getAsString());
            } catch (IllegalArgumentException ex) {
                bad.add(map("block", e.getAsString(), "error", String.valueOf(ex.getMessage())));
            }
        }
        return map("invalid", bad);
    }

    private Object undo(JsonObject b) {
        Edit edit;
        if (b.has("id")) {
            int id = b.get("id").getAsInt();
            edit = history.stream().filter(e -> e.id == id).findFirst()
                    .orElseThrow(() -> new IllegalArgumentException("no edit " + id + " in history"));
            if (history.peek() != edit)
                throw new IllegalArgumentException("edit " + id + " is not the latest; undo newer edits first");
        } else {
            edit = history.peek();
            if (edit == null) throw new IllegalArgumentException("nothing to undo");
        }
        try (EditSession undo = WorldEdit.getInstance().newEditSessionBuilder()
                .world(BukkitAdapter.adapt(Bukkit.getWorld(edit.world))).maxBlocks(-1).build()) {
            edit.session.undo(undo);
        }
        history.remove(edit);
        return map("undone", edit.summary());
    }

    // ---- helpers ----

    private static World world(JsonObject b) {
        String name = b.has("world") ? b.get("world").getAsString() : Bukkit.getWorlds().get(0).getName();
        World w = Bukkit.getWorld(name);
        if (w == null) throw new IllegalArgumentException("no world " + name);
        return w;
    }

    private static int[] ints(JsonObject b, String key, int n) {
        JsonArray a = b.getAsJsonArray(key);
        if (a == null || a.size() != n) throw new IllegalArgumentException(key + " needs " + n + " integers");
        int[] out = new int[n];
        for (int i = 0; i < n; i++) out[i] = a.get(i).getAsInt();
        return out;
    }

    private static int[] box(int[] min, int[] max) {
        int[] size = {max[0] - min[0] + 1, max[1] - min[1] + 1, max[2] - min[2] + 1};
        if (size[0] < 1 || size[1] < 1 || size[2] < 1) throw new IllegalArgumentException("max must be >= min");
        if ((long) size[0] * size[1] * size[2] > MAX_VOLUME)
            throw new IllegalArgumentException("region too large (max " + MAX_VOLUME + " blocks)");
        return size;
    }

    private static Map<String, Object> map(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    /** Run-length pairs [value, count, value, count, ...]. */
    private static final class Rle {
        private final List<Integer> out = new ArrayList<>();
        private int value = -1, count = 0;

        void add(int v) {
            if (v == value) {
                count++;
                return;
            }
            flush();
            value = v;
            count = 1;
        }

        private void flush() {
            if (count > 0) {
                out.add(value);
                out.add(count);
            }
        }

        List<Integer> done() {
            flush();
            count = 0;
            return out;
        }

        static int[] decode(JsonArray rle, long volume, int paletteSize) {
            int[] cells = new int[(int) volume];
            int i = 0;
            for (int k = 0; k + 1 < rle.size(); k += 2) {
                int v = rle.get(k).getAsInt(), n = rle.get(k + 1).getAsInt();
                if (v < 0 || v >= paletteSize) throw new IllegalArgumentException("palette index out of range: " + v);
                if (n < 0 || i + n > volume) throw new IllegalArgumentException("rle longer than the box");
                java.util.Arrays.fill(cells, i, i + n, v);
                i += n;
            }
            if (i != volume) throw new IllegalArgumentException("rle covers " + i + " blocks, box has " + volume);
            return cells;
        }
    }
}
