#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")"

export PYTHONWARNINGS="ignore::UserWarning,ignore::FutureWarning"

git ls-files ':(glob)*/*.py' \
    | xargs grep -l "^#\!" \
    | while read -r script_path; do
    echo "Checking $script_path..."
    python "$script_path" --help > /dev/null
done

echo "Checking the crawler..."
node crawler/build/crawler.js --help > /dev/null

echo "Done!"
