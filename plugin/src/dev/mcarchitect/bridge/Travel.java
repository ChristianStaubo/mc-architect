package dev.mcarchitect.bridge;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Survival travel for every player, no operator needed: /sethome and /home, and /tpa, /tpahere,
 * /tpaccept, /tpdeny (a teleport only happens when the other player accepts). Homes are kept in
 * plugins/MCBridge/homes.json; requests live in memory and expire after a minute.
 */
final class Travel implements CommandExecutor {
    static final String[] COMMANDS = {"sethome", "home", "tpa", "tpahere", "tpaccept", "tpdeny"};
    private static final long REQUEST_MS = 60_000;
    private static final long COOLDOWN_MS = 10_000;

    /** from asked to go to target (or, with here, asked target to come to them). */
    private record Request(UUID from, boolean here, long time) {}

    private final JavaPlugin plugin;
    private final Path homesFile;
    private final Gson gson = new Gson();
    private final Map<UUID, JsonObject> homes = new HashMap<>();
    private final Map<UUID, LinkedHashMap<UUID, Request>> requests = new HashMap<>();  // by target
    private final Map<UUID, Long> lastTeleport = new HashMap<>();

    Travel(JavaPlugin plugin) {
        this.plugin = plugin;
        this.homesFile = plugin.getDataFolder().toPath().resolve("homes.json");
        loadHomes();
        for (String name : COMMANDS) plugin.getCommand(name).setExecutor(this);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can use /" + command.getName());
            return true;
        }
        switch (command.getName()) {
            case "sethome" -> setHome(p);
            case "home" -> home(p);
            case "tpa", "tpahere" -> {
                if (args.length != 1) return false;  // shows the usage from plugin.yml
                ask(p, args[0], command.getName().equals("tpahere"));
            }
            case "tpaccept" -> answer(p, args.length > 0 ? args[0] : null, true);
            case "tpdeny" -> answer(p, args.length > 0 ? args[0] : null, false);
            default -> { return false; }
        }
        return true;
    }

    // ---- homes ----

    private void setHome(Player p) {
        Location l = p.getLocation();
        JsonObject h = new JsonObject();
        h.addProperty("world", l.getWorld().getName());
        h.addProperty("x", l.getX());
        h.addProperty("y", l.getY());
        h.addProperty("z", l.getZ());
        h.addProperty("yaw", l.getYaw());
        h.addProperty("pitch", l.getPitch());
        homes.put(p.getUniqueId(), h);
        saveHomes();
        say(p, "Home set at " + l.getBlockX() + " " + l.getBlockY() + " " + l.getBlockZ() + ". /home brings you back.");
    }

    private void home(Player p) {
        JsonObject h = homes.get(p.getUniqueId());
        if (h == null) {
            warn(p, "You have no home yet. Stand where you want it and use /sethome.");
            return;
        }
        World w = Bukkit.getWorld(h.get("world").getAsString());
        if (w == null) {
            warn(p, "Your home's world isn't loaded. Set a new home with /sethome.");
            return;
        }
        if (coolingDown(p)) return;
        Location to = new Location(w, h.get("x").getAsDouble(), h.get("y").getAsDouble(), h.get("z").getAsDouble(),
                h.get("yaw").getAsFloat(), h.get("pitch").getAsFloat());
        teleport(p, to, "Welcome home.");
    }

    private void loadHomes() {
        try {
            if (!Files.exists(homesFile)) return;
            JsonObject all = JsonParser.parseString(Files.readString(homesFile)).getAsJsonObject();
            for (String id : all.keySet()) homes.put(UUID.fromString(id), all.getAsJsonObject(id));
        } catch (IOException | RuntimeException e) {
            plugin.getLogger().warning("could not read " + homesFile + ": " + e);
        }
    }

    private void saveHomes() {
        JsonObject all = new JsonObject();
        homes.forEach((id, h) -> all.add(id.toString(), h));
        try {
            Files.createDirectories(homesFile.getParent());
            Path tmp = homesFile.resolveSibling("homes.json.tmp");
            Files.writeString(tmp, gson.toJson(all));
            Files.move(tmp, homesFile, java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                    java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            plugin.getLogger().warning("could not save " + homesFile + ": " + e);
        }
    }

    // ---- teleport requests ----

    private void ask(Player from, String name, boolean here) {
        Player to = Bukkit.getPlayerExact(name);
        if (to == null) {
            warn(from, name + " isn't online.");
            return;
        }
        if (to.equals(from)) {
            warn(from, "That's you.");
            return;
        }
        requests.computeIfAbsent(to.getUniqueId(), k -> new LinkedHashMap<>())
                .put(from.getUniqueId(), new Request(from.getUniqueId(), here, System.currentTimeMillis()));
        say(from, "Asked " + to.getName() + (here ? " to come to you." : " if you can teleport to them.")
                + " The request lasts a minute.");
        String ask = here ? from.getName() + " wants you to teleport to them. "
                : from.getName() + " wants to teleport to you. ";
        to.sendMessage(Component.text(ask, NamedTextColor.GOLD)
                .append(Component.text("[Accept]", NamedTextColor.GREEN)
                        .clickEvent(ClickEvent.runCommand("/tpaccept " + from.getName())))
                .append(Component.text(" "))
                .append(Component.text("[Deny]", NamedTextColor.RED)
                        .clickEvent(ClickEvent.runCommand("/tpdeny " + from.getName())))
                .append(Component.text("  or /tpaccept, /tpdeny", NamedTextColor.GRAY)));
    }

    private void answer(Player target, String fromName, boolean accept) {
        LinkedHashMap<UUID, Request> mine = requests.getOrDefault(target.getUniqueId(), new LinkedHashMap<>());
        long now = System.currentTimeMillis();
        mine.values().removeIf(r -> now - r.time() > REQUEST_MS || Bukkit.getPlayer(r.from()) == null);
        Request r = null;
        if (fromName != null) {
            Player from = Bukkit.getPlayerExact(fromName);
            if (from != null) r = mine.get(from.getUniqueId());
        } else {
            for (Request x : mine.values()) r = x;  // the newest
        }
        if (r == null) {
            warn(target, fromName == null ? "You have no teleport requests." : "No request from " + fromName + ".");
            return;
        }
        mine.remove(r.from());
        Player from = Bukkit.getPlayer(r.from());
        if (!accept) {
            say(target, "Denied " + from.getName() + "'s request.");
            warn(from, target.getName() + " said no.");
            return;
        }
        Player mover = r.here() ? target : from;
        Player anchor = r.here() ? from : target;
        if (coolingDown(mover)) {
            if (mover != target) warn(target, mover.getName() + " has to wait a few seconds before teleporting again.");
            return;
        }
        say(target, "Accepted.");
        teleport(mover, anchor.getLocation(), "Teleported to " + anchor.getName() + ".");
    }

    // ---- shared ----

    private boolean coolingDown(Player p) {
        long left = lastTeleport.getOrDefault(p.getUniqueId(), 0L) + COOLDOWN_MS - System.currentTimeMillis();
        if (left > 0) {
            warn(p, "Wait " + ((left + 999) / 1000) + "s before teleporting again.");
            return true;
        }
        return false;
    }

    private void teleport(Player p, Location to, String done) {
        lastTeleport.put(p.getUniqueId(), System.currentTimeMillis());
        p.teleportAsync(to).thenAccept(ok -> {
            if (ok) say(p, done);
            else warn(p, "The teleport didn't work. Try again in a moment.");
        });
    }

    private static void say(CommandSender s, String text) {
        s.sendMessage(Component.text(text, NamedTextColor.GREEN));
    }

    private static void warn(CommandSender s, String text) {
        s.sendMessage(Component.text(text, NamedTextColor.YELLOW));
    }
}
