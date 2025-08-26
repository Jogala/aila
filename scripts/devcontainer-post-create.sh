#!/usr/bin/env bash
set -euo pipefail
set -x

cd /workspace

echo "[post-create] Working dir: $(pwd)"
echo "[post-create] Which python3.12: $(command -v /usr/local/bin/python3.12 || true)"
echo "[post-create] Creating/reusing venv at .venv"
if [[ -x ./.venv/bin/python ]]; then
  PY=./.venv/bin/python
else
  set +e
  /usr/local/bin/python3.12 -m venv .venv
  VENV_STATUS=$?
  set -e
  if [[ $VENV_STATUS -ne 0 || ! -x ./.venv/bin/python ]]; then
    echo "[post-create] stdlib venv creation failed or incomplete (status=$VENV_STATUS). Falling back to virtualenv in-place..."
    /usr/local/bin/python3.12 -m pip install --user --upgrade virtualenv
    set +e
    /usr/local/bin/python3.12 -m virtualenv -p /usr/local/bin/python3.12 .venv
    VENV2_STATUS=$?
    set -e
    if [[ $VENV2_STATUS -ne 0 || ! -x ./.venv/bin/python ]]; then
      echo "[post-create] in-place virtualenv failed (status=$VENV2_STATUS). Falling back to HOME venv with symlink..."
      HOME_VENV="$HOME/.venvs/aila"
      mkdir -p "$HOME/.venvs"
      /usr/local/bin/python3.12 -m virtualenv -p /usr/local/bin/python3.12 "$HOME_VENV"
      # Replace .venv with symlink to home venv
      rm -rf .venv
      ln -s "$HOME_VENV" .venv
    fi
  fi
  PY=./.venv/bin/python
fi

ls -l .venv/bin || true

# Ensure versioned interpreter path exists to satisfy any shebangs or tools
if [[ -e ./.venv/bin/python && ! -e ./.venv/bin/python3.12 ]]; then
  ln -sf python ./.venv/bin/python3.12 || true
fi
ls -l .venv/bin || true

"$PY" -m pip install -U pip setuptools wheel
"$PY" -V

if command -v poetry >/dev/null 2>&1; then
  echo "[post-create] Poetry: $(poetry --version) at $(command -v poetry)"
  poetry export --with api -f requirements.txt --without-hashes -o /tmp/requirements.txt
  ls -l /tmp/requirements.txt
  "$PY" -m pip install -r /tmp/requirements.txt
else
  echo "Poetry not found; skipping dependency export/install"
fi

echo "postCreate completed using $PY"
