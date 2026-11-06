package dev.mcarchitect.ghost;

import com.google.gson.JsonObject;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.World;
import org.bukkit.entity.Mannequin;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.LeatherArmorMeta;
import org.bukkit.plugin.Plugin;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.Team;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Map;

import static dev.mcarchitect.core.Json.map;
import static dev.mcarchitect.core.Json.str;

/**
 * The ghosts' bodies: a mannequin per house, in house-coloured leather, glowing in the house colour, with
 * a faint trail. It floats (no gravity, no pathfinding, through walls), gliding a little each tick toward
 * its target: a spot, or a player it follows. Everyone sees it. Not saved with the world: ghost-core
 * spawns them again after a restart.
 */
final class Bodies {
    private static final double SPEED = 0.35;         // blocks per tick
    private static final double FOLLOW_SIDE = 3.0;    // off to the player's side, a little ahead: in view, not in the way
    private static final double FOLLOW_AHEAD = 1.5;
    private static final double FOLLOW_SLACK = 6.0;   // closer than this, it just hovers and watches

    private static final class Body {
        Mannequin entity;
        Location target;      // a fixed spot, or null
        String follow;        // a player name, or null
        String lookAt;        // a player name to face when idle
        Location last;        // where it was: a body whose chunk unloaded comes back here
        long ticks;
    }

    private final Houses houses;
    private final Map<String, Body> bodies = new HashMap<>();   // by ghost (house id or "spirit")

    Bodies(Plugin plugin, Houses houses) {
        this.houses = houses;
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 1, 1);
    }

    /** body: ghost, action spawn|go_to|follow|stop|look_at|despawn, pos [x,y,z], player, world. */
    Object act(JsonObject b) {
        String ghost = str(b, "ghost");
        String action = str(b, "action");
        Body body = bodies.get(ghost);
        if (action.equals("despawn")) {
            if (body != null && body.entity != null) body.entity.remove();
            bodies.remove(ghost);
            return map("ghost", ghost, "despawned", body != null);
        }
        if (body == null || body.entity == null || !body.entity.isValid()) {
            // gone (its chunk unloaded when nobody was near) or never made: back where it was, or at the spot asked
            Location at = body != null && body.last != null && !action.equals("spawn") ? body.last : spot(b);
            if (at == null && body != null) at = body.last;
            if (at == null) throw new IllegalArgumentException("no body for " + ghost + " yet: spawn it with a pos or a player");
            if (body == null) body = new Body();
            body.entity = spawn(ghost, at);
            body.last = at;
            bodies.put(ghost, body);
        }
        switch (action) {
            case "spawn" -> {}
            case "go_to" -> {
                body.follow = null;
                body.target = spot(b);
            }
            case "follow" -> {
                body.follow = str(b, "player");
                body.target = null;
            }
            case "stop" -> {
                body.follow = null;
                body.target = null;
            }
            case "look_at" -> body.lookAt = str(b, "player");
            default -> throw new IllegalArgumentException("unknown action " + action);
        }
        return describeOne(ghost, body);
    }

    Object describe() {
        Map<String, Object> out = new HashMap<>();
        bodies.forEach((g, b) -> out.put(g, describeOne(g, b)));
        return map("bodies", out);
    }

    private Map<String, Object> describeOne(String ghost, Body b) {
        Location l = b.entity != null && b.entity.isValid() ? b.entity.getLocation() : b.last;
        return map("ghost", ghost, "pos", new double[]{round(l.getX()), round(l.getY()), round(l.getZ())},
                "world", l.getWorld().getName(), "follow", b.follow, "moving", b.target != null || b.follow != null,
                "here", b.entity != null && b.entity.isValid());
    }

    /** Is any ghost's body within `r` blocks of this player? (Chat near a ghost is a candidate.) */
    String near(Player p, double r) {
        for (var e : bodies.entrySet()) {
            Mannequin m = e.getValue().entity;
            if (m != null && m.isValid() && m.getWorld().equals(p.getWorld()) && m.getLocation().distance(p.getLocation()) <= r)
                return e.getKey();
        }
        return null;
    }

    void stop(String ghost) {
        Body b = bodies.get(ghost);
        if (b != null) {
            b.follow = null;
            b.target = null;
        }
    }

    void removeAll() {
        bodies.values().forEach(b -> {
            if (b.entity != null) b.entity.remove();
        });
        bodies.clear();
    }

    private Location spot(JsonObject b) {
        if (b.has("pos")) {
            var a = b.getAsJsonArray("pos");
            World w = Bukkit.getWorld(str(b, "world", "world"));
            return new Location(w, a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble());
        }
        if (b.has("player")) {
            Player p = Bukkit.getPlayerExact(str(b, "player"));
            if (p != null) return p.getLocation().add(p.getLocation().getDirection().setY(0).normalize().multiply(2)).add(0, 0.5, 0);
        }
        return null;
    }

    private Mannequin spawn(String ghost, Location at) {
        Houses.House h = houses.get(ghost);
        String name = h == null ? "The spirit" : h.name() + " ghost";
        Color c = h == null ? Color.WHITE : Color.fromRGB(h.color().value());
        return at.getWorld().spawn(at, Mannequin.class, m -> {
            m.customName(Component.text(name, h == null ? NamedTextColor.WHITE : h.color()));
            m.setCustomNameVisible(true);
            m.setDescription(Component.text("say: ghost, ...", NamedTextColor.GRAY));  // not "NPC"
            m.setGravity(false);
            m.setInvulnerable(true);
            m.setSilent(true);
            m.setPersistent(false);
            m.setImmovable(true);
            m.setGlowing(true);
            m.setCollidable(false);
            m.addScoreboardTag("mcarchitect_ghost");
            m.getEquipment().setHelmet(dyed(Material.LEATHER_HELMET, c));
            m.getEquipment().setChestplate(dyed(Material.LEATHER_CHESTPLATE, c));
            m.getEquipment().setLeggings(dyed(Material.LEATHER_LEGGINGS, c));
            m.getEquipment().setBoots(dyed(Material.LEATHER_BOOTS, c));
            team(ghost, h).addEntity(m);
        });
    }

    private static ItemStack dyed(Material m, Color c) {
        ItemStack it = new ItemStack(m);
        it.editMeta(LeatherArmorMeta.class, meta -> meta.setColor(c));
        return it;
    }

    /** The glow takes its colour from a scoreboard team. */
    private Team team(String ghost, Houses.House h) {
        Scoreboard sb = Bukkit.getScoreboardManager().getMainScoreboard();
        String name = "ghost_" + ghost;
        Team t = sb.getTeam(name);
        if (t == null) t = sb.registerNewTeam(name);
        NamedTextColor nc = h == null ? NamedTextColor.WHITE
                : NamedTextColor.nearestTo(h.color());
        t.color(nc);
        t.setOption(Team.Option.COLLISION_RULE, Team.OptionStatus.NEVER);
        return t;
    }

    private void tick() {
        for (var e : bodies.entrySet()) {
            Body b = e.getValue();
            Mannequin m = b.entity;
            if ((m == null || !m.isValid()) && b.last != null
                    && b.last.getWorld().isChunkLoaded(b.last.getBlockX() >> 4, b.last.getBlockZ() >> 4)) {
                b.entity = m = spawn(e.getKey(), b.last);   // its chunk is back (someone came near): so is it
            }
            if (m == null || !m.isValid()) continue;
            b.ticks++;
            b.last = m.getLocation();
            Location goal = b.target;
            Player face = null;
            if (b.follow != null) {
                Player p = Bukkit.getPlayerExact(b.follow);
                if (p != null && p.getWorld().equals(m.getWorld())) {
                    face = p;
                    if (m.getLocation().distance(p.getLocation()) > FOLLOW_SLACK) {
                        Vector fwd = p.getLocation().getDirection().setY(0);
                        if (fwd.lengthSquared() < 1e-6) fwd = new Vector(0, 0, 1);
                        fwd.normalize();
                        Vector side = new Vector(-fwd.getZ(), 0, fwd.getX());  // the player's right
                        goal = p.getLocation().add(side.multiply(FOLLOW_SIDE)).add(fwd.multiply(FOLLOW_AHEAD)).add(0, 0.8, 0);
                    }
                }
            } else if (b.lookAt != null) {
                face = Bukkit.getPlayerExact(b.lookAt);
            }
            Location now = m.getLocation();
            Location next = now.clone();
            if (goal != null && goal.getWorld().equals(now.getWorld())) {
                Vector d = goal.toVector().subtract(now.toVector());
                double dist = d.length();
                if (dist > 60) next = goal.clone();                          // too far: appear there
                else if (dist > 0.1) next.add(d.normalize().multiply(Math.min(SPEED, dist)));
                else if (b.follow == null) b.target = null;                  // arrived
            }
            next.add(0, Math.sin(b.ticks / 12.0) * 0.01, 0);                 // a slow bob
            Location lookFrom = next.clone().add(0, 1.6, 0);
            Location toward = face != null ? face.getEyeLocation() : goal;
            if (toward != null && toward.getWorld().equals(next.getWorld())) {
                Vector dir = toward.toVector().subtract(lookFrom.toVector());
                if (dir.lengthSquared() > 1e-6) next.setDirection(dir);
            } else {
                next.setYaw(now.getYaw());
                next.setPitch(now.getPitch());
            }
            m.teleport(next);
            if (b.ticks % 10 == 0)  // a faint glow drifting off it
                m.getWorld().spawnParticle(Particle.GLOW, next.clone().add(0, 1.0, 0), 1, 0.3, 0.5, 0.3, 0);
        }
    }

    private static double round(double v) {
        return Math.round(v * 10) / 10.0;
    }

}
