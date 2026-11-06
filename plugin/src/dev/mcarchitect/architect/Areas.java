package dev.mcarchitect.architect;

import com.sk89q.worldedit.IncompleteRegionException;
import com.sk89q.worldedit.LocalSession;
import com.sk89q.worldedit.WorldEdit;
import com.sk89q.worldedit.bukkit.BukkitAdapter;
import com.sk89q.worldedit.extension.platform.permission.ActorSelectorLimits;
import com.sk89q.worldedit.math.BlockVector3;
import com.sk89q.worldedit.regions.RegionSelector;
import dev.mcarchitect.core.Chat;
import io.papermc.paper.event.packet.PlayerChunkLoadEvent;
import org.bukkit.Bukkit;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * Marking an area without the WorldEdit wand: /arc mark while looking at one corner, then at the opposite
 * corner. That sets the player's WorldEdit selection (the one place the architect reads an area from) a
 * little taller than the corners, and draws it in gold for them. A build placed with /arc yes uses the
 * selection up (clear()); so do /arc clear and a new first corner.
 */
final class Areas implements Listener {
    private static final int HEADROOM = 8;  // the selection reaches this far above the higher corner

    private final Plugin plugin;
    private final Set<String> half = new HashSet<>();            // first corner marked, waiting for the second
    private final Map<String, Frame> frames = new HashMap<>();   // by player name (lower case)

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
        var actor = BukkitAdapter.adapt(p);
        RegionSelector sel = session(p).getRegionSelector(BukkitAdapter.adapt(b.getWorld()));
        var limits = ActorSelectorLimits.forActor(actor);
        BlockVector3 first = half.remove(key) ? primary(sel) : null;
        if (first == null) {  // (also when the wand changed the selection in between)
            clear(p.getName());
            sel.selectPrimary(BlockVector3.at(b.getX(), b.getY(), b.getZ()), limits);
            half.add(key);
            Chat.say(p, "First corner at " + b.getX() + " " + b.getY() + " " + b.getZ()
                    + ". Now look at the opposite corner and /arc mark again.");
            return;
        }
        int top = Math.max(first.y(), b.getY()) + HEADROOM;
        sel.selectPrimary(BlockVector3.at(first.x(), Math.min(first.y(), b.getY()), first.z()), limits);
        sel.selectSecondary(BlockVector3.at(b.getX(), top, b.getZ()), limits);
        session(p).dispatchCUISelection(actor);
        int[] min = {Math.min(first.x(), b.getX()), Math.min(first.y(), b.getY()), Math.min(first.z(), b.getZ())};
        int[] max = {Math.max(first.x(), b.getX()), top, Math.max(first.z(), b.getZ())};
        frames.put(key, new Frame(plugin, b.getWorld(), min, max, Frame.AREA).show(p));
        Chat.say(p, "Area marked: " + (max[0] - min[0] + 1) + " by " + (max[2] - min[2] + 1)
                + " blocks. Now tell the architect what to build there: /arc <idea>. /arc clear drops it.");
    }

    /** Drop the player's selection (marked or made with the wand) and its frame. */
    boolean clear(String name) {
        String key = name.toLowerCase();
        half.remove(key);
        Frame f = frames.remove(key);
        if (f != null) f.remove();
        Player p = Bukkit.getPlayerExact(name);
        if (p == null) return f != null;
        RegionSelector sel = session(p).getRegionSelector(BukkitAdapter.adapt(p.getWorld()));
        boolean had = f != null || sel.isDefined();
        sel.clear();
        session(p).dispatchCUISelection(BukkitAdapter.adapt(p));
        return had;
    }

    private static BlockVector3 primary(RegionSelector sel) {
        try {
            return sel.getPrimaryPosition();
        } catch (IncompleteRegionException e) {
            return null;
        }
    }

    private static LocalSession session(Player p) {
        return WorldEdit.getInstance().getSessionManager().get(BukkitAdapter.adapt(p));
    }

    @EventHandler
    public void onChunk(PlayerChunkLoadEvent e) {
        Frame f = frames.get(e.getPlayer().getName().toLowerCase());
        if (f != null && e.getWorld().equals(f.world) && f.covers(e.getChunk().getX(), e.getChunk().getZ()))
            f.repairSoon(e.getPlayer());
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Frame f = frames.get(e.getPlayer().getName().toLowerCase());
        if (f != null) f.showTo(e.getPlayer());
    }
}
