"""Exercise distribution gates without compiling or loading a native DLL."""

import hashlib
import os
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import driver


class MockAptToolchain(unittest.TestCase):
    """Run the real plan/toolchain orchestration against a deterministic apt fixture."""

    def setUp(self):
        base = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp")
        self.root = base / ("mpv-apt-test-" + uuid.uuid4().hex)
        self.root.mkdir(mode=0o755)
        self.packages = (driver.SCRIPTS / "toolchain-packages.txt").read_text().splitlines()
        self.packages = list(filter(None, self.packages))
        self.missing = {("binutils", "2.41.90.20240122-1ubuntu1")}
        self.bad_hash = False
        self.host = "archive.ubuntu.com"
        self.installed = {}
        for package in self.packages:
            if package.startswith("binutils"):
                fields = (
                    "2.41.90.20240122-1ubuntu1+11.4",
                    "binutils-mingw-w64",
                    "11.4",
                    "binutils (= 2.41.90.20240122-1ubuntu1)",
                )
            elif package.startswith("mingw"):
                fields = ("11.0.1-3build1", "mingw-w64", "11.0.1-3build1", "")
            else:
                fields = (
                    "13.2.0-6ubuntu1+26.1",
                    "gcc-mingw-w64",
                    "26.1",
                    "gcc-13 (= 13.2.0-6ubuntu1)",
                )
            self.installed[package] = fields
        self.owners = {
            "libmingw32.a": "mingw-w64-x86-64-dev",
            "_mingw.h": "mingw-w64-x86-64-dev",
            "libwinpthread.a": "mingw-w64-x86-64-dev",
            "libgcc.a": "gcc-mingw-w64-x86-64-posix",
            "libstdc++.a": "g++-mingw-w64-x86-64-posix",
        }
        self.downloads = []

    def tearDown(self):
        shutil.rmtree(self.root)

    def archive(self, package, version):
        filename = f"{package}_{version}.orig.tar.xz"
        data = f"mock source {package}={version}".encode()
        return filename, data

    def apt_output(self, *args, cwd=None):
        if args[:2] == ("apt-cache", "policy"):
            return "  Candidate: " + self.installed[args[2]][0] + "\n"
        if args[:2] == ("dpkg-query", "-W"):
            return "\t".join(self.installed[args[-1]])
        if args[0].endswith("g++-posix") and args[1].startswith("-print-file-name="):
            return "/usr/lib/mock/../../lib/mock/" + args[1].split("=", 1)[1] + "\n"
        if args[:2] == ("dpkg-query", "-S"):
            return self.owners[Path(args[2]).name] + ": " + args[2] + "\n"
        if args[:2] == ("apt-cache", "showsrc"):
            package = args[-1]
            pairs = {(v[1], v[2]) for v in self.installed.values()}
            pairs.update({("binutils", "2.41.90.20240122-1ubuntu1"), ("gcc-13", "13.2.0-6ubuntu1")})
            stanzas = []
            for name, version in sorted(pairs - self.missing):
                if name != package:
                    continue
                filename, data = self.archive(name, version)
                checksum = "0" * 64 if self.bad_hash else hashlib.sha256(data).hexdigest()
                stanzas.append(
                    f"Package: {name}\nVersion: {version}\nChecksums-Sha256:\n"
                    f" {checksum} {len(data)} {filename}\n"
                )
            return "\n".join(stanzas)
        if args[:2] == ("apt-get", "source"):
            name, version = args[-1].split("=", 1)
            filename, _ = self.archive(name, version)
            return f"'http://{self.host}/ubuntu/pool/{filename}' {filename} 100 SHA256:mock\n"
        if args[0].endswith("gcc-posix") or args[0].endswith("g++-posix"):
            return "mock compiler 13.2.0\n"
        raise AssertionError(f"Unexpected output command: {args}")

    def run_command(self, args, **kwargs):
        if args[:2] == ["apt-get", "source"]:
            name, version = args[-1].split("=", 1)
            filename, data = self.archive(name, version)
            (kwargs["cwd"] / filename).write_bytes(data)
            self.downloads.append((name, version))
            return SimpleNamespace(returncode=0)
        if args == ["x86_64-w64-mingw32-gcc-posix", "-v"]:
            return SimpleNamespace(stderr="mock GCC configuration", returncode=0)
        raise AssertionError(f"Unexpected run command: {args}")

    def run_toolchain(self):
        with (
            patch.object(driver, "output", side_effect=self.apt_output),
            patch.object(driver.subprocess, "run", side_effect=self.run_command),
            patch.dict(os.environ, {"GITHUB_OUTPUT": ""}),
        ):
            driver.plan(self.root)
            driver.toolchain(self.root)
        return driver.load(self.root / "toolchain.json")

    def test_missing_built_using_source_records_exact_ci_failure_and_continues(self):
        result = self.run_toolchain()
        missing = [s for s in result["source_packages"] if s["status"] == "unavailable in deb-src"]
        self.assertEqual([(s["package"], s["version"]) for s in missing], sorted(self.missing))
        self.assertIn("launchpad.net/ubuntu/+source/binutils/", missing[0]["source_url"])
        self.assertNotIn(next(iter(self.missing)), self.downloads)
        self.assertTrue(result["sources"])
        self.assertEqual(len(result["packages"]), 7)
        self.assertEqual(len(result["runtime_components"]), 5)

    def test_missing_runtime_and_compiler_sources_retain_versions_licences_and_urls(self):
        self.missing.update({(v[1], v[2]) for v in self.installed.values()})
        self.missing.add(("gcc-13", "13.2.0-6ubuntu1"))
        result = self.run_toolchain()
        self.assertEqual(result["sources"], [])
        for record in result["runtime_components"]:
            self.assertEqual(record["version"], self.installed[record["package"]][0])
            self.assertTrue(record["licence_spdx"])
            self.assertIn("launchpad.net/ubuntu/+source/", record["source_url"])
        self.assertEqual(
            {r["licence_spdx"] for r in result["runtime_components"]},
            {
                "ZPL-2.1 AND LicenseRef-Public-Domain",
                "MIT",
                "GPL-3.0-or-later WITH GCC-exception-3.1",
            },
        )

    def test_available_source_hash_mismatch_still_fails(self):
        self.bad_hash = True
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_toolchain()

    def test_available_source_unofficial_host_still_fails(self):
        self.host = "untrusted.example"
        with self.assertRaisesRegex(ValueError, "Unexpected Ubuntu source host"):
            self.run_toolchain()

    def test_installed_version_must_match_plan(self):
        with (
            patch.object(driver, "output", side_effect=self.apt_output),
            patch.dict(os.environ, {"GITHUB_OUTPUT": ""}),
        ):
            driver.plan(self.root)
            package = self.packages[0]
            self.installed[package] = ("different", *self.installed[package][1:])
            with self.assertRaisesRegex(ValueError, "does not match plan"):
                driver.toolchain(self.root)

    def test_plan_writes_exact_versions_stable_key_and_actions_outputs(self):
        outputs = self.root / "github-output"
        with (
            patch.object(driver, "output", side_effect=self.apt_output),
            patch.dict(os.environ, {"GITHUB_OUTPUT": str(outputs)}),
        ):
            driver.plan(self.root)
        text = (self.root / "toolchain-plan.txt").read_text()
        self.assertEqual(text.splitlines(), [f"{p}={self.installed[p][0]}" for p in self.packages])
        self.assertIn(
            "toolchain_key=" + hashlib.sha256(text.encode()).hexdigest(), outputs.read_text()
        )
        self.assertIn("artifact_name=libmpv-lgpl-0fae469547", outputs.read_text())

    def test_plan_rejects_missing_candidate(self):
        with patch.object(driver, "output", return_value="Candidate: (none)\n"):
            with self.assertRaisesRegex(ValueError, "No Ubuntu candidate"):
                driver.plan(self.root)

    def test_missing_source_package_apt_error_is_nonfatal(self):
        error = subprocess.CalledProcessError(
            100, "apt-cache", stderr="E: Unable to find a source package for binutils"
        )
        with patch.object(driver, "output", side_effect=error):
            self.assertIsNone(driver.ubuntu_source_metadata("binutils", "old"))

    def test_source_index_error_still_fails(self):
        error = subprocess.CalledProcessError(100, "apt-cache", stderr="E: Index signature invalid")
        with patch.object(driver, "output", side_effect=error):
            with self.assertRaises(subprocess.CalledProcessError):
                driver.ubuntu_source_metadata("binutils", "old")

    def test_matching_source_without_sha256_metadata_still_fails(self):
        with patch.object(driver, "output", return_value="Package: binutils\nVersion: old\n"):
            with self.assertRaisesRegex(ValueError, "Missing source SHA-256"):
                driver.ubuntu_source_metadata("binutils", "old")

    def test_other_source_version_is_not_substituted(self):
        text = "Package: binutils\nVersion: newer\nChecksums-Sha256:\n abc 1 source.tar.xz\n"
        with patch.object(driver, "output", return_value=text):
            self.assertIsNone(driver.ubuntu_source_metadata("binutils", "old"))

    def test_runtime_input_without_installed_owner_fails(self):
        with patch.object(driver, "output", return_value="unresolved.a\n"):
            with self.assertRaisesRegex(ValueError, "cannot locate runtime input"):
                driver.runtime_components()

    def test_source_download_failure_is_not_treated_as_unavailable(self):
        with (
            patch.object(driver, "output", side_effect=self.apt_output),
            patch.object(
                driver.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(100, "apt-get source"),
            ),
            patch.dict(os.environ, {"GITHUB_OUTPUT": ""}),
        ):
            driver.plan(self.root)
            with self.assertRaises(subprocess.CalledProcessError):
                driver.toolchain(self.root)


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
