#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec > >(tee "$ROOT/logs/prepare.log") 2>&1
# This bootstrap is for the free, disposable Ubuntu 24.04 runner only.
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || {
    echo 'Bootstrap requires Ubuntu 24.04. See README for manual Linux use.' >&2
    exit 1
}
# Enable source indexes in the same official Ubuntu archive configuration.
sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential cmake meson ninja-build pkgconf nasm python3 python3-jinja2 \
    python3-yaml curl xz-utils zstd ca-certificates
python3 -B -m unittest discover -s "$CI_SCRIPTS" -p 'test_*.py' -v
python3 "$CI_SCRIPTS/driver.py" plan "$ROOT"
