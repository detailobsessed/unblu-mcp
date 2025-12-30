#!/bin/bash
# Check that pyproject.toml and uv.lock don't contain non-PyPI URLs
# This prevents accidentally committing corporate PyPI mirror URLs

# Only allow official PyPI URLs
PYPI_PATTERN="https://(files\.pythonhosted\.org|pypi\.org|test\.pypi\.org)"

# Check for any URL in uv.lock that's not from PyPI
if grep -E "url = \"https?://" uv.lock 2>/dev/null | grep -vE "$PYPI_PATTERN" | grep -q .; then
    echo "ERROR: Non-PyPI URL found in uv.lock"
    echo "Regenerate with: uv lock --refresh --no-config"
    echo "This happens when 'uv lock' uses your local PyPI mirror config."
    exit 1
fi

# Check for any [[tool.uv.index]] section in pyproject.toml (shouldn't exist for public projects)
if grep -q '\[\[tool\.uv\.index\]\]' pyproject.toml 2>/dev/null; then
    echo "ERROR: Custom index found in pyproject.toml"
    echo "Remove the [[tool.uv.index]] section before committing."
    echo "This happens when 'uv add' persists your local PyPI mirror config."
    exit 1
fi

exit 0
