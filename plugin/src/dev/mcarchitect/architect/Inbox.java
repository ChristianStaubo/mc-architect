package dev.mcarchitect.architect;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static dev.mcarchitect.core.Json.map;

/**
 * Events for the architect's daemon: every /arc becomes one, with the player's context. The daemon
 * long-polls (/inbox), handles them and acknowledges (/inbox/ack); unacknowledged events are handed out
 * again, so a daemon that restarts mid-job loses nothing. Kept in memory: a server restart drops them.
 */
final class Inbox {
    private static final long STALE_MS = 60_000;     // handed out but not acknowledged: hand out again
    private final Map<Long, Map<String, Object>> pending = new LinkedHashMap<>();
    private final Map<Long, Long> handedOut = new LinkedHashMap<>();
    private final Gson gson = new Gson();
    private long nextId = 1;
    private volatile long lastPoll = 0;

    synchronized long post(String kind, String text, Map<String, Object> context) {
        long id = nextId++;
        pending.put(id, map("id", id, "time", System.currentTimeMillis(), "kind", kind, "text", text,
                "player", context.get("player"), "context", context));
        notifyAll();
        return id;
    }

    /** The events not yet handed out (or handed out long ago and never acknowledged), waiting up to waitMs. */
    synchronized List<Map<String, Object>> poll(long waitMs) throws InterruptedException {
        lastPoll = System.currentTimeMillis();
        long until = lastPoll + waitMs;
        List<Map<String, Object>> out = ready();
        while (out.isEmpty() && System.currentTimeMillis() < until) {
            wait(Math.max(1, until - System.currentTimeMillis()));
            out = ready();
        }
        lastPoll = System.currentTimeMillis();
        long now = lastPoll;
        out.forEach(e -> handedOut.put((Long) e.get("id"), now));
        return out;
    }

    private List<Map<String, Object>> ready() {
        long now = System.currentTimeMillis();
        List<Map<String, Object>> out = new ArrayList<>();
        for (var e : pending.entrySet()) {
            Long at = handedOut.get(e.getKey());
            if (at == null || now - at > STALE_MS) out.add(e.getValue());
        }
        return out;
    }

    synchronized int ack(Iterable<JsonElement> ids) {
        int n = 0;
        for (JsonElement id : ids) {
            if (pending.remove(id.getAsLong()) != null) n++;
            handedOut.remove(id.getAsLong());
        }
        return n;
    }

    /** Is a daemon listening? (It polls at least every half minute.) */
    boolean listening() {
        return System.currentTimeMillis() - lastPoll < 40_000;
    }

    /** An event from the bridge, for a player who may not be online (evals' virtual players). */
    long postVirtual(JsonObject b) {
        @SuppressWarnings("unchecked")
        Map<String, Object> ctx = gson.fromJson(b.getAsJsonObject("context"), Map.class);
        if (ctx.get("player") == null) throw new IllegalArgumentException("context.player is needed");
        String kind = b.has("kind") ? b.get("kind").getAsString() : "request";
        return post(kind, b.has("text") ? b.get("text").getAsString() : "", ctx);
    }
}
