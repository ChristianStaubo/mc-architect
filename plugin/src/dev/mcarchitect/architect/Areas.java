package dev.mcarchitect.architect;

import dev.mcarchitect.core.Chat;
import io.papermc.paper.event.packet.PlayerChunkLoadEvent;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static dev.mcarchitect.core.Json.map;

/**
 * Areas players mark for the architect, without WorldEdit: /arc mark while looking at one corner, then at
 * the opposite corner. The area glows gold (only for them) and is their "selection" for the next requests,
 * until /arc clear, a new mark, or a build placed with /arc yes.
 */
final class Areas implements Listener {
    private static final int HEADROOM = 8;  // the frame shows a little above the higher corner

    private static final class Area {
        final World world;
        final int[] min, max;
        List<Entity> frame = List.of();

        Area(World world, int[] min, int[] max) {
            this.world = world;
            this.min = min;
            this.max = max;
        }
    }

    private final Plugin plugin;
    private final Map<String, Block> corner = new HashMap<>();   // the first corner, waiting for the second
    private final Map<String, Area> areas = new HashMap<>();     // by player name (lower case)

    Areas(Plugin plugin) {
        this.plugin = plugin;
    }

    void mark(Player p) {
        Block b = Context.target(p);
        if (b == null) {
            Chat.warn(p, "Look at the ground where a corner should be (within 200 blocks), then /arc mark.");
            return;
        }
        String key = p.getName().toLowerCase();
        Block first = corner.remove(key);
        if (first == null || !first.getWorld().equals(b.getWorld())) {
            clear(p.getName());
            corner.put(key, b);
            Chat.say(p, "First corner at " + b.getX() + " " + b.getY() + " " + b.getZ()
                    + ". Now look at the opposite corner and /arc mark again.");
            return;
        }
        int[] min = {Math.min(first.getX(), b.getX()), Math.min(first.getY(), b.getY()), Math.min(first.getZ(), b.getZ())};
        int[] max = {Math.max(first.getX(), b.getX()), Math.max(first.getY(), b.getY()) + HEADROOM, Math.max(first.getZ(), b.getZ())};
        Area a = new Area(b.getWorld(), min, max);
        a.frame = Frame.show(plugin, a.world, min, max, p, Frame.AREA);
        areas.put(key, a);
        Chat.say(p, "Area marked: " + (max[0] - min[0] + 1) + " by " + (max[2] - min[2] + 1)
                + " blocks. Now tell the architect what to build there: /arc <idea>. /arc clear drops it.");
    }

    boolean clear(String name) {
        corner.remove(name.toLowerCase());
        Area a = areas.remove(name.toLowerCase());
        if (a != null) Frame.remove(a.frame);
        return a != null;
    }

    /** The player's marked area, shaped like a WorldEdit selection, or null. */
    Map<String, Object> selection(Player p) {
        Area a = areas.get(p.getName().toLowerCase());
        return a == null || !a.world.equals(p.getWorld()) ? null : map("min", a.min, "max", a.max, "marked", true);
    }

    @EventHandler
    public void onChunk(PlayerChunkLoadEvent e) {  // display entities go when their chunk unloads: draw it again
        Area a = areas.get(e.getPlayer().getName().toLowerCase());
        if (a == null || !e.getWorld().equals(a.world) || Frame.intact(a.frame)) return;
        int cx = e.getChunk().getX(), cz = e.getChunk().getZ();
        if (cx < a.min[0] >> 4 || cx > a.max[0] >> 4 || cz < a.min[2] >> 4 || cz > a.max[2] >> 4) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (Frame.intact(a.frame)) return;
            Frame.remove(a.frame);
            a.frame = Frame.show(plugin, a.world, a.min, a.max, p, Frame.AREA);
        }, 2);
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Area a = areas.get(e.getPlayer().getName().toLowerCase());
        if (a != null) a.frame.forEach(rod -> e.getPlayer().showEntity(plugin, rod));
    }
}
