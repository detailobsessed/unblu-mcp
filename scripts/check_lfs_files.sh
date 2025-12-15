#!/bin/bash
# Check that LFS files are actual content, not pointers
# This prevents accidentally committing/pushing LFS pointer files

set -e

for f in $(git lfs ls-files -n 2>/dev/null); do
    if head -1 "$f" 2>/dev/null | grep -q "^version https://git-lfs"; then
        echo "ERROR: $f is an LFS pointer, not actual content."
        echo "Run: git lfs pull"
        exit 1
    fi
done

echo "All LFS files are actual content."
