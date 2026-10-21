//go:build linux && arm64

package seekdb

import native "github.com/Mai-icy/seekdb-go-bindings/native/linux-arm64"

func platformBundle() []byte       { return native.Archive }
func platformLibrary() string      { return "libseekdb.so" }
func platformExecutable() string   { return "seekdb" }
func platformServerBinary() string { return "seekdb.bin" }
