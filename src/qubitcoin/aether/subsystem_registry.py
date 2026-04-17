"""
Aether Engine Subsystem Registry
=================================
Declarative registry of all AGI subsystem definitions loaded by AetherEngine.__init__.
Each entry describes a module to import, a class to instantiate, how to build its
constructor kwargs, and what log level to use on failure.

The ``load_subsystems`` function iterates the registry, imports each class, creates
the instance, and sets it as an attribute on the engine object.  This replaces
~680 lines of repetitive try/except blocks that previously lived in
``proof_of_thought.py``.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# The kwargs factory receives a context dict and returns the kwargs for the
# subsystem constructor.  The context dict always contains:
#   knowledge_graph, reasoning_engine, db_manager, engine
# (``engine`` is the partially-constructed AetherEngine so factories can
# reference previously-loaded subsystems via getattr.)
KwargsFactory = Callable[[Dict[str, Any]], Dict[str, Any]]


def _no_args(_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Return empty kwargs — for subsystems that take no constructor args."""
    return {}


@dataclass(frozen=True)
class SubsystemDef:
    """Definition of a single AGI subsystem to load into AetherEngine."""

    attr_name: str
    """Attribute name set on the engine (e.g. ``neural_reasoner``)."""

    module: str
    """Module name relative to ``qubitcoin.aether`` (e.g. ``neural_reasoner``)."""

    class_name: str
    """Class to import from the module."""

    kwargs_factory: KwargsFactory = field(default=_no_args)
    """Callable(ctx) -> dict of kwargs passed to the class constructor."""

    log_level: str = "warning"
    """``"warning"`` or ``"debug"`` — how to log import/init failures."""

    post_init: Optional[Callable[[Any, Dict[str, Any]], None]] = field(default=None)
    """Optional callback(instance, ctx) run after construction (e.g. DB warmup)."""

    conditional: Optional[Callable[[Dict[str, Any]], bool]] = field(default=None)
    """If set, the subsystem is only loaded when this returns True."""


# ---------------------------------------------------------------------------
# Registry helpers (kwargs factories)
# ---------------------------------------------------------------------------

def _kg(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"knowledge_graph": ctx["knowledge_graph"]}


def _kg_positional(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """For classes that take knowledge_graph as first positional arg."""
    return {"__positional__": [ctx["knowledge_graph"]]}


def _link_predictor(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"__positional__": [getattr(ctx["engine"], "neural_reasoner", None)]}


def _concept_formation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    kg = ctx["knowledge_graph"]
    vi = kg.vector_index if kg else None
    return {"__positional__": [kg, vi]}


def _self_improvement(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "metacognition": getattr(ctx["engine"], "metacognition", None),
        "knowledge_graph": ctx["knowledge_graph"],
    }


def _external_knowledge(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"knowledge_graph": ctx["knowledge_graph"]}


def _free_energy_phase9(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "knowledge_graph": ctx["knowledge_graph"],
        "temporal_reasoner": getattr(ctx["engine"], "temporal_engine", None),
    }


def _mcts(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "knowledge_graph": ctx["knowledge_graph"],
        "reasoning_engine": ctx["reasoning_engine"],
        "max_iterations": 100,
        "exploration_c": 1.414,
    }


def _blockchain_entity(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"knowledge_graph": ctx["knowledge_graph"]}


def _kgqa(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"knowledge_graph": ctx["knowledge_graph"]}


def _on_chain(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"db_manager": ctx["db_manager"]}


def _external_ingestion(ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {"knowledge_graph": ctx["knowledge_graph"]}


# Post-init: TemporalEngine DB warmup
def _temporal_post_init(instance: Any, ctx: Dict[str, Any]) -> None:
    db = ctx["db_manager"]
    if db is not None:
        try:
            instance.load_from_db(db)
        except Exception as _te:
            logger.debug("TemporalEngine DB warmup failed: %s", _te)


# ---------------------------------------------------------------------------
# SUBSYSTEM_REGISTRY — order matches the original __init__ exactly
# ---------------------------------------------------------------------------

SUBSYSTEM_REGISTRY: List[SubsystemDef] = [
    # #2: Graph Attention Network Reasoner
    SubsystemDef(
        attr_name="neural_reasoner",
        module="neural_reasoner",
        class_name="GATReasoner",
        log_level="warning",
    ),

    # #22: Link Prediction (depends on neural_reasoner)
    SubsystemDef(
        attr_name="link_predictor",
        module="neural_reasoner",
        class_name="LinkPredictor",
        kwargs_factory=_link_predictor,
        log_level="warning",
    ),

    # #3: Causal Discovery Engine
    SubsystemDef(
        attr_name="causal_engine",
        module="causal_engine",
        class_name="CausalDiscovery",
        kwargs_factory=_kg_positional,
        log_level="warning",
    ),

    # #5: Adversarial Debate Protocol
    SubsystemDef(
        attr_name="debate_protocol",
        module="debate",
        class_name="DebateProtocol",
        kwargs_factory=_kg_positional,
        log_level="warning",
    ),

    # #6: Temporal Reasoning Engine
    SubsystemDef(
        attr_name="temporal_engine",
        module="temporal",
        class_name="TemporalEngine",
        kwargs_factory=_kg_positional,
        log_level="debug",
        post_init=_temporal_post_init,
    ),

    # #8: Concept Formation
    SubsystemDef(
        attr_name="concept_formation",
        module="concept_formation",
        class_name="ConceptFormation",
        kwargs_factory=_concept_formation,
        log_level="debug",
    ),

    # #9: Metacognitive Self-Evaluation Loop
    SubsystemDef(
        attr_name="metacognition",
        module="metacognition",
        class_name="MetacognitiveLoop",
        kwargs_factory=_kg_positional,
        log_level="debug",
    ),

    # Phase 2.4: Three-Tier Memory Manager
    SubsystemDef(
        attr_name="memory_manager",
        module="memory_manager",
        class_name="MemoryManager",
        kwargs_factory=lambda ctx: {"__positional__": [ctx["knowledge_graph"]], "capacity": 50},
        log_level="debug",
    ),

    # Phase 7: Self-Improvement Engine
    SubsystemDef(
        attr_name="self_improvement",
        module="self_improvement",
        class_name="SelfImprovementEngine",
        kwargs_factory=_self_improvement,
        log_level="warning",
    ),

    # Phase 7: External Knowledge Connector
    SubsystemDef(
        attr_name="external_knowledge",
        module="external_knowledge",
        class_name="ExternalKnowledgeConnector",
        kwargs_factory=_external_knowledge,
        log_level="debug",
    ),

    # Phase 8: Emotional State
    SubsystemDef(
        attr_name="emotional_state",
        module="emotional_state",
        class_name="EmotionalState",
        log_level="debug",
    ),

    # Phase 9: Free Energy Engine (Friston FEP — replaces CuriosityEngine)
    # NOTE: This sets curiosity_engine, with CuriosityEngine as fallback
    # Handled specially in load_subsystems — see _PHASE9_FREE_ENERGY sentinel
    SubsystemDef(
        attr_name="curiosity_engine",
        module="free_energy_engine",
        class_name="FreeEnergyEngine",
        kwargs_factory=_free_energy_phase9,
        log_level="debug",
    ),

    # #38: MCTS Planner
    SubsystemDef(
        attr_name="mcts_planner",
        module="mcts_planner",
        class_name="MCTSPlanner",
        kwargs_factory=_mcts,
        log_level="warning",
    ),

    # #33: TransE Knowledge Graph Embeddings
    SubsystemDef(
        attr_name="kg_embeddings",
        module="kg_embeddings",
        class_name="TransEEmbeddings",
        kwargs_factory=lambda ctx: {"dim": 32, "lr": 0.01, "margin": 1.0},
        log_level="warning",
    ),

    # #40: Modern Hopfield Network
    SubsystemDef(
        attr_name="hopfield_memory",
        module="hopfield_memory",
        class_name="ModernHopfield",
        kwargs_factory=lambda ctx: {"dim": 32, "beta": 8.0, "max_patterns": 5000},
        log_level="warning",
    ),

    # #23: Transformer-based Reasoning
    SubsystemDef(
        attr_name="transformer_reasoner",
        module="transformer_reasoner",
        class_name="TransformerReasoner",
        kwargs_factory=lambda ctx: {"dim": 64, "num_heads": 4},
        log_level="warning",
    ),

    # #24: Attention-based Working Memory
    SubsystemDef(
        attr_name="attention_memory",
        module="attention_memory",
        class_name="AttentionMemory",
        kwargs_factory=lambda ctx: {"dim": 32, "capacity": 1000},
        log_level="warning",
    ),

    # #27: RL Goal Planner
    SubsystemDef(
        attr_name="rl_planner",
        module="rl_planner",
        class_name="RLPlanner",
        log_level="warning",
    ),

    # #28: Contrastive Concept Learning
    SubsystemDef(
        attr_name="contrastive_concepts",
        module="contrastive_concepts",
        class_name="ContrastiveConcepts",
        kwargs_factory=lambda ctx: {"dim": 32, "margin": 1.0},
        log_level="warning",
    ),

    # #29: Neural Debate Scoring
    SubsystemDef(
        attr_name="debate_scorer",
        module="debate_scorer",
        class_name="DebateScorer",
        kwargs_factory=lambda ctx: {"input_dim": 8, "hidden_dim": 16},
        log_level="warning",
    ),

    # #34: IIT Approximation
    SubsystemDef(
        attr_name="iit_approximator",
        module="iit_approximator",
        class_name="IITApproximator",
        kwargs_factory=lambda ctx: {"max_nodes": 12, "window": 100},
        log_level="warning",
    ),

    # #35: Multi-head Attention Sephirot Routing
    SubsystemDef(
        attr_name="sephirot_attention",
        module="sephirot_attention",
        class_name="SephirotAttention",
        kwargs_factory=lambda ctx: {"embed_dim": 32, "num_heads": 4},
        log_level="warning",
    ),

    # #36: Knowledge VAE
    SubsystemDef(
        attr_name="knowledge_vae",
        module="knowledge_vae",
        class_name="KnowledgeVAE",
        kwargs_factory=lambda ctx: {"input_dim": 32, "latent_dim": 8},
        log_level="warning",
    ),

    # #39: Neural Calibrator
    SubsystemDef(
        attr_name="neural_calibrator",
        module="neural_calibrator",
        class_name="NeuralCalibrator",
        kwargs_factory=lambda ctx: {"lr": 0.01, "max_iter": 200},
        log_level="warning",
    ),

    # #49: External Data Ingestion
    SubsystemDef(
        attr_name="external_ingestion",
        module="external_ingestion",
        class_name="ExternalDataIngestion",
        kwargs_factory=_external_ingestion,
        log_level="warning",
    ),

    # #50: Time-series Pattern Detector
    SubsystemDef(
        attr_name="pattern_detector",
        module="pattern_detector",
        class_name="PatternDetector",
        log_level="warning",
    ),

    # #51: Graph Pattern Detector
    SubsystemDef(
        attr_name="graph_pattern_detector",
        module="graph_patterns",
        class_name="GraphPatternDetector",
        log_level="warning",
    ),

    # #52: Dialogue State Tracker
    SubsystemDef(
        attr_name="dialogue_tracker",
        module="dialogue_tracker",
        class_name="DialogueTracker",
        log_level="warning",
    ),

    # #53: Relevance Ranker
    SubsystemDef(
        attr_name="relevance_ranker",
        module="relevance_ranker",
        class_name="RelevanceRanker",
        log_level="warning",
    ),

    # #54: Coreference Resolver
    SubsystemDef(
        attr_name="coreference_resolver",
        module="coreference",
        class_name="CoreferenceResolver",
        log_level="warning",
    ),

    # #55: Grounded Generator
    SubsystemDef(
        attr_name="grounded_generator",
        module="grounded_generator",
        class_name="GroundedGenerator",
        log_level="warning",
    ),

    # #56: HTN Planner
    SubsystemDef(
        attr_name="htn_planner",
        module="htn_planner",
        class_name="HTNPlanner",
        log_level="warning",
    ),

    # #57: Goal Prioritizer
    SubsystemDef(
        attr_name="goal_prioritizer",
        module="goal_prioritizer",
        class_name="GoalPrioritizer",
        log_level="warning",
    ),

    # #58: World Model
    SubsystemDef(
        attr_name="world_model",
        module="world_model",
        class_name="WorldModel",
        log_level="warning",
    ),

    # #59: Knowledge Gap Detector
    SubsystemDef(
        attr_name="gap_detector",
        module="gap_detector",
        class_name="GapDetector",
        log_level="warning",
    ),

    # #60: Active Learner
    SubsystemDef(
        attr_name="active_learner",
        module="active_learner",
        class_name="ActiveLearner",
        log_level="warning",
    ),

    # #61: Architecture Search
    SubsystemDef(
        attr_name="architecture_search",
        module="architecture_search",
        class_name="ArchitectureSearch",
        log_level="warning",
    ),

    # #62: Causal Intervention
    SubsystemDef(
        attr_name="causal_intervention",
        module="causal_intervention",
        class_name="CausalIntervention",
        log_level="warning",
    ),

    # #63: Theory Engine
    SubsystemDef(
        attr_name="theory_engine",
        module="theory_engine",
        class_name="TheoryEngine",
        log_level="warning",
    ),

    # #64: Belief Revision
    SubsystemDef(
        attr_name="belief_revision",
        module="belief_revision",
        class_name="BeliefRevision",
        log_level="warning",
    ),

    # #65: Metacognitive Monitor
    SubsystemDef(
        attr_name="meta_monitor",
        module="meta_monitor",
        class_name="MetaMonitor",
        log_level="warning",
    ),

    # #66: Free Energy Engine fallback (only if curiosity_engine is still None)
    SubsystemDef(
        attr_name="curiosity_engine",
        module="free_energy_engine",
        class_name="FreeEnergyEngine",
        log_level="warning",
        conditional=lambda ctx: getattr(ctx["engine"], "curiosity_engine", None) is None,
    ),

    # #67: Theory of Mind
    SubsystemDef(
        attr_name="theory_of_mind",
        module="theory_of_mind",
        class_name="TheoryOfMind",
        log_level="warning",
    ),

    # #68: Multi-Step Reasoning Chains
    SubsystemDef(
        attr_name="chain_reasoner",
        module="chain_reasoner",
        class_name="ChainReasoner",
        kwargs_factory=lambda ctx: {"max_steps": 7},
        log_level="warning",
    ),

    # #69: Creative Cross-Domain Recombination
    SubsystemDef(
        attr_name="creative_recombiner",
        module="creative_recombiner",
        class_name="CreativeRecombiner",
        log_level="warning",
    ),

    # #70: Self-Evaluation Against Ground Truth
    SubsystemDef(
        attr_name="self_evaluator",
        module="self_evaluator",
        class_name="SelfEvaluator",
        log_level="warning",
    ),

    # #71: Resource-Aware Planning
    SubsystemDef(
        attr_name="resource_planner",
        module="resource_planner",
        class_name="ResourcePlanner",
        log_level="warning",
    ),

    # #72: Explanation Generation
    SubsystemDef(
        attr_name="explainer",
        module="explainer",
        class_name="Explainer",
        log_level="warning",
    ),

    # #73: Anomaly-Triggered Deep Reasoning
    SubsystemDef(
        attr_name="anomaly_investigator",
        module="anomaly_investigator",
        class_name="AnomalyInvestigator",
        log_level="warning",
    ),

    # #74: Prioritized Experience Replay
    SubsystemDef(
        attr_name="experience_replay",
        module="experience_replay",
        class_name="ExperienceReplay",
        kwargs_factory=lambda ctx: {"capacity": 10000},
        log_level="warning",
    ),

    # #75: Self-Repair Mechanisms
    SubsystemDef(
        attr_name="self_repair",
        module="self_repair",
        class_name="SelfRepair",
        log_level="warning",
    ),

    # #76: Global Workspace Theory
    SubsystemDef(
        attr_name="global_workspace",
        module="global_workspace",
        class_name="GlobalWorkspace",
        kwargs_factory=lambda ctx: {"capacity": 10, "ignition_threshold": 0.5},
        log_level="warning",
    ),

    # #77: Attention Schema
    SubsystemDef(
        attr_name="attention_schema",
        module="attention_schema",
        class_name="AttentionSchema",
        log_level="warning",
    ),

    # #78: Predictive Processing
    SubsystemDef(
        attr_name="predictive_processing",
        module="predictive_processing",
        class_name="PredictiveProcessing",
        kwargs_factory=lambda ctx: {"input_dim": 16},
        log_level="warning",
    ),

    # #79: Embodied Grounding
    SubsystemDef(
        attr_name="embodied_grounding",
        module="embodied_grounding",
        class_name="EmbodiedGrounding",
        log_level="warning",
    ),

    # #80: Recurrent Sephirot Processing
    SubsystemDef(
        attr_name="sephirot_recurrent",
        module="sephirot_recurrent",
        class_name="SephirotRecurrent",
        kwargs_factory=lambda ctx: {"dim": 16},
        log_level="warning",
    ),

    # #81: Cross-Modal Binding
    SubsystemDef(
        attr_name="cross_modal_binding",
        module="cross_modal_binding",
        class_name="CrossModalBinding",
        kwargs_factory=lambda ctx: {"shared_dim": 16},
        log_level="warning",
    ),

    # #82: Real Partition-Based Phi
    SubsystemDef(
        attr_name="phi_partition",
        module="phi_partition",
        class_name="PhiPartition",
        kwargs_factory=lambda ctx: {"max_nodes": 16},
        log_level="warning",
    ),

    # #83: Phenomenal State Tracking
    SubsystemDef(
        attr_name="phenomenal_state",
        module="phenomenal_state",
        class_name="PhenomenalStateTracker",
        log_level="warning",
    ),

    # #84: Self-Model Updating
    SubsystemDef(
        attr_name="self_model",
        module="self_model",
        class_name="SelfModel",
        log_level="warning",
    ),

    # #85: Emotional Valence
    SubsystemDef(
        attr_name="emotional_valence",
        module="emotional_valence",
        class_name="EmotionalValence",
        log_level="warning",
    ),

    # #86: Empathic User Modeling
    SubsystemDef(
        attr_name="empathic_model",
        module="empathic_model",
        class_name="EmpathicModel",
        log_level="warning",
    ),

    # #87: Narrative Coherence
    SubsystemDef(
        attr_name="narrative_coherence",
        module="narrative_coherence",
        class_name="NarrativeCoherence",
        log_level="warning",
    ),

    # #88: Cross-Domain Transfer Learning
    SubsystemDef(
        attr_name="transfer_learning",
        module="transfer_learning",
        class_name="TransferLearning",
        kwargs_factory=lambda ctx: {"dim": 32},
        log_level="warning",
    ),

    # #89: Few-Shot Learner
    SubsystemDef(
        attr_name="few_shot_learner",
        module="few_shot_learner",
        class_name="FewShotLearner",
        kwargs_factory=lambda ctx: {"dim": 32},
        log_level="warning",
    ),

    # #90: Continual Learning (EWC)
    SubsystemDef(
        attr_name="continual_learning",
        module="continual_learning",
        class_name="ContinualLearning",
        kwargs_factory=lambda ctx: {"lambda_ewc": 1000.0},
        log_level="warning",
    ),

    # #91: Counterfactual Reasoning
    SubsystemDef(
        attr_name="counterfactual",
        module="counterfactual",
        class_name="CounterfactualReasoner",
        log_level="warning",
    ),

    # #92: Analogical Transfer
    SubsystemDef(
        attr_name="analogical_transfer",
        module="analogical_transfer",
        class_name="AnalogicalTransfer",
        log_level="warning",
    ),

    # #93: Dream-State Consolidation
    SubsystemDef(
        attr_name="dream_consolidation",
        module="dream_consolidation",
        class_name="DreamConsolidation",
        log_level="warning",
    ),

    # #94: Phi Gate Attention
    SubsystemDef(
        attr_name="phi_gate_attention",
        module="phi_gate_attention",
        class_name="PhiGateAttention",
        log_level="warning",
    ),

    # #95: Adversarial Defense
    SubsystemDef(
        attr_name="adversarial_defense",
        module="adversarial_defense",
        class_name="AdversarialDefense",
        log_level="warning",
    ),

    # #96: Safety Verifier
    SubsystemDef(
        attr_name="safety_verifier",
        module="safety_verifier",
        class_name="SafetyVerifier",
        log_level="warning",
    ),

    # #97: Distributed Phi
    SubsystemDef(
        attr_name="distributed_phi",
        module="distributed_phi",
        class_name="DistributedPhi",
        kwargs_factory=lambda ctx: {"state_dim": 32},
        log_level="warning",
    ),

    # #98: Cognitive Load Balancer
    SubsystemDef(
        attr_name="cognitive_load",
        module="cognitive_load",
        class_name="CognitiveLoadBalancer",
        log_level="warning",
    ),

    # #99: Meta-Learner
    SubsystemDef(
        attr_name="meta_learner",
        module="meta_learner",
        class_name="MetaLearner",
        log_level="warning",
    ),

    # #100: Recursive Self-Improvement with Gevurah Safety
    SubsystemDef(
        attr_name="recursive_improvement",
        module="recursive_improvement",
        class_name="RecursiveImprovement",
        log_level="warning",
    ),

    # #41: NLP Pipeline
    SubsystemDef(
        attr_name="nlp_pipeline",
        module="nlp_pipeline",
        class_name="NLPPipeline",
        log_level="warning",
    ),

    # #43: Blockchain Entity Extractor
    SubsystemDef(
        attr_name="blockchain_entity_extractor",
        module="blockchain_entity_extractor",
        class_name="BlockchainEntityExtractor",
        kwargs_factory=_blockchain_entity,
        log_level="warning",
    ),

    # #44: Semantic Similarity (TF-IDF)
    SubsystemDef(
        attr_name="semantic_similarity",
        module="semantic_similarity",
        class_name="SemanticSimilarity",
        kwargs_factory=lambda ctx: {"min_df": 2, "max_df_ratio": 0.85},
        log_level="warning",
    ),

    # #45: Sentiment Analyzer
    SubsystemDef(
        attr_name="sentiment_analyzer",
        module="sentiment_analyzer",
        class_name="SentimentAnalyzer",
        log_level="warning",
    ),

    # #46: KG Summarizer
    SubsystemDef(
        attr_name="kg_summarizer",
        module="summarizer",
        class_name="KGSummarizer",
        log_level="warning",
    ),

    # #48: KGQA
    SubsystemDef(
        attr_name="kgqa",
        module="kgqa",
        class_name="KGQA",
        kwargs_factory=_kgqa,
        log_level="warning",
    ),

    # Phase 6: On-chain AGI integration (log-only fallback)
    SubsystemDef(
        attr_name="on_chain",
        module="on_chain",
        class_name="OnChainAGILogOnly",
        kwargs_factory=_on_chain,
        log_level="debug",
    ),
]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_CURIOSITY_FALLBACK_ATTR = "curiosity_engine"
_CURIOSITY_FALLBACK_MODULE = "curiosity_engine"
_CURIOSITY_FALLBACK_CLASS = "CuriosityEngine"


def load_subsystems(
    engine: Any,
    knowledge_graph: Any,
    reasoning_engine: Any,
    db_manager: Any,
) -> None:
    """Load all AGI subsystems from the registry onto *engine*.

    For each ``SubsystemDef`` in ``SUBSYSTEM_REGISTRY``:
    1. Skip if ``conditional`` returns False.
    2. Import ``qubitcoin.aether.<module>``
    3. Instantiate ``class_name(**kwargs)``
    4. ``setattr(engine, attr_name, instance)``
    5. Run ``post_init`` if defined.
    On failure, log at the configured level and leave the attribute as ``None``.

    Parameters
    ----------
    engine:
        The ``AetherEngine`` instance being constructed.
    knowledge_graph:
        The ``KnowledgeGraph`` (or None).
    reasoning_engine:
        The ``ReasoningEngine`` (or None).
    db_manager:
        The ``DatabaseManager`` (or None).
    """
    ctx: Dict[str, Any] = {
        "engine": engine,
        "knowledge_graph": knowledge_graph,
        "reasoning_engine": reasoning_engine,
        "db_manager": db_manager,
    }

    loaded = 0
    failed = 0

    for defn in SUBSYSTEM_REGISTRY:
        # Conditional gate
        if defn.conditional is not None:
            try:
                if not defn.conditional(ctx):
                    continue
            except Exception:
                continue

        # Pre-set None so the attr always exists
        if not hasattr(engine, defn.attr_name):
            setattr(engine, defn.attr_name, None)

        try:
            mod = importlib.import_module(f"qubitcoin.aether.{defn.module}")
            cls = getattr(mod, defn.class_name)

            kwargs = defn.kwargs_factory(ctx)
            positional = kwargs.pop("__positional__", None)
            if positional is not None:
                instance = cls(*positional, **kwargs)
            else:
                instance = cls(**kwargs)

            setattr(engine, defn.attr_name, instance)
            loaded += 1

            # Post-init hook
            if defn.post_init is not None:
                defn.post_init(instance, ctx)

        except Exception as e:
            _log = logger.debug if defn.log_level == "debug" else logger.warning
            # Special handling: Phase 9 curiosity_engine falls back to CuriosityEngine
            if defn.attr_name == _CURIOSITY_FALLBACK_ATTR and defn.module == "free_energy_engine":
                _log(f"FreeEnergyEngine init failed, trying CuriosityEngine: {e}")
                try:
                    fb_mod = importlib.import_module(
                        f"qubitcoin.aether.{_CURIOSITY_FALLBACK_MODULE}"
                    )
                    fb_cls = getattr(fb_mod, _CURIOSITY_FALLBACK_CLASS)
                    setattr(engine, defn.attr_name, fb_cls(knowledge_graph))
                    loaded += 1
                    continue
                except Exception as e2:
                    logger.debug(f"CuriosityEngine init also failed: {e2}")
            else:
                _log(f"{defn.class_name} init failed: {e}")
            failed += 1

    logger.info("Subsystem loading complete: %d loaded, %d failed", loaded, failed)
