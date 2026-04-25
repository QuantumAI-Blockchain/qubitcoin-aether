"""
Aether Mind V5 — Neural Cognitive Engine (Rust)
================================================
The Python aether package is now a thin proxy layer.
All AI inference runs in the Rust aether-mind binary on port 5003.
This package provides import-compatible stubs so the Python node
can function as an API/DB gateway without loading 69K LOC of AI code.
"""

from ._v5_proxy import (
    # Core
    KnowledgeGraph,
    KeterNode,
    PhiCalculator,
    ReasoningEngine,
    ReasoningStep,
    ProofOfThought,
    AetherEngine,
    # Genesis
    AetherGenesis,
    # Chat
    AetherChat,
    ChatMemory,
    # Fees
    AetherFeeManager,
    # Sephirot
    SephirotManager,
    SephirahRole,
    SephirahState,
    # Sephirot Nodes
    BaseSephirah,
    NodeMessage,
    ProcessingResult,
    KeterNode,
    ChochmahNode,
    BinahNode,
    ChesedNode,
    GevurahNode,
    TiferetNode,
    NetzachNode,
    HodNode,
    YesodNode,
    MalkuthNode,
    create_all_nodes,
    # CSF
    CSFTransport,
    CSFMessage,
    # Pineal
    PinealOrchestrator,
    CircadianPhase,
    # Memory
    MemoryManager,
    MemoryType,
    # Safety
    SafetyManager,
    GevurahVeto,
    MultiNodeConsensus,
    # Knowledge
    KnowledgeExtractor,
    # Task Protocol
    ProofOfThoughtProtocol,
    TaskMarket,
    ValidatorRegistry,
    # Consciousness
    ConsciousnessDashboard,
    # Query
    QueryTranslator,
    QueryIntent,
    QueryResult,
    # WebSocket
    AetherWSManager,
    AetherWSClient,
    # Circulation
    CirculationTracker,
    CirculationSnapshot,
    # LLM
    LLMAdapter,
    LLMResponse,
    LLMAdapterManager,
    OpenAIAdapter,
    ClaudeAdapter,
    LocalAdapter,
    BitNetAdapter,
    KnowledgeDistiller,
    # Seeder
    KnowledgeSeeder,
    MASTER_PROMPTS,
    # IPFS
    IPFSMemoryStore,
    # Neural
    GATReasoner,
    GATLayer,
)

__all__ = [
    'KnowledgeGraph', 'KeterNode', 'PhiCalculator', 'ReasoningEngine',
    'ProofOfThought', 'AetherEngine', 'AetherGenesis', 'AetherChat',
    'AetherFeeManager', 'SephirotManager', 'SephirahRole', 'SephirahState',
    'CSFTransport', 'CSFMessage', 'PinealOrchestrator', 'CircadianPhase',
    'MemoryManager', 'MemoryType', 'SafetyManager', 'GevurahVeto',
    'MultiNodeConsensus', 'KnowledgeExtractor', 'ProofOfThoughtProtocol',
    'TaskMarket', 'ValidatorRegistry', 'ConsciousnessDashboard',
    'QueryTranslator', 'QueryIntent', 'QueryResult',
    'AetherWSManager', 'AetherWSClient', 'CirculationTracker',
    'CirculationSnapshot', 'LLMAdapter', 'LLMResponse', 'LLMAdapterManager',
    'OpenAIAdapter', 'ClaudeAdapter', 'LocalAdapter', 'BitNetAdapter',
    'KnowledgeDistiller', 'KnowledgeSeeder', 'MASTER_PROMPTS',
    'IPFSMemoryStore', 'GATReasoner', 'GATLayer',
    'BaseSephirah', 'NodeMessage', 'ProcessingResult',
    'ChochmahNode', 'BinahNode', 'ChesedNode', 'GevurahNode',
    'TiferetNode', 'NetzachNode', 'HodNode', 'YesodNode', 'MalkuthNode',
    'create_all_nodes',
]
