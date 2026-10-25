# Experimental LGPL libmpv source-build artifact

This artifact is for validation. A green cross build does not establish Windows
playback, hardware decoding or product packaging acceptance. The operator must
verify SHA256SUMS and the designer must review the manifest and runtime proof.
The prebuilt measurement candidate is never a shipping fallback.

The target libraries are built from the exact SHA-256-pinned upstream sources
in sources.lock.json. FFmpeg is built without GPL, nonfree or version3 options.
mpv is built with gpl=false. D3D11 requires libplacebo, shaderc (glslang, SPIRV-Tools and SPIRV-Headers)
and SPIRV-Cross.
The LGPL-2.1-or-later components are elected to LGPL-3.0-or-later for the combined
distribution because of the Apache-2.0 shader dependencies. This election does
not turn off the separate permissive attribution and notice requirements.
FFmpeg itself needs no --enable-version3 dependency in this recipe.

See LICENSES/ for the full upstream licence and copyright texts. FreeType is
used under the FreeType Project License (FTL), not its alternative GPL licence:
this software uses the FreeType Project, https://www.freetype.org/.
glslang's BSD, MIT and Apache notices and SPIRV-Cross's Apache notice are retained.
The glslang aggregate also includes BSD-2-Clause and the two generated
glslang_tab.cpp / glslang_tab.cpp.h parser files under
GPL-3.0-or-later WITH Bison-exception-2.2. Their complete source notices are
included under LICENSES/glslang, with full GPLv3 text under LICENSES/toolchain/GPL-3.
The source lock records exact file hashes and the build rejects missing/changed
exception evidence or extra unapproved GPL C/C++ source in glslang.

Compatibility rationale for the selected rendering library and MIT application:

- BSD-2-Clause, BSD-3-Clause and MIT permit this use with their notices retained;
  the BSD endorsement restriction remains applicable.
- Shaderc/SPIRV-Tools/SPIRV-Cross Apache-2.0 notices and patent terms remain
  applicable. The combined LGPL library uses the LGPL-3.0-or-later election
  above, whose GPLv3 base accommodates Apache-2.0; this does not relicense the
  application or remove Apache notices.
- Bison-exception-2.2 permits the generated parser skeleton in a larger work
  under chosen terms when that work is not a parser generator using the skeleton.
  This shader compiler/rendering library meets that stated use, and the exception
  is retained unchanged. Plain GPL shader/parser code without an applicable
  exception is not an approved dependency. The application remains separate and
  must still satisfy the LGPL DLL replacement/source requirements below.

References: [Bison exception text](https://spdx.org/licenses/Bison-exception-2.2.html),
[Apache compatibility](https://www.apache.org/licenses/GPL-compatibility.html),
[LGPLv3 terms](https://spdx.org/licenses/LGPL-3.0-or-later.html),
[MIT terms](https://spdx.org/licenses/MIT.html), and
[BSD terms](https://spdx.org/licenses/BSD-3-Clause.html).

The Ubuntu MinGW compiler runtimes have their own notices: GCC's runtime-library
exception and the mixed permissive MinGW-w64/winpthreads copyright texts are in
LICENSES/toolchain. They are compiler infrastructure under the approved Ubuntu
toolchain route, not unrelated optional media libraries. No GPL-only media or
shader component is enabled. The runtime exception does not impose GPL licensing
on the application; retain its text. CRT/headers are recorded under ZPL/public
domain notices and winpthreads under MIT. The manifest records each installed
runtime input's owning package, exact version, licence and source URL. Available
exact runtime sources are included; where deb-src no longer has that version,
the exact Launchpad source reference is recorded instead. The GCC Runtime Library
Exception permits distribution without corresponding runtime source.

libmpv is a separate dynamically loaded DLL. Users must be allowed to replace it
and debug their modified library. Do not add an integrity restriction that blocks
these rights. Keep the additional dependency DLLs beside it if the manifest
lists them. The source archive includes the exact upstream source archives,
available Ubuntu compiler/runtime sources and distro patches, scripts, cross files and
actual command/configuration receipts. Rebuilding yields a replacement library;
the product must remain dynamically linked to it.
Compiler and binutils sources are supplementary and are not required by the
LGPL source offer; those tools are not shipped. Missing toolchain source versions
are explicitly listed as `unavailable in deb-src` in the manifest. This exception
does not apply to any of the fourteen required upstream source components.

Attach this exact sources.tar.zst and these notices to every release containing
the DLLs. A moving Git URL is not the corresponding-source delivery. Validate the
final distribution and source/relinking arrangement before shipping. This file
does not replace the build-specific LICENSES.md review required on the PC.

