//! ML-KEM-768 Handshake Protocol
//!
//! Implements the post-quantum key exchange that runs after the classical Noise handshake.
//!
//! ## Protocol Flow
//!
//! ```text
//! Initiator                              Responder
//! ---------                              ---------
//! Generate ML-KEM-768 keypair
//! Send: [version | KyberPubKey | ek]  →
//!                                        Encapsulate(ek) → (ss, ct)
//!                               ←  Send: [version | KyberCiphertext | ct]
//! Decapsulate(ct, dk) → ss
//! Derive session_key = HKDF(classical_ss || kyber_ss)
//! Send: [HandshakeComplete]       →
//!                               ←  Send: [HandshakeComplete]
//! ```

use crate::error::KyberTransportError;
use crate::{HKDF_INFO, MessageType, PROTOCOL_VERSION};

use hkdf::Hkdf;
use ml_kem::kem::{Decapsulate, DecapsulationKey, Encapsulate, EncapsulationKey};
use ml_kem::{Encoded, EncodedSizeUser, KemCore, MlKem768, MlKem768Params};
use rand::rngs::OsRng;
use sha2::Sha256;

/// ML-KEM-768 encapsulation key size in bytes.
const EK_SIZE: usize = 1184;

/// ML-KEM-768 ciphertext size in bytes.
const CT_SIZE: usize = 1088;

/// The role in the handshake (initiator or responder).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HandshakeRole {
    /// The peer that initiates the connection.
    Initiator,
    /// The peer that accepts the connection.
    Responder,
}

/// ML-KEM-768 handshake state machine.
pub struct KyberHandshake {
    role: HandshakeRole,
    /// ML-KEM decapsulation key (initiator only, consumed during decapsulation).
    decapsulation_key: Option<DecapsulationKey<MlKem768Params>>,
    /// The derived 32-byte shared secret from ML-KEM.
    kyber_shared_secret: Option<[u8; 32]>,
    /// The classical shared secret from Noise (optional, for hybrid derivation).
    classical_shared_secret: Option<Vec<u8>>,
    /// Whether handshake is complete.
    complete: bool,
}

impl KyberHandshake {
    /// Create a new handshake for the given role.
    ///
    /// `classical_secret` is the shared secret from the Noise handshake (if available).
    /// If provided, the final session key combines both classical and PQ secrets.
    pub fn new(role: HandshakeRole, classical_secret: Option<Vec<u8>>) -> Self {
        Self {
            role,
            decapsulation_key: None,
            kyber_shared_secret: None,
            classical_shared_secret: classical_secret,
            complete: false,
        }
    }

    /// Returns the handshake role.
    pub fn role(&self) -> HandshakeRole {
        self.role
    }

    /// Returns true if the handshake is complete.
    pub fn is_complete(&self) -> bool {
        self.complete
    }

    /// Generate the initiator's first message: the ML-KEM-768 encapsulation key.
    ///
    /// Returns the serialized handshake message to send to the responder.
    pub fn initiator_generate_pubkey(&mut self) -> Result<Vec<u8>, KyberTransportError> {
        if self.role != HandshakeRole::Initiator {
            return Err(KyberTransportError::Handshake(
                "only initiator can generate pubkey".into(),
            ));
        }

        let (dk, ek) = MlKem768::generate(&mut OsRng);
        self.decapsulation_key = Some(dk);

        let ek_encoded = ek.as_bytes();
        let ek_bytes: &[u8] = ek_encoded.as_ref();
        let mut msg = Vec::with_capacity(2 + ek_bytes.len());
        msg.push(PROTOCOL_VERSION);
        msg.push(MessageType::KyberPubKey as u8);
        msg.extend_from_slice(ek_bytes);

        log::debug!(
            "Kyber handshake: initiator generated ML-KEM-768 encapsulation key ({} bytes)",
            ek_bytes.len()
        );

        Ok(msg)
    }

    /// Process the initiator's pubkey message (responder side).
    ///
    /// Encapsulates a shared secret using the received encapsulation key.
    /// Returns the ciphertext message to send back.
    pub fn responder_encapsulate(
        &mut self,
        initiator_msg: &[u8],
    ) -> Result<Vec<u8>, KyberTransportError> {
        if self.role != HandshakeRole::Responder {
            return Err(KyberTransportError::Handshake(
                "only responder can encapsulate".into(),
            ));
        }

        // Parse message: [version(1) | type(1) | ek_bytes(...)]
        if initiator_msg.len() < 3 {
            return Err(KyberTransportError::Handshake("message too short".into()));
        }

        let version = initiator_msg[0];
        if version != PROTOCOL_VERSION {
            return Err(KyberTransportError::VersionMismatch {
                local: PROTOCOL_VERSION,
                remote: version,
            });
        }

        let msg_type = MessageType::try_from(initiator_msg[1])?;
        if msg_type != MessageType::KyberPubKey {
            return Err(KyberTransportError::UnexpectedMessage {
                expected: "KyberPubKey".into(),
                got: format!("{msg_type:?}"),
            });
        }

        let ek_bytes = &initiator_msg[2..];

        // Deserialize encapsulation key
        if ek_bytes.len() != EK_SIZE {
            return Err(KyberTransportError::Encapsulation(format!(
                "invalid encapsulation key size: expected {EK_SIZE}, got {}",
                ek_bytes.len()
            )));
        }

        let ek_array: [u8; EK_SIZE] = ek_bytes.try_into().unwrap();
        let ek_encoded: Encoded<EncapsulationKey<MlKem768Params>> = ek_array.into();
        let ek = EncapsulationKey::<MlKem768Params>::from_bytes(&ek_encoded);

        // Encapsulate: produces ciphertext + shared secret
        let (ct, ss) = ek.encapsulate(&mut OsRng).map_err(|e| {
            KyberTransportError::Encapsulation(format!("{e:?}"))
        })?;

        // Store the shared secret (Array<u8, U32> → [u8; 32])
        let ss_slice: &[u8] = ss.as_slice();
        let mut ss_bytes = [0u8; 32];
        ss_bytes.copy_from_slice(ss_slice);
        self.kyber_shared_secret = Some(ss_bytes);

        // Build response message — ct is Array<u8, CiphertextSize>
        let ct_slice: &[u8] = ct.as_slice();
        let mut msg = Vec::with_capacity(2 + ct_slice.len());
        msg.push(PROTOCOL_VERSION);
        msg.push(MessageType::KyberCiphertext as u8);
        msg.extend_from_slice(ct_slice);

        log::debug!(
            "Kyber handshake: responder encapsulated shared secret (ciphertext {} bytes)",
            ct_slice.len()
        );

        Ok(msg)
    }

    /// Process the responder's ciphertext message (initiator side).
    ///
    /// Decapsulates to recover the shared secret.
    pub fn initiator_decapsulate(
        &mut self,
        responder_msg: &[u8],
    ) -> Result<(), KyberTransportError> {
        if self.role != HandshakeRole::Initiator {
            return Err(KyberTransportError::Handshake(
                "only initiator can decapsulate".into(),
            ));
        }

        // Parse message
        if responder_msg.len() < 3 {
            return Err(KyberTransportError::Handshake("message too short".into()));
        }

        let version = responder_msg[0];
        if version != PROTOCOL_VERSION {
            return Err(KyberTransportError::VersionMismatch {
                local: PROTOCOL_VERSION,
                remote: version,
            });
        }

        let msg_type = MessageType::try_from(responder_msg[1])?;
        if msg_type != MessageType::KyberCiphertext {
            return Err(KyberTransportError::UnexpectedMessage {
                expected: "KyberCiphertext".into(),
                got: format!("{msg_type:?}"),
            });
        }

        let ct_bytes = &responder_msg[2..];

        // Deserialize ciphertext
        if ct_bytes.len() != CT_SIZE {
            return Err(KyberTransportError::Decapsulation(format!(
                "invalid ciphertext size: expected {CT_SIZE}, got {}",
                ct_bytes.len()
            )));
        }

        let ct_array: [u8; CT_SIZE] = ct_bytes.try_into().unwrap();

        // Decapsulate using our secret key
        let dk = self.decapsulation_key.take().ok_or_else(|| {
            KyberTransportError::Decapsulation("decapsulation key already consumed".into())
        })?;

        // decapsulate expects &EncodedCiphertext (Array<u8, CiphertextSize>)
        let ct_encoded = ct_array.into();
        let ss = dk.decapsulate(&ct_encoded).map_err(|e| {
            KyberTransportError::Decapsulation(format!("{e:?}"))
        })?;

        let ss_slice: &[u8] = ss.as_slice();
        let mut ss_bytes = [0u8; 32];
        ss_bytes.copy_from_slice(ss_slice);
        self.kyber_shared_secret = Some(ss_bytes);

        log::debug!("Kyber handshake: initiator decapsulated shared secret");

        Ok(())
    }

    /// Generate the handshake-complete acknowledgment message.
    pub fn complete_message(&self) -> Vec<u8> {
        vec![PROTOCOL_VERSION, MessageType::HandshakeComplete as u8]
    }

    /// Verify a handshake-complete message from the peer.
    pub fn verify_complete(msg: &[u8]) -> Result<(), KyberTransportError> {
        if msg.len() < 2 {
            return Err(KyberTransportError::Handshake(
                "complete message too short".into(),
            ));
        }
        if msg[0] != PROTOCOL_VERSION {
            return Err(KyberTransportError::VersionMismatch {
                local: PROTOCOL_VERSION,
                remote: msg[0],
            });
        }
        let msg_type = MessageType::try_from(msg[1])?;
        if msg_type != MessageType::HandshakeComplete {
            return Err(KyberTransportError::UnexpectedMessage {
                expected: "HandshakeComplete".into(),
                got: format!("{msg_type:?}"),
            });
        }
        Ok(())
    }

    /// Finalize the handshake and derive the 32-byte session key.
    ///
    /// Uses HKDF-SHA256 to combine:
    /// - The classical Noise shared secret (if present)
    /// - The ML-KEM-768 shared secret
    ///
    /// Returns the derived session key for AES-256-GCM.
    pub fn derive_session_key(&mut self) -> Result<[u8; 32], KyberTransportError> {
        let kyber_ss = self.kyber_shared_secret.take().ok_or_else(|| {
            KyberTransportError::KeyDerivation("kyber shared secret not available".into())
        })?;

        // Combine classical + PQ shared secrets as IKM
        let mut ikm = Vec::with_capacity(64);
        if let Some(classical) = &self.classical_shared_secret {
            ikm.extend_from_slice(classical);
        }
        ikm.extend_from_slice(&kyber_ss);

        // Derive session key via HKDF-SHA256
        let hk = Hkdf::<Sha256>::new(None, &ikm);
        let mut session_key = [0u8; 32];
        hk.expand(HKDF_INFO, &mut session_key).map_err(|e| {
            KyberTransportError::KeyDerivation(format!("HKDF expand failed: {e}"))
        })?;

        self.complete = true;

        log::info!(
            "Kyber handshake complete — hybrid session key derived (classical={}, PQ=ML-KEM-768)",
            if self.classical_shared_secret.is_some() {
                "yes"
            } else {
                "none"
            }
        );

        Ok(session_key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_full_handshake_without_classical() {
        let mut initiator = KyberHandshake::new(HandshakeRole::Initiator, None);
        let pubkey_msg = initiator.initiator_generate_pubkey().unwrap();

        let mut responder = KyberHandshake::new(HandshakeRole::Responder, None);
        let ciphertext_msg = responder.responder_encapsulate(&pubkey_msg).unwrap();

        initiator.initiator_decapsulate(&ciphertext_msg).unwrap();

        let initiator_key = initiator.derive_session_key().unwrap();
        let responder_key = responder.derive_session_key().unwrap();

        assert_eq!(initiator_key, responder_key);
        assert!(initiator.is_complete());
        assert!(responder.is_complete());
    }

    #[test]
    fn test_full_handshake_with_classical_secret() {
        let classical = vec![0xAB; 32];

        let mut initiator =
            KyberHandshake::new(HandshakeRole::Initiator, Some(classical.clone()));
        let pubkey_msg = initiator.initiator_generate_pubkey().unwrap();

        let mut responder = KyberHandshake::new(HandshakeRole::Responder, Some(classical));
        let ciphertext_msg = responder.responder_encapsulate(&pubkey_msg).unwrap();

        initiator.initiator_decapsulate(&ciphertext_msg).unwrap();

        let initiator_key = initiator.derive_session_key().unwrap();
        let responder_key = responder.derive_session_key().unwrap();

        assert_eq!(initiator_key, responder_key);
    }

    #[test]
    fn test_handshake_complete_messages() {
        let initiator = KyberHandshake::new(HandshakeRole::Initiator, None);
        let msg = initiator.complete_message();
        assert_eq!(msg[0], PROTOCOL_VERSION);
        assert_eq!(msg[1], MessageType::HandshakeComplete as u8);
        KyberHandshake::verify_complete(&msg).unwrap();
    }

    #[test]
    fn test_version_mismatch() {
        let mut bad_msg = vec![0xFF, MessageType::KyberPubKey as u8];
        bad_msg.extend_from_slice(&[0u8; EK_SIZE]);

        let mut responder = KyberHandshake::new(HandshakeRole::Responder, None);
        let err = responder.responder_encapsulate(&bad_msg).unwrap_err();
        assert!(matches!(err, KyberTransportError::VersionMismatch { .. }));
    }

    #[test]
    fn test_wrong_role_errors() {
        let mut responder = KyberHandshake::new(HandshakeRole::Responder, None);
        assert!(responder.initiator_generate_pubkey().is_err());

        let mut initiator = KyberHandshake::new(HandshakeRole::Initiator, None);
        assert!(initiator.responder_encapsulate(&[]).is_err());
    }

    #[test]
    fn test_different_classical_secrets_produce_different_keys() {
        let mut init_a = KyberHandshake::new(HandshakeRole::Initiator, Some(vec![0xAA; 32]));
        let pubkey_msg = init_a.initiator_generate_pubkey().unwrap();
        let mut resp_a = KyberHandshake::new(HandshakeRole::Responder, Some(vec![0xAA; 32]));
        let ct_msg = resp_a.responder_encapsulate(&pubkey_msg).unwrap();
        init_a.initiator_decapsulate(&ct_msg).unwrap();
        let key_a = init_a.derive_session_key().unwrap();

        let mut init_b = KyberHandshake::new(HandshakeRole::Initiator, Some(vec![0xBB; 32]));
        let pubkey_msg_b = init_b.initiator_generate_pubkey().unwrap();
        let mut resp_b = KyberHandshake::new(HandshakeRole::Responder, Some(vec![0xBB; 32]));
        let ct_msg_b = resp_b.responder_encapsulate(&pubkey_msg_b).unwrap();
        init_b.initiator_decapsulate(&ct_msg_b).unwrap();
        let key_b = init_b.derive_session_key().unwrap();

        // Different Kyber keypairs + different classical → different session keys
        assert_ne!(key_a, key_b);
    }
}
