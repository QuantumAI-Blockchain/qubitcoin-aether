// Package main implements the QVM CLI tool.
//
// The QVM CLI provides commands for contract deployment, interaction,
// and debugging against a running QVM server.
//
// Usage:
//
//	qvm-cli deploy --bytecode 0x... --gas 1000000
//	qvm-cli call --contract 0x... --function transfer --args ...
//	qvm-cli debug --bytecode 0x... --step
package main

import (
	"fmt"
	"os"
)

var version = "dev"

func main() {
	if len(os.Args) > 1 && os.Args[1] == "version" {
		fmt.Printf("qvm-cli %s\n", version)
		os.Exit(0)
	}

	fmt.Println("qvm-cli — QVM contract deployment and interaction tool")
	fmt.Println("Not yet implemented. See cmd/qvm-cli/ for planned features.")
	os.Exit(0)
}
