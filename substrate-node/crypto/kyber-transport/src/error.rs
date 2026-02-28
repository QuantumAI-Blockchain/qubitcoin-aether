//! Error types for the Kyber transport layer.

use thiserror::Error;

/// Errors that can occur during Kyber transport operations.
#[derive(Debug, Error)]
pub enum KyberTransportError {
    /// Invalid message type byte received.
    #[error("invalid message type: 0x{0:02x}")]
    InvalidMessageType(u8),

    /// ML-KEM key generation failed.
    #[error("ML-KEM key generation failed: {0}")]
    KeyGeneration(String),

    /// ML-KEM encapsulation failed.
    #[error("ML-KEM encapsulation failed: {0}")]
    Encapsulation(String),

    /// ML-KEM decapsulation failed.
    #[error("ML-KEM decapsulation failed: {0}")]
    Decapsulation(String),

    /// AES-GCM encryption failed.
    #[error("AES-GCM encryption failed: {0}")]
    Encryption(String),

    /// AES-GCM decryption failed (tampered or wrong key).
    #[error("AES-GCM decryption failed — ciphertext may be tampered")]
    Decryption,

    /// HKDF key derivation failed.
    #[error("HKDF key derivation failed: {0}")]
    KeyDerivation(String),

    /// Handshake protocol error.
    #[error("handshake error: {0}")]
    Handshake(String),

    /// Handshake not completed before sending data.
    #[error("session not established — handshake not complete")]
    SessionNotEstablished,

    /// Message too large.
    #[error("message size {0} exceeds maximum {1}")]
    MessageTooLarge(usize, usize),

    /// Unexpected handshake message.
    #[error("unexpected message type during handshake: expected {expected:?}, got {got:?}")]
    UnexpectedMessage {
        expected: String,
        got: String,
    },

    /// Protocol version mismatch.
    #[error("protocol version mismatch: local={local}, remote={remote}")]
    VersionMismatch {
        local: u8,
        remote: u8,
    },

    /// Nonce overflow — session must be rekeyed.
    #[error("nonce counter overflow — session must be rekeyed")]
    NonceOverflow,

    /// I/O error from underlying transport.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}
