#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11+ is required. Install Python from your OS package manager, then rerun: bash scripts/bootstrap.sh" >&2
  exit 1
fi
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required; current version: " + sys.version.split()[0])
PY
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv --without-pip .venv || { echo "Could not create .venv. Install the matching Python venv package and retry." >&2; exit 1; }
fi
if [[ ! -f "${AGENT_HARNESS_HOME:-$HOME/.haness-9router}/config.env" ]]; then
  .venv/bin/python -m agent_harness configure
fi
"$ROOT/run.sh" doctor
