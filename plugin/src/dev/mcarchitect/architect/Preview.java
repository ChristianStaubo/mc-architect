package dev.mcarchitect.architect;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import dev.mcarchitect.bridge.Body;
import io.papermc.paper.event.packet.PlayerChunkLoadEvent;
import io.papermc.paper.math.Position;
import net.kyori.adventure.bossbar.BossBar;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Ghost builds: blocks sent to one player's client only (the world doesn't change), so they can walk
 * around a design before saying yes. The client forgets them when a chunk reloads, so each chunk's share is
 * sent again when the player loads it (cells are kept by chunk for that). Around the build (its own box,
 * sent by the agent's tools) a glowing frame only they see marks where it goes, and a bar at the top of
 * their screen says it's a preview. Cleared by a new preview, /preview/clear (the real blocks go back) or
 * after half an hour.
 */
final class Preview implements Listener {
    static final int MAX_CELLS = 250_000;
    private static final long LIFETIME_MS = 30 * 60_000;

    /** A player's preview: cells by chunk, the frame's box and rods, the bar, when it lapses. */
    private static final class Shown {
        final World world;
        final Map<Long, Map<Position, BlockData>> chunks;
        final int blocks;
        final int[] min, max, fmin, fmax;
        final BossBar bar;
        final long until = System.currentTimeMillis() + LIFETIME_MS;
        List<Entity> frame = List.of();

        Shown(Body body, Map<Long, Map<Position, BlockData>> chunks, int blocks, int[] fmin, int[] fmax, String label) {
            this.world = body.world();
            this.chunks = chunks;
            this.blocks = blocks;
            this.min = body.origin();
            this.max = body.max();
            this.fmin = fmin;
            this.fmax = fmax;
            this.bar = BossBar.bossBar(Component.text("Preview: " + label.replace('_', ' ') + " · only you see it · ", NamedTextColor.AQUA)
                    .append(Component.text("/arc yes · /arc no", NamedTextColor.GRAY)), 1f, BossBar.Color.BLUE, BossBar.Overlay.PROGRESS);
        }
    }

    private final Plugin plugin;
    private final Map<String, Shown> shown = new HashMap<>();  // by player name (lower case), main thread only

    Preview(Plugin plugin) {
        this.plugin = plugin;
        Bukkit.getScheduler().runTaskTimer(plugin, this::expire, 20 * 60, 20 * 60);
    }

    private static long chunkKey(int x, int z) {
        return ((long) (x >> 4) << 32) ^ ((z >> 4) & 0xffffffffL);
    }

    /** A preview decoded and sorted by chunk, ready for show() on the main thread. */
    record Prepared(String name, Shown shown) {}

    /** Off the main thread: decode the body and sort its cells by chunk. */
    static Prepared prepare(JsonObject b) {
        String name = dev.mcarchitect.core.Json.str(b, "player");
        String label = dev.mcarchitect.core.Json.str(b, "label", "build");
        Body body = Body.decode(b);
        Map<Long, Map<Position, BlockData>> chunks = new HashMap<>();
        int[] n = {0};
        body.forEach((x, y, z, d) -> {
            chunks.computeIfAbsent(chunkKey(x, z), k -> new HashMap<>()).put(Position.block(x, y, z), d);
            n[0]++;
        });
        if (n[0] > MAX_CELLS) throw new IllegalArgumentException("preview too large: " + n[0] + " blocks");
        JsonArray f = b.has("frame") ? b.getAsJsonArray("frame") : null;  // the build's own box, from mc preview
        int[] fmin = f == null ? body.origin() : ints(f.get(0).getAsJsonArray()), fmax = f == null ? body.max() : ints(f.get(1).getAsJsonArray());
        return new Prepared(name, new Shown(body, chunks, n[0], fmin, fmax, label));
    }

    private static int[] ints(JsonArray a) {
        return new int[]{a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt()};
    }

    Map<String, Object> show(Prepared prepared) {
        String name = prepared.name();
        Shown s = prepared.shown();
        Shown old = shown.put(name.toLowerCase(), s);
        Player p = Bukkit.getPlayerExact(name);
        if (old != null) restore(old, p, s);
        if (p != null && p.getWorld().equals(s.world)) {
            s.chunks.values().forEach(p::sendMultiBlockChange);
            s.frame = Frame.show(plugin, s.world, s.fmin, s.fmax, p);
            p.showBossBar(s.bar);
        }
        return Map.of("player", name, "blocks", s.blocks, "shown", p != null, "min", s.min, "max", s.max);
    }

    /** Take a player's preview away: their client gets the real blocks back. */
    boolean clear(String name) {
        Shown s = shown.remove(name.toLowerCase());
        if (s == null) return false;
        restore(s, Bukkit.getPlayerExact(name), null);
        return true;
    }

    /** Undo what an old preview showed: frame, bar, and the real blocks back, except where the next
     * preview covers them anyway, and only in chunks the server has loaded (others reload real later). */
    private void restore(Shown old, Player p, Shown next) {
        Frame.remove(old.frame);
        if (p == null) return;
        p.hideBossBar(old.bar);
        if (!p.getWorld().equals(old.world)) return;
        old.chunks.forEach((key, cells) -> {
            Map<Position, BlockData> covered = next == null ? Map.of() : next.chunks.getOrDefault(key, Map.of());
            Map<Position, BlockData> real = new HashMap<>();
            for (Position pos : cells.keySet()) {
                if (covered.containsKey(pos) || !old.world.isChunkLoaded(pos.blockX() >> 4, pos.blockZ() >> 4)) continue;
                real.put(pos, old.world.getBlockAt(pos.blockX(), pos.blockY(), pos.blockZ()).getBlockData());
            }
            if (!real.isEmpty()) p.sendMultiBlockChange(real);
        });
    }

    Map<String, Object> describe(String name) {
        Shown s = shown.get(name.toLowerCase());
        return s == null ? Map.of("player", name, "preview", false)
                : Map.of("player", name, "preview", true, "blocks", s.blocks, "min", s.min, "max", s.max);
    }

    @EventHandler
    public void onChunk(PlayerChunkLoadEvent e) {
        Player p = e.getPlayer();
        Shown s = shown.get(p.getName().toLowerCase());
        if (s == null || !e.getWorld().equals(s.world)) return;
        Map<Position, BlockData> part = s.chunks.get(chunkKey(e.getChunk().getX() << 4, e.getChunk().getZ() << 4));
        if (part == null) return;
        Bukkit.getScheduler().runTaskLater(plugin, () -> {  // after the chunk itself reaches the client
            p.sendMultiBlockChange(part);
            if (!Frame.intact(s.frame)) {  // display entities go when their chunk unloads
                Frame.remove(s.frame);
                s.frame = Frame.show(plugin, s.world, s.fmin, s.fmax, p);
            }
        }, 2);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Shown s = shown.get(p.getName().toLowerCase());
        if (s == null) return;
        p.showBossBar(s.bar);
        s.frame.forEach(rod -> p.showEntity(plugin, rod));  // a rejoined player is a new viewer; cells come per chunk
    }

    private void expire() {
        long now = System.currentTimeMillis();
        shown.entrySet().stream().filter(e -> e.getValue().until < now).map(Map.Entry::getKey).toList()
                .forEach(this::clear);
    }
}
