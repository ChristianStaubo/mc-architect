package dev.mcarchitect.core;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.command.CommandSender;

/** The plugin's chat voice: green for done, yellow for problems, clickable buttons for answers. */
public final class Chat {
    private Chat() {}

    public static void say(CommandSender s, String text) {
        s.sendMessage(Component.text(text, NamedTextColor.GREEN));
    }

    public static void warn(CommandSender s, String text) {
        s.sendMessage(Component.text(text, NamedTextColor.YELLOW));
    }

    /** A clickable "[label]" that runs a command for whoever clicks it. */
    public static Component button(String label, String command, NamedTextColor color) {
        return Component.text("[" + label + "]", color).clickEvent(ClickEvent.runCommand(command));
    }
}
