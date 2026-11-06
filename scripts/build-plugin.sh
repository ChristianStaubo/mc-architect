#!/usr/bin/env bash
# Compile the bridge plugin inside the server image, against the exact Paper and WorldEdit jars it runs
# with: no Gradle, no Maven, nothing downloaded. Output: plugin/build/mc-bridge.jar, and the optional
# ghost plugin (ghost-plugin/, compiled against the bridge) as plugin/build/ghost.jar.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/plugin/build"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$ROOT/plugin:/src" -v "$ROOT/ghost-plugin:/ghost:ro" --entrypoint sh mc-architect-server:local -c '
    set -e
    cd /opt/paper
    CP=$(find libraries versions -name "*.jar" | sed "s#^#/opt/paper/#" | tr "\n" ":")/opt/paper/worldedit.jar
    rm -rf /tmp/classes && mkdir -p /tmp/classes
    javac --release 25 -Xlint:-options -cp "$CP" -d /tmp/classes $(find /src/src -name "*.java")
    cp /src/resources/plugin.yml /tmp/classes/
    jar --create --file /src/build/mc-bridge.jar -C /tmp/classes .
    rm -rf /tmp/ghost && mkdir -p /tmp/ghost
    javac --release 25 -Xlint:-options -cp "$CP:/tmp/classes" -d /tmp/ghost $(find /ghost/src -name "*.java")
    cp /ghost/resources/plugin.yml /tmp/ghost/
    jar --create --file /src/build/ghost.jar -C /tmp/ghost .
  '
echo "built plugin/build/mc-bridge.jar and plugin/build/ghost.jar"
