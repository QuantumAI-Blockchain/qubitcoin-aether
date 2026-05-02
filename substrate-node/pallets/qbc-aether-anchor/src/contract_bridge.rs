//! Sephirot Contract Bridge — builds EVM calldata for ISephirah cognitive cycles.
//!
//! This module constructs ABI-encoded calldata for the 10 deployed Sephirot contracts.
//! It does NOT execute calls directly; instead it returns `(address, calldata)` tuples
//! that the consensus engine dispatches to the QVM gRPC sidecar for inclusion in blocks.

use sp_core::{H160, H256, U256};
use sp_std::vec::Vec;

// ═══════════════════════════════════════════════════════════════════════════
// Function Selectors — keccak256(signature)[:4]
// ═══════════════════════════════════════════════════════════════════════════

/// `recordActivation()` — keccak256("recordActivation()")[:4]
const SEL_RECORD_ACTIVATION: [u8; 4] = [0xcf, 0x58, 0xb6, 0x97];

/// `updateQuantumState(bytes32)` — keccak256("updateQuantumState(bytes32)")[:4]
const SEL_UPDATE_QUANTUM_STATE: [u8; 4] = [0xa6, 0xeb, 0x8c, 0xd4];

/// `setEnergyLevel(uint256)` — keccak256("setEnergyLevel(uint256)")[:4]
const SEL_SET_ENERGY_LEVEL: [u8; 4] = [0x3d, 0x98, 0x39, 0xac];

/// `setCognitiveMass(uint256)` — keccak256("setCognitiveMass(uint256)")[:4]
const SEL_SET_COGNITIVE_MASS: [u8; 4] = [0xc2, 0x3b, 0xf5, 0x24];

/// `processMessage(uint8,bytes32,bytes)` — keccak256("processMessage(uint8,bytes32,bytes)")[:4]
const SEL_PROCESS_MESSAGE: [u8; 4] = [0x6b, 0x27, 0xd6, 0xca];

// ═══════════════════════════════════════════════════════════════════════════
// Sephirot Contract Addresses (proxy addresses from contract_registry.json)
// ═══════════════════════════════════════════════════════════════════════════

/// Node IDs 0-9 corresponding to the 10 Sephirot in the Tree of Life.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum SephirahId {
    Keter = 0,
    Chochmah = 1,
    Binah = 2,
    Chesed = 3,
    Gevurah = 4,
    Tiferet = 5,
    Netzach = 6,
    Hod = 7,
    Yesod = 8,
    Malkuth = 9,
}

impl SephirahId {
    /// Returns all 10 Sephirot IDs in emanation order.
    pub fn all() -> [SephirahId; 10] {
        [
            SephirahId::Keter,
            SephirahId::Chochmah,
            SephirahId::Binah,
            SephirahId::Chesed,
            SephirahId::Gevurah,
            SephirahId::Tiferet,
            SephirahId::Netzach,
            SephirahId::Hod,
            SephirahId::Yesod,
            SephirahId::Malkuth,
        ]
    }
}

/// Deployed proxy addresses for each Sephirah contract on QBC chain (chain ID 3303).
/// These are the proxy addresses from contract_registry.json.
pub const SEPHIROT_ADDRESSES: [H160; 10] = [
    // 0: Keter    — 0x70f0880765a6574e3ba7c25bc369a9aa72be8fb1
    H160([
        0x70, 0xf0, 0x88, 0x07, 0x65, 0xa6, 0x57, 0x4e, 0x3b, 0xa7,
        0xc2, 0x5b, 0xc3, 0x69, 0xa9, 0xaa, 0x72, 0xbe, 0x8f, 0xb1,
    ]),
    // 1: Chochmah — 0x0fd8430e1d3c74d8ea77bae433b74b4dcec44a2b
    H160([
        0x0f, 0xd8, 0x43, 0x0e, 0x1d, 0x3c, 0x74, 0xd8, 0xea, 0x77,
        0xba, 0xe4, 0x33, 0xb7, 0x4b, 0x4d, 0xce, 0xc4, 0x4a, 0x2b,
    ]),
    // 2: Binah    — 0x48f968a4926a4783b178bb67be63cbd074d2f887
    H160([
        0x48, 0xf9, 0x68, 0xa4, 0x92, 0x6a, 0x47, 0x83, 0xb1, 0x78,
        0xbb, 0x67, 0xbe, 0x63, 0xcb, 0xd0, 0x74, 0xd2, 0xf8, 0x87,
    ]),
    // 3: Chesed   — 0x533eb7f3c2fb721c7d2b74d6ff246ca8201ad2db
    H160([
        0x53, 0x3e, 0xb7, 0xf3, 0xc2, 0xfb, 0x72, 0x1c, 0x7d, 0x2b,
        0x74, 0xd6, 0xff, 0x24, 0x6c, 0xa8, 0x20, 0x1a, 0xd2, 0xdb,
    ]),
    // 4: Gevurah  — 0x65de61b759dfc92d0272244161df0fc9d41a2bcc
    H160([
        0x65, 0xde, 0x61, 0xb7, 0x59, 0xdf, 0xc9, 0x2d, 0x02, 0x72,
        0x24, 0x41, 0x61, 0xdf, 0x0f, 0xc9, 0xd4, 0x1a, 0x2b, 0xcc,
    ]),
    // 5: Tiferet  — 0xc20fafbcc6fb5f70ef2b31b18b611c6bc2b20999
    H160([
        0xc2, 0x0f, 0xaf, 0xbc, 0xc6, 0xfb, 0x5f, 0x70, 0xef, 0x2b,
        0x31, 0xb1, 0x8b, 0x61, 0x1c, 0x6b, 0xc2, 0xb2, 0x09, 0x99,
    ]),
    // 6: Netzach  — 0x3c3fd097760646875f5f2abb2a64891245461a20
    H160([
        0x3c, 0x3f, 0xd0, 0x97, 0x76, 0x06, 0x46, 0x87, 0x5f, 0x5f,
        0x2a, 0xbb, 0x2a, 0x64, 0x89, 0x12, 0x45, 0x46, 0x1a, 0x20,
    ]),
    // 7: Hod      — 0x6eaaf710a7312b2bda75a7c55ac5076d9dbc5d86
    H160([
        0x6e, 0xaa, 0xf7, 0x10, 0xa7, 0x31, 0x2b, 0x2b, 0xda, 0x75,
        0xa7, 0xc5, 0x5a, 0xc5, 0x07, 0x6d, 0x9d, 0xbc, 0x5d, 0x86,
    ]),
    // 8: Yesod    — 0x6b4e05615dea5a0f492ef24b7cfa1cbc957d5578
    H160([
        0x6b, 0x4e, 0x05, 0x61, 0x5d, 0xea, 0x5a, 0x0f, 0x49, 0x2e,
        0xf2, 0x4b, 0x7c, 0xfa, 0x1c, 0xbc, 0x95, 0x7d, 0x55, 0x78,
    ]),
    // 9: Malkuth  — 0x5d242419d98ec93b87be4b80a97176b4e3cdd419
    H160([
        0x5d, 0x24, 0x24, 0x19, 0xd9, 0x8e, 0xc9, 0x3b, 0x87, 0xbe,
        0x4b, 0x80, 0xa9, 0x71, 0x76, 0xb4, 0xe3, 0xcd, 0xd4, 0x19,
    ]),
];

/// Returns the deployed proxy address for a given Sephirah.
pub fn sephirah_address(id: SephirahId) -> H160 {
    SEPHIROT_ADDRESSES[id as usize]
}

// ═══════════════════════════════════════════════════════════════════════════
// ABI Encoding Helpers
// ═══════════════════════════════════════════════════════════════════════════

/// Encode a `U256` value as a 32-byte big-endian ABI word.
fn encode_u256(value: U256) -> [u8; 32] {
    value.to_big_endian()
}

/// Encode a `u8` value as a 32-byte ABI word (right-aligned, zero-padded).
fn encode_u8(value: u8) -> [u8; 32] {
    let mut buf = [0u8; 32];
    buf[31] = value;
    buf
}

// ═══════════════════════════════════════════════════════════════════════════
// Calldata Builders
// ═══════════════════════════════════════════════════════════════════════════

/// Build calldata for `recordActivation()`.
///
/// No parameters — just the 4-byte selector.
pub fn build_record_activation_calldata() -> Vec<u8> {
    SEL_RECORD_ACTIVATION.to_vec()
}

/// Build calldata for `updateQuantumState(bytes32 newStateHash)`.
///
/// ABI: selector (4 bytes) + bytes32 (32 bytes) = 36 bytes total.
pub fn build_update_quantum_state_calldata(state_hash: [u8; 32]) -> Vec<u8> {
    let mut calldata = Vec::with_capacity(36);
    calldata.extend_from_slice(&SEL_UPDATE_QUANTUM_STATE);
    calldata.extend_from_slice(&state_hash);
    calldata
}

/// Build calldata for `setEnergyLevel(uint256 energy)`.
///
/// ABI: selector (4 bytes) + uint256 (32 bytes) = 36 bytes total.
pub fn build_set_energy_calldata(energy: U256) -> Vec<u8> {
    let mut calldata = Vec::with_capacity(36);
    calldata.extend_from_slice(&SEL_SET_ENERGY_LEVEL);
    calldata.extend_from_slice(&encode_u256(energy));
    calldata
}

/// Build calldata for `setCognitiveMass(uint256 mass)`.
///
/// ABI: selector (4 bytes) + uint256 (32 bytes) = 36 bytes total.
pub fn build_set_cognitive_mass_calldata(mass: U256) -> Vec<u8> {
    let mut calldata = Vec::with_capacity(36);
    calldata.extend_from_slice(&SEL_SET_COGNITIVE_MASS);
    calldata.extend_from_slice(&encode_u256(mass));
    calldata
}

/// Build calldata for `processMessage(uint8 fromNodeId, bytes32 messageType, bytes payload)`.
///
/// ABI encoding for dynamic `bytes` parameter:
/// ```text
/// [0..4]    selector
/// [4..36]   uint8 fromNodeId (padded to 32 bytes)
/// [36..68]  bytes32 messageType
/// [68..100] offset to `payload` data (always 96 = 0x60 for 3 head slots)
/// [100..132] payload length
/// [132..]   payload data (padded to 32-byte boundary)
/// ```
pub fn build_process_message_calldata(
    from_id: u8,
    msg_type: [u8; 32],
    payload: &[u8],
) -> Vec<u8> {
    // Payload is padded to the next 32-byte boundary
    let padded_payload_len = (payload.len() + 31) & !31;
    // Total: 4 (selector) + 32*3 (head) + 32 (length word) + padded_payload
    let total_len = 4 + 96 + 32 + padded_payload_len;
    let mut calldata = Vec::with_capacity(total_len);

    // Selector
    calldata.extend_from_slice(&SEL_PROCESS_MESSAGE);

    // Param 1: uint8 fromNodeId
    calldata.extend_from_slice(&encode_u8(from_id));

    // Param 2: bytes32 messageType
    calldata.extend_from_slice(&msg_type);

    // Param 3: offset to dynamic `bytes` data (3 head slots * 32 = 96 = 0x60)
    calldata.extend_from_slice(&encode_u256(U256::from(96)));

    // Dynamic data: length prefix
    calldata.extend_from_slice(&encode_u256(U256::from(payload.len())));

    // Dynamic data: payload bytes (zero-padded to 32-byte boundary)
    calldata.extend_from_slice(payload);
    // Pad remaining bytes to 32-byte alignment
    let padding = padded_payload_len - payload.len();
    for _ in 0..padding {
        calldata.push(0u8);
    }

    calldata
}

// ═══════════════════════════════════════════════════════════════════════════
// Cognitive Cycle Dispatch
// ═══════════════════════════════════════════════════════════════════════════

/// Parameters for a single Sephirah's cognitive cycle activation.
pub struct SephirahCycleParams {
    /// Quantum state hash for this Sephirah's current cognitive state.
    pub state_hash: H256,
    /// Energy level (SUSY balance).
    pub energy: U256,
    /// Cognitive mass from Higgs field.
    pub cognitive_mass: U256,
}

/// A single call to be dispatched to the QVM sidecar.
pub struct SephirotCall {
    /// Target contract address.
    pub address: H160,
    /// ABI-encoded calldata.
    pub calldata: Vec<u8>,
}

/// Build the complete calldata batch for a full Sephirot cognitive cycle.
///
/// For each of the 10 Sephirot, this generates 4 calls:
///   1. `recordActivation()` — mark the Sephirah as activated this cycle
///   2. `updateQuantumState(state_hash)` — update quantum coherence state
///   3. `setEnergyLevel(energy)` — set SUSY energy balance
///   4. `setCognitiveMass(mass)` — set Higgs cognitive mass
///
/// Returns a `Vec<SephirotCall>` (40 calls total) ready for dispatch to the
/// QVM gRPC sidecar. The consensus engine includes these in the block.
///
/// # Arguments
///
/// * `params` — A 10-element array of [`SephirahCycleParams`], one per Sephirah
///   in emanation order (Keter=0 through Malkuth=9).
pub fn activate_sephirot_cycle(
    params: &[SephirahCycleParams; 10],
) -> Vec<SephirotCall> {
    let mut calls = Vec::with_capacity(40);

    for (i, sephirah_id) in SephirahId::all().iter().enumerate() {
        let address = sephirah_address(*sephirah_id);
        let p = &params[i];

        // 1. Record activation
        calls.push(SephirotCall {
            address,
            calldata: build_record_activation_calldata(),
        });

        // 2. Update quantum state
        calls.push(SephirotCall {
            address,
            calldata: build_update_quantum_state_calldata(p.state_hash.0),
        });

        // 3. Set energy level
        calls.push(SephirotCall {
            address,
            calldata: build_set_energy_calldata(p.energy),
        });

        // 4. Set cognitive mass
        calls.push(SephirotCall {
            address,
            calldata: build_set_cognitive_mass_calldata(p.cognitive_mass),
        });
    }

    calls
}

// ═══════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_activation_calldata_is_4_bytes() {
        let data = build_record_activation_calldata();
        assert_eq!(data.len(), 4);
        assert_eq!(data.as_slice(), &SEL_RECORD_ACTIVATION);
    }

    #[test]
    fn update_quantum_state_calldata_is_36_bytes() {
        let hash = [0xab; 32];
        let data = build_update_quantum_state_calldata(hash);
        assert_eq!(data.len(), 36);
        assert_eq!(&data[0..4], &SEL_UPDATE_QUANTUM_STATE);
        assert_eq!(&data[4..36], &hash);
    }

    #[test]
    fn set_energy_calldata_encodes_u256() {
        let energy = U256::from(1_000_000u64);
        let data = build_set_energy_calldata(energy);
        assert_eq!(data.len(), 36);
        assert_eq!(&data[0..4], &SEL_SET_ENERGY_LEVEL);
        // Verify the encoded value
        let expected = energy.to_big_endian();
        assert_eq!(&data[4..36], &expected);
    }

    #[test]
    fn set_cognitive_mass_calldata_encodes_u256() {
        let mass = U256::from(174_140_000u64); // 174.14 * 10^6
        let data = build_set_cognitive_mass_calldata(mass);
        assert_eq!(data.len(), 36);
        assert_eq!(&data[0..4], &SEL_SET_COGNITIVE_MASS);
    }

    #[test]
    fn process_message_calldata_encodes_dynamic_bytes() {
        let from_id = 5u8; // Tiferet
        let msg_type = [0x01; 32];
        let payload = b"hello sephirot";

        let data = build_process_message_calldata(from_id, msg_type, payload);

        // selector(4) + uint8(32) + bytes32(32) + offset(32) + length(32) + padded_data(32)
        assert_eq!(data.len(), 4 + 32 + 32 + 32 + 32 + 32);

        // Check selector
        assert_eq!(&data[0..4], &SEL_PROCESS_MESSAGE);

        // Check from_id is in last byte of first word
        assert_eq!(data[35], 5);
        // All preceding bytes zero
        assert!(data[4..35].iter().all(|&b| b == 0));

        // Check messageType
        assert_eq!(&data[36..68], &msg_type);

        // Check offset = 96 (0x60)
        assert_eq!(data[99], 0x60);

        // Check length = 14
        assert_eq!(data[131], 14);

        // Check payload content
        assert_eq!(&data[132..146], payload.as_slice());
        // Check zero padding
        assert!(data[146..164].iter().all(|&b| b == 0));
    }

    #[test]
    fn process_message_empty_payload() {
        let data = build_process_message_calldata(0, [0u8; 32], &[]);
        // selector(4) + head(96) + length(32) + no padded data
        assert_eq!(data.len(), 4 + 96 + 32);
    }

    #[test]
    fn activate_sephirot_cycle_returns_40_calls() {
        let params: [SephirahCycleParams; 10] = core::array::from_fn(|_| SephirahCycleParams {
            state_hash: H256::zero(),
            energy: U256::zero(),
            cognitive_mass: U256::zero(),
        });

        let calls = activate_sephirot_cycle(&params);
        assert_eq!(calls.len(), 40); // 10 sephirot * 4 calls each
    }

    #[test]
    fn sephirot_addresses_are_unique() {
        for i in 0..10 {
            for j in (i + 1)..10 {
                assert_ne!(
                    SEPHIROT_ADDRESSES[i], SEPHIROT_ADDRESSES[j],
                    "Sephirot addresses {} and {} must be unique",
                    i, j
                );
            }
        }
    }

    #[test]
    fn cycle_calls_target_correct_addresses() {
        let params: [SephirahCycleParams; 10] = core::array::from_fn(|_| SephirahCycleParams {
            state_hash: H256::zero(),
            energy: U256::zero(),
            cognitive_mass: U256::zero(),
        });

        let calls = activate_sephirot_cycle(&params);

        // Each Sephirah gets 4 consecutive calls
        for (i, id) in SephirahId::all().iter().enumerate() {
            let expected_addr = sephirah_address(*id);
            for offset in 0..4 {
                assert_eq!(
                    calls[i * 4 + offset].address,
                    expected_addr,
                    "Call {} for Sephirah {:?} targets wrong address",
                    offset,
                    id
                );
            }
        }
    }

    #[test]
    fn cycle_calls_have_correct_selectors() {
        let params: [SephirahCycleParams; 10] = core::array::from_fn(|_| SephirahCycleParams {
            state_hash: H256::from([0xaa; 32]),
            energy: U256::from(100),
            cognitive_mass: U256::from(200),
        });

        let calls = activate_sephirot_cycle(&params);

        for i in 0..10 {
            let base = i * 4;
            assert_eq!(&calls[base].calldata[0..4], &SEL_RECORD_ACTIVATION);
            assert_eq!(&calls[base + 1].calldata[0..4], &SEL_UPDATE_QUANTUM_STATE);
            assert_eq!(&calls[base + 2].calldata[0..4], &SEL_SET_ENERGY_LEVEL);
            assert_eq!(&calls[base + 3].calldata[0..4], &SEL_SET_COGNITIVE_MASS);
        }
    }
}
