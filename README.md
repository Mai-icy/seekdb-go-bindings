# seekdb Go bindings

This package manages an embedded seekdb server through the `libseekdb` C API.
It provides `Open`, `ConnectionOptions`, and `Close`. Use a MySQL protocol
driver of your choice for SQL queries.

## Install

```sh
go get github.com/Mai-icy/seekdb-go-bindings@v0.2.0
```

Building requires Go 1.22 or newer, `CGO_ENABLED=1`, and a C compiler. Native
bundles are available for macOS arm64, Linux amd64/arm64, and Windows amd64.
The Linux bundles require glibc 2.28 or newer and do not support musl/Alpine.
The Windows bundle requires the Microsoft Visual C++ runtime.

```go
package main

import (
    "log"

    seekdb "github.com/Mai-icy/seekdb-go-bindings"
)

func main() {
    db, err := seekdb.Open("./data")
    if err != nil {
        log.Fatal(err)
    }
    defer db.Close()

    endpoint, err := db.ConnectionOptions()
    if err != nil {
        log.Fatal(err)
    }
    log.Printf("seekdb transport: %s", endpoint.Transport)
    // Connect to endpoint with a MySQL protocol client.
}
```

`Open` creates the database directory when needed and reopens existing data.
Close SQL client connections before calling `Close`.

## Native modules

The repository contains four separately versioned native Go modules:

| Target | Module | Bundle |
| --- | --- | ---: |
| macOS arm64 | `github.com/Mai-icy/seekdb-go-bindings/native/darwin-arm64` | 52.0 MB |
| Linux amd64 | `github.com/Mai-icy/seekdb-go-bindings/native/linux-amd64` | 53.6 MB |
| Linux arm64 | `github.com/Mai-icy/seekdb-go-bindings/native/linux-arm64` | 49.2 MB |
| Windows amd64 | `github.com/Mai-icy/seekdb-go-bindings/native/windows-amd64` | 64.9 MB |

Each module carries a `bundle.tar.gz` with a prebuilt seekdb executable,
`libseekdb` shared library, and required runtime libraries. The `.so`/`.dylib`/`.dll`
is needed by the Go binding and is small compared with the seekdb executable.
The Go build selects the matching module using build constraints and embeds its
bundle in the resulting program. At the first `Open`, the program extracts the
files under the user cache directory (`seekdb-go/<bundle SHA-256>/`) and loads
`libseekdb`. The cache is validated on first use in each process and rebuilt
if files are missing or damaged. `Open` does not download files.

Go downloads native modules from its normal module proxy or this GitHub
repository. A fresh `go get` can download all four platform bundles because the
root module declares all four dependencies; the build embeds only the selected
platform. A new native release uses a new module tag;
existing `go.mod` and `go.sum` files keep applications on their selected
version until they upgrade it.

The four bundles are built from the seekdb 1.4.0.0-r1 C SDK runtime archives.
Each native module records its exact source URL, SHA-256, and runtime baseline
in `SOURCE.txt`. The Linux bundles include OpenSSL 1.1, libaio, and zlib.
The macOS and Linux amd64 bundles were exercised by `go test ./...` on their
respective platforms. The Linux arm64 bundle passed archive integrity and ELF
dependency checks. The Windows amd64 bundle passed archive integrity and PE
architecture checks, and the Go binding was cross-compiled with MinGW; its
runtime behavior has not yet been tested on Windows.

| Input/artifact | SHA-256 |
| --- | --- |
| macOS arm64 bundle | `8267306ccd5e38076df790b025f01b0f403f9524bc98529573eac0e305e8c583` |
| Linux amd64 bundle | `73bae794192b643a4b836cedb1b7f6dd5b7fa5210654d57b804bdc74fe2d1cc7` |
| Linux arm64 bundle | `91b28ab4e0c4c15bab1c7972aec212c9aaee19bc0ce57e25fbff62d2763ca647` |
| Windows amd64 bundle | `3a50225198ac67f26f1777dd02cd6a5357ceb0a7ed33fa78db05a2e7a33af295` |

## Develop and release

The root `go.work` uses the local platform modules for source checkout builds:

```sh
go test ./...
```

To prepare another native release, run on the target platform and supply the
seekdb executable and a matching prebuilt `libseekdb`. The script uses `ldd`
and `patchelf` on Linux, or `otool`, `install_name_tool`, `lipo`, and `codesign`
on macOS, to collect and relocate runtime libraries recursively. Use
`--library-dir` for dependencies outside the SDK directory (repeatable):

```sh
python3 scripts/prepare_native_bundle.py linux-amd64 /path/to/support \
  native/linux-amd64/bundle.tar.gz --seekdb-bin /path/to/seekdb \
  --library-dir /path/to/openssl/lib
```

To reproduce the four current bundles from their pinned runtime archives, run
the following on macOS with `patchelf` installed:

```sh
python3 scripts/build_release_bundles.py
```

The release script verifies the outer and inner SHA-256 checksums and checks
the architecture of each runtime file. It requires `patchelf` to check Linux
dependencies; the macOS build also needs `otool`, `install_name_tool`, `lipo`,
and `codesign`. The locally built Linux workflow still checks the EL7 baseline:
it needs `objdump`, sets `$ORIGIN` on ELF files, and verifies that every
non-system dependency resolves inside the bundle. Each platform module has its
own `go.mod` and is published by a tag prefixed with its directory, for example
`native/linux-amd64/v1.4.1`. The root module uses a root tag such as `v0.2.0`.
Publish changed native bundles under new, immutable versions.
