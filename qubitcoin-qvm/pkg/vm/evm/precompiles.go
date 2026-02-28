package evm

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/sha256"
	"fmt"
	"math/big"

	"golang.org/x/crypto/ripemd160"
	"golang.org/x/crypto/sha3"
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
	// Pad input to 128 bytes if shorter
	padded := make([]byte, 128)
	copy(padded, input)

	// Extract: hash(32) + v(32) + r(32) + s(32)
	hash := padded[:32]
	vBig := new(big.Int).SetBytes(padded[32:64])
	r := new(big.Int).SetBytes(padded[64:96])
	s := new(big.Int).SetBytes(padded[96:128])

	// v must be 27 or 28 (Ethereum convention)
	v := byte(vBig.Uint64())
	if v != 27 && v != 28 {
		return make([]byte, 32), nil // invalid v, return zero
	}

	// Validate r and s are in [1, secp256k1.N)
	secp256k1N, _ := new(big.Int).SetString("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
	if r.Sign() <= 0 || r.Cmp(secp256k1N) >= 0 {
		return make([]byte, 32), nil
	}
	if s.Sign() <= 0 || s.Cmp(secp256k1N) >= 0 {
		return make([]byte, 32), nil
	}

	// Recover the public key from the signature
	// Recovery ID = v - 27 (0 or 1)
	recoveryID := v - 27

	// Reconstruct the 65-byte signature: r(32) + s(32) + recoveryID(1)
	sig := make([]byte, 65)
	rBytes := r.Bytes()
	sBytes := s.Bytes()
	copy(sig[32-len(rBytes):32], rBytes)
	copy(sig[64-len(sBytes):64], sBytes)
	sig[64] = recoveryID

	// Use secp256k1 curve (Ethereum-compatible)
	curve := Secp256k1()

	// Recover public key using standard ECDSA verification approach:
	// Given (hash, r, s, v), reconstruct the point R from r and recovery bit,
	// then compute pubkey = (s*R - hash*G) / r
	pubKey, err := recoverPublicKey(curve, hash, r, s, int(recoveryID))
	if err != nil || pubKey == nil {
		return make([]byte, 32), nil
	}

	// Derive Ethereum address: keccak256(pubkey_uncompressed[1:])[12:]
	pubBytes := elliptic.Marshal(curve, pubKey.X, pubKey.Y)
	if len(pubBytes) < 2 {
		return make([]byte, 32), nil
	}
	// Hash the uncompressed public key (without 0x04 prefix)
	addrHash := keccak256(pubBytes[1:])

	output := make([]byte, 32)
	copy(output[12:], addrHash[12:32]) // last 20 bytes = address
	return output, nil
}

// recoverPublicKey recovers an ECDSA public key from a signature.
// This implements the EC point recovery algorithm for signature verification.
func recoverPublicKey(curve elliptic.Curve, hash []byte, r, s *big.Int, recoveryID int) (*ecdsa.PublicKey, error) {
	// Get curve parameters
	params := curve.Params()
	byteLen := (params.BitSize + 7) / 8

	// Step 1: Compute R point from r value
	// x = r + recoveryID * N (we only use recoveryID 0 or 1, and for 0, x = r)
	rx := new(big.Int).Set(r)
	if recoveryID >= 2 {
		rx.Add(rx, params.N)
	}

	// Check rx is valid for the curve
	if rx.Cmp(params.P) >= 0 {
		return nil, fmt.Errorf("rx out of range")
	}

	// Compute y from x on the curve: y^2 = x^3 + b (mod p)
	// For secp256k1: a = 0, b = 7, so y^2 = x^3 + 7
	x3 := new(big.Int).Mul(rx, rx)
	x3.Mul(x3, rx)
	x3.Mod(x3, params.P)

	// y^2 = x^3 + b (mod p) for secp256k1
	ySquared := new(big.Int).Add(x3, params.B)
	ySquared.Mod(ySquared, params.P)

	// Compute y = sqrt(y^2) mod p
	ry := new(big.Int).ModSqrt(ySquared, params.P)
	if ry == nil {
		return nil, fmt.Errorf("no valid y for given r")
	}

	// Choose correct y parity based on recoveryID
	if ry.Bit(0) != uint(recoveryID&1) {
		ry.Sub(params.P, ry)
	}

	// Verify point is on curve
	if !curve.IsOnCurve(rx, ry) {
		return nil, fmt.Errorf("recovered point not on curve")
	}

	// Step 2: Compute public key = r^(-1) * (s*R - e*G)
	e := new(big.Int).SetBytes(hash)
	_ = byteLen // used for padding if needed

	rInv := new(big.Int).ModInverse(r, params.N)
	if rInv == nil {
		return nil, fmt.Errorf("r has no modular inverse")
	}

	// s * R
	sRx, sRy := curve.ScalarMult(rx, ry, s.Bytes())

	// e * G
	eGx, eGy := curve.ScalarBaseMult(e.Bytes())

	// s*R - e*G = s*R + (-e*G)
	negEGy := new(big.Int).Sub(params.P, eGy)
	sumX, sumY := curve.Add(sRx, sRy, eGx, negEGy)

	// pubkey = rInv * (s*R - e*G)
	pubX, pubY := curve.ScalarMult(sumX, sumY, rInv.Bytes())

	if pubX.Sign() == 0 && pubY.Sign() == 0 {
		return nil, fmt.Errorf("recovered null public key")
	}

	return &ecdsa.PublicKey{Curve: curve, X: pubX, Y: pubY}, nil
}

// keccak256 computes Keccak-256 hash (Ethereum-compatible).
func keccak256(data []byte) []byte {
	h := sha3.NewLegacyKeccak256()
	h.Write(data)
	return h.Sum(nil)
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
	// EIP-198 gas formula: max(200, mult_complexity * iter_count / 3)
	if len(input) < 96 {
		return 200
	}
	bLen := new(big.Int).SetBytes(getData(input, 0, 32)).Uint64()
	eLen := new(big.Int).SetBytes(getData(input, 32, 32)).Uint64()
	mLen := new(big.Int).SetBytes(getData(input, 64, 32)).Uint64()

	// mult_complexity based on max(bLen, mLen)
	maxLen := bLen
	if mLen > maxLen {
		maxLen = mLen
	}
	var multComplexity uint64
	if maxLen <= 64 {
		multComplexity = maxLen * maxLen
	} else if maxLen <= 1024 {
		multComplexity = maxLen*maxLen/4 + 96*maxLen - 3072
	} else {
		multComplexity = maxLen*maxLen/16 + 480*maxLen - 199680
	}

	// Adjusted exponent length
	var adjExpLen uint64
	if eLen <= 32 {
		expHead := getData(input, 96+bLen, eLen)
		expHeadInt := new(big.Int).SetBytes(expHead)
		bitLen := expHeadInt.BitLen()
		if bitLen > 1 {
			adjExpLen = uint64(bitLen - 1)
		}
	} else {
		expHead := getData(input, 96+bLen, 32)
		expHeadInt := new(big.Int).SetBytes(expHead)
		bitLen := expHeadInt.BitLen()
		adjExpLen = 8 * (eLen - 32)
		if bitLen > 1 {
			adjExpLen += uint64(bitLen - 1)
		}
	}

	iterCount := adjExpLen
	if iterCount < 1 {
		iterCount = 1
	}

	gas := multComplexity * iterCount / 3
	if gas < 200 {
		return 200
	}
	return gas
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

// ─── secp256k1 Curve ──────────────────────────────────────────────────
// Ethereum uses secp256k1, not P-256. We define the curve parameters
// here to avoid adding an external dependency like btcec.

var secp256k1once = &elliptic.CurveParams{
	P:       fromHex("fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f"),
	N:       fromHex("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141"),
	B:       big.NewInt(7),
	Gx:      fromHex("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),
	Gy:      fromHex("483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8"),
	BitSize: 256,
	Name:    "secp256k1",
}

// Secp256k1 returns the secp256k1 elliptic curve parameters used by Ethereum.
func Secp256k1() elliptic.Curve {
	return secp256k1once
}

func fromHex(s string) *big.Int {
	v, _ := new(big.Int).SetString(s, 16)
	return v
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
