#!/usr/bin/env bash
# Clone the repository into a temporary directory, install it in a new virtual
# environment, and run the unit tests and verify_reproduction.py.
# REPO_URL may be a URL or a local path. Default: the repository this script is in.
# PYTHON may name the interpreter to use (default: python3).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_URL="${REPO_URL:-$HERE}"
PYTHON="${PYTHON:-python3}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "== clone: $REPO_URL"
git clone --quiet "$REPO_URL" "$WORK/repo"
cd "$WORK/repo"

echo "== venv + pip install -e ."
"$PYTHON" -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --quiet --upgrade pip
"$WORK/venv/bin/python" -m pip install --quiet -e .

echo "== unit tests"
"$WORK/venv/bin/python" -m unittest discover -s tests

echo "== verify_reproduction.py"
"$WORK/venv/bin/python" verify_reproduction.py > "$WORK/verify.log"
grep -E '"(python|tests_run|failures|errors|skipped|stored_result_matches|frontier_result_matches)"' "$WORK/verify.log"

echo "FRESH CLONE OK"
