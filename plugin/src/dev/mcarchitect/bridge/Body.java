package dev.mcarchitect.bridge;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.data.BlockData;

import static dev.mcarchitect.core.Json.ints;


/**
 * A block grid as the agent sends it (/place, /preview): origin, size, a palette of block-data strings
 * (null = leave alone) and run-length pairs in y, z, x order. Decoding touches no blocks, so it can run off
 * the main thread.
 */
public record Body(World world, int[] origin, int[] size, int[] max, BlockData[] palette, int[] cells) {
    static final int MAX_VOLUME = 4_000_000;

    public static Body decode(JsonObject b) {
        World w = dev.mcarchitect.core.Json.world(b);
        int[] origin = ints(b, "origin", 3), size = ints(b, "size", 3);
        int[] max = {origin[0] + size[0] - 1, origin[1] + size[1] - 1, origin[2] + size[2] - 1};
        box(origin, max);
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
        long volume = (long) size[0] * size[1] * size[2];
        return new Body(w, origin, size, max, data, WorldRoutes.Rle.decode(b.getAsJsonArray("rle"), volume, data.length));
    }

    /** Each cell's block (null: leave alone), with its world position: visit(x, y, z, data). */
    public void forEach(Cell visit) {
        int i = 0;
        for (int y = 0; y < size[1]; y++)
            for (int z = 0; z < size[2]; z++)
                for (int x = 0; x < size[0]; x++, i++)
                    if (palette[cells[i]] != null) visit.at(origin[0] + x, origin[1] + y, origin[2] + z, palette[cells[i]]);
    }

    public interface Cell {
        void at(int x, int y, int z, BlockData data);
    }

    static int[] box(int[] min, int[] max) {
        int[] size = {max[0] - min[0] + 1, max[1] - min[1] + 1, max[2] - min[2] + 1};
        if (size[0] < 1 || size[1] < 1 || size[2] < 1) throw new IllegalArgumentException("max must be >= min");
        if ((long) size[0] * size[1] * size[2] > MAX_VOLUME)
            throw new IllegalArgumentException("region too large (max " + MAX_VOLUME + " blocks)");
        return size;
    }
}
