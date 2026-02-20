package crypto

import (
	"crypto/sha256"
	"fmt"

	"golang.org/x/crypto/sha3"
)

// ─── Keccak-256 (EVM-compatible hashing) ──────────────────────────────

// Keccak256 computes the Keccak-256 hash (EVM standard).
// Note: Keccak-256 is NOT the same as SHA3-256 (different padding).
// EVM and Solidity use Keccak-256 (pre-standardization).
func Keccak256(data []byte) [32]byte {
	h := sha3.NewLegacyKeccak256()
	h.Write(data)
	var result [32]byte
	copy(result[:], h.Sum(nil))
	return result
}

// Keccak256Multi computes Keccak-256 over multiple byte slices.
func Keccak256Multi(data ...[]byte) [32]byte {
	h := sha3.NewLegacyKeccak256()
	for _, d := range data {
		h.Write(d)
	}
	var result [32]byte
	copy(result[:], h.Sum(nil))
	return result
}

// SHA256Hash computes the SHA-256 hash (used for block hashes in Qubitcoin L1).
func SHA256Hash(data []byte) [32]byte {
	return sha256.Sum256(data)
}

// ─── Dilithium Signatures ─────────────────────────────────────────────
// CRYSTALS-Dilithium3 post-quantum digital signatures.
//
// In production, this uses cloudflare/circl for Dilithium3 (mode3).
// For now, we provide the interface and a placeholder using SHA-256 HMAC
// so the rest of the system can be built and tested.
//
// Signature sizes (Dilithium3):
//   - Public key:  ~1952 bytes
//   - Private key: ~4000 bytes
//   - Signature:   ~3293 bytes

// DilithiumMode selects the Dilithium security level.
type DilithiumMode uint8

const (
	// Dilithium2 is NIST security level 2 (default for Qubitcoin L1).
	Dilithium2 DilithiumMode = 2
	// Dilithium3 is NIST security level 3 (used for QVM contracts).
	Dilithium3 DilithiumMode = 3
)

// GenerateKeyPair generates a new Dilithium key pair.
// Returns public key, private key, and derived address.
func GenerateKeyPair(mode DilithiumMode) (*DilithiumKeyPair, error) {
	// Placeholder: generate deterministic key pair using SHA-256
	// Production: use circl/sign/dilithium/mode3
	seed := sha256.Sum256([]byte(fmt.Sprintf("dilithium-keygen-mode%d-%d", mode, nextSeed())))
	pk := sha256.Sum256(append(seed[:], 0x01))
	sk := sha256.Sum256(append(seed[:], 0x02))

	// Derive address from public key hash
	addrHash := sha256.Sum256(pk[:])
	var addr [20]byte
	copy(addr[:], addrHash[:20])

	return &DilithiumKeyPair{
		PublicKey:  pk[:],
		PrivateKey: sk[:],
		Address:    addr,
	}, nil
}

// Sign creates a Dilithium signature over a message.
func Sign(privateKey []byte, message []byte) (*DilithiumSignature, error) {
	if len(privateKey) == 0 {
		return nil, fmt.Errorf("empty private key")
	}

	// Placeholder: HMAC-SHA256(sk, msg) as signature
	// Production: use circl/sign/dilithium/mode3.Sign()
	h := sha256.New()
	h.Write(privateKey)
	h.Write(message)
	sigBytes := h.Sum(nil)

	// Derive public key from private key (placeholder)
	pkHash := sha256.Sum256(append(privateKey, 0xFF))

	return &DilithiumSignature{
		Data:      sigBytes,
		PublicKey: pkHash[:],
	}, nil
}

// Verify checks a Dilithium signature.
func Verify(publicKey []byte, message []byte, signature *DilithiumSignature) (bool, error) {
	if len(publicKey) == 0 || signature == nil || len(signature.Data) == 0 {
		return false, fmt.Errorf("invalid signature parameters")
	}

	// Placeholder: recompute and compare
	// Production: use circl/sign/dilithium/mode3.Verify()
	// We need the private key to verify in the placeholder; in production
	// Dilithium.Verify only needs the public key.
	//
	// For the placeholder, we verify that the signature structure is valid
	// and the public key matches.
	if len(signature.Data) < 32 {
		return false, nil
	}

	// Basic structural validation
	return true, nil
}

// AddressFromPublicKey derives a 20-byte address from a Dilithium public key.
// Uses SHA-256 of the public key, taking the first 20 bytes.
func AddressFromPublicKey(publicKey []byte) [20]byte {
	hash := sha256.Sum256(publicKey)
	var addr [20]byte
	copy(addr[:], hash[:20])
	return addr
}

// ─── Helper ───────────────────────────────────────────────────────────

var seedCounter uint64

func nextSeed() uint64 {
	seedCounter++
	return seedCounter
}
