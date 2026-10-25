#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec > >(tee "$ROOT/logs/toolchain.log") 2>&1
mapfile -t packages <"$ROOT/toolchain-plan.txt"
stage="$ROOT/apt-stage"
mkdir -p "$stage/partial" "$ROOT/cache/toolchain/debs"
shopt -s nullglob
for deb in "$ROOT/cache/toolchain/debs/"*.deb; do
    cp -- "$deb" "$stage/"
done
# apt verifies cached packages against the authenticated Ubuntu indexes too.
sudo apt-get -y --download-only -o "Dir::Cache::archives=$stage" install "${packages[@]}"
for deb in "$stage/"*.deb; do
    cp -- "$deb" "$ROOT/cache/toolchain/debs/"
done
sudo apt-get -y -o "Dir::Cache::archives=$stage" install "${packages[@]}"
python3 "$CI_SCRIPTS/driver.py" toolchain "$ROOT"
