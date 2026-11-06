package dev.mcarchitect.architect;

import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.BlockDisplay;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.util.ArrayList;
import java.util.List;

/**
 * A glowing wireframe around a box, seen by one player only: 12 thin block displays (vanilla display
 * entities) with the glowing outline, which shows through walls and hills. Not saved with the world, and
 * redrawn when a chunk reload has taken some of its rods (display entities go when their chunk unloads).
 */
final class Frame {
    private static final float T = 0.08f;                       // rod thickness, in blocks
    static final Color PREVIEW = Color.fromRGB(0x55, 0xD6, 0xFF);   // light blue: a design waiting for a yes
    static final Color AREA = Color.fromRGB(0xFF, 0xC8, 0x3C);      // gold: the area a player marked

    private final Plugin plugin;
    final World world;
    final int[] min, max;  // inclusive block corners
    private final Color glow;
    private List<Entity> rods = List.of();

    Frame(Plugin plugin, World world, int[] min, int[] max, Color glow) {
        this.plugin = plugin;
        this.world = world;
        this.min = min;
        this.max = max;
        this.glow = glow;
    }

    /** Draw it for the viewer (again, if it was drawn before). */
    Frame show(Player viewer) {
        remove();
        float x0 = min[0], y0 = min[1], z0 = min[2], x1 = max[0] + 1, y1 = max[1] + 1, z1 = max[2] + 1;
        List<Entity> r = new ArrayList<>();
        for (float y : new float[]{y0, y1})
            for (float z : new float[]{z0, z1}) r.add(rod(x0, y, z, x1 - x0, T, T, viewer));
        for (float x : new float[]{x0, x1})
            for (float z : new float[]{z0, z1}) r.add(rod(x, y0, z, T, y1 - y0, T, viewer));
        for (float x : new float[]{x0, x1})
            for (float y : new float[]{y0, y1}) r.add(rod(x, y, z0, T, T, z1 - z0, viewer));
        rods = r;
        return this;
    }

    /** On a chunk load: a couple of ticks later (once the chunk reaches the client), redraw it if a rod is gone. */
    void repairSoon(Player viewer) {
        if (intact()) return;
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!intact()) show(viewer);
        }, 2);
    }

    /** A rejoined player is a new viewer. */
    void showTo(Player viewer) {
        rods.forEach(rod -> viewer.showEntity(plugin, rod));
    }

    boolean covers(int chunkX, int chunkZ) {
        return chunkX >= min[0] >> 4 && chunkX <= max[0] >> 4 && chunkZ >= min[2] >> 4 && chunkZ <= max[2] >> 4;
    }

    void remove() {
        rods.forEach(Entity::remove);
        rods = List.of();
    }

    private boolean intact() {
        return !rods.isEmpty() && rods.stream().allMatch(Entity::isValid);
    }

    private Entity rod(float x, float y, float z, float sx, float sy, float sz, Player viewer) {
        return world.spawn(new Location(world, x, y, z), BlockDisplay.class, d -> {
            d.setBlock(Material.WHITE_CONCRETE.createBlockData());
            d.setTransformation(new Transformation(new Vector3f(-T / 2 * (sx == T ? 1 : 0), -T / 2 * (sy == T ? 1 : 0),
                    -T / 2 * (sz == T ? 1 : 0)), new AxisAngle4f(), new Vector3f(sx, sy, sz), new AxisAngle4f()));
            d.setGlowing(true);
            d.setGlowColorOverride(glow);
            d.setBrightness(new Display.Brightness(15, 15));
            d.setViewRange(4f);                  // x64 blocks: visible from across a valley
            d.setPersistent(false);              // never saved: a crash can't leave frames behind
            d.setVisibleByDefault(false);        // only the asking player sees it
            d.addScoreboardTag("mcarchitect_preview");
            if (viewer != null) viewer.showEntity(plugin, d);
        });
    }
}
