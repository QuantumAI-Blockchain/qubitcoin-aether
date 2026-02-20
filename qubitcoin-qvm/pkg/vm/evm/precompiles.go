package evm

import (
	"crypto/sha256"
	"fmt"
	"math/big"

	"golang.org/x/crypto/ripemd160"
)

// PrecompiledContract is the interface for EVM precompiled contracts (0x01-0x09).
type PrecompiledContract interface {
	// RequiredGas returns the gas cost for the given input.
	RequiredGas(input []byte) uint64
	// Run executes the precompile and returns the output.
	Run(input []byte) ([]byte, error)
}

// PrecompileMap maps addresses (1-9) to their precompiled contract implementations.
var PrecompileMap = map[uint64]PrecompiledContract{
	1: &ecRecover{},
	2: &sha256Hash{},
	3: &ripemd160Hash{},
	4: &dataCopy{},
	5: &bigModExp{},
	6: &bn256Add{},
	7: &bn256Mul{},
	8: &bn256Pairing{},
	9: &blake2F{},
}

// IsPrecompile returns true if the address is a precompiled contract.
func IsPrecompile(addr uint64) bool {
	_, ok := PrecompileMap[addr]
	return ok
}

// ExecutePrecompile runs a precompiled contract and returns the result.
func ExecutePrecompile(addr uint64, input []byte, gas uint64) ([]byte, uint64, error) {
	pc, ok := PrecompileMap[addr]
	if !ok {
		return nil, 0, fmt.Errorf("unknown precompile address: %d", addr)
	}

	requiredGas := pc.RequiredGas(input)
	if requiredGas > gas {
		return nil, gas, fmt.Errorf("out of gas in precompile %d: need %d, have %d", addr, requiredGas, gas)
	}

	output, err := pc.Run(input)
	if err != nil {
		return nil, requiredGas, err
	}

	return output, requiredGas, nil
}

// ─── 0x01: ecRecover ──────────────────────────────────────────────────
// Recovers the signer address from an ECDSA signature.
// Input: hash(32) + v(32) + r(32) + s(32) = 128 bytes
// Output: address(32) (left-padded 20-byte address)
type ecRecover struct{}

func (c *ecRecover) RequiredGas(_ []byte) uint64 { return 3000 }

func (c *ecRecover) Run(input []byte) ([]byte, error) {
	if len(input) < 128 {
		return make([]byte, 32), nil
	}
	// Placeholder: hash inputs to derive a pseudo-address
	h := sha256.Sum256(input[:128])
	output := make([]byte, 32)
	copy(output[12:], h[:20]) // left-pad to 32 bytes
	return output, nil
}

// ─── 0x02: SHA-256 ───────────────────────────────────────────────────
type sha256Hash struct{}

func (c *sha256Hash) RequiredGas(input []byte) uint64 {
	words := uint64((len(input) + 31) / 32)
	return 60 + 12*words
}

func (c *sha256Hash) Run(input []byte) ([]byte, error) {
	h := sha256.Sum256(input)
	return h[:], nil
}

// ─── 0x03: RIPEMD-160 ────────────────────────────────────────────────
type ripemd160Hash struct{}

func (c *ripemd160Hash) RequiredGas(input []byte) uint64 {
	words := uint64((len(input) + 31) / 32)
	return 600 + 120*words
}

func (c *ripemd160Hash) Run(input []byte) ([]byte, error) {
	h := ripemd160.New()
	h.Write(input)
	digest := h.Sum(nil) // 20 bytes
	// Left-pad to 32 bytes
	output := make([]byte, 32)
	copy(output[12:], digest)
	return output, nil
}

// ─── 0x04: Identity (data copy) ──────────────────────────────────────
type dataCopy struct{}

func (c *dataCopy) RequiredGas(input []byte) uint64 {
	words := uint64((len(input) + 31) / 32)
	return 15 + 3*words
}

func (c *dataCopy) Run(input []byte) ([]byte, error) {
	output := make([]byte, len(input))
	copy(output, input)
	return output, nil
}

// ─── 0x05: ModExp ────────────────────────────────────────────────────
// Computes base^exp % mod with arbitrary precision.
// Input: Bsize(32) + Esize(32) + Msize(32) + B(Bsize) + E(Esize) + M(Msize)
type bigModExp struct{}

func (c *bigModExp) RequiredGas(input []byte) uint64 {
	// Simplified gas: 200 base + dynamic based on sizes
	if len(input) < 96 {
		return 200
	}
	bLen := new(big.Int).SetBytes(getData(input, 0, 32)).Uint64()
	eLen := new(big.Int).SetBytes(getData(input, 32, 32)).Uint64()
	mLen := new(big.Int).SetBytes(getData(input, 64, 32)).Uint64()
	maxLen := bLen
	if eLen > maxLen {
		maxLen = eLen
	}
	if mLen > maxLen {
		maxLen = mLen
	}
	words := (maxLen + 7) / 8
	if words < 1 {
		words = 1
	}
	return 200 + words*words/10
}

func (c *bigModExp) Run(input []byte) ([]byte, error) {
	if len(input) < 96 {
		return make([]byte, 32), nil
	}

	bLen := new(big.Int).SetBytes(getData(input, 0, 32)).Uint64()
	eLen := new(big.Int).SetBytes(getData(input, 32, 32)).Uint64()
	mLen := new(big.Int).SetBytes(getData(input, 64, 32)).Uint64()

	if mLen == 0 {
		return make([]byte, 0), nil
	}

	base := new(big.Int).SetBytes(getData(input, 96, bLen))
	exp := new(big.Int).SetBytes(getData(input, 96+bLen, eLen))
	mod := new(big.Int).SetBytes(getData(input, 96+bLen+eLen, mLen))

	if mod.Sign() == 0 {
		return make([]byte, mLen), nil
	}

	result := new(big.Int).Exp(base, exp, mod)
	out := result.Bytes()

	// Left-pad to mLen
	if uint64(len(out)) < mLen {
		padded := make([]byte, mLen)
		copy(padded[mLen-uint64(len(out)):], out)
		return padded, nil
	}
	return out[:mLen], nil
}

// ─── 0x06: bn256Add ──────────────────────────────────────────────────
// Alt_bn128 elliptic curve point addition.
type bn256Add struct{}

func (c *bn256Add) RequiredGas(_ []byte) uint64 { return 150 }

func (c *bn256Add) Run(_ []byte) ([]byte, error) {
	// Stub: return identity point (0, 0)
	return make([]byte, 64), nil
}

// ─── 0x07: bn256ScalarMul ────────────────────────────────────────────
type bn256Mul struct{}

func (c *bn256Mul) RequiredGas(_ []byte) uint64 { return 6000 }

func (c *bn256Mul) Run(_ []byte) ([]byte, error) {
	return make([]byte, 64), nil
}

// ─── 0x08: bn256Pairing ──────────────────────────────────────────────
type bn256Pairing struct{}

func (c *bn256Pairing) RequiredGas(input []byte) uint64 {
	pairs := uint64(len(input)) / 192
	return 45000 + 34000*pairs
}

func (c *bn256Pairing) Run(_ []byte) ([]byte, error) {
	// Stub: return true (pairing check passes)
	result := make([]byte, 32)
	result[31] = 1
	return result, nil
}

// ─── 0x09: Blake2F ───────────────────────────────────────────────────
type blake2F struct{}

func (c *blake2F) RequiredGas(input []byte) uint64 {
	if len(input) < 4 {
		return 0
	}
	rounds := uint64(input[0])<<24 | uint64(input[1])<<16 | uint64(input[2])<<8 | uint64(input[3])
	return rounds
}

func (c *blake2F) Run(_ []byte) ([]byte, error) {
	return make([]byte, 64), nil
}

// ─── Helpers ──────────────────────────────────────────────────────────

// getData returns a slice from data, padded with zeros if necessary.
func getData(data []byte, offset, length uint64) []byte {
	result := make([]byte, length)
	if offset >= uint64(len(data)) {
		return result
	}
	end := offset + length
	if end > uint64(len(data)) {
		end = uint64(len(data))
	}
	copy(result, data[offset:end])
	return result
}
