"""
Rust Bridge — central import point for aether_core Rust/PyO3 bindings.

Every Python module that wants to use Rust acceleration imports from here.
If the Rust extension is not installed, all symbols are None and RUST_AVAILABLE
is False. This lets the node run in pure-Python mode without any code changes.

Usage in other modules:
    from .rust_bridge import RUST_AVAILABLE, RustEmotionalState
    if RUST_AVAILABLE and RustEmotionalState is not None:
        ...
"""

from ..utils.logger import get_logger

logger = get_logger(__name__)

RUST_AVAILABLE: bool = False

# -- aether-types --
RustKeterNode = None
RustKeterEdge = None

# -- aether-graph --
RustKnowledgeGraph = None

# -- aether-phi --
RustPhiCalculator = None

# -- aether-memory --
RustVectorIndex = None
RustHNSWIndex = None
RustWorkingMemory = None
RustMemoryManager = None
RustLongTermMemory = None

# -- aether-neural --
RustGATReasoner = None

# -- aether-sephirot --
RustCSFTransport = None
RustCSFMessage = None

# -- aether-cognitive --
RustEmotionalState = None
RustCuriosityEngine = None
RustMetacognitionEngine = None
RustSelfImprovementEngine = None

# -- aether-safety --
RustContentFilter = None
RustGevurahVeto = None
RustSafetyManager = None
RustAuditLog = None

# -- aether-infra --
RustAPIKeyVault = None
RustCircuitBreaker = None

try:
    import aether_core

    # aether-types
    RustKeterNode = aether_core.KeterNode
    RustKeterEdge = aether_core.KeterEdge

    # aether-graph
    RustKnowledgeGraph = aether_core.KnowledgeGraph

    # aether-phi
    RustPhiCalculator = aether_core.PhiCalculator

    # aether-memory
    RustVectorIndex = aether_core.VectorIndex
    RustHNSWIndex = aether_core.HNSWIndex
    RustWorkingMemory = aether_core.WorkingMemory
    RustMemoryManager = aether_core.MemoryManager
    RustLongTermMemory = aether_core.LongTermMemory

    # aether-neural
    RustGATReasoner = aether_core.RustGATReasoner

    # aether-sephirot
    RustCSFTransport = aether_core.CSFTransport
    RustCSFMessage = aether_core.CSFMessage

    # aether-cognitive
    RustEmotionalState = aether_core.EmotionalState
    RustCuriosityEngine = aether_core.CuriosityEngine
    RustMetacognitionEngine = aether_core.MetacognitionEngine
    RustSelfImprovementEngine = aether_core.SelfImprovementEngine

    # aether-safety
    RustContentFilter = aether_core.ContentFilter
    RustGevurahVeto = aether_core.GevurahVeto
    RustSafetyManager = aether_core.SafetyManager
    RustAuditLog = aether_core.AuditLog

    # aether-infra
    RustAPIKeyVault = aether_core.APIKeyVault
    RustCircuitBreaker = aether_core.CircuitBreaker

    RUST_AVAILABLE = True
    logger.info(
        "aether_core Rust extension loaded — %d exports available",
        len([a for a in dir(aether_core) if not a.startswith("_")]),
    )
except ImportError:
    logger.info("aether_core Rust extension not installed — running pure Python")
except Exception as exc:
    logger.warning("aether_core Rust extension failed to load: %s", exc)
