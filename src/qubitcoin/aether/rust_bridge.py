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

    def _get(name: str):
        return getattr(aether_core, name, None)

    # aether-types
    RustKeterNode = _get("KeterNode")
    RustKeterEdge = _get("KeterEdge")

    # aether-graph
    RustKnowledgeGraph = _get("KnowledgeGraph")

    # aether-phi
    RustPhiCalculator = _get("PhiCalculator")

    # aether-memory
    RustVectorIndex = _get("VectorIndex")
    RustHNSWIndex = _get("HNSWIndex")
    RustWorkingMemory = _get("WorkingMemory")
    RustMemoryManager = _get("MemoryManager")
    RustLongTermMemory = _get("LongTermMemory")

    # aether-neural
    RustGATReasoner = _get("RustGATReasoner")

    # aether-sephirot
    RustCSFTransport = _get("CSFTransport")
    RustCSFMessage = _get("CSFMessage")

    # aether-cognitive
    RustEmotionalState = _get("EmotionalState")
    RustCuriosityEngine = _get("CuriosityEngine")
    RustMetacognitionEngine = _get("MetacognitionEngine")
    RustSelfImprovementEngine = _get("SelfImprovementEngine")

    # aether-safety
    RustContentFilter = _get("ContentFilter")
    RustGevurahVeto = _get("GevurahVeto")
    RustSafetyManager = _get("SafetyManager")
    RustAuditLog = _get("AuditLog")

    # aether-infra
    RustAPIKeyVault = _get("APIKeyVault")
    RustCircuitBreaker = _get("CircuitBreaker")

    RUST_AVAILABLE = True
    exports = len([a for a in dir(aether_core) if not a.startswith("_")])
    logger.info("aether_core Rust extension loaded — %d exports available", exports)
except ImportError:
    logger.info("aether_core Rust extension not installed — running pure Python")
except Exception as exc:
    logger.warning("aether_core Rust extension failed to load: %s", exc)
