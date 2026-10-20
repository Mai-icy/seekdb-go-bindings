#!/usr/bin/env python3
"""Build a native bundle from a supplied seekdb binary and C SDK."""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from native_deps import collect_linux, collect_mac

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("darwin-arm64", "linux-amd64"))
    parser.add_argument("support_dir", type=Path, help="directory containing libseekdb")
    parser.add_argument("output", type=Path, help="output bundle.tar.gz path")
    parser.add_argument("--seekdb-bin", type=Path, required=True, help="locally supplied seekdb executable")
    parser.add_argument("--library-dir", type=Path, action="append", default=[],
                        help="additional directory to search for native dependencies (repeatable)")
    args = parser.parse_args()

    library_name = "libseekdb.dylib" if args.platform == "darwin-arm64" else "libseekdb.so"
    support = args.support_dir.resolve(strict=True)
    executable = args.seekdb_bin.resolve(strict=True)
    search = [directory.resolve(strict=True) for directory in args.library_dir]
    if not (support / library_name).is_file():
        parser.error(f"missing {library_name} in {support}")

    with tempfile.TemporaryDirectory(prefix="seekdb-release-") as temp_name:
        stage = Path(temp_name) / "stage"
        stage.mkdir()
        shutil.copy2(support / library_name, stage / library_name)
        binary = stage / "seekdb"
        shutil.copy2(executable, binary)
        binary.chmod(0o755)
        try:
            if args.platform == "linux-amd64":
                collect_linux(stage, [support, *search])
            else:
                collect_mac(stage, support, executable, search)
        except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
            parser.error(str(error))
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_native.py"),
             args.platform, str(stage), str(args.output)],
            check=True,
        )
    print(f"bundle SHA-256 {sha256(args.output)}: {args.output}")


if __name__ == "__main__":
    main()
