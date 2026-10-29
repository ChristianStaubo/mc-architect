"""The in-game architect's daemon (docs/in-game-architect.md): it reads /arc events from the plugin's
inbox, answers yes / no / undo / cancel / status itself, and hands requests to a Claude agent that
designs, previews and talks to the player through the mc tools."""
