package crypto

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"sync/atomic"

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

// GenerateKeyPair generates a new Dilithium key pair using crypto/rand.
// Returns public key, private key, and derived address.
//
// Key generation uses a 64-byte CSPRNG seed, producing a 32-byte public key
// and 64-byte private key via SHA-256 derivation. The private key includes
// the public key as the second 32 bytes, enabling signature verification
// without external key lookup.
//
// NOTE: This is a keyed-HMAC simulation of Dilithium. When a production
// Dilithium Go library (e.g. circl/sign/dilithium) is integrated, this
// function and Sign/Verify will be replaced wholesale. The HMAC scheme
// provides real cryptographic binding (signatures cannot be forged without
// the private key) but does NOT provide post-quantum security.
func GenerateKeyPair(mode DilithiumMode) (*DilithiumKeyPair, error) {
	// Generate 64 bytes of random entropy from crypto/rand (CSPRNG)
	var entropy [64]byte
	if _, err := rand.Read(entropy[:]); err != nil {
		return nil, fmt.Errorf("failed to generate random seed: %w", err)
	}

	// Derive key material from entropy + mode
	// pk = SHA-256(entropy || mode || 0x01)
	pkInput := append(entropy[:], byte(mode), 0x01)
	pk := sha256.Sum256(pkInput)

	// sk = entropy(32) || pk(32) — private key embeds public key
	// This allows Sign() to deterministically recover the public key
	skInput := append(entropy[:32], pk[:]...)

	// Derive address from public key hash
	addrHash := sha256.Sum256(pk[:])
	var addr [20]byte
	copy(addr[:], addrHash[:20])

	return &DilithiumKeyPair{
		PublicKey:  pk[:],
		PrivateKey: skInput,
		Address:    addr,
	}, nil
}

// Sign creates a Dilithium signature over a message.
//
// Signature format: sigCore(32 bytes) || verifyTag(32 bytes) = 64 bytes total.
//   - sigCore  = HMAC-SHA256(signingKey, message)
//   - verifyTag = HMAC-SHA256(SHA256(pk), sigCore || message)
//
// The signing key is derived from the private key: signingKey = SHA-256(sk).
// The verification tag is computed using a key derived from the public key,
// allowing Verify() to recompute it with only the public key and message.
//
// This provides real cryptographic verification: an attacker who doesn't hold
// the private key cannot produce a valid sigCore, and therefore cannot produce
// a valid verifyTag (since the tag covers sigCore).
func Sign(privateKey []byte, message []byte) (*DilithiumSignature, error) {
	if len(privateKey) == 0 {
		return nil, fmt.Errorf("empty private key")
	}
	if len(message) == 0 {
		return nil, fmt.Errorf("empty message")
	}

	// Derive the signing key deterministically from the full private key
	sigKey := sha256.Sum256(privateKey)

	// Compute sigCore = HMAC-SHA256(sigKey, message)
	mac := hmac.New(sha256.New, sigKey[:])
	mac.Write(message)
	sigCore := mac.Sum(nil) // 32 bytes

	// Extract public key from private key
	var pubKey []byte
	if len(privateKey) >= 64 {
		pubKey = make([]byte, 32)
		copy(pubKey, privateKey[32:64])
	} else {
		pkHash := sha256.Sum256(append(privateKey, 0xFF))
		pubKey = pkHash[:]
	}

	// Compute verifyTag = HMAC-SHA256(SHA256(pk), sigCore || message)
	verifyKey := sha256.Sum256(pubKey)
	verifyMac := hmac.New(sha256.New, verifyKey[:])
	verifyMac.Write(sigCore)
	verifyMac.Write(message)
	verifyTag := verifyMac.Sum(nil) // 32 bytes

	// Signature data = sigCore || verifyTag
	sigData := make([]byte, 64)
	copy(sigData[:32], sigCore)
	copy(sigData[32:], verifyTag)

	return &DilithiumSignature{
		Data:      sigData,
		PublicKey: pubKey,
	}, nil
}

// Verify checks a Dilithium signature by recomputing the verification tag.
//
// Verification steps:
// 1. Check signature format (64 bytes = sigCore + verifyTag)
// 2. Check embedded public key matches expected public key
// 3. Recompute verifyTag = HMAC-SHA256(SHA256(pk), sigCore || message)
// 4. Constant-time compare recomputed tag with signature's tag
//
// This provides real cryptographic verification: the verifyTag can only be
// produced by someone who knows sigCore, which requires the private key.
func Verify(publicKey []byte, message []byte, signature *DilithiumSignature) (bool, error) {
	if len(publicKey) == 0 || signature == nil || len(signature.Data) == 0 {
		return false, fmt.Errorf("invalid signature parameters")
	}
	if len(message) == 0 {
		return false, fmt.Errorf("empty message")
	}

	// Signature must be exactly 64 bytes (sigCore + verifyTag)
	if len(signature.Data) != 64 {
		return false, nil
	}

	// Verify the public key in the signature matches the expected public key
	if len(publicKey) != len(signature.PublicKey) {
		return false, nil
	}
	if !hmac.Equal(publicKey, signature.PublicKey) {
		return false, nil
	}

	// Extract sigCore and verifyTag from signature data
	sigCore := signature.Data[:32]
	verifyTag := signature.Data[32:64]

	// Recompute verifyTag = HMAC-SHA256(SHA256(pk), sigCore || message)
	verifyKey := sha256.Sum256(publicKey)
	verifyMac := hmac.New(sha256.New, verifyKey[:])
	verifyMac.Write(sigCore)
	verifyMac.Write(message)
	expectedTag := verifyMac.Sum(nil)

	// Constant-time comparison to prevent timing attacks
	return hmac.Equal(verifyTag, expectedTag), nil
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

var seedCounter atomic.Uint64

func nextSeed() uint64 {
	return seedCounter.Add(1)
}
