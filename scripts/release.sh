
#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/release.sh 0.1.1
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version>" >&2
  exit 1
fi

# Update version in pyproject and package __init__
sed -i.bak -E "s/^version = \"[0-9]+\.[0-9]+\.[0-9]+\"/version = \"${VERSION}\"/" pyproject.toml
sed -i.bak -E "s/__version__ = \"[0-9]+\.[0-9]+\.[0-9]+\"/__version__ = \"${VERSION}\"/" src/pyxfs/__init__.py
rm -f pyproject.toml.bak src/pyxfs/__init__.py.bak

git add pyproject.toml src/pyxfs/__init__.py CHANGELOG.md
git commit -m "chore: release ${VERSION}"
git tag -a "v${VERSION}" -m "Release ${VERSION}"
git push origin main --tags

echo "Create a GitHub Release for tag v${VERSION} to trigger PyPI publish."
