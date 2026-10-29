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
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Material;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static dev.mcarchitect.core.Json.ints;
import static dev.mcarchitect.core.Json.world;

/**
 * Ghost builds: blocks sent to one player's client only (the world doesn't change), so they can walk
 * around a design before saying yes. The client forgets them when a chunk reloads, so they're sent again
 * when the player loads one of the preview's chunks or rejoins. Around the build (not the trees cleared
 * for it) a glowing frame only they see marks where it goes, and a line above their hotbar says it's a
 * preview. Cleared by a new preview, /preview/clear (the real blocks are sent back) or after half an hour.
 */
final class Preview implements Listener {
    static final int MAX_CELLS = 250_000;
    private static final long LIFETIME_MS = 30 * 60_000;

    private record Shown(String world, Map<Position, BlockData> cells, long until, int[] min, int[] max, String label,
                         int[] fmin, int[] fmax, List<Entity>[] frame) {}

    private final Plugin plugin;
    private final Map<String, Shown> shown = new HashMap<>();  // by player name (lower case)

    Preview(Plugin plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::expire, 20 * 60, 20 * 60);
        Bukkit.getScheduler().runTaskTimer(plugin, this::remind, 20, 30);
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
        int[] fmin = {Integer.MAX_VALUE, Integer.MAX_VALUE, Integer.MAX_VALUE}, fmax = {Integer.MIN_VALUE, Integer.MIN_VALUE, Integer.MIN_VALUE};
        out.forEach((pos, d) -> {  // the frame goes round the build's own blocks, not the cleared trees
            if (d.getMaterial() == Material.AIR) return;
            int[] v = {pos.blockX(), pos.blockY(), pos.blockZ()};
            for (int k = 0; k < 3; k++) {
                fmin[k] = Math.min(fmin[k], v[k]);
                fmax[k] = Math.max(fmax[k], v[k]);
            }
        });
        String label = b.has("label") ? b.get("label").getAsString() : "build";
        @SuppressWarnings("unchecked")
        List<Entity>[] frame = new List[]{List.of()};
        Shown s = new Shown(w.getName(), out, System.currentTimeMillis() + LIFETIME_MS, origin, max, label,
                fmin[0] == Integer.MAX_VALUE ? origin : fmin, fmin[0] == Integer.MAX_VALUE ? max : fmax, frame);
        shown.put(name.toLowerCase(), s);
        Player p = Bukkit.getPlayerExact(name);
        if (p != null && p.getWorld().equals(w)) {
            p.sendMultiBlockChange(out);
            frame[0] = Frame.show(plugin, w, s.fmin(), s.fmax(), p);
        }
        return Map.of("player", name, "blocks", out.size(), "shown", p != null, "min", origin, "max", max);
    }

    /** Take a player's preview away: their client gets the real blocks back. */
    boolean clear(String name) {
        Shown s = shown.remove(name.toLowerCase());
        if (s == null) return false;
        Frame.remove(s.frame()[0]);
        Player p = Bukkit.getPlayerExact(name);
        World w = Bukkit.getWorld(s.world());
        if (p != null) p.sendActionBar(Component.empty());
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
        if (s != null && e.getPlayer().getWorld().getName().equals(s.world())) {
            Frame.remove(s.frame()[0]);  // the next reminder draws it again, shown to this player
            s.frame()[0] = List.of();
            Bukkit.getScheduler().runTaskLater(plugin, () -> e.getPlayer().sendMultiBlockChange(s.cells()), 40);
        }
    }

    /** Every 1.5 s: the "this is a preview" line (it fades on its own), and the frame back if the game
     * dropped it (display entities aren't kept when their chunk unloads). */
    private void remind() {
        shown.forEach((name, s) -> {
            Player p = Bukkit.getPlayerExact(name);
            if (p == null || !p.getWorld().getName().equals(s.world())) return;
            p.sendActionBar(Component.text("Preview: " + s.label().replace('_', ' ') + " · only you see it  ", NamedTextColor.AQUA)
                    .append(Component.text("/arc yes · /arc no", NamedTextColor.GRAY)));
            if (!Frame.intact(s.frame()[0]) && near(p, s)) {
                Frame.remove(s.frame()[0]);
                s.frame()[0] = Frame.show(plugin, p.getWorld(), s.fmin(), s.fmax(), p);
            }
        });
    }

    private static boolean near(Player p, Shown s) {
        var l = p.getLocation();
        return Math.abs(l.getX() - (s.fmin()[0] + s.fmax()[0]) / 2.0) < 160 && Math.abs(l.getZ() - (s.fmin()[2] + s.fmax()[2]) / 2.0) < 160;
    }

    private void expire() {
        long now = System.currentTimeMillis();
        shown.entrySet().stream().filter(e -> e.getValue().until() < now).map(Map.Entry::getKey).toList()
                .forEach(this::clear);
    }
}
