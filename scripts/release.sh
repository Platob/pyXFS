#!/usr/bin/env bash
set -euo pipefail

# pyxfs release helper (Linux/macOS bash)
# - Bumps version (pyproject.toml + src/pyxfs/__init__.py)
# - Commits, tags, pushes
# - Builds distributions
# - Optionally uploads to PyPI or TestPyPI via twine
#
# Usage:
#   scripts/release.sh 1.2.3 [--upload pypi|testpypi] [--no-push]
#   scripts/release.sh --bump patch|minor|major [--upload pypi|testpypi] [--no-push]
#
# Examples:
#   scripts/release.sh 0.1.1 --upload testpypi
#   scripts/release.sh --bump patch --upload pypi
#
# Requirements:
#   - git clean working tree (or commit/stash yourself)
#   - Python, pip, build, twine (the script installs build/twine if needed)
#   - For uploads: PyPI/TestPyPI credentials (username: __token__, password: API token)
#   - Run from project root

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYPROJECT="pyproject.toml"
INIT_FILE="src/pyxfs/__init__.py"

if [[ ! -f "$PYPROJECT" ]] || [[ ! -f "$INIT_FILE" ]]; then
  echo "❌ Missing $PYPROJECT or $INIT_FILE. Run from the project root." >&2
  exit 1
fi

# --- parse args ---
NEW_VERSION=""
BUMP_KIND=""
UPLOAD_TARGET=""
PUSH=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bump)
      BUMP_KIND="${2:-}"; shift 2 ;;
    --upload)
      UPLOAD_TARGET="${2:-}"; shift 2 ;;
    --no-push)
      PUSH=0; shift ;;
    -*)
      echo "Unknown option: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$NEW_VERSION" ]]; then
        NEW_VERSION="$1"; shift
      else
        echo "Unexpected arg: $1" >&2; exit 2
      fi
      ;;
  esac
done

if [[ -z "$NEW_VERSION" && -z "$BUMP_KIND" ]]; then
  cat <<EOF
Usage:
  scripts/release.sh <version> [--upload pypi|testpypi] [--no-push]
  scripts/release.sh --bump patch|minor|major [--upload pypi|testpypi] [--no-push]
EOF
  exit 2
fi

if [[ -n "$UPLOAD_TARGET" && "$UPLOAD_TARGET" != "pypi" && "$UPLOAD_TARGET" != "testpypi" ]]; then
  echo "❌ --upload must be 'pypi' or 'testpypi'." >&2
  exit 2
fi

# --- ensure clean git state ---
if [[ -n "$(git status --porcelain)" ]]; then
  echo "❌ Working tree not clean. Commit or stash your changes first." >&2
  exit 1
fi

# --- read current version from pyproject ---
CURRENT_VERSION="$(python - <<'PY'
import re, sys
t=open("pyproject.toml","r",encoding="utf-8").read()
m=re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"\s*$', t)
print(m.group(1) if m else "", end="")
PY
)"
if [[ -z "$CURRENT_VERSION" ]]; then
  echo "❌ Could not read current version from pyproject.toml" >&2
  exit 1
fi

# --- compute new version if bump requested ---
if [[ -n "$BUMP_KIND" ]]; then
  NEW_VERSION="$(python - "$CURRENT_VERSION" "$BUMP_KIND" <<'PY'
import sys
cur=sys.argv[1]
kind=sys.argv[2]
def bump(v,k):
    import re
    m=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(.*)?', v)
    if not m: raise SystemExit(f"Unrecognized version: {v}")
    major, minor, patch, rest = m.groups()
    major, minor, patch = int(major), int(minor), int(patch)
    if k=="patch": patch+=1
    elif k=="minor": minor, patch = minor+1, 0
    elif k=="major": major, minor, patch = major+1, 0, 0
    else: raise SystemExit(f"Unknown bump: {k}")
    return f"{major}.{minor}.{patch}"
print(bump(cur, kind), end="")
PY
)"
fi

echo "Current version : $CURRENT_VERSION"
echo "New version     : $NEW_VERSION"

# --- update files using Python (portable across GNU/BSD) ---
python - "$NEW_VERSION" <<'PY'
import re, sys, io
new = sys.argv[1]

def sub_file(path, pattern, repl):
    s = io.open(path, "r", encoding="utf-8").read()
    s2, n = re.subn(pattern, repl, s, count=1, flags=re.M)
    if n == 0:
        raise SystemExit(f"Failed to update version in {path}")
    io.open(path, "w", encoding="utf-8").write(s2)

sub_file("pyproject.toml",
         r'(?m)^\s*version\s*=\s*"\d+\.\d+\.\d+(?:[-\w\.]+)?"\s*$',
         f'version = "{new}"')
sub_file("src/pyxfs/__init__.py",
         r'(?m)^__version__\s*=\s*"\d+\.\d+\.\d+(?:[-\w\.]+)?"\s*$',
         f'__version__ = "{new}"')
PY

# --- commit & tag ---
git add "$PYPROJECT" "$INIT_FILE"
git commit -m "chore: release ${NEW_VERSION}"
git tag -a "v${NEW_VERSION}" -m "Release ${NEW_VERSION}"

if [[ $PUSH -eq 1 ]]; then
  git push origin HEAD
  git push origin "v${NEW_VERSION}"
  echo "✅ Pushed commit and tag v${NEW_VERSION}"
else
  echo "ℹ️  Skipped push (--no-push). Tag v${NEW_VERSION} created locally."
fi

# --- build ---
python -m pip install --upgrade pip >/dev/null
python -m pip install --upgrade build twine >/dev/null
python -m build

# --- upload (optional) ---
if [[ -n "$UPLOAD_TARGET" ]]; then
  if [[ "$UPLOAD_TARGET" == "testpypi" ]]; then
    echo "🚀 Uploading to TestPyPI..."
    twine upload --repository testpypi dist/*
    echo "Try install: pip install --index-url https://test.pypi.org/simple/ --no-deps pyxfs"
  else
    echo "🚀 Uploading to PyPI..."
    twine upload dist/*
  fi
else
  echo "ℹ️  Not uploading (no --upload)."
  echo "   You can also publish via GitHub Release if you use the workflow."
fi

echo "🎉 Done. Released ${NEW_VERSION}."
