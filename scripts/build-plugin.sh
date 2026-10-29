#!/usr/bin/env bash
# Compile the bridge plugin inside the server image, against the exact Paper and WorldEdit jars it runs
# with: no Gradle, no Maven, nothing downloaded. Output: plugin/build/mc-bridge.jar
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/plugin/build"
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$ROOT/plugin:/src" --entrypoint sh mc-architect-server:local -c '
    set -e
    cd /opt/paper
    CP=$(find libraries versions -name "*.jar" | sed "s#^#/opt/paper/#" | tr "\n" ":")/opt/paper/worldedit.jar
    rm -rf /tmp/classes && mkdir -p /tmp/classes
    javac --release 25 -Xlint:-options -cp "$CP" -d /tmp/classes $(find /src/src -name "*.java")
    cp /src/resources/plugin.yml /tmp/classes/
    jar --create --file /src/build/mc-bridge.jar -C /tmp/classes .
  '
echo "built plugin/build/mc-bridge.jar"
