# Running the service on a Linux server

This guide runs the headless VideoEnhancer service on an Ubuntu server with an
NVIDIA GPU, so that iPads and Macs on the home network use the server instead of
a Windows PC. The iPad web app, pairing, notifications and library work as
described in [remote access](REMOTE.md).

The layout below puts VideoEnhancer in its own unprivileged Incus container. The
host only manages the container and forwards two ports from its home-network
address. Nothing is published outside the home network: no router change is
needed or wanted.

> Status: the service, certificates and pairing for this layout are covered by
> CPU tests. GPU processing inside the container still needs the measurements
> listed under [What is verified](#what-is-verified).

## Requirements

- x86_64 Linux with glibc 2.28 or newer (the published PyNvVideoCodec and
  PyTorch wheels are `manylinux_2_28`).
- An NVIDIA GPU whose driver supports CUDA 13.0 or newer, with the NVENC and
  NVDEC libraries (`libnvidia-encode.so.1`, `libnvcuvid.so.1`).
- FFmpeg and ffprobe, Git, `uv`, and Python 3.12 (`uv python install 3.12`
  works where the distribution has no 3.12 package).
- systemd for the per-user service.
- Avahi on the host, so that iPads can resolve `<host>.local`.

`python3 scripts/check_linux_host.py` measures these on a host or in a
container without changing anything, and lists findings that would block the
service. It only checks that FFmpeg was built with NVENC; the GPU smoke test
below shows whether the driver libraries actually load.

## Host driver packages

A headless or compute-only NVIDIA driver installation leaves out the encode and
decode libraries. A container can only use libraries that exist on the host, so
install them on the host, matching the driver branch (595 server here):

```bash
sudo apt-get install libnvidia-encode-595-server libnvidia-decode-595-server
```

## Container settings (on the host)

An Incus container with an NVIDIA GPU receives only the compute libraries
unless the driver's `video` capability is allowed. Without it, NVENC, NVDEC and
PyNvVideoCodec fail with `Cannot load libnvidia-encode.so.1`. Allow it for this
container only, then restart the container:

```bash
incus config set videoenhancer nvidia.driver.capabilities compute,utility,video
incus restart videoenhancer
```

An iPad cannot reach the container's private bridge address. Forward the two
gateway ports from the host's home-network address to the container's loopback
interface (replace the address with the host's own):

```bash
incus config device add videoenhancer ve-https proxy \
  listen=tcp:192.168.1.20:8443 connect=tcp:127.0.0.1:8443
incus config device add videoenhancer ve-setup proxy \
  listen=tcp:192.168.1.20:8080 connect=tcp:127.0.0.1:8080
```

These proxies open connections from inside the container, so the container's
network filter (ACL) does not need to change. The gateway sees forwarded
connections from `127.0.0.1`, which it accepts like any private address. Keep
the listen address on the home network only.

The forwarding and the certificate both name this address. Reserve it for the
server in the router (a DHCP reservation), so that it does not change.

## Install the service (inside the container)

```bash
git clone https://github.com/Kei-Takamizawa/VideoEnhancer.git ~/videoenhancer/repo
cd ~/videoenhancer/repo
uv sync --locked --extra gpu --extra models
.venv/bin/ve remote install --name homeserver --address 192.168.1.20
.venv/bin/ve remote status
```

`--name` and `--address` are the host name (without `.local`) and the
home-network address that iPads use. They are saved as the `remote_name` and
`remote_addresses` settings, and the HTTPS certificate is issued for
`homeserver.local`, `homeserver` and that address instead of the container's own names.
Without them, the service uses this machine's host name and private addresses,
which is right when it runs directly on the server.

`remote install` writes the systemd user unit
`~/.config/systemd/user/videoenhancer.service`, enables and starts it, and opens
pairing for two minutes. The unit restarts a failed service three times, one
minute apart, like the Windows task. It asks logind, without a password prompt,
to keep this user's services running after sign-out and at boot ("lingering").
If that is refused, the result says so; run `sudo loginctl enable-linger <user>`
once.

`ve remote pair`, `stop`, `restart`, `status` and `uninstall` work as on
Windows. There is no Start-menu shortcut or message box; `ve remote pair`
prints the setup address and closing time. VideoEnhancer never changes a Linux
firewall. If one is active on the host, allow the two ports from the home
network only.

Finished videos are kept in `~/Videos/VideoEnhancer` unless `library_folder`
is set.

## What is verified

On 2026-11-25, in an Ubuntu 26.04 Incus container on an RTX 4060 Ti (8 GB,
driver 595.91.07, CUDA 13.2):

- `uv sync --locked --extra gpu --extra models` installed PyTorch
  2.14.1+cu130 and torchvision 0.29.1+cu130 from PyPI. A 4096 x 4096 FP16
  matrix product ran on the GPU at 42.6 TFLOPS, and `torchvision.ops.nms` ran
  on CUDA. The environment used 5.9 GB.
- `ve remote install --name ... --address ...` started the systemd user service
  with lingering on. Through the two Incus proxy devices, another computer on
  the home network received HTTP 200 from the setup port and from
  `/api/session` on the HTTPS port.
- NVENC, NVDEC and PyNvVideoCodec failed to load their libraries, both without
  the `video` capability and with it, because the host had the headless driver
  without the encode and decode packages.

Not yet measured: NVENC, NVDEC and PyNvVideoCodec with the `video` capability,
a complete Standard or Fast job, GPU memory use on an 8 GB card, calibration and
estimate accuracy on this GPU, and pairing an iPad through the forwarded ports.
On Linux, the per-process GPU memory counters used on Windows are unavailable;
reports show them as unavailable and keep the PyTorch and NVML device figures.
