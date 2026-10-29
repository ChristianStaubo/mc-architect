# The Paper server image. Nothing is downloaded by this file except Mojang's server jar, which Paper's
# own launcher fetches from Mojang and checks against the hash built into paper.jar. Java, Paper and
# WorldEdit come from .tools/stage: `python3 scripts/deps.py stage linux-aarch64` (pinned, hash-checked).

# Debian stable, dated release 2026-10-20 (pushed 2026-10-21), pinned by digest: at least a week old.
FROM debian:stable-20261020-slim@sha256:a717a33469731894e77e912ea7d714e27c2dc38ee6554fd1a3102e92999cfc66

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mc

COPY .tools/stage/java.tar.gz /tmp/java.tar.gz
RUN mkdir /opt/java && tar -xzf /tmp/java.tar.gz -C /opt/java --strip-components=1 && rm /tmp/java.tar.gz
ENV PATH=/opt/java/bin:$PATH

# Unpack Paper once, at build time, so the container downloads nothing when it starts.
COPY .tools/stage/paper.jar .tools/stage/worldedit.jar .tools/stage/versions.txt /opt/paper/
RUN cd /opt/paper && java -Dpaperclip.patchonly=true -jar paper.jar && chown -R root:root /opt/paper

COPY docker/entrypoint.sh /opt/entrypoint.sh
USER mc
WORKDIR /data
EXPOSE 25565 8765
ENTRYPOINT ["/opt/entrypoint.sh"]
