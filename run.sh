#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Runtime is not installed. Run: bash \"$ROOT/scripts/bootstrap.sh\"" >&2
  exit 1
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$ROOT/.venv/bin/python" -m agent_harness "$@"
