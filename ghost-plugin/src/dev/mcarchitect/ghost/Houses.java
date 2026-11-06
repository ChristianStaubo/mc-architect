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
    record House(String id, String name, TextColor color, String motto, List<int[]> zones) {}

    private final Plugin plugin;
    private final Inbox inbox;
    private final Map<String, House> houses = new java.util.LinkedHashMap<>();
    private final Map<String, String> members = new HashMap<>();   // player (lower case) -> house id
    private final Map<String, String> roles = new HashMap<>();

    Houses(Plugin plugin, Inbox inbox) {
        this.plugin = plugin;
        this.inbox = inbox;
    }

    /** body: houses [{id, name, color, motto, zones: [[x0, z0, x1, z1]]}], members {player: {house, role}}. */
    Object set(JsonObject b) {
        if (b.has("houses")) {
            houses.clear();
            for (JsonElement e : b.getAsJsonArray("houses")) {
                JsonObject h = e.getAsJsonObject();
                List<int[]> zs = new ArrayList<>();
                for (JsonElement z : h.getAsJsonArray("zones")) {
                    var a = z.getAsJsonArray();
                    zs.add(new int[]{a.get(0).getAsInt(), a.get(1).getAsInt(), a.get(2).getAsInt(), a.get(3).getAsInt()});
                }
                houses.put(str(h, "id"), new House(str(h, "id"), str(h, "name"), TextColor.fromHexString(str(h, "color")),
                        str(h, "motto", ""), zs));
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

    Iterable<House> all() {
        return houses.values();
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

    void open(Player p) {
        if (houses.isEmpty()) return;
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

    Object openFor(JsonObject b) {
        Player p = Bukkit.getPlayerExact(str(b, "player"));
        if (p != null) open(p);
        return map("opened", p != null);
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
        String house = m.slots.get(slot);
        p.closeInventory();
        inbox.post("pick_house", house, Listen.context(p, this));
        House chosen = houses.get(house);
        p.sendMessage(Component.text("You chose " + chosen.name() + ".", chosen.color()));
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
