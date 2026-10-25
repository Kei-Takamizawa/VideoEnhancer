#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"
exec > >(tee "$ROOT/logs/build.log") 2>&1
[[ ! -e "$ROOT/build" && ! -e "$PREFIX" && ! -e "$ROOT/src" ]] || {
    echo 'Use a fresh MPV_CI_ROOT for every build; only cache/ is reusable.' >&2
    exit 1
}
mkdir -p "$ROOT/build" "$PREFIX/include" "$PREFIX/lib/pkgconfig"
export CC="$TARGET-gcc-posix" CXX="$TARGET-g++-posix"
export AR="$TARGET-ar" RANLIB="$TARGET-ranlib" STRIP="$TARGET-strip"
export PKG_CONFIG_PATH=
export PKG_CONFIG_LIBDIR="$PREFIX/lib/pkgconfig:$PREFIX/share/pkgconfig"
export CFLAGS="-O2 -I$PREFIX/include"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-L$PREFIX/lib -static-libgcc -static-libstdc++"
python3 "$CI_SCRIPTS/driver.py" fetch "$ROOT"
sed "s|@PREFIX@|$PREFIX|g" "$CI_SCRIPTS/mingw.ini.in" >"$ROOT/mingw.ini"
sed "s|@PREFIX@|$PREFIX|g" "$CI_SCRIPTS/mingw.cmake.in" >"$ROOT/mingw.cmake"
component=
run() { python3 "$CI_SCRIPTS/driver.py" exec "$ROOT" "$component" "$@"; }
done_component() { python3 "$CI_SCRIPTS/driver.py" complete "$ROOT" "$component"; }
meson_component() {
    component=$1
    shift
    local library=static
    if [[ $component == mpv ]]; then library=shared; fi
    run meson setup "$ROOT/build/$component" "$ROOT/src/$component" \
        --prefix "$PREFIX" --libdir lib --cross-file "$ROOT/mingw.ini" \
        --wrap-mode=nodownload --auto-features=disabled --buildtype=release \
        -Ddefault_library="$library" -Dprefer_static=true "$@"
    run meson compile -C "$ROOT/build/$component" -j "$BUILD_JOBS"
    run meson install -C "$ROOT/build/$component" --no-rebuild
    done_component
}
cmake_component() {
    component=$1
    shift
    run cmake -S "$ROOT/src/$component" -B "$ROOT/build/$component" -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE="$ROOT/mingw.cmake" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" -DCMAKE_INSTALL_LIBDIR=lib \
        -DCMAKE_PREFIX_PATH="$PREFIX" -DBUILD_SHARED_LIBS=OFF "$@"
    run cmake --build "$ROOT/build/$component" --parallel "$BUILD_JOBS"
    run cmake --install "$ROOT/build/$component"
    done_component
}

# zlib 1.3.1 builds both flavours in CMake. Build/install only its static target.
component=zlib
run cmake -S "$ROOT/src/zlib" -B "$ROOT/build/zlib" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$ROOT/mingw.cmake" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" -DZLIB_BUILD_EXAMPLES=OFF
run cmake --build "$ROOT/build/zlib" --target zlibstatic --parallel "$BUILD_JOBS"
run install -m 644 "$ROOT/build/zlib/libzlibstatic.a" "$PREFIX/lib/libz.a"
run install -m 644 "$ROOT/src/zlib/zlib.h" "$ROOT/build/zlib/zconf.h" "$PREFIX/include/"
run install -m 644 "$ROOT/build/zlib/zlib.pc" "$PREFIX/lib/pkgconfig/zlib.pc"
done_component

cmake_component freetype -DFT_REQUIRE_ZLIB=ON -DFT_DISABLE_BZIP2=ON \
    -DFT_DISABLE_PNG=ON -DFT_DISABLE_HARFBUZZ=ON -DFT_DISABLE_BROTLI=ON
meson_component fribidi -Ddocs=false -Dbin=false -Dtests=false
meson_component harfbuzz -Dfreetype=enabled -Dzlib=enabled -Dtests=disabled \
    -Dutilities=disabled -Dsubset=disabled -Draster=disabled -Dvector=disabled \
    -Dgpu=disabled -Dwith_libstdcxx=true
meson_component libass -Ddirectwrite=enabled -Dasm=enabled
meson_component dav1d -Denable_tools=false -Denable_tests=false \
    -Denable_examples=false -Denable_docs=false -Denable_asm=true
# The pinned mpv D3D11 render API requires shaderc as well as SPIRV-Cross.
# Use exactly shaderc's DEPS revisions, supplied without git-sync-deps.
cmake_component shaderc -DSHADERC_SKIP_TESTS=ON -DSHADERC_SKIP_EXAMPLES=ON \
    -DSHADERC_SKIP_EXECUTABLES=ON -DSHADERC_SKIP_COPYRIGHT_CHECK=ON \
    -DSHADERC_ENABLE_WERROR_COMPILE=OFF -DSHADERC_ENABLE_WGSL_OUTPUT=OFF \
    -DSHADERC_GLSLANG_DIR="$ROOT/src/glslang" \
    -DSHADERC_SPIRV_TOOLS_DIR="$ROOT/src/spirv-tools" \
    -DSHADERC_SPIRV_HEADERS_DIR="$ROOT/src/spirv-headers" \
    -DSPIRV-Headers_SOURCE_DIR="$ROOT/src/spirv-headers" \
    -DSPIRV_SKIP_TESTS=ON -DSPIRV_SKIP_EXECUTABLES=ON \
    -DSPIRV_WERROR=OFF -DGLSLANG_TESTS=OFF -DENABLE_GLSLANG_BINARIES=OFF \
    -DENABLE_SPVREMAPPER=OFF -DENABLE_PCH=OFF
for child in glslang spirv-tools spirv-headers; do
    python3 "$CI_SCRIPTS/driver.py" complete "$ROOT" "$child" shaderc
done
# libplacebo's D3D11 backend requires the spirv-cross-c-shared API.
# Keep this permissive dependency replaceable rather than fabricating a .pc alias.
cmake_component spirv-cross -DSPIRV_CROSS_SHARED=ON -DSPIRV_CROSS_STATIC=OFF \
    -DSPIRV_CROSS_CLI=OFF -DSPIRV_CROSS_ENABLE_TESTS=OFF \
    -DSPIRV_CROSS_ENABLE_MSL=OFF -DSPIRV_CROSS_ENABLE_CPP=OFF \
    -DSPIRV_CROSS_ENABLE_REFLECT=OFF
meson_component libplacebo -Dd3d11=enabled -Dshaderc=enabled -Dglslang=disabled -Ddemos=false \
    -Dtests=false -Dbench=false -Dfuzz=false

component=ffmpeg
mkdir -p "$ROOT/build/ffmpeg"
cd "$ROOT/build/ffmpeg"
run "$ROOT/src/ffmpeg/configure" \
    --prefix="$PREFIX" --target-os=mingw32 --arch=x86_64 --enable-cross-compile \
    --cross-prefix="$TARGET-" --cc="$CC" --cxx="$CXX" \
    --x86asmexe=nasm --enable-asm --enable-x86asm \
    --pkg-config=pkg-config --pkg-config-flags=--static \
    --extra-cflags="$CFLAGS" --extra-ldflags="$LDFLAGS" \
    --disable-autodetect --disable-everything --disable-gpl --disable-nonfree \
    --disable-programs --disable-doc --disable-network --disable-devices \
    --disable-encoders --disable-muxers --disable-debug --disable-avdevice \
    --disable-shared --enable-static --enable-avcodec --enable-avformat \
    --enable-avfilter --enable-swscale --enable-swresample \
    --enable-protocol=file --enable-demuxer=mov,matroska \
    --enable-decoder=h264,hevc,av1,libdav1d,vp9,aac,aac_fixed,opus,vorbis,mp3,mp3float,flac,pcm_alaw,pcm_mulaw,pcm_s8,pcm_u8,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_s32be,pcm_f32le,pcm_f32be,pcm_f64le,pcm_f64be \
    --enable-parser=h264,hevc,av1,vp9,aac,aac_latm,opus,vorbis,mpegaudio,flac \
    --enable-hwaccel=h264_d3d11va,h264_d3d11va2,hevc_d3d11va,hevc_d3d11va2,vp9_d3d11va,vp9_d3d11va2,av1_d3d11va,av1_d3d11va2 \
    --enable-d3d11va --enable-w32threads --disable-pthreads \
    --enable-libdav1d --enable-zlib \
    --enable-filter=abuffer,abuffersink,aformat,anull,aresample,atempo,atrim,asetpts,pan,volume,buffer,buffersink,format,null,scale,split,trim,setpts,hstack,vstack,crop,overlay
run make -j "$BUILD_JOBS"
run make install
done_component
cd "$ROOT"
meson_component mpv -Dgpl=false -Dlibmpv=true \
    -Dcplayer=false -Dbuild-date=false -Dd3d11=enabled -Dd3d-hwaccel=enabled \
    -Dwasapi=enabled -Dwin32-threads=enabled -Dzlib=enabled -Dlua=disabled \
    -Dshaderc=enabled -Dspirv-cross=enabled -Dgl=disabled
