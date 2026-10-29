# Hosting plan

How we take the server from this laptop to somewhere friends can join any time (roadmap goal 4).
Researched 2026-10-29; prices are from that day and need checking at checkout.

## The shape
One small Linux VPS running two containers from our own image (the one we already build from pinned,
hash-checked files):

| | live | staging |
|---|---|---|
| who | friends, survival | the agent and us |
| game port | 25565, public | none (Tailscale only) |
| bridge | off, or Tailscale only | on, Tailscale only |
| heap | ~4.5 GB | ~2 GB |
| world | the real one | a copy, refreshed from the newest live backup every week |

The agent builds on staging. An approved build goes to live by reading its box from the staging bridge
(`/region`) and placing it on live (`/place`): the same calls we use today, with an undo snapshot on
live. Nothing the agent tries ever lands on live unasked.

## Where
Minecraft's game loop runs on one thread, so per-core speed matters more than core count; Paper's
guidance is a heap set once (Xms = Xmx) with ~1-1.5 GB left for the OS. For 3-8 players plus staging,
8 GB of RAM.

| Option | Cost/month | Fit |
|---|---|---|
| **OVH VPS-2** (4 vCore, 8 GB, 75 GB NVMe, anti-DDoS, unlimited traffic) | from ~$8.50 | **First choice.** Root, our Docker image, Tailscale. Check the CPU model and any commitment term at checkout. |
| Hetzner CX33 (4 vCPU, 8 GB) | €8.99 + ~€0.50 IPv4 | Same fit, but cloud instances have been out of stock since June 2026. |
| DigitalOcean / Akamai 8 GB | ~$48 | Works, five times the price. |
| Oracle Always Free (ARM, now 2 OCPU / 12 GB) | $0 | Needs an arm64 image; idle instances can be reclaimed. Fine to experiment, not for an always-on server. |
| Managed Minecraft hosts (Apex, Shockbyte, Bisect...) | ~$10-15 | **No:** no Docker and no private network, so the bridge would have to be public. |
| A spare PC at home + Tailscale (+ playit.gg for the public port) | power | Good if there's an x86 PC to spare; uptime depends on home power and internet. A Raspberry Pi is too slow per core. |

## Backups
- **restic** to cheap object storage: Backblaze B2 (first 10 GB free, then $6.95/TB) or Cloudflare R2
  (10 GB free, no egress fees). A deduplicated world repo of a few GB costs cents a month.
- Around each snapshot: `save-off`, `save-all flush`, snapshot, `save-on`, through the bridge we already
  have (no RCON port). Hourly while people are on, nightly otherwise; keep 24 hourly, 7 daily, 4 weekly,
  6 monthly.
- Always a snapshot before a Paper/WorldEdit upgrade and before promoting a build to live.
- **Restore drill**: the weekly staging refresh *is* a restore of the newest live backup, so backups
  get tested every week without extra work.
- restic is a single static binary from its GitHub releases: pinned and hash-checked like everything
  else in `deps.lock.json`, under the 7-day rule.

## Security
- `online-mode=true`, `white-list=true`, `enforce-whitelist=true`; friends added by name.
- Firewall (the provider's plus nftables/ufw): only 25565/tcp open to the internet. SSH over Tailscale
  only (or keys only).
- Docker bypasses ufw for published ports: publish the bridge on `127.0.0.1` or the Tailscale address,
  never `0.0.0.0`. (Our compose file already binds to 127.0.0.1.)
- Tailscale (free plan: 6 users, unlimited devices) for the bridge and staging: no open ports, and the
  agent's machine reaches the bridge directly. The bearer token stays as a second lock.
- DDoS: OVH includes protection; a proxy like TCPShield isn't worth it for a whitelisted friends server.
- Debian `unattended-upgrades` with an automatic reboot window; our image stays non-root with
  `cap_drop: ALL` and `no-new-privileges`.

## Running it
- **Monitoring**: an external ping of the game port (e.g. a free uptime checker) and a heartbeat after
  every successful backup, so a missed backup alerts us; disk at 80% alerts.
- **Updates**: bump Paper/WorldEdit in `deps.lock.json` (7-day rule), build the image, run it on
  staging, run `mc eval gate` against staging, snapshot live, switch live to the new image digest. Keep
  the previous digest to roll back. World upgrades are one-way: never skip the snapshot.
- **Logs**: Docker `json-file` with `max-size`/`max-file`; Paper rotates its own logs.

## What we need to build
1. `compose.prod.yaml`: live + staging services, heaps, ports as above, restart policies, log limits.
2. `mc` pointing at a named server (`MC_SERVER=staging|live`, each with its bridge URL and token).
3. `scripts/backup.sh` (restic via the bridge's save-off/save-on) + a systemd timer, and
   `scripts/restore.sh` (also the weekly staging refresh).
4. `mc promote EDIT`: copy an approved build's box from staging to live, with a live snapshot first.
5. A server setup script or checklist (user, Docker, Tailscale, firewall, unattended-upgrades).
6. Whitelist management (`mc whitelist add NAME`, or by hand in the console).
7. A restore drill and a rollback drill once, before friends rely on it.

## Decisions for the owner
- Where: OVH VPS-2 (recommended), Hetzner when it's back in stock, or a spare PC at home.
- Backup storage: B2 or R2 (both effectively free at our size).
- Who's on the whitelist.
- Account sign-ups and payment are the owner's to do; we build and test everything else locally first.

Sources: [Paper: Aikar's flags](https://docs.papermc.io/paper/aikars-flags),
[OVH VPS](https://www.ovhcloud.com/en/vps/), [Hetzner cloud](https://www.hetzner.com/cloud/cost-optimized/),
[Hetzner status](https://status.hetzner.com/), [DigitalOcean](https://www.digitalocean.com/pricing/droplets),
[Oracle free tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm),
[Shockbyte custom jars](https://shockbyte.com/help/knowledgebase/articles/how-to-install-a-custom-jar-custom-server-type),
[docker-mc-backup](https://github.com/itzg/docker-mc-backup), [Backblaze B2](https://www.backblaze.com/cloud-storage/pricing),
[Cloudflare R2](https://developers.cloudflare.com/r2/pricing/), [Tailscale pricing](https://tailscale.com/pricing),
[TCPShield plans](https://tcpshield.com/plans), [playit.gg](https://playit.gg/).
