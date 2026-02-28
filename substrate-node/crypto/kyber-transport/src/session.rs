//! Secure session — AES-256-GCM encrypted communication channel.
//!
//! After the Kyber handshake completes, all data flows through this encrypted session.
//! Uses monotonically increasing nonces to prevent replay attacks.

use crate::error::KyberTransportError;
use crate::{MAX_MESSAGE_SIZE, MessageType, NONCE_SIZE, TAG_SIZE};

use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};

/// An established encrypted session using AES-256-GCM.
///
/// The session maintains a monotonic nonce counter for each direction
/// (send/receive) to prevent replay attacks. When the counter reaches
/// 2^32 - 1, the session must be rekeyed.
pub struct SecureSession {
    /// AES-256-GCM cipher instance for encryption.
    send_cipher: Aes256Gcm,
    /// AES-256-GCM cipher instance for decryption.
    recv_cipher: Aes256Gcm,
    /// Send nonce counter (monotonically increasing).
    send_nonce: u64,
    /// Receive nonce counter (monotonically increasing).
    recv_nonce: u64,
    /// Total bytes encrypted in this session (for metrics).
    bytes_encrypted: u64,
    /// Total bytes decrypted in this session (for metrics).
    bytes_decrypted: u64,
    /// Total messages sent.
    messages_sent: u64,
    /// Total messages received.
    messages_received: u64,
}

impl SecureSession {
    /// Create a new secure session from the derived session key.
    ///
    /// Both peers derive the same key from the handshake, so both sides
    /// use the same key for both send and receive ciphers.
    pub fn new(session_key: [u8; 32]) -> Self {
        let cipher = Aes256Gcm::new_from_slice(&session_key)
            .expect("32-byte key is always valid for AES-256-GCM");

        // Clone key for separate send/recv cipher instances
        let send_cipher = Aes256Gcm::new_from_slice(&session_key).unwrap();
        let recv_cipher = cipher;

        Self {
            send_cipher,
            recv_cipher,
            send_nonce: 0,
            recv_nonce: 0,
            bytes_encrypted: 0,
            bytes_decrypted: 0,
            messages_sent: 0,
            messages_received: 0,
        }
    }

    /// Encrypt a message for sending.
    ///
    /// Returns the framed message: `[type(1) | nonce(12) | ciphertext+tag(...)]`
    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<Vec<u8>, KyberTransportError> {
        if plaintext.len() > MAX_MESSAGE_SIZE {
            return Err(KyberTransportError::MessageTooLarge(
                plaintext.len(),
                MAX_MESSAGE_SIZE,
            ));
        }

        if self.send_nonce >= u64::MAX - 1 {
            return Err(KyberTransportError::NonceOverflow);
        }

        let nonce_bytes = self.build_nonce(self.send_nonce);
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = self
            .send_cipher
            .encrypt(nonce, plaintext)
            .map_err(|_| KyberTransportError::Encryption("AES-GCM encrypt failed".into()))?;

        // Frame: [type | nonce | ciphertext+tag]
        let mut frame = Vec::with_capacity(1 + NONCE_SIZE + ciphertext.len());
        frame.push(MessageType::EncryptedData as u8);
        frame.extend_from_slice(&nonce_bytes);
        frame.extend_from_slice(&ciphertext);

        self.send_nonce += 1;
        self.bytes_encrypted += plaintext.len() as u64;
        self.messages_sent += 1;

        Ok(frame)
    }

    /// Decrypt a received message.
    ///
    /// Input is the framed message: `[type(1) | nonce(12) | ciphertext+tag(...)]`
    pub fn decrypt(&mut self, frame: &[u8]) -> Result<Vec<u8>, KyberTransportError> {
        let min_size = 1 + NONCE_SIZE + TAG_SIZE;
        if frame.len() < min_size {
            return Err(KyberTransportError::Decryption);
        }

        let msg_type = MessageType::try_from(frame[0])?;
        if msg_type != MessageType::EncryptedData {
            return Err(KyberTransportError::UnexpectedMessage {
                expected: "EncryptedData".into(),
                got: format!("{msg_type:?}"),
            });
        }

        let nonce_bytes = &frame[1..1 + NONCE_SIZE];
        let ciphertext = &frame[1 + NONCE_SIZE..];

        // Verify nonce is what we expect (prevents replay)
        let expected_nonce = self.build_nonce(self.recv_nonce);
        if nonce_bytes != expected_nonce.as_slice() {
            return Err(KyberTransportError::Decryption);
        }

        let nonce = Nonce::from_slice(nonce_bytes);

        let plaintext = self
            .recv_cipher
            .decrypt(nonce, ciphertext)
            .map_err(|_| KyberTransportError::Decryption)?;

        self.recv_nonce += 1;
        self.bytes_decrypted += plaintext.len() as u64;
        self.messages_received += 1;

        Ok(plaintext)
    }

    /// Build a 12-byte nonce from a counter.
    ///
    /// Format: [0x00; 4] || counter_be(8)
    /// The first 4 bytes are zero-padded, last 8 are the big-endian counter.
    fn build_nonce(&self, counter: u64) -> [u8; NONCE_SIZE] {
        let mut nonce = [0u8; NONCE_SIZE];
        nonce[4..12].copy_from_slice(&counter.to_be_bytes());
        nonce
    }

    /// Get session statistics.
    pub fn stats(&self) -> SessionStats {
        SessionStats {
            messages_sent: self.messages_sent,
            messages_received: self.messages_received,
            bytes_encrypted: self.bytes_encrypted,
            bytes_decrypted: self.bytes_decrypted,
            send_nonce: self.send_nonce,
            recv_nonce: self.recv_nonce,
        }
    }

    /// Generate a rekey request message.
    ///
    /// Rekeying should happen periodically (e.g., every 2^32 messages)
    /// or after a configurable amount of data has been encrypted.
    pub fn rekey_request(&self) -> Vec<u8> {
        vec![MessageType::Rekey as u8]
    }

    /// Reset nonce counters after a successful rekey.
    pub fn reset_after_rekey(&mut self, new_key: [u8; 32]) {
        self.send_cipher = Aes256Gcm::new_from_slice(&new_key).unwrap();
        self.recv_cipher = Aes256Gcm::new_from_slice(&new_key).unwrap();
        self.send_nonce = 0;
        self.recv_nonce = 0;
    }
}

/// Session statistics for monitoring.
#[derive(Debug, Clone)]
pub struct SessionStats {
    pub messages_sent: u64,
    pub messages_received: u64,
    pub bytes_encrypted: u64,
    pub bytes_decrypted: u64,
    pub send_nonce: u64,
    pub recv_nonce: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_session_pair() -> (SecureSession, SecureSession) {
        let key = [0x42u8; 32];
        (SecureSession::new(key), SecureSession::new(key))
    }

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let (mut sender, mut receiver) = make_session_pair();

        let plaintext = b"Hello, quantum world!";
        let frame = sender.encrypt(plaintext).unwrap();
        let decrypted = receiver.decrypt(&frame).unwrap();

        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_multiple_messages() {
        let (mut sender, mut receiver) = make_session_pair();

        for i in 0..100 {
            let msg = format!("Message #{i}");
            let frame = sender.encrypt(msg.as_bytes()).unwrap();
            let decrypted = receiver.decrypt(&frame).unwrap();
            assert_eq!(decrypted, msg.as_bytes());
        }

        let stats = sender.stats();
        assert_eq!(stats.messages_sent, 100);
        assert_eq!(stats.send_nonce, 100);
    }

    #[test]
    fn test_tampered_ciphertext_fails() {
        let (mut sender, mut receiver) = make_session_pair();

        let plaintext = b"sensitive data";
        let mut frame = sender.encrypt(plaintext).unwrap();

        // Tamper with ciphertext (last byte before tag)
        let len = frame.len();
        frame[len - TAG_SIZE - 1] ^= 0xFF;

        assert!(receiver.decrypt(&frame).is_err());
    }

    #[test]
    fn test_replay_attack_fails() {
        let (mut sender, mut receiver) = make_session_pair();

        let frame1 = sender.encrypt(b"message 1").unwrap();
        let _frame2 = sender.encrypt(b"message 2").unwrap();

        // Decrypt first message
        receiver.decrypt(&frame1).unwrap();

        // Replaying the first message should fail (nonce mismatch)
        assert!(receiver.decrypt(&frame1).is_err());
    }

    #[test]
    fn test_message_too_large() {
        let (mut sender, _) = make_session_pair();

        let large_msg = vec![0u8; MAX_MESSAGE_SIZE + 1];
        assert!(matches!(
            sender.encrypt(&large_msg).unwrap_err(),
            KyberTransportError::MessageTooLarge(_, _)
        ));
    }

    #[test]
    fn test_empty_message() {
        let (mut sender, mut receiver) = make_session_pair();

        let frame = sender.encrypt(b"").unwrap();
        let decrypted = receiver.decrypt(&frame).unwrap();
        assert!(decrypted.is_empty());
    }

    #[test]
    fn test_max_size_message() {
        let (mut sender, mut receiver) = make_session_pair();

        let msg = vec![0xAB; MAX_MESSAGE_SIZE];
        let frame = sender.encrypt(&msg).unwrap();
        let decrypted = receiver.decrypt(&frame).unwrap();
        assert_eq!(decrypted, msg);
    }

    #[test]
    fn test_rekey() {
        let (mut sender, mut receiver) = make_session_pair();

        // Send some messages
        for _ in 0..10 {
            let frame = sender.encrypt(b"pre-rekey").unwrap();
            receiver.decrypt(&frame).unwrap();
        }

        // Rekey
        let new_key = [0x99u8; 32];
        sender.reset_after_rekey(new_key);
        receiver.reset_after_rekey(new_key);

        // Send more messages after rekey
        let frame = sender.encrypt(b"post-rekey").unwrap();
        let decrypted = receiver.decrypt(&frame).unwrap();
        assert_eq!(decrypted, b"post-rekey");

        // Nonce should be reset
        assert_eq!(sender.stats().send_nonce, 1);
    }

    #[test]
    fn test_different_keys_fail() {
        let mut sender = SecureSession::new([0xAA; 32]);
        let mut receiver = SecureSession::new([0xBB; 32]);

        let frame = sender.encrypt(b"hello").unwrap();
        assert!(receiver.decrypt(&frame).is_err());
    }

    #[test]
    fn test_nonce_format() {
        let session = SecureSession::new([0; 32]);
        let nonce = session.build_nonce(42);
        assert_eq!(&nonce[0..4], &[0, 0, 0, 0]);
        assert_eq!(&nonce[4..12], &42u64.to_be_bytes());
    }
}
