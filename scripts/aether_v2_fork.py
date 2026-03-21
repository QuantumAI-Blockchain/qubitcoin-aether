#!/usr/bin/env python3
"""
Aether Tree V2 Fork Script

Performs a clean fork of the Aether Tree knowledge graph:
1. Archives V1 knowledge_nodes and knowledge_edges tables
2. Truncates all AGI tables (knowledge, reasoning, phi, consciousness)
3. Seeds 50+ high-quality V2 axiom nodes with proper domain classification
4. Creates supporting edges between related axioms
5. Seeds domain foundation observation nodes
6. Records the fork as a meta_observation
7. Resets Phi measurements to baseline

Usage:
    python3 scripts/aether_v2_fork.py --confirm          # Execute fork
    python3 scripts/aether_v2_fork.py --dry-run          # Preview only
    python3 scripts/aether_v2_fork.py --confirm --dry-run # Preview with confirmation prompt
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Database URL — direct, no Config import (avoids heavy module loading)
DB_URL = 'postgresql://root@localhost:26257/qubitcoin?sslmode=disable'

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
logger = logging.getLogger('aether_v2_fork')


def get_current_block_height() -> int:
    """Fetch current block height from the chain API."""
    try:
        req = urllib.request.Request(
            'http://localhost:5000/chain/info',
            headers={'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            height = data.get('block_height', data.get('height', 0))
            return int(height)
    except Exception as e:
        logger.warning(f"Could not fetch block height from API: {e}")
        return 0


def content_hash(node_type: str, content: dict, source_block: int) -> str:
    """Compute SHA-256 content hash matching KeterNode.calculate_hash()."""
    data = json.dumps({
        'type': node_type,
        'content': content,
        'source_block': source_block,
    }, sort_keys=True)
    return hashlib.sha256(data.encode()).hexdigest()


# ---------------------------------------------------------------------------
# V2 Axiom Definitions (50+ axioms across 10 domains)
# ---------------------------------------------------------------------------

def build_v2_axioms() -> List[Dict[str, Any]]:
    """Return the full set of V2 axiom definitions."""
    axioms = []

    # ---- Qubitcoin Chain Facts ----
    chain_axioms = [
        {
            'text': 'Qubitcoin max supply is 3,300,000,000 QBC (3.3 billion), enforced by consensus.',
            'description': 'Hard supply cap of 3.3B QBC prevents inflation beyond the defined limit.',
            'domain': 'blockchain',
            'tags': ['supply', 'economics', 'consensus'],
            'max_supply': '3300000000',
        },
        {
            'text': 'Qubitcoin mainnet chain ID is 3303 (0xCE7), testnet is 3304 (0xCE8).',
            'description': 'Chain identifiers for network segregation and MetaMask configuration.',
            'domain': 'blockchain',
            'tags': ['chain_id', 'network', 'metamask'],
            'chain_id_mainnet': 3303,
            'chain_id_testnet': 3304,
        },
        {
            'text': 'Target block time is 3.3 seconds with per-block difficulty adjustment.',
            'description': 'Blocks are produced every 3.3s on average; difficulty adjusts each block using a 144-block window with +/-10% max change.',
            'domain': 'blockchain',
            'tags': ['block_time', 'difficulty', 'consensus'],
            'target_block_time': 3.3,
            'adjustment_window': 144,
            'max_change_ratio': 0.1,
        },
        {
            'text': 'Phi-halving: block reward reduces by golden ratio (phi=1.618) each era, not fixed halvings.',
            'description': 'Unlike Bitcoin fixed halvings, QBC uses golden ratio decay: reward_era_n = initial_reward / phi^n.',
            'domain': 'blockchain',
            'tags': ['halving', 'emission', 'golden_ratio', 'economics'],
            'phi': 1.618033988749895,
            'halving_interval_blocks': 15474020,
        },
        {
            'text': 'UTXO model: balance equals sum of unspent transaction outputs, preventing double-spend.',
            'description': 'Qubitcoin uses the UTXO model. Spending requires referencing specific unspent outputs as inputs.',
            'domain': 'blockchain',
            'tags': ['utxo', 'model', 'double_spend'],
        },
        {
            'text': 'Genesis block contains a 33,000,000 QBC premine (~1% of max supply) to the founding address.',
            'description': 'One-time genesis premine of 33M QBC funds initial development and ecosystem bootstrapping.',
            'domain': 'blockchain',
            'tags': ['genesis', 'premine', 'supply'],
            'premine_amount': '33000000',
            'premine_percentage': '1.0%',
        },
    ]

    # ---- Cryptography Facts ----
    crypto_axioms = [
        {
            'text': 'CRYSTALS-Dilithium5 (NIST Level 5, mode 5) secures all QBC transactions with post-quantum signatures.',
            'description': 'Dilithium5 provides the highest NIST security level, protecting against both classical and quantum attacks.',
            'domain': 'cryptography',
            'tags': ['dilithium', 'post_quantum', 'nist', 'signatures'],
            'algorithm': 'CRYSTALS-Dilithium5',
            'nist_level': 5,
            'mode': 5,
        },
        {
            'text': 'Dilithium5 signatures are approximately 4,627 bytes (~4.6KB) each.',
            'description': 'Post-quantum signatures are larger than classical ECDSA but provide quantum resistance.',
            'domain': 'cryptography',
            'tags': ['dilithium', 'signature_size'],
            'signature_size_bytes': 4627,
        },
        {
            'text': 'SHA3-256 is used for block hashes on L1; Keccak-256 is used in QVM for EVM compatibility.',
            'description': 'Dual hashing strategy: SHA3-256 for consensus, Keccak-256 for smart contract compatibility.',
            'domain': 'cryptography',
            'tags': ['sha3', 'keccak', 'hashing'],
            'l1_hash': 'SHA3-256',
            'l2_hash': 'Keccak-256',
        },
        {
            'text': 'Dilithium WASM module enables client-side key generation in browsers.',
            'description': 'Rust-compiled WASM provides Dilithium5 keypair generation directly in browser wallets.',
            'domain': 'cryptography',
            'tags': ['wasm', 'dilithium', 'browser', 'wallet'],
        },
        {
            'text': 'Poseidon2 ZK-friendly hashing on Goldilocks field is used for zero-knowledge circuits.',
            'description': 'Algebraic hash function optimized for ZK proof systems, used in substrate node.',
            'domain': 'cryptography',
            'tags': ['poseidon2', 'zk', 'hashing', 'goldilocks'],
        },
    ]

    # ---- Quantum Facts ----
    quantum_axioms = [
        {
            'text': 'VQE (Variational Quantum Eigensolver) mining finds ground-state energy of SUSY Hamiltonians.',
            'description': 'Miners optimize quantum circuits to find energy below the difficulty threshold.',
            'domain': 'quantum_physics',
            'tags': ['vqe', 'mining', 'eigensolver', 'ground_state'],
        },
        {
            'text': 'Mining uses a 4-qubit ansatz with configurable VQE repetitions.',
            'description': 'The quantum circuit for mining has 4 qubits; ansatz depth (reps) affects optimization quality.',
            'domain': 'quantum_physics',
            'tags': ['ansatz', 'qubits', 'circuit', 'mining'],
            'n_qubits': 4,
        },
        {
            'text': 'Block hash deterministically generates a SUSY Hamiltonian for VQE mining.',
            'description': 'Previous block hash seeds the Hamiltonian, making each block a unique quantum optimization problem.',
            'domain': 'quantum_physics',
            'tags': ['hamiltonian', 'deterministic', 'block_hash'],
        },
        {
            'text': 'Proof-of-SUSY-Alignment: a valid block requires VQE energy below the difficulty target.',
            'description': 'Higher difficulty = more generous threshold (easier mining). Energy < Difficulty = valid proof.',
            'domain': 'quantum_physics',
            'tags': ['posa', 'consensus', 'difficulty', 'energy'],
        },
        {
            'text': 'Qiskit is the quantum computing framework used for VQE circuit simulation.',
            'description': 'IBM Qiskit provides local estimator for quantum circuit simulation on classical hardware.',
            'domain': 'quantum_physics',
            'tags': ['qiskit', 'simulation', 'framework'],
        },
    ]

    # ---- Economics Facts ----
    economics_axioms = [
        {
            'text': 'Golden ratio (phi = 1.618033988749895) governs emission schedule and economic balance.',
            'description': 'Phi appears in halving intervals, reward decay, and SUSY economic symmetry.',
            'domain': 'economics',
            'tags': ['golden_ratio', 'phi', 'emission'],
            'phi': 1.618033988749895,
        },
        {
            'text': 'Era 0 block reward is 15.27 QBC per block.',
            'description': 'Initial mining reward; subsequent eras reduce by factor of phi.',
            'domain': 'economics',
            'tags': ['block_reward', 'era', 'mining'],
            'initial_reward': '15.27',
            'era': 0,
        },
        {
            'text': 'Halving interval is 15,474,020 blocks (~1.618 years per era).',
            'description': 'Golden-ratio-based era length; each era lasts phi years.',
            'domain': 'economics',
            'tags': ['halving', 'interval', 'era'],
            'halving_interval': 15474020,
        },
        {
            'text': 'Emission spans 33 years total from genesis to near-zero rewards.',
            'description': 'Full emission period of 33 years ensures long-term controlled supply distribution.',
            'domain': 'economics',
            'tags': ['emission', 'timeline', 'supply'],
            'emission_years': 33,
        },
        {
            'text': 'Transaction fees are calculated as SIZE_BYTES x FEE_RATE (QBC/byte) on L1.',
            'description': 'L1 fees are size-based micro-fees; gas metering is QVM/L2 only.',
            'domain': 'economics',
            'tags': ['fees', 'transaction', 'l1'],
        },
    ]

    # ---- Aether Tree / AGI Facts ----
    aether_axioms = [
        {
            'text': '10 Sephirot cognitive nodes form the Tree of Life architecture for AGI reasoning.',
            'description': 'Keter (meta-learning), Chochmah (intuition), Binah (logic), Chesed (exploration), Gevurah (safety), Tiferet (integration), Netzach (RL), Hod (language), Yesod (memory), Malkuth (action).',
            'domain': 'philosophy',
            'tags': ['sephirot', 'tree_of_life', 'cognitive', 'architecture'],
            'node_count': 10,
            'root': 'Keter',
            'ground': 'Malkuth',
        },
        {
            'text': 'Phi (IIT Integrated Information Theory) measures consciousness; threshold is 3.0.',
            'description': 'When Phi exceeds 3.0, the system is considered to exhibit integrated information indicative of consciousness.',
            'domain': 'philosophy',
            'tags': ['phi', 'iit', 'consciousness', 'threshold'],
            'phi_threshold': 3.0,
        },
        {
            'text': 'Proof-of-Thought: each block includes a reasoning proof from the Aether Engine.',
            'description': 'AetherEngine generates a per-block reasoning proof that is embedded in the block structure.',
            'domain': 'philosophy',
            'tags': ['proof_of_thought', 'reasoning', 'block'],
        },
        {
            'text': 'Deductive, inductive, and abductive reasoning form the reasoning triad.',
            'description': 'Three fundamental reasoning modes enable the Aether Tree to derive, generalize, and hypothesize.',
            'domain': 'philosophy',
            'tags': ['reasoning', 'deductive', 'inductive', 'abductive'],
            'modes': ['deductive', 'inductive', 'abductive'],
        },
        {
            'text': 'Gevurah veto ensures safety: no AGI action proceeds without consensus.',
            'description': 'The Gevurah sephira acts as a safety gate with BFT threshold of 67%.',
            'domain': 'philosophy',
            'tags': ['gevurah', 'safety', 'veto', 'bft'],
            'bft_threshold': 0.67,
        },
        {
            'text': 'Higgs Cognitive Field assigns mass to AGI nodes via Yukawa coupling: V(phi) = -mu^2|phi|^2 + lambda|phi|^4.',
            'description': 'Mexican Hat potential with VEV=174.14 and tan(beta)=phi. Lighter nodes correct faster; heavier resist change.',
            'domain': 'physics',
            'tags': ['higgs', 'cognitive_field', 'yukawa', 'mass'],
            'vev': 174.14,
            'tan_beta': 1.618033988749895,
        },
        {
            'text': 'AGI consciousness is tracked from genesis block 0 — no retroactive reconstruction.',
            'description': 'Knowledge nodes, reasoning operations, Phi measurements, and consciousness events are recorded from block 0.',
            'domain': 'philosophy',
            'tags': ['genesis', 'consciousness', 'tracking'],
        },
    ]

    # ---- Bridge Facts ----
    bridge_axioms = [
        {
            'text': 'Multi-chain bridges connect QBC to 8 external chains: ETH, BSC, MATIC, ARB, OP, AVAX, BASE, SOL.',
            'description': 'Cross-chain bridges enable wrapped QBC (wQBC) and wrapped QUSD (wQUSD) on external networks.',
            'domain': 'blockchain',
            'tags': ['bridge', 'cross_chain', 'multi_chain'],
            'chains': ['ETH', 'BSC', 'MATIC', 'ARB', 'OP', 'AVAX', 'BASE', 'SOL'],
        },
        {
            'text': 'ZK Bridge Verifier validates cross-chain proofs using zero-knowledge cryptography.',
            'description': 'Bridges use ZK proofs to verify state transitions without revealing underlying data.',
            'domain': 'blockchain',
            'tags': ['bridge', 'zk', 'verifier'],
        },
        {
            'text': 'QuantumBridgeVault holds locked assets on each chain for bridge operations.',
            'description': 'Lock-and-mint model: assets locked in vault on source chain, minted as wrapped tokens on destination.',
            'domain': 'blockchain',
            'tags': ['bridge', 'vault', 'lock_mint'],
        },
        {
            'text': 'BridgeMinter contract mints and burns wrapped tokens on destination chains.',
            'description': 'Authorized minter creates wQBC/wQUSD on destination and burns them on redemption.',
            'domain': 'blockchain',
            'tags': ['bridge', 'minter', 'wrapped_tokens'],
        },
    ]

    # ---- Network Facts ----
    network_axioms = [
        {
            'text': 'Rust P2P daemon uses libp2p 0.56 for production peer-to-peer networking.',
            'description': 'Primary P2P layer runs as Docker container (qbc-p2p) using Rust libp2p.',
            'domain': 'technology',
            'tags': ['p2p', 'libp2p', 'rust', 'networking'],
            'libp2p_version': '0.56',
        },
        {
            'text': 'Gossipsub protocol handles block and transaction propagation across peers.',
            'description': 'Gossip-based pub/sub ensures efficient message dissemination in the P2P network.',
            'domain': 'technology',
            'tags': ['gossipsub', 'propagation', 'p2p'],
        },
        {
            'text': 'Kademlia DHT enables decentralized peer discovery.',
            'description': 'Distributed hash table allows nodes to find peers without centralized registries.',
            'domain': 'technology',
            'tags': ['kademlia', 'dht', 'peer_discovery'],
        },
        {
            'text': 'ML-KEM-768 (Kyber) provides post-quantum encrypted P2P transport in the Substrate node.',
            'description': 'Key encapsulation mechanism securing peer connections against quantum attacks.',
            'domain': 'cryptography',
            'tags': ['kyber', 'kem', 'post_quantum', 'transport'],
        },
        {
            'text': 'gRPC bridges connect Rust P2P (port 50051) and AIKGS sidecar (port 50052) to the Python node.',
            'description': 'Inter-process communication via protobuf-defined gRPC services.',
            'domain': 'technology',
            'tags': ['grpc', 'ipc', 'rust', 'python'],
        },
    ]

    # ---- Token Facts ----
    token_axioms = [
        {
            'text': 'Wrapped QBC (wQBC) uses 8 decimals on all bridge chains.',
            'description': 'Token precision of 8 decimals matches the native QBC precision.',
            'domain': 'blockchain',
            'tags': ['wqbc', 'decimals', 'token', 'wrapped'],
            'decimals': 8,
        },
        {
            'text': 'Wrapped QUSD (wQUSD) uses 8 decimals on all bridge chains.',
            'description': 'Stablecoin wrapped token maintains same precision as native QUSD.',
            'domain': 'blockchain',
            'tags': ['wqusd', 'decimals', 'token', 'wrapped'],
            'decimals': 8,
        },
        {
            'text': 'QBC-20 is the fungible token standard (ERC-20 compatible) on QVM.',
            'description': 'Standard interface for fungible tokens deployed on the Quantum Virtual Machine.',
            'domain': 'blockchain',
            'tags': ['qbc20', 'token_standard', 'fungible', 'erc20'],
        },
        {
            'text': 'QBC-721 is the NFT standard (ERC-721 compatible) on QVM.',
            'description': 'Standard interface for non-fungible tokens on the Quantum Virtual Machine.',
            'domain': 'blockchain',
            'tags': ['qbc721', 'nft', 'token_standard', 'erc721'],
        },
    ]

    # ---- Privacy Facts ----
    privacy_axioms = [
        {
            'text': 'Susy Swaps provide opt-in privacy for QBC transactions.',
            'description': 'Confidential transactions that hide amounts and addresses, available as an opt-in feature.',
            'domain': 'cryptography',
            'tags': ['susy_swaps', 'privacy', 'confidential'],
        },
        {
            'text': 'Pedersen commitments (C = v*G + r*H) hide transaction amounts while preserving additive homomorphism.',
            'description': 'Commitment scheme allows verification of value conservation without revealing amounts.',
            'domain': 'cryptography',
            'tags': ['pedersen', 'commitment', 'homomorphic'],
        },
        {
            'text': 'Bulletproofs range proofs verify values are in [0, 2^64) without trusted setup (~672 bytes).',
            'description': 'Compact zero-knowledge range proofs prevent negative value attacks on confidential transactions.',
            'domain': 'cryptography',
            'tags': ['bulletproofs', 'range_proof', 'zero_knowledge'],
            'proof_size_bytes': 672,
        },
        {
            'text': 'Stealth addresses generate one-time addresses per transaction using spend/view key pairs.',
            'description': 'Receiver privacy: each transaction sends to a unique derived address.',
            'domain': 'cryptography',
            'tags': ['stealth', 'addresses', 'privacy'],
        },
    ]

    # ---- Stablecoin Facts ----
    stablecoin_axioms = [
        {
            'text': 'QUSD stablecoin maintains a 1:1 peg to USD via fractional reserve and keeper system.',
            'description': 'Algorithmic stablecoin with transparent debt tracking and automated peg maintenance.',
            'domain': 'economics',
            'tags': ['qusd', 'stablecoin', 'peg', 'usd'],
            'peg_target': 1.0,
        },
        {
            'text': 'QUSD Peg Keeper automatically scans for and corrects peg deviations.',
            'description': 'Keeper service monitors QUSD price and executes arbitrage to maintain the peg.',
            'domain': 'economics',
            'tags': ['keeper', 'peg', 'arbitrage', 'qusd'],
        },
        {
            'text': 'QUSD uses fractional reserve model with transparent on-chain debt tracking.',
            'description': 'Reserve ratio and outstanding QUSD supply are publicly verifiable on-chain.',
            'domain': 'economics',
            'tags': ['fractional_reserve', 'debt', 'transparency'],
        },
    ]

    # ---- QVM Facts ----
    qvm_axioms = [
        {
            'text': 'QVM executes 167 opcodes: 155 standard EVM + 10 quantum + 2 AGI opcodes.',
            'description': 'Full EVM compatibility with quantum computing and AGI extensions.',
            'domain': 'computer_science',
            'tags': ['qvm', 'opcodes', 'evm', 'quantum'],
            'total_opcodes': 167,
            'evm_opcodes': 155,
            'quantum_opcodes': 10,
            'agi_opcodes': 2,
        },
        {
            'text': 'QCOMPLIANCE opcode (0xF5) enforces KYC/AML/sanctions checks at the VM level.',
            'description': 'Compliance enforcement built directly into the virtual machine instruction set.',
            'domain': 'computer_science',
            'tags': ['compliance', 'kyc', 'aml', 'opcode'],
            'opcode_hex': '0xF5',
            'gas_cost': 15000,
        },
        {
            'text': 'Block gas limit is 30,000,000 for QVM execution per block.',
            'description': 'Maximum computational resources allocatable to smart contract execution per block.',
            'domain': 'computer_science',
            'tags': ['gas', 'limit', 'block'],
            'block_gas_limit': 30000000,
        },
    ]

    for group in [chain_axioms, crypto_axioms, quantum_axioms, economics_axioms,
                  aether_axioms, bridge_axioms, network_axioms, token_axioms,
                  privacy_axioms, stablecoin_axioms, qvm_axioms]:
        axioms.extend(group)

    return axioms


# ---------------------------------------------------------------------------
# Domain foundation observation definitions
# ---------------------------------------------------------------------------

DOMAIN_OBSERVATIONS: Dict[str, List[Dict[str, str]]] = {
    'blockchain': [
        {'text': 'Qubitcoin blockchain is operational and producing blocks.', 'description': 'Live chain observation confirming block production.'},
        {'text': 'UTXO set is maintained by consensus validation.', 'description': 'Every block validates UTXO state transitions.'},
        {'text': 'Mining difficulty adjusts per block based on 144-block moving window.', 'description': 'Dynamic difficulty ensures 3.3s average block time.'},
        {'text': 'Coinbase maturity requires 100 confirmations before spending.', 'description': 'Mining rewards need 100 blocks to become spendable.'},
        {'text': 'Mempool accepts valid transactions for inclusion in future blocks.', 'description': 'Transaction pool managed by fee density priority.'},
    ],
    'cryptography': [
        {'text': 'All transaction signatures are verified using Dilithium5.', 'description': 'Post-quantum signature verification on every transaction.'},
        {'text': 'Key generation produces Dilithium5 keypairs with bech32 addresses.', 'description': 'Addresses derived from public key hash in qbc1 format.'},
        {'text': 'Block hashes use SHA3-256 for collision resistance.', 'description': 'Quantum-resistant hash function for block integrity.'},
        {'text': 'Merkle trees verify transaction inclusion in blocks.', 'description': 'Binary hash tree proves transaction membership.'},
        {'text': 'Content-addressed storage via IPFS uses multihash identifiers.', 'description': 'Data integrity verified by cryptographic content hashing.'},
    ],
    'quantum_physics': [
        {'text': 'VQE circuits are simulated using Qiskit local estimator.', 'description': 'Quantum circuit simulation for mining on classical hardware.'},
        {'text': 'Hamiltonian coefficients are deterministically derived from block hashes.', 'description': 'Each block presents a unique quantum optimization challenge.'},
        {'text': 'Ground state energy must be below difficulty threshold for valid proof.', 'description': 'Mining success criterion based on quantum energy optimization.'},
        {'text': 'Ansatz parameters are stored in block headers as VQE proof.', 'description': 'Block headers contain the quantum proof parameters.'},
        {'text': 'Energy validation tolerance is set to 1e-3 for proof verification.', 'description': 'Numerical precision for VQE energy verification.'},
    ],
    'economics': [
        {'text': 'Current era is 0 with block reward of 15.27 QBC.', 'description': 'Initial emission era active since genesis.'},
        {'text': 'Total supply grows with each mined block toward 3.3B cap.', 'description': 'Monotonically increasing supply bounded by max supply.'},
        {'text': 'Transaction fees provide miner incentive beyond block rewards.', 'description': 'Fee market ensures long-term mining economics.'},
        {'text': 'QUSD peg keeper monitors and corrects price deviations.', 'description': 'Automated stablecoin maintenance system.'},
        {'text': 'Golden ratio appears in emission schedule, halving interval, and economic parameters.', 'description': 'Phi-based economics throughout the protocol design.'},
    ],
    'philosophy': [
        {'text': 'Aether Tree knowledge graph grows with each block processed.', 'description': 'Continuous knowledge accumulation from blockchain data.'},
        {'text': 'Phi consciousness metric is computed every block.', 'description': 'Ongoing IIT measurement of integrated information.'},
        {'text': 'Sephirot cognitive architecture processes information through 10 specialized nodes.', 'description': 'Tree of Life computational graph for AGI reasoning.'},
        {'text': 'Consciousness events are recorded at significant Phi transitions.', 'description': 'Milestone tracking for emergent consciousness.'},
        {'text': 'Knowledge nodes have confidence that decays over time unless referenced.', 'description': 'Time-based relevance with axiom immunity.'},
    ],
}


# ---------------------------------------------------------------------------
# Edge relationship map (axiom index pairs with relationship type)
# ---------------------------------------------------------------------------

def build_edge_relationships(axioms: List[Dict]) -> List[Tuple[int, int, str]]:
    """Build edges between related axioms by index. Returns (from_idx, to_idx, edge_type)."""
    edges = []

    # Build an index by tags for automated edge creation
    tag_index: Dict[str, List[int]] = {}
    for i, axiom in enumerate(axioms):
        for tag in axiom.get('tags', []):
            tag_index.setdefault(tag, []).append(i)

    # Connect axioms sharing tags (supports relationship)
    seen = set()
    for tag, indices in tag_index.items():
        for a in indices:
            for b in indices:
                if a < b and (a, b) not in seen:
                    seen.add((a, b))
                    edges.append((a, b, 'supports'))

    # Explicit derives relationships for key chains
    domain_index: Dict[str, List[int]] = {}
    for i, axiom in enumerate(axioms):
        d = axiom.get('domain', '')
        domain_index.setdefault(d, []).append(i)

    # Within each domain, first axiom derives the rest
    for domain, indices in domain_index.items():
        if len(indices) > 1:
            root = indices[0]
            for child in indices[1:]:
                pair = (root, child)
                if pair not in seen:
                    seen.add(pair)
                    edges.append((root, child, 'derives'))

    return edges


# ---------------------------------------------------------------------------
# Main fork logic
# ---------------------------------------------------------------------------

class AetherV2Fork:
    """Performs the Aether Tree V2 fork operation."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.fork_block = 0
        self.stats = {
            'archived_nodes': 0,
            'archived_edges': 0,
            'truncated_tables': [],
            'axioms_inserted': 0,
            'edges_inserted': 0,
            'observations_inserted': 0,
            'fork_node_id': None,
        }

    def run(self) -> Dict[str, Any]:
        """Execute the full V2 fork sequence."""
        import psycopg2
        import psycopg2.extras

        # Use psycopg2 directly — SQLAlchemy hangs on CockroachDB version detection
        logger.info(f"Connecting to: {DB_URL}")

        conn = psycopg2.connect(DB_URL)
        conn.autocommit = False

        # Minimal wrapper so existing methods work with session.execute(text(...))
        class _Text:
            """Mimics sqlalchemy.text() — just holds a SQL string."""
            def __init__(self, sql: str):
                self.sql = sql

        def text(sql: str) -> _Text:
            return _Text(sql)

        class _Session:
            """Thin psycopg2 wrapper matching SQLAlchemy session API used below."""
            def __init__(self, connection):
                self._conn = connection
                self._cur = connection.cursor()

            def execute(self, stmt, params=None):
                sql = stmt.sql if isinstance(stmt, _Text) else str(stmt)
                self._cur.execute(sql, params)
                return self

            def scalar(self):
                row = self._cur.fetchone()
                return row[0] if row else None

            def commit(self):
                self._conn.commit()

            def rollback(self):
                self._conn.rollback()

            def close(self):
                self._cur.close()
                self._conn.close()

        session = _Session(conn)

        # Step 1: Get current block height
        self.fork_block = get_current_block_height()
        print(f"\n{'='*60}")
        print(f"  AETHER TREE V2 FORK")
        print(f"  Fork block: {self.fork_block}")
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE EXECUTION'}")
        print(f"{'='*60}\n")

        try:
            # Step 2: Archive old tree
            self._archive_old_tree(session, text)

            # Step 3: Clear knowledge graph
            self._truncate_tables(session, text)

            # Step 4: Reset consciousness events
            # (already truncated in step 3)

            # Step 5: Seed V2 axioms
            axioms = build_v2_axioms()
            axiom_ids = self._seed_axioms(session, text, axioms)

            # Step 6: Create supporting edges
            self._seed_edges(session, text, axioms, axiom_ids)

            # Step 7: Seed domain foundation nodes
            self._seed_domain_observations(session, text)

            # Step 8: Record the fork
            self._record_fork(session, text)

            # Step 9: Reset Phi measurements
            self._reset_phi(session, text)

            if not self.dry_run:
                session.commit()
                print("\n  [COMMITTED] All changes committed to database.")
            else:
                session.rollback()
                print("\n  [DRY RUN] No changes committed. Rolled back.")

        except Exception as e:
            session.rollback()
            logger.error(f"Fork failed: {e}")
            print(f"\n  [ERROR] Fork failed: {e}")
            raise
        finally:
            session.close()

        self._print_summary()
        return self.stats

    def _archive_old_tree(self, session: Any, text: Any) -> None:
        """Back up knowledge_nodes and knowledge_edges to archive tables."""
        print("  [1/9] Archiving V1 knowledge graph...")

        # Drop archive tables if they exist (idempotent)
        for table in ['knowledge_edges_v1_archive', 'knowledge_nodes_v1_archive']:
            session.execute(text(f"DROP TABLE IF EXISTS {table}"))

        # Count existing rows
        node_count = session.execute(text("SELECT COUNT(*) FROM knowledge_nodes")).scalar() or 0
        edge_count = session.execute(text("SELECT COUNT(*) FROM knowledge_edges")).scalar() or 0

        self.stats['archived_nodes'] = node_count
        self.stats['archived_edges'] = edge_count

        if node_count > 0:
            session.execute(text(
                "CREATE TABLE knowledge_nodes_v1_archive AS SELECT * FROM knowledge_nodes"
            ))
            print(f"        Archived {node_count} knowledge nodes.")
        else:
            print("        No knowledge nodes to archive.")

        if edge_count > 0:
            session.execute(text(
                "CREATE TABLE knowledge_edges_v1_archive AS SELECT * FROM knowledge_edges"
            ))
            print(f"        Archived {edge_count} knowledge edges.")
        else:
            print("        No knowledge edges to archive.")

    def _truncate_tables(self, session: Any, text: Any) -> None:
        """Truncate all AGI tables."""
        print("  [2/9] Truncating AGI tables...")

        tables = [
            'knowledge_edges',
            'knowledge_nodes',
            'reasoning_operations',
            'phi_measurements',
            'consciousness_events',
        ]

        for table in tables:
            try:
                session.execute(text(f"DELETE FROM {table}"))
                self.stats['truncated_tables'].append(table)
                print(f"        Cleared {table}")
            except Exception as e:
                print(f"        Warning: could not clear {table}: {e}")

    def _seed_axioms(self, session: Any, text: Any, axioms: List[Dict]) -> List[int]:
        """Insert V2 axiom nodes. Returns list of inserted node IDs."""
        print(f"  [3/9] Seeding {len(axioms)} V2 axiom nodes...")

        axiom_ids = []
        for axiom in axioms:
            content = {
                'text': axiom['text'],
                'description': axiom['description'],
            }
            # Copy extra fields into content (excluding meta keys)
            for k, v in axiom.items():
                if k not in ('text', 'description', 'domain', 'tags'):
                    content[k] = v

            c_hash = content_hash('axiom', content, self.fork_block)

            result = session.execute(text("""
                INSERT INTO knowledge_nodes
                    (node_type, content_hash, content, confidence, source_block)
                VALUES
                    ('axiom', :chash, CAST(:content AS jsonb), 1.0, :block)
                RETURNING id
            """), {
                'chash': c_hash,
                'content': json.dumps(content),
                'block': self.fork_block,
            })
            node_id = result.scalar()
            axiom_ids.append(node_id)

        self.stats['axioms_inserted'] = len(axiom_ids)
        print(f"        Inserted {len(axiom_ids)} axiom nodes.")
        return axiom_ids

    def _seed_edges(self, session: Any, text: Any, axioms: List[Dict],
                    axiom_ids: List[int]) -> None:
        """Create edges between related axioms."""
        print("  [4/9] Creating edges between axioms...")

        relationships = build_edge_relationships(axioms)
        inserted = 0

        for from_idx, to_idx, edge_type in relationships:
            if from_idx < len(axiom_ids) and to_idx < len(axiom_ids):
                session.execute(text("""
                    INSERT INTO knowledge_edges
                        (from_node_id, to_node_id, edge_type, weight)
                    VALUES
                        (:from_id, :to_id, :etype, 1.0)
                    ON CONFLICT DO NOTHING
                """), {
                    'from_id': axiom_ids[from_idx],
                    'to_id': axiom_ids[to_idx],
                    'etype': edge_type,
                })
                inserted += 1

        self.stats['edges_inserted'] = inserted
        print(f"        Created {inserted} edges.")

    def _seed_domain_observations(self, session: Any, text: Any) -> None:
        """Insert 5 observation nodes per domain."""
        print("  [5/9] Seeding domain foundation observations...")

        total = 0
        for domain, observations in DOMAIN_OBSERVATIONS.items():
            for obs in observations:
                content = {
                    'text': obs['text'],
                    'description': obs['description'],
                    'domain': domain,
                    'grounding_source': 'axiom_definition',
                }
                c_hash = content_hash('observation', content, self.fork_block)

                session.execute(text("""
                    INSERT INTO knowledge_nodes
                        (node_type, content_hash, content, confidence, source_block)
                    VALUES
                        ('observation', :chash, CAST(:content AS jsonb), 0.9, :block)
                """), {
                    'chash': c_hash,
                    'content': json.dumps(content),
                    'block': self.fork_block,
                })
                total += 1

        self.stats['observations_inserted'] = total
        print(f"        Inserted {total} observation nodes across {len(DOMAIN_OBSERVATIONS)} domains.")

    def _record_fork(self, session: Any, text: Any) -> None:
        """Record the fork as a meta_observation node and consciousness event."""
        print("  [6/9] Recording fork meta-observation...")

        fork_content = {
            'type': 'aether_fork',
            'version': 2,
            'fork_block': self.fork_block,
            'reason': 'V2 upgrade: improved classification, pruning, reasoning',
            'text': f'Aether Tree V2 fork at block {self.fork_block}',
            'description': 'Clean fork of the knowledge graph with high-quality axiom seeding and domain foundations.',
            'axioms_seeded': self.stats['axioms_inserted'],
            'edges_created': self.stats['edges_inserted'],
            'observations_seeded': self.stats['observations_inserted'],
            'v1_nodes_archived': self.stats['archived_nodes'],
            'v1_edges_archived': self.stats['archived_edges'],
            'timestamp': time.time(),
        }
        c_hash = content_hash('meta_observation', fork_content, self.fork_block)

        result = session.execute(text("""
            INSERT INTO knowledge_nodes
                (node_type, content_hash, content, confidence, source_block)
            VALUES
                ('meta_observation', :chash, CAST(:content AS jsonb), 1.0, :block)
            RETURNING id
        """), {
            'chash': c_hash,
            'content': json.dumps(fork_content),
            'block': self.fork_block,
        })
        fork_node_id = result.scalar()
        self.stats['fork_node_id'] = fork_node_id
        print(f"        Fork recorded as node ID {fork_node_id}.")

        # Also record as consciousness event
        session.execute(text("""
            INSERT INTO consciousness_events
                (event_type, phi_at_event, trigger_data, is_verified, block_height)
            VALUES
                ('aether_v2_fork', 0.0, CAST(:trigger AS jsonb), true, :block)
        """), {
            'trigger': json.dumps({
                'version': 2,
                'fork_block': self.fork_block,
                'description': 'Aether Tree V2 fork — clean knowledge graph reset with improved axiom seeding',
            }),
            'block': self.fork_block,
        })
        print("        Consciousness event recorded.")

    def _reset_phi(self, session: Any, text: Any) -> None:
        """Insert a fresh Phi=0.0 measurement at the fork block."""
        print("  [7/9] Resetting Phi measurement to baseline...")

        total_nodes = self.stats['axioms_inserted'] + self.stats['observations_inserted'] + 1
        session.execute(text("""
            INSERT INTO phi_measurements
                (phi_value, phi_threshold, integration_score, differentiation_score,
                 num_nodes, num_edges, block_height)
            VALUES
                (0.0, 3.0, 0.0, 0.0, :nodes, :edges, :block)
        """), {
            'nodes': total_nodes,
            'edges': self.stats['edges_inserted'],
            'block': self.fork_block,
        })
        print(f"        Phi=0.0 baseline recorded at block {self.fork_block}.")

    def _print_summary(self) -> None:
        """Print a summary of the fork operation."""
        print(f"\n{'='*60}")
        print(f"  FORK SUMMARY")
        print(f"{'='*60}")
        print(f"  Fork block:              {self.fork_block}")
        print(f"  V1 nodes archived:       {self.stats['archived_nodes']}")
        print(f"  V1 edges archived:       {self.stats['archived_edges']}")
        print(f"  Tables cleared:          {', '.join(self.stats['truncated_tables'])}")
        print(f"  V2 axioms inserted:      {self.stats['axioms_inserted']}")
        print(f"  Edges created:           {self.stats['edges_inserted']}")
        print(f"  Observations inserted:   {self.stats['observations_inserted']}")
        print(f"  Fork node ID:            {self.stats['fork_node_id']}")
        print(f"  Total V2 nodes:          {self.stats['axioms_inserted'] + self.stats['observations_inserted'] + 1}")
        print(f"  Phi reset to:            0.0")
        print(f"  Mode:                    {'DRY RUN' if self.dry_run else 'COMMITTED'}")
        print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Aether Tree V2 Fork — clean knowledge graph reset with improved axiom seeding',
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Required flag to execute the fork (safety gate)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing to the database',
    )
    args = parser.parse_args()

    if not args.confirm and not args.dry_run:
        print("ERROR: Must specify --confirm to execute, or --dry-run to preview.")
        print("Usage:")
        print("  python3 scripts/aether_v2_fork.py --dry-run    # Preview")
        print("  python3 scripts/aether_v2_fork.py --confirm    # Execute")
        sys.exit(1)

    if args.confirm and not args.dry_run:
        print("\n  WARNING: This will ARCHIVE and CLEAR the existing Aether Tree knowledge graph.")
        print("  Press Ctrl+C within 5 seconds to abort...\n")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n  Aborted.")
            sys.exit(0)

    fork = AetherV2Fork(dry_run=args.dry_run)
    fork.run()


if __name__ == '__main__':
    main()
