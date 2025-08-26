#!/usr/bin/env bash
set -Eeuo pipefail

section() { echo; echo "=== $* ==="; }

section "Environment info"
echo "User: $(id -u -n) (uid=$(id -u))"
echo "PWD:  $(pwd)"
echo "PATH: $PATH"

section "Locale"
echo "LANG=$LANG LC_ALL=$LC_ALL LANGUAGE=${LANGUAGE:-}"
if locale -a | grep -qi '^en_US\.utf8$'; then
  echo "en_US.utf8 locale available"
else
  echo "WARN: en_US.utf8 not listed by locale -a"
fi

section "Python / venv"
if [[ ! -x .venv/bin/python ]]; then
  echo "ERROR: .venv/bin/python not found or not executable"
  exit 1
fi
PY=./.venv/bin/python
echo "Using PY=$PY"
$PY -V
$PY - <<'PY'
import sys, platform
print('Executable:', sys.executable)
print('Version   :', platform.python_version())
print('Prefix    :', sys.prefix)
PY

section "Required packages present"
$PY - <<'PY'
import importlib.util, sys
mods = ["fastapi", "uvicorn", "pydantic"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("Missing:", missing)
    sys.exit(1)
print("OK:", mods)
PY

section "Poetry export"
if command -v poetry >/dev/null 2>&1; then
  poetry --version
  poetry export --with api -f requirements.txt --without-hashes -o /tmp/smoke-req.txt
  test -s /tmp/smoke-req.txt && echo "Export OK: /tmp/smoke-req.txt (size $(wc -c </tmp/smoke-req.txt) bytes)"
else
  echo "WARN: poetry not found; skipping export check"
fi

section "Claude CLI"
if command -v claude >/dev/null 2>&1; then
  echo "claude: $(claude --version)"
else
  echo "ERROR: claude CLI not found"
  exit 1
fi

section "API /health"
set +e
$PY -m uvicorn aila.api.main:app --host 127.0.0.1 --port 8000 --log-level warning &
S_PID=$!
cleanup() { kill "$S_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

ok=0
for i in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/health.json 2>/dev/null; then
    ok=1; break
  fi
  sleep 0.5
done
cleanup
trap - EXIT
set -e

if [[ "$ok" -ne 1 ]]; then
  echo "ERROR: /health did not respond"
  exit 1
fi
echo "Health OK: $(cat /tmp/health.json)"

echo
echo "All smoke checks passed."

