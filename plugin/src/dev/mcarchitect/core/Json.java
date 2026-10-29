package dev.mcarchitect.core;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.World;

import java.util.LinkedHashMap;
import java.util.Map;

/** Small helpers for the bridge's JSON bodies and replies. */
public final class Json {
    private Json() {}

    public static Map<String, Object> map(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    public static int[] ints(JsonObject b, String key, int n) {
        JsonArray a = b.getAsJsonArray(key);
        if (a == null || a.size() != n) throw new IllegalArgumentException(key + " needs " + n + " integers");
        int[] out = new int[n];
        for (int i = 0; i < n; i++) out[i] = a.get(i).getAsInt();
        return out;
    }

    public static String str(JsonObject b, String key) {
        if (!b.has(key) || b.get(key).isJsonNull()) throw new IllegalArgumentException("missing " + key);
        return b.get(key).getAsString();
    }

    public static String str(JsonObject b, String key, String otherwise) {
        return b.has(key) && !b.get(key).isJsonNull() ? b.get(key).getAsString() : otherwise;
    }

    public static int integer(JsonObject b, String key, int otherwise) {
        return b.has(key) && !b.get(key).isJsonNull() ? b.get(key).getAsInt() : otherwise;
    }

    public static boolean bool(JsonObject b, String key, boolean otherwise) {
        return b.has(key) && !b.get(key).isJsonNull() ? b.get(key).getAsBoolean() : otherwise;
    }

    /** The body's "world", or the main world. */
    public static World world(JsonObject b) {
        String name = str(b, "world", Bukkit.getWorlds().get(0).getName());
        World w = Bukkit.getWorld(name);
        if (w == null) throw new IllegalArgumentException("no world " + name);
        return w;
    }
}
