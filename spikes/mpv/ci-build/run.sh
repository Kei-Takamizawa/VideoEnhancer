#!/usr/bin/env bash
# Manual entry point: the same stages as GitHub Actions, without the cache action.
set -Eeuo pipefail
scripts=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for stage in prepare toolchain build package; do
    bash "$scripts/$stage.sh"
done
