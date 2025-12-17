#!/bin/bash
# Check that pyproject.toml doesn't contain internal URLs
# This prevents accidentally committing corporate PyPI mirror URLs

if grep -qE "(artifactory\.tools\.post\.ch|\.pnet\.ch)" pyproject.toml; then
    echo "ERROR: Internal URL found in pyproject.toml"
    echo "Remove the [[tool.uv.index]] section before committing."
    echo "This happens when 'uv add' persists your local PyPI mirror config."
    exit 1
fi
exit 0
