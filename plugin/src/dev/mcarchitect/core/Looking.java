package dev.mcarchitect.core;

import org.bukkit.FluidCollisionMode;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;

/** Where a player is looking and facing, the same way for /arc and the ghost. */
public final class Looking {
    public static final int RANGE = 200;

    private Looking() {}

    /** The block under the crosshair (through grass and flowers, not water), or null past RANGE blocks. */
    public static Block target(Player p) {
        var eye = p.getEyeLocation();
        var hit = p.getWorld().rayTraceBlocks(eye, eye.getDirection(), RANGE, FluidCollisionMode.NEVER, true);
        return hit == null ? null : hit.getHitBlock();
    }

    /** The way a yaw looks: Minecraft's yaw 0 is south, 90 west, 180 north, 270 east. */
    public static String facing(float yaw) {
        return new String[]{"south", "west", "north", "east"}[Math.floorMod(Math.round(yaw / 90f), 4)];
    }
}
