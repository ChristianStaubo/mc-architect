package dev.mcarchitect.bridge;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Two guarantees for world edits made by an agent system (docs/ghost/design.md, Durability):
 * <ul>
 * <li><b>Idempotency keys:</b> a /place with a key that was already applied returns the stored result and
 * changes nothing, so a retried step (Temporal retries activities) never builds twice. Keys survive
 * restarts: each applied key is appended to plugins/MCBridge/keys.jsonl (one short line, not a rewrite).</li>
 * <li><b>Signed grants:</b> a /place may carry a grant (task, box, block cap, expiry) signed with
 * plugins/MCBridge/grant-key. The build must fit the box and the cap, the grant must not have expired,
 * and the signature must match; the key never reaches a model.</li>
 * </ul>
 */
final class Grants {
    private final Path keysFile;
    private final byte[] secret;
    private final Gson gson = new Gson();
    private final Map<String, Map<String, Object>> applied = new LinkedHashMap<>();   // key -> the edit summary
    private final Map<String, Integer> used = new LinkedHashMap<>();     // task -> blocks placed under grants

    Grants(Path dataFolder) throws IOException {
        Files.createDirectories(dataFolder);
        keysFile = dataFolder.resolve("keys.jsonl");
        Path keyFile = dataFolder.resolve("grant-key");
        if (!Files.exists(keyFile)) {
            byte[] k = new byte[32];
            new SecureRandom().nextBytes(k);
            Files.writeString(keyFile, HexFormat.of().formatHex(k));
        }
        secret = HexFormat.of().parseHex(Files.readString(keyFile).trim());
        if (Files.exists(keysFile))
            for (String line : Files.readAllLines(keysFile)) {
                if (line.isBlank()) continue;
                JsonObject o = JsonParser.parseString(line).getAsJsonObject();
                if (o.has("key")) applied.put(o.get("key").getAsString(), summary(o.getAsJsonObject("summary")));
                if (o.has("task")) used.merge(o.get("task").getAsString(), o.get("blocks").getAsInt(), Integer::sum);
            }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> summary(JsonObject o) {
        return gson.fromJson(o, Map.class);
    }

    /** The stored result if this key was already applied, else null. */
    synchronized Map<String, Object> repeat(String key) {
        return key == null ? null : applied.get(key);
    }

    /** Throws if the grant doesn't cover a build of `blocks` cells in min..max. */
    synchronized void check(JsonObject g, String world, int[] min, int[] max, int blocks) {
        String task = g.get("task").getAsString();
        int[] gmin = ints(g.getAsJsonArray("min")), gmax = ints(g.getAsJsonArray("max"));
        if (!MessageDigest.isEqual(sign(g).getBytes(StandardCharsets.UTF_8), g.get("sig").getAsString().getBytes(StandardCharsets.UTF_8)))
            throw new IllegalArgumentException("grant signature doesn't match");
        if (g.get("exp").getAsLong() < System.currentTimeMillis() / 1000)
            throw new IllegalArgumentException("grant expired");
        if (!g.get("world").getAsString().equals(world))
            throw new IllegalArgumentException("grant is for world " + g.get("world").getAsString());
        for (int i = 0; i < 3; i++)
            if (min[i] < gmin[i] || max[i] > gmax[i])
                throw new IllegalArgumentException("build goes outside the granted box");
        int cap = g.get("max_blocks").getAsInt(), so_far = used.getOrDefault(task, 0);
        if (so_far + blocks > cap)
            throw new IllegalArgumentException("grant allows " + cap + " blocks; " + so_far + " used, this adds " + blocks);
    }

    synchronized void record(String key, JsonObject grant, int blocks, Map<String, Object> summary) throws IOException {
        Map<String, Object> line = new LinkedHashMap<>();
        if (key != null) {
            applied.put(key, summary);
            line.put("key", key);
            line.put("summary", summary);
        }
        if (grant != null) {
            String task = grant.get("task").getAsString();
            used.merge(task, blocks, Integer::sum);
            line.put("task", task);
            line.put("blocks", blocks);
        }
        Files.writeString(keysFile, gson.toJson(line) + "\n", java.nio.file.StandardOpenOption.CREATE,
                java.nio.file.StandardOpenOption.APPEND);
    }

    /** HMAC-SHA256 over the grant's fields in a fixed order (ghost/tools.py signs the same way). */
    private String sign(JsonObject g) {
        String msg = String.join("|", g.get("task").getAsString(), g.get("world").getAsString(),
                g.get("min").toString(), g.get("max").toString(), g.get("max_blocks").getAsString(), g.get("exp").getAsString());
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            return HexFormat.of().formatHex(mac.doFinal(msg.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static int[] ints(JsonArray a) {
        return new int[]{a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt()};
    }
}
