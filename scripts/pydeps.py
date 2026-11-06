#!/usr/bin/env python3
"""The ghost's Python dependencies, pinned and hash-checked like the rest of the kit.

    python3 scripts/pydeps.py lock      # write ghost/requirements.lock (exact versions + every file hash)
    python3 scripts/pydeps.py install   # make .venv and install the lock with --require-hashes --no-deps

PINS names every package, transitive ones included, at an exact version. `lock` refuses a version
uploaded less than `min_release_age_days` ago (deps.lock.json's rule) and records the hash of every file
PyPI has for it; pip then installs nothing that isn't listed (--no-deps) and nothing whose hash differs.
Standard library only.
"""

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "ghost" / "requirements.lock"
VENV = ROOT / ".venv"
MIN_AGE = json.loads((ROOT / "deps.lock.json").read_text())["min_release_age_days"]

PINS = {
    "temporalio": "1.35.0",          # durable workflows (docs/ghost/design.md)
    "nexus-rpc": "1.4.0",            # temporalio requires exactly this
    "protobuf": "7.36.2",
    "types-protobuf": "7.35.1.20260906",
    "typing-extensions": "4.16.0",
    "psycopg": "3.3.6",              # Postgres
    "psycopg-binary": "3.3.6",
    "cedarpy": "4.12.2",             # Cedar policies
}


def pypi(name, version):
    out = subprocess.run(["curl", "-fsSL", "--proto", "=https", f"https://pypi.org/pypi/{name}/{version}/json"],
                         capture_output=True, check=True).stdout
    return json.loads(out)


def lock():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MIN_AGE)
    lines = [f"# Written by scripts/pydeps.py lock on {dt.date.today()}; every version at least {MIN_AGE} days old.",
             "# Install with: python3 scripts/pydeps.py install"]
    for name, version in PINS.items():
        files = pypi(name, version)["urls"]
        first = min(dt.datetime.fromisoformat(f["upload_time_iso_8601"].replace("Z", "+00:00")) for f in files)
        if first > cutoff:
            sys.exit(f"{name} {version} was uploaded {first:%Y-%m-%d}: younger than {MIN_AGE} days")
        if any(f.get("yanked") for f in files):
            sys.exit(f"{name} {version} is yanked")
        hashes = " ".join(f"--hash=sha256:{f['digests']['sha256']}" for f in files)
        lines.append(f"{name}=={version} {hashes}")
        print(f"{name} {version} (uploaded {first:%Y-%m-%d}, {len(files)} files)")
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text("\n".join(lines) + "\n")
    print(f"wrote {LOCK.relative_to(ROOT)}")


def install():
    if not VENV.exists():
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    pip = VENV / "bin" / "pip"
    subprocess.run([str(pip), "install", "--require-hashes", "--no-deps", "--only-binary", ":all:",
                    "-r", str(LOCK)], check=True)
    subprocess.run([str(pip), "check"], check=True)


if __name__ == "__main__":
    {"lock": lock, "install": install}[sys.argv[1] if len(sys.argv) > 1 else "lock"]()
