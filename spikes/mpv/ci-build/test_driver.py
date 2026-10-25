"""Exercise distribution gates without compiling or loading a native DLL."""

import unittest

import driver


def clean_ffmpeg_defines():
    values = {
        "CONFIG_GPL": 0,
        "CONFIG_NONFREE": 0,
        "CONFIG_VERSION3": 0,
        "CONFIG_NETWORK": 0,
        "CONFIG_AVDEVICE": 0,
    }
    for codec in ("H264", "HEVC", "VP9", "AV1"):
        for variant in ("D3D11VA", "D3D11VA2"):
            values[f"CONFIG_{codec}_{variant}_HWACCEL"] = 1
    for suffix in (
        "H264_DECODER",
        "HEVC_DECODER",
        "AV1_DECODER",
        "LIBDAV1D_DECODER",
        "VP9_DECODER",
        "AAC_DECODER",
        "OPUS_DECODER",
        "VORBIS_DECODER",
        "MP3_DECODER",
        "FLAC_DECODER",
        "MOV_DEMUXER",
        "MATROSKA_DEMUXER",
        "FILE_PROTOCOL",
        "HSTACK_FILTER",
        "VSTACK_FILTER",
        "SPLIT_FILTER",
        "SCALE_FILTER",
        "CROP_FILTER",
        "OVERLAY_FILTER",
    ):
        values["CONFIG_" + suffix] = 1
    return values


class DistributionGates(unittest.TestCase):
    def test_mpv_requires_gpl_false_in_actual_build_options(self):
        values = {
            "gpl": True,
            "libmpv": True,
            "cplayer": False,
            "auto_features": "disabled",
            "d3d11": "enabled",
            "d3d-hwaccel": "enabled",
            "gl": "disabled",
            "lua": "disabled",
            "shaderc": "enabled",
            "spirv-cross": "enabled",
        }
        with self.assertRaises(ValueError):
            driver.require_mpv_options([{"name": k, "value": v} for k, v in values.items()])
        values["gpl"] = False
        driver.require_mpv_options([{"name": k, "value": v} for k, v in values.items()])

    def test_mpv_rejects_optional_features_even_with_gpl_false(self):
        values = {
            "gpl": False,
            "libmpv": True,
            "cplayer": False,
            "auto_features": "disabled",
            "d3d11": "enabled",
            "d3d-hwaccel": "enabled",
            "gl": "disabled",
            "lua": "disabled",
            "shaderc": "enabled",
            "spirv-cross": "enabled",
            "libarchive": "enabled",
        }
        with self.assertRaises(ValueError):
            driver.require_mpv_options([{"name": k, "value": v} for k, v in values.items()])

    def test_clean_minimal_configuration(self):
        driver.validate_ffmpeg("--disable-gpl --disable-nonfree", clean_ffmpeg_defines())

    def test_licence_enable_flags_are_rejected_even_with_clean_macros(self):
        for flag in ("--enable-gpl", "--enable-nonfree", "--enable-version3"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                driver.validate_ffmpeg(flag, clean_ffmpeg_defines())

    def test_generated_gpl_macro_overrides_clean_command_line(self):
        values = clean_ffmpeg_defines()
        values["CONFIG_GPL"] = 1
        with self.assertRaises(ValueError):
            driver.validate_ffmpeg("--disable-gpl", values)

    def test_unlisted_external_codec_is_rejected(self):
        values = clean_ffmpeg_defines()
        values["CONFIG_LIBX264"] = 1
        with self.assertRaises(ValueError):
            driver.validate_ffmpeg("--disable-gpl", values)

    def test_encoder_and_muxer_are_rejected(self):
        for name in ("CONFIG_AAC_ENCODER", "CONFIG_MP4_MUXER"):
            values = clean_ffmpeg_defines()
            values[name] = 1
            with self.subTest(name=name), self.assertRaises(ValueError):
                driver.validate_ffmpeg("--disable-gpl", values)

    def test_missing_hardware_path_is_rejected(self):
        values = clean_ffmpeg_defines()
        values["CONFIG_AV1_D3D11VA2_HWACCEL"] = 0
        with self.assertRaises(ValueError):
            driver.validate_ffmpeg("--disable-gpl", values)

    def test_windows_system_and_explicit_bundled_dependency(self):
        text = "file format pei-x86-64\nDLL Name: KERNEL32.dll\nDLL Name: libwinpthread-1.dll"
        self.assertEqual(len(driver.validate_imports(text, {"libwinpthread-1.dll"})), 2)

    def test_missing_runtime_dll_is_rejected(self):
        with self.assertRaises(ValueError):
            driver.validate_imports("pei-x86-64\nDLL Name: libwinpthread-1.dll", set())

    def test_unlisted_dll_is_rejected_even_when_bundled(self):
        with self.assertRaises(ValueError):
            driver.validate_imports("pei-x86-64\nDLL Name: unknown.dll", {"unknown.dll"})

    def test_wrong_binary_architecture_is_rejected(self):
        with self.assertRaises(ValueError):
            driver.validate_imports("pei-i386\nDLL Name: KERNEL32.dll", set())


if __name__ == "__main__":
    unittest.main()
