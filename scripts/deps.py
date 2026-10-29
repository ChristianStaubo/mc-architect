#!/usr/bin/env python3
"""Pinned, hash-checked dependencies: Java (Temurin), Paper, WorldEdit.

    python3 scripts/deps.py lock      # pick the newest release at least a week old, write deps.lock.json
    python3 scripts/deps.py install   # download what the lock names, verify every hash, put it in place
    python3 scripts/deps.py stage linux-aarch64   # verified files for the Docker build (.tools/stage)

Only official sources: Adoptium's API (Java), PaperMC's Fill API (Paper), Modrinth (WorldEdit, published
by the EngineHub maintainers). Nothing younger than `min_release_age_days` is ever locked, the same rule
as pnpm's minimumReleaseAge. Standard library only, so it runs before anything is installed.
"""

import datetime as dt
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "deps.lock.json"
TOOLS = ROOT / ".tools"
CACHE = TOOLS / "cache"
SERVER = ROOT / "server"
UA = {"User-Agent": "mc-architect-deps (personal project)"}

DEFAULTS = {"minecraft": "26.3", "java_feature": 25, "min_release_age_days": 7}
# Adoptium names for each platform we lock Java for (friends may be on any of them).
PLATFORMS = {
    "mac-aarch64": ("mac", "aarch64"),
    "mac-x64": ("mac", "x64"),
    "linux-x64": ("linux", "x64"),
    "linux-aarch64": ("linux", "aarch64"),
    "windows-x64": ("windows", "x64"),
}


def curl(url, out=None):
    """HTTPS through curl: it uses the OS trust store (python.org builds on macOS ship without one),
    and TLS verification always stays on."""
    cmd = ["curl", "-fsSL", "--proto", "=https", "--retry", "3", "-A", UA["User-Agent"], url]
    if out:
        cmd += ["-o", str(out)]
    return subprocess.run(cmd, check=True, capture_output=not out).stdout


def get_json(url):
    return json.loads(curl(url))


def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def lock():
    old = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    cfg = {k: old.get(k, v) for k, v in DEFAULTS.items()}
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=cfg["min_release_age_days"])
    old_enough = lambda t: parse_time(t) <= cutoff  # noqa: E731

    # Paper: newest STABLE build of our Minecraft version, at least a week old.
    builds = get_json(f"https://fill.papermc.io/v3/projects/paper/versions/{cfg['minecraft']}/builds")
    b = next(b for b in builds if b["channel"] == "STABLE" and old_enough(b["time"]))
    s = b["downloads"]["server:default"]
    paper = {"build": b["id"], "released": b["time"], "file": s["name"], "url": s["url"],
             "size": s["size"], "sha256": s["checksums"]["sha256"]}

    # WorldEdit: newest full release on Modrinth for Paper + our Minecraft version, at least a week old.
    q = urllib.parse.urlencode({"loaders": json.dumps(["paper"]),
                                "game_versions": json.dumps([cfg["minecraft"]])})
    versions = get_json(f"https://api.modrinth.com/v2/project/worldedit/version?{q}")
    v = next(v for v in versions if v["version_type"] == "release" and old_enough(v["date_published"]))
    f = next(f for f in v["files"] if f["primary"])
    worldedit = {"version": v["version_number"], "released": v["date_published"], "file": f["filename"],
                 "url": f["url"], "size": f["size"], "sha512": f["hashes"]["sha512"]}

    # Java: newest Temurin GA of the feature release Paper needs, per platform, at least a week old.
    java = {}
    for name, (os_, arch) in PLATFORMS.items():
        q = urllib.parse.urlencode({"architecture": arch, "os": os_, "image_type": "jdk",
                                    "page_size": 10, "sort_order": "DESC"})
        rels = get_json(f"https://api.adoptium.net/v3/assets/feature_releases/{cfg['java_feature']}/ga?{q}")
        r = next(r for r in rels if old_enough(r["timestamp"]))
        p = r["binaries"][0]["package"]
        java[name] = {"release": r["release_name"], "released": r["timestamp"], "file": p["name"],
                      "url": p["link"], "size": p["size"], "sha256": p["checksum"]}

    out = {**cfg, "locked_at": now.isoformat(timespec="seconds"), "paper": paper,
           "worldedit": worldedit, "java": java}
    LOCK.write_text(json.dumps(out, indent=2) + "\n")
    print(f"locked (cutoff {cutoff:%Y-%m-%d}): Paper {cfg['minecraft']} build {paper['build']} "
          f"({paper['released'][:10]}), WorldEdit {worldedit['version']} ({worldedit['released'][:10]}), "
          f"Java {java['mac-aarch64']['release']} ({java['mac-aarch64']['released'][:10]})")


def this_platform():
    os_ = {"Darwin": "mac", "Linux": "linux", "Windows": "windows"}[platform.system()]
    arch = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x64", "AMD64": "x64"}[platform.machine()]
    return f"{os_}-{arch}"


def fetch(dep, algo):
    """Download into the cache (or reuse it) and refuse anything whose hash differs from the lock."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / dep["file"]
    if not (path.exists() and digest(path, algo) == dep[algo]):
        print(f"  downloading {dep['file']} ({dep['size'] / 1e6:.0f} MB)")
        tmp = path.with_suffix(path.suffix + ".part")
        curl(dep["url"], out=tmp)
        got = digest(tmp, algo)
        if got != dep[algo]:
            tmp.unlink()
            sys.exit(f"HASH MISMATCH for {dep['file']}: expected {dep[algo][:16]}…, got {got[:16]}…. Nothing installed.")
        tmp.rename(path)
    print(f"  ok  {dep['file']}  {algo} {dep[algo][:16]}…  released {dep['released'][:10]}")
    return path


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def install():
    lk = json.loads(LOCK.read_text())
    plat = this_platform()

    print(f"Java {lk['java'][plat]['release']} ({plat})")
    archive = fetch(lk["java"][plat], "sha256")
    dest = TOOLS / "java"
    marker = dest / ".release"
    if not (marker.exists() and marker.read_text() == lk["java"][plat]["release"]):
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(dest)
        else:
            with tarfile.open(archive) as t:
                t.extractall(dest, filter="data")  # refuses links and paths outside dest
        marker.write_text(lk["java"][plat]["release"])

    print(f"Paper {lk['minecraft']} build {lk['paper']['build']}")
    SERVER.mkdir(exist_ok=True)
    shutil.copyfile(fetch(lk["paper"], "sha256"), SERVER / "paper.jar")

    print(f"WorldEdit {lk['worldedit']['version']}")
    plugins = SERVER / "plugins"
    plugins.mkdir(exist_ok=True)
    for stale in plugins.glob("worldedit-*.jar"):
        stale.unlink()
    shutil.copyfile(fetch(lk["worldedit"], "sha512"), plugins / lk["worldedit"]["file"])
    print(f"installed. java: {java_bin()}")


def stage(plat):
    """Verified copies for the Docker build (docker/Dockerfile COPYs .tools/stage; no downloads in the image)."""
    lk = json.loads(LOCK.read_text())
    out = TOOLS / "stage"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    print(f"staging for {plat}")
    shutil.copyfile(fetch(lk["java"][plat], "sha256"), out / "java.tar.gz")
    shutil.copyfile(fetch(lk["paper"], "sha256"), out / "paper.jar")
    shutil.copyfile(fetch(lk["worldedit"], "sha512"), out / "worldedit.jar")
    (out / "versions.txt").write_text(
        f"java {lk['java'][plat]['release']}\npaper {lk['minecraft']}-{lk['paper']['build']}\n"
        f"worldedit {lk['worldedit']['version']}\n")


def java_bin():
    hits = sorted((TOOLS / "java").glob("*/Contents/Home/bin/java")) or sorted((TOOLS / "java").glob("*/bin/java*"))
    return hits[0] if hits else None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "lock":
        lock()
    elif cmd == "install":
        install()
    elif cmd == "stage":
        stage(sys.argv[2] if len(sys.argv) > 2 else "linux-aarch64")
    elif cmd == "java":
        print(java_bin() or "")
    else:
        sys.exit(__doc__)
