package dev.mcarchitect.core;

import dev.mcarchitect.MCBridgePlugin;

/**
 * A part of the plugin that can be switched on (travel, the architect, ...). It registers its own
 * commands (declared in plugin.yml), listeners and bridge routes in enable().
 */
public interface Feature {
    void enable(MCBridgePlugin plugin);

    default void disable() {}
}
