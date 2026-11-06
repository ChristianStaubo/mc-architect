package dev.mcarchitect.ghost;

import com.google.gson.JsonObject;
import dev.mcarchitect.core.Chat;
import dev.mcarchitect.core.Inbox;
import dev.mcarchitect.core.Looking;
import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.plugin.Plugin;

import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.str;

/**
 * How the ghost listens (docs/ghost/design.md, "Listening"). Code decides only who a message is
 * addressed to, never what it means:
 * <ul>
 * <li><b>explicit</b>: /ghost ..., chat starting with "ghost" or "@ghost", button clicks;</li>
 * <li><b>candidate</b>: chat mentioning "ghost" anywhere, or said within NEAR blocks of a ghost's body
 *     (ghost-core asks a small model whether it's for the ghost);</li>
 * <li>everything else is never sent anywhere.</li>
 * </ul>
 * /ghost stop never waits on a model: the body stops here, and ghost-core is told.
 */
final class Listen implements Listener, TabExecutor {
    private static final double NEAR = 10;
    private static final Pattern START = Pattern.compile("^\\s*@?ghost\\b[\\s,:!]*", Pattern.CASE_INSENSITIVE);
    private static final Pattern MENTION = Pattern.compile("\\bghosts?\\b", Pattern.CASE_INSENSITIVE);

    private final Plugin plugin;
    private final Inbox inbox;
    private final Houses houses;
    private final Bodies bodies;

    Listen(Plugin plugin, Inbox inbox, Houses houses, Bodies bodies) {
        this.plugin = plugin;
        this.inbox = inbox;
        this.houses = houses;
        this.bodies = bodies;
    }

    /** What ghost-core knows about the player when they speak: where, facing, looking at, their house. */
    static Map<String, Object> context(Player p, Houses houses) {
        Location l = p.getLocation();
        Block t = Looking.target(p);
        return map("player", p.getName(), "uuid", p.getUniqueId().toString(), "world", l.getWorld().getName(),
                "pos", new int[]{l.getBlockX(), l.getBlockY(), l.getBlockZ()},
                "facing", Looking.facing(l.getYaw()), "house", houses.houseOf(p.getName()), "role", houses.roleOf(p.getName()),
                "target", t == null ? null : map("pos", new int[]{t.getX(), t.getY(), t.getZ()},
                        "block", t.getBlockData().getAsString()));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        String text = PlainTextComponentSerializer.plainText().serialize(e.message());
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(plugin, () -> {  // context is read on the main thread
            var start = START.matcher(text);
            String near = bodies.near(p, NEAR);
            String addressed = start.find() ? "explicit" : (MENTION.matcher(text).find() || near != null) ? "candidate" : null;
            if (addressed == null) return;  // not for the ghost: never leaves the server
            Map<String, Object> ctx = context(p, houses);
            ctx.put("addressed", addressed);
            ctx.put("near_ghost", near);
            inbox.post("chat", addressed.equals("explicit") ? start.replaceFirst("") : text, ctx);
        });
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can talk to the ghost.");
            return true;
        }
        if (args.length == 0) {
            Chat.warn(p, "Talk to your house's ghost: /ghost follow me, /ghost build a bench here. "
                    + "/ghost stop stops it at once. /ghost house shows the houses.");
            return true;
        }
        String first = args[0].toLowerCase();
        Map<String, Object> ctx = context(p, houses);
        ctx.put("addressed", "explicit");
        switch (first) {
            case "stop" -> {  // the kill switch: never waits on a model
                String g = houses.houseOf(p.getName());
                if (g != null) bodies.stop(g);
                inbox.post("button", "stop", ctx);
                p.sendMessage(Component.text("(stopped)", NamedTextColor.GRAY));
            }
            case "house" -> houses.open(p);
            case "yes", "no", "approve", "deny", "undo", "status" ->  // buttons: structured, no model needed
                    inbox.post("button", String.join(" ", args).toLowerCase(), ctx);
            default -> {
                inbox.post("command", String.join(" ", args), ctx);
                p.sendMessage(Component.text(inbox.listening() ? "(the ghost heard you)"
                        : "(the ghost is away right now; it'll hear this when it's back)", NamedTextColor.GRAY));
            }
        }
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length != 1) return List.of();
        return List.of("follow me", "come here", "stop", "house", "status").stream()
                .filter(w -> w.startsWith(args[0].toLowerCase())).toList();
    }

    /** body: ghost (house id or "spirit"), player (or null: everyone), text, buttons [[label, command]]. */
    Object say(JsonObject b) {
        String ghost = str(b, "ghost", "spirit");
        Houses.House h = houses.get(ghost);
        TextColor color = h == null ? NamedTextColor.WHITE : h.color();
        String name = h == null ? "The spirit" : h.name() + " ghost";
        Component msg = Chat.withButtons(Component.text("[" + name + "] ", color)
                .append(Component.text(str(b, "text"), NamedTextColor.WHITE)), b.has("buttons") ? b.getAsJsonArray("buttons") : null);
        String to = b.has("player") && !b.get("player").isJsonNull() ? str(b, "player") : null;
        if (to == null) {
            Bukkit.broadcast(msg);
            return map("delivered", true, "to", "everyone");
        }
        Player p = Bukkit.getPlayerExact(to);
        if (p == null) return map("delivered", false, "to", to);
        p.sendMessage(msg);
        return map("delivered", true, "to", to);
    }
}
