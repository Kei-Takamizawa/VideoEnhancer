#!/usr/bin/env bash
# Shared environment; never execute the development PC's MSYS2 toolchain.
set -Eeuo pipefail
umask 022
CI_SCRIPTS=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=${MPV_CI_ROOT:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}/libmpv-lgpl}
export CI_SCRIPTS ROOT
export TARGET=x86_64-w64-mingw32
export PREFIX="$ROOT/prefix"
export BUILD_JOBS=${BUILD_JOBS:-2}
export SOURCE_DATE_EPOCH=1792713600
if [[ $(uname -s) != Linux ]]; then
    echo 'The cross build requires Linux; Windows runs static validation only.' >&2
    exit 1
fi
python3 - "$ROOT" "$CI_SCRIPTS" <<'PY'
import pathlib, sys
root, scripts = (pathlib.Path(p).resolve() for p in sys.argv[1:])
repo = scripts.parents[2]
if root == pathlib.Path('/') or root == repo or repo in root.parents:
    raise SystemExit('Build root must be outside the checkout and cannot be /.')
PY
mkdir -p "$ROOT" "$ROOT/cache/downloads" "$ROOT/cache/toolchain" "$ROOT/logs"
