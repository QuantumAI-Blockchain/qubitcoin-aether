#!/usr/bin/env python3
"""
Qubitcoin Node Runner
Simple entry point to start the node
"""
import sys

# QVM executes EVM bytecode with 256-bit integers that can produce
# very large numbers (e.g., ERC-1967 storage slots). Remove Python's
# integer-to-string conversion limit to avoid ValueError.
sys.set_int_max_str_digits(0)

if __name__ == "__main__":
    from qubitcoin import main
    main()
