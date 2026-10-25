"""Pinned-source receipts, fail-closed checks and packaging for the Linux cross build."""

import ast
import configparser
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SYSTEM_DLLS = {
    "advapi32.dll",
    "avrt.dll",
    "bcrypt.dll",
    "comctl32.dll",
    "comdlg32.dll",
    "crypt32.dll",
    "d3d11.dll",
    "d3dcompiler_43.dll",
    "d3dcompiler_47.dll",
    "dcomp.dll",
    "dwrite.dll",
    "dwmapi.dll",
    "dxgi.dll",
    "gdi32.dll",
    "imm32.dll",
    "kernel32.dll",
    "msimg32.dll",
    "msvcrt.dll",
    "normaliz.dll",
    "ntdll.dll",
    "ole32.dll",
    "oleaut32.dll",
    "pathcch.dll",
    "powrprof.dll",
    "propsys.dll",
    "psapi.dll",
    "rpcrt4.dll",
    "secur32.dll",
    "setupapi.dll",
    "shcore.dll",
    "shell32.dll",
    "shlwapi.dll",
    "ucrtbase.dll",
    "user32.dll",
    "uxtheme.dll",
    "version.dll",
    "winmm.dll",
    "ws2_32.dll",
}
RUNTIME_DLLS = {"libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll"}
TARGET_DLLS = {
    "libmpv-2.dll",
    "libspirv-cross-c-shared.dll",
    "spirv-cross-c-shared.dll",
    "libshaderc_shared.dll",
    "shaderc_shared.dll",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def output(*args, cwd=None):
    try:
        return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr, end="")
        raise


def lock():
    data = load(SCRIPTS / "sources.lock.json")
    names = [c["name"] for c in data["components"]]
    if len(names) != 15 or len(set(names)) != len(names):
        raise ValueError("Expected fifteen unique source components")
    for component in data["components"]:
        if not re.fullmatch(r"[0-9a-f]{64}", component["sha256"]):
            raise ValueError("Missing pinned source SHA-256")
        if component["patches"]:
            raise ValueError("This recipe has no source patches; unexpected patch declaration")
    return data


def plan(root):
    packages = (SCRIPTS / "toolchain-packages.txt").read_text().splitlines()
    pins = []
    for package in filter(None, packages):
        policy = output("apt-cache", "policy", package)
        match = re.search(r"Candidate:\s*(\S+)", policy)
        if not match or match[1] == "(none)":
            raise ValueError(f"No Ubuntu candidate for {package}")
        pins.append(f"{package}={match[1]}")
    text = "\n".join(pins) + "\n"
    (root / "toolchain-plan.txt").write_text(text)
    values = {
        "toolchain_key": hashlib.sha256(text.encode()).hexdigest(),
        "artifact_name": "libmpv-lgpl-" + lock()["mpv_commit"][:10],
    }
    for key, value in values.items():
        print(f"{key}={value}")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def ubuntu_source_metadata(package, version):
    try:
        text = output("apt-cache", "showsrc", "--only-source", package)
    except subprocess.CalledProcessError as error:
        # Missing packages are expected in rolling Ubuntu source indexes.
        # Authentication/index/transport failures must still stop the build.
        if re.search(r"Unable to (?:locate|find a) source package", error.stderr or ""):
            return None
        raise
    for stanza in text.split("\n\n"):
        if f"Version: {version}\n" not in stanza + "\n":
            continue
        checksums = {}
        in_hashes = False
        for line in stanza.splitlines():
            if line == "Checksums-Sha256:":
                in_hashes = True
            elif in_hashes and line.startswith(" "):
                sha, size, filename = line.split()
                checksums[filename] = {"sha256": sha, "bytes": int(size)}
            else:
                in_hashes = False
        if checksums:
            return checksums
        raise ValueError(f"Missing source SHA-256 metadata for {package}={version}")
    return None


def source_reference(package, version):
    return "https://launchpad.net/ubuntu/+source/" + "/".join(
        urllib.parse.quote(value, safe="") for value in (package, version)
    )


def installed_package(package):
    fields = output(
        "dpkg-query",
        "-W",
        "-f",
        "${Version}\t${source:Package}\t${source:Version}\t${Built-Using}",
        package,
    ).split("\t")
    if len(fields) != 4 or not all(fields[:3]):
        raise ValueError(f"Incomplete installed package metadata: {package}")
    return {
        "package": package,
        "version": fields[0],
        "source_package": fields[1],
        "source_version": fields[2],
        "built_using": fields[3],
        "source_url": source_reference(fields[1], fields[2]),
    }


def runtime_components():
    """Identify installed owners, including transitive packages, of linked inputs."""
    inputs = [
        ("mingw-w64 CRT", "libmingw32.a", "ZPL-2.1 AND LicenseRef-Public-Domain"),
        (
            "mingw-w64 headers",
            "/usr/x86_64-w64-mingw32/include/_mingw.h",
            "ZPL-2.1 AND LicenseRef-Public-Domain",
        ),
        ("winpthreads", "libwinpthread.a", "MIT"),
        ("libgcc", "libgcc.a", "GPL-3.0-or-later WITH GCC-exception-3.1"),
        ("libstdc++", "libstdc++.a", "GPL-3.0-or-later WITH GCC-exception-3.1"),
    ]
    records = []
    for name, filename, licence in inputs:
        file = (
            filename
            if filename.startswith("/")
            else output("x86_64-w64-mingw32-g++-posix", "-print-file-name=" + filename).strip()
        )
        if not file.startswith("/"):
            raise ValueError(f"Compiler cannot locate runtime input: {filename}")
        # GCC may return /usr/lib/gcc/.../../../../../x86_64-w64-mingw32/lib/...
        file = posixpath.normpath(file)
        owners = output("dpkg-query", "-S", file).strip().splitlines()
        if len(owners) != 1 or ": " not in owners[0]:
            raise ValueError(f"Ambiguous runtime input ownership: {file}")
        package = owners[0].rsplit(": ", 1)[0]
        records.append(
            {
                "component": name,
                "input": file,
                "licence_spdx": licence,
                "linkage": "headers" if name.endswith("headers") else "static input",
                **installed_package(package),
            }
        )
    return records


def ubuntu_mirror_hosts(path=Path("/etc/apt/apt-mirrors.txt")):
    hosts = set()
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            url = urllib.parse.urlparse(line.split()[0])
            host = url.hostname or ""
            if url.scheme in {"http", "https"} and (
                host == "ubuntu.com" or host.endswith(".ubuntu.com")
            ):
                hosts.add(host)
    return hosts


def validate_source_hosts(hosts, mirrors):
    if not hosts:
        raise ValueError("Cannot resolve Ubuntu source host from apt Get lines")
    for host in hosts:
        if not (
            host in {"archive.ubuntu.com", "security.ubuntu.com"}
            or host.endswith(".archive.ubuntu.com")
            or host in mirrors
        ):
            raise ValueError(f"Unexpected Ubuntu source host: {host}")


def source_download_hosts(url, transcript, mirrors):
    parsed = urllib.parse.urlparse(url or "")
    if parsed.scheme not in {"http", "https", "mirror+file"}:
        raise ValueError(f"Unsupported Ubuntu source URI: {url}")
    get_urls = re.findall(r"^Get:\d+\s+(https?://\S+)", transcript, re.MULTILINE)
    hosts = sorted({urllib.parse.urlparse(value).hostname or "" for value in get_urls})
    if not hosts and parsed.scheme in {"http", "https"}:
        hosts = [parsed.hostname or ""]
    validate_source_hosts(hosts, mirrors)
    return hosts


def fetch_toolchain_sources(root, package, version, checksums, urls, mirrors):
    folder = root / "cache/toolchain/sources" / package / version
    folder.mkdir(parents=True, exist_ok=True)
    origin_file = folder / "download-origin.json"
    # A cache hit emits no Get lines. Reuse only a recorded actual origin whose
    # bytes still match the current authenticated index; old caches refetch once.
    cached_origin = load(origin_file) if origin_file.is_file() else {}
    cached = all((folder / name).is_file() for name in checksums)
    if cached:
        for name, expected in checksums.items():
            if digest(folder / name) != expected["sha256"]:
                raise ValueError(f"Ubuntu source hash mismatch: {folder / name}")
        cached = all(
            cached_origin.get(name, {}).get("sha256") == expected["sha256"]
            for name, expected in checksums.items()
        )
    if cached:
        origins = cached_origin
        for name in checksums:
            validate_source_hosts(origins[name]["resolved_hosts"], mirrors)
    else:
        # Never let apt silently reuse an archive with no origin receipt.
        stage = root / "source-downloads" / package / version
        stage.mkdir(parents=True)
        try:
            result = subprocess.run(
                ["apt-get", "source", "--download-only", f"{package}={version}"],
                cwd=stage,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as error:
            print(error.stdout or "", end="", flush=True)
            raise
        transcript = result.stdout
        print(transcript, end="", flush=True)
        origins = {}
        for name, expected in checksums.items():
            file = stage / name
            if not file.is_file() or digest(file) != expected["sha256"]:
                raise ValueError(f"Ubuntu source hash mismatch: {file}")
            origins[name] = {
                "sha256": expected["sha256"],
                "resolved_hosts": source_download_hosts(urls.get(name), transcript, mirrors),
                "apt_get_lines": [
                    line for line in transcript.splitlines() if line.startswith("Get:")
                ],
            }
        for name in checksums:
            shutil.move(stage / name, folder / name)
        stage.rmdir()
        save(origin_file, origins)
    return [
        {
            "package": package,
            "version": version,
            "url": urls.get(name),
            "file": str((folder / name).relative_to(root)),
            **expected,
            "resolved_hosts": origins[name]["resolved_hosts"],
            "apt_get_lines": origins[name]["apt_get_lines"],
        }
        for name, expected in sorted(checksums.items())
    ]


def nasm_version(text):
    match = re.search(r"NASM version (\d+)\.(\d+)(?:\.(\d+))?", text)
    if not match or tuple(int(v or 0) for v in match.groups()) < (2, 14, 0):
        raise ValueError("NASM >= 2.14 required by pinned dav1d (libass needs >= 2.10)")
    return {
        "version_output": text.strip(),
        "minimum": "2.14",
        "ffmpeg_check": "FFmpeg configure must pass its x86asm instruction probes",
    }


def cross_tools():
    config = configparser.ConfigParser(interpolation=None)
    config.read_string((SCRIPTS / "mingw.ini.in").read_text())
    tools = {}
    for name, literal in config["binaries"].items():
        command = ast.literal_eval(literal)
        path = shutil.which(command)
        if not path and name != "windmc":
            raise ValueError(f"Required cross tool not found or executable: {name}={command}")
        tools[name] = {"command": command, "path": path, "optional": name == "windmc"}
    return tools


def configure_cross(root):
    tools = cross_tools()
    text = (SCRIPTS / "mingw.ini.in").read_text()
    if not tools["windmc"]["path"]:
        text = re.sub(r"^windmc = .*\n", "", text, flags=re.MULTILINE)
    (root / "mingw.ini").write_text(text.replace("@PREFIX@", str(root / "prefix")))
    (root / "mingw.cmake").write_text(
        (SCRIPTS / "mingw.cmake.in").read_text().replace("@PREFIX@", str(root / "prefix"))
    )
    save(root / "cross-tools.json", tools)


def add_pc_private(text, flags):
    lines = text.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith("Libs.private:")]
    if len(matches) > 1:
        raise ValueError("Duplicate Libs.private fields")
    existing = shlex.split(lines[matches[0]].partition(":")[2]) if matches else []
    private = existing.copy()
    for flag in flags:
        if flag not in private:
            private.append(flag)
    line = "Libs.private: " + shlex.join(private)
    if matches:
        lines[matches[0]] = line
    else:
        lines.append(line)
    return "\n".join(lines) + "\n"


def validate_cxx_link_order(args, require_placebo=False):
    names = [Path(arg).name for arg in args]
    shader = [
        i
        for i, name in enumerate(names)
        if name in {"libshaderc_combined.a", "-lshaderc_combined", "-l:libshaderc_combined.a"}
    ]
    cpp = [
        i
        for i, name in enumerate(names)
        if name
        in {
            "libplacebo.a",
            "-lplacebo",
            "libharfbuzz.a",
            "-lharfbuzz",
            "libshaderc_combined.a",
            "-lshaderc_combined",
            "-l:libshaderc_combined.a",
        }
    ]
    runtime = [i for i, name in enumerate(names) if name in {"libstdc++.a", "-l:libstdc++.a"}]
    if not shader or not runtime or max(runtime) <= max(cpp):
        raise ValueError("Static C++ runtime must follow shaderc and the other C++ archives")
    if require_placebo and not any(name in {"libplacebo.a", "-lplacebo"} for name in names):
        raise ValueError("mpv link is missing static libplacebo")
    if any(
        "spirv-cross" in name and name.endswith(".a") and not name.endswith(".dll.a")
        for name in names
    ):
        raise ValueError("SPIRV-Cross must keep its separate shared C API")
    return {
        "static_cxx_runtime_after_archives": True,
        "cxx_archives": [args[i] for i in cpp],
        "runtime": args[max(runtime)],
    }


def static_cxx_recipe(root):
    pc = root / "prefix/lib/pkgconfig/shaderc_combined.pc"
    before = pc.read_text()
    if "-lshaderc_combined" not in before:
        raise ValueError("Unexpected installed shaderc_combined.pc")
    runtime = Path(output("x86_64-w64-mingw32-g++-posix", "-print-file-name=libstdc++.a").strip())
    if not runtime.is_absolute() or not runtime.is_file():
        raise ValueError("Static libstdc++.a not found in the pinned toolchain")
    flags = ["-L" + str(runtime.parent), "-l:libstdc++.a"]
    folder = root / "build/cxx-runtime-probe"
    folder.mkdir(parents=True)
    source = folder / "probe.c"
    source.write_text(
        "#include <shaderc/shaderc.h>\n"
        "int main(void) { shaderc_compiler_t c = shaderc_compiler_initialize(); "
        "shaderc_compiler_release(c); return 0; }\n"
    )
    attempts = []
    for attempt in range(2):
        argv = [
            "x86_64-w64-mingw32-gcc-posix",
            "-shared",
            "-static-libgcc",
            "-I" + str(root / "prefix/include"),
            str(source),
            str(root / "prefix/lib/libshaderc_combined.a"),
            *flags,
            "-o",
            str(folder / "probe.dll"),
        ]
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        attempts.append(
            {
                "argv": argv,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        print("+ " + shlex.join(argv), flush=True)
        print(result.stdout + result.stderr, end="", flush=True)
        if result.returncode == 0:
            break
        if attempt == 0 and re.search(r"undefined reference[^\n]*(pthread_|sem_)", result.stderr):
            pthread = Path(
                output("x86_64-w64-mingw32-g++-posix", "-print-file-name=libwinpthread.a").strip()
            )
            if not pthread.is_absolute() or not pthread.is_file():
                raise ValueError("Probe needs static winpthread, but its archive is unavailable")
            flags += ["-L" + str(pthread.parent), "-l:libwinpthread.a"]
        else:
            raise ValueError("Static shaderc C-driver probe failed; see linker output")
    after = add_pc_private(before, flags)
    pc.write_text(after)
    pkg_args = shlex.split(output("pkg-config", "--static", "--libs", "shaderc_combined"))
    validate_cxx_link_order(pkg_args)
    save(
        root / "recipe-changes.json",
        [
            {
                "component": "shaderc",
                "kind": "installed-pkg-config build recipe; not upstream patch",
                "file": "prefix/lib/pkgconfig/shaderc_combined.pc",
                "before": before,
                "after": after,
                "sha256": digest(pc),
                "added_private_flags": flags,
                "pkg_config_static_libs": pkg_args,
                "probe_source": source.read_text(),
                "probe_attempts": attempts,
            }
        ],
    )


def check_mpv_link(root):
    commands = output("ninja", "-C", str(root / "build/mpv"), "-t", "commands", "libmpv-2.dll")
    links = []
    for line in commands.splitlines():
        args = shlex.split(line)
        if "-o" in args and args[args.index("-o") + 1] == "libmpv-2.dll":
            links.append(args)
    if len(links) != 1:
        raise ValueError("Cannot identify the generated libmpv link command")
    args = links[0]
    proof = validate_cxx_link_order(args, require_placebo=True)
    if not any("spirv-cross-c-shared" in arg for arg in args):
        raise ValueError("mpv link is missing the separate SPIRV-Cross C API")
    import_lib = root / "prefix/lib/libspirv-cross-c-shared.dll.a"
    if not import_lib.is_file() or (import_lib.parent / "libspirv-cross-c-shared.a").exists():
        raise ValueError(
            "SPIRV-Cross shared import library is missing or shadowed by a static archive"
        )
    save(
        root / "mpv-link.json",
        {"argv": args, **proof, "spirv_cross_import_library_sha256": digest(import_lib)},
    )
    print(
        "Verified generated mpv link: static C++ runtime follows C++ archives; SPIRV-Cross shared"
    )


def toolchain(root):
    tools = cross_tools()
    assembler = nasm_version(output("nasm", "-v"))
    records, sources = [], set()
    for pin in (root / "toolchain-plan.txt").read_text().splitlines():
        package, version = pin.split("=", 1)
        record = installed_package(package)
        if record["version"] != version:
            raise ValueError(f"Installed toolchain does not match plan: {pin}")
        records.append(record)
    runtimes = runtime_components()
    for record in records + runtimes:
        sources.add((record["source_package"], record["source_version"]))
        sources.update(re.findall(r"([a-z0-9.+-]+) \(= ([^)]+)\)", record["built_using"]))
    fetched, source_packages = [], []
    mirrors = ubuntu_mirror_hosts()
    uri_dir = root / "source-uri-plan"
    uri_dir.mkdir(exist_ok=True)
    for package, version in sorted(sources):
        checksums = ubuntu_source_metadata(package, version)
        source_record = {
            "package": package,
            "version": version,
            "source_url": source_reference(package, version),
            "status": "available" if checksums is not None else "unavailable in deb-src",
        }
        source_packages.append(source_record)
        if checksums is None:
            print(f"Toolchain source {package}={version}: unavailable in deb-src", flush=True)
            continue
        uris = output(
            "apt-get",
            "source",
            "--print-uris",
            "--download-only",
            f"{package}={version}",
            cwd=uri_dir,
        )
        urls = dict(
            (filename, url) for url, filename in re.findall(r"^'([^']+)' (\S+)", uris, re.MULTILINE)
        )
        fetched.extend(fetch_toolchain_sources(root, package, version, checksums, urls, mirrors))
    save(
        root / "toolchain.json",
        {
            "packages": records,
            "sources": fetched,
            "source_packages": source_packages,
            "runtime_components": runtimes,
            "nasm": assembler,
            "cross_tools": tools,
            "compiler": output("x86_64-w64-mingw32-gcc-posix", "--version"),
            "cxx": output("x86_64-w64-mingw32-g++-posix", "--version"),
            "compiler_configuration": subprocess.run(
                ["x86_64-w64-mingw32-gcc-posix", "-v"],
                capture_output=True,
                text=True,
                check=True,
            ).stderr,
            "runtime_licences": {
                "libgcc/libstdc++": "GPL-3.0-or-later WITH GCC-exception-3.1",
                "MinGW-w64/winpthreads": "LicenseRef-MinGW-w64-runtime",
            },
        },
    )


def verify_component_licences(base, component):
    verified = []
    for evidence in component.get("licence_evidence", []):
        file = base / evidence["path"]
        if not file.is_file() or digest(file) != evidence["sha256"]:
            raise ValueError(f"Licence evidence changed or missing: {file}")
        licence = evidence["licence_spdx"]
        if "GPL-" in licence:
            if licence != "GPL-3.0-or-later WITH Bison-exception-2.2":
                raise ValueError(f"Unapproved shader GPL licence: {licence}")
            text = " ".join(file.read_text().split())
            for required in (
                "either version 3 of the License",
                "any later version",
                "As a special exception",
                "under terms of your choice",
                "parser generator using the skeleton",
                "version 2.2 of Bison",
            ):
                if required not in text:
                    raise ValueError(f"Bison exception evidence missing: {file}")
        verified.append({**evidence, "verified_sha256": digest(file)})
    if component["name"] == "glslang":
        approved = {e["path"] for e in verified if "WITH Bison-exception-2.2" in e["licence_spdx"]}
        for file in base.rglob("*"):
            if file.suffix not in {".c", ".cpp", ".h", ".hpp"} or not file.is_file():
                continue
            if "GNU General Public License" in file.read_text(errors="replace"):
                if file.relative_to(base).as_posix() not in approved:
                    raise ValueError(f"Unapproved GPL source without verified exception: {file}")
    return verified


def fetch(root):
    receipts = []
    source_dir = root / "src"
    source_dir.mkdir(exist_ok=True)
    for component in lock()["components"]:
        url = component["url"]
        suffix = ".tar.xz" if url.endswith(".xz") else ".tar.gz"
        name = component["name"]
        archive = root / "cache/downloads" / (name + "-" + component["sha256"] + suffix)
        if not archive.exists():
            with urllib.request.urlopen(url, timeout=120) as response, archive.open("wb") as dest:
                shutil.copyfileobj(response, dest)
        if digest(archive) != component["sha256"]:
            raise ValueError(f"Source SHA-256 mismatch (including cached file): {name}")
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if not parts or parts[0] != component["archive_root"] or ".." in parts:
                    raise ValueError(f"Unexpected archive layout: {name}: {member.name}")
            tar.extractall(source_dir, filter="data")
        (source_dir / component["archive_root"]).rename(source_dir / name)
        for licence in component["licence_files"]:
            if not (source_dir / name / licence).is_file():
                raise ValueError(f"Required licence text missing: {name}/{licence}")
        licence_evidence = verify_component_licences(source_dir / name, component)
        receipts.append(
            {
                **component,
                "archive": str(archive.relative_to(root)),
                "verified_sha256": digest(archive),
                "verified_licence_evidence": licence_evidence,
            }
        )
        print(f"Verified {name}: {component['sha256']}", flush=True)
    save(root / "fetched.json", receipts)
    deps = (source_dir / "shaderc/DEPS").read_text()
    for name in ("glslang", "spirv-headers", "spirv-tools"):
        component = next(c for c in receipts if c["name"] == name)
        key = name.replace("-", "_") + "_revision"
        match = re.search(r"'" + key + r"':\s*'([0-9a-f]{40})'", deps)
        if not match or component["commit"] != match[1]:
            raise ValueError(f"Source pin does not match shaderc DEPS: {name}")


def execute(root, component, argv):
    print("+ " + shlex.join(argv), flush=True)
    record = {"component": component, "cwd": os.getcwd(), "argv": argv}
    result = subprocess.run(argv, check=False)
    record["exit_code"] = result.returncode
    with (root / "commands.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    if result.returncode:
        raise SystemExit(result.returncode)


def validate_ffmpeg(configuration, defines):
    forbidden = {
        "--enable-gpl",
        "--enable-nonfree",
        "--enable-version3",
        "--disable-asm",
        "--disable-x86asm",
    }
    if any(arg.split("=", 1)[0] in forbidden for arg in shlex.split(configuration)):
        raise ValueError("Forbidden FFmpeg configuration flag")
    required = {
        "HAVE_X86ASM": 1,
        "CONFIG_GPL": 0,
        "CONFIG_NONFREE": 0,
        "CONFIG_VERSION3": 0,
        "CONFIG_NETWORK": 0,
        "CONFIG_AVDEVICE": 0,
    }
    for name, value in required.items():
        if defines.get(name) != value:
            raise ValueError(f"FFmpeg configuration gate failed: {name}")
    for codec in ("H264", "HEVC", "VP9", "AV1"):
        for variant in ("D3D11VA", "D3D11VA2"):
            if defines.get(f"CONFIG_{codec}_{variant}_HWACCEL") != 1:
                raise ValueError(f"Missing D3D11VA hwaccel: {codec}/{variant}")
    for name in (
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
        if defines.get("CONFIG_" + name) != 1:
            raise ValueError(f"Missing required FFmpeg component: {name}")
    for name, enabled in defines.items():
        if enabled and re.fullmatch(r"CONFIG_.*_(ENCODER|MUXER)", name):
            raise ValueError(f"Forbidden FFmpeg encoder/muxer: {name}")
        if (
            enabled
            and name.startswith("CONFIG_LIB")
            and name not in {"CONFIG_LIBDAV1D", "CONFIG_LIBDAV1D_DECODER"}
        ):
            raise ValueError(f"Unlisted FFmpeg external library: {name}")


def validate_imports(text, packaged):
    if "pei-x86-64" not in text:
        raise ValueError("DLL is not Windows x86_64 PE")
    imports = re.findall(r"DLL Name:\s*(\S+)", text, re.IGNORECASE)
    if not imports:
        raise ValueError("No DLL import table found")
    for name in imports:
        lower = name.lower()
        if lower == "vulkan-1.dll":
            raise ValueError("Vulkan loader import is forbidden")
        if lower in SYSTEM_DLLS or re.fullmatch(r"api-ms-win-[a-z0-9-]+\.dll", lower):
            continue
        if lower not in TARGET_DLLS | RUNTIME_DLLS or lower not in packaged:
            raise ValueError(f"Unexpected or unbundled DLL import: {name}")
    return imports


def macro(text, name):
    match = re.search(r"^#define " + re.escape(name) + r' (".*")$', text, re.MULTILINE)
    if not match:
        raise ValueError(f"Missing generated configuration macro: {name}")
    return ast.literal_eval(match[1])


def subtitle_decoder_features(name, text):
    defines = {
        k: int(v) for k, v in re.findall(r"^#define\s+(\w+)\s+([01])\s*$", text, re.MULTILINE)
    }
    assembly = "CONFIG_ASM" if name == "libass" else "HAVE_ASM"
    if defines.get(assembly) != 1:
        raise ValueError(f"{name} assembly was not built")
    features = {"assembly": True}
    if name == "libass":
        for feature in ("iconv", "libpng"):
            enabled = bool(defines.get("CONFIG_" + feature.upper(), 0))
            if enabled:
                raise ValueError(f"Unrequested libass dependency enabled: {feature}")
            features[feature] = False
    return features


def vulkan_header_receipt(root):
    base = root / "src/vulkan-headers/include"
    installed = root / "prefix/include"
    core = (base / "vulkan/vulkan_core.h").read_text()
    if not re.search(r"^#define VK_VERSION_1_4 1$", core, re.MULTILINE):
        raise ValueError("Vulkan headers must expose Vulkan 1.4 for pinned libplacebo")
    headers = []
    for folder in ("vulkan", "vk_video"):
        files = sorted(p for p in (base / folder).rglob("*") if p.is_file())
        if not files:
            raise ValueError(f"Required Vulkan header directory is empty: {folder}")
        for source in files:
            relative = source.relative_to(base)
            target = installed / relative
            if not target.is_file() or digest(source) != digest(target):
                raise ValueError(f"Installed Vulkan header missing or changed: {relative}")
            headers.append({"file": relative.as_posix(), "sha256": digest(target)})
    return {
        "status": "header-only",
        "usage": "compile-time only; no Vulkan loader or backend",
        "binary_linkage": "none",
        "installed_headers": headers,
    }


def require_libplacebo_options(options):
    values = {option["name"]: option["value"] for option in options}
    for name, value in {"vulkan": "disabled", "d3d11": "enabled", "shaderc": "enabled"}.items():
        if values.get(name) != value:
            raise ValueError(f"Actual libplacebo option failed: {name}={values.get(name)}")


def complete(root, name, parent=None):
    receipt = {"component": name, "status": "built"}
    build = root / "build" / name
    if parent:
        if load(root / "receipts" / (parent + ".json"))["status"] != "built":
            raise ValueError("Parent shader build has not succeeded")
        receipt["builder_component"] = parent
        if name == "spirv-headers":
            receipt["status"] = "header-only"
    if (build / "CMakeCache.txt").is_file():
        receipt["cmake_cache"] = (build / "CMakeCache.txt").read_text()
    if (build / "meson-info/intro-buildoptions.json").exists():
        receipt["meson_options"] = load(build / "meson-info/intro-buildoptions.json")
    if name == "vulkan-headers":
        receipt.update(vulkan_header_receipt(root))
    if name == "libplacebo":
        require_libplacebo_options(receipt["meson_options"])
    if name == "shaderc":
        changes = root / "recipe-changes.json"
        if changes.is_file():
            receipt["recipe_changes"] = load(changes)
    if name in {"libass", "dav1d"}:
        receipt["features"] = subtitle_decoder_features(name, (build / "config.h").read_text())
    if name == "ffmpeg":
        text = (build / "config.h").read_text() + (build / "config_components.h").read_text()
        defines = {
            k: int(v)
            for k, v in re.findall(r"^#define (CONFIG_\w+|HAVE_X86ASM) ([01])$", text, re.MULTILINE)
        }
        configuration = macro(text, "FFMPEG_CONFIGURATION")
        validate_ffmpeg(configuration, defines)
        library = root / "prefix/lib/libavcodec.a"
        if configuration.encode() not in library.read_bytes():
            raise ValueError("FFmpeg static library lacks its recorded configuration string")
        receipt.update(
            configuration=configuration, defines=defines, static_avcodec_sha256=digest(library)
        )
    save(root / "receipts" / (name + ".json"), receipt)


def require_mpv_options(options):
    values = {o["name"]: o["value"] for o in options}
    expected = {
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
    }
    for name, value in expected.items():
        if values.get(name) != value:
            raise ValueError(f"Actual mpv option failed: {name}={values.get(name)}")
    allowed = {"d3d11", "d3d-hwaccel", "wasapi", "win32-threads", "zlib", "shaderc", "spirv-cross"}
    for option in options:
        if option["value"] == "enabled" and option["name"] not in allowed:
            raise ValueError(f"Unneeded mpv feature enabled: {option['name']}")


def package(root):
    recipe_changes = load(root / "recipe-changes.json")
    for change in recipe_changes:
        if digest(root / change["file"]) != change["sha256"]:
            raise ValueError("Installed pkg-config recipe changed after configuration")
    link = load(root / "mpv-link.json")
    validate_cxx_link_order(link["argv"], require_placebo=True)
    fetched = load(root / "fetched.json")
    commands = [json.loads(line) for line in (root / "commands.jsonl").read_text().splitlines()]
    components = []
    for source in fetched:
        if digest(root / source["archive"]) != source["verified_sha256"]:
            raise ValueError("Source archive changed after extraction")
        verify_component_licences(root / "src" / source["name"], source)
        receipt = load(root / "receipts" / (source["name"] + ".json"))
        if receipt["status"] not in {"built", "header-only"}:
            raise ValueError("Incomplete component")
        builder = receipt.get("builder_component", source["name"])
        calls = [c for c in commands if c["component"] == builder]
        if not calls or any(c["exit_code"] for c in calls):
            raise ValueError("Missing or failed build command")
        components.append({**source, **receipt, "commands": calls})
    if {c["name"] for c in components} != {c["name"] for c in lock()["components"]}:
        raise ValueError("Manifest does not cover every pinned component")
    mpv = next(c for c in components if c["name"] == "mpv")
    placebo = next(c for c in components if c["name"] == "libplacebo")
    ffmpeg = next(c for c in components if c["name"] == "ffmpeg")
    require_mpv_options(mpv["meson_options"])
    require_libplacebo_options(placebo["meson_options"])
    validate_ffmpeg(ffmpeg["configuration"], ffmpeg["defines"])
    artifact = root / "artifact"
    artifact.mkdir()
    prefix_dlls = {p.name.lower(): p for p in (root / "prefix/bin").glob("*.dll")}
    if "libmpv-2.dll" in prefix_dlls:
        shutil.copy2(prefix_dlls["libmpv-2.dll"], artifact / "libmpv-2.dll")
    if not (artifact / "libmpv-2.dll").is_file():
        raise ValueError("libmpv-2.dll was not built")
    # Add only required compiler runtime DLLs, then verify the full closure.
    for _ in range(8):
        added = False
        for file in list(artifact.glob("*.dll")):
            text = output("x86_64-w64-mingw32-objdump", "-p", str(file))
            for name in re.findall(r"DLL Name:\s*(\S+)", text, re.IGNORECASE):
                if name.lower() not in RUNTIME_DLLS | TARGET_DLLS or (artifact / name).exists():
                    continue
                if name.lower() in TARGET_DLLS:
                    path = prefix_dlls.get(name.lower())
                else:
                    path = Path(
                        output("x86_64-w64-mingw32-g++-posix", "-print-file-name=" + name).strip()
                    )
                if path is None or not path.is_file():
                    raise ValueError(f"Required DLL not found: {name}")
                shutil.copy2(path, artifact / name)
                added = True
        if not added:
            break
    dlls = {p.name.lower() for p in artifact.glob("*.dll")}
    imports = {}
    for file in sorted(artifact.glob("*.dll")):
        text = output("x86_64-w64-mingw32-objdump", "-p", str(file))
        imports[file.name] = validate_imports(text, dlls)
        (artifact / (file.name + ".imports.txt")).write_text(text)
        print(f"{digest(file)}  {file.name}", flush=True)
    for component in components:
        component["shipped_dlls"] = [
            name for name in sorted(dlls) if name in component.get("provides_dll_names", [])
        ]
    dll = artifact / "libmpv-2.dll"
    config = macro((root / "build/mpv/config.h").read_text(), "CONFIGURATION")
    if "-Dgpl=false" not in shlex.split(config):
        raise ValueError("Recorded mpv configuration does not explicitly disable GPL")
    if ffmpeg["configuration"].encode() not in dll.read_bytes():
        raise ValueError("The DLL lacks the verified embedded FFmpeg configuration")
    if b"-Dgpl=false" not in dll.read_bytes():
        raise ValueError("The DLL lacks the GPL-disabled mpv configuration")
    licence_root = artifact / "LICENSES"
    for component in components:
        base = root / "src" / component["name"]
        paths = set(component["licence_files"])
        for file in base.rglob("*"):
            if file.is_file() and file.name.lower().startswith(("license", "licence", "copying")):
                paths.add(str(file.relative_to(base)))
        texts = []
        for relative in sorted(paths):
            file = base / relative
            dest = licence_root / component["name"] / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, dest)
            texts.append({"file": str(dest.relative_to(artifact)), "sha256": digest(dest)})
        component["shipped_licence_texts"] = texts
    tool = load(root / "toolchain.json")
    notices = {r["package"]: r for r in tool["packages"] + tool["runtime_components"]}
    for record in notices.values():
        name = record["package"]
        source = Path("/usr/share/doc") / name.split(":", 1)[0] / "copyright"
        dest = licence_root / "toolchain" / (name + ".copyright")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
    for name in ("GPL-3", "LGPL-3", "LGPL-2.1"):
        shutil.copy2(Path("/usr/share/common-licenses") / name, licence_root / "toolchain" / name)
    all_copyright = "\n".join(
        p.read_text(errors="replace") for p in (licence_root / "toolchain").glob("*.copyright")
    )
    if "Runtime Library Exception" not in all_copyright:
        raise ValueError("Compiler runtime exception licence text is missing")
    save(
        artifact / "source-manifest.json",
        {
            "schema": 1,
            "target": lock()["target"],
            "mpv_commit": lock()["mpv_commit"],
            "components": components,
            "toolchain": tool,
            "build_recipe_changes": recipe_changes,
            "mpv_link": link,
            "dll_imports": imports,
            "dlls": [
                {"file": p.name, "bytes": p.stat().st_size, "sha256": digest(p)}
                for p in sorted(artifact.glob("*.dll"))
            ],
            "mpv_configuration": config,
            "embedded_ffmpeg_configuration": ffmpeg["configuration"],
            "combined_lgpl_election": "LGPL-3.0-or-later for Apache-2.0 shader dependencies",
            "runtime_proof": "PENDING: Windows libmpv properties and D3D11VA validation",
            "source_offer": "sources.tar.zst: exact archives, distro patches, scripts and receipts",
        },
    )
    shutil.copy2(SCRIPTS / "DISTRIBUTION.md", artifact / "DISTRIBUTION.md")
    offer = root / "source-offer"
    offer.mkdir()
    shutil.copytree(SCRIPTS, offer / "ci-build", ignore=shutil.ignore_patterns("__pycache__"))
    for source in fetched:
        dest = offer / "archives" / Path(source["archive"]).name
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(root / source["archive"], dest)
    for source in tool["sources"]:
        file = root / source["file"]
        if digest(file) != source["sha256"]:
            raise ValueError("Toolchain corresponding source changed")
        dest = offer / "toolchain-sources" / source["package"] / source["version"] / file.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, dest)
    for name in (
        "toolchain-plan.txt",
        "toolchain.json",
        "cross-tools.json",
        "recipe-changes.json",
        "mpv-link.json",
        "fetched.json",
        "commands.jsonl",
        "mingw.ini",
        "mingw.cmake",
    ):
        shutil.copy2(root / name, offer / name)
    shutil.copytree(root / "receipts", offer / "receipts")
    shutil.copy2(artifact / "source-manifest.json", offer / "source-manifest.json")
    subprocess.run(
        [
            "tar",
            "--sort=name",
            "--mtime=@0",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "-I",
            "zstd -T2 -10",
            "-cf",
            str(artifact / "sources.tar.zst"),
            "-C",
            str(offer),
            ".",
        ],
        check=True,
    )
    sums = [
        f"{digest(p)}  {p.relative_to(artifact).as_posix()}"
        for p in sorted(artifact.rglob("*"))
        if p.is_file()
    ]
    (artifact / "SHA256SUMS").write_text("\n".join(sums) + "\n")


def main():
    command, folder, *args = sys.argv[1:]
    root = Path(folder).resolve()
    actions = {
        "plan": plan,
        "toolchain": toolchain,
        "fetch": fetch,
        "package": package,
        "configure-cross": configure_cross,
        "static-cxx": static_cxx_recipe,
        "check-mpv-link": check_mpv_link,
    }
    if command == "exec":
        execute(root, args[0], args[1:])
    elif command == "complete":
        complete(root, args[0], args[1] if len(args) > 1 else None)
    else:
        actions[command](root)


if __name__ == "__main__":
    main()
