package dev.mcarchitect.architect;

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
 * entities) with the glowing outline, which shows through walls and hills. Not saved with the world.
 */
final class Frame {
    private static final float T = 0.08f;                       // rod thickness, in blocks
    private static final Color GLOW = Color.fromRGB(0x55, 0xD6, 0xFF);

    private Frame() {}

    /** min..max inclusive block corners. */
    static List<Entity> show(Plugin plugin, World w, int[] min, int[] max, Player viewer) {
        float x0 = min[0], y0 = min[1], z0 = min[2], x1 = max[0] + 1, y1 = max[1] + 1, z1 = max[2] + 1;
        List<Entity> rods = new ArrayList<>();
        for (float y : new float[]{y0, y1})
            for (float z : new float[]{z0, z1}) rods.add(rod(plugin, w, x0, y, z, x1 - x0, T, T, viewer));
        for (float x : new float[]{x0, x1})
            for (float z : new float[]{z0, z1}) rods.add(rod(plugin, w, x, y0, z, T, y1 - y0, T, viewer));
        for (float x : new float[]{x0, x1})
            for (float y : new float[]{y0, y1}) rods.add(rod(plugin, w, x, y, z0, T, T, z1 - z0, viewer));
        return rods;
    }

    static boolean intact(List<Entity> rods) {
        return !rods.isEmpty() && rods.stream().allMatch(Entity::isValid);
    }

    static void remove(List<Entity> rods) {
        rods.forEach(Entity::remove);
    }

    private static Entity rod(Plugin plugin, World w, float x, float y, float z, float sx, float sy, float sz, Player viewer) {
        return w.spawn(new Location(w, x, y, z), BlockDisplay.class, d -> {
            d.setBlock(Material.WHITE_CONCRETE.createBlockData());
            d.setTransformation(new Transformation(new Vector3f(-T / 2 * (sx == T ? 1 : 0), -T / 2 * (sy == T ? 1 : 0),
                    -T / 2 * (sz == T ? 1 : 0)), new AxisAngle4f(), new Vector3f(sx, sy, sz), new AxisAngle4f()));
            d.setGlowing(true);
            d.setGlowColorOverride(GLOW);
            d.setBrightness(new Display.Brightness(15, 15));
            d.setViewRange(4f);                  // x64 blocks: visible from across a valley
            d.setPersistent(false);              // never saved: a crash can't leave frames behind
            d.setVisibleByDefault(false);        // only the asking player sees it
            d.addScoreboardTag("mcarchitect_preview");
            if (viewer != null) viewer.showEntity(plugin, d);
        });
    }
}
