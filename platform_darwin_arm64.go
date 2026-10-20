//go:build darwin && arm64

package seekdb

import native "github.com/Mai-icy/seekdb-go-bindings/native/darwin-arm64"

func platformBundle() []byte     { return native.Archive }
func platformLibrary() string    { return "libseekdb.dylib" }
func platformExecutable() string { return "seekdb" }
