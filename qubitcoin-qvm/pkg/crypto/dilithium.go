// Package crypto implements post-quantum cryptographic primitives.
//
// Provides:
//   - CRYSTALS-Dilithium3 signatures (2420 bytes)
//   - CRYSTALS-Kyber1024 key encapsulation
//   - Groth16 zkSNARK proof generation/verification
//   - Keccak-256 hashing (EVM compatible)
//
// All cryptographic operations use the cloudflare/circl library for
// post-quantum algorithm implementations.
package crypto

// DilithiumKeyPair holds a Dilithium3 key pair.
type DilithiumKeyPair struct {
	PublicKey  []byte // ~1952 bytes
	PrivateKey []byte // ~4000 bytes
	Address    [20]byte
}

// DilithiumSignature is a Dilithium3 signature (~3293 bytes).
type DilithiumSignature struct {
	Data      []byte
	PublicKey []byte
}

// KyberKeyPair holds a Kyber1024 key pair for key encapsulation.
type KyberKeyPair struct {
	PublicKey  []byte
	PrivateKey []byte
}

// ZKProof represents a Groth16 zkSNARK proof.
type ZKProof struct {
	A     [2][]byte // G1 point
	B     [4][]byte // G2 point (2x2)
	C     [2][]byte // G1 point
	Input [][]byte  // public inputs
}
