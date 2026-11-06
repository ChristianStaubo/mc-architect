package dev.mcarchitect.architect;

import com.sk89q.worldedit.IncompleteRegionException;
import com.sk89q.worldedit.WorldEdit;
import com.sk89q.worldedit.bukkit.BukkitAdapter;
import com.sk89q.worldedit.regions.Region;
import org.bukkit.FluidCollisionMode;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;

import java.util.Map;

import static dev.mcarchitect.core.Json.map;

/** What the architect knows about a player when they ask: where they are, what they face, what they selected. */
final class Context {
    private Context() {}

    /** The block under the player's crosshair (through grass and flowers, not water), or null past 200 blocks. */
    static Block target(Player p) {
        var eye = p.getEyeLocation();
        var hit = p.getWorld().rayTraceBlocks(eye, eye.getDirection(), 200, FluidCollisionMode.NEVER, true);
        return hit == null ? null : hit.getHitBlock();
    }

    static Map<String, Object> of(Player p, Areas areas) {
        Location l = p.getLocation();
        Block ground = l.getBlock().getRelative(0, -1, 0);
        while (ground.isPassable() && ground.getY() > l.getWorld().getMinHeight()) ground = ground.getRelative(0, -1, 0);
        Map<String, Object> c = map("player", p.getName(), "world", l.getWorld().getName(),
                "pos", new int[]{l.getBlockX(), l.getBlockY(), l.getBlockZ()},
                "facing", facing(l.getYaw()), "yaw", Math.round(l.getYaw()),
                "ground", map("y", ground.getY(), "block", ground.getBlockData().getAsString()),
                "biome", l.getBlock().getBiome().getKey().getKey(),
                "gamemode", p.getGameMode().name().toLowerCase());
        try {
            Region r = WorldEdit.getInstance().getSessionManager().get(BukkitAdapter.adapt(p))
                    .getSelection(BukkitAdapter.adapt(l.getWorld()));
            var lo = r.getMinimumPoint();
            var hi = r.getMaximumPoint();
            c.put("selection", map("min", new int[]{lo.x(), lo.y(), lo.z()}, "max", new int[]{hi.x(), hi.y(), hi.z()}));
        } catch (IncompleteRegionException e) {
            c.put("selection", areas.selection(p));  // no WorldEdit selection: the area marked with /arc mark
        }
        Block t = target(p);  // "here", "there", "on this hill": where they're looking
        c.put("target", t == null ? null : map("pos", new int[]{t.getX(), t.getY(), t.getZ()},
                "block", t.getBlockData().getAsString(), "distance", (int) Math.round(t.getLocation().distance(l))));
        return c;
    }

    /** The way a yaw looks: Minecraft's yaw 0 is south, 90 west, 180 north, 270 east. */
    static String facing(float yaw) {
        int q = Math.floorMod(Math.round(yaw / 90f), 4);
        return new String[]{"south", "west", "north", "east"}[q];
    }
}
