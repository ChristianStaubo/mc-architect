package dev.mcarchitect.architect;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import dev.mcarchitect.MCBridgePlugin;
import dev.mcarchitect.bridge.HttpBridge;
import dev.mcarchitect.core.Chat;
import dev.mcarchitect.core.Feature;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;
import org.bukkit.entity.Player;

import java.util.List;
import java.util.Set;

import static dev.mcarchitect.core.Json.integer;
import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.str;

/**
 * The in-game architect (docs/architect.md). /arc turns what a player says into an event for the
 * daemon (mc architect serve), which answers through /say and shows designs through /preview. The plugin
 * never decides anything itself: it carries words, context and ghost blocks.
 */
public final class Architect implements Feature, TabExecutor {
    static final Set<String> WORDS = Set.of("yes", "no", "undo", "cancel", "status");  // for the daemon
    private static final List<String> COMPLETIONS = List.of("cancel", "clear", "mark", "no", "status", "undo", "yes");
    private static final Component NAME = Component.text("[Architect] ", NamedTextColor.AQUA);

    private final Inbox inbox = new Inbox();
    private Preview preview;
    private Areas areas;

    @Override
    public void enable(MCBridgePlugin plugin) {
        preview = new Preview(plugin);
        Bukkit.getPluginManager().registerEvents(preview, plugin);
        areas = new Areas(plugin);
        Bukkit.getPluginManager().registerEvents(areas, plugin);
        plugin.getCommand("arc").setExecutor(this);
        plugin.getCommand("arc").setTabCompleter(this);
        HttpBridge bridge = plugin.bridge();
        bridge.route("/inbox", b -> map("events", inbox.poll(1000L * Math.min(30, integer(b, "wait", 25)))));
        bridge.route("/inbox/ack", b -> map("acked", inbox.ack(b.getAsJsonArray("ids"))));
        bridge.route("/inbox/post", b -> map("id", inbox.postVirtual(b)));
        bridge.route("/say", b -> bridge.sync(() -> say(b)));
        bridge.route("/preview", b -> {
            Preview.Prepared ready = Preview.prepare(b);  // decoding stays off the main thread
            return bridge.sync(() -> preview.show(ready));
        });
        bridge.route("/preview/clear", b -> bridge.sync(() -> {  // area: true also drops their selection (used up by a build)
            if (b.has("area") && b.get("area").getAsBoolean()) areas.clear(str(b, "player"));
            return map("cleared", preview.clear(str(b, "player")));
        }));
        bridge.route("/preview/get", b -> bridge.sync(() -> preview.describe(str(b, "player"))));
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can talk to the architect.");
            return true;
        }
        if (args.length == 0) {
            Chat.warn(p, "Tell the architect what to build: /arc a stone well with a little roof, right here "
                    + "(it builds where you look). To pick an area: look at one corner, /arc mark, then the "
                    + "opposite corner, /arc mark. Then /arc yes, /arc no, or say what to change; /arc undo.");
            return true;
        }
        String first = args.length == 1 ? args[0].toLowerCase() : "";
        switch (first) {
            case "mark" -> {
                areas.mark(p);
                return true;
            }
            case "clear" -> {
                Chat.say(p, areas.clear(p.getName()) ? "Area cleared." : "You have no marked area.");
                return true;
            }
            default -> {}
        }
        boolean word = WORDS.contains(first);
        inbox.post(word ? first : "request", word ? "" : String.join(" ", args), Context.of(p, !word));
        p.sendMessage(Component.text(inbox.listening() ? "(sent to the architect)"
                : "(the architect isn't at the drawing board right now; it'll get this when it's back)", NamedTextColor.GRAY));
        return true;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length != 1) return List.of();
        return COMPLETIONS.stream().filter(w -> w.startsWith(args[0].toLowerCase())).toList();
    }

    /** body: player, text, tone (info|done|warn|thinking), buttons [[label, command], ...]. */
    private Object say(JsonObject b) {
        String name = str(b, "player");
        Player p = Bukkit.getPlayerExact(name);
        if (p == null) return map("player", name, "delivered", false);
        Component msg = NAME.append(Component.text(str(b, "text"), Chat.tone(str(b, "tone", "info"))));
        if (b.has("buttons"))
            for (var e : b.getAsJsonArray("buttons")) {
                JsonArray pair = e.getAsJsonArray();
                msg = msg.append(Component.text(" ")).append(Chat.button(pair.get(0).getAsString(), pair.get(1).getAsString(),
                        NamedTextColor.GOLD));
            }
        p.sendMessage(msg);
        return map("player", name, "delivered", true);
    }
}
