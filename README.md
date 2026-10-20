# seekdb Go bindings

This package manages an embedded seekdb server through the `libseekdb` C API.
It provides `Open`, `ConnectionOptions`, and `Close`. Use a MySQL protocol
driver of your choice for SQL queries.

## Install

```sh
go get github.com/Mai-icy/seekdb-go-bindings@v0.1.0
```

Building requires Go 1.22 or newer, `CGO_ENABLED=1`, and a C compiler. Native
bundles are supported for macOS arm64 and Linux amd64. The Linux bundle is
built for the EL7/glibc 2.17 baseline and requires glibc, so it does not
support musl/Alpine.

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

The repository contains two separately versioned Go modules:

| Target | Module | Bundle |
| --- | --- | ---: |
| macOS arm64 | `github.com/Mai-icy/seekdb-go-bindings/native/darwin-arm64` | 60.4 MB |
| Linux amd64 | `github.com/Mai-icy/seekdb-go-bindings/native/linux-amd64` | 58.7 MB |

Each module carries a `bundle.tar.gz` with a prebuilt seekdb executable,
`libseekdb` shared library, and required runtime libraries. The `.so`/`.dylib`
is needed by the Go binding and is small compared with the seekdb executable.
The Go build selects the matching module using build constraints and embeds its
bundle in the resulting program. At the first `Open`, the program extracts the
files under the user cache directory (`seekdb-go/<bundle SHA-256>/`) and loads
`libseekdb`. `Open` does not download files.

Go downloads the selected native module from its normal module proxy or this
GitHub repository. Dependency management commands such as `go mod download all`
may fetch both platform modules. A new native release uses a new module tag;
existing `go.mod` and `go.sum` files keep applications on their selected
version until they upgrade it.

The Linux bundle was built from the [official seekdb v1.4.0 EL7 x86_64 RPM](https://github.com/oceanbase/seekdb/releases/download/v1.4.0/seekdb-1.4.0-100000172026082615.el7.x86_64.rpm)
and the C SDK at `Mai-icy/seekdb-bindings` commit `0c42ba6` with
[`patches/libseekdb-el7.patch`](patches/libseekdb-el7.patch). OpenSSL 3.4.5,
libaio, and zlib are included in the Linux bundle. The package was built in a
CentOS 7 based manylinux2014 container and tested there and on Alibaba Cloud
Linux 3. The macOS bundle was migrated from the original Go binding branch.

| Input/artifact | SHA-256 |
| --- | --- |
| Official EL7 RPM | `968e69f3147231c7a14f42dc564ceb95a52dd0c80a365c59d96cf1c00402f52b` |
| Linux bundle | `9b2952f86173b3c300cd08bc509b78c8ce3c8036a8089bcf1c38b717ca817463` |
| macOS bundle | `922125a531e39a73b6fa2304f1aa6590758b3bd069f5721287e69e02ebd75b40` |

## Develop and release

The root `go.work` uses the local platform modules for source checkout builds:

```sh
go test ./...
```

To prepare another native release, supply the seekdb executable and a directory
with a matching prebuilt `libseekdb` plus its runtime libraries:

```sh
python3 scripts/prepare_native_bundle.py linux-amd64 /path/to/support \
  native/linux-amd64/bundle.tar.gz --seekdb-bin /path/to/seekdb
```

On Linux, the inputs need `$ORIGIN` runtime search paths. The preparation
script sets this path on the copied seekdb executable and validates the shared
libraries. Each platform module has its own `go.mod` and is published by a tag
prefixed with its directory, for example `native/linux-amd64/v1.4.0`. The root
module uses a root tag such as `v0.1.0`. Publish changed native bundles under
new, immutable versions.
