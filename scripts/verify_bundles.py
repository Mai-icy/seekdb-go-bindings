#!/usr/bin/env python3
"""Check native bundles and their recorded release inputs before tagging."""

import hashlib
import re
import tarfile
from pathlib import Path

from build_release_bundles import BASE_URL, SOURCES

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "darwin-arm64": "macOS arm64",
    "linux-amd64": "Linux amd64",
    "linux-arm64": "Linux arm64",
    "windows-amd64": "Windows amd64",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(platform: str, readme: str) -> None:
    native_dir = ROOT / "native" / platform
    archive_path = native_dir / "bundle.tar.gz"
    label = LABELS[platform]
    match = re.search(rf"^\| {re.escape(label)} bundle \| `([0-9a-f]{{64}})` \|$", readme, re.M)
    if match is None:
        raise ValueError(f"missing README checksum for {platform}")
    actual = sha256(archive_path)
    if actual != match.group(1):
        raise ValueError(f"{platform}: bundle SHA-256 {actual} differs from README")

    source_name, source_hash, baseline = SOURCES[platform]
    source_record = (
        f"Source: {BASE_URL}{source_name}\n"
        f"SHA-256: {source_hash}\n"
        f"Runtime baseline: {baseline}\n"
    )
    if (native_dir / "SOURCE.txt").read_text() != source_record:
        raise ValueError(f"{platform}: SOURCE.txt differs from the pinned build recipe")

    library = "libseekdb.dylib" if platform == "darwin-arm64" else (
        "seekdb.dll" if platform == "windows-amd64" else "libseekdb.so"
    )
    required = {library, "seekdb.exe"} if platform == "windows-amd64" else {
        library, "seekdb", "seekdb.bin"
    }
    names = set()
    with tarfile.open(archive_path, "r:gz") as archive:
        for entry in archive:
            if (not entry.isfile() or not entry.name or
                    entry.name in (".", "..") or "/" in entry.name or "\\" in entry.name or
                    entry.name in names or entry.size == 0):
                raise ValueError(f"{platform}: invalid bundle entry {entry.name!r}")
            names.add(entry.name)
    if not required <= names:
        raise ValueError(f"{platform}: missing bundle entries {sorted(required - names)}")
    print(f"{platform}: verified {actual}")


def main() -> None:
    readme = (ROOT / "README.md").read_text()
    for platform in SOURCES:
        verify(platform, readme)


if __name__ == "__main__":
    main()
