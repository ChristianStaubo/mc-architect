package dev.mcarchitect;

import dev.mcarchitect.architect.Architect;
import dev.mcarchitect.bridge.HttpBridge;
import dev.mcarchitect.bridge.PlayerRoutes;
import dev.mcarchitect.bridge.WorldRoutes;
import dev.mcarchitect.core.Feature;
import dev.mcarchitect.travel.Travel;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.IOException;
import java.util.List;

/** Starts the bridge and switches the features on. Each feature lives in its own package. */
public final class MCBridgePlugin extends JavaPlugin {
    private HttpBridge bridge;
    private List<Feature> features = List.of();

    @Override
    public void onEnable() {
        try {
            bridge = new HttpBridge(this);
        } catch (IOException e) {
            throw new RuntimeException("bridge failed to start", e);
        }
        WorldRoutes world = new WorldRoutes(this, bridge);
        new PlayerRoutes(bridge, world);
        features = List.of(new Travel(), new Architect());
        features.forEach(f -> f.enable(this));
        bridge.start();
    }

    @Override
    public void onDisable() {
        features.forEach(Feature::disable);
        if (bridge != null) bridge.stop();
    }

    /** For features that add routes to the agent's API. */
    public HttpBridge bridge() {
        return bridge;
    }
}
