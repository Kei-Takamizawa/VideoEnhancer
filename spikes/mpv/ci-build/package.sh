#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec > >(tee "$ROOT/logs/package.log") 2>&1
python3 "$CI_SCRIPTS/driver.py" package "$ROOT"
