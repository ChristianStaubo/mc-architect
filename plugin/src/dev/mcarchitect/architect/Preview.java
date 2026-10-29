package dev.mcarchitect.architect;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import dev.mcarchitect.bridge.WorldRoutes;
import io.papermc.paper.event.packet.PlayerChunkLoadEvent;
import io.papermc.paper.math.Position;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;

import java.util.HashMap;
import java.util.Map;

import static dev.mcarchitect.core.Json.ints;
import static dev.mcarchitect.core.Json.world;

/**
 * Ghost builds: blocks sent to one player's client only (the world doesn't change), so they can walk
 * around a design before saying yes. The client forgets them when a chunk reloads, so they're sent again
 * when the player loads one of the preview's chunks or rejoins. Cleared by a new preview, /preview/clear
 * (the real blocks are sent back) or after half an hour.
 */
final class Preview implements Listener {
    static final int MAX_CELLS = 250_000;
    private static final long LIFETIME_MS = 30 * 60_000;

    private record Shown(String world, Map<Position, BlockData> cells, long until, int[] min, int[] max) {}

    private final Plugin plugin;
    private final Map<String, Shown> shown = new HashMap<>();  // by player name (lower case)

    Preview(Plugin plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::expire, 20 * 60, 20 * 60);
    }

    /** body: player + the /place payload (origin, size, palette, rle); null palette entries are skipped. */
    Map<String, Object> show(JsonObject b) {
        String name = b.get("player").getAsString();
        World w = world(b);
        int[] origin = ints(b, "origin", 3), size = ints(b, "size", 3);
        long volume = (long) size[0] * size[1] * size[2];
        if (volume > 8L * MAX_CELLS) throw new IllegalArgumentException("preview box too large: " + volume);
        JsonArray pal = b.getAsJsonArray("palette");
        BlockData[] data = new BlockData[pal.size()];
        for (int i = 0; i < pal.size(); i++) {
            JsonElement e = pal.get(i);
            if (e.isJsonNull()) continue;
            try {
                data[i] = Bukkit.createBlockData(e.getAsString());
            } catch (IllegalArgumentException ex) {
                throw new IllegalArgumentException("unknown block: " + e.getAsString());
            }
        }
        int[] cells = WorldRoutes.Rle.decode(b.getAsJsonArray("rle"), volume, data.length);
        Map<Position, BlockData> out = new HashMap<>();
        int i = 0;
        for (int y = 0; y < size[1]; y++)
            for (int z = 0; z < size[2]; z++)
                for (int x = 0; x < size[0]; x++, i++)
                    if (data[cells[i]] != null) out.put(Position.block(origin[0] + x, origin[1] + y, origin[2] + z), data[cells[i]]);
        if (out.size() > MAX_CELLS) throw new IllegalArgumentException("preview too large: " + out.size() + " blocks");
        clear(name);
        int[] max = {origin[0] + size[0] - 1, origin[1] + size[1] - 1, origin[2] + size[2] - 1};
        shown.put(name.toLowerCase(), new Shown(w.getName(), out, System.currentTimeMillis() + LIFETIME_MS, origin, max));
        Player p = Bukkit.getPlayerExact(name);
        if (p != null && p.getWorld().equals(w)) p.sendMultiBlockChange(out);
        return Map.of("player", name, "blocks", out.size(), "shown", p != null, "min", origin, "max", max);
    }

    /** Take a player's preview away: their client gets the real blocks back. */
    boolean clear(String name) {
        Shown s = shown.remove(name.toLowerCase());
        if (s == null) return false;
        Player p = Bukkit.getPlayerExact(name);
        World w = Bukkit.getWorld(s.world());
        if (p != null && w != null && p.getWorld().equals(w)) {
            Map<Position, BlockData> real = new HashMap<>();
            for (Position pos : s.cells().keySet())
                real.put(pos, w.getBlockAt(pos.blockX(), pos.blockY(), pos.blockZ()).getBlockData());
            p.sendMultiBlockChange(real);
        }
        return true;
    }

    Map<String, Object> describe(String name) {
        Shown s = shown.get(name.toLowerCase());
        return s == null ? Map.of("player", name, "preview", false)
                : Map.of("player", name, "preview", true, "blocks", s.cells().size(), "min", s.min(), "max", s.max());
    }

    @EventHandler
    public void onChunk(PlayerChunkLoadEvent e) {
        Shown s = shown.get(e.getPlayer().getName().toLowerCase());
        if (s == null || !e.getWorld().getName().equals(s.world())) return;
        int cx = e.getChunk().getX(), cz = e.getChunk().getZ();
        Map<Position, BlockData> part = new HashMap<>();
        s.cells().forEach((pos, d) -> {
            if (pos.blockX() >> 4 == cx && pos.blockZ() >> 4 == cz) part.put(pos, d);
        });
        if (!part.isEmpty()) {
            Player p = e.getPlayer();  // after the chunk itself reaches the client
            Bukkit.getScheduler().runTaskLater(plugin, () -> p.sendMultiBlockChange(part), 2);
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Shown s = shown.get(e.getPlayer().getName().toLowerCase());
        if (s != null && e.getPlayer().getWorld().getName().equals(s.world()))
            Bukkit.getScheduler().runTaskLater(plugin, () -> e.getPlayer().sendMultiBlockChange(s.cells()), 40);
    }

    private void expire() {
        long now = System.currentTimeMillis();
        shown.entrySet().stream().filter(e -> e.getValue().until() < now).map(Map.Entry::getKey).toList()
                .forEach(this::clear);
    }
}
