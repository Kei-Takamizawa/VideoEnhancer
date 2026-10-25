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
        tools = patch.object(driver.shutil, "which", side_effect=lambda name: "/usr/bin/" + name)
        tools.start()
        self.addCleanup(tools.stop)
        self.packages = (driver.SCRIPTS / "toolchain-packages.txt").read_text().splitlines()
        self.packages = list(filter(None, self.packages))
        self.missing = {("binutils", "2.41.90.20240122-1ubuntu1")}
        self.bad_hash = False
        self.host = "archive.ubuntu.com"
        self.mirror_uri = False
        self.no_get_lines = False
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
        if args == ("nasm", "-v"):
            return "NASM version 2.16.01 compiled on mock date\n"
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
            url = f"http://{self.host}/ubuntu/pool/{filename}"
            if self.mirror_uri:
                url = "mirror+file:/etc/apt/apt-mirrors.txt/pool/universe/b/" + filename
            return f"'{url}' {filename} 100 SHA256:mock\n"
        if args[0].endswith("gcc-posix") or args[0].endswith("g++-posix"):
            return "mock compiler 13.2.0\n"
        raise AssertionError(f"Unexpected output command: {args}")

    def run_command(self, args, **kwargs):
        if args[:2] == ["apt-get", "source"]:
            name, version = args[-1].split("=", 1)
            filename, data = self.archive(name, version)
            (kwargs["cwd"] / filename).write_bytes(data)
            self.downloads.append((name, version))
            transcript = (
                f"Get:2 http://{self.host}/ubuntu noble/universe {name} {version} (tar) [100 B]\n"
            )
            return SimpleNamespace(returncode=0, stdout="" if self.no_get_lines else transcript)
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

    def test_mirror_method_download_records_resolved_hosts(self):
        self.mirror_uri = True
        self.host = "azure.archive.ubuntu.com"
        result = self.run_toolchain()
        self.assertTrue(result["sources"])
        for source in result["sources"]:
            self.assertTrue(source["url"].startswith("mirror+file:"))
            self.assertEqual(source["resolved_hosts"], [self.host])
            self.assertTrue(source["apt_get_lines"])

    def test_mirror_method_cache_hit_uses_verified_recorded_origin_without_download(self):
        self.mirror_uri = True
        self.host = "azure.archive.ubuntu.com"
        first = self.run_toolchain()
        self.downloads.clear()
        self.no_get_lines = True
        second = self.run_toolchain()
        self.assertEqual(first["sources"], second["sources"])
        self.assertEqual(self.downloads, [])

    def test_old_cache_without_origin_receipt_is_refetched(self):
        self.mirror_uri = True
        self.run_toolchain()
        for receipt in (self.root / "cache/toolchain/sources").rglob("download-origin.json"):
            receipt.unlink()
        self.downloads.clear()
        self.run_toolchain()
        self.assertTrue(self.downloads)

    def test_corrupt_cached_source_still_fails_before_reuse(self):
        result = self.run_toolchain()
        (self.root / result["sources"][0]["file"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_toolchain()

    def test_mirror_method_does_not_bypass_hash_gate(self):
        self.mirror_uri = True
        self.host = "azure.archive.ubuntu.com"
        self.bad_hash = True
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_toolchain()

    def test_mirror_method_missing_get_lines_cannot_invent_a_resolved_host(self):
        self.mirror_uri = True
        self.no_get_lines = True
        with self.assertRaisesRegex(ValueError, "Cannot resolve"):
            self.run_toolchain()

    def test_runner_mirror_list_only_extends_allowlist_under_ubuntu_com(self):
        mirrors = self.root / "apt-mirrors.txt"
        mirrors.write_text(
            "# runner mirrors\nhttps://mirror.ubuntu.com/ubuntu priority:1\n"
            "http://notubuntu.com/ubuntu\nhttps://ubuntu.com.evil.example/\n"
            "file:/local\n"
        )
        hosts = driver.ubuntu_mirror_hosts(mirrors)
        self.assertEqual(hosts, {"mirror.ubuntu.com"})
        self.assertEqual(
            driver.source_download_hosts(
                "mirror+file:/etc/apt/apt-mirrors.txt/file",
                "Get:1 https://mirror.ubuntu.com/ubuntu x (tar)\n",
                hosts,
            ),
            ["mirror.ubuntu.com"],
        )
        with self.assertRaisesRegex(ValueError, "Unexpected Ubuntu source host"):
            driver.source_download_hosts("https://unlisted.ubuntu.com/file", "", hosts)

    def test_tampered_cached_origin_host_is_rejected(self):
        self.run_toolchain()
        receipt = next((self.root / "cache/toolchain/sources").rglob("download-origin.json"))
        origin = driver.load(receipt)
        for file in origin.values():
            file["resolved_hosts"] = ["evil.example"]
        driver.save(receipt, origin)
        with self.assertRaisesRegex(ValueError, "Unexpected Ubuntu source host"):
            self.run_toolchain()

    def test_complete_records_generated_libass_and_dav1d_features(self):
        for name, text, expected in (
            (
                "libass",
                "#define CONFIG_ASM 1\n",
                {"assembly": True, "iconv": False, "libpng": False},
            ),
            ("dav1d", "#define HAVE_ASM 1\n", {"assembly": True}),
        ):
            build = self.root / "build" / name
            build.mkdir(parents=True)
            (build / "config.h").write_text(text)
            driver.complete(self.root, name)
            receipt = driver.load(self.root / "receipts" / (name + ".json"))
            self.assertEqual(receipt["features"], expected)

    def test_prefixed_binutils_are_checked_and_recorded(self):
        tools = driver.cross_tools()
        for name in ("dlltool", "ranlib", "nm", "objcopy", "objdump", "ld", "windmc"):
            self.assertEqual(tools[name]["command"], "x86_64-w64-mingw32-" + name)
            self.assertEqual(tools[name]["path"], "/usr/bin/x86_64-w64-mingw32-" + name)
        driver.configure_cross(self.root)
        self.assertIn("windmc = 'x86_64-w64-mingw32-windmc'", (self.root / "mingw.ini").read_text())

    def test_missing_dlltool_fails_before_configure(self):
        with patch.object(
            driver.shutil,
            "which",
            side_effect=lambda name: None if name.endswith("-dlltool") else "/usr/bin/" + name,
        ):
            with self.assertRaisesRegex(ValueError, "dlltool"):
                driver.configure_cross(self.root)
        self.assertFalse((self.root / "mingw.ini").exists())

    def test_optional_windmc_is_omitted_when_absent(self):
        with patch.object(
            driver.shutil,
            "which",
            side_effect=lambda name: None if name.endswith("-windmc") else "/usr/bin/" + name,
        ):
            driver.configure_cross(self.root)
        text = (self.root / "mingw.ini").read_text()
        self.assertNotIn("windmc =", text)
        self.assertIn("dlltool = 'x86_64-w64-mingw32-dlltool'", text)
        self.assertNotIn("@PREFIX@", text)
        self.assertIsNone(driver.load(self.root / "cross-tools.json")["windmc"]["path"])

    def test_bison_exception_evidence_is_required_and_hashed(self):
        text = (
            "GNU General Public License either version 3 of the License any later version "
            "As a special exception under terms of your choice "
            "parser generator using the skeleton version 2.2 of Bison"
        )
        file = self.root / "parser.cpp"
        file.write_text(text)
        evidence = {
            "path": "parser.cpp",
            "sha256": driver.digest(file),
            "licence_spdx": "GPL-3.0-or-later WITH Bison-exception-2.2",
        }
        component = {"name": "glslang", "licence_evidence": [evidence]}
        self.assertEqual(len(driver.verify_component_licences(self.root, component)), 1)
        file.write_text("GNU General Public License")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            driver.verify_component_licences(self.root, component)
        evidence["sha256"] = driver.digest(file)
        with self.assertRaisesRegex(ValueError, "Bison exception evidence missing"):
            driver.verify_component_licences(self.root, component)
        evidence["licence_spdx"] = "GPL-3.0-or-later"
        with self.assertRaisesRegex(ValueError, "Unapproved shader GPL"):
            driver.verify_component_licences(self.root, component)

    def test_additional_gpl_source_without_exception_is_rejected(self):
        (self.root / "unexpected.cpp").write_text("GNU General Public License")
        with self.assertRaisesRegex(ValueError, "Unapproved GPL source"):
            driver.verify_component_licences(self.root, {"name": "glslang"})

    def vulkan_header_tree(self):
        source = self.root / "src/vulkan-headers/include"
        for name, text in {
            "vulkan/vulkan.h": '#include "vulkan_core.h"\n',
            "vulkan/vulkan_core.h": "#define VK_VERSION_1_4 1\n",
            "vk_video/vulkan_video_codec_h264std.h": "/* mock codec declarations */\n",
        }.items():
            file = source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)
        shutil.copytree(source, self.root / "prefix/include")

    def test_vulkan_header_only_receipt_records_actual_installed_files(self):
        self.vulkan_header_tree()
        driver.complete(self.root, "vulkan-headers")
        receipt = driver.load(self.root / "receipts/vulkan-headers.json")
        self.assertEqual(receipt["status"], "header-only")
        self.assertEqual(receipt["binary_linkage"], "none")
        self.assertEqual(len(receipt["installed_headers"]), 3)
        for header in receipt["installed_headers"]:
            self.assertEqual(
                header["sha256"], driver.digest(self.root / "prefix/include" / header["file"])
            )

    def test_missing_or_changed_vulkan_video_header_fails(self):
        self.vulkan_header_tree()
        file = self.root / "prefix/include/vk_video/vulkan_video_codec_h264std.h"
        file.unlink()
        with self.assertRaisesRegex(ValueError, "header missing or changed"):
            driver.vulkan_header_receipt(self.root)
        file.write_text("changed")
        with self.assertRaisesRegex(ValueError, "header missing or changed"):
            driver.vulkan_header_receipt(self.root)

    def test_vulkan_header_version_must_meet_libplacebo_requirement(self):
        self.vulkan_header_tree()
        (self.root / "src/vulkan-headers/include/vulkan/vulkan_core.h").write_text(
            "#define VK_VERSION_1_3 1\n"
        )
        with self.assertRaisesRegex(ValueError, "Vulkan 1.4"):
            driver.vulkan_header_receipt(self.root)

    def cxx_fixture(self):
        pc = self.root / "prefix/lib/pkgconfig/shaderc_combined.pc"
        pc.parent.mkdir(parents=True)
        pc.write_text(
            "Name: shaderc\nLibs: -L${libdir} -lshaderc_combined\nRequires.private: zlib\n"
        )
        runtime = self.root / "compiler/libstdc++.a"
        runtime.parent.mkdir()
        runtime.write_bytes(b"mock static C++ archive")
        (runtime.parent / "libwinpthread.a").write_bytes(b"mock static thread archive")
        return pc, runtime

    def cxx_output(self, runtime, *args, cwd=None):
        if args[0].endswith("g++-posix"):
            return str(runtime.parent / args[-1].split("=", 1)[1])
        if args[:2] == ("pkg-config", "--static"):
            return "-lshaderc_combined -l:libstdc++.a"
        raise AssertionError(args)

    def test_shaderc_private_runtime_recipe_and_manifest_evidence(self):
        pc, runtime = self.cxx_fixture()
        with (
            patch.object(
                driver, "output", side_effect=lambda *a, **kw: self.cxx_output(runtime, *a, **kw)
            ),
            patch.object(
                driver.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ),
        ):
            driver.static_cxx_recipe(self.root)
        text = pc.read_text()
        self.assertIn("Libs: -L${libdir} -lshaderc_combined\n", text)
        self.assertIn("Requires.private: zlib", text)
        self.assertIn("-l:libstdc++.a", text)
        changes = driver.load(self.root / "recipe-changes.json")
        self.assertEqual(changes[0]["sha256"], driver.digest(pc))
        self.assertNotIn("-l:libwinpthread.a", changes[0]["added_private_flags"])
        self.assertEqual(len(changes[0]["probe_attempts"]), 1)
        driver.complete(self.root, "shaderc")
        self.assertEqual(
            driver.load(self.root / "receipts/shaderc.json")["recipe_changes"], changes
        )

    def test_winpthread_is_added_only_after_a_real_thread_symbol_failure(self):
        _, runtime = self.cxx_fixture()
        with (
            patch.object(
                driver, "output", side_effect=lambda *a, **kw: self.cxx_output(runtime, *a, **kw)
            ),
            patch.object(
                driver.subprocess,
                "run",
                side_effect=[
                    SimpleNamespace(
                        returncode=1, stdout="", stderr="undefined reference to `pthread_once'"
                    ),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                ],
            ),
        ):
            driver.static_cxx_recipe(self.root)
        change = driver.load(self.root / "recipe-changes.json")[0]
        self.assertIn("-l:libwinpthread.a", change["added_private_flags"])
        self.assertEqual([a["exit_code"] for a in change["probe_attempts"]], [1, 0])

    def test_unrelated_link_failure_does_not_add_pthread_or_hide_failure(self):
        pc, runtime = self.cxx_fixture()
        before = pc.read_text()
        with (
            patch.object(
                driver, "output", side_effect=lambda *a, **kw: self.cxx_output(runtime, *a, **kw)
            ),
            patch.object(
                driver.subprocess,
                "run",
                return_value=SimpleNamespace(
                    returncode=1, stdout="", stderr="undefined reference to `unrelated_symbol'"
                ),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "probe failed"):
                driver.static_cxx_recipe(self.root)
        self.assertEqual(pc.read_text(), before)

    def test_generated_mpv_link_checks_runtime_order_and_shared_spirv_cross(self):
        import_lib = self.root / "prefix/lib/libspirv-cross-c-shared.dll.a"
        import_lib.parent.mkdir(parents=True)
        import_lib.write_bytes(b"mock import archive")
        command = (
            "x86_64-w64-mingw32-gcc-posix -o libmpv-2.dll main.o libharfbuzz.a "
            "libplacebo.a libshaderc_combined.a -l:libstdc++.a -lspirv-cross-c-shared"
        )
        with patch.object(driver, "output", return_value=command):
            driver.check_mpv_link(self.root)
        proof = driver.load(self.root / "mpv-link.json")
        self.assertTrue(proof["static_cxx_runtime_after_archives"])
        self.assertEqual(proof["spirv_cross_import_library_sha256"], driver.digest(import_lib))


class AptSourceOrigins(unittest.TestCase):
    def test_exact_round_2_pseudo_uri_and_get_line(self):
        uri = (
            "mirror+file:/etc/apt/apt-mirrors.txt/pool/universe/b/"
            "binutils-mingw-w64/binutils-mingw-w64_11.4.dsc"
        )
        text = (
            "Get:2 http://azure.archive.ubuntu.com/ubuntu noble/universe "
            "binutils-mingw-w64 11.4 (dsc) [1898 B]\n"
        )
        self.assertEqual(
            driver.source_download_hosts(uri, text, set()), ["azure.archive.ubuntu.com"]
        )

    def test_direct_urls_still_work_without_get_lines(self):
        for host in ("archive.ubuntu.com", "security.ubuntu.com", "us.archive.ubuntu.com"):
            self.assertEqual(
                driver.source_download_hosts(f"https://{host}/file", "", set()), [host]
            )

    def test_untrusted_resolved_host_rejected_even_with_official_planned_url(self):
        with self.assertRaisesRegex(ValueError, "Unexpected Ubuntu source host"):
            driver.source_download_hosts(
                "https://archive.ubuntu.com/file",
                "Get:1 https://archive.ubuntu.com.evil.example/ubuntu x\n",
                set(),
            )

    def test_multiple_hosts_are_all_checked(self):
        text = (
            "Get:1 http://azure.archive.ubuntu.com/ubuntu x (dsc)\n"
            "Get:2 http://evil.example/ubuntu x (tar)\n"
        )
        with self.assertRaisesRegex(ValueError, "Unexpected Ubuntu source host"):
            driver.source_download_hosts("mirror+file:/etc/apt/apt-mirrors.txt/file", text, set())

    def test_non_http_source_method_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported Ubuntu source URI"):
            driver.source_download_hosts("file:/tmp/local-source", "", set())


def clean_ffmpeg_defines():
    values = {
        "HAVE_X86ASM": 1,
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
    def test_pc_private_edit_preserves_flags_and_deduplicates(self):
        text = "Name: shaderc\nLibs: -lshaderc_combined\nLibs.private: -lm\n"
        patched = driver.add_pc_private(text, ["-l:libstdc++.a"])
        self.assertIn("Libs.private: -lm -l:libstdc++.a", patched)
        self.assertEqual(patched, driver.add_pc_private(patched, ["-l:libstdc++.a"]))
        with self.assertRaisesRegex(ValueError, "Duplicate Libs.private"):
            driver.add_pc_private(text + "Libs.private: -ldummy\n", [])

    def test_cxx_runtime_must_follow_all_static_cxx_archives(self):
        good = ["libharfbuzz.a", "libplacebo.a", "libshaderc_combined.a", "-l:libstdc++.a"]
        driver.validate_cxx_link_order(good, require_placebo=True)
        for bad in (
            ["-l:libstdc++.a", *good[:-1]],
            [*good[:-1], "-lstdc++"],
            [*good, "libharfbuzz.a"],
            [*good, "libspirv-cross-c-shared.a"],
        ):
            with self.subTest(args=bad), self.assertRaises(ValueError):
                driver.validate_cxx_link_order(bad, require_placebo=True)

    def test_libplacebo_vulkan_backend_must_stay_disabled(self):
        options = [
            {"name": "vulkan", "value": "disabled"},
            {"name": "d3d11", "value": "enabled"},
            {"name": "shaderc", "value": "enabled"},
        ]
        driver.require_libplacebo_options(options)
        options[0]["value"] = "enabled"
        with self.assertRaisesRegex(ValueError, "Actual libplacebo option failed: vulkan"):
            driver.require_libplacebo_options(options)

    def test_vulkan_loader_import_is_rejected_even_if_bundled(self):
        with self.assertRaisesRegex(ValueError, "Vulkan loader import is forbidden"):
            driver.validate_imports("pei-x86-64\nDLL Name: vulkan-1.dll", {"vulkan-1.dll"})

    def test_nasm_minimum_for_pinned_projects(self):
        self.assertEqual(
            driver.nasm_version("NASM version 2.16.01 compiled on date")["minimum"], "2.14"
        )
        driver.nasm_version("NASM version 2.14")
        for text in ("NASM version 2.13.03", "NASM version 2.9", "yasm 1.3"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                driver.nasm_version(text)

    def test_libass_disabled_optional_features_and_required_assembly(self):
        self.assertEqual(
            driver.subtitle_decoder_features(
                "libass",
                "#define CONFIG_ASM 1\n/* #undef CONFIG_ICONV */\n/* #undef CONFIG_LIBPNG */\n",
            ),
            {"assembly": True, "iconv": False, "libpng": False},
        )
        for text in (
            "#define CONFIG_ASM 0\n",
            "",
            "#define CONFIG_ASM 1\n#define CONFIG_ICONV 1\n",
            "#define CONFIG_ASM 1\n#define CONFIG_LIBPNG 1\n",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                driver.subtitle_decoder_features("libass", text)

    def test_dav1d_assembly_is_required(self):
        self.assertEqual(
            driver.subtitle_decoder_features("dav1d", "#define HAVE_ASM 1\n"), {"assembly": True}
        )
        with self.assertRaisesRegex(ValueError, "assembly was not built"):
            driver.subtitle_decoder_features("dav1d", "#define HAVE_ASM 0\n")

    def test_ffmpeg_external_assembly_cannot_be_disabled(self):
        values = clean_ffmpeg_defines()
        values["HAVE_X86ASM"] = 0
        with self.assertRaisesRegex(ValueError, "HAVE_X86ASM"):
            driver.validate_ffmpeg("--enable-x86asm", values)
        for flag in ("--disable-x86asm", "--disable-asm"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                driver.validate_ffmpeg(flag, clean_ffmpeg_defines())

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
            "vulkan": "disabled",
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
            "vulkan": "disabled",
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

    def test_separate_spirv_cross_and_shaderc_imports_are_explicitly_allowed(self):
        dlls = {"libspirv-cross-c-shared.dll", "libshaderc_shared.dll"}
        text = "pei-x86-64\n" + "\n".join("DLL Name: " + name for name in sorted(dlls))
        self.assertEqual(set(driver.validate_imports(text, dlls)), dlls)

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
