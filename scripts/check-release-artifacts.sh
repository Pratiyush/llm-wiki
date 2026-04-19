#!/usr/bin/env bash
# Local dry-run of the PyPI release artifact pipeline (#101).
#
# Builds the sdist + wheel the same way .github/workflows/release.yml
# does, then runs `twine check` on them so broken metadata is caught
# before a tag push. Does NOT upload anything.
#
# Usage:
#   scripts/check-release-artifacts.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo "→ Cleaning old build output…"
rm -rf build dist llmwiki.egg-info

echo "→ Installing build + twine in a throwaway venv…"
python3 -m venv .release-smoke
# shellcheck disable=SC1091
source .release-smoke/bin/activate
pip install --quiet --upgrade pip build twine

echo "→ Building sdist + wheel (python -m build)…"
python -m build

echo ""
echo "→ Dist contents:"
ls -la dist/

echo ""
echo "→ twine check …"
twine check dist/*

echo ""
echo "✓ Release artifacts look publishable."
echo "  sdist: $(ls dist/*.tar.gz)"
echo "  wheel: $(ls dist/*.whl)"
echo ""
echo "Next steps:"
echo "  • Follow docs/deploy/pypi-publishing.md to configure PyPI"
echo "  • Then: git tag -s vX.Y.Z -m '...' && git push origin vX.Y.Z"

deactivate
rm -rf .release-smoke
