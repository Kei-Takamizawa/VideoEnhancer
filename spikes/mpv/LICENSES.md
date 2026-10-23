# libmpv candidate: distribution is not cleared

The product remains MIT. This spike loads a DLL dynamically; it adds no library
to the product or package. Do not distribute the candidate until all open items
below are resolved. A file named `lgpl` is not sufficient evidence.

## Pinned upstream evidence

- [Release 2026-10-23-0fae469547](https://github.com/zhongfly/mpv-winbuild/releases/tag/2026-10-23-0fae469547).
- [Builder workflow](https://github.com/zhongfly/mpv-winbuild/blob/b120d7d8a64d17bd40b893f585429ef3845ac766/.github/workflows/mpv.yml)
  and [LGPL patch](https://github.com/zhongfly/mpv-winbuild/blob/b120d7d8a64d17bd40b893f585429ef3845ac766/compile-lgpl-libmpv.patch).
- [mpv copyright and build-dependent licensing](https://github.com/mpv-player/mpv/blob/0fae4695470bf2c0c06762503292ee5379f62f62/Copyright).
- [FFmpeg compliance checklist](https://ffmpeg.org/legal.html).

`download.ps1` pins the two release archives and checks their published SHA-256
values before extracting. `audit.py` also pins the extracted libmpv DLL hash.
The DLL contains `-Dgpl=false`. The companion FFmpeg EXE reports
`--enable-version3` and neither `--enable-gpl` nor `--enable-nonfree`.
Its configuration is evidence for that EXE, not a substitute for the exact
FFmpeg build configuration statically linked into libmpv.

## DLL inventory

| Bundled DLL | Bytes | SHA-256 | Licence status |
| --- | ---: | --- | --- |
| libmpv-2.dll | 101511680 | b9f3ddd1ef2d43d6424addb835824ddb4e1e5f72c067e2816f0e09b19a6c4752 | mpv configured LGPL; aggregate static dependency audit OPEN |

The archive contains only one DLL, an import archive, and four public headers.
It contains no licence texts, dependency manifest, or corresponding source.
Dependencies may be statically included in that DLL. Counting DLLs does not
enumerate those dependencies. A complete list of every linked dependency,
version, licence, source, patches and build flags remains **OPEN**.

The companion FFmpeg EXE is a fixture-generation tool, not a proposed product
dependency. Its SHA-256 is
`201f7112b9b76aaec64b5dbaa56b39335e962d8b9a1d2ef0de8a5a099dabca69`.

## Proposed shipping requirements, pending complete audit

Provide attribution and the applicable LGPL/GPL licence texts, including those
required by LGPL version 3 dependencies. Include the MIT/BSD/other notices for
all permissively licensed dependencies. LGPL licensing can require including
the GPL text; this does not permit linking a GPL-only component.

Keep libmpv replaceable as a separate DLL and permit the debugging and library
replacement rights required by the applicable licence. Preserve notices in
the app and download documentation. Supply the exact corresponding source,
patches and build instructions for copyleft libraries with the release; use
an accompanying source download rather than relying on a moving upstream
branch. Include relinking materials when required for statically combined
LGPL libraries. The final package must contain no GPL-only or nonfree code.

**OPEN:** validate the licence version of the final combined DLL, source
delivery and relinking materials; produce the complete dependency manifest;
verify the embedded FFmpeg configuration; collect all required licence texts.
This spike has not established that the prebuilt binary satisfies Part A's
dependency licence requirement, and has not built an alternative from source.
