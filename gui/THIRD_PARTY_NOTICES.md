# VideoEnhancer open-source notices

VideoEnhancer is distributed under the MIT licence. Its source is available at
https://github.com/Kei-Takamizawa/VideoEnhancer.

Application dependency licence texts and notices are in `LICENSES/VideoEnhancer/`.
The unmodified published source for `selectors` 0.38.0 (MPL-2.0) is included at
`LICENSES/VideoEnhancer/selectors-0.38.0/source/`, along with the full MPL text.
Its upstream source is https://github.com/servo/stylo at commit
572ecba2d1600e7c3d490586692a209faf703baa. Supplemental licence provenance and
checksums are included beside these materials. Other application dependencies
retain their own MIT, Apache, BSD, Boost and other supplied terms.

## Optional native player

The separate VideoEnhancer-Player helper dynamically loads libmpv. Packages
without the helper use the existing browser player. Packages with it include
the complete upstream notices in `LICENSES/` and `DISTRIBUTION.md`.

The combined libmpv library elects LGPL-3.0-or-later. This does not change the
MIT licence of the separate application. The library includes mpv, FFmpeg,
libplacebo, FriBidi, FreeType, HarfBuzz, libass, dav1d, zlib, SPIRV-Cross,
shaderc, glslang, SPIRV-Tools and their header/runtime dependencies. Their
copyright notices, licence texts, Apache notices, Bison exception and GCC
Runtime Library Exception are preserved in the supplied licence directory.
This software uses the FreeType Project (https://www.freetype.org/), under FTL.

## Corresponding source and written offer

Every distribution containing these DLLs must supply `sources.tar.zst` next
to the application package, together with `SHA256SUMS` and the build manifest.
The archive contains the exact source archives, patches, build scripts and
configuration receipts for the pinned build. Rebuilding instructions are in
the repository's `spikes/mpv/ci-build/README.md`.

For at least three years after distribution, and for as long as spare parts
or customer support for this version are offered, the distributor offers
anyone possessing this binary a copy of its complete corresponding source
under the applicable LGPL terms, at no charge for an electronic copy. Request
it through the repository's issue tracker, identifying the release and CI
run 40202006764. The accompanying archive is the immediate source delivery;
a moving upstream download link is not a substitute for it.

## Replacement and debugging rights

You may replace `libmpv-2.dll` and its dependencies beside the player helper
with compatible modified versions. VideoEnhancer does not check their hashes
at runtime. Hash checks protect the distributor's packaging step only. You
may modify the LGPL components and reverse engineer the combined work to
debug those modifications, as permitted by their licences. No application
term restricts these rights. Keep compatible Windows x86-64 libraries and
their notices together. The HTML5 fallback remains available if a replacement
cannot load. See `DISTRIBUTION.md` and the full LGPL text for details.
