#!/usr/bin/env bash
# Installs a warn-only pre-push hook: the regression gate's offline half (unit tests, every part and
# example plan audited) runs before each push and warns on failures without blocking (docs/evals.md §11).
# The full gate (`./mc.py eval gate`) also places and undoes on the test server: run it yourself before
# pushing placement, bridge or redstone changes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cat > "$ROOT/.git/hooks/pre-push" <<'HOOK'
#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)"
if ! out=$(python3 mc.py eval gate --offline 2>&1); then
  echo "$out" | grep -E "FAIL|passed" >&2
  echo "warning: regression gate (offline) has failures; pushing anyway (warn-only, docs/evals.md §14)" >&2
fi
exit 0
HOOK
chmod +x "$ROOT/.git/hooks/pre-push"
echo "installed .git/hooks/pre-push (warn-only, offline regression gate)"
