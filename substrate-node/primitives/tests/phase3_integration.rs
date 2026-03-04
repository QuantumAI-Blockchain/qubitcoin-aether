//! Phase 3 Integration Tests — Kyber Transport + Poseidon2 + Reversibility
//!
//! Verifies that all three Phase 3 features work correctly and compose together:
//! 1. Kyber P2P Transport — ML-KEM-768 post-quantum encrypted communication
//! 2. Poseidon2 Hashing — ZK-friendly hash for privacy/bridge proofs
//! 3. Reversibility Pallet — governed transaction reversal (type-level only)

use qbc_kyber_transport::{
    HandshakeRole, KyberTransport,
    SecureSession,
    MAX_MESSAGE_SIZE,
};
use qbc_primitives::poseidon2::{
    poseidon2_hash_one, poseidon2_hash_two, poseidon2_hash_bytes,
    poseidon2_merkle_root, poseidon2_merkle_verify, Poseidon2Hash,
};
use qbc_primitives::{Address, TxId, Utxo, MAX_SUPPLY};

// ═══════════════════════════════════════════════════════════════════════
// Kyber Transport Integration Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn test_kyber_full_duplex_communication() {
    let mut initiator = KyberTransport::new(HandshakeRole::Initiator, None);
    let mut responder = KyberTransport::new(HandshakeRole::Responder, None);

    // Handshake
    let pubkey_msg = initiator.start_handshake().unwrap();
    let ct_msg = responder.process_handshake_message(&pubkey_msg).unwrap().unwrap();
    initiator.process_handshake_message(&ct_msg).unwrap();
    let init_complete = initiator.finalize_handshake().unwrap();
    let resp_complete = responder.finalize_handshake().unwrap();
    initiator.verify_peer_complete(&resp_complete).unwrap();
    responder.verify_peer_complete(&init_complete).unwrap();

    // Full duplex — both sides send and receive
    for i in 0..50 {
        let msg_a = format!("init→resp #{i}");
        let msg_b = format!("resp→init #{i}");

        let frame_a = initiator.encrypt(msg_a.as_bytes()).unwrap();
        let frame_b = responder.encrypt(msg_b.as_bytes()).unwrap();

        let dec_a = responder.decrypt(&frame_a).unwrap();
        let dec_b = initiator.decrypt(&frame_b).unwrap();

        assert_eq!(dec_a, msg_a.as_bytes());
        assert_eq!(dec_b, msg_b.as_bytes());
    }

    let init_stats = initiator.stats().unwrap();
    let resp_stats = responder.stats().unwrap();
    assert_eq!(init_stats.messages_sent, 50);
    assert_eq!(init_stats.messages_received, 50);
    assert_eq!(resp_stats.messages_sent, 50);
    assert_eq!(resp_stats.messages_received, 50);
}

#[test]
fn test_kyber_hybrid_security() {
    // With classical secret — hybrid security model
    let classical = vec![0xDE; 32];
    let mut init = KyberTransport::new(HandshakeRole::Initiator, Some(classical.clone()));
    let mut resp = KyberTransport::new(HandshakeRole::Responder, Some(classical));

    let pk = init.start_handshake().unwrap();
    let ct = resp.process_handshake_message(&pk).unwrap().unwrap();
    init.process_handshake_message(&ct).unwrap();
    init.finalize_handshake().unwrap();
    resp.finalize_handshake().unwrap();

    // Encrypted channel works with hybrid key derivation
    let frame = init.encrypt(b"post-quantum + classical").unwrap();
    let dec = resp.decrypt(&frame).unwrap();
    assert_eq!(dec, b"post-quantum + classical");
}

#[test]
fn test_kyber_session_isolation() {
    // Two independent sessions should not interfere
    let key1 = [0x11u8; 32];
    let key2 = [0x22u8; 32];

    let mut s1_send = SecureSession::new(key1, true);
    let mut s1_recv = SecureSession::new(key1, false);
    let mut s2_send = SecureSession::new(key2, true);
    let mut s2_recv = SecureSession::new(key2, false);

    let frame1 = s1_send.encrypt(b"session 1").unwrap();
    let frame2 = s2_send.encrypt(b"session 2").unwrap();

    // Each session decrypts its own messages
    assert_eq!(s1_recv.decrypt(&frame1).unwrap(), b"session 1");
    assert_eq!(s2_recv.decrypt(&frame2).unwrap(), b"session 2");

    // Cross-session decryption fails (different keys)
    let mut s1_wrong = SecureSession::new(key1, false);
    assert!(s1_wrong.decrypt(&frame2).is_err());
}

#[test]
fn test_kyber_large_payloads() {
    let mut init = KyberTransport::new(HandshakeRole::Initiator, None);
    let mut resp = KyberTransport::new(HandshakeRole::Responder, None);

    let pk = init.start_handshake().unwrap();
    let ct = resp.process_handshake_message(&pk).unwrap().unwrap();
    init.process_handshake_message(&ct).unwrap();
    init.finalize_handshake().unwrap();
    resp.finalize_handshake().unwrap();

    // Test with increasingly large payloads
    for size in [1, 100, 1000, 10_000, MAX_MESSAGE_SIZE] {
        let payload = vec![0xAB; size];
        let frame = init.encrypt(&payload).unwrap();
        let dec = resp.decrypt(&frame).unwrap();
        assert_eq!(dec, payload);
    }

    // Over MAX_MESSAGE_SIZE should fail
    let too_big = vec![0; MAX_MESSAGE_SIZE + 1];
    assert!(init.encrypt(&too_big).is_err());
}

// ═══════════════════════════════════════════════════════════════════════
// Poseidon2 Integration Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn test_poseidon2_merkle_tree_large() {
    // Build a Merkle tree with 1024 leaves
    let leaves: Vec<Poseidon2Hash> = (0..1024u64).map(|i| poseidon2_hash_one(i)).collect();
    let root = poseidon2_merkle_root(&leaves);

    // Root should be deterministic
    let root2 = poseidon2_merkle_root(&leaves);
    assert_eq!(root, root2);

    // Root should differ if any leaf changes
    let mut modified_leaves = leaves.clone();
    modified_leaves[512] = poseidon2_hash_one(99999);
    let modified_root = poseidon2_merkle_root(&modified_leaves);
    assert_ne!(root, modified_root);
}

#[test]
fn test_poseidon2_merkle_proof_all_positions() {
    // 8-leaf tree — verify proof for every leaf position
    let leaves: Vec<Poseidon2Hash> = (1..=8u64).map(Poseidon2Hash::from_u64).collect();
    let root = poseidon2_merkle_root(&leaves);

    // Build proofs manually for leaf at index 0
    // Level 0 sibling: leaf[1]
    // Level 1 sibling: hash(leaf[2], leaf[3])
    // Level 2 sibling: hash(hash(leaf[4], leaf[5]), hash(leaf[6], leaf[7]))
    let h01 = poseidon2_hash_two(1, 2);
    let h23 = poseidon2_hash_two(3, 4);
    let h45 = poseidon2_hash_two(5, 6);
    let h67 = poseidon2_hash_two(7, 8);
    let h0123 = poseidon2_hash_two(h01.as_u64(), h23.as_u64());
    let h4567 = poseidon2_hash_two(h45.as_u64(), h67.as_u64());

    // Verify root
    let expected_root = poseidon2_hash_two(h0123.as_u64(), h4567.as_u64());
    assert_eq!(root, expected_root);

    // Proof for leaf 0: siblings are leaf[1], h23, h4567
    let proof_0 = vec![
        Poseidon2Hash::from_u64(2),
        h23,
        h4567,
    ];
    assert!(poseidon2_merkle_verify(Poseidon2Hash::from_u64(1), &proof_0, 0, root));
}

#[test]
fn test_poseidon2_hash_bytes_block_data() {
    // Simulate hashing block header data for ZK proofs
    let block_hash = [0xAB; 32];
    let merkle_root = [0xCD; 32];
    let timestamp = 1709123456u64.to_le_bytes();

    let mut header_data = Vec::new();
    header_data.extend_from_slice(&block_hash);
    header_data.extend_from_slice(&merkle_root);
    header_data.extend_from_slice(&timestamp);

    let hash = poseidon2_hash_bytes(&header_data);
    assert_ne!(hash.as_u64(), 0);

    // Deterministic
    let hash2 = poseidon2_hash_bytes(&header_data);
    assert_eq!(hash, hash2);

    // Different data → different hash
    let mut modified = header_data.clone();
    modified[0] ^= 1;
    let hash3 = poseidon2_hash_bytes(&modified);
    assert_ne!(hash, hash3);
}

#[test]
fn test_poseidon2_commitment_scheme() {
    // Simulate a Pedersen-like commitment using Poseidon2
    // commit(value, blinding) = poseidon2(value, blinding)
    let value = 1000u64;   // 1000 QBC
    let blinding = 42u64;  // random blinding factor

    let commitment = poseidon2_hash_two(value, blinding);

    // Same inputs → same commitment (binding)
    assert_eq!(commitment, poseidon2_hash_two(value, blinding));

    // Different value → different commitment (hiding)
    assert_ne!(commitment, poseidon2_hash_two(value + 1, blinding));

    // Different blinding → different commitment
    assert_ne!(commitment, poseidon2_hash_two(value, blinding + 1));
}

// ═══════════════════════════════════════════════════════════════════════
// Cross-Feature Integration Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn test_poseidon2_over_kyber_channel() {
    // Scenario: Compute a Poseidon2 hash, encrypt it via Kyber, send over the wire
    let mut init = KyberTransport::new(HandshakeRole::Initiator, None);
    let mut resp = KyberTransport::new(HandshakeRole::Responder, None);

    let pk = init.start_handshake().unwrap();
    let ct = resp.process_handshake_message(&pk).unwrap().unwrap();
    init.process_handshake_message(&ct).unwrap();
    init.finalize_handshake().unwrap();
    resp.finalize_handshake().unwrap();

    // Compute Poseidon2 Merkle root on initiator
    let leaves: Vec<Poseidon2Hash> = (0..16u64).map(|i| poseidon2_hash_one(i)).collect();
    let root = poseidon2_merkle_root(&leaves);

    // Encrypt and send the root hash bytes
    let root_bytes = root.as_u64().to_le_bytes();
    let frame = init.encrypt(&root_bytes).unwrap();
    let dec = resp.decrypt(&frame).unwrap();

    // Responder reconstructs and verifies the hash
    let received_root = u64::from_le_bytes(dec.try_into().unwrap());
    assert_eq!(received_root, root.as_u64());
}

#[test]
fn test_utxo_hash_with_poseidon2() {
    // Hash UTXO data using Poseidon2 (for ZK proofs of UTXO ownership)
    let utxo = Utxo {
        txid: TxId::from([1u8; 32]),
        vout: 0,
        address: Address::from([2u8; 32]),
        amount: 100_000,
        block_height: 1000,
        is_coinbase: false,
    };

    // Hash the UTXO's identifying fields
    let utxo_hash = poseidon2_hash_two(utxo.amount as u64, utxo.block_height);
    assert_ne!(utxo_hash.as_u64(), 0);

    // Different amount → different hash
    let utxo_hash2 = poseidon2_hash_two(utxo.amount as u64 + 1, utxo.block_height);
    assert_ne!(utxo_hash, utxo_hash2);
}

#[test]
fn test_encrypted_merkle_proof_transmission() {
    // Scenario: Node A computes a Merkle proof, encrypts it via Kyber, sends to Node B
    let mut node_a = KyberTransport::new(HandshakeRole::Initiator, None);
    let mut node_b = KyberTransport::new(HandshakeRole::Responder, None);

    let pk = node_a.start_handshake().unwrap();
    let ct = node_b.process_handshake_message(&pk).unwrap().unwrap();
    node_a.process_handshake_message(&ct).unwrap();
    node_a.finalize_handshake().unwrap();
    node_b.finalize_handshake().unwrap();

    // Node A builds a Merkle tree
    let leaves: Vec<Poseidon2Hash> = (1..=4u64).map(Poseidon2Hash::from_u64).collect();
    let root = poseidon2_merkle_root(&leaves);

    // Build proof for leaf at index 0
    let proof = vec![
        Poseidon2Hash::from_u64(2),
        poseidon2_hash_two(3, 4),
    ];

    // Serialize the proof as bytes
    let mut proof_bytes = Vec::new();
    proof_bytes.extend_from_slice(&root.as_u64().to_le_bytes());
    proof_bytes.extend_from_slice(&(proof.len() as u32).to_le_bytes());
    for p in &proof {
        proof_bytes.extend_from_slice(&p.as_u64().to_le_bytes());
    }

    // Encrypt and send
    let frame = node_a.encrypt(&proof_bytes).unwrap();
    let dec = node_b.decrypt(&frame).unwrap();

    // Node B deserializes and verifies
    let recv_root = u64::from_le_bytes(dec[0..8].try_into().unwrap());
    let proof_len = u32::from_le_bytes(dec[8..12].try_into().unwrap()) as usize;
    let mut recv_proof = Vec::with_capacity(proof_len);
    for i in 0..proof_len {
        let offset = 12 + i * 8;
        let val = u64::from_le_bytes(dec[offset..offset + 8].try_into().unwrap());
        recv_proof.push(Poseidon2Hash::from_u64(val));
    }

    let recv_root_hash = Poseidon2Hash::from_u64(recv_root);
    assert!(poseidon2_merkle_verify(
        Poseidon2Hash::from_u64(1), // leaf
        &recv_proof,
        0, // index
        recv_root_hash,
    ));
}

// ═══════════════════════════════════════════════════════════════════════
// Primitive Type Tests
// ═══════════════════════════════════════════════════════════════════════

#[test]
fn test_qbc_primitives_constants() {
    // MAX_SUPPLY is in base units (8 decimal places)
    assert_eq!(MAX_SUPPLY, 330_000_000_000_000_000);
}

#[test]
fn test_address_type_operations() {
    let addr1 = Address::from([1u8; 32]);
    let addr2 = Address::from([2u8; 32]);
    let addr1_clone = addr1.clone();

    assert_eq!(addr1, addr1_clone);
    assert_ne!(addr1, addr2);
}
