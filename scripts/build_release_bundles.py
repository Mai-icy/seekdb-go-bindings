#!/usr/bin/env python3
"""Build the four Go native modules from pinned libseekdb release archives."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://6.12.233.133:4000/1.4.0.0/"
SOURCES = {
    "darwin-arm64": (
        "libseekdb-macos-arm64/libseekdb-1.4.0.0-r1-macos15.6-arm64-sdb596e4a5c9809-bndcdb303fbbd5e.tar.gz",
        "347db30614ff0e90f35277aeaa1f7091f6bf7223ed7c3c717d68d6b5f0731a8a",
        "macOS 15.6.1 or newer",
    ),
    "linux-amd64": (
        "libseekdb-linux-x86_64/libseekdb-1.4.0.0-r1-linux-x86_64-glibc2.28-sdb596e4a5c9809-bndcdb303fbbd5e.tar.gz",
        "90f0d3e39fa53a23331fd432fa7f6c1bfe2016cb784f659ff6cb3252890f17cd",
        "glibc 2.28 or newer",
    ),
    "linux-arm64": (
        "libseekdb-linux-aarch64/libseekdb-1.4.0.0-r1-linux-aarch64-glibc2.28-sdb596e4a5c9809-bndcdb303fbbd5e.tar.gz",
        "7860c9f7a8ce381d076bb27cd92b1c892587232733842bf57ff81375adf5a883",
        "glibc 2.28 or newer",
    ),
    "windows-amd64": (
        "libseekdb-windows-x86_64/libseekdb-1.4.0.0-r1-windows-x86_64-sdb596e4a5c9809-bndcdb303fbbd5.tar.gz",
        "46cd2390d7bf85595bc956b2b4bd218458c51078636bae5f190fa1e67a36fefe",
        "Windows x86_64 with the MSVC runtime",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_archive(platform: str, cache: Path) -> Path:
    relative, expected, _ = SOURCES[platform]
    archive = cache / f"{platform}.tar.gz"
    cache.mkdir(parents=True, exist_ok=True)
    if archive.exists() and sha256(archive) == expected:
        return archive
    temporary = archive.with_suffix(".partial")
    try:
        with urllib.request.urlopen(BASE_URL + relative, timeout=180) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual = sha256(temporary)
        if actual != expected:
            raise ValueError(f"{temporary}: SHA-256 {actual}, expected {expected}")
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


def members_by_relative_path(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    result = {}
    for member in archive.getmembers():
        parts = member.name.split("/", 1)
        if len(parts) != 2 or not parts[1] or ".." in Path(parts[1]).parts:
            continue
        if parts[1] in result:
            raise ValueError(f"duplicate release entry: {parts[1]}")
        result[parts[1]] = member
    return result


def copy_member(archive: tarfile.TarFile, member: tarfile.TarInfo, destination: Path) -> None:
    if not member.isfile():
        raise ValueError(f"expected a regular file: {member.name}")
    source = archive.extractfile(member)
    if source is None:
        raise ValueError(f"cannot read {member.name}")
    with source, destination.open("wb") as output:
        shutil.copyfileobj(source, output)
    destination.chmod(0o755 if member.mode & 0o111 else 0o644)


def verify_inner_checksums(archive: tarfile.TarFile, entries: dict[str, tarfile.TarInfo]) -> None:
    sums = archive.extractfile(entries["SHA256SUMS"])
    if sums is None:
        raise ValueError("missing SHA256SUMS")
    with sums:
        lines = sums.read().decode().splitlines()
    for line in lines:
        expected, name = line.split(maxsplit=1)
        name = name.lstrip("*").removeprefix("./")
        member = entries.get(name)
        if member is None or not member.isfile():
            raise ValueError(f"missing checksum target {name}")
        digest = hashlib.sha256()
        source = archive.extractfile(member)
        if source is None:
            raise ValueError(f"cannot read {name}")
        with source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"bad inner checksum for {name}")


def verify_machine(platform: str, path: Path) -> None:
    with path.open("rb") as binary:
        header = binary.read(64)
        if platform.startswith("linux-"):
            expected = 62 if platform == "linux-amd64" else 183
            if header[:4] != b"\x7fELF" or struct.unpack_from("<H", header, 18)[0] != expected:
                raise ValueError(f"wrong ELF architecture: {path}")
        elif platform == "windows-amd64":
            if header[:2] != b"MZ":
                raise ValueError(f"not a Windows PE file: {path}")
            binary.seek(struct.unpack_from("<I", header, 0x3C)[0])
            if binary.read(4) != b"PE\0\0" or struct.unpack("<H", binary.read(2))[0] != 0x8664:
                raise ValueError(f"wrong PE architecture: {path}")


def build_one(platform: str, cache: Path) -> None:
    source = source_archive(platform, cache)
    output = ROOT / "native" / platform / "bundle.tar.gz"
    with tempfile.TemporaryDirectory(prefix=f"seekdb-{platform}-") as temp_name:
        stage = Path(temp_name) / "stage"
        stage.mkdir()
        with tarfile.open(source, "r:gz") as archive:
            entries = members_by_relative_path(archive)
            verify_inner_checksums(archive, entries)
            header = entries.get("include/seekdb/seekdb.h")
            source_header = archive.extractfile(header) if header is not None else None
            if source_header is None:
                raise ValueError(f"{platform}: C header differs from binding")
            with source_header:
                if source_header.read() != (ROOT / "seekdb.h").read_bytes():
                    raise ValueError(f"{platform}: C header differs from binding")
            for name, member in entries.items():
                if member.isfile() and name.startswith("lib/") and (
                    name.endswith((".dylib", ".so", ".dll")) or ".so." in name
                ):
                    target = stage / Path(name).name
                    copy_member(archive, member, target)
                    if platform != "darwin-arm64":
                        verify_machine(platform, target)
            executable = "bin/seekdb.exe" if platform == "windows-amd64" else "lib/seekdb"
            copy_member(archive, entries[executable], stage / Path(executable).name)
            if platform != "darwin-arm64":
                verify_machine(platform, stage / Path(executable).name)
            notice = entries.get("licenses/seekdb-NOTICE")
            if notice is not None:
                copy_member(archive, notice, output.parent / "NOTICE")
            if platform.startswith("linux-"):
                openssl_licenses = [member for name, member in entries.items()
                                    if name.startswith("licenses/runtime-openssl-libs-") and name.endswith("-LICENSE")]
                if len(openssl_licenses) != 1:
                    raise ValueError(f"{platform}: expected one OpenSSL license")
                license_path = output.parent / "LICENSE.openssl"
                copy_member(archive, openssl_licenses[0], license_path)
                license_path.write_bytes(license_path.read_bytes().rstrip() + b"\n")
        if platform == "darwin-arm64":
            command = [sys.executable, str(ROOT / "scripts/prepare_native_bundle.py"), platform,
                       str(stage), str(output), "--seekdb-bin", str(stage / "seekdb")]
        else:
            command = [sys.executable, str(ROOT / "scripts/package_native.py"), platform,
                       str(stage), str(output)]
        subprocess.run(command, check=True)
    relative, expected, baseline = SOURCES[platform]
    (output.parent / "SOURCE.txt").write_text(
        f"Source: {BASE_URL}{relative}\nSHA-256: {expected}\nRuntime baseline: {baseline}\n"
    )
    print(f"{platform}: {output.stat().st_size} bytes, SHA-256 {sha256(output)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", nargs="*", choices=sorted(SOURCES),
                        help="platforms to build; default: all four")
    parser.add_argument("--archive-dir", type=Path, default=Path.home() / ".cache/seekdb-go-releases",
                        help="cache for the pinned source archives")
    args = parser.parse_args()
    for platform in args.platform or SOURCES:
        build_one(platform, args.archive_dir)


if __name__ == "__main__":
    main()
