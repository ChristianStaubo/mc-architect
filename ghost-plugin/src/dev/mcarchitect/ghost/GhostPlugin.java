package dev.mcarchitect.ghost;

import dev.mcarchitect.MCBridgePlugin;
import dev.mcarchitect.bridge.HttpBridge;
import dev.mcarchitect.core.Inbox;
import org.bukkit.Bukkit;
import org.bukkit.plugin.java.JavaPlugin;

import static dev.mcarchitect.core.Json.map;

/**
 * The ghost's side of the server (docs/ghost/design.md). The plugin decides nothing: it turns what players
 * say and click into events for ghost-core, shows the house picker, moves the ghosts' bodies and says what
 * ghost-core tells it to. Its routes ride on MCBridge's bridge (same token).
 */
public final class GhostPlugin extends JavaPlugin {
    // ghost-core drops repeats itself (events are stored by plugin id), so a lost event can come back fast
    private final Inbox inbox = new Inbox(20_000);
    private Houses houses;
    private Bodies bodies;

    @Override
    public void onEnable() {
        MCBridgePlugin mc = (MCBridgePlugin) Bukkit.getPluginManager().getPlugin("MCBridge");
        HttpBridge bridge = mc.bridge();
        houses = new Houses(this, inbox);
        bodies = new Bodies(this, houses);
        Listen listen = new Listen(this, inbox, houses, bodies);
        Bukkit.getPluginManager().registerEvents(houses, this);
        Bukkit.getPluginManager().registerEvents(listen, this);
        getCommand("ghost").setExecutor(listen);
        getCommand("ghost").setTabCompleter(listen);

        inbox.routes(bridge, "/ghost/inbox");  // (inbox/post: simulated players, for the evals)
        bridge.route("/ghost/houses", b -> bridge.sync(() -> houses.set(b)));
        bridge.route("/ghost/say", b -> bridge.sync(() -> listen.say(b)));
        bridge.route("/ghost/body", b -> bridge.sync(() -> bodies.act(b)));
        bridge.route("/ghost/bodies", b -> bridge.sync(bodies::describe));
        bridge.route("/ghost/status", b -> map("listening", inbox.listening(), "houses", houses.count()));
    }

    @Override
    public void onDisable() {
        if (bodies != null) bodies.removeAll();
    }
}
