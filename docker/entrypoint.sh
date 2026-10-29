#!/bin/sh
# Start Paper in /data (the mounted server/ folder: world, logs, Paper's configs).
# Paper's files live read-only in the image and are linked in; our settings win over Paper's.
set -eu

for f in paper.jar libraries versions cache; do ln -sfn "/opt/paper/$f" "/data/$f"; done
mkdir -p /data/plugins
rm -f /data/plugins/worldedit*.jar
ln -sfn /opt/paper/worldedit.jar /data/plugins/worldedit.jar
# Our bridge plugin, compiled by scripts/build-plugin.sh into plugin/build.
[ -f /plugin/mc-bridge.jar ] && ln -sfn /plugin/mc-bridge.jar /data/plugins/mc-bridge.jar

# The person running the server accepts the Minecraft EULA themselves (server/eula.txt).
if ! grep -qs '^eula=true' /data/eula.txt; then
  echo "Minecraft EULA not accepted: set eula=true in server/eula.txt (https://aka.ms/MinecraftEULA)" >&2
  exit 1
fi

# Merge config/server.properties (ours) over server.properties (Paper's full file).
touch /data/server.properties
awk -F= '
  FNR == NR { if ($0 !~ /^#/ && NF > 1) { k = $1; sub(/^[^=]*=/, ""); ours[k] = $0 }; next }
  { k = $1; if (k in ours) { print k "=" ours[k]; done[k] = 1 } else print }
  END { for (k in ours) if (!(k in done)) print k "=" ours[k] }
' /config/server.properties /data/server.properties > /tmp/server.properties
cp /tmp/server.properties /data/server.properties

exec java -Xms${MEMORY:-3G} -Xmx${MEMORY:-3G} \
  -XX:+AlwaysPreTouch -XX:+DisableExplicitGC -XX:+ParallelRefProcEnabled -XX:+PerfDisableSharedMem \
  -XX:+UnlockExperimentalVMOptions -XX:+UseG1GC -XX:G1HeapRegionSize=8M -XX:G1HeapWastePercent=5 \
  -XX:G1MaxNewSizePercent=40 -XX:G1MixedGCCountTarget=4 -XX:G1MixedGCLiveThresholdPercent=90 \
  -XX:G1NewSizePercent=30 -XX:G1RSetUpdatingPauseTimePercent=5 -XX:G1ReservePercent=20 \
  -XX:InitiatingHeapOccupancyPercent=15 -XX:MaxGCPauseMillis=200 -XX:MaxTenuringThreshold=1 \
  -XX:SurvivorRatio=32 \
  -jar paper.jar --nogui
