package dev.mcarchitect.ghost;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import dev.mcarchitect.core.Inbox;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.Plugin;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.str;

/**
 * A copy of the houses and who's in them, sent by ghost-core (the store is the truth), and the house
 * picker: a small menu with a banner per house, opened on a player's first join. A click becomes a
 * pick_house event; ghost-core records it and sends the members back.
 */
final class Houses implements Listener {
    record House(String id, String name, TextColor color, String motto, String style) {}

    private final Plugin plugin;
    private final Inbox inbox;
    private final Map<String, House> houses = new java.util.LinkedHashMap<>();
    private final Map<String, String> members = new HashMap<>();   // player (lower case) -> house id
    private final Map<String, String> roles = new HashMap<>();

    Houses(Plugin plugin, Inbox inbox) {
        this.plugin = plugin;
        this.inbox = inbox;
    }

    /** body: houses [{id, name, color, motto}], members {player: {house, role}}. The plugin needs no zones:
     * every decision about land is ghost-core's. */
    Object set(JsonObject b) {
        if (b.has("houses")) {
            houses.clear();
            for (JsonElement e : b.getAsJsonArray("houses")) {
                JsonObject h = e.getAsJsonObject();
                houses.put(str(h, "id"), new House(str(h, "id"), str(h, "name"), TextColor.fromHexString(str(h, "color")),
                        str(h, "motto", ""), str(h, "style", "")));
            }
        }
        if (b.has("members")) {
            members.clear();
            roles.clear();
            b.getAsJsonObject("members").entrySet().forEach(e -> {
                JsonObject m = e.getValue().getAsJsonObject();
                if (m.has("house") && !m.get("house").isJsonNull()) members.put(e.getKey().toLowerCase(), m.get("house").getAsString());
                roles.put(e.getKey().toLowerCase(), str(m, "role", "guest"));
            });
        }
        return map("houses", houses.size(), "members", members.size());
    }

    int count() {
        return houses.size();
    }

    House get(String id) {
        return houses.get(id);
    }

    String houseOf(String player) {
        return members.get(player.toLowerCase());
    }

    String roleOf(String player) {
        return roles.getOrDefault(player.toLowerCase(), "guest");
    }

    private static final class Menu implements InventoryHolder {
        final List<String> slots = new ArrayList<>();
        Inventory inv;

        @Override
        public Inventory getInventory() {
            return inv;
        }
    }

    /** The house picker: a dialog screen (Minecraft's own UI since 1.21.6) with each house's banner, motto,
     * style and members, and a button to join; the chest menu if the dialog can't be shown. */
    void open(Player p) {
        if (houses.isEmpty()) return;
        try {
            p.showDialog(dialog());
        } catch (RuntimeException | LinkageError e) {
            plugin.getLogger().warning("house dialog failed (" + e + "); showing the menu instead");
            openMenu(p);
        }
    }

    private io.papermc.paper.dialog.Dialog dialog() {
        List<io.papermc.paper.registry.data.dialog.body.DialogBody> body = new ArrayList<>();
        body.add(io.papermc.paper.registry.data.dialog.body.DialogBody.plainMessage(Component.text(
                "Each house has its own land, its own style and its own ghost, who builds with you. "
                        + "Choose one; only the server owner can move you later.", NamedTextColor.GRAY), 300));
        List<io.papermc.paper.registry.data.dialog.ActionButton> buttons = new ArrayList<>();
        for (House h : houses.values()) {
            long n = members.values().stream().filter(h.id()::equals).count();
            Component about = Component.text(h.name(), h.color()).decorate(TextDecoration.BOLD)
                    .append(Component.text("  " + n + (n == 1 ? " member" : " members"), NamedTextColor.DARK_GRAY))
                    .append(Component.newline()).append(Component.text(h.motto(), NamedTextColor.WHITE))
                    .append(h.style().isEmpty() ? Component.empty()
                            : Component.newline().append(Component.text(h.style(), NamedTextColor.GRAY)));
            body.add(io.papermc.paper.registry.data.dialog.body.DialogBody.item(new ItemStack(banner(h.color())),
                    io.papermc.paper.registry.data.dialog.body.DialogBody.plainMessage(about, 260), false, false, 16, 16));
            buttons.add(io.papermc.paper.registry.data.dialog.ActionButton.create(
                    Component.text("Join " + h.name(), h.color()), Component.text(h.motto()), 140,
                    io.papermc.paper.registry.data.dialog.action.DialogAction.customClick((view, audience) -> {
                        if (audience instanceof Player who) choose(who, h.id());
                    }, net.kyori.adventure.text.event.ClickCallback.Options.builder().uses(1).build())));
        }
        var later = io.papermc.paper.registry.data.dialog.ActionButton.create(Component.text("Decide later"),
                Component.text("/ghost house opens this again"), 140, null);
        return io.papermc.paper.dialog.Dialog.create(f -> f.empty()
                .base(io.papermc.paper.registry.data.dialog.DialogBase.builder(Component.text("Choose your house"))
                        .canCloseWithEscape(true).body(body).build())
                .type(io.papermc.paper.registry.data.dialog.type.DialogType.multiAction(buttons, later, 2)));
    }

    private void choose(Player p, String house) {
        if (houseOf(p.getName()) != null) return;  // a second click, or a stale screen
        inbox.post("pick_house", house, Listen.context(p, this));
        House chosen = houses.get(house);
        p.sendMessage(Component.text("You chose " + chosen.name() + ".", chosen.color()));
    }

    private void openMenu(Player p) {
        Menu m = new Menu();
        m.inv = Bukkit.createInventory(m, 9, Component.text("Pick your house"));
        int slot = houses.size() == 2 ? 2 : 0;
        for (House h : houses.values()) {
            ItemStack banner = new ItemStack(banner(h.color()));
            banner.editMeta(meta -> {
                meta.displayName(Component.text(h.name(), h.color()).decoration(TextDecoration.ITALIC, false)
                        .decorate(TextDecoration.BOLD));
                meta.lore(List.of(Component.text(h.motto(), NamedTextColor.GRAY).decoration(TextDecoration.ITALIC, false),
                        Component.text("Click to join", NamedTextColor.YELLOW).decoration(TextDecoration.ITALIC, false)));
            });
            m.inv.setItem(slot, banner);
            while (m.slots.size() <= slot) m.slots.add(null);
            m.slots.set(slot, h.id());
            slot += houses.size() == 2 ? 4 : 2;
        }
        p.openInventory(m.inv);
    }

    private static Material banner(TextColor c) {
        // the nearest of a few banner colours to the house colour
        int r = c.red(), g = c.green(), bl = c.blue();
        if (bl > r && bl > g) return Material.LIGHT_BLUE_BANNER;
        if (r > g && r > bl) return Material.RED_BANNER;
        if (g > r && g > bl) return Material.LIME_BANNER;
        return Material.WHITE_BANNER;
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Menu m)) return;
        e.setCancelled(true);
        int slot = e.getRawSlot();
        if (slot < 0 || slot >= m.slots.size() || m.slots.get(slot) == null) return;
        Player p = (Player) e.getWhoClicked();
        p.closeInventory();
        choose(p, m.slots.get(slot));
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        inbox.post("join", "", Listen.context(p, this));
        if (houseOf(p.getName()) == null)  // a moment after joining, so the client is ready for a menu
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (p.isOnline() && houseOf(p.getName()) == null) open(p);
            }, 60);
    }
}
