//! Post-Quantum P2P Transport Layer — Hybrid Noise + ML-KEM-768 (Kyber)
//!
//! Provides quantum-resistant encryption for all P2P connections in the Qubitcoin network.
//!
//! ## Architecture
//!
//! The transport uses a **hybrid approach**:
//! 1. Standard Noise XX handshake establishes classical connection (X25519)
//! 2. Post-handshake: Kyber key exchange adds post-quantum layer
//! 3. Session key derived from both classical and PQ shared secrets via HKDF
//! 4. All data encrypted with AES-256-GCM using the combined session key
//!
//! If a quantum computer breaks X25519, the Kyber layer still protects the session.
//! If Kyber is broken classically, the Noise layer still protects.

pub mod handshake;
pub mod session;
pub mod transport;
pub mod error;

pub use error::KyberTransportError;
pub use handshake::{KyberHandshake, HandshakeRole};
pub use session::SecureSession;
pub use transport::KyberTransport;

/// ML-KEM-768 security level (NIST Level 3 — equivalent to AES-192).
/// Chosen for balance between security margin and performance.
pub const KYBER_SECURITY_LEVEL: &str = "ML-KEM-768";

/// AES-256-GCM nonce size in bytes (96 bits as per NIST SP 800-38D).
pub const NONCE_SIZE: usize = 12;

/// AES-256-GCM tag size in bytes (128 bits).
pub const TAG_SIZE: usize = 16;

/// Maximum message size before fragmentation (64 KB).
pub const MAX_MESSAGE_SIZE: usize = 65_536;

/// HKDF info string for session key derivation.
pub const HKDF_INFO: &[u8] = b"qubitcoin-kyber-session-v1";

/// Handshake protocol version.
pub const PROTOCOL_VERSION: u8 = 1;

/// Handshake message types.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum MessageType {
    /// Initiator sends Kyber public key (encapsulation key).
    KyberPubKey = 0x01,
    /// Responder sends ciphertext (encapsulated shared secret).
    KyberCiphertext = 0x02,
    /// Handshake complete acknowledgment.
    HandshakeComplete = 0x03,
    /// Encrypted application data.
    EncryptedData = 0x10,
    /// Session rekeying request.
    Rekey = 0x20,
}

impl TryFrom<u8> for MessageType {
    type Error = KyberTransportError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x01 => Ok(Self::KyberPubKey),
            0x02 => Ok(Self::KyberCiphertext),
            0x03 => Ok(Self::HandshakeComplete),
            0x10 => Ok(Self::EncryptedData),
            0x20 => Ok(Self::Rekey),
            _ => Err(KyberTransportError::InvalidMessageType(value)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_message_type_roundtrip() {
        let types = [
            MessageType::KyberPubKey,
            MessageType::KyberCiphertext,
            MessageType::HandshakeComplete,
            MessageType::EncryptedData,
            MessageType::Rekey,
        ];
        for mt in types {
            let byte = mt as u8;
            let decoded = MessageType::try_from(byte).unwrap();
            assert_eq!(mt, decoded);
        }
    }

    #[test]
    fn test_invalid_message_type() {
        assert!(MessageType::try_from(0xFF).is_err());
    }

    #[test]
    fn test_constants() {
        assert_eq!(NONCE_SIZE, 12);
        assert_eq!(TAG_SIZE, 16);
        assert_eq!(MAX_MESSAGE_SIZE, 65_536);
        assert_eq!(PROTOCOL_VERSION, 1);
    }
}
