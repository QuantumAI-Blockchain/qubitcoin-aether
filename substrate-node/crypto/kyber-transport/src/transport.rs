//! High-level Kyber transport — combines handshake + session into a usable API.
//!
//! This module provides the `KyberTransport` struct that manages the full lifecycle:
//! 1. Perform Kyber handshake (generate keys, exchange, derive session key)
//! 2. Transition to encrypted session
//! 3. Encrypt/decrypt messages transparently
//!
//! ## Usage
//!
//! ```rust,no_run
//! use qbc_kyber_transport::{KyberTransport, HandshakeRole};
//!
//! // Initiator side
//! let mut initiator = KyberTransport::new(HandshakeRole::Initiator, None);
//! let pubkey_msg = initiator.start_handshake().unwrap();
//! // ... send pubkey_msg to peer, receive ciphertext_msg ...
//! // initiator.process_handshake_message(&ciphertext_msg).unwrap();
//! // let complete_msg = initiator.finalize_handshake().unwrap();
//! ```

use crate::error::KyberTransportError;
use crate::handshake::{HandshakeRole, KyberHandshake};
use crate::session::SecureSession;

/// Transport state machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransportState {
    /// Initial state — no handshake started.
    New,
    /// Handshake in progress — waiting for peer messages.
    Handshaking,
    /// Handshake complete — secure session established.
    Established,
    /// Session closed or errored.
    Closed,
}

/// High-level Kyber-encrypted transport.
///
/// Manages the complete lifecycle from handshake to encrypted data transfer.
pub struct KyberTransport {
    state: TransportState,
    handshake: KyberHandshake,
    session: Option<SecureSession>,
}

impl KyberTransport {
    /// Create a new transport.
    ///
    /// - `role`: Whether this peer initiates or responds.
    /// - `classical_secret`: Optional shared secret from a classical handshake (Noise).
    pub fn new(role: HandshakeRole, classical_secret: Option<Vec<u8>>) -> Self {
        Self {
            state: TransportState::New,
            handshake: KyberHandshake::new(role, classical_secret),
            session: None,
        }
    }

    /// Get the current transport state.
    pub fn state(&self) -> TransportState {
        self.state
    }

    /// Get the handshake role.
    pub fn role(&self) -> HandshakeRole {
        self.handshake.role()
    }

    /// Start the handshake (initiator only).
    ///
    /// Returns the first handshake message (Kyber public key) to send to the peer.
    pub fn start_handshake(&mut self) -> Result<Vec<u8>, KyberTransportError> {
        if self.state != TransportState::New {
            return Err(KyberTransportError::Handshake(
                "handshake already started".into(),
            ));
        }

        let msg = self.handshake.initiator_generate_pubkey()?;
        self.state = TransportState::Handshaking;
        Ok(msg)
    }

    /// Process an incoming handshake message from the peer.
    ///
    /// - For responder: processes the initiator's pubkey, returns ciphertext to send back.
    /// - For initiator: processes the responder's ciphertext, returns None (proceed to finalize).
    pub fn process_handshake_message(
        &mut self,
        msg: &[u8],
    ) -> Result<Option<Vec<u8>>, KyberTransportError> {
        match self.handshake.role() {
            HandshakeRole::Responder => {
                self.state = TransportState::Handshaking;
                let response = self.handshake.responder_encapsulate(msg)?;
                Ok(Some(response))
            }
            HandshakeRole::Initiator => {
                self.handshake.initiator_decapsulate(msg)?;
                Ok(None)
            }
        }
    }

    /// Finalize the handshake and establish the secure session.
    ///
    /// Returns the handshake-complete message to send to the peer.
    pub fn finalize_handshake(&mut self) -> Result<Vec<u8>, KyberTransportError> {
        let session_key = self.handshake.derive_session_key()?;
        let is_initiator = self.handshake.role() == HandshakeRole::Initiator;
        self.session = Some(SecureSession::new(session_key, is_initiator));
        self.state = TransportState::Established;

        Ok(self.handshake.complete_message())
    }

    /// Verify the peer's handshake-complete message.
    pub fn verify_peer_complete(&self, msg: &[u8]) -> Result<(), KyberTransportError> {
        KyberHandshake::verify_complete(msg)
    }

    /// Encrypt a message for sending over the established session.
    pub fn encrypt(&mut self, plaintext: &[u8]) -> Result<Vec<u8>, KyberTransportError> {
        let session = self
            .session
            .as_mut()
            .ok_or(KyberTransportError::SessionNotEstablished)?;
        session.encrypt(plaintext)
    }

    /// Decrypt a received message from the established session.
    pub fn decrypt(&mut self, frame: &[u8]) -> Result<Vec<u8>, KyberTransportError> {
        let session = self
            .session
            .as_mut()
            .ok_or(KyberTransportError::SessionNotEstablished)?;
        session.decrypt(frame)
    }

    /// Get session statistics (only available after handshake).
    pub fn stats(&self) -> Option<crate::session::SessionStats> {
        self.session.as_ref().map(|s| s.stats())
    }

    /// Close the transport.
    pub fn close(&mut self) {
        self.state = TransportState::Closed;
        self.session = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_full_transport_lifecycle() {
        // Create initiator and responder
        let mut initiator = KyberTransport::new(HandshakeRole::Initiator, None);
        let mut responder = KyberTransport::new(HandshakeRole::Responder, None);

        assert_eq!(initiator.state(), TransportState::New);
        assert_eq!(responder.state(), TransportState::New);

        // Step 1: Initiator starts handshake
        let pubkey_msg = initiator.start_handshake().unwrap();
        assert_eq!(initiator.state(), TransportState::Handshaking);

        // Step 2: Responder processes pubkey and generates ciphertext
        let ct_msg = responder.process_handshake_message(&pubkey_msg).unwrap().unwrap();

        // Step 3: Initiator processes ciphertext
        let response = initiator.process_handshake_message(&ct_msg).unwrap();
        assert!(response.is_none()); // Initiator has nothing to send back

        // Step 4: Both finalize
        let init_complete = initiator.finalize_handshake().unwrap();
        let resp_complete = responder.finalize_handshake().unwrap();

        // Step 5: Verify completion
        responder.verify_peer_complete(&init_complete).unwrap();
        initiator.verify_peer_complete(&resp_complete).unwrap();

        assert_eq!(initiator.state(), TransportState::Established);
        assert_eq!(responder.state(), TransportState::Established);

        // Step 6: Exchange encrypted messages
        let frame = initiator.encrypt(b"Hello from initiator!").unwrap();
        let plaintext = responder.decrypt(&frame).unwrap();
        assert_eq!(plaintext, b"Hello from initiator!");

        let frame = responder.encrypt(b"Hello from responder!").unwrap();
        let plaintext = initiator.decrypt(&frame).unwrap();
        assert_eq!(plaintext, b"Hello from responder!");

        // Step 7: Check stats
        let init_stats = initiator.stats().unwrap();
        assert_eq!(init_stats.messages_sent, 1);
        assert_eq!(init_stats.messages_received, 1);
    }

    #[test]
    fn test_transport_with_classical_secret() {
        let classical = vec![0x42; 32];

        let mut initiator = KyberTransport::new(HandshakeRole::Initiator, Some(classical.clone()));
        let mut responder = KyberTransport::new(HandshakeRole::Responder, Some(classical));

        let pubkey_msg = initiator.start_handshake().unwrap();
        let ct_msg = responder.process_handshake_message(&pubkey_msg).unwrap().unwrap();
        initiator.process_handshake_message(&ct_msg).unwrap();

        initiator.finalize_handshake().unwrap();
        responder.finalize_handshake().unwrap();

        // Bidirectional communication works
        let frame = initiator.encrypt(b"hybrid encryption").unwrap();
        let plaintext = responder.decrypt(&frame).unwrap();
        assert_eq!(plaintext, b"hybrid encryption");
    }

    #[test]
    fn test_encrypt_before_handshake_fails() {
        let mut transport = KyberTransport::new(HandshakeRole::Initiator, None);
        assert!(matches!(
            transport.encrypt(b"too early").unwrap_err(),
            KyberTransportError::SessionNotEstablished
        ));
    }

    #[test]
    fn test_close() {
        let mut transport = KyberTransport::new(HandshakeRole::Initiator, None);
        transport.close();
        assert_eq!(transport.state(), TransportState::Closed);
        assert!(transport.stats().is_none());
    }

    #[test]
    fn test_double_handshake_start_fails() {
        let mut initiator = KyberTransport::new(HandshakeRole::Initiator, None);
        initiator.start_handshake().unwrap();
        assert!(initiator.start_handshake().is_err());
    }

    #[test]
    fn test_bidirectional_heavy_traffic() {
        let mut initiator = KyberTransport::new(HandshakeRole::Initiator, None);
        let mut responder = KyberTransport::new(HandshakeRole::Responder, None);

        let pubkey_msg = initiator.start_handshake().unwrap();
        let ct_msg = responder.process_handshake_message(&pubkey_msg).unwrap().unwrap();
        initiator.process_handshake_message(&ct_msg).unwrap();
        initiator.finalize_handshake().unwrap();
        responder.finalize_handshake().unwrap();

        // 1000 bidirectional messages
        for i in 0u32..1000 {
            let msg = format!("message-{i}");

            let frame = initiator.encrypt(msg.as_bytes()).unwrap();
            let dec = responder.decrypt(&frame).unwrap();
            assert_eq!(dec, msg.as_bytes());

            let frame = responder.encrypt(msg.as_bytes()).unwrap();
            let dec = initiator.decrypt(&frame).unwrap();
            assert_eq!(dec, msg.as_bytes());
        }

        assert_eq!(initiator.stats().unwrap().messages_sent, 1000);
        assert_eq!(responder.stats().unwrap().messages_sent, 1000);
    }
}
