package dev.mcarchitect.bridge;

import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;

import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.str;

/** The server and the people on it: status, console commands, commands as a player. */
public final class PlayerRoutes {
    private final WorldRoutes world;

    public PlayerRoutes(HttpBridge bridge, WorldRoutes world) {
        this.world = world;
        bridge.route("/status", b -> bridge.sync(this::status));
        bridge.route("/command", b -> bridge.sync(() -> command(str(b, "command"))));
        bridge.route("/as", b -> bridge.sync(() -> asPlayer(str(b, "player"), str(b, "command"))));
    }

    private Object status() {
        List<Object> players = new ArrayList<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            Location l = p.getLocation();
            players.add(map("name", p.getName(), "world", l.getWorld().getName(),
                    "pos", new double[]{l.getX(), l.getY(), l.getZ()}, "yaw", l.getYaw(),
                    "gamemode", p.getGameMode().name()));
        }
        World w = Bukkit.getWorlds().get(0);
        Location s = w.getSpawnLocation();
        return map("minecraft", Bukkit.getMinecraftVersion(), "server", Bukkit.getVersion(),
                "tps", Bukkit.getTPS()[0], "players", players,
                "worlds", Bukkit.getWorlds().stream().map(World::getName).toList(),
                "spawn", new int[]{s.getBlockX(), s.getBlockY(), s.getBlockZ()},
                "world_height", new int[]{w.getMinHeight(), w.getMaxHeight()}, "edits", world.historySize());
    }

    private Object command(String cmd) {
        List<String> out = new ArrayList<>();
        var sender = Bukkit.createCommandSender(c -> out.add(PlainTextComponentSerializer.plainText().serialize(c)));
        boolean ok = Bukkit.dispatchCommand(sender, cmd.startsWith("/") ? cmd.substring(1) : cmd);
        return map("ok", ok, "output", out);
    }

    /** Run a command exactly as if the player typed it (plugin commands see the Player; `execute as`
     * doesn't give them one). Replies go to the player's chat, not back here. */
    private Object asPlayer(String name, String cmd) {
        Player p = Bukkit.getPlayerExact(name);
        if (p == null) throw new IllegalArgumentException(name + " isn't online");
        return map("ok", Bukkit.dispatchCommand(p, cmd.startsWith("/") ? cmd.substring(1) : cmd));
    }
}
