package dev.mcarchitect.bridge;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.sk89q.worldedit.EditSession;
import com.sk89q.worldedit.WorldEdit;
import com.sk89q.worldedit.bukkit.BukkitAdapter;
import com.sk89q.worldedit.math.BlockVector3;
import com.sk89q.worldedit.world.block.BlockState;
import org.bukkit.Bukkit;
import org.bukkit.HeightMap;
import org.bukkit.World;
import org.bukkit.plugin.Plugin;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static dev.mcarchitect.core.Json.ints;
import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.world;

/**
 * Reading and changing the world. Block grids are sent run-length encoded in y, z, x order (x fastest),
 * with a palette of block-data strings; a null palette entry means "leave this block alone". Every
 * placement goes through a WorldEdit EditSession, so it can be undone.
 */
public final class WorldRoutes {
    static final int MAX_VOLUME = 4_000_000;
    private static final int MAX_HISTORY = 100;

    private final Plugin plugin;
    private final Deque<Edit> history = new ArrayDeque<>();
    private int nextEditId = 1;

    private record Edit(int id, String label, String world, int[] min, int[] max, int changed, long time,
                        EditSession session) {
        Map<String, Object> summary() {
            return map("id", id, "label", label, "world", world, "min", min, "max", max,
                    "changed", changed, "time", time);
        }
    }

    public WorldRoutes(Plugin plugin, HttpBridge bridge) {
        this.plugin = plugin;
        bridge.route("/region", b -> bridge.sync(() -> region(b)));
        bridge.route("/heightmap", b -> bridge.sync(() -> heightmap(b)));
        bridge.route("/place", b -> bridge.sync(() -> place(b)));
        bridge.route("/undo", b -> bridge.sync(() -> undo(b)));
        bridge.route("/history", b -> bridge.sync(() -> map("edits", history.stream().map(Edit::summary).toList())));
        bridge.route("/blocks", b -> map("blocks", java.util.Arrays.stream(org.bukkit.Material.values())
                .filter(m -> m.isBlock() && !m.isLegacy()).map(m -> m.getKey().getKey()).sorted().toList()));
        bridge.route("/validate", b -> bridge.sync(() -> validate(b)));
        bridge.route("/use", b -> bridge.sync(() -> use(b)));
        bridge.route("/kick", b -> bridge.sync(() -> map("kicked", kick(world(b), ints(b, "min", 3), ints(b, "max", 3)))));
        bridge.route("/sign", b -> bridge.sync(() -> sign(b)));
    }

    public int historySize() {
        return history.size();
    }

    private Object region(JsonObject b) {
        World w = world(b);
        int[] min = ints(b, "min", 3), max = ints(b, "max", 3);
        int[] size = box(min, max);
        Map<org.bukkit.block.data.BlockData, Integer> palette = new LinkedHashMap<>();
        Rle rle = new Rle();
        for (int y = min[1]; y <= max[1]; y++)
            for (int z = min[2]; z <= max[2]; z++)
                for (int x = min[0]; x <= max[0]; x++)
                    rle.add(palette.computeIfAbsent(w.getBlockAt(x, y, z).getBlockData(), k -> palette.size()));
        List<String> names = palette.keySet().stream().map(org.bukkit.block.data.BlockData::getAsString).toList();
        return map("world", w.getName(), "min", min, "max", max, "size", size, "palette", names, "rle", rle.done());
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
        box(origin, new int[]{origin[0] + size[0] - 1, origin[1] + size[1] - 1, origin[2] + size[2] - 1});
        long volume = (long) size[0] * size[1] * size[2];
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
        if (!b.has("history") || b.get("history").getAsBoolean()) {  // eval site resets keep out: nothing to undo
            history.push(edit);
            while (history.size() > MAX_HISTORY) history.removeLast();
        }
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
        kickAround(attached);
        if (on && blk.getType().name().endsWith("_BUTTON")) {
            final org.bukkit.block.Block button = blk, base = attached;
            int ticks = b.has("ticks") ? b.get("ticks").getAsInt() : 20;
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (button.getBlockData() instanceof org.bukkit.block.data.Powerable p2) {
                    p2.setPowered(false);
                    button.setBlockData(p2, true);
                    kickAround(base);
                }
            }, ticks);
        }
        return map("pos", at, "block", blk.getBlockData().getAsString(), "powered", on);
    }

    /** Write up to 4 lines of text on a sign (front or back). Block data can't carry text. */
    private Object sign(JsonObject b) {
        World w = world(b);
        int[] at = ints(b, "pos", 3);
        org.bukkit.block.Block blk = w.getBlockAt(at[0], at[1], at[2]);
        if (!(blk.getState() instanceof org.bukkit.block.Sign sg))
            throw new IllegalArgumentException("not a sign: " + blk.getBlockData().getAsString());
        org.bukkit.block.sign.Side side = org.bukkit.block.sign.Side.valueOf(
                b.has("side") ? b.get("side").getAsString().toUpperCase() : "FRONT");
        JsonArray lines = b.getAsJsonArray("lines");
        var face = sg.getSide(side);
        for (int i = 0; i < 4; i++)
            face.line(i, net.kyori.adventure.text.Component.text(i < lines.size() ? lines.get(i).getAsString() : ""));
        sg.update(true, false);
        return map("pos", at, "lines", lines.size());
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
    private int kickAround(org.bukkit.block.Block c) {
        return kick(c.getWorld(), new int[]{c.getX() - 1, c.getY() - 1, c.getZ() - 1},
                new int[]{c.getX() + 1, c.getY() + 1, c.getZ() + 1});
    }

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

    static int[] box(int[] min, int[] max) {
        int[] size = {max[0] - min[0] + 1, max[1] - min[1] + 1, max[2] - min[2] + 1};
        if (size[0] < 1 || size[1] < 1 || size[2] < 1) throw new IllegalArgumentException("max must be >= min");
        if ((long) size[0] * size[1] * size[2] > MAX_VOLUME)
            throw new IllegalArgumentException("region too large (max " + MAX_VOLUME + " blocks)");
        return size;
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
