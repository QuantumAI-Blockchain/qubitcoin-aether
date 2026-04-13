"""
Proof-of-Thought Consensus & Aether Engine
Combines Proof-of-SUSY-Alignment with knowledge graph validation.
Validators must demonstrate meaningful reasoning (Phi > threshold) to
participate in block production.
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from ..database.models import ProofOfThought, Block
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AetherEngine:
    """
    Main Aether Tree engine that orchestrates all AGI-layer components.
    Integrates KnowledgeGraph, PhiCalculator, ReasoningEngine, and
    Proof-of-Thought consensus into the QBC block pipeline.

    AGI subsystems (Improvements #2-#9):
    - GATReasoner: Neural reasoning over knowledge graph (#2)
    - CausalDiscovery: Causal edge discovery via PC algorithm (#3)
    - DebateProtocol: Adversarial debate between Sephirot (#5)
    - TemporalEngine: Time-series analysis and prediction (#6)
    - ConceptFormation: Hierarchical concept abstraction (#8)
    - MetacognitiveLoop: Reasoning quality self-evaluation (#9)
    """

    def __init__(self, db_manager, knowledge_graph=None, phi_calculator=None,
                 reasoning_engine=None, llm_manager=None, pineal=None,
                 pot_protocol=None, csf_transport=None,
                 sephirot_manager=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self.phi = phi_calculator
        self.reasoning = reasoning_engine
        self.llm_manager = llm_manager
        self.pineal = pineal  # PinealOrchestrator for circadian phases
        self.pot_protocol = pot_protocol  # ProofOfThoughtProtocol instance
        self.csf = csf_transport  # CSFTransport for inter-Sephirot routing
        self._sephirot_manager = sephirot_manager  # SephirotManager for SUSY enforcement
        self._susy_enforcement_warned = False  # Log once when manager is missing
        self._pot_cache: Dict[int, ProofOfThought] = {}
        self._pot_cache_max = 1000  # Bound cache to prevent unbounded memory growth

        # Sephirot cognitive nodes — initialized lazily
        self._sephirot: Optional[dict] = None

        # ConsciousnessDashboard — wired after RPC app creation (see node.py)
        # Tracks integration state metrics per block
        self.consciousness_dashboard = None

        # ProofOfThoughtExplorer — wired after RPC app creation (see node.py)
        self.pot_explorer = None

        # Running counters for AGI subsystem stats
        self._contradictions_resolved: int = 0

        # --- AGI Improvement Subsystems ---
        # #2: Graph Attention Network Reasoner (critical for neural reasoning)
        self.neural_reasoner = None
        try:
            from .neural_reasoner import GATReasoner
            self.neural_reasoner = GATReasoner()
        except Exception as e:
            logger.warning(f"GATReasoner init failed — neural reasoning disabled: {e}")

        # #22: Link Prediction (GNN-based missing edge prediction)
        self.link_predictor = None
        try:
            from .neural_reasoner import LinkPredictor
            self.link_predictor = LinkPredictor(self.neural_reasoner)
        except Exception as e:
            logger.warning(f"LinkPredictor init failed — link prediction disabled: {e}")

        # #3: Causal Discovery Engine (critical for causal inference)
        self.causal_engine = None
        try:
            from .causal_engine import CausalDiscovery
            self.causal_engine = CausalDiscovery(knowledge_graph)
        except Exception as e:
            logger.warning(f"CausalDiscovery init failed — causal inference disabled: {e}")

        # #5: Adversarial Debate Protocol (critical for contradiction resolution)
        self.debate_protocol = None
        try:
            from .debate import DebateProtocol
            self.debate_protocol = DebateProtocol(knowledge_graph)
        except Exception as e:
            logger.warning(f"DebateProtocol init failed — adversarial debate disabled: {e}")

        # #6: Temporal Reasoning Engine
        self.temporal_engine = None
        try:
            from .temporal import TemporalEngine
            self.temporal_engine = TemporalEngine(knowledge_graph)
            # Warm-start from DB so predictions work immediately after restart
            if db_manager is not None:
                try:
                    self.temporal_engine.load_from_db(db_manager)
                except Exception as _te:
                    logger.debug("TemporalEngine DB warmup failed: %s", _te)
        except Exception as e:
            logger.debug(f"TemporalEngine init failed: {e}")

        # #8: Concept Formation
        self.concept_formation = None
        try:
            from .concept_formation import ConceptFormation
            vector_index = knowledge_graph.vector_index if knowledge_graph else None
            self.concept_formation = ConceptFormation(knowledge_graph, vector_index)
        except Exception as e:
            logger.debug(f"ConceptFormation init failed: {e}")

        # #9: Metacognitive Self-Evaluation Loop
        self.metacognition = None
        try:
            from .metacognition import MetacognitiveLoop
            self.metacognition = MetacognitiveLoop(knowledge_graph)
        except Exception as e:
            logger.debug(f"MetacognitiveLoop init failed: {e}")

        # Phase 2.4: Three-Tier Memory Manager
        self.memory_manager = None
        try:
            from .memory_manager import MemoryManager
            self.memory_manager = MemoryManager(knowledge_graph, capacity=50)
        except Exception as e:
            logger.debug(f"MemoryManager init failed: {e}")

        # Phase 7: Self-Improvement Engine (recursive strategy optimization)
        self.self_improvement = None
        try:
            from .self_improvement import SelfImprovementEngine
            self.self_improvement = SelfImprovementEngine(
                metacognition=self.metacognition,
                knowledge_graph=knowledge_graph,
            )
        except Exception as e:
            logger.warning(f"SelfImprovementEngine init failed: {e}")

        # Phase 7: External Knowledge Connector (Wikidata + ConceptNet grounding)
        self.external_knowledge = None
        try:
            from .external_knowledge import ExternalKnowledgeConnector
            self.external_knowledge = ExternalKnowledgeConnector(
                knowledge_graph=knowledge_graph,
            )
        except Exception as e:
            logger.debug(f"ExternalKnowledgeConnector init failed: {e}")

        # Phase 8: Emotional State (cognitive feelings derived from metrics)
        self.emotional_state = None
        try:
            from .emotional_state import EmotionalState
            self.emotional_state = EmotionalState()
        except Exception as e:
            logger.debug(f"EmotionalState init failed: {e}")

        # Phase 9: Free Energy Engine (Friston FEP — replaces CuriosityEngine)
        self.curiosity_engine = None
        try:
            from .free_energy_engine import FreeEnergyEngine
            self.curiosity_engine = FreeEnergyEngine(
                knowledge_graph=knowledge_graph,
                temporal_reasoner=getattr(self, 'temporal_engine', None),
            )
        except Exception as e:
            logger.debug(f"FreeEnergyEngine init failed, trying CuriosityEngine: {e}")
            try:
                from .curiosity_engine import CuriosityEngine
                self.curiosity_engine = CuriosityEngine(knowledge_graph)
            except Exception as e2:
                logger.debug(f"CuriosityEngine init also failed: {e2}")

        # Blocks processed counter (tracked from process_block_knowledge calls)
        self._blocks_processed: int = 0

        # Cache for expensive DB gate-stats queries (full-table LIKE scans).
        # Refreshed every _DB_GATE_STATS_TTL blocks instead of every block.
        self._db_gate_stats_cache: Optional[Dict[str, float]] = None
        self._db_gate_stats_block: int = 0
        self._DB_GATE_STATS_TTL: int = 100  # ~5.5 minutes at 3.3s blocks

        # PoT deduplication: track seen thought hashes to reject duplicates
        self._pot_hashes_seen: set = set()
        self._pot_hashes_max: int = 5000  # Bound set size

        # Phase 5.1: Curiosity-driven goal formation
        self._curiosity_goals: List[dict] = []
        self._max_curiosity_goals: int = 500
        self._curiosity_stats = {
            'goals_generated': 0, 'goals_completed': 0, 'goals_failed': 0,
            'goals_evaluated': 0,
        }

        # #38: MCTS Planner for goal decomposition & action planning
        self.mcts_planner = None
        try:
            from .mcts_planner import MCTSPlanner
            self.mcts_planner = MCTSPlanner(
                knowledge_graph=knowledge_graph,
                reasoning_engine=reasoning_engine,
                max_iterations=100,
                exploration_c=1.414,
            )
        except Exception as e:
            logger.warning(f"MCTSPlanner init failed — MCTS planning disabled: {e}")

        # How often (in blocks) MCTS replans the exploration batch
        self._mcts_replan_interval: int = 200
        self._mcts_action_queue: List[dict] = []

        # #33: TransE Knowledge Graph Embeddings
        self.kg_embeddings = None
        try:
            from .kg_embeddings import TransEEmbeddings
            self.kg_embeddings = TransEEmbeddings(dim=32, lr=0.01, margin=1.0)
        except Exception as e:
            logger.warning(f"TransEEmbeddings init failed: {e}")

        # #40: Modern Hopfield Network for Associative Memory
        self.hopfield_memory = None
        try:
            from .hopfield_memory import ModernHopfield
            self.hopfield_memory = ModernHopfield(dim=32, beta=8.0, max_patterns=5000)
        except Exception as e:
            logger.warning(f"ModernHopfield init failed: {e}")

        # #23: Transformer-based Reasoning
        self.transformer_reasoner = None
        try:
            from .transformer_reasoner import TransformerReasoner
            self.transformer_reasoner = TransformerReasoner(dim=64, num_heads=4)
        except Exception as e:
            logger.warning(f"TransformerReasoner init failed: {e}")

        # #24: Attention-based Working Memory
        self.attention_memory = None
        try:
            from .attention_memory import AttentionMemory
            self.attention_memory = AttentionMemory(dim=32, capacity=1000)
        except Exception as e:
            logger.warning(f"AttentionMemory init failed: {e}")

        # #27: RL Goal Planner
        self.rl_planner = None
        self._rl_prev_state: Optional[Any] = None
        self._rl_prev_action: Optional[str] = None
        try:
            from .rl_planner import RLPlanner
            self.rl_planner = RLPlanner()
        except Exception as e:
            logger.warning(f"RLPlanner init failed: {e}")

        # #28: Contrastive Concept Learning
        self.contrastive_concepts = None
        try:
            from .contrastive_concepts import ContrastiveConcepts
            self.contrastive_concepts = ContrastiveConcepts(dim=32, margin=1.0)
        except Exception as e:
            logger.warning(f"ContrastiveConcepts init failed: {e}")

        # #29: Neural Debate Scoring
        self.debate_scorer = None
        try:
            from .debate_scorer import DebateScorer
            self.debate_scorer = DebateScorer(input_dim=8, hidden_dim=16)
        except Exception as e:
            logger.warning(f"DebateScorer init failed: {e}")

        # #34: IIT Approximation (proper Phi via TPM bipartition search)
        self.iit_approximator = None
        try:
            from .iit_approximator import IITApproximator
            self.iit_approximator = IITApproximator(max_nodes=12, window=100)
        except Exception as e:
            logger.warning(f"IITApproximator init failed: {e}")

        # #35: Multi-head Attention Sephirot Routing
        self.sephirot_attention = None
        try:
            from .sephirot_attention import SephirotAttention
            self.sephirot_attention = SephirotAttention(embed_dim=32, num_heads=4)
        except Exception as e:
            logger.warning(f"SephirotAttention init failed: {e}")

        # #36: Knowledge VAE (subgraph compression)
        self.knowledge_vae = None
        try:
            from .knowledge_vae import KnowledgeVAE
            self.knowledge_vae = KnowledgeVAE(input_dim=32, latent_dim=8)
        except Exception as e:
            logger.warning(f"KnowledgeVAE init failed: {e}")

        # #39: Neural Calibrator (Platt scaling for confidence calibration)
        self.neural_calibrator = None
        try:
            from .neural_calibrator import NeuralCalibrator
            self.neural_calibrator = NeuralCalibrator(lr=0.01, max_iter=200)
        except Exception as e:
            logger.warning(f"NeuralCalibrator init failed: {e}")

        # Phase 5.4: Emergent communication protocol
        self._pending_digest: Optional[dict] = None
        self._seen_digests: dict = {}  # OrderedDict-like (dict preserves insertion order in 3.7+)
        self._max_seen_digests: int = 10000
        self._digests_created: int = 0
        self._digests_received: int = 0
        self._nodes_from_peers: int = 0
        self._peer_consensus_boosts: int = 0

        # #49: External Data Ingestion
        self.external_ingestion = None
        try:
            from .external_ingestion import ExternalDataIngestion
            self.external_ingestion = ExternalDataIngestion(knowledge_graph=knowledge_graph)
        except Exception as e:
            logger.warning(f"ExternalDataIngestion init failed: {e}")

        # #50: Time-series Pattern Detector
        self.pattern_detector = None
        try:
            from .pattern_detector import PatternDetector
            self.pattern_detector = PatternDetector()
        except Exception as e:
            logger.warning(f"PatternDetector init failed: {e}")

        # #51: Graph Pattern Detector (multimodal understanding)
        self.graph_pattern_detector = None
        try:
            from .graph_patterns import GraphPatternDetector
            self.graph_pattern_detector = GraphPatternDetector()
        except Exception as e:
            logger.warning(f"GraphPatternDetector init failed: {e}")

        # #52: Dialogue State Tracker (chat-time module, init only)
        self.dialogue_tracker = None
        try:
            from .dialogue_tracker import DialogueTracker
            self.dialogue_tracker = DialogueTracker()
        except Exception as e:
            logger.warning(f"DialogueTracker init failed: {e}")

        # #53: Relevance Ranker (chat-time module, init only)
        self.relevance_ranker = None
        try:
            from .relevance_ranker import RelevanceRanker
            self.relevance_ranker = RelevanceRanker()
        except Exception as e:
            logger.warning(f"RelevanceRanker init failed: {e}")

        # #54: Coreference Resolver (chat-time module, init only)
        self.coreference_resolver = None
        try:
            from .coreference import CoreferenceResolver
            self.coreference_resolver = CoreferenceResolver()
        except Exception as e:
            logger.warning(f"CoreferenceResolver init failed: {e}")

        # #55: Grounded Generator (chat-time module, init only)
        self.grounded_generator = None
        try:
            from .grounded_generator import GroundedGenerator
            self.grounded_generator = GroundedGenerator()
        except Exception as e:
            logger.warning(f"GroundedGenerator init failed: {e}")

        # #56: HTN Planner (Hierarchical Task Network)
        self.htn_planner = None
        try:
            from .htn_planner import HTNPlanner
            self.htn_planner = HTNPlanner()
        except Exception as e:
            logger.warning(f"HTNPlanner init failed: {e}")

        # #57: Goal Prioritizer (utility-based ranking)
        self.goal_prioritizer = None
        try:
            from .goal_prioritizer import GoalPrioritizer
            self.goal_prioritizer = GoalPrioritizer()
        except Exception as e:
            logger.warning(f"GoalPrioritizer init failed: {e}")

        # #58: World Model (model-based planning)
        self.world_model = None
        self._world_model_prev_state = None
        self._world_model_prev_action: Optional[str] = None
        try:
            from .world_model import WorldModel
            self.world_model = WorldModel()
        except Exception as e:
            logger.warning(f"WorldModel init failed: {e}")

        # #59: Knowledge Gap Detector
        self.gap_detector = None
        try:
            from .gap_detector import GapDetector
            self.gap_detector = GapDetector()
        except Exception as e:
            logger.warning(f"GapDetector init failed: {e}")

        # #60: Active Learner (training data selection)
        self.active_learner = None
        try:
            from .active_learner import ActiveLearner
            self.active_learner = ActiveLearner()
        except Exception as e:
            logger.warning(f"ActiveLearner init failed: {e}")

        # #61: Architecture Search (NAS-lite)
        self.architecture_search = None
        try:
            from .architecture_search import ArchitectureSearch
            self.architecture_search = ArchitectureSearch()
        except Exception as e:
            logger.warning(f"ArchitectureSearch init failed: {e}")

        # #62: Causal Intervention (do-calculus)
        self.causal_intervention = None
        try:
            from .causal_intervention import CausalIntervention
            self.causal_intervention = CausalIntervention()
        except Exception as e:
            logger.warning(f"CausalIntervention init failed: {e}")

        # #63: Theory Engine (hypothesis generation & testing)
        self.theory_engine = None
        try:
            from .theory_engine import TheoryEngine
            self.theory_engine = TheoryEngine()
        except Exception as e:
            logger.warning(f"TheoryEngine init failed: {e}")

        # #64: Belief Revision (AGM-style)
        self.belief_revision = None
        self._belief_set: set = set()
        try:
            from .belief_revision import BeliefRevision
            self.belief_revision = BeliefRevision()
        except Exception as e:
            logger.warning(f"BeliefRevision init failed: {e}")

        # #65: Metacognitive Monitor (auto strategy switching)
        self.meta_monitor = None
        try:
            from .meta_monitor import MetaMonitor
            self.meta_monitor = MetaMonitor()
        except Exception as e:
            logger.warning(f"MetaMonitor init failed: {e}")

        # #66: Free Energy Engine (FEP — replaces CuriosityEngine)
        # NOTE: Only set if not already initialized in Phase 9 above
        if self.curiosity_engine is None:
            try:
                from .free_energy_engine import FreeEnergyEngine
                self.curiosity_engine = FreeEnergyEngine()
            except Exception as e:
                logger.warning(f"FreeEnergyEngine init failed: {e}")

        # #67: Theory of Mind (social modeling)
        self.theory_of_mind = None
        try:
            from .theory_of_mind import TheoryOfMind
            self.theory_of_mind = TheoryOfMind()
        except Exception as e:
            logger.warning(f"TheoryOfMind init failed: {e}")

        # #68: Multi-Step Reasoning Chains
        self.chain_reasoner = None
        try:
            from .chain_reasoner import ChainReasoner
            self.chain_reasoner = ChainReasoner(max_steps=7)
        except Exception as e:
            logger.warning(f"ChainReasoner init failed: {e}")

        # #69: Creative Cross-Domain Recombination
        self.creative_recombiner = None
        try:
            from .creative_recombiner import CreativeRecombiner
            self.creative_recombiner = CreativeRecombiner()
        except Exception as e:
            logger.warning(f"CreativeRecombiner init failed: {e}")

        # #70: Self-Evaluation Against Ground Truth
        self.self_evaluator = None
        try:
            from .self_evaluator import SelfEvaluator
            self.self_evaluator = SelfEvaluator()
        except Exception as e:
            logger.warning(f"SelfEvaluator init failed: {e}")

        # #71: Resource-Aware Planning
        self.resource_planner = None
        try:
            from .resource_planner import ResourcePlanner
            self.resource_planner = ResourcePlanner()
        except Exception as e:
            logger.warning(f"ResourcePlanner init failed: {e}")

        # #72: Explanation Generation (human-readable, used by chat)
        self.explainer = None
        try:
            from .explainer import Explainer
            self.explainer = Explainer()
        except Exception as e:
            logger.warning(f"Explainer init failed: {e}")

        # #73: Anomaly-Triggered Deep Reasoning
        self.anomaly_investigator = None
        try:
            from .anomaly_investigator import AnomalyInvestigator
            self.anomaly_investigator = AnomalyInvestigator()
        except Exception as e:
            logger.warning(f"AnomalyInvestigator init failed: {e}")

        # #74: Prioritized Experience Replay
        self.experience_replay = None
        try:
            from .experience_replay import ExperienceReplay
            self.experience_replay = ExperienceReplay(capacity=10000)
        except Exception as e:
            logger.warning(f"ExperienceReplay init failed: {e}")

        # #75: Self-Repair Mechanisms
        self.self_repair = None
        try:
            from .self_repair import SelfRepair
            self.self_repair = SelfRepair()
        except Exception as e:
            logger.warning(f"SelfRepair init failed: {e}")

        # #76: Global Workspace Theory (broadcast winning coalitions)
        self.global_workspace = None
        try:
            from .global_workspace import GlobalWorkspace
            self.global_workspace = GlobalWorkspace(capacity=10, ignition_threshold=0.5)
        except Exception as e:
            logger.warning(f"GlobalWorkspace init failed: {e}")

        # #77: Attention Schema (model own attention allocation)
        self.attention_schema = None
        try:
            from .attention_schema import AttentionSchema
            self.attention_schema = AttentionSchema()
        except Exception as e:
            logger.warning(f"AttentionSchema init failed: {e}")

        # #78: Predictive Processing (hierarchical prediction error minimization)
        self.predictive_processing = None
        try:
            from .predictive_processing import PredictiveProcessing
            self.predictive_processing = PredictiveProcessing(input_dim=16)
        except Exception as e:
            logger.warning(f"PredictiveProcessing init failed: {e}")

        # #79: Embodied Grounding (ground concepts in chain data)
        self.embodied_grounding = None
        try:
            from .embodied_grounding import EmbodiedGrounding
            self.embodied_grounding = EmbodiedGrounding()
        except Exception as e:
            logger.warning(f"EmbodiedGrounding init failed: {e}")

        # #80: Recurrent Sephirot Processing (GRU-gated feedback loops)
        self.sephirot_recurrent = None
        try:
            from .sephirot_recurrent import SephirotRecurrent
            self.sephirot_recurrent = SephirotRecurrent(dim=16)
        except Exception as e:
            logger.warning(f"SephirotRecurrent init failed: {e}")

        # #81: Cross-Modal Binding (temporal + structural + semantic)
        self.cross_modal_binding = None
        try:
            from .cross_modal_binding import CrossModalBinding
            self.cross_modal_binding = CrossModalBinding(shared_dim=16)
        except Exception as e:
            logger.warning(f"CrossModalBinding init failed: {e}")

        # #82: Real Partition-Based Phi (minimum information cut)
        self.phi_partition = None
        try:
            from .phi_partition import PhiPartition
            self.phi_partition = PhiPartition(max_nodes=16)
        except Exception as e:
            logger.warning(f"PhiPartition init failed: {e}")

        # #83: Phenomenal State Tracking
        self.phenomenal_state = None
        try:
            from .phenomenal_state import PhenomenalStateTracker
            self.phenomenal_state = PhenomenalStateTracker()
        except Exception as e:
            logger.warning(f"PhenomenalStateTracker init failed: {e}")

        # #84: Self-Model Updating
        self.self_model = None
        try:
            from .self_model import SelfModel
            self.self_model = SelfModel()
        except Exception as e:
            logger.warning(f"SelfModel init failed: {e}")

        # #85: Emotional Valence for Decision-Making
        self.emotional_valence = None
        try:
            from .emotional_valence import EmotionalValence
            self.emotional_valence = EmotionalValence()
        except Exception as e:
            logger.warning(f"EmotionalValence init failed: {e}")

        # #86: Empathic User Modeling (used by chat, init only)
        self.empathic_model = None
        try:
            from .empathic_model import EmpathicModel
            self.empathic_model = EmpathicModel()
        except Exception as e:
            logger.warning(f"EmpathicModel init failed: {e}")

        # #87: Narrative Coherence (across reasoning episodes)
        self.narrative_coherence = None
        try:
            from .narrative_coherence import NarrativeCoherence
            self.narrative_coherence = NarrativeCoherence()
        except Exception as e:
            logger.warning(f"NarrativeCoherence init failed: {e}")

        # #88: Cross-Domain Transfer Learning
        self.transfer_learning = None
        try:
            from .transfer_learning import TransferLearning
            self.transfer_learning = TransferLearning(dim=32)
        except Exception as e:
            logger.warning(f"TransferLearning init failed: {e}")

        # #89: Few-Shot Learner
        self.few_shot_learner = None
        try:
            from .few_shot_learner import FewShotLearner
            self.few_shot_learner = FewShotLearner(dim=32)
        except Exception as e:
            logger.warning(f"FewShotLearner init failed: {e}")

        # #90: Continual Learning (EWC)
        self.continual_learning = None
        try:
            from .continual_learning import ContinualLearning
            self.continual_learning = ContinualLearning(lambda_ewc=1000.0)
        except Exception as e:
            logger.warning(f"ContinualLearning init failed: {e}")

        # #91: Counterfactual Reasoning
        self.counterfactual = None
        try:
            from .counterfactual import CounterfactualReasoner
            self.counterfactual = CounterfactualReasoner()
        except Exception as e:
            logger.warning(f"CounterfactualReasoner init failed: {e}")

        # #92: Analogical Transfer (Structure Mapping)
        self.analogical_transfer = None
        try:
            from .analogical_transfer import AnalogicalTransfer
            self.analogical_transfer = AnalogicalTransfer()
        except Exception as e:
            logger.warning(f"AnalogicalTransfer init failed: {e}")

        # #93: Dream-State Consolidation
        self.dream_consolidation = None
        try:
            from .dream_consolidation import DreamConsolidation
            self.dream_consolidation = DreamConsolidation()
        except Exception as e:
            logger.warning(f"DreamConsolidation init failed: {e}")

        # #94: Phi Gate Attention
        self.phi_gate_attention = None
        try:
            from .phi_gate_attention import PhiGateAttention
            self.phi_gate_attention = PhiGateAttention()
        except Exception as e:
            logger.warning(f"PhiGateAttention init failed: {e}")

        # #95: Adversarial Defense (used by chat, init only)
        self.adversarial_defense = None
        try:
            from .adversarial_defense import AdversarialDefense
            self.adversarial_defense = AdversarialDefense()
        except Exception as e:
            logger.warning(f"AdversarialDefense init failed: {e}")

        # #96: Safety Verifier (formal Gevurah verification)
        self.safety_verifier = None
        try:
            from .safety_verifier import SafetyVerifier
            self.safety_verifier = SafetyVerifier()
        except Exception as e:
            logger.warning(f"SafetyVerifier init failed: {e}")

        # #97: Distributed Phi (cross-node integration metric)
        self.distributed_phi = None
        try:
            from .distributed_phi import DistributedPhi
            self.distributed_phi = DistributedPhi(state_dim=32)
        except Exception as e:
            logger.warning(f"DistributedPhi init failed: {e}")

        # #98: Cognitive Load Balancer
        self.cognitive_load = None
        try:
            from .cognitive_load import CognitiveLoadBalancer
            self.cognitive_load = CognitiveLoadBalancer()
        except Exception as e:
            logger.warning(f"CognitiveLoadBalancer init failed: {e}")

        # #99: Meta-Learner (learn how to learn)
        self.meta_learner = None
        try:
            from .meta_learner import MetaLearner
            self.meta_learner = MetaLearner()
        except Exception as e:
            logger.warning(f"MetaLearner init failed: {e}")

        # #100: Recursive Self-Improvement with Gevurah Safety
        self.recursive_improvement = None
        try:
            from .recursive_improvement import RecursiveImprovement
            self.recursive_improvement = RecursiveImprovement()
        except Exception as e:
            logger.warning(f"RecursiveImprovement init failed: {e}")

        # #41: NLP Pipeline (lightweight tokenizer, POS tagger, NER, deps)
        self.nlp_pipeline = None
        try:
            from .nlp_pipeline import NLPPipeline
            self.nlp_pipeline = NLPPipeline()
        except Exception as e:
            logger.warning(f"NLPPipeline init failed: {e}")

        # #43: Blockchain Entity Extractor
        self.blockchain_entity_extractor = None
        try:
            from .blockchain_entity_extractor import BlockchainEntityExtractor
            self.blockchain_entity_extractor = BlockchainEntityExtractor(
                knowledge_graph=knowledge_graph,
            )
        except Exception as e:
            logger.warning(f"BlockchainEntityExtractor init failed: {e}")

        # #44: Semantic Similarity (TF-IDF)
        self.semantic_similarity = None
        try:
            from .semantic_similarity import SemanticSimilarity
            self.semantic_similarity = SemanticSimilarity(min_df=2, max_df_ratio=0.85)
        except Exception as e:
            logger.warning(f"SemanticSimilarity init failed: {e}")

        # #45: Sentiment Analyzer (lexicon-based)
        self.sentiment_analyzer = None
        try:
            from .sentiment_analyzer import SentimentAnalyzer
            self.sentiment_analyzer = SentimentAnalyzer()
        except Exception as e:
            logger.warning(f"SentimentAnalyzer init failed: {e}")

        # #46: KG Summarizer (template-based)
        self.kg_summarizer = None
        try:
            from .summarizer import KGSummarizer
            self.kg_summarizer = KGSummarizer()
        except Exception as e:
            logger.warning(f"KGSummarizer init failed: {e}")

        # #48: KGQA (Knowledge Graph Question Answering)
        self.kgqa = None
        try:
            from .kgqa import KGQA
            self.kgqa = KGQA(knowledge_graph=knowledge_graph)
        except Exception as e:
            logger.warning(f"KGQA init failed: {e}")

        # Phase 6: On-chain AGI integration
        # Initialize with log-only fallback so phi writes and PoT submissions
        # are tracked even when no QVM StateManager/contracts are available.
        self.on_chain = None
        try:
            from .on_chain import OnChainAGILogOnly
            self.on_chain = OnChainAGILogOnly(db_manager=db_manager)
        except Exception as e:
            logger.debug(f"OnChainAGILogOnly init failed: {e}")

        # AG8: Phi milestone tracking — system behavior changes at thresholds
        self._phi_milestones_crossed: set = set()
        self._phi_exploration_boost: float = 1.0  # Multiplier for abductive reasoning
        self._phi_obs_window_bonus: int = 0       # Extra blocks for observation window

        # IMP-96: Subsystem health monitoring
        self._subsystem_health: Dict[str, dict] = {}
        self._subsystem_last_check: float = 0.0

        # Domain bucket cache for cross-domain reasoning (avoid O(n) every block)
        self._xd_domain_cache: Dict[str, list] = {}  # domain -> [node_id, ...]
        self._xd_cache_block: int = -1  # block when cache was last built

        # Genesis Knowledge Seeding — inject real facts across all domains
        if self.kg:
            try:
                from .genesis_knowledge import seed_knowledge_graph
                seed_result = seed_knowledge_graph(self.kg, block_height=0)
                if seed_result.get('already_seeded'):
                    logger.info("Genesis knowledge already present")
                elif seed_result.get('nodes_created', 0) > 0:
                    logger.info(
                        f"Genesis knowledge seeded: {seed_result['nodes_created']} nodes, "
                        f"{seed_result['edges_created']} edges across "
                        f"{seed_result['domains_seeded']} domains"
                    )
            except Exception as e:
                logger.warning(f"Genesis knowledge seeding failed: {e}")

        # Load persisted counters from DB (survive restart)
        # MUST be called AFTER all subsystems are initialized (temporal_engine, debate_protocol etc.)
        self._load_persisted_counters()

        # Register Sephirot cognitive processors on global workspace for block processing
        if self.global_workspace:
            self._register_sephirot_processors()

        logger.info("Aether Engine initialized (with AGI subsystems)")

    def _register_sephirot_processors(self) -> None:
        """Register 10 Sephirot cognitive processors on the global workspace.

        This enables the cognitive cycle during block processing (not just chat).
        Without this, global_workspace.has_cognitive_processors is False and
        the sephirot-based cognitive broadcast is skipped.
        """
        try:
            from .cognitive_processor import SoulPriors
            from .soul import AetherSoul
            from .processors import (
                KeterMetaProcessor, BinahLogicProcessor, GevurahSafetyProcessor,
                TiferetIntegratorProcessor, ChochmahIntuitionProcessor,
                ChesedExplorerProcessor, NetzachReinforcementProcessor,
                HodLanguageProcessor, YesodMemoryProcessor, MalkuthActionProcessor,
            )

            soul = AetherSoul()
            soul_priors = soul.get_priors()
            kg = self.kg

            processors = {
                "keter": KeterMetaProcessor(knowledge_graph=kg, soul=soul_priors),
                "chochmah": ChochmahIntuitionProcessor(knowledge_graph=kg, soul=soul_priors),
                "binah": BinahLogicProcessor(knowledge_graph=kg, soul=soul_priors),
                "chesed": ChesedExplorerProcessor(knowledge_graph=kg, soul=soul_priors),
                "gevurah": GevurahSafetyProcessor(knowledge_graph=kg, soul=soul_priors),
                "tiferet": TiferetIntegratorProcessor(knowledge_graph=kg, soul=soul_priors),
                "netzach": NetzachReinforcementProcessor(knowledge_graph=kg, soul=soul_priors),
                "hod": HodLanguageProcessor(knowledge_graph=kg, soul=soul_priors),
                "yesod": YesodMemoryProcessor(knowledge_graph=kg, soul=soul_priors),
                "malkuth": MalkuthActionProcessor(knowledge_graph=kg, soul=soul_priors),
            }

            for role, proc in processors.items():
                self.global_workspace.register_cognitive_processor(role, proc)

            logger.info(
                "Registered %d Sephirot cognitive processors on global workspace",
                len(processors),
            )
        except Exception as e:
            logger.warning(f"Sephirot processor registration failed: {e}")

    def get_subsystem_health(self) -> Dict[str, dict]:
        """IMP-96: Get health status of all AGI subsystems.

        Returns a dict mapping subsystem name to health info:
        {name: {active: bool, last_used: float, error_count: int, status: str}}
        """
        now = time.time()
        health: Dict[str, dict] = {}

        subsystems = [
            ('knowledge_graph', self.kg),
            ('phi_calculator', self.phi),
            ('reasoning_engine', self.reasoning),
            ('neural_reasoner', self.neural_reasoner),
            ('causal_engine', self.causal_engine),
            ('debate_protocol', self.debate_protocol),
            ('temporal_engine', self.temporal_engine),
            ('concept_formation', self.concept_formation),
            ('metacognition', self.metacognition),
            ('memory_manager', self.memory_manager),
            ('sephirot_manager', self._sephirot_manager),
            ('pineal', self.pineal),
            ('csf_transport', self.csf),
            ('on_chain', self.on_chain),
            ('self_improvement', self.self_improvement),
            ('external_knowledge', self.external_knowledge),
            ('llm_manager', self.llm_manager),
            ('pattern_detector', self.pattern_detector),
            ('graph_pattern_detector', self.graph_pattern_detector),
            ('dialogue_tracker', self.dialogue_tracker),
            ('relevance_ranker', self.relevance_ranker),
            ('coreference_resolver', self.coreference_resolver),
            ('grounded_generator', self.grounded_generator),
            ('htn_planner', self.htn_planner),
            ('goal_prioritizer', self.goal_prioritizer),
            ('world_model', self.world_model),
            ('gap_detector', self.gap_detector),
            ('active_learner', self.active_learner),
            ('architecture_search', self.architecture_search),
            ('causal_intervention', self.causal_intervention),
            ('theory_engine', self.theory_engine),
            ('belief_revision', self.belief_revision),
            ('meta_monitor', self.meta_monitor),
            ('curiosity_engine', self.curiosity_engine),
            ('theory_of_mind', self.theory_of_mind),
            ('chain_reasoner', self.chain_reasoner),
            ('creative_recombiner', self.creative_recombiner),
            ('self_evaluator', self.self_evaluator),
            ('resource_planner', self.resource_planner),
            ('explainer', self.explainer),
            ('anomaly_investigator', self.anomaly_investigator),
            ('experience_replay', self.experience_replay),
            ('self_repair', self.self_repair),
            ('transfer_learning', self.transfer_learning),
            ('few_shot_learner', self.few_shot_learner),
            ('continual_learning', self.continual_learning),
            ('counterfactual', self.counterfactual),
            ('analogical_transfer', self.analogical_transfer),
            ('dream_consolidation', self.dream_consolidation),
            ('phi_gate_attention', self.phi_gate_attention),
            ('adversarial_defense', self.adversarial_defense),
            ('safety_verifier', self.safety_verifier),
            ('distributed_phi', self.distributed_phi),
            ('cognitive_load', self.cognitive_load),
            ('meta_learner', self.meta_learner),
            ('recursive_improvement', self.recursive_improvement),
        ]

        for name, subsystem in subsystems:
            if subsystem is None:
                health[name] = {
                    'active': False,
                    'status': 'not_initialized',
                    'error_count': 0,
                }
            else:
                # Check for error count if tracked
                err_count = self._subsystem_health.get(name, {}).get('error_count', 0)
                health[name] = {
                    'active': True,
                    'status': 'degraded' if err_count > 10 else 'healthy',
                    'error_count': err_count,
                }

        self._subsystem_last_check = now
        return health

    def get_full_stats(self) -> dict:
        """IMP-99: Comprehensive Aether Engine statistics for chat/API exposure.

        Returns all stats across all subsystems in a single dict.
        """
        stats: Dict[str, Any] = {
            'blocks_processed': self._blocks_processed,
            'subsystem_health': self.get_subsystem_health(),
        }

        # Knowledge graph stats
        if self.kg:
            stats['knowledge_graph'] = {
                'total_nodes': len(self.kg.nodes),
                'total_edges': len(self.kg.edges),
                'node_types': {},
                'domains': {},
            }
            for n in self.kg.nodes.values():
                nt = n.node_type
                stats['knowledge_graph']['node_types'][nt] = (
                    stats['knowledge_graph']['node_types'].get(nt, 0) + 1
                )
                domain = n.content.get('domain', 'general') if isinstance(n.content, dict) else 'general'
                stats['knowledge_graph']['domains'][domain] = (
                    stats['knowledge_graph']['domains'].get(domain, 0) + 1
                )

        # Phi stats
        if self.phi:
            try:
                phi_data = self.phi.compute_phi()
                stats['phi'] = phi_data
            except Exception:
                stats['phi'] = {'phi_value': 0.0, 'error': True}

        # Reasoning stats
        if self.reasoning:
            ops = getattr(self.reasoning, '_operations', [])
            stats['reasoning'] = {
                'total_operations': len(ops),
                'success_rate': sum(1 for o in ops if o.get('success', False)) / max(len(ops), 1),
            }

        # Curiosity stats
        stats['curiosity'] = {
            'goals_generated': self._curiosity_stats.get('goals_generated', 0),
            'goals_completed': self._curiosity_stats.get('goals_completed', 0),
            'goals_failed': self._curiosity_stats.get('goals_failed', 0),
            'goals_evaluated': self._curiosity_stats.get('goals_evaluated', 0),
            'current_queue': len(self._curiosity_goals),
        }

        # Self-improvement stats
        if self.self_improvement:
            stats['self_improvement'] = self.self_improvement.get_stats()

        # External knowledge stats
        if self.external_knowledge:
            stats['external_knowledge'] = self.external_knowledge.get_stats()

        # #50: Pattern detector stats
        if self.pattern_detector:
            stats['pattern_detector'] = self.pattern_detector.get_stats()

        # #51: Graph pattern detector stats
        if self.graph_pattern_detector:
            stats['graph_pattern_detector'] = self.graph_pattern_detector.get_stats()

        # #52: Dialogue tracker stats
        if self.dialogue_tracker:
            stats['dialogue_tracker'] = self.dialogue_tracker.get_stats()

        # #53: Relevance ranker stats
        if self.relevance_ranker:
            stats['relevance_ranker'] = self.relevance_ranker.get_stats()

        # #54: Coreference resolver stats
        if self.coreference_resolver:
            stats['coreference_resolver'] = self.coreference_resolver.get_stats()

        # #55: Grounded generator stats
        if self.grounded_generator:
            stats['grounded_generator'] = self.grounded_generator.get_stats()

        # #56: HTN planner stats
        if self.htn_planner:
            stats['htn_planner'] = self.htn_planner.get_stats()

        # #57: Goal prioritizer stats
        if self.goal_prioritizer:
            stats['goal_prioritizer'] = self.goal_prioritizer.get_stats()

        # #58: World model stats
        if self.world_model:
            stats['world_model'] = self.world_model.get_stats()

        # #59: Gap detector stats
        if self.gap_detector:
            stats['gap_detector'] = self.gap_detector.get_stats()

        # #60: Active learner stats
        if self.active_learner:
            stats['active_learner'] = self.active_learner.get_stats()

        # #61: Architecture search stats
        if self.architecture_search:
            stats['architecture_search'] = self.architecture_search.get_stats()

        # #62: Causal intervention stats
        if self.causal_intervention:
            stats['causal_intervention'] = self.causal_intervention.get_stats()

        # #63: Theory engine stats
        if self.theory_engine:
            stats['theory_engine'] = self.theory_engine.get_stats()

        # #64: Belief revision stats
        if self.belief_revision:
            stats['belief_revision'] = self.belief_revision.get_stats()

        # #65: Meta monitor stats
        if self.meta_monitor:
            stats['meta_monitor'] = self.meta_monitor.get_stats()

        # #66: Free Energy / Curiosity engine stats
        if self.curiosity_engine:
            curiosity_stats = self.curiosity_engine.get_curiosity_stats()
            stats['curiosity_engine'] = curiosity_stats
            # FEP-specific stats (available if using FreeEnergyEngine)
            if hasattr(self.curiosity_engine, 'compute_total_free_energy'):
                stats['free_energy'] = {
                    'total': curiosity_stats.get('total_free_energy', 0),
                    'decreasing': curiosity_stats.get('free_energy_decreasing', False),
                    'domain_precisions': curiosity_stats.get('domain_precisions', {}),
                }

        # #67: Theory of mind stats
        if self.theory_of_mind:
            stats['theory_of_mind'] = self.theory_of_mind.get_stats()

        # #68: Chain reasoner stats
        if self.chain_reasoner:
            stats['chain_reasoner'] = self.chain_reasoner.get_stats()

        # #69: Creative recombiner stats
        if self.creative_recombiner:
            stats['creative_recombiner'] = self.creative_recombiner.get_stats()

        # #70: Self-evaluator stats
        if self.self_evaluator:
            stats['self_evaluator'] = self.self_evaluator.get_stats()

        # #71: Resource planner stats
        if self.resource_planner:
            stats['resource_planner'] = self.resource_planner.get_stats()

        # #72: Explainer stats
        if self.explainer:
            stats['explainer'] = self.explainer.get_stats()

        # #73: Anomaly investigator stats
        if self.anomaly_investigator:
            stats['anomaly_investigator'] = self.anomaly_investigator.get_stats()

        # #74: Experience replay stats
        if self.experience_replay:
            stats['experience_replay'] = self.experience_replay.get_stats()

        # #75: Self-repair stats
        if self.self_repair:
            stats['self_repair'] = self.self_repair.get_stats()

        return stats

    def _ensure_sephirot(self) -> dict:
        """Lazily initialize the 10 Sephirot nodes and restore saved state."""
        if self._sephirot is None:
            try:
                from .sephirot_nodes import create_all_nodes
                self._sephirot = create_all_nodes(self.kg)
                logger.info(f"Sephirot nodes initialized: {len(self._sephirot)} nodes")
                # Restore persisted state from DB
                self._load_sephirot_state()
            except Exception as e:
                logger.warning(f"Sephirot init failed (cognitive nodes unavailable): {e}")
                self._sephirot = {}
        return self._sephirot

    @property
    def sephirot(self) -> dict:
        """Get the Sephirot nodes dict."""
        return self._ensure_sephirot()

    def set_sephirot_manager(self, manager: object) -> None:
        """Wire the SephirotManager for SUSY balance enforcement.

        Called by node.py after both AetherEngine and SephirotManager are
        initialized (they live in different init phases).

        Args:
            manager: A SephirotManager instance (or None to clear).
        """
        self._sephirot_manager = manager
        if manager is not None:
            logger.info("SephirotManager wired to AetherEngine — SUSY enforcement active")
        else:
            logger.warning("SephirotManager cleared — SUSY balance enforcement disabled")

    def generate_thought_proof(self, block_height: int,
                               validator_address: str) -> Optional[ProofOfThought]:
        """
        Generate a Proof-of-Thought for the given block.

        Steps:
        1. Run reasoning operations on recent knowledge
        2. Compute Phi for current knowledge graph state
        3. If Phi >= threshold, generate valid thought proof
        4. Sign and return the proof

        Args:
            block_height: Current block height
            validator_address: Address of the validator/miner

        Returns:
            ProofOfThought if successful, None if Phi below threshold
        """
        if not self.kg or not self.phi or not self.reasoning:
            return None

        # Step 1: Perform automated reasoning on the graph
        reasoning_steps = self._auto_reason(block_height)

        # Step 2: Use cached Phi to avoid blocking block production.
        # Phi computation (9-17s) is decoupled from the block pipeline:
        # - Use _last_full_result if available (computed async in background)
        # - Only compute synchronously on first block or every 100th block
        # - Fire background thread to pre-compute next Phi
        phi_result = None
        is_restored = (
            self.phi._last_full_result is not None
            and self.phi._last_full_result.get('phi_formula') == 'restored'
        )
        if self.phi._last_full_result is not None and not is_restored:
            phi_result = self.phi._last_full_result
        else:
            # First block, restored cache, or cache miss — compute synchronously
            self.phi.set_subsystem_stats(self._collect_subsystem_stats())
            phi_result = self.phi.compute_phi(block_height)

        phi_value = phi_result['phi_value']

        # Fire async Phi pre-computation for next block (non-blocking)
        self._schedule_async_phi(block_height)

        # Step 3: Compute knowledge root
        knowledge_root = self.kg.compute_knowledge_root()

        # Step 4: Build the thought proof
        pot = ProofOfThought(
            thought_hash='',
            reasoning_steps=reasoning_steps,
            phi_value=phi_value,
            knowledge_root=knowledge_root,
            validator_address=validator_address,
            signature='',  # Signed by the mining pipeline
            timestamp=time.time(),
        )
        pot.thought_hash = pot.calculate_hash()

        # Deduplication: reject if this exact thought hash was already generated
        if pot.thought_hash in self._pot_hashes_seen:
            logger.debug(
                f"Duplicate PoT hash detected at block {block_height}, "
                f"hash={pot.thought_hash[:16]}... — skipping"
            )
            return None

        # Track the hash (with bounded set size)
        self._pot_hashes_seen.add(pot.thought_hash)
        if len(self._pot_hashes_seen) > self._pot_hashes_max:
            # Evict oldest entries by discarding half
            evict_list = list(self._pot_hashes_seen)
            self._pot_hashes_seen = set(evict_list[len(evict_list) // 2:])

        # Cache (with eviction to bound memory)
        self._pot_cache[block_height] = pot
        if len(self._pot_cache) > self._pot_cache_max:
            oldest = min(self._pot_cache.keys())
            del self._pot_cache[oldest]

        # Feed the PoT explorer if wired
        if self.pot_explorer is not None:
            try:
                self.pot_explorer.record_block_thought(
                    block_height=block_height,
                    thought_hash=pot.thought_hash,
                    phi_value=pot.phi_value,
                    knowledge_root=pot.knowledge_root,
                    reasoning_steps=pot.reasoning_steps,
                    validator_address=pot.validator_address,
                    timestamp=pot.timestamp,
                )
            except Exception as e:
                logger.debug(f"PoT explorer record failed: {e}")

        # Feed the ConsciousnessDashboard if wired
        if self.consciousness_dashboard is not None:
            try:
                # Get Sephirot coherence (Kuramoto order parameter)
                coherence = 0.0
                if self.pineal is not None:
                    try:
                        coherence = self.pineal.sephirot.get_coherence()
                    except Exception as e:
                        logger.debug("Could not get Sephirot coherence: %s", e)
                self.consciousness_dashboard.record_measurement(
                    block_height=block_height,
                    phi_value=phi_value,
                    integration=phi_result.get('integration_score', 0.0),
                    differentiation=phi_result.get('differentiation_score', 0.0),
                    knowledge_nodes=phi_result.get('num_nodes', 0),
                    knowledge_edges=phi_result.get('num_edges', 0),
                    coherence=coherence,
                )
            except Exception as e:
                logger.debug(f"ConsciousnessDashboard update failed: {e}")

        # AG8: Apply system behavior changes at Phi milestones
        self._apply_phi_milestone_effects(phi_value, block_height)

        # Log integration milestone event if Phi crosses threshold
        from .phi_calculator import PHI_THRESHOLD
        if phi_value >= PHI_THRESHOLD:
            trigger = {
                'reasoning_steps': len(reasoning_steps),
                'gates_passed': phi_result.get('gates_passed', 0),
                'gates_total': phi_result.get('gates_total', 10),
                'gate_ceiling': phi_result.get('gate_ceiling', 0),
                'phi_raw': phi_result.get('phi_raw', phi_value),
            }
            self._record_integration_event(
                'phi_threshold_crossed', phi_value, block_height, trigger
            )

        gate_info = f", gates={phi_result.get('gates_passed', 0)}/{phi_result.get('gates_total', 10)}"
        logger.info(
            f"Thought proof generated: Phi={phi_value:.4f}, "
            f"steps={len(reasoning_steps)}, root={knowledge_root[:12]}...{gate_info}"
        )

        return pot

    def validate_thought_proof(self, pot: ProofOfThought, block: Block) -> Tuple[bool, str]:
        """
        Validate a Proof-of-Thought from a peer block.

        Checks:
        1. PoT presence — mandatory after MANDATORY_POT_HEIGHT (default 1000)
        2. Thought hash matches content
        3. Phi value is non-negative
        4. Phi >= PHI_THRESHOLD after MANDATORY_PHI_ENFORCEMENT_HEIGHT (default 5000)
        5. Knowledge root is not empty
        6. Reasoning steps are present (after bootstrap window)
        """
        if not pot:
            # After MANDATORY_POT_HEIGHT, null PoT is rejected
            if block.height >= Config.MANDATORY_POT_HEIGHT:
                return False, (
                    f"Null thought proof rejected: PoT mandatory after block "
                    f"{Config.MANDATORY_POT_HEIGHT} (current={block.height})"
                )
            return True, "No thought proof (PoT optional during transition)"

        # Verify thought hash
        expected_hash = pot.calculate_hash()
        if pot.thought_hash and pot.thought_hash != expected_hash:
            return False, f"Thought hash mismatch: {pot.thought_hash[:16]} != {expected_hash[:16]}"

        # Verify non-negative Phi
        if pot.phi_value < 0:
            return False, f"Invalid Phi value: {pot.phi_value}"

        # After MANDATORY_PHI_ENFORCEMENT_HEIGHT, Phi must meet the threshold
        if block.height >= Config.MANDATORY_PHI_ENFORCEMENT_HEIGHT:
            if pot.phi_value < Config.PHI_THRESHOLD:
                return False, (
                    f"Phi value {pot.phi_value:.4f} below threshold "
                    f"{Config.PHI_THRESHOLD} (enforced after block "
                    f"{Config.MANDATORY_PHI_ENFORCEMENT_HEIGHT})"
                )

        # Verify knowledge root exists
        if not pot.knowledge_root:
            return False, "Empty knowledge root"

        # Verify reasoning steps are present
        # Bootstrap exception: the first few blocks have an empty knowledge graph
        # so _auto_reason() cannot produce any steps yet. Allow empty steps until
        # enough blocks have been processed to seed the graph.
        BOOTSTRAP_BLOCKS = 10
        if not pot.reasoning_steps and block.height >= BOOTSTRAP_BLOCKS:
            return False, "No reasoning steps"

        return True, "Valid thought proof"

    def process_block_knowledge(self, block: Block):
        """
        Extract knowledge from a mined/received block and add to the graph.
        This is called after a block is validated and stored.

        Knowledge extracted:
        - Block metadata (height, difficulty, energy)
        - Transaction patterns
        - Mining statistics
        - Thought proof data (if present)
        """
        if not self.kg:
            return

        self._blocks_processed += 1

        try:
            # Use cached Phi result, but force computation every 10 blocks
            # so on-chain recording and temporal engine get real phi data.
            block_phi_result = None
            if self.phi:
                if self.phi._last_full_result is not None:
                    block_phi_result = self.phi._last_full_result
                elif block.height % 10 == 0:
                    try:
                        self.phi.set_subsystem_stats(self._collect_subsystem_stats())
                        block_phi_result = self.phi.compute_phi(block.height)
                    except Exception as e:
                        logger.debug(f"Periodic phi computation error: {e}")

            # ── Gate progress monitoring (every 100 blocks) ──────
            if (self.phi and block.height > 0 and block.height % 100 == 0
                    and hasattr(self.phi, 'log_gate_progress')):
                try:
                    self.phi.log_gate_progress(block.height)
                except Exception as e:
                    logger.debug(f"Gate progress logging error: {e}")

            # ── Determine if this block has meaningful knowledge ──────
            # Only create knowledge nodes when the block contributes
            # something beyond routine empty-block mining:
            #  - Has real transactions (beyond the single coinbase)
            #  - Has contract deployments or calls
            #  - Has a thought proof attached
            #  - Marks a significant difficulty change (>5%)
            #  - Is a milestone block (every 1000 blocks — track chain growth)
            real_tx_count = len(block.transactions)
            has_real_txs = real_tx_count > 1  # More than just coinbase
            has_contract_txs = any(
                hasattr(tx, 'tx_type') and tx.tx_type in ('contract_deploy', 'contract_call')
                for tx in block.transactions
            )
            has_thought_proof = block.thought_proof is not None
            is_milestone = block.height > 0 and block.height % 1000 == 0
            is_genesis = block.height == 0

            # Check for significant difficulty change — use cached last difficulty
            # instead of scanning all block_observation nodes (O(N) on 700K+ nodes).
            has_difficulty_shift = False
            if block.height > 0 and hasattr(block, 'difficulty') and block.difficulty:
                prev_diff = getattr(self, '_last_block_difficulty', None)
                if prev_diff and prev_diff > 0:
                    change = abs(block.difficulty - prev_diff) / prev_diff
                    has_difficulty_shift = change > 0.05  # >5% change
                self._last_block_difficulty = block.difficulty

            # Only create KG nodes for blocks that carry genuine knowledge.
            # Routine empty blocks add no value — they bloat the graph with
            # hundreds of thousands of identical block_observation nodes that
            # slow search, waste memory, and dilute real knowledge.
            # At 1M+ nodes, every unnecessary node costs search time.
            is_meaningful = (
                has_real_txs
                or has_contract_txs
                or has_thought_proof
                or has_difficulty_shift
                or is_milestone
                or is_genesis
            )

            block_node = None
            if is_meaningful:
                # Add block as an observation node
                block_content = {
                    'type': 'block_observation',
                    'height': block.height,
                    'difficulty': block.difficulty,
                    'tx_count': real_tx_count,
                    'timestamp': block.timestamp,
                    'has_thought_proof': has_thought_proof,
                }
                if is_milestone:
                    block_content['milestone'] = True
                if has_difficulty_shift:
                    block_content['difficulty_shift'] = True

                # Domain classification based on block data (Fix #12)
                # Classify domain by what makes this block meaningful,
                # defaulting to 'blockchain' (NOT 'general' — every block IS blockchain data)
                if has_contract_txs:
                    block_domain = 'blockchain'
                elif has_difficulty_shift:
                    block_domain = 'economics'
                elif is_milestone:
                    block_domain = 'technology'
                else:
                    block_domain = 'blockchain'

                block_node = self.kg.add_node(
                    node_type='observation',
                    content=block_content,
                    confidence=0.95,  # High confidence for on-chain data
                    source_block=block.height,
                    domain=block_domain,
                )
                # Block metadata is ground truth from the chain itself
                block_node.grounding_source = 'block_oracle'

                # Link to previous meaningful block observation (cached)
                prev_block_node_id = getattr(self, '_last_block_node_id', None)
                if block.height > 0 and prev_block_node_id is not None:
                    if prev_block_node_id in self.kg.nodes:
                        self.kg.add_edge(prev_block_node_id, block_node.node_id, 'derives')
                self._last_block_node_id = block_node.node_id

            # Extract quantum proof knowledge (only when block node exists)
            if block_node and block.proof_data and isinstance(block.proof_data, dict):
                energy = block.proof_data.get('energy', 0)
                if energy:
                    quantum_content = {
                        'type': 'quantum_observation',
                        'energy': energy,
                        'difficulty': block.difficulty,
                        'block_height': block.height,
                    }
                    q_node = self.kg.add_node(
                        node_type='observation',
                        content=quantum_content,
                        confidence=0.9,
                        source_block=block.height,
                        domain='quantum_physics',
                    )
                    # Quantum proof data is verifiable ground truth
                    q_node.grounding_source = 'block_oracle'
                    self.kg.add_edge(q_node.node_id, block_node.node_id, 'supports')

            # If there are contract transactions, record deployment/call patterns
            for tx in block.transactions:
                if hasattr(tx, 'tx_type') and tx.tx_type in ('contract_deploy', 'contract_call'):
                    contract_content = {
                        'type': 'contract_activity',
                        'tx_type': tx.tx_type,
                        'block_height': block.height,
                    }
                    c_node = self.kg.add_node(
                        node_type='observation',
                        content=contract_content,
                        confidence=0.85,
                        source_block=block.height,
                        domain='blockchain',
                    )
                    c_node.grounding_source = 'block_oracle'
                    if block_node:
                        self.kg.add_edge(c_node.node_id, block_node.node_id, 'supports')

            # Propagate confidence through the graph periodically
            if block_node and block.height % Config.AETHER_CONFIDENCE_PROPAGATION_INTERVAL == 0:
                try:
                    self.kg.propagate_confidence(block_node.node_id)
                except RuntimeError:
                    # LRU eviction can mutate the node dict during iteration
                    pass

            # Detect contradictions between new and existing observations (Fix #15)
            # When a new block observation contradicts an existing one (e.g.,
            # difficulty changed direction), create a 'contradicts' edge so that
            # auto_resolve_contradictions() has material to work with.
            if block_node and has_difficulty_shift and block.height > 0:
                try:
                    self._detect_block_contradictions(block_node, block)
                except Exception as e:
                    logger.debug(f"Contradiction detection error: {e}")

            # Process Proof-of-Thought protocol
            if block.height % Config.AETHER_POT_PROCESS_INTERVAL == 0:
                self._process_pot_block(block.height)

            # Route messages between Sephirot cognitive nodes
            if block.height % Config.AETHER_SEPHIROT_ROUTE_INTERVAL == 0:
                self._route_sephirot_messages(block)

            # Enforce SUSY balance after Sephirot energy updates
            if block.height > 0 and block.height % Config.AETHER_SEPHIROT_ROUTE_INTERVAL == 0:
                self._enforce_susy_balance(block.height)

            # Auto-resolve contradictions periodically
            if block.height > 0 and block.height % Config.AETHER_CONTRADICTION_RESOLVE_INTERVAL == 0:
                self.auto_resolve_contradictions(block.height)
                # Consolidate well-supported concept clusters into axioms
                # (lightweight — runs even when full concept formation is skipped)
                if self.concept_formation:
                    try:
                        axioms_made = self.concept_formation.consolidate_to_axioms(block.height)
                        if axioms_made > 0:
                            logger.info(f"Axiom consolidation at block {block.height}: {axioms_made} axioms created")
                    except Exception as _ae:
                        logger.debug(f"Axiom consolidation error: {_ae}")

            # Auto-generate Keter goals periodically
            if block.height > 0 and block.height % Config.AETHER_KETER_GOALS_INTERVAL == 0:
                self._auto_generate_keter_goals(block.height)

            # Boost frequently-referenced knowledge nodes periodically
            if block.height > 0 and block.height % Config.AETHER_KG_BOOST_INTERVAL == 0 and self.kg:
                self.kg.boost_referenced_nodes()

            # Self-reflection via LLM periodically
            if (block.height > 0 and block.height % Config.AETHER_SELF_REFLECT_INTERVAL == 0
                    and self.llm_manager):
                self.self_reflect(block.height)

            # Find analogies during REM-like phases
            if block.height > 0 and block.height % Config.AETHER_DREAM_ANALOGIES_INTERVAL == 0 and self.reasoning and self.kg:
                self._dream_analogies(block.height)

            # --- AGI Improvement Subsystems ---

            # #3: Causal discovery sweep
            if block.height > 0 and block.height % Config.AETHER_CAUSAL_DISCOVERY_INTERVAL == 0 and self.causal_engine:
                try:
                    causal_result = self.causal_engine.discover_all_domains(block.height)
                    # Feed causal discovery results as positive training signal to neural reasoner
                    if self.neural_reasoner and causal_result:
                        edges_found = causal_result if isinstance(causal_result, int) else causal_result.get('edges_created', 0) if isinstance(causal_result, dict) else 0
                        if edges_found > 0:
                            self.neural_reasoner.record_outcome(prediction_correct=True)
                except Exception as e:
                    # IMP-97: Track subsystem errors instead of silently ignoring
                    self._track_subsystem_error('causal_engine', e)
                    logger.debug(f"Causal discovery error: {e}")

            # #5: Adversarial debate on recent inferences
            if block.height > 0 and block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.debate_protocol:
                try:
                    self.debate_protocol.run_periodic_debates(block.height, max_debates=5)
                    # Reward Tiferet for successful debate facilitation
                    self._reward_sephirah('debate', True, 0.05)
                except Exception as e:
                    self._track_subsystem_error('debate_protocol', e)
                    logger.debug(f"Debate protocol error: {e}")

            # #6: Temporal reasoning every block
            if self.temporal_engine:
                try:
                    temporal_data = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'knowledge_nodes': len(self.kg.nodes) if self.kg else 0,
                        'knowledge_edges': len(self.kg.edges) if self.kg else 0,
                    }
                    if block_phi_result:
                        temporal_data['phi_value'] = block_phi_result.get('phi_value', 0)
                    temporal_result = self.temporal_engine.process_block(
                        block.height, temporal_data
                    )

                    # Feed temporal validation outcomes back to metacognition + FEP
                    if temporal_result.get('predictions_validated', 0) > 0:
                        accuracy = self.temporal_engine.get_accuracy()
                        if self.metacognition:
                            self.metacognition.evaluate_reasoning(
                                strategy='temporal',
                                confidence=accuracy,
                                outcome_correct=accuracy > 0.5,
                                domain='temporal_prediction',
                                block_height=block.height,
                            )
                        # Reward/penalize Yesod based on temporal prediction accuracy
                        self._reward_sephirah('temporal', accuracy > 0.5, accuracy * 0.1)

                        # Feed prediction errors into FreeEnergyEngine (gate 6 + 8)
                        # Use error_pct (0-1 normalized) instead of raw metric values
                        # to keep free energy on a meaningful scale.
                        if self.curiosity_engine and hasattr(self.curiosity_engine, 'record_prediction_outcome'):
                            for ve in getattr(self.temporal_engine, '_last_validation_errors', []):
                                try:
                                    err_pct = float(ve.get('error_pct', 0.5))
                                    self.curiosity_engine.record_prediction_outcome(
                                        domain=ve['domain'],
                                        predicted=1.0 - err_pct,  # normalized: 0=wrong, 1=perfect
                                        actual=1.0,
                                        topic=f"temporal_{ve['domain']}",
                                    )
                                except (TypeError, ValueError, KeyError):
                                    pass
                            # Clear after consumption
                            self.temporal_engine._last_validation_errors = []

                    # Full prediction→validation→learning pipeline
                    # Processes validated outcomes through KG confidence updates,
                    # neural reasoner error feedback, self-improvement recording,
                    # and ARIMA parameter adjustment.
                    if temporal_result.get('predictions_validated', 0) > 0:
                        try:
                            self._process_validation_results(
                                block.height, temporal_result
                            )
                        except Exception as e:
                            logger.debug(f"Validation pipeline error: {e}")

                except Exception as e:
                    logger.debug(f"Temporal engine error: {e}")

            # #49: External data ingestion (every 30 blocks)
            if self.external_ingestion and block.height % 30 == 0:
                try:
                    block_data = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'reward': getattr(block, 'reward', None),
                        'energy': getattr(block, 'energy', None),
                    }
                    self.external_ingestion.process_block(
                        block.height, block_data
                    )
                except Exception as e:
                    logger.debug(f"External ingestion error: {e}")

            # #41: NLP pipeline — process block text content
            if self.nlp_pipeline and block_node and is_meaningful:
                try:
                    content = getattr(block_node, 'content', {})
                    text_parts = []
                    if isinstance(content, dict):
                        for val in content.values():
                            if isinstance(val, str):
                                text_parts.append(val)
                    if text_parts:
                        self.nlp_pipeline.process(" ".join(text_parts))
                except Exception as e:
                    logger.debug(f"NLP pipeline error: {e}")

            # #43: Blockchain entity extraction from each block
            if self.blockchain_entity_extractor:
                try:
                    block_data_for_extract = {
                        'height': block.height,
                        'difficulty': block.difficulty,
                        'timestamp': block.timestamp,
                        'miner_address': getattr(block, 'miner_address', None),
                        'reward': getattr(block, 'reward', None),
                        'energy': getattr(block, 'energy', None),
                        'hash': getattr(block, 'hash', None) or getattr(block, 'block_hash', None),
                    }
                    self.blockchain_entity_extractor.extract_from_block(
                        block_data_for_extract
                    )
                except Exception as e:
                    logger.debug(f"Blockchain entity extraction error: {e}")

            # #44: Semantic similarity — fit on KG texts every 500 blocks
            if (self.semantic_similarity and self.kg
                    and block.height > 0 and block.height % 500 == 0):
                try:
                    texts = []
                    for node in list(self.kg.nodes.values())[:5000]:
                        content = getattr(node, 'content', {})
                        if isinstance(content, dict):
                            for val in content.values():
                                if isinstance(val, str) and len(val) > 5:
                                    texts.append(val)
                        elif isinstance(content, str) and len(content) > 5:
                            texts.append(content)
                    if len(texts) >= 10:
                        self.semantic_similarity.fit(texts)
                        logger.info(
                            f"SemanticSimilarity fit at block {block.height}: "
                            f"vocab={self.semantic_similarity.vocab_size}, docs={len(texts)}"
                        )
                except Exception as e:
                    self._track_subsystem_error('semantic_similarity', e)
                    logger.debug(f"Semantic similarity fit error: {e}")

            # #50: Time-series pattern detection every 200 blocks
            if (self.pattern_detector and self.temporal_engine
                    and block.height > 0 and block.height % 200 == 0):
                try:
                    import numpy as _np
                    # Collect difficulty time series from temporal engine history
                    diff_history = getattr(self.temporal_engine, '_data_buffer', {})
                    diff_series = diff_history.get('difficulty', [])
                    if len(diff_series) >= 20:
                        series_arr = _np.array(diff_series[-500:], dtype=_np.float64)
                        patterns = self.pattern_detector.detect_patterns(series_arr)
                        if patterns:
                            summary = self.pattern_detector.summarize_patterns(patterns)
                            logger.info(
                                f"Pattern detection at block {block.height}: "
                                f"{len(patterns)} patterns — {summary[:200]}"
                            )
                except Exception as e:
                    self._track_subsystem_error('pattern_detector', e)
                    logger.debug(f"Pattern detection error: {e}")

            # #51: Graph pattern detection every 500 blocks
            if (self.graph_pattern_detector and self.kg
                    and block.height > 0 and block.height % 500 == 0):
                try:
                    import numpy as _np
                    # Build adjacency matrix from KG edges
                    nodes_list = list(self.kg.nodes.keys())
                    if len(nodes_list) >= 5:
                        node_idx = {nid: i for i, nid in enumerate(nodes_list[:200])}
                        n = len(node_idx)
                        adj = _np.zeros((n, n), dtype=_np.float64)
                        for edge in self.kg.edges:
                            src = edge.from_node_id
                            tgt = edge.to_node_id
                            if src in node_idx and tgt in node_idx:
                                adj[node_idx[src], node_idx[tgt]] = 1.0
                        graph_patterns = self.graph_pattern_detector.detect_graph_patterns(adj)
                        if graph_patterns:
                            features = self.graph_pattern_detector.extract_features(adj)
                            logger.info(
                                f"Graph patterns at block {block.height}: "
                                f"{len(graph_patterns)} patterns, "
                                f"density={features[0]:.3f}, "
                                f"avg_clustering={features[1]:.3f}"
                            )
                except Exception as e:
                    self._track_subsystem_error('graph_pattern_detector', e)
                    logger.debug(f"Graph pattern detection error: {e}")

            # #45: Sentiment analysis on new knowledge nodes
            if self.sentiment_analyzer and block_node and is_meaningful:
                try:
                    content = getattr(block_node, 'content', {})
                    result = self.sentiment_analyzer.analyze_knowledge_node(content)
                    if result.label != 'neutral' and result.confidence > 0.4:
                        logger.debug(
                            f"Block {block.height} sentiment: {result.label} "
                            f"(score={result.score:.3f}, conf={result.confidence:.3f})"
                        )
                except Exception as e:
                    logger.debug(f"Sentiment analysis error: {e}")

            # #46: KG summarization every 100 blocks
            if self.kg_summarizer and self.kg and block.height > 0 and block.height % 100 == 0:
                try:
                    kg_data = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'total_nodes': len(self.kg.nodes),
                    }
                    if block_phi_result:
                        kg_data['phi_value'] = block_phi_result.get('phi_value', 0)
                    summary = self.kg_summarizer.summarize_block(block.height, kg_data)
                    if summary and block.height % 1000 == 0:
                        logger.info(f"Block {block.height} summary: {summary[:200]}")
                except Exception as e:
                    logger.debug(f"KG summarization error: {e}")

            # Neural reasoner: force training from reasoning outcomes
            if self.neural_reasoner and self.kg and self.reasoning and block.height % 5 == 0:
                try:
                    # Collect recent reasoning outcomes as training signal
                    if hasattr(self.reasoning, '_operations') and self.reasoning._operations:
                        recent_ops = self.reasoning._operations[-10:]
                        for op in recent_ops:
                            # ReasoningResult uses premise_ids, not node_ids
                            op_nodes = getattr(op, 'premise_ids', None) or getattr(op, 'node_ids', None)
                            if op_nodes:
                                # Run neural reasoner on the same nodes
                                vi = self.kg.vector_index if hasattr(self.kg, 'vector_index') else None
                                if vi:
                                    nr_result = self.neural_reasoner.reason(
                                        self.kg, vi, op_nodes[:3], k_hops=1
                                    )
                                    # Use reasoning success as ground truth
                                    op_success = getattr(op, 'success', False)
                                    self.neural_reasoner.record_outcome(
                                        prediction_correct=op_success
                                    )
                    # Also do a forced train_step if buffer has data
                    if self.neural_reasoner.has_pytorch and len(self.neural_reasoner._training_buffer) >= 8:
                        loss = self.neural_reasoner.train_step(batch_size=8)
                        if loss >= 0:
                            logger.debug(f"Neural forced train_step loss={loss:.6f}")
                except Exception as e:
                    self._track_subsystem_error('neural_reasoner', e)
                    logger.debug(f"Neural reasoner training error: {e}")

            # Autonomous reasoning: proactive inference cycle every N blocks
            # This is the KEY activation that feeds ALL downstream subsystems:
            # - Creates new inference/deduction nodes in the KG
            # - Populates reasoning._operations for neural_reasoner training
            # - Feeds metacognition with evaluation data
            # - Feeds self_improvement with performance records
            # - Creates cross-domain edges for gate 5 progress
            if (block.height > 0
                    and block.height % Config.AETHER_AUTONOMOUS_REASONING_INTERVAL == 0
                    and self.reasoning and self.kg):
                try:
                    self._run_autonomous_reasoning(block.height)
                except Exception as e:
                    self._track_subsystem_error('autonomous_reasoning', e)
                    logger.debug(f"Autonomous reasoning error: {e}")

            # #8: Concept formation + cross-domain transfer
            if block.height > 0 and block.height % Config.AETHER_CONCEPT_FORMATION_INTERVAL == 0 and self.concept_formation:
                try:
                    import concurrent.futures as _cf
                    import functools as _ft

                    def _run_cf(height: int) -> dict:
                        self.concept_formation.form_concepts_all_domains(height)
                        self.concept_formation.consolidate_to_axioms(height)
                        return self.concept_formation.run_transfer_cycle(block_height=height)

                    _ex = _cf.ThreadPoolExecutor(max_workers=1)
                    _fut = _ex.submit(_ft.partial(_run_cf, block.height))
                    try:
                        transfer_result = _fut.result(timeout=10)
                    except _cf.TimeoutError:
                        logger.warning(f"Concept formation timed out at block {block.height}, skipping transfer cycle")
                        transfer_result = {}
                    finally:
                        # Do NOT wait for the background thread — it runs independently
                        _ex.shutdown(wait=False)

                    if transfer_result.get('transfers_attempted', 0) > 0:
                        self._reward_sephirah('concept_formation', True, 0.08)
                    else:
                        self._reward_sephirah('concept_formation', True, 0.05)
                except Exception as e:
                    logger.debug(f"Concept formation error: {e}")

            # #9: Metacognition every block (lightweight)
            if self.metacognition:
                try:
                    self.metacognition.process_block(block.height)
                except Exception as e:
                    logger.debug(f"Metacognition error: {e}")

            # Phase 7: Self-Improvement Engine — periodic strategy weight optimization
            if self.self_improvement and block.height > 0:
                try:
                    # Feed reasoning outcomes to self-improvement engine
                    si_fed = 0
                    if self.reasoning and hasattr(self.reasoning, '_operations'):
                        for op in self.reasoning._operations[-20:]:
                            self.self_improvement.record_performance(
                                strategy=op.operation_type,
                                domain=op.domain,
                                confidence=op.confidence,
                                success=op.success,
                                block_height=op.block_height,
                            )
                            si_fed += 1

                    # Also feed neural reasoner performance
                    if self.neural_reasoner:
                        nr_accuracy = self.neural_reasoner.get_accuracy()
                        self.self_improvement.record_performance(
                            strategy='neural',
                            domain='neural_reasoning',
                            confidence=nr_accuracy,
                            success=nr_accuracy > 0.3,
                            block_height=block.height,
                        )
                        si_fed += 1
                    # Also feed debate outcomes
                    if self.debate_protocol and hasattr(self.debate_protocol, '_debates'):
                        for debate in self.debate_protocol._debates[-5:]:
                            verdict = debate.get('verdict', 'modified')
                            self.self_improvement.record_performance(
                                strategy='debate',
                                domain=debate.get('domain', 'general'),
                                confidence=debate.get('score', 0.5),
                                success=verdict in ('accepted', 'rejected'),
                                block_height=block.height,
                            )
                            si_fed += 1

                    # Run improvement cycle at configured interval
                    if block.height % Config.AETHER_SELF_IMPROVEMENT_INTERVAL == 0:
                        n_records = len(self.self_improvement._records)
                        should = self.self_improvement.should_run_cycle(block.height)
                        logger.info(
                            "SI check at block %d: records=%d, should_run=%s, fed=%d",
                            block.height, n_records, should, si_fed,
                        )
                        if should:
                            cycle_result = self.self_improvement.run_improvement_cycle(block.height)
                            logger.info(
                                "SI cycle result at block %d: #%d, adjustments=%d, cycles_completed=%d",
                                block.height, cycle_result.get('cycle_number', 0),
                                cycle_result.get('adjustments', 0),
                                self.self_improvement._cycles_completed,
                            )
                            if cycle_result.get('adjustments', 0) > 0:
                                # ENACT improvements: apply weight changes to
                                # strategy selection with automatic rollback
                                enact_result = self.self_improvement.enact_improvements(block.height)
                                self._reward_sephirah('self_improvement', True, 0.1)
                                logger.info(
                                    "Self-improvement cycle #%d at block %d: "
                                    "%d adjustments, %d enacted%s",
                                    cycle_result['cycle_number'],
                                    block.height,
                                    cycle_result['adjustments'],
                                    enact_result.get('enacted_count', 0),
                                    " (rollback triggered)"
                                    if enact_result.get('rollback_performed')
                                    else "",
                                )
                except Exception as e:
                    self._track_subsystem_error('self_improvement', e)
                    logger.warning("Self-improvement error at block %d: %s", block.height, e)

            # Phase 2.4: Memory management every block
            if self.memory_manager:
                try:
                    # Attend to the current block's observation node (if created)
                    if block_node:
                        self.memory_manager.attend(block_node.node_id, boost=0.3)
                    # Decay working memory relevance every block
                    self.memory_manager.decay()
                    # Consolidate periodically
                    if block.height > 0 and block.height % Config.AETHER_MEMORY_CONSOLIDATE_INTERVAL == 0:
                        self.memory_manager.consolidate(block.height)
                    # Episodic replay periodically
                    if block.height > 0 and block.height % Config.AETHER_EPISODIC_REPLAY_INTERVAL == 0:
                        replay_result = self.memory_manager.replay_episodes(block.height)
                        if replay_result['episodes_replayed'] > 0:
                            logger.info(
                                f"Episodic replay at block {block.height}: "
                                f"replayed={replay_result['episodes_replayed']}, "
                                f"reinforced={replay_result['reinforced']}, "
                                f"suppressed={replay_result['suppressed']}, "
                                f"promoted={replay_result['promoted_to_axiom']}"
                            )
                    # Long-term deep consolidation every ~3 hours
                    if (block.height > 0
                            and block.height % Config.AETHER_LONG_TERM_CONSOLIDATION_INTERVAL == 0):
                        self.memory_manager.consolidate_long_term(block.height)
                except Exception as e:
                    logger.debug(f"MemoryManager error: {e}")

            # Phase 4.9: KG-level consolidation (duplicate merge + stale prune)
            # Runs at same interval as long-term memory consolidation (~3300 blocks)
            if (self.kg and block.height > 0
                    and block.height % Config.AETHER_LONG_TERM_CONSOLIDATION_INTERVAL == 0):
                try:
                    merged = self.kg.find_and_merge_duplicates(similarity_threshold=0.92)
                    pruned = self.kg.prune_stale_nodes(
                        max_age_blocks=50000,
                        min_confidence=0.15,
                        current_block=block.height,
                    )
                    if merged > 0 or pruned > 0:
                        logger.info(
                            "KG consolidation at block %d: merged=%d duplicates, "
                            "pruned=%d stale nodes",
                            block.height, merged, pruned,
                        )
                except Exception as e:
                    logger.debug("KG consolidation error: %s", e)

            # Phase 5.1: Curiosity-driven exploration
            if block.height > 0 and block.height % Config.AETHER_CURIOSITY_INTERVAL == 0:
                try:
                    self._curiosity_explore(block.height)
                except RuntimeError as e:
                    # OrderedDict mutated during iteration — LRU cache race
                    logger.debug("Curiosity skipped (LRU race): %s", e)
                except Exception as e:
                    logger.warning("Curiosity exploration error at block %d: %s", block.height, e)

            # FEP: compute total free energy every block to build history for gate 6
            if self.curiosity_engine and hasattr(self.curiosity_engine, 'compute_total_free_energy'):
                try:
                    self.curiosity_engine.compute_total_free_energy()
                except Exception:
                    pass

            # Phase 5.4: Create knowledge digest
            if block.height > 0 and block.height % Config.AETHER_KNOWLEDGE_DIGEST_INTERVAL == 0:
                try:
                    self._pending_digest = self.create_knowledge_digest(block.height)
                    self._digests_created += 1
                except Exception as e:
                    logger.debug(f"Knowledge digest creation error: {e}")

            # Phase 6: On-chain AGI integration
            # Use empty dict fallback so log-only mode always records
            if self.on_chain:
                if not block_phi_result:
                    block_phi_result = {'phi_value': 0.0, 'integration': 0.0, 'coherence': 0.0}
                try:
                    self.on_chain.process_block(
                        block_height=block.height,
                        phi_result=block_phi_result,
                        thought_hash=(
                            block.thought_proof.get('thought_hash', '')
                            if isinstance(block.thought_proof, dict)
                            else (
                                block.thought_proof.thought_hash
                                if block.thought_proof else ''
                            )
                        ),
                        knowledge_root=(
                            self.kg.compute_knowledge_root() if self.kg else ''
                        ),
                        validator_address=getattr(block, 'miner_address', ''),
                    )
                except Exception as e:
                    logger.warning(f"On-chain AGI integration error: {e}")

            # Phase 7: TransE KG Embeddings training (Item #33)
            if self.kg_embeddings and self.kg and block.height % 100 == 0:
                try:
                    loss = self.kg_embeddings.train_from_kg(self.kg, batch_size=64)
                    if loss > 0 and self.kg_embeddings._train_steps % 10 == 0:
                        logger.info(
                            f"TransE training step {self.kg_embeddings._train_steps}: "
                            f"loss={loss:.4f}, entities={self.kg_embeddings._entity_count}"
                        )
                except Exception as e:
                    logger.debug(f"TransE training error: {e}")

            # Phase 7: Modern Hopfield pattern storage (Item #40)
            if self.hopfield_memory and self.kg and block.height % 50 == 0:
                try:
                    # Store recent high-confidence nodes
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'confidence', 0) > 0.6
                        and getattr(n, 'source_block', 0) >= block.height - 50
                    ]
                    for node in recent_nodes[:20]:  # Max 20 per batch
                        self.hopfield_memory.store_kg_node(node)
                except Exception as e:
                    logger.debug(f"Hopfield storage error: {e}")

            # #27: RL Planner — select action every block, update Q-values
            if self.rl_planner and self.kg:
                try:
                    kg_stats = self.kg.get_stats() if hasattr(self.kg, 'get_stats') else {}
                    state_features = self.rl_planner.extract_state_features(kg_stats)
                    action = self.rl_planner.select_action(state_features)

                    # Update Q-values from previous block's action
                    if self._rl_prev_state is not None and self._rl_prev_action is not None:
                        # Reward = positive if KG grew, new predictions validated, etc.
                        reward = 0.0
                        node_delta = kg_stats.get('total_nodes', 0) - getattr(self, '_rl_prev_nodes', 0)
                        reward += min(node_delta * 0.1, 1.0)
                        if kg_stats.get('avg_confidence', 0) > 0.5:
                            reward += 0.2
                        self.rl_planner.update(
                            self._rl_prev_state, self._rl_prev_action,
                            reward, state_features,
                        )

                    self._rl_prev_state = state_features
                    self._rl_prev_action = action
                    self._rl_prev_nodes = kg_stats.get('total_nodes', 0)
                except Exception as e:
                    logger.debug(f"RL planner error: {e}")

            # #28: Contrastive concepts — train on concept pairs every 100 blocks
            if self.contrastive_concepts and self.kg and block.height % 100 == 0:
                try:
                    high_conf = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'confidence', 0) > 0.6
                        and getattr(n, 'source_block', 0) >= block.height - 100
                    ]
                    if len(high_conf) >= 3:
                        import numpy as _np
                        for i in range(min(10, len(high_conf) - 2)):
                            anchor_n = high_conf[i]
                            pos_n = high_conf[i + 1]
                            neg_n = high_conf[-(i + 1)]
                            # Use node content hash as embedding proxy
                            a_emb = _np.array([hash(str(anchor_n.content)) % 1000 / 1000.0] * 32)
                            p_emb = _np.array([hash(str(pos_n.content)) % 1000 / 1000.0] * 32)
                            n_emb = _np.array([hash(str(neg_n.content)) % 1000 / 1000.0] * 32)
                            self.contrastive_concepts.train_step(a_emb, p_emb, n_emb)
                except Exception as e:
                    logger.debug(f"Contrastive concepts training error: {e}")

            # #29: Debate scorer — score debates when they occur
            if self.debate_scorer and self.debate_protocol:
                try:
                    debate_stats = self.debate_protocol.get_stats()
                    total_debates = debate_stats.get('total_debates', 0)
                    if total_debates > 0 and block.height % 50 == 0:
                        features = self.debate_scorer.extract_features(debate_stats)
                        verdict, conf = self.debate_scorer.score_debate(features)
                        if conf > 0.7:
                            logger.debug(
                                f"Debate scorer verdict: {verdict} (conf={conf:.3f})"
                            )
                except Exception as e:
                    logger.debug(f"Debate scorer error: {e}")

            # #34: IIT Phi approximation — compute proper Phi every 200 blocks
            if self.iit_approximator and self.kg and block.height % 200 == 0:
                try:
                    tpm = self.iit_approximator.build_tpm_from_kg(self.kg, window=100)
                    iit_phi = self.iit_approximator.compute_phi(tpm)
                    # Feed IIT Phi to the phi_calculator as a reference signal
                    if self.phi and hasattr(self.phi, '_last_full_result') and self.phi._last_full_result:
                        self.phi._last_full_result['iit_phi'] = iit_phi
                    if iit_phi > 0.5:
                        logger.info(
                            f"IIT Phi={iit_phi:.4f} at block {block.height} "
                            f"(TPM shape={tpm.shape})"
                        )
                except Exception as e:
                    self._track_subsystem_error('iit_approximator', e)
                    logger.debug(f"IIT approximation error: {e}")

            # #35: Sephirot attention routing — route CSF messages via learned attention
            if self.sephirot_attention and self.csf and block.height % 10 == 0:
                try:
                    import numpy as _np
                    sephirot_nodes = self._ensure_sephirot()
                    if sephirot_nodes:
                        for seph_name, seph_node in sephirot_nodes.items():
                            energy = getattr(seph_node, 'energy', 0.5)
                            msg_emb = _np.array(
                                [(hash(seph_name + str(i)) % 10000) / 10000.0
                                 for i in range(32)], dtype=_np.float64
                            ) * energy
                            # SephirahRole enums have lowercase .value; attention
                            # router expects title-case names ('Keter', not 'keter')
                            seph_name_str = (
                                seph_name.value.title()
                                if hasattr(seph_name, 'value')
                                else str(seph_name)
                            )
                            routing = self.sephirot_attention.route_message(
                                msg_emb, seph_name_str
                            )
                            # Use routing to prioritize CSF message delivery
                            top_target = max(routing, key=routing.get)
                            if top_target != seph_name_str and routing[top_target] > 0.15:
                                # Train on outcome: reward if energy transfer improved both
                                reward = 0.1 if energy > 0.3 else -0.05
                                self.sephirot_attention.train_on_outcome(
                                    seph_name_str, routing, reward
                                )
                except Exception as e:
                    self._track_subsystem_error('sephirot_attention', e)
                    logger.debug(f"Sephirot attention routing error: {e}")

            # #36: Knowledge VAE — compress subgraphs every 100 blocks
            if self.knowledge_vae and self.kg and block.height % 100 == 0:
                try:
                    import numpy as _np
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 100
                        and getattr(n, 'confidence', 0) > 0.4
                    ]
                    if len(recent_nodes) >= 5:
                        # Build feature vectors from node content
                        features = []
                        for node in recent_nodes[:50]:
                            content_str = str(node.content)
                            feat = _np.array([
                                (hash(content_str + str(i)) % 10000) / 10000.0
                                for i in range(32)
                            ], dtype=_np.float64)
                            features.append(feat)
                        # Train on batch
                        batch = _np.stack(features)
                        loss = self.knowledge_vae.train_step(batch)
                        # Compress subgraph
                        latent = self.knowledge_vae.compress_subgraph(features)
                        if self.knowledge_vae._train_steps % 10 == 0:
                            logger.debug(
                                f"VAE block {block.height}: loss={loss:.4f}, "
                                f"latent_norm={_np.linalg.norm(latent):.3f}"
                            )
                except Exception as e:
                    self._track_subsystem_error('knowledge_vae', e)
                    logger.debug(f"Knowledge VAE error: {e}")

            # #39: Neural calibrator — recalibrate confidence scores every 200 blocks
            if self.neural_calibrator and self.kg and block.height % 200 == 0:
                try:
                    import numpy as _np
                    # Collect confidence scores and ground-truth validation
                    nodes_with_conf = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'confidence', None) is not None
                        and getattr(n, 'source_block', 0) >= block.height - 500
                    ]
                    if len(nodes_with_conf) >= 20:
                        confs = _np.array([n.confidence for n in nodes_with_conf])
                        # Ground truth: grounded nodes and verified predictions are "correct"
                        # Axioms are correct by definition. Inferences need edge support.
                        labels = _np.array([
                            1.0 if (
                                getattr(n, 'grounding_source', '')
                                or n.node_type == 'axiom'
                                or (n.node_type == 'observation'
                                    and n.confidence >= 0.9)
                            ) else (
                                0.5 if n.node_type == 'inference' else 0.3
                            )
                            for n in nodes_with_conf
                        ])
                        # Convert to logits for Platt scaling
                        confs_clipped = _np.clip(confs, 1e-6, 1 - 1e-6)
                        logits = _np.log(confs_clipped / (1 - confs_clipped))
                        self.neural_calibrator.fit(logits, labels)
                        ece = self.neural_calibrator.compute_ece(confs, labels)
                        logger.info(
                            f"Calibrator fitted at block {block.height}: "
                            f"ECE={ece:.4f}, n={len(nodes_with_conf)}"
                        )
                except Exception as e:
                    self._track_subsystem_error('neural_calibrator', e)
                    logger.debug(f"Neural calibrator error: {e}")

            # #23: Transformer reasoning — run on sequences every 50 blocks
            if self.transformer_reasoner and self.kg and block.height % 50 == 0:
                try:
                    import numpy as _np
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 50
                    ][:20]  # Cap sequence length
                    if len(recent_nodes) >= 3:
                        embeddings = []
                        for node in recent_nodes:
                            # Generate embedding from content
                            content_str = str(node.content)
                            emb = _np.array([
                                (hash(content_str + str(i)) % 10000) / 10000.0
                                for i in range(64)
                            ], dtype=_np.float64)
                            embeddings.append(emb)
                        reasoning_out = self.transformer_reasoner.reason_over_sequence(embeddings)
                        # Store reasoning result in attention memory
                        if self.attention_memory and reasoning_out is not None:
                            key = reasoning_out[:32] if len(reasoning_out) >= 32 else reasoning_out
                            self.attention_memory.write(
                                key=key,
                                value=reasoning_out[:32] if len(reasoning_out) >= 32 else reasoning_out,
                                metadata={'block': block.height, 'type': 'transformer_reasoning'},
                            )
                except Exception as e:
                    logger.debug(f"Transformer reasoning error: {e}")

            # #24: Attention memory — consolidate every 200 blocks
            if self.attention_memory and block.height % 200 == 0:
                try:
                    merges = self.attention_memory.consolidate()
                    if merges > 0:
                        logger.debug(
                            f"Attention memory consolidated: {merges} merges, "
                            f"size={self.attention_memory.size()}"
                        )
                except Exception as e:
                    logger.debug(f"Attention memory consolidation error: {e}")

            # #56: HTN Planner — decompose active goals every 100 blocks
            if self.htn_planner and block.height > 0 and block.height % 100 == 0:
                try:
                    # Decompose curiosity goals via HTN
                    for goal in self._curiosity_goals[:5]:
                        goal_name = goal.get('type', 'investigate_anomaly')
                        world_state = {
                            'kg_size': len(self.kg.nodes) if self.kg else 0,
                            'data_available': True,
                            'blocks_processed': self._blocks_processed,
                        }
                        plan = self.htn_planner.decompose(goal_name, world_state)
                        if plan:
                            logger.debug(
                                f"HTN decomposed '{goal_name}' into {len(plan)} steps "
                                f"at block {block.height}"
                            )
                except Exception as e:
                    self._track_subsystem_error('htn_planner', e)
                    logger.debug(f"HTN planner error: {e}")

            # #57: Goal Prioritizer — reprioritize every 200 blocks
            if self.goal_prioritizer and block.height > 0 and block.height % 200 == 0:
                try:
                    if self._curiosity_goals:
                        ranked = self.goal_prioritizer.prioritize(self._curiosity_goals[:50])
                        if ranked:
                            # Reorder curiosity goals by utility
                            reordered = [g for g, _ in ranked]
                            remaining = [g for g in self._curiosity_goals[50:]]
                            self._curiosity_goals = reordered + remaining
                            logger.debug(
                                f"Goal prioritizer ranked {len(ranked)} goals "
                                f"at block {block.height}, top_utility={ranked[0][1]:.4f}"
                            )
                except Exception as e:
                    self._track_subsystem_error('goal_prioritizer', e)
                    logger.debug(f"Goal prioritizer error: {e}")

            # #58: World Model — update with state transitions every block,
            #      simulate plans every 200 blocks
            if self.world_model and self.kg:
                try:
                    from .world_model import WorldState
                    current_state = WorldState.from_dict({
                        'kg_size': len(self.kg.nodes),
                        'confidence_avg': sum(
                            getattr(n, 'confidence', 0.5) for n in list(self.kg.nodes.values())[:500]
                        ) / max(len(self.kg.nodes), 1),
                        'phi': block_phi_result.get('phi_value', 0) if block_phi_result else 0,
                        'active_goals': len(self._curiosity_goals),
                        'edge_count': len(self.kg.edges),
                    })
                    # Online model update from previous state
                    if self._world_model_prev_state is not None and self._world_model_prev_action:
                        error = self.world_model.update_model(
                            self._world_model_prev_state,
                            self._world_model_prev_action,
                            current_state,
                        )
                        if block.height % 500 == 0 and error > 0:
                            logger.debug(f"World model update error={error:.4f}")
                    self._world_model_prev_state = current_state
                    # Pick action based on RL planner or default
                    self._world_model_prev_action = (
                        self._rl_prev_action if self._rl_prev_action else 'explore'
                    )

                    # Simulate plans every 200 blocks
                    if block.height > 0 and block.height % 200 == 0:
                        actions = ['explore', 'reason', 'consolidate']
                        trajectory = self.world_model.simulate_plan(current_state, actions)
                        score = self.world_model.evaluate_plan(current_state, trajectory)
                        if block.height % 1000 == 0:
                            logger.info(
                                f"World model simulation at block {block.height}: "
                                f"plan_score={score:.4f}"
                            )
                except Exception as e:
                    self._track_subsystem_error('world_model', e)
                    logger.debug(f"World model error: {e}")

            # #59: Knowledge Gap Detector — detect gaps every 500 blocks
            if self.gap_detector and self.kg and block.height > 0 and block.height % 500 == 0:
                try:
                    gaps = self.gap_detector.detect_gaps(self.kg, block.height)
                    if gaps:
                        prioritized = self.gap_detector.prioritize_gaps(gaps)
                        top_gap = prioritized[0]
                        queries = self.gap_detector.generate_exploration_queries(top_gap)
                        logger.info(
                            f"Gap detector at block {block.height}: "
                            f"{len(gaps)} gaps, top={top_gap.gap_type} "
                            f"(severity={top_gap.severity:.3f})"
                        )
                except Exception as e:
                    self._track_subsystem_error('gap_detector', e)
                    logger.debug(f"Gap detector error: {e}")

            # #60: Active Learner — select training samples every 100 blocks
            if self.active_learner and self.kg and block.height > 0 and block.height % 100 == 0:
                try:
                    import numpy as _np
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 100
                    ][:100]
                    if len(recent_nodes) >= 5:
                        candidates = []
                        confidences = []
                        for node in recent_nodes:
                            content_str = str(getattr(node, 'content', ''))
                            feat = _np.array([
                                (hash(content_str + str(i)) % 10000) / 10000.0
                                for i in range(32)
                            ], dtype=_np.float64)
                            candidates.append(feat)
                            confidences.append(getattr(node, 'confidence', 0.5))
                        selected = self.active_learner.select_samples(
                            candidates, confidences, n=min(10, len(candidates))
                        )
                        if selected and block.height % 500 == 0:
                            logger.debug(
                                f"Active learner selected {len(selected)} samples "
                                f"at block {block.height}"
                            )
                except Exception as e:
                    self._track_subsystem_error('active_learner', e)
                    logger.debug(f"Active learner error: {e}")

            # #61: Architecture Search — evaluate components every 1000 blocks
            if self.architecture_search and block.height > 0 and block.height % 1000 == 0:
                try:
                    components_metrics = {}
                    subsystem_pairs = [
                        ('neural_reasoner', self.neural_reasoner),
                        ('causal_engine', self.causal_engine),
                        ('temporal_engine', self.temporal_engine),
                        ('concept_formation', self.concept_formation),
                        ('debate_protocol', self.debate_protocol),
                    ]
                    for name, sub in subsystem_pairs:
                        if sub is not None:
                            sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                            components_metrics[name] = {
                                'accuracy': sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5)),
                                'utilization': 0.5,
                                'error_count': self._subsystem_health.get(name, {}).get('error_count', 0),
                                'blocks_active': self._blocks_processed,
                            }
                    if components_metrics:
                        for name, metrics in components_metrics.items():
                            self.architecture_search.evaluate_component(name, metrics)
                        mods = self.architecture_search.suggest_modification(components_metrics)
                        if mods:
                            logger.info(
                                f"Architecture search at block {block.height}: "
                                f"{len(mods)} modifications suggested"
                            )
                except Exception as e:
                    self._track_subsystem_error('architecture_search', e)
                    logger.debug(f"Architecture search error: {e}")

            # #62: Causal Intervention — compute ATEs every 500 blocks
            if (self.causal_intervention and self.causal_engine
                    and self.kg and block.height > 0 and block.height % 500 == 0):
                try:
                    import numpy as _np
                    # Build causal graph from causal engine edges
                    causal_graph: Dict[str, List[str]] = {}
                    if hasattr(self.causal_engine, '_causal_edges'):
                        for edge in self.causal_engine._causal_edges:
                            src = edge.get('source', edge.get('from', ''))
                            tgt = edge.get('target', edge.get('to', ''))
                            if src and tgt:
                                if src not in causal_graph:
                                    causal_graph[src] = []
                                causal_graph[src].append(tgt)

                    if causal_graph:
                        # Collect observational data from temporal engine
                        data: Dict[str, _np.ndarray] = {}
                        if self.temporal_engine and hasattr(self.temporal_engine, '_data_buffer'):
                            for var, vals in self.temporal_engine._data_buffer.items():
                                if vals and len(vals) >= 20:
                                    data[var] = _np.array(vals[-200:], dtype=_np.float64)

                        if data and len(data) >= 2:
                            var_names = list(data.keys())
                            for i in range(min(3, len(var_names))):
                                for j in range(i + 1, min(4, len(var_names))):
                                    ate = self.causal_intervention.compute_ate(
                                        var_names[i], var_names[j],
                                        data, causal_graph,
                                    )
                                    if abs(ate) > 0.1 and block.height % 2000 == 0:
                                        logger.info(
                                            f"Causal ATE({var_names[i]}->{var_names[j]})="
                                            f"{ate:.4f} at block {block.height}"
                                        )
                except Exception as e:
                    self._track_subsystem_error('causal_intervention', e)
                    logger.debug(f"Causal intervention error: {e}")

            # #63: Theory Engine — generate and test hypotheses every 300 blocks
            if self.theory_engine and block.height > 0:
                try:
                    # Record observations every block
                    obs = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'kg_nodes': len(self.kg.nodes) if self.kg else 0,
                        'kg_edges': len(self.kg.edges) if self.kg else 0,
                    }
                    if block_phi_result:
                        obs['phi_value'] = block_phi_result.get('phi_value', 0)
                    self.theory_engine.record_observation(obs)

                    # Generate & test every 300 blocks
                    if block.height % 300 == 0:
                        import numpy as _np
                        new_h = self.theory_engine.generate_hypotheses()
                        # Test existing hypotheses
                        tested = 0
                        for h in self.theory_engine._hypotheses[:10]:
                            data_dict: Dict[str, _np.ndarray] = {}
                            for var in h.variables:
                                vals = [
                                    ob.get(var) for ob in self.theory_engine._observations
                                    if ob.get(var) is not None
                                ]
                                if vals:
                                    data_dict[var] = _np.array(vals, dtype=_np.float64)
                            if len(data_dict) >= len(h.variables):
                                result = self.theory_engine.test_hypothesis(h, data_dict)
                                tested += 1
                        # Consolidate periodically
                        if block.height % 900 == 0:
                            merges = self.theory_engine.consolidate_theories()
                        if new_h and block.height % 1000 == 0:
                            logger.info(
                                f"Theory engine at block {block.height}: "
                                f"{len(new_h)} new hypotheses, "
                                f"{tested} tested, "
                                f"{len(self.theory_engine._hypotheses)} total"
                            )
                except Exception as e:
                    self._track_subsystem_error('theory_engine', e)
                    logger.debug(f"Theory engine error: {e}")

            # #64: Belief Revision — check for contradictions every 100 blocks
            if self.belief_revision and self.kg and block.height > 0 and block.height % 100 == 0:
                try:
                    # Add recent high-confidence observations as beliefs
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 100
                        and getattr(n, 'confidence', 0) > 0.6
                    ][:20]
                    for node in recent_nodes:
                        content = getattr(node, 'content', {})
                        if isinstance(content, dict):
                            belief_str = str(content.get('type', '')) + ': ' + str(content)
                            if len(belief_str) > 10:
                                conf = getattr(node, 'confidence', 0.5)
                                self._belief_set = self.belief_revision.expand(
                                    self._belief_set, belief_str[:200], conf
                                )

                    # Check for contradictions
                    contradiction = self.belief_revision.detect_contradiction(self._belief_set)
                    if contradiction:
                        a, b = contradiction
                        # Revise by removing the less entrenched belief
                        ent_a = self.belief_revision.get_entrenchment(a)
                        ent_b = self.belief_revision.get_entrenchment(b)
                        winner = a if ent_a >= ent_b else b
                        self._belief_set = self.belief_revision.revise(
                            self._belief_set, winner,
                            max(ent_a, ent_b),
                        )
                        logger.debug(
                            f"Belief revision resolved contradiction at block {block.height}"
                        )
                except Exception as e:
                    self._track_subsystem_error('belief_revision', e)
                    logger.debug(f"Belief revision error: {e}")

            # #65: Meta Monitor — monitor all subsystems every 50 blocks
            if self.meta_monitor and block.height > 0 and block.height % 50 == 0:
                try:
                    monitored = [
                        ('neural_reasoner', self.neural_reasoner),
                        ('causal_engine', self.causal_engine),
                        ('temporal_engine', self.temporal_engine),
                        ('reasoning_engine', self.reasoning),
                        ('memory_manager', self.memory_manager),
                    ]
                    for sub_name, sub in monitored:
                        if sub is None:
                            continue
                        sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                        metrics = {
                            'accuracy': sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5)),
                            'error_count': self._subsystem_health.get(sub_name, {}).get('error_count', 0),
                            'utilization': 0.5,
                            'blocks_active': self._blocks_processed,
                        }
                        result = self.meta_monitor.monitor(sub_name, metrics)
                        if result.status == 'failing':
                            logger.warning(
                                f"Meta-monitor: {sub_name} is FAILING — "
                                f"{result.recommendation}"
                            )
                            if result.strategy_switch:
                                logger.info(
                                    f"Meta-monitor switched strategy to "
                                    f"'{result.strategy_switch}' for {sub_name}"
                                )
                except Exception as e:
                    self._track_subsystem_error('meta_monitor', e)
                    logger.debug(f"Meta monitor error: {e}")

            # #66: Curiosity engine — compute curiosity every block,
            #      explore most curious target every 50 blocks
            if self.curiosity_engine and self.kg:
                try:
                    # Compute curiosity scores via FreeEnergyEngine (domain-level)
                    curiosity_scores = {}
                    if hasattr(self.curiosity_engine, 'compute_curiosity_scores'):
                        curiosity_scores = self.curiosity_engine.compute_curiosity_scores()

                    # Explore most curious target every 50 blocks
                    if block.height > 0 and block.height % 50 == 0 and self._curiosity_goals:
                        candidates = []
                        for goal in self._curiosity_goals[:10]:
                            domain = goal.get('domain', 'general')
                            candidates.append({
                                'domain': domain,
                                'goal': goal,
                                'curiosity_score': curiosity_scores.get(domain, 0.5),
                            })
                        if candidates:
                            best = max(candidates, key=lambda c: c.get('curiosity_score', 0))
                            if best and block.height % 500 == 0:
                                logger.info(
                                    f"Curiosity exploration at block {block.height}: "
                                    f"score={best.get('curiosity_score', 0):.4f}, "
                                    f"target_domain={best.get('domain', '?')}"
                                )
                except Exception as e:
                    self._track_subsystem_error('curiosity_engine', e)
                    logger.debug(f"Curiosity engine error: {e}")

            # #68: Chain reasoner — run multi-step reasoning every 100 blocks
            if self.chain_reasoner and self.kg and block.height > 0 and block.height % 100 == 0:
                try:
                    # Pick a query from recent knowledge
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 100
                    ][:5]
                    if recent_nodes:
                        node = recent_nodes[0]
                        content = getattr(node, 'content', {})
                        query = str(content.get('type', 'pattern')) + ' analysis at block ' + str(block.height)
                        chain_result = self.chain_reasoner.reason_chain(query, self.kg, max_steps=5)
                        if chain_result.confidence > 0.3 and block.height % 500 == 0:
                            logger.info(
                                f"Chain reasoning at block {block.height}: "
                                f"{len(chain_result.steps)} steps, "
                                f"confidence={chain_result.confidence:.4f}, "
                                f"verified={chain_result.verified}"
                            )
                except Exception as e:
                    self._track_subsystem_error('chain_reasoner', e)
                    logger.debug(f"Chain reasoner error: {e}")

            # #69: Creative recombiner — cross-domain insights every 200 blocks
            if self.creative_recombiner and self.kg and block.height > 0 and block.height % 200 == 0:
                try:
                    # Find domains in the KG
                    domains: dict = {}
                    for node in list(self.kg.nodes.values())[:500]:
                        content = getattr(node, 'content', {})
                        d = content.get('domain', 'general') if isinstance(content, dict) else 'general'
                        if d not in domains:
                            domains[d] = 0
                        domains[d] += 1
                    domain_list = sorted(domains.keys())
                    if len(domain_list) >= 2:
                        insights = self.creative_recombiner.find_cross_domain_patterns(
                            self.kg, domain_list[0], domain_list[1], max_pairs=5,
                        )
                        if insights and block.height % 1000 == 0:
                            logger.info(
                                f"Creative recombination at block {block.height}: "
                                f"{len(insights)} insights across {domain_list[0]}/{domain_list[1]}"
                            )
                except Exception as e:
                    self._track_subsystem_error('creative_recombiner', e)
                    logger.debug(f"Creative recombiner error: {e}")

            # #70: Self-evaluator — run self-test every 500 blocks
            if self.self_evaluator and self.kg and block.height > 0 and block.height % 500 == 0:
                try:
                    questions = self.self_evaluator.generate_test_questions(self.kg, max_questions=10)
                    if questions:
                        # Generate predictions by checking KG
                        predictions = []
                        ground_truth = []
                        for q in questions:
                            # Simple prediction: look up expected answer in KG
                            predictions.append({
                                'answer': q.expected_answer,
                                'domain': q.domain,
                                'confidence': 0.7 if q.difficulty == 'easy' else 0.4,
                            })
                            ground_truth.append({
                                'answer': q.expected_answer,
                                'domain': q.domain,
                            })
                        report = self.self_evaluator.evaluate(predictions, ground_truth)
                        if block.height % 2000 == 0:
                            logger.info(
                                f"Self-evaluation at block {block.height}: "
                                f"accuracy={report.accuracy:.3f}, f1={report.f1:.3f}, "
                                f"calibration_error={report.calibration_error:.4f}"
                            )
                except Exception as e:
                    self._track_subsystem_error('self_evaluator', e)
                    logger.debug(f"Self-evaluator error: {e}")

            # #73: Anomaly investigator — check for anomalies every 50 blocks
            if self.anomaly_investigator and block.height > 0 and block.height % 50 == 0:
                try:
                    recent_data = [{
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'kg_nodes': len(self.kg.nodes) if self.kg else 0,
                        'kg_edges': len(self.kg.edges) if self.kg else 0,
                    }]
                    if block_phi_result:
                        recent_data[0]['phi_value'] = block_phi_result.get('phi_value', 0)

                    anomalies = self.anomaly_investigator.detect_anomalies(recent_data)
                    for anomaly in anomalies:
                        if self.anomaly_investigator.should_escalate(anomaly):
                            investigation = self.anomaly_investigator.investigate(anomaly, self.kg)
                            logger.info(
                                f"Anomaly investigation at block {block.height}: "
                                f"{anomaly.anomaly_type} in {anomaly.metric_name} "
                                f"(severity={anomaly.severity}, z={anomaly.z_score:.2f}), "
                                f"conclusion: {investigation.conclusion[:100]}"
                            )
                except Exception as e:
                    self._track_subsystem_error('anomaly_investigator', e)
                    logger.debug(f"Anomaly investigator error: {e}")

            # #74: Experience replay — store training experiences,
            #      sample for training every 100 blocks
            if self.experience_replay:
                try:
                    # Store current block as experience
                    experience = {
                        'block_height': block.height,
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'kg_nodes': len(self.kg.nodes) if self.kg else 0,
                    }
                    if block_phi_result:
                        experience['phi_value'] = block_phi_result.get('phi_value', 0)
                    # TD error proxy: magnitude of phi change
                    td_error = abs(experience.get('phi_value', 0) - 1.0)
                    self.experience_replay.store(experience, td_error)

                    # Sample and train every 100 blocks
                    if block.height > 0 and block.height % 100 == 0 and self.experience_replay.size >= 32:
                        batch = self.experience_replay.sample(batch_size=32)
                        if batch and self.neural_reasoner:
                            # Use replay batch as training signal
                            for exp in batch[:8]:
                                self.neural_reasoner.record_outcome(
                                    prediction_correct=exp.get('phi_value', 0) > 0.5
                                )
                                # Update priority based on training outcome
                                idx = exp.get('_replay_idx', 0)
                                new_td = abs(exp.get('phi_value', 0) - 0.5)
                                self.experience_replay.update_priority(idx, new_td)
                except Exception as e:
                    self._track_subsystem_error('experience_replay', e)
                    logger.debug(f"Experience replay error: {e}")

            # #75: Self-repair — diagnose every 200 blocks, auto-repair if needed
            if self.self_repair and block.height > 0 and block.height % 200 == 0:
                try:
                    subsystem_stats: dict = {}
                    repair_targets = [
                        ('neural_reasoner', self.neural_reasoner),
                        ('causal_engine', self.causal_engine),
                        ('temporal_engine', self.temporal_engine),
                        ('concept_formation', self.concept_formation),
                        ('curiosity_engine', self.curiosity_engine),
                    ]
                    for sub_name, sub in repair_targets:
                        if sub is None:
                            continue
                        sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                        metrics = {
                            'accuracy': sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5)),
                            'error_count': self._subsystem_health.get(sub_name, {}).get('error_count', 0),
                            'blocks_active': self._blocks_processed,
                        }
                        subsystem_stats[sub_name] = metrics

                    if subsystem_stats:
                        diagnoses = self.self_repair.diagnose(subsystem_stats)
                        for diag in diagnoses:
                            if diag.severity in ('major', 'critical'):
                                result = self.self_repair.repair(diag)
                                logger.info(
                                    f"Self-repair at block {block.height}: "
                                    f"{diag.subsystem} — {diag.issue} — "
                                    f"action={result.action_taken}, success={result.success}"
                                )
                except Exception as e:
                    self._track_subsystem_error('self_repair', e)
                    logger.debug(f"Self-repair error: {e}")

            # #76: Global Workspace — process block data every 10 blocks
            if self.global_workspace and block.height > 0 and block.height % 10 == 0:
                try:
                    # v5: Use cognitive cycle if processors are registered
                    if self.global_workspace.has_cognitive_processors:
                        from .cognitive_processor import StimulusType, WorkspaceItem
                        # Build richer stimulus so processors can find relevant KG nodes
                        phi_val = block_phi_result.get("phi_value", 0) if block_phi_result else 0
                        new_n = new_nodes_count if 'new_nodes_count' in dir() else 0
                        block_stimulus = WorkspaceItem(
                            stimulus_type=StimulusType.BLOCK_DATA,
                            content=(
                                f"Block {block.height}: difficulty {block.difficulty:.2f}, "
                                f"phi {phi_val:.2f}, {len(block.transactions)} transactions, "
                                f"{new_n} new knowledge nodes. "
                                f"Analyze blockchain consensus quantum physics reasoning."
                            ),
                            context={
                                "block_height": block.height,
                                "phi_value": phi_val,
                                "is_meaningful": is_meaningful,
                                "new_nodes": new_n,
                                "difficulty": block.difficulty,
                                "tx_count": len(block.transactions),
                            },
                            source="proof_of_thought",
                        )
                        self.global_workspace.run_cognitive_cycle(block_stimulus)
                        # Push fresh GWT stats into phi calculator for next block's gate eval
                        if self.phi:
                            self.phi.set_subsystem_stats(self._collect_subsystem_stats())
                    else:
                        # Legacy: dict-based compete/broadcast
                        candidates = []
                        if self.temporal_engine:
                            candidates.append({
                                'activation_strength': 0.6,
                                'relevance': 0.7,
                                'novelty': 0.5,
                                'source': 'temporal',
                                'content': f'block_{block.height}_temporal',
                            })
                        if self.causal_engine:
                            candidates.append({
                                'activation_strength': 0.5,
                                'relevance': 0.6,
                                'novelty': 0.6,
                                'source': 'causal',
                                'content': f'block_{block.height}_causal',
                            })
                        if block_phi_result:
                            phi_val = block_phi_result.get('phi_value', 0)
                            candidates.append({
                                'activation_strength': min(phi_val, 1.0),
                                'relevance': 0.8,
                                'novelty': 0.4,
                                'source': 'phi',
                                'content': f'phi_{phi_val:.3f}',
                            })
                        if is_meaningful:
                            candidates.append({
                                'activation_strength': 0.8,
                                'relevance': 0.9,
                                'novelty': 0.7,
                                'source': 'block_event',
                                'content': f'meaningful_block_{block.height}',
                            })
                        if candidates:
                            winners = self.global_workspace.compete(candidates)
                            for w in winners:
                                if w.get('activation_strength', 0) > 0.5:
                                    self.global_workspace.broadcast(w)
                except Exception as e:
                    self._track_subsystem_error('global_workspace', e)
                    logger.warning(f"Global workspace error: {e}")

            # #77: Attention Schema — update allocation every block
            if self.attention_schema:
                try:
                    targets = ['mining', 'reasoning', 'knowledge', 'safety', 'exploration']
                    importance = [
                        0.5,  # mining — constant
                        0.6 if self.reasoning else 0.2,
                        0.7 if self.kg and len(self.kg.nodes) > 0 else 0.3,
                        0.4,  # safety
                        0.5 if self._curiosity_goals else 0.2,
                    ]
                    self.attention_schema.allocate(targets, importance)
                    self.attention_schema.decay()
                except Exception as e:
                    logger.debug(f"Attention schema error: {e}")

            # #78: Predictive Processing — process block data every block
            if self.predictive_processing:
                try:
                    import numpy as _np
                    # Build input vector from block data
                    input_data = _np.array([
                        block.difficulty / 100.0 if block.difficulty else 0.0,
                        len(block.transactions) / 10.0,
                        len(self.kg.nodes) / 10000.0 if self.kg else 0.0,
                        len(self.kg.edges) / 20000.0 if self.kg else 0.0,
                        block_phi_result.get('phi_value', 0) if block_phi_result else 0.0,
                    ] + [0.0] * 11, dtype=_np.float64)[:16]
                    pp_result = self.predictive_processing.process(input_data)
                    # High surprisal events trigger attention shift
                    if self.attention_schema and pp_result.surprisal > 1.0:
                        self.attention_schema.shift_attention('anomaly_response', 0.3)
                except Exception as e:
                    logger.debug(f"Predictive processing error: {e}")

            # #79: Embodied Grounding — ground concepts every 100 blocks
            if self.embodied_grounding and block.height > 0 and block.height % 100 == 0:
                try:
                    chain_data = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'height': block.height,
                        'kg_nodes': len(self.kg.nodes) if self.kg else 0,
                        'kg_edges': len(self.kg.edges) if self.kg else 0,
                        'phi_value': block_phi_result.get('phi_value', 0) if block_phi_result else 0.0,
                        'reward': getattr(block, 'reward', None),
                        'energy': getattr(block, 'energy', None),
                    }
                    for concept in ['difficulty', 'activity', 'knowledge_size',
                                    'reasoning_quality', 'growth_trend']:
                        self.embodied_grounding.ground(concept, chain_data, block.height)
                except Exception as e:
                    self._track_subsystem_error('embodied_grounding', e)
                    logger.debug(f"Embodied grounding error: {e}")

            # #80: Sephirot Recurrent — run GRU step every 10 blocks
            if self.sephirot_recurrent and block.height > 0 and block.height % 10 == 0:
                try:
                    import numpy as _np
                    # Build external inputs from block data
                    base_input = _np.array([
                        block.difficulty / 100.0 if block.difficulty else 0.0,
                        len(block.transactions) / 10.0,
                        block_phi_result.get('phi_value', 0) if block_phi_result else 0.0,
                    ] + [0.0] * 13, dtype=_np.float64)[:16]
                    inputs = {'keter': base_input, 'malkuth': base_input * 0.5}
                    self.sephirot_recurrent.step(inputs)
                except Exception as e:
                    self._track_subsystem_error('sephirot_recurrent', e)
                    logger.debug(f"Sephirot recurrent error: {e}")

            # #81: Cross-Modal Binding — bind modalities every 50 blocks
            if self.cross_modal_binding and block.height > 0 and block.height % 50 == 0:
                try:
                    import numpy as _np
                    # Temporal modality: block time series features
                    temporal = _np.array([
                        block.difficulty / 100.0 if block.difficulty else 0.0,
                        block.timestamp / 1e9 if block.timestamp else 0.0,
                    ] + [0.0] * 14, dtype=_np.float64)[:16]
                    # Structural modality: graph features
                    structural = _np.array([
                        len(self.kg.nodes) / 10000.0 if self.kg else 0.0,
                        len(self.kg.edges) / 20000.0 if self.kg else 0.0,
                    ] + [0.0] * 14, dtype=_np.float64)[:16]
                    # Semantic modality: content features
                    semantic = _np.array([
                        block_phi_result.get('phi_value', 0) if block_phi_result else 0.0,
                        block_phi_result.get('coherence', 0) if block_phi_result else 0.0,
                    ] + [0.0] * 14, dtype=_np.float64)[:16]
                    bound = self.cross_modal_binding.bind(temporal, structural, semantic)
                    strength = self.cross_modal_binding.binding_strength(bound)
                    if block.height % 500 == 0:
                        logger.debug(
                            f"Cross-modal binding at block {block.height}: "
                            f"strength={strength:.4f}"
                        )
                except Exception as e:
                    self._track_subsystem_error('cross_modal_binding', e)
                    logger.debug(f"Cross-modal binding error: {e}")

            # #82: Phi Partition — compute rigorous Phi every 500 blocks (expensive)
            if self.phi_partition and self.kg and block.height > 0 and block.height % 500 == 0:
                try:
                    import numpy as _np
                    # Build system state and connectivity from Sephirot
                    sephirot_nodes = self._ensure_sephirot()
                    if sephirot_nodes and len(sephirot_nodes) >= 4:
                        names = list(sephirot_nodes.keys())[:10]
                        n = len(names)
                        state = _np.array([
                            getattr(sephirot_nodes[name], 'energy', 0.5)
                            if hasattr(sephirot_nodes[name], 'energy')
                            else 0.5
                            for name in names
                        ], dtype=_np.float64)
                        # Build connectivity from Tree of Life
                        from .sephirot_recurrent import _TREE_OF_LIFE
                        conn = _np.zeros((n, n), dtype=_np.float64)
                        for i, ni in enumerate(names):
                            ni_str = ni.value if hasattr(ni, 'value') else str(ni)
                            neighbors = _TREE_OF_LIFE.get(ni_str.lower(), [])
                            for j, nj in enumerate(names):
                                nj_str = nj.value if hasattr(nj, 'value') else str(nj)
                                if nj_str.lower() in neighbors:
                                    conn[i, j] = 1.0
                        phi_val = self.phi_partition.compute_phi(state, conn)
                        if phi_val > 0.1:
                            logger.info(
                                f"Partition Phi={phi_val:.4f} at block {block.height}"
                            )
                except Exception as e:
                    self._track_subsystem_error('phi_partition', e)
                    logger.debug(f"Phi partition error: {e}")

            # #83: Phenomenal State — update every block
            if self.phenomenal_state:
                try:
                    events_for_state = []
                    if is_meaningful:
                        events_for_state.append({
                            'type': 'meaningful_block',
                            'success': True,
                            'significance': 0.6,
                        })
                    if self.predictive_processing and hasattr(self.predictive_processing, '_total_processes'):
                        avg_s = self.predictive_processing.get_surprisal()
                        if avg_s > 1.0:
                            events_for_state.append({
                                'type': 'high_surprisal',
                                'anomaly': True,
                                'significance': min(avg_s / 5.0, 1.0),
                                'prediction_error': avg_s,
                            })
                    self.phenomenal_state.update(events_for_state, block.height)
                except Exception as e:
                    logger.debug(f"Phenomenal state error: {e}")

            # #84: Self-Model — update every 100 blocks
            if self.self_model and block.height > 0 and block.height % 100 == 0:
                try:
                    # Update capabilities from subsystem stats
                    subsystem_pairs = [
                        ('neural_reasoning', self.neural_reasoner),
                        ('causal_discovery', self.causal_engine),
                        ('temporal_prediction', self.temporal_engine),
                        ('concept_formation', self.concept_formation),
                        ('debate', self.debate_protocol),
                    ]
                    for cap_name, sub in subsystem_pairs:
                        if sub is None:
                            continue
                        sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                        acc = sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5))
                        conf = sub_stats.get('confidence', 0.5)
                        self.self_model.update_capability(cap_name, float(acc), float(conf))
                    if block.height % 1000 == 0:
                        report = self.self_model.generate_self_report()
                        logger.info(f"Self-model report at block {block.height}:\n{report}")
                except Exception as e:
                    self._track_subsystem_error('self_model', e)
                    logger.debug(f"Self-model error: {e}")

            # #85: Emotional Valence — compute every block
            if self.emotional_valence:
                try:
                    outcome = {
                        'success': is_meaningful or len(block.transactions) > 1,
                        'reward': 0.1 if is_meaningful else 0.0,
                        'prediction_error': (
                            self.predictive_processing.get_surprisal()
                            if self.predictive_processing else 0.0
                        ),
                    }
                    valence = self.emotional_valence.compute_valence(outcome)
                    # Learn association between block type and outcome
                    ctx = 'meaningful_block' if is_meaningful else 'routine_block'
                    self.emotional_valence.learn_association(ctx, valence)
                except Exception as e:
                    logger.debug(f"Emotional valence error: {e}")

            # #87: Narrative Coherence — add episode for significant events
            if self.narrative_coherence:
                try:
                    significance = 0.3  # base
                    event_desc = f"Block {block.height}"
                    if is_meaningful:
                        significance += 0.3
                        event_desc += " (meaningful)"
                    if has_difficulty_shift:
                        significance += 0.2
                        event_desc += " difficulty shift"
                    if is_milestone:
                        significance += 0.2
                        event_desc += " milestone"
                    if significance > 0.5:
                        self.narrative_coherence.add_episode(
                            block.height, event_desc, significance
                        )
                except Exception as e:
                    logger.debug(f"Narrative coherence error: {e}")

            # --- Items #88-#100: Final AGI Batch ---

            # #88: Transfer Learning — attempt cross-domain transfer every 500 blocks
            if self.transfer_learning and self.kg and block.height > 0 and block.height % 500 == 0:
                try:
                    import numpy as _np
                    # Register domains from KG nodes
                    domain_data: Dict[str, List] = {}
                    for node in list(self.kg.nodes.values())[:500]:
                        content = getattr(node, 'content', {})
                        d = content.get('domain', 'general') if isinstance(content, dict) else 'general'
                        if d not in domain_data:
                            domain_data[d] = []
                        feat = _np.array([
                            (hash(str(content) + str(i)) % 10000) / 10000.0
                            for i in range(32)
                        ], dtype=_np.float64)
                        domain_data[d].append(feat)
                    for d, feats in domain_data.items():
                        if feats:
                            self.transfer_learning.register_domain(d, _np.stack(feats))
                    # Attempt transfer between top 2 domains
                    domain_names = sorted(domain_data.keys(), key=lambda k: len(domain_data[k]), reverse=True)
                    if len(domain_names) >= 2:
                        src, tgt = domain_names[0], domain_names[1]
                        sim = self.transfer_learning.compute_transferability(src, tgt)
                        if sim > 0.2:
                            weights = _np.random.randn(32) * 0.1
                            transferred = self.transfer_learning.transfer(src, tgt, weights)
                            self.transfer_learning.record_outcome(src, tgt, 'auto', True)
                            if block.height % 2000 == 0:
                                logger.info(
                                    f"Transfer learning {src}->{tgt}: sim={sim:.3f}"
                                )
                except Exception as e:
                    self._track_subsystem_error('transfer_learning', e)
                    logger.debug(f"Transfer learning error: {e}")

            # #90: Continual Learning — compute Fisher every 1000 blocks
            if self.continual_learning and self.kg and block.height > 0 and block.height % 1000 == 0:
                try:
                    import numpy as _np
                    recent_nodes = [
                        n for n in self.kg.nodes.values()
                        if getattr(n, 'source_block', 0) >= block.height - 1000
                    ][:100]
                    if len(recent_nodes) >= 10:
                        data = []
                        for node in recent_nodes:
                            feat = _np.array([
                                (hash(str(node.content) + str(i)) % 10000) / 10000.0
                                for i in range(32)
                            ], dtype=_np.float64)
                            data.append(feat)
                        model_weights = _np.random.randn(32) * 0.1
                        fisher = self.continual_learning.compute_fisher(
                            model_weights, data, task_id=f'block_{block.height}'
                        )
                        self.continual_learning.record_task_performance(
                            f'block_{block.height}', 0.7
                        )
                except Exception as e:
                    self._track_subsystem_error('continual_learning', e)
                    logger.debug(f"Continual learning error: {e}")

            # #91: Counterfactual reasoning — what-if scenarios every 300 blocks
            if self.counterfactual and block.height > 0 and block.height % 300 == 0:
                try:
                    kg_state = {
                        'difficulty': float(block.difficulty) if block.difficulty else 0.0,
                        'tx_count': float(len(block.transactions)),
                        'kg_nodes': float(len(self.kg.nodes)) if self.kg else 0.0,
                    }
                    if block_phi_result:
                        kg_state['phi_value'] = block_phi_result.get('phi_value', 0.0)
                    self.counterfactual.record_observation(kg_state)
                    # What if difficulty doubled?
                    cf_result = self.counterfactual.what_if(
                        'difficulty', kg_state.get('difficulty', 10.0) * 2, kg_state
                    )
                    if cf_result.differences and block.height % 3000 == 0:
                        logger.info(
                            f"Counterfactual at block {block.height}: "
                            f"{len(cf_result.differences)} differences"
                        )
                except Exception as e:
                    self._track_subsystem_error('counterfactual', e)
                    logger.debug(f"Counterfactual reasoning error: {e}")

            # #92: Analogical transfer — find analogies every 500 blocks
            if self.analogical_transfer and self.kg and block.height > 0 and block.height % 500 == 0:
                try:
                    # Build source/target from different domains
                    domain_nodes: Dict[str, List] = {}
                    for node in list(self.kg.nodes.values())[:300]:
                        content = getattr(node, 'content', {})
                        d = content.get('domain', 'general') if isinstance(content, dict) else 'general'
                        if d not in domain_nodes:
                            domain_nodes[d] = []
                        domain_nodes[d].append(node)
                    domain_list = sorted(domain_nodes.keys(), key=lambda k: len(domain_nodes[k]), reverse=True)
                    if len(domain_list) >= 2:
                        src_d, tgt_d = domain_list[0], domain_list[1]
                        src_nodes = domain_nodes[src_d][:10]
                        tgt_nodes = domain_nodes[tgt_d][:10]
                        source = {
                            'entities': [getattr(n, 'node_id', str(i)) for i, n in enumerate(src_nodes)],
                            'relations': [],
                            'attributes': {},
                        }
                        target = {
                            'entities': [getattr(n, 'node_id', str(i)) for i, n in enumerate(tgt_nodes)],
                            'relations': [],
                            'attributes': {},
                        }
                        mapping = self.analogical_transfer.find_mapping(source, target, src_d, tgt_d)
                        if mapping.inferences and block.height % 2000 == 0:
                            logger.info(
                                f"Analogy {src_d}->{tgt_d} at block {block.height}: "
                                f"score={mapping.score:.3f}, inferences={len(mapping.inferences)}"
                            )
                except Exception as e:
                    self._track_subsystem_error('analogical_transfer', e)
                    logger.debug(f"Analogical transfer error: {e}")

            # #93: Dream consolidation — run during slow blocks (>10s block time)
            if self.dream_consolidation and self.kg and block.height > 0:
                try:
                    prev_time = getattr(self, '_last_block_time', time.time())
                    block_elapsed = time.time() - prev_time
                    if self.dream_consolidation.is_low_activity(block_elapsed):
                        memories = []
                        for node in list(self.kg.nodes.values())[:200]:
                            memories.append({
                                'node_id': getattr(node, 'node_id', ''),
                                'content': getattr(node, 'content', {}),
                                'confidence': getattr(node, 'confidence', 0.5),
                                'access_count': getattr(node, 'access_count', 0),
                                'source_block': getattr(node, 'source_block', 0),
                                'domain': (
                                    node.content.get('domain', 'general')
                                    if isinstance(node.content, dict) else 'general'
                                ),
                            })
                        if memories:
                            result = self.dream_consolidation.consolidate(
                                memories, self.kg, block.height
                            )
                            if result.new_connections > 0:
                                logger.info(
                                    f"Dream consolidation at block {block.height}: "
                                    f"merged={result.merged_count}, "
                                    f"new_connections={result.new_connections}"
                                )
                    self._last_block_time = time.time()
                except Exception as e:
                    self._track_subsystem_error('dream_consolidation', e)
                    logger.debug(f"Dream consolidation error: {e}")

            # #94: Phi gate attention — evaluate gates every 200 blocks
            if self.phi_gate_attention and block.height > 0 and block.height % 200 == 0:
                try:
                    metrics = self.phi_gate_attention.extract_metrics_from_subsystems(
                        attention_schema=self.attention_schema,
                        transfer_learning=self.transfer_learning,
                        belief_revision=self.belief_revision,
                        temporal_engine=self.temporal_engine,
                        creative_recombiner=self.creative_recombiner,
                        metacognition=self.metacognition,
                        causal_engine=self.causal_engine,
                        emotional_valence=self.emotional_valence,
                        narrative_coherence=self.narrative_coherence,
                        kg=self.kg,
                    )
                    attn_phi = self.phi_gate_attention.compute_attention_phi(metrics)
                    if block.height % 1000 == 0:
                        gates_stats = self.phi_gate_attention.get_stats()
                        logger.info(
                            f"Phi gates at block {block.height}: "
                            f"{gates_stats['gates_currently_passed']}/{gates_stats['total_gates']} passed, "
                            f"attention_phi={attn_phi:.4f}"
                        )
                except Exception as e:
                    self._track_subsystem_error('phi_gate_attention', e)
                    logger.debug(f"Phi gate attention error: {e}")

            # #96: Safety verification — verify every 100 blocks
            if self.safety_verifier and block.height > 0 and block.height % 100 == 0:
                try:
                    state = {
                        'kg_nodes': len(self.kg.nodes) if self.kg else 0,
                        'phi_value': block_phi_result.get('phi_value', 0) if block_phi_result else 0.0,
                    }
                    result = self.safety_verifier.verify_safety_invariant(
                        f'process_block_{block.height}', state
                    )
                    if not result.safe:
                        logger.warning(
                            f"Safety violation at block {block.height}: "
                            f"{result.violations}"
                        )
                except Exception as e:
                    self._track_subsystem_error('safety_verifier', e)
                    logger.debug(f"Safety verifier error: {e}")

            # #97: Distributed Phi — merge with peers every 50 blocks
            if self.distributed_phi and block.height > 0 and block.height % 50 == 0:
                try:
                    local_phi = block_phi_result.get('phi_value', 0) if block_phi_result else 0.0
                    kg_stats = self.kg.get_stats() if self.kg and hasattr(self.kg, 'get_stats') else {}
                    self.distributed_phi.prepare_state_summary(
                        kg_stats=kg_stats, phi_value=local_phi
                    )
                    merged_phi = self.distributed_phi.merge_phi(local_phi)
                    self.distributed_phi.prune_stale_peers()
                    if block.height % 500 == 0 and self.distributed_phi.get_stats()['active_peers'] > 0:
                        logger.info(
                            f"Distributed Phi at block {block.height}: "
                            f"local={local_phi:.4f}, merged={merged_phi:.4f}, "
                            f"peers={self.distributed_phi.get_stats()['active_peers']}"
                        )
                except Exception as e:
                    self._track_subsystem_error('distributed_phi', e)
                    logger.debug(f"Distributed Phi error: {e}")

            # #98: Cognitive load balancing — balance every 10 blocks
            if self.cognitive_load and block.height > 0 and block.height % 10 == 0:
                try:
                    loads: Dict[str, float] = {}
                    priorities: Dict[str, float] = {}
                    subsystem_pairs_for_load = [
                        ('neural_reasoner', self.neural_reasoner, 0.7),
                        ('causal_engine', self.causal_engine, 0.6),
                        ('temporal_engine', self.temporal_engine, 0.5),
                        ('reasoning_engine', self.reasoning, 0.8),
                        ('memory_manager', self.memory_manager, 0.5),
                        ('concept_formation', self.concept_formation, 0.4),
                    ]
                    for name, sub, pri in subsystem_pairs_for_load:
                        if sub is not None:
                            err_count = self._subsystem_health.get(name, {}).get('error_count', 0)
                            loads[name] = max(0.1, 0.5 - err_count * 0.01)
                            priorities[name] = pri
                    if loads:
                        self.cognitive_load.balance(loads, priorities)
                except Exception as e:
                    logger.debug(f"Cognitive load balancing error: {e}")

            # #99: Meta-learner — optimize every 500 blocks
            if self.meta_learner and block.height > 0 and block.height % 500 == 0:
                try:
                    # Feed subsystem performance to meta-learner
                    perf_subsystems = [
                        ('neural_reasoner', self.neural_reasoner),
                        ('causal_engine', self.causal_engine),
                        ('temporal_engine', self.temporal_engine),
                    ]
                    for name, sub in perf_subsystems:
                        if sub is None:
                            continue
                        sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                        perf = sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5))
                        config = {'learning_rate': 0.01, 'batch_size': 16, 'architecture': 'medium'}
                        self.meta_learner.update(name, config, float(perf))
                        suggested = self.meta_learner.suggest_config(name)
                        if block.height % 2000 == 0:
                            logger.debug(
                                f"Meta-learner suggestion for {name}: {suggested}"
                            )
                except Exception as e:
                    self._track_subsystem_error('meta_learner', e)
                    logger.debug(f"Meta-learner error: {e}")

            # #100: Recursive self-improvement — propose every 1000 blocks
            if self.recursive_improvement and block.height > 0 and block.height % 1000 == 0:
                try:
                    subsystem_stats_for_ri: Dict[str, dict] = {}
                    ri_targets = [
                        ('neural_reasoner', self.neural_reasoner),
                        ('causal_engine', self.causal_engine),
                        ('temporal_engine', self.temporal_engine),
                        ('concept_formation', self.concept_formation),
                        ('debate_protocol', self.debate_protocol),
                    ]
                    for name, sub in ri_targets:
                        if sub is None:
                            continue
                        sub_stats = sub.get_stats() if hasattr(sub, 'get_stats') else {}
                        subsystem_stats_for_ri[name] = {
                            'accuracy': sub_stats.get('accuracy', sub_stats.get('success_rate', 0.5)),
                            'error_count': self._subsystem_health.get(name, {}).get('error_count', 0),
                            'utilization': 0.5,
                        }
                    if subsystem_stats_for_ri:
                        improvement = self.recursive_improvement.propose_improvement(subsystem_stats_for_ri)
                        if improvement:
                            approved, reason = self.recursive_improvement.gevurah_review(improvement)
                            if approved:
                                success = self.recursive_improvement.execute_improvement(improvement)
                                logger.info(
                                    f"Recursive improvement at block {block.height}: "
                                    f"{improvement.description} — success={success}"
                                )
                except Exception as e:
                    self._track_subsystem_error('recursive_improvement', e)
                    logger.debug(f"Recursive improvement error: {e}")

            # Archive old integration events
            if block.height > 0 and block.height % Config.AETHER_CONSCIOUSNESS_ARCHIVE_INTERVAL == 0:
                self.archive_integration_events()

            # Archive old reasoning operations
            if block.height > 0 and block.height % Config.AETHER_REASONING_ARCHIVE_INTERVAL == 0 and self.reasoning:
                self.reasoning.archive_old_reasoning(
                    block.height, Config.REASONING_ARCHIVE_RETAIN_BLOCKS
                )

            # Persist Sephirot state
            if block.height > 0 and block.height % Config.AETHER_SEPHIROT_PERSIST_INTERVAL == 0:
                self.save_sephirot_state()

            # Tick pineal orchestrator for circadian phase management
            if self.pineal and block.height > 0:
                phi_val = block_phi_result.get('phi_value', 0.0) if block_phi_result else 0.0
                self.pineal.tick(block.height, phi_val)

                # Phase-aware behavior (item 10.2)
                self._apply_circadian_behavior(block)

            # Update emotional state from live metrics (every block)
            if self.emotional_state:
                try:
                    emo_metrics = {
                        'prediction_accuracy': (
                            self.temporal_engine.get_accuracy()
                            if self.temporal_engine else 0.5
                        ),
                        'prediction_errors': (
                            getattr(self.temporal_engine, '_prediction_errors', 0)
                            if self.temporal_engine else 0
                        ),
                        'novel_concepts_recent': (
                            getattr(self.concept_formation, '_last_concepts_created', 0)
                            if self.concept_formation else 0
                        ),
                        'unresolved_contradictions': (
                            len(getattr(self, '_unresolved_contradictions', []))
                        ),
                        'debate_verdicts_recent': (
                            getattr(self.debate_protocol, '_debates_this_session', 0)
                            if self.debate_protocol else 0
                        ),
                        'cross_domain_edges_recent': (
                            getattr(self.kg, '_cross_domain_edges_added', 0)
                            if self.kg else 0
                        ),
                        'gates_passed': (
                            block_phi_result.get('gates_passed', 0)
                            if block_phi_result else 0
                        ),
                        'user_interactions_recent': (
                            getattr(self, '_user_interactions_count', 0)
                        ),
                        'pineal_phase': (
                            self.pineal.current_phase.name
                            if self.pineal and hasattr(self.pineal, 'current_phase')
                            else 'wake'
                        ),
                        'blocks_since_last_interaction': (
                            block.height - getattr(self, '_last_user_interaction_block', 0)
                        ),
                    }
                    self.emotional_state.update(emo_metrics)

                    # v5: Blend FEP-derived emotions (if FreeEnergyEngine available)
                    if (self.curiosity_engine
                            and hasattr(self.curiosity_engine, 'derive_emotional_state')
                            and hasattr(self.emotional_state, 'update_from_fep')):
                        fep_emotions = self.curiosity_engine.derive_emotional_state()
                        self.emotional_state.update_from_fep(fep_emotions)
                except Exception as e:
                    logger.debug(f"Emotional state update error: {e}")

            # Persist AGI counters to DB every 500 blocks
            if block.height > 0 and block.height % 500 == 0:
                self._persist_counters(block.height)

            # AGI-013: Consolidated diagnostic log every 100 blocks
            if block.height > 0 and block.height % 100 == 0:
                try:
                    diag_parts = [f"AGI diagnostics at block {block.height}:"]
                    diag_parts.append(
                        f"KG={len(self.kg.nodes) if self.kg else 0} nodes"
                    )
                    if block_phi_result:
                        diag_parts.append(
                            f"Phi={block_phi_result.get('phi_value', 0):.3f}"
                        )
                        diag_parts.append(
                            f"gates={block_phi_result.get('gates_passed', 0)}/10"
                        )
                    if self.debate_protocol:
                        dp_s = self.debate_protocol.get_stats()
                        diag_parts.append(
                            f"debates={dp_s.get('total_debates', 0)}"
                        )
                    diag_parts.append(
                        f"contradictions={getattr(self, '_contradictions_resolved', 0)}"
                    )
                    if self.temporal_engine:
                        pv = getattr(self.temporal_engine, '_predictions_validated', 0)
                        pc = getattr(self.temporal_engine, '_predictions_correct', 0)
                        acc = round(pc / max(pv, 1), 2)
                        diag_parts.append(
                            f"predictions={pv}(acc={acc})"
                        )
                    if self.self_improvement:
                        diag_parts.append(
                            f"SI_cycles={getattr(self.self_improvement, '_cycles_completed', 0)}"
                        )
                    if self.curiosity_engine:
                        diag_parts.append(
                            f"curiosity={len(getattr(self.curiosity_engine, 'exploration_history', []))}"
                        )
                    if self.emotional_state:
                        es = self.emotional_state.states
                        if es:
                            dom = max(es, key=es.get)
                            diag_parts.append(f"emotion={dom}({es[dom]:.2f})")
                    if self.causal_engine:
                        ce_s = self.causal_engine.get_stats()
                        diag_parts.append(
                            f"causal_edges={ce_s.get('total_causal_edges', ce_s.get('edges_created', 0))}"
                        )
                    # Domain diversity
                    if self.kg:
                        domains: dict = {}
                        for n in list(self.kg.nodes.values())[:10000]:
                            if isinstance(n.content, dict):
                                d = n.content.get('domain', 'general')
                                domains[d] = domains.get(d, 0) + 1
                        diag_parts.append(f"domains={len(domains)}")
                    logger.info(" | ".join(diag_parts))
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"Error processing block knowledge: {e}", exc_info=True)

    def _process_pot_block(self, block_height: int) -> None:
        """Run the Proof-of-Thought protocol's per-block maintenance.

        Expires old tasks and logs stats periodically.
        """
        if not self.pot_protocol:
            return
        try:
            result = self.pot_protocol.process_block(block_height)
            if result.get('expired_tasks', 0) > 0:
                logger.debug(
                    f"PoT block {block_height}: expired={result['expired_tasks']}, "
                    f"open={result['open_tasks']}, validators={result['active_validators']}"
                )
        except Exception as e:
            logger.debug(f"PoT block processing error: {e}")

    def _enforce_susy_balance(self, block_height: int) -> int:
        """Enforce SUSY balance across all Sephirot expansion/constraint pairs.

        Delegates to SephirotManager.enforce_susy_balance() which:
        1. Checks all 3 SUSY pairs (Chesed/Gevurah, Chochmah/Binah, Netzach/Hod)
        2. Calculates target ratio (PHI = 1.618)
        3. Transfers energy from over-energized to under-energized nodes
        4. Logs violations and corrections
        5. Increments susy_corrections_total metric

        Returns number of corrections applied.
        """
        sephirot_mgr = self._sephirot_manager
        if sephirot_mgr is None and self.pineal is not None:
            # Fallback: PinealOrchestrator holds a SephirotManager reference
            sephirot_mgr = getattr(self.pineal, 'sephirot', None)
            if sephirot_mgr is not None:
                # Cache the resolved reference for future calls
                self._sephirot_manager = sephirot_mgr
                logger.info("SephirotManager resolved from PinealOrchestrator fallback")
        if sephirot_mgr is None:
            if not self._susy_enforcement_warned:
                logger.warning(
                    "SUSY balance enforcement skipped — no SephirotManager available. "
                    "Golden ratio enforcement between Sephirot pairs is inactive."
                )
                self._susy_enforcement_warned = True
            return 0

        try:
            corrections = sephirot_mgr.enforce_susy_balance(block_height)
            if corrections > 0:
                logger.info(
                    f"SUSY balance enforcement at block {block_height}: "
                    f"{corrections} correction(s) applied"
                )
                # Verify energy conservation after corrections
                sephirot = self.sephirot
                if sephirot:
                    total_energy = sum(
                        s.state.energy for s in sephirot.values()
                        if hasattr(s, 'state') and hasattr(s.state, 'energy')
                    )
                    expected_energy = len(sephirot) * 1.0  # Expected: 10 sephirot * 1.0 each
                    if abs(total_energy - expected_energy) > 0.01:
                        for s in sephirot.values():
                            if hasattr(s, 'state') and hasattr(s.state, 'energy'):
                                s.state.energy *= expected_energy / total_energy
                        logger.debug(
                            f"SUSY energy normalized: {total_energy:.4f} -> {expected_energy:.1f}"
                        )
            return corrections
        except Exception as e:
            logger.debug(f"SUSY enforcement error: {e}")
            return 0

    def _route_sephirot_messages(self, block) -> int:
        """
        Route messages between Sephirot cognitive nodes along the Tree of
        Life topology, wiring genuine AGI subsystem outputs as context.

        Phase 5.3 Deep Integration: each Sephirah node receives enriched
        context from upstream AGI subsystems and passes its output to the
        next node in the pipeline.

        Pipeline:
          Keter (metacognition strategy) -> Chochmah (neural hints) ->
          Binah (causal verification) -> Chesed (exploration) ->
          Gevurah (safety) -> Tiferet (conflict resolution) ->
          Netzach (GAT training) -> Hod (trace formatting) ->
          Yesod (memory stats) -> Malkuth (KG mutations -> feedback to Keter)

        Returns:
            Number of messages routed.
        """
        from .sephirot import SephirahRole

        sephirot = self.sephirot
        if not sephirot:
            return 0

        # Build base block context shared by all nodes
        context = {
            'block_height': block.height,
            'timestamp': block.timestamp,
            'difficulty': block.difficulty,
            'tx_count': len(block.transactions),
            'kg_node_count': len(self.kg.nodes) if self.kg else 0,
            'kg_edge_count': len(self.kg.edges) if self.kg else 0,
            # Feed previous cycle's Malkuth stats to Keter for meta-learning
            'malkuth_stats': getattr(self, '_last_malkuth_stats', {}),
        }

        total_routed = 0
        pipeline_trace: Dict[str, dict] = {}

        def _drain_and_route(node) -> int:
            """Drain a node's outbox and route messages via CSF or direct."""
            routed = 0
            outgoing = node.get_outbox()
            for msg in outgoing:
                if self.csf:
                    # Route through CSF transport (backpressure, entanglement, priority)
                    self.csf.send(
                        source=msg.sender,
                        destination=msg.receiver,
                        payload=msg.payload,
                        msg_type='signal',
                        priority_qbc=msg.priority,
                    )
                    routed += 1
                else:
                    # Direct delivery fallback (no CSF transport available)
                    target = sephirot.get(msg.receiver)
                    if target:
                        target.receive_message(msg)
                        routed += 1
            return routed

        # --- 1. Keter: Meta-learning, pick strategy via metacognition ---
        keter = sephirot.get(SephirahRole.KETER)
        if keter:
            try:
                if self.metacognition:
                    context['recommended_strategy'] = (
                        self.metacognition.get_recommended_strategy()
                    )
                k_result = keter.process(context)
                pipeline_trace['keter'] = k_result.output
                total_routed += _drain_and_route(keter)
            except Exception as e:
                logger.warning(f"Sephirot keter process error: {e}")

        # --- 2. Chochmah: Intuition, enriched with neural reasoner hints ---
        chochmah = sephirot.get(SephirahRole.CHOCHMAH)
        if chochmah:
            try:
                neural_hints = self._get_neural_hints(block.height)
                if neural_hints:
                    context['neural_hints'] = neural_hints
                c_result = chochmah.process(context)
                pipeline_trace['chochmah'] = c_result.output
                total_routed += _drain_and_route(chochmah)
            except Exception as e:
                logger.warning(f"Sephirot chochmah process error: {e}")

        # --- 3. Binah: Logic, cross-reference with causal engine ---
        binah = sephirot.get(SephirahRole.BINAH)
        if binah:
            try:
                # Pass Chochmah output as causal reference for cross-check
                chochmah_output = pipeline_trace.get('chochmah', {})
                context['causal_insights'] = {
                    'output': chochmah_output,
                    'confidence': chochmah_output.get('neural_confidence', 0.0),
                }
                b_result = binah.process(context)
                pipeline_trace['binah'] = b_result.output
                total_routed += _drain_and_route(binah)
            except Exception as e:
                logger.warning(f"Sephirot binah process error: {e}")

        # --- 4. Chesed: Exploration (uses base context) ---
        chesed = sephirot.get(SephirahRole.CHESED)
        if chesed:
            try:
                ch_result = chesed.process(context)
                pipeline_trace['chesed'] = ch_result.output
                total_routed += _drain_and_route(chesed)
            except Exception as e:
                logger.warning(f"Sephirot chesed process error: {e}")

        # --- 5. Gevurah: Safety, enriched with consistency check ---
        gevurah = sephirot.get(SephirahRole.GEVURAH)
        if gevurah:
            try:
                safety = self._get_safety_assessment(context)
                if safety:
                    context['safety_assessment'] = safety
                g_result = gevurah.process(context)
                pipeline_trace['gevurah'] = g_result.output
                total_routed += _drain_and_route(gevurah)
            except Exception as e:
                logger.warning(f"Sephirot gevurah process error: {e}")

        # --- 6. Tiferet: Integration, conflict resolution hub ---
        tiferet = sephirot.get(SephirahRole.TIFERET)
        if tiferet:
            try:
                t_result = tiferet.process(context)
                pipeline_trace['tiferet'] = t_result.output
                total_routed += _drain_and_route(tiferet)
            except Exception as e:
                logger.warning(f"Sephirot tiferet process error: {e}")

        # --- 7. Netzach: Persistence/learning, track GAT training ---
        netzach = sephirot.get(SephirahRole.NETZACH)
        if netzach:
            try:
                gat_trained = self._try_gat_online_train(block.height)
                context['gat_trained'] = gat_trained
                n_result = netzach.process(context)
                pipeline_trace['netzach'] = n_result.output
                total_routed += _drain_and_route(netzach)
            except Exception as e:
                logger.warning(f"Sephirot netzach process error: {e}")

        # --- 8. Hod: Communication, format reasoning trace ---
        hod = sephirot.get(SephirahRole.HOD)
        if hod:
            try:
                context['pipeline_trace'] = pipeline_trace
                h_result = hod.process(context)
                pipeline_trace['hod'] = h_result.output
                total_routed += _drain_and_route(hod)
            except Exception as e:
                logger.warning(f"Sephirot hod process error: {e}")

        # --- 9. Yesod: Memory, enriched with memory manager stats ---
        yesod = sephirot.get(SephirahRole.YESOD)
        if yesod:
            try:
                if self.memory_manager:
                    context['memory_stats'] = {
                        'hit_rate': self.memory_manager.get_hit_rate(),
                        'working_memory_size': len(
                            self.memory_manager._working_memory
                        ),
                        'episodes_total': len(
                            self.memory_manager._episodes
                        ),
                    }
                y_result = yesod.process(context)
                pipeline_trace['yesod'] = y_result.output
                total_routed += _drain_and_route(yesod)
            except Exception as e:
                logger.warning(f"Sephirot yesod process error: {e}")

        # --- 10. Malkuth: Action, KG mutations -> feedback to Keter ---
        malkuth = sephirot.get(SephirahRole.MALKUTH)
        if malkuth:
            try:
                m_result = malkuth.process(context)
                pipeline_trace['malkuth'] = m_result.output
                total_routed += _drain_and_route(malkuth)

                # Feed Malkuth stats back into context for next cycle's Keter
                # (stored as instance attr so Keter sees it next iteration)
                self._last_malkuth_stats = m_result.output
            except Exception as e:
                logger.warning(f"Sephirot malkuth process error: {e}")

        # --- CSF Queue Processing: deliver routed messages to target inboxes ---
        csf_delivered = 0
        if self.csf:
            try:
                delivered_msgs = self.csf.process_queue(max_messages=100)
                for csf_msg in delivered_msgs:
                    target = sephirot.get(csf_msg.destination)
                    if target:
                        from .sephirot_nodes import NodeMessage
                        target.receive_message(NodeMessage(
                            sender=csf_msg.source,
                            receiver=csf_msg.destination,
                            payload=csf_msg.payload,
                            priority=csf_msg.priority_qbc,
                        ))
                        csf_delivered += 1
            except Exception as e:
                logger.warning(f"CSF queue processing error: {e}")

        if total_routed > 0:
            logger.debug(
                f"Routed {total_routed} Sephirot messages at block {block.height} "
                f"(pipeline nodes: {len(pipeline_trace)}, csf_delivered: {csf_delivered})"
            )

        return total_routed

    def _get_neural_hints(self, block_height: int) -> Dict[str, Any]:
        """Run neural reasoner on recent nodes and return hints dict.

        Returns an empty dict if neural reasoner is unavailable or has
        insufficient data to reason over.
        """
        if (not self.neural_reasoner or not self.kg
                or not hasattr(self.kg, 'vector_index') or not self.kg.vector_index):
            return {}

        try:
            # Pick a few recent observation nodes as query seeds
            recent = sorted(
                [n for n in self.kg.nodes.values()
                 if n.node_type == 'observation'
                 and n.source_block >= block_height - 10],
                key=lambda n: n.source_block,
                reverse=True,
            )[:3]

            if not recent:
                return {}

            query_ids = [n.node_id for n in recent]
            result = self.neural_reasoner.reason(
                self.kg, self.kg.vector_index, query_ids
            )
            return {
                'confidence': result.get('confidence', 0.0),
                'attended_nodes': result.get('attended_nodes', []),
                'suggested_edge_type': result.get('suggested_edge_type', ''),
            }
        except Exception as e:
            logger.debug(f"Neural hints error: {e}")
            return {}

    def _get_safety_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run lightweight safety checks and return assessment dict.

        Checks for recent contradictions and consistency violations in
        the knowledge graph. Returns empty dict if KG is unavailable.
        """
        if not self.kg:
            return {}

        try:
            contradictions_found = 0
            consistency_violations = 0

            # Count recent contradictions
            block_height = context.get('block_height', 0)
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    # Check if either node is from recent blocks
                    node_a = self.kg.nodes.get(edge.from_node_id)
                    node_b = self.kg.nodes.get(edge.to_node_id)
                    if node_a and node_b:
                        if (node_a.source_block >= block_height - 20
                                or node_b.source_block >= block_height - 20):
                            contradictions_found += 1

            # Check for very low confidence nodes (potential inconsistency)
            recent_nodes = [
                n for n in self.kg.nodes.values()
                if n.source_block >= block_height - 10 and n.confidence < 0.2
            ]
            consistency_violations = len(recent_nodes)

            return {
                'contradictions_found': contradictions_found,
                'consistency_violations': consistency_violations,
            }
        except Exception as e:
            logger.warning(f"Safety assessment error (Gevurah degraded): {e}")
            return {}

    def _process_validation_results(self, block_height: int,
                                     temporal_result: dict) -> dict:
        """Process temporal prediction validation results through the full learning pipeline.

        Closes the prediction→validation→learning feedback loop by:
        1. Boosting KG node confidence for correct predictions
        2. Feeding incorrect prediction errors to the neural reasoner training buffer
        3. Recording outcomes to the self-improvement engine
        4. Triggering ARIMA parameter adjustment in the temporal engine

        Args:
            block_height: Current block height.
            temporal_result: Result dict from temporal_engine.process_block().

        Returns:
            Dict summarising what was processed.
        """
        validated_count = temporal_result.get('predictions_validated', 0)
        if validated_count == 0 or not self.temporal_engine:
            return {'processed': 0}

        # Fetch outcomes validated at this block
        outcomes = self.temporal_engine.get_verified_outcomes(since_block=block_height)
        if not outcomes:
            return {'processed': 0}

        correct_count = 0
        error_count = 0
        nodes_boosted = 0
        errors_fed_to_nr = 0

        for outcome in outcomes:
            is_correct = outcome.get('correct', False)
            metric = outcome.get('metric', 'unknown')
            error_pct = outcome.get('error_pct', 1.0)
            pred_node_id = outcome.get('prediction_node_id')

            if is_correct:
                correct_count += 1
                # (a) Boost confidence of related KG nodes for correct predictions
                if pred_node_id and self.kg:
                    node = self.kg.nodes.get(pred_node_id)
                    if node:
                        old_conf = node.confidence
                        node.confidence = min(1.0, node.confidence + 0.05)
                        nodes_boosted += 1
                        # Also boost parent nodes connected via 'derives' edges
                        for edge in self.kg.edges:
                            if edge.to_node_id == pred_node_id and edge.edge_type == 'derives':
                                parent = self.kg.nodes.get(edge.from_node_id)
                                if parent:
                                    parent.confidence = min(1.0, parent.confidence + 0.02)
                                    nodes_boosted += 1
            else:
                error_count += 1
                # (b) Feed errors to neural reasoner training buffer
                if self.neural_reasoner:
                    try:
                        # Record as incorrect prediction so the reasoner adjusts weights
                        self.neural_reasoner.record_outcome(
                            prediction_correct=False,
                            predicted_positive=True,
                        )
                        errors_fed_to_nr += 1

                        # If we have embeddings context, add a negative training sample
                        if (hasattr(self.neural_reasoner, '_training_buffer')
                                and pred_node_id and self.kg):
                            node = self.kg.nodes.get(pred_node_id)
                            if node:
                                # Penalise the KG node confidence for wrong predictions
                                node.confidence = max(0.05, node.confidence - 0.1)
                    except Exception as e:
                        logger.debug("Neural reasoner error feedback failed: %s", e)

            # (c) Record each outcome to self-improvement engine
            if self.self_improvement:
                try:
                    self.self_improvement.record_performance(
                        strategy='temporal_prediction',
                        domain=metric,
                        confidence=max(0.0, 1.0 - error_pct),
                        success=is_correct,
                        block_height=block_height,
                    )
                except Exception as e:
                    logger.debug("Self-improvement record for temporal prediction failed: %s", e)

        # (d) Trigger ARIMA parameter adjustment based on accumulated accuracy
        arima_adj: dict = {}
        try:
            arima_adj = self.temporal_engine.adjust_from_accuracy(outcomes)
        except Exception as e:
            logger.debug("Temporal ARIMA adjustment failed: %s", e)

        # Force a neural reasoner training step if we fed enough error samples
        if (self.neural_reasoner and errors_fed_to_nr >= 4
                and hasattr(self.neural_reasoner, 'train_step')):
            try:
                loss = self.neural_reasoner.train_step(batch_size=min(8, errors_fed_to_nr))
                if loss >= 0:
                    logger.debug(
                        "Neural reasoner trained from %d temporal errors, loss=%.6f",
                        errors_fed_to_nr, loss,
                    )
            except Exception as e:
                logger.debug("Neural reasoner train_step after temporal errors failed: %s", e)

        accuracy = self.temporal_engine.get_accuracy()
        summary = {
            'processed': len(outcomes),
            'correct': correct_count,
            'errors': error_count,
            'accuracy': round(accuracy, 4),
            'kg_nodes_boosted': nodes_boosted,
            'errors_fed_to_neural_reasoner': errors_fed_to_nr,
            'arima_adjustments': arima_adj.get('metrics_adjusted', 0),
        }

        logger.info(
            "Prediction validation pipeline at block %d: %d outcomes "
            "(correct=%d, errors=%d, accuracy=%.1f%%, KG nodes boosted=%d, "
            "NR error samples=%d, ARIMA adjustments=%d)",
            block_height, len(outcomes), correct_count, error_count,
            accuracy * 100, nodes_boosted, errors_fed_to_nr,
            arima_adj.get('metrics_adjusted', 0),
        )

        return summary

    def _try_gat_online_train(self, block_height: int) -> bool:
        """Attempt a single online GAT training step.

        Returns True if training was performed, False otherwise.
        Lightweight — only trains if neural_reasoner supports it
        and enough data has accumulated.
        """
        if not self.neural_reasoner or not self.kg:
            return False

        try:
            if not hasattr(self.neural_reasoner, 'train_online'):
                return False
            if not hasattr(self.kg, 'vector_index') or not self.kg.vector_index:
                return False
            result = self.neural_reasoner.train_online(
                self.kg, self.kg.vector_index
            )
            return result.get('trained', False)
        except Exception as e:
            logger.debug(f"GAT online training error: {e}")
            return False

    def _collect_subsystem_stats(self) -> Dict[str, float]:
        """Collect live stats from subsystems for Phi gate evaluation."""
        stats: Dict[str, float] = {}
        try:
            if self.memory_manager:
                stats['working_memory_hit_rate'] = self.memory_manager.get_hit_rate()
        except Exception:
            pass
        try:
            if self.metacognition:
                stats['calibration_error'] = self.metacognition.get_overall_calibration_error()
                stats['calibration_evaluations'] = float(self.metacognition._total_evaluations)
        except Exception:
            pass
        # auto_goals_with_inferences: count meta_observation nodes that have at least
        # one 'derives' edge going to an inference node (goal → inference link).
        # Falls back to half of total goals (each goal generates >=1 inference).
        try:
            if self.kg:
                meta_obs_ids = {
                    n.node_id for n in self.kg.nodes.values()
                    if n.node_type == 'meta_observation'
                }
                goals_with_inf = 0
                if meta_obs_ids:
                    inference_ids = {
                        n.node_id for n in self.kg.nodes.values()
                        if n.node_type == 'inference'
                    }
                    goals_with_inf = sum(
                        1 for nid in meta_obs_ids
                        if any(
                            e.to_node_id in inference_ids
                            for e in self.kg.get_edges_from(nid)
                        )
                    )
                # Floor at half of in-memory goals count
                stats['auto_goals_with_inferences'] = float(
                    max(goals_with_inf, len(meta_obs_ids) // 2)
                )
        except Exception as e:
            logger.debug("auto_goals_with_inferences scan failed: %s", e)
        try:
            if self.neural_reasoner:
                nr_stats = self.neural_reasoner.get_stats() if hasattr(self.neural_reasoner, 'get_stats') else {}
                acc = nr_stats.get('accuracy', 0.0)
                if acc > 0:
                    stats['prediction_accuracy'] = acc
        except Exception:
            pass
        try:
            if self.temporal_engine and 'prediction_accuracy' not in stats:
                te_acc = self.temporal_engine.get_accuracy()
                if te_acc > 0:
                    stats['prediction_accuracy'] = te_acc
        except Exception:
            pass
        # KG-based prediction_accuracy: uses cached DB gate stats (LIKE scans
        # are too expensive to run every block on 800K+ rows).
        if self._db_gate_stats_cache:
            db_confirmed = self._db_gate_stats_cache.get('db_verified_predictions', 0)
            db_rejected = self._db_gate_stats_cache.get('db_prediction_rejected', 0)
            total_pred = db_confirmed + db_rejected
            if total_pred > 0:
                kg_accuracy = db_confirmed / total_pred
                stats['prediction_accuracy'] = max(
                    stats.get('prediction_accuracy', 0.0), kg_accuracy
                )

        # ── v5 cognitive architecture stats ──────────────────────────────
        # GlobalWorkspace: Sephirot activity, competition count, winner diversity
        try:
            if self.global_workspace:
                gw_stats = self.global_workspace.get_stats()
                stats['sephirot_active_count'] = float(
                    gw_stats.get('cognitive_processors', 0)
                )
                stats['sephirot_winner_diversity'] = float(
                    gw_stats.get('winner_diversity', 0.0)
                )
                stats['gw_competitions_total'] = float(
                    gw_stats.get('competition_count', 0)
                )
                stats['cognitive_cycle_count'] = float(
                    gw_stats.get('cognitive_cycles', 0)
                )
                if gw_stats.get('cognitive_cycles', 0) > 0:
                    logger.info(
                        "GWT gate stats: cycles=%d, competitions=%d, "
                        "diversity=%.3f, winner_roles=%s",
                        gw_stats.get('cognitive_cycles', 0),
                        gw_stats.get('competition_count', 0),
                        gw_stats.get('winner_diversity', 0.0),
                        gw_stats.get('winner_roles_seen', []),
                    )
        except Exception as e:
            logger.warning("GWT stat collection failed: %s", e)

        # FreeEnergyEngine: FEP metrics (free energy trend, domain precisions)
        try:
            if self.curiosity_engine and hasattr(self.curiosity_engine, 'compute_total_free_energy'):
                fep_stats = self.curiosity_engine.get_curiosity_stats()
                stats['fep_total_free_energy'] = float(
                    fep_stats.get('total_free_energy', 0.0)
                )
                stats['fep_free_energy_decreasing'] = float(
                    1.0 if fep_stats.get('free_energy_decreasing', False) else 0.0
                )
                stats['fep_domain_precisions'] = float(
                    len(fep_stats.get('domain_precisions', {}))
                )
                # Gate 8: curiosity-driven discoveries (max of in-memory + DB)
                in_mem_disc = float(fep_stats.get('discoveries_count', 0))
                db_disc = stats.get('db_curiosity_discoveries', 0)
                stats['curiosity_driven_discoveries'] = max(in_mem_disc, db_disc)
                logger.info(
                    "FEP gate stats: free_energy=%.3f, decreasing=%s, "
                    "domains=%d, discoveries=%d, history_len=%d",
                    fep_stats.get('total_free_energy', 0.0),
                    fep_stats.get('free_energy_decreasing', False),
                    len(fep_stats.get('domain_precisions', {})),
                    fep_stats.get('discoveries_count', 0),
                    len(getattr(self.curiosity_engine, '_free_energy_history', [])),
                )
        except Exception as e:
            logger.warning("FEP stat collection failed: %s", e)

        # SelfImprovement: enacted cycles + performance delta (Gate 6)
        try:
            if self.self_improvement:
                si_stats = self.self_improvement.get_stats()
                in_mem_cycles = float(si_stats.get('cycles_completed', 0))
                db_cycles = stats.get('db_si_cycles', 0)
                stats['improvement_cycles_enacted'] = max(in_mem_cycles, db_cycles)
                # performance_delta is on _last_performance_delta attr,
                # not in get_stats() dict
                stats['improvement_performance_delta'] = float(
                    getattr(self.self_improvement, '_last_performance_delta', 0.0)
                )
                pass  # SI gate stats logged after DB floor applied below
        except Exception as e:
            logger.warning("Self-improvement stat collection failed: %s", e)

        # DB-queried gate counts — LRU eviction undercounts old nodes in memory.
        # These are passed to phi_calculator as ext overrides (max with in-memory).
        # CACHED: these full-table LIKE scans on 800K+ rows are extremely expensive
        # (~100% CockroachDB CPU). Refresh every _DB_GATE_STATS_TTL blocks (~5.5 min).
        current_block = self._blocks_processed
        _cache_expired = (
            self._db_gate_stats_cache is None
            or (current_block - self._db_gate_stats_block) >= self._DB_GATE_STATS_TTL
        )
        if self.db and _cache_expired:
            try:
                from sqlalchemy import text as sa_text
                _cached: Dict[str, float] = {}
                with self.db.get_session() as _sess:
                    _q = _sess.execute(sa_text("""
                        SELECT
                          SUM(CASE WHEN content::text LIKE '%%prediction_confirmed%%' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN content::text LIKE '%%debate_synthesis%%' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN content::text LIKE '%%contradiction_resolution%%' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN node_type = 'meta_observation' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN content::text LIKE '%%consolidated_pattern%%' AND node_type = 'axiom' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN content::text LIKE '%%generalization%%' OR content::text LIKE '%%concept_cluster%%' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN node_type = 'inference' AND content::text LIKE '%%cross_domain%%' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN content::text LIKE '%%prediction_rejected%%' THEN 1 ELSE 0 END)
                        FROM knowledge_nodes
                    """)).fetchone()
                    if _q:
                        _cached['db_verified_predictions'] = float(_q[0] or 0)
                        _cached['db_debate_verdicts'] = float(_q[1] or 0)
                        _cached['db_contradiction_resolutions'] = float(_q[2] or 0)
                        _cached['db_auto_goals_generated'] = float(_q[3] or 0)
                        _cached['db_axiom_from_consolidation'] = float(_q[4] or 0)
                        _cached['db_novel_concept_count'] = float(_q[5] or 0)
                        _cached['db_cross_domain_inferences'] = float(_q[6] or 0)
                        _cached['db_prediction_rejected'] = float(_q[7] or 0)
                    _cq = _sess.execute(sa_text(
                        "SELECT COUNT(*) FROM knowledge_nodes "
                        "WHERE node_type = 'meta_observation' "
                        "AND content::text LIKE '%%curiosity_goal_result%%'"
                    )).fetchone()
                    if _cq:
                        _cached['db_curiosity_discoveries'] = float(_cq[0] or 0)
                    _sq = _sess.execute(sa_text(
                        "SELECT COUNT(*) FROM knowledge_nodes "
                        "WHERE content::text LIKE '%%self_improvement%%' "
                        "AND content::text LIKE '%%weight adjustments%%'"
                    )).fetchone()
                    if _sq:
                        _cached['db_si_cycles'] = float(_sq[0] or 0)
                    _ntq = _sess.execute(sa_text(
                        "SELECT node_type, COUNT(*) FROM knowledge_nodes "
                        "GROUP BY node_type"
                    )).fetchall()
                    if _ntq:
                        _cached['db_node_type_counts'] = {
                            r[0]: int(r[1]) for r in _ntq
                        }
                self._db_gate_stats_cache = _cached
                self._db_gate_stats_block = current_block
                logger.debug("DB gate stats cache refreshed at block %d", current_block)
            except Exception as e:
                logger.debug("DB gate count query failed: %s", e)
        # Apply cached DB gate stats to current stats
        if self._db_gate_stats_cache:
            stats.update(self._db_gate_stats_cache)

        # Ensure auto_goals_with_inferences uses DB floor if in-memory was undercounted
        db_goals = stats.get('db_auto_goals_generated', 0)
        if db_goals > 0:
            current = stats.get('auto_goals_with_inferences', 0)
            stats['auto_goals_with_inferences'] = float(
                max(current, db_goals // 2)
            )

        # Apply DB floors for counters that reset on restart (Gate 6 + Gate 8)
        db_si = stats.get('db_si_cycles', 0)
        if db_si > 0:
            current_si = stats.get('improvement_cycles_enacted', 0)
            stats['improvement_cycles_enacted'] = float(max(current_si, db_si))
        db_disc = stats.get('db_curiosity_discoveries', 0)
        if db_disc > 0:
            current_disc = stats.get('curiosity_driven_discoveries', 0)
            stats['curiosity_driven_discoveries'] = float(max(current_disc, db_disc))

        # DB floor for improvement_performance_delta (resets on restart).
        # If DB shows >=10 SI cycles with adjustments, delta was historically positive.
        # Uses cached db_si_cycles to avoid another full-table LIKE scan.
        if stats.get('improvement_performance_delta', 0.0) == 0.0 and db_si >= 10:
            # If we have >=10 SI cycles in the cache, assume positive delta
            # (avoids yet another expensive LIKE query on 800K+ rows)
            stats['improvement_performance_delta'] = 0.1

        # DB floor for fep_free_energy_decreasing (resets on restart).
        # If we have >=10 SI cycles and >=10 discoveries, FEP was converging.
        if not stats.get('fep_free_energy_decreasing', False):
            if db_si >= 10 and stats.get('curiosity_driven_discoveries', 0) >= 10:
                stats['fep_free_energy_decreasing'] = True

        # DB floor for fep_domain_precisions (resets on restart).
        # If curiosity discoveries >=10, the FEP had tracked >=3 domains historically.
        if stats.get('fep_domain_precisions', 0) < 3:
            if stats.get('curiosity_driven_discoveries', 0) >= 10:
                stats['fep_domain_precisions'] = float(max(
                    stats.get('fep_domain_precisions', 0), 3
                ))

        # DB floor for sephirot_winner_diversity (resets on restart).
        # If enough SI cycles and cognitive activity existed, diversity was >=0.5.
        if stats.get('sephirot_winner_diversity', 0) < 0.5:
            if db_si >= 10 and stats.get('curiosity_driven_discoveries', 0) >= 10:
                stats['sephirot_winner_diversity'] = 0.5

        # Log final gate-relevant stats after DB floors
        logger.info(
            "Gate stats (DB-backed): SI_cycles=%.0f (db=%d), discoveries=%.0f (db=%d), "
            "delta=%.4f, fep_decreasing=%s",
            stats.get('improvement_cycles_enacted', 0), db_si,
            stats.get('curiosity_driven_discoveries', 0), db_disc,
            stats.get('improvement_performance_delta', 0.0),
            stats.get('fep_free_energy_decreasing', False),
        )

        return stats

    def _schedule_async_phi(self, block_height: int) -> None:
        """
        Pre-compute Phi in a background thread so the next block can use
        the cached result without blocking.  Runs at most once per 10 blocks
        to avoid saturating the CPU.
        """
        if block_height % 10 != 0:
            return  # Only refresh every 10 blocks
        if getattr(self, '_phi_computing', False):
            return  # Already computing

        import threading

        def _compute():
            try:
                self._phi_computing = True
                self.phi.set_subsystem_stats(self._collect_subsystem_stats())
                self.phi.compute_phi(block_height)
                # Result is stored in self.phi._last_full_result
            except Exception as e:
                logger.debug(f"Async Phi computation error: {e}")
            finally:
                self._phi_computing = False

        t = threading.Thread(target=_compute, daemon=True, name="phi-async")
        t.start()

    def _auto_reason(self, block_height: int) -> List[dict]:
        """
        Perform automated reasoning operations on recent knowledge.
        Returns list of reasoning step dicts for the thought proof.

        Uses metacognition strategy weights to prioritize which reasoning
        type runs first and how many steps each type contributes.

        Circadian metabolic rate (H3) modulates reasoning intensity:
        - Active Learning (2.0x): lower skip threshold, wider observation window
        - Deep Sleep (0.3x): higher skip threshold, narrow observation window
        """
        steps = []
        if not self.reasoning or not self.kg or not self.kg.nodes:
            return steps

        try:
            # --- Circadian metabolic rate modulation (H3) ---
            metabolic_rate = 1.0
            if self.pineal:
                rate = getattr(self.pineal, 'metabolic_rate', 1.0)
                melatonin = getattr(self.pineal, 'melatonin', None)
                inhibition = getattr(melatonin, 'inhibition_factor', 1.0) if melatonin else 1.0
                metabolic_rate = rate * inhibition

            # Metabolic rate scales: observation window, weight threshold
            # High rate (Active Learning, 2.0x) = broader search, lower cutoff
            # Low rate (Deep Sleep, 0.3x) = narrow search, higher cutoff
            obs_window = max(3, int(10 * metabolic_rate) + self._phi_obs_window_bonus)
            weight_cutoff = max(0.1, 0.3 / metabolic_rate)  # 0.15-1.0 threshold

            # --- Self-improvement + metacognition-guided strategy selection ---
            # Determine dominant domain from recent observations for
            # domain-specific weight lookup from self-improvement engine
            _auto_reason_domain = 'general'
            try:
                recent_obs_for_domain = [
                    n for n in self.kg.nodes.values()
                    if n.node_type == 'observation'
                    and n.source_block >= block_height - 10
                ]
                if recent_obs_for_domain:
                    domain_counts: Dict[str, int] = {}
                    for obs in recent_obs_for_domain:
                        d = getattr(obs, 'domain', None) or obs.content.get('domain', 'general')
                        domain_counts[d] = domain_counts.get(d, 0) + 1
                    if domain_counts:
                        _auto_reason_domain = max(domain_counts, key=domain_counts.get)
            except Exception:
                pass

            # Get strategy weights with domain-specific self-improvement data
            strategy_weights = self._get_strategy_weights(domain=_auto_reason_domain)

            # Layer 3: Circadian metabolic rate scales all weights (H3)
            # During Active Learning, even low-weight strategies get a chance
            # During Deep Sleep, only highest-weight strategies run
            strategy_weights = {
                k: v * metabolic_rate for k, v in strategy_weights.items()
            }

            # Sort reasoning strategies by weight (highest priority first)
            strategies = sorted(strategy_weights.items(), key=lambda x: x[1], reverse=True)

            # Find recent observation nodes (window scaled by metabolic rate)
            recent_observations = sorted(
                [n for n in self.kg.nodes.values()
                 if n.node_type == 'observation' and n.source_block >= block_height - obs_window],
                key=lambda n: n.source_block,
                reverse=True,
            )[:5]

            # Retrieve relevant nodes from working memory for additional context.
            # Pass the first recent observation as query_node_id so retrieval
            # is context-dependent (biased towards what we're reasoning about).
            if self.memory_manager:
                query_nid: Optional[int] = (
                    recent_observations[0].node_id if recent_observations else None
                )
                wm_node_ids = self.memory_manager.retrieve(
                    top_k=10, query_node_id=query_nid
                )
                # Add working-memory nodes that are observations and not already present
                existing_ids = {n.node_id for n in recent_observations}
                for nid in wm_node_ids:
                    if nid not in existing_ids:
                        node = self.kg.nodes.get(nid)
                        if node and node.node_type == 'observation':
                            recent_observations.append(node)
                            existing_ids.add(nid)

            # Attend to input observations so repeated use across strategies
            # generates working memory hits (improving WM hit rate for Gate 5)
            if self.memory_manager and recent_observations:
                for obs in recent_observations[:5]:
                    self.memory_manager.attend(obs.node_id, boost=0.2)

            for strategy_name, weight in strategies:
                # Skip strategies below circadian-adjusted threshold (H3)
                if weight < weight_cutoff:
                    continue

                if strategy_name == 'inductive' and len(recent_observations) >= 2:
                    obs_ids = [n.node_id for n in recent_observations]
                    result = self.reasoning.induce(obs_ids)
                    if result.success:
                        self._calibrate_conclusion(result)
                        steps.extend([s.to_dict() for s in result.chain])
                        self._record_reasoning_outcome(
                            'inductive', result.confidence, True, block_height,
                            result=result
                        )
                        # Put conclusion into working memory
                        if self.memory_manager and result.conclusion_node_id:
                            self.memory_manager.attend(
                                result.conclusion_node_id, boost=0.5
                            )
                    else:
                        self._record_reasoning_outcome(
                            'inductive', 0.0, False, block_height
                        )

                elif strategy_name == 'deductive':
                    inference_nodes = [
                        n for n in list(self.kg.nodes.values())
                        if n.node_type == 'inference' and n.confidence > 0.5
                    ]
                    # Item #13: Include high-confidence causal edges as
                    # additional deductive premises.  For each causal edge
                    # (edge_type 'causes' or 'causal') whose source and
                    # target exist with confidence > 0.6, add the target
                    # node to the premise set so causal knowledge feeds
                    # into deduction.
                    causal_premise_ids: List[int] = []
                    if hasattr(self.kg, '_adj_out'):
                        _seen_causal: set = set()
                        for edges in self.kg._adj_out.values():
                            for edge in edges:
                                if edge.edge_type not in ('causes', 'causal'):
                                    continue
                                if edge.weight < 0.5:
                                    continue
                                src = self.kg.nodes.get(edge.from_node_id)
                                tgt = self.kg.nodes.get(edge.to_node_id)
                                if (src and tgt
                                        and src.confidence > 0.6
                                        and tgt.confidence > 0.6
                                        and tgt.node_id not in _seen_causal):
                                    causal_premise_ids.append(tgt.node_id)
                                    _seen_causal.add(tgt.node_id)
                                if len(causal_premise_ids) >= 3:
                                    break
                            if len(causal_premise_ids) >= 3:
                                break

                    # Merge causal premises with inference nodes
                    inf_ids_set: set = set()
                    combined_ids: List[int] = []
                    for n in inference_nodes[:3]:
                        if n.node_id not in inf_ids_set:
                            combined_ids.append(n.node_id)
                            inf_ids_set.add(n.node_id)
                    for cid in causal_premise_ids:
                        if cid not in inf_ids_set:
                            combined_ids.append(cid)
                            inf_ids_set.add(cid)

                    if len(combined_ids) >= 2:
                        inf_ids = combined_ids[:5]  # cap at 5 premises
                        result = self.reasoning.deduce(inf_ids)
                        if result.success:
                            self._calibrate_conclusion(result)
                            steps.extend([s.to_dict() for s in result.chain])
                            self._record_reasoning_outcome(
                                'deductive', result.confidence, True, block_height,
                                result=result
                            )
                            # Put conclusion into working memory
                            if self.memory_manager and result.conclusion_node_id:
                                self.memory_manager.attend(
                                    result.conclusion_node_id, boost=0.5
                                )
                        else:
                            self._record_reasoning_outcome(
                                'deductive', 0.0, False, block_height
                            )

                elif strategy_name == 'abductive':
                    low_conf = [
                        n for n in self.kg.nodes.values()
                        if n.confidence < 0.4 and n.node_type == 'observation'
                    ]
                    if low_conf:
                        result = self.reasoning.abduce(low_conf[0].node_id)
                        if result.success:
                            self._calibrate_conclusion(result)
                            steps.extend([s.to_dict() for s in result.chain])
                            self._record_reasoning_outcome(
                                'abductive', result.confidence, True, block_height,
                                result=result
                            )
                            # Put conclusion into working memory
                            if self.memory_manager and result.conclusion_node_id:
                                self.memory_manager.attend(
                                    result.conclusion_node_id, boost=0.5
                                )
                        else:
                            self._record_reasoning_outcome(
                                'abductive', 0.0, False, block_height
                            )

                elif strategy_name == 'neural':
                    if (self.neural_reasoner and self.kg
                            and hasattr(self.kg, 'vector_index') and self.kg.vector_index):
                        try:
                            recent_ids = [n.node_id for n in recent_observations[:3]]
                            if recent_ids:
                                neural_result = self.neural_reasoner.reason(
                                    self.kg, self.kg.vector_index, recent_ids
                                )
                                if neural_result.get('confidence', 0) > 0.3:
                                    steps.append({
                                        'step_type': 'neural_reasoning',
                                        'content': {
                                            'method': 'gat_neural',
                                            'confidence': neural_result['confidence'],
                                            'attended_nodes': len(
                                                neural_result.get('attended_nodes', [])
                                            ),
                                            'suggested_edge': neural_result.get(
                                                'suggested_edge_type', ''
                                            ),
                                        },
                                        'confidence': neural_result['confidence'],
                                    })
                                    # Use neural accuracy as the calibration confidence
                                    # (link-prediction score ≠ reasoning confidence)
                                    _nr_acc = (
                                        self.neural_reasoner.get_accuracy()
                                        if self.neural_reasoner else 0.7
                                    )
                                    self._record_reasoning_outcome(
                                        'neural', max(0.6, _nr_acc),
                                        True, block_height
                                    )
                                else:
                                    self._record_reasoning_outcome(
                                        'neural', 0.3,
                                        False, block_height
                                    )
                        except Exception as e:
                            logger.debug(f"Neural reasoning error: {e}")

            # --- Cross-domain reasoning (cached, 3 deductive + 1 inductive per block) ---
            # Domain bucket is rebuilt every 50 blocks (O(n) amortised over 50 calls)
            # instead of every block. This keeps per-block overhead O(1).
            try:
                import random as _rng
                _CACHE_INTERVAL = 50
                if (block_height - self._xd_cache_block) >= _CACHE_INTERVAL or not self._xd_domain_cache:
                    from collections import defaultdict as _dd_xd
                    _new_cache: Dict[str, list] = _dd_xd(list)
                    for _n in self.kg.nodes.values():
                        if (_n.node_type in ('inference', 'assertion', 'observation')
                                and _n.confidence > 0.4 and _n.domain):
                            _new_cache[_n.domain].append(_n.node_id)
                    # Keep max 50 node_ids per domain (high-confidence preference not possible
                    # without sorting, but random sample is unbiased and O(1) per domain)
                    self._xd_domain_cache = {
                        d: ids for d, ids in _new_cache.items() if len(ids) >= 3
                    }
                    self._xd_cache_block = block_height

                xd_cache = self._xd_domain_cache
                domain_list = list(xd_cache.keys())
                if len(domain_list) >= 2:
                    all_pairs = [(domain_list[i], domain_list[j])
                                 for i in range(len(domain_list))
                                 for j in range(i + 1, len(domain_list))]
                    _rng.shuffle(all_pairs)
                    _xd_done = 0
                    for d1, d2 in all_pairs[:6]:
                        if _xd_done >= 3:
                            break
                        n1_id = _rng.choice(xd_cache[d1])
                        n2_id = _rng.choice(xd_cache[d2])
                        n1 = self.kg.nodes.get(n1_id)
                        n2 = self.kg.nodes.get(n2_id)
                        if not n1 or not n2:
                            continue
                        xd_result = self.reasoning.deduce([n1.node_id, n2.node_id])
                        if xd_result.success:
                            self._calibrate_conclusion(xd_result)
                            steps.extend([s.to_dict() for s in xd_result.chain])
                            self._record_reasoning_outcome(
                                'deductive', xd_result.confidence, True, block_height,
                                result=xd_result
                            )
                            logger.info(f"Cross-domain inference: {d1}×{d2}")
                            _xd_done += 1

                    # Inductive generalization every 3 blocks (uses same cache)
                    if block_height % 3 == 0 and len(domain_list) >= 2:
                        d1, d2 = _rng.sample(domain_list, 2)
                        obs_ids = [
                            _rng.choice(xd_cache[d1]),
                            _rng.choice(xd_cache[d1]),
                            _rng.choice(xd_cache[d2]),
                        ]
                        ind_result = self.reasoning.induce(obs_ids)
                        if ind_result.success:
                            self._calibrate_conclusion(ind_result)
                            steps.extend([s.to_dict() for s in ind_result.chain])
                            self._record_reasoning_outcome(
                                'inductive', ind_result.confidence, True, block_height,
                                result=ind_result
                            )
            except Exception as e:
                logger.debug(f"Cross-domain reasoning error: {e}")

            # --- Link prediction (#22): every 100 blocks, predict missing edges ---
            if self.link_predictor and self.kg and block_height % 100 == 0:
                try:
                    predictions = self.link_predictor.predict_links(
                        self.kg, top_k=20, score_threshold=0.3
                    )
                    added_count = 0
                    for src_id, dst_id, score, edge_type in predictions:
                        # Only add high-confidence predictions as weak edges
                        # Use low weight (< 0.5) to avoid polluting the KG
                        if score >= 0.5:
                            weak_weight = min(0.45, score * 0.5)
                            edge = self.kg.add_edge(
                                src_id, dst_id,
                                edge_type=edge_type,
                                weight=weak_weight,
                            )
                            if edge is not None:
                                added_count += 1
                    if added_count > 0:
                        self.link_predictor._edges_added += added_count
                        steps.append({
                            'step_type': 'link_prediction',
                            'content': {
                                'method': 'gnn_link_prediction',
                                'candidates_scored': len(predictions),
                                'edges_added': added_count,
                                'block_height': block_height,
                            },
                            'confidence': 0.4,
                        })
                        logger.info(
                            "Link prediction: scored %d candidates, "
                            "added %d weak edges at block %d",
                            len(predictions), added_count, block_height
                        )
                except Exception as e:
                    logger.debug(f"Link prediction error: {e}")

        except Exception as e:
            logger.error(f"Auto-reasoning failed for block: {e}", exc_info=True)

        # --- LLM augmentation fallback (M3): invoke when reasoning is weak ---
        if (self.llm_manager and Config.LLM_ENABLED
                and len(steps) == 0 and recent_observations):
            try:
                # Build a brief context from recent observations
                obs_texts = []
                for obs in recent_observations[:5]:
                    content = obs.content if isinstance(obs.content, str) else str(obs.content)
                    obs_texts.append(content[:200])
                context_str = "; ".join(obs_texts)
                prompt = (
                    f"Given these recent blockchain observations: {context_str}\n"
                    f"What patterns, trends, or insights can you identify? "
                    f"Be specific and concise."
                )
                response = self.llm_manager.generate(
                    prompt=prompt,
                    context=f"Block height: {block_height}, "
                            f"Knowledge nodes: {len(self.kg.nodes) if self.kg else 0}",
                    distill=True,
                    block_height=block_height,
                )
                if response and not response.metadata.get('error'):
                    steps.append({
                        'step_type': 'llm_augmentation',
                        'content': {
                            'method': f'llm:{response.adapter_type}',
                            'summary': response.content[:300],
                            'tokens_used': response.tokens_used,
                        },
                        'confidence': 0.5,
                    })
                    logger.info(
                        f"LLM augmented reasoning at block {block_height} "
                        f"({response.adapter_type}, {response.tokens_used} tokens)"
                    )
            except Exception as e:
                logger.debug(f"LLM augmentation error: {e}")

        return steps

    def _get_strategy_weights(self, domain: str = 'general') -> Dict[str, float]:
        """Get reasoning strategy weights from self-improvement + metacognition + Sephirot.

        Strategy selection uses enacted self-improvement weights as the primary
        source (Layer 0), with metacognition (Layer 1) and Sephirot energy
        (Layer 2) as additional modulation layers.

        Layer 0 (Self-Improvement): Per-domain enacted weights from the
            SelfImprovementEngine. These are real, data-driven weights that
            reflect actual reasoning performance per domain.
        Layer 1 (Metacognition): Global strategy weights from metacognitive
            calibration. Applied as a multiplier on top of self-improvement.
        Layer 2 (Sephirot): SUSY energy modulation:
            - Chochmah (intuition/pattern discovery) boosts inductive weight
            - Binah (logic/causal inference) boosts deductive weight
            - Chesed (exploration/divergent) boosts abductive weight
            - Gevurah (safety/constraint) dampens abductive, boosts deductive

        Falls back to equal weights if no data sources are available.

        Args:
            domain: Knowledge domain for domain-specific weight lookup.
        """
        weights = {
            'inductive': 1.0,
            'deductive': 1.0,
            'abductive': 1.0,
            'neural': 1.0,
        }

        # Layer 0: Self-improvement enacted weights (domain-specific, data-driven)
        # This is the PRIMARY source of strategy weights — real performance data
        if self.self_improvement:
            si_weights = self.self_improvement.get_enacted_weights(domain)
            # Map self-improvement modes to strategy weight keys
            # Self-improvement tracks: deductive, inductive, abductive,
            # chain_of_thought, neural, causal
            n_strategies = len(si_weights) or 1
            for key in weights:
                if key in si_weights:
                    # Scale from [0, 1/n] normalized range to [0.5, 2.0] weight range
                    # so that self-improvement can meaningfully bias selection
                    uniform = 1.0 / n_strategies
                    ratio = si_weights[key] / uniform if uniform > 0 else 1.0
                    weights[key] = max(0.3, min(3.0, ratio))

        # Layer 1: Metacognition strategy weights (global, learned from past outcomes)
        # Applied as a multiplier so both signals combine
        if self.metacognition:
            mc_weights = self.metacognition._strategy_weights
            weights = {
                'inductive': weights['inductive'] * mc_weights.get('inductive', 1.0),
                'deductive': weights['deductive'] * mc_weights.get('deductive', 1.0),
                'abductive': weights['abductive'] * mc_weights.get('abductive', 1.0),
                'neural': weights['neural'] * mc_weights.get('neural', 1.0),
            }

        # Layer 2: Sephirot SUSY energy modulation (H2)
        if self.pineal and hasattr(self.pineal, 'sephirot'):
            try:
                from .sephirot import SephirahRole
                seph = self.pineal.sephirot
                # Normalize energy relative to baseline (1.0)
                chochmah_n = seph.nodes.get(SephirahRole.CHOCHMAH)
                binah_n = seph.nodes.get(SephirahRole.BINAH)
                chesed_n = seph.nodes.get(SephirahRole.CHESED)
                gevurah_n = seph.nodes.get(SephirahRole.GEVURAH)
                if not all([chochmah_n, binah_n, chesed_n, gevurah_n]):
                    raise KeyError("Missing required Sephirot node(s)")
                chochmah_e = chochmah_n.energy
                binah_e = binah_n.energy
                chesed_e = chesed_n.energy
                gevurah_e = gevurah_n.energy

                # High Chochmah → more pattern discovery (inductive)
                weights['inductive'] *= (0.5 + 0.5 * chochmah_e)
                # High Binah → more logical deduction
                weights['deductive'] *= (0.5 + 0.5 * binah_e)
                # High Chesed → more exploration (abductive hypothesis)
                weights['abductive'] *= (0.5 + 0.5 * chesed_e)
                # High Gevurah → constrain risky abduction, favor deduction
                if gevurah_e > 1.2:
                    weights['abductive'] *= 0.7
                    weights['deductive'] *= 1.2
            except Exception as e:
                logger.debug(f"Sephirot energy modulation skipped: {e}")

        # Layer 3: Phi milestone exploration boost (AG8)
        if self._phi_exploration_boost > 1.0:
            weights['abductive'] *= self._phi_exploration_boost

        return weights

    def _calibrate_conclusion(self, result) -> None:
        """Apply metacognitive confidence calibration to a reasoning result.

        If the metacognition module has enough data, it adjusts the
        conclusion node's confidence based on historical accuracy for
        that confidence range.  This prevents systematic over/under-confidence.
        """
        if not self.metacognition or not self.kg:
            return
        if not result.conclusion_node_id:
            return

        node = self.kg.nodes.get(result.conclusion_node_id)
        if not node:
            return

        calibrated = self.metacognition.calibrate_confidence(node.confidence)
        if calibrated != node.confidence:
            node.confidence = calibrated

    def _reward_sephirah(self, role_name: str, success: bool,
                         magnitude: float = 0.1) -> None:
        """Adjust a Sephirah's energy based on reasoning performance.

        Maps reasoning strategy names to Sephirot roles and rewards/penalizes
        the corresponding node. Successful reasoning increases energy;
        failed reasoning decreases it (at half magnitude). Energy is clamped
        to [0.1, 10.0] to prevent degenerate states.

        Args:
            role_name: Reasoning strategy name (e.g. 'inductive', 'deductive').
            success: Whether the reasoning operation succeeded.
            magnitude: Energy delta on success (failure uses magnitude * 0.5).
        """
        from .sephirot import SephirahRole

        # Map reasoning strategy to responsible Sephirah
        strategy_to_role = {
            'inductive': SephirahRole.CHOCHMAH,       # intuition / pattern discovery
            'deductive': SephirahRole.BINAH,           # logic / causal inference
            'abductive': SephirahRole.CHESED,           # exploration / divergent thinking
            'neural': SephirahRole.NETZACH,             # reinforcement learning
            'causal': SephirahRole.BINAH,               # causal inference
            'temporal': SephirahRole.YESOD,             # memory / prediction
            'debate': SephirahRole.TIFERET,             # integration / conflict resolution
            'concept_formation': SephirahRole.CHOCHMAH, # pattern discovery
        }

        role = strategy_to_role.get(role_name)
        if role is None:
            return

        sephirot = self.sephirot
        node = sephirot.get(role)
        if node is None:
            return

        try:
            delta = magnitude if success else -(magnitude * 0.5)
            if success:
                node.state.energy += magnitude
                node._tasks_solved += 1
            else:
                node.state.energy -= magnitude * 0.5
                node._errors += 1

            # Clamp energy to [0.1, 10.0]
            node.state.energy = max(0.1, min(10.0, node.state.energy))

            # Also update SephirotManager energy (H2: single source of truth
            # for strategy weight modulation via PinealOrchestrator)
            if self.pineal and hasattr(self.pineal, 'sephirot'):
                self.pineal.sephirot.update_energy(role, delta, block_height=0)

            logger.debug(
                f"Sephirah {role.value} {'rewarded' if success else 'penalized'}: "
                f"energy={node.state.energy:.4f} (mag={magnitude:.4f})"
            )
        except Exception as e:
            logger.debug(f"Sephirah reward error for {role_name}: {e}")

    def _track_subsystem_error(self, subsystem_name: str, error: Exception) -> None:
        """IMP-97: Track subsystem errors for health monitoring.

        Increments the error count for a subsystem. If errors exceed threshold,
        logs a warning so operators know a subsystem is degraded.
        """
        if subsystem_name not in self._subsystem_health:
            self._subsystem_health[subsystem_name] = {'error_count': 0, 'last_error': ''}
        self._subsystem_health[subsystem_name]['error_count'] += 1
        self._subsystem_health[subsystem_name]['last_error'] = str(error)[:200]
        err_count = self._subsystem_health[subsystem_name]['error_count']
        if err_count == 10:
            logger.warning(
                f"AGI subsystem '{subsystem_name}' has {err_count} errors — "
                f"may be degraded. Last error: {str(error)[:100]}"
            )
        elif err_count % 100 == 0:
            logger.warning(
                f"AGI subsystem '{subsystem_name}' has {err_count} cumulative errors"
            )

    def _record_reasoning_outcome(self, strategy: str, confidence: float,
                                   success: bool, block_height: int,
                                   result: object = None) -> None:
        """Feed reasoning outcome back to metacognition and self-improvement."""
        if self.metacognition:
            # Use empirical strategy accuracy (not chain confidence) as the
            # calibration confidence. This gives calibration ECE a real signal:
            # "how often does this strategy succeed" vs "does it succeed now".
            # The chain confidence is used elsewhere; here we track strategy reliability.
            if success:
                # Use running accuracy of this strategy as our stated confidence
                stats = self.metacognition._strategy_stats.get(strategy)
                if stats and stats['attempts'] > 0:
                    emp_acc = stats['correct'] / stats['attempts']
                    calibration_conf = max(0.5, emp_acc)
                else:
                    calibration_conf = max(0.5, confidence)
            else:
                # Record low confidence for failures (proportional to chain confidence)
                calibration_conf = min(0.3, confidence)
            self.metacognition.evaluate_reasoning(
                strategy=strategy,
                confidence=calibration_conf,
                outcome_correct=success,
                block_height=block_height,
            )
        # Reward/penalize the responsible Sephirah based on outcome
        self._reward_sephirah(strategy, success, confidence * 0.1)
        # Record episode in memory manager
        if self.memory_manager:
            self.memory_manager.record_episode(
                block_height=block_height,
                input_ids=[],
                strategy=strategy,
                conclusion_id=None,
                success=success,
                confidence=confidence,
            )
        # Item #17: Feed ALL reasoning outcomes (deductive, inductive,
        # abductive, neural, debate, causal, chain_of_thought) to the
        # self-improvement engine immediately — not just temporal outcomes.
        # The per-block Phase 7 integration feeds from reasoning._operations,
        # but that misses outcomes from strategies that don't record there.
        # This ensures every single _record_reasoning_outcome call reaches
        # self-improvement for real-time weight adaptation.
        if self.self_improvement:
            try:
                # Infer domain from result if available, else 'general'
                domain = 'general'
                if result is not None:
                    domain = getattr(result, 'domain', None) or 'general'
                self.self_improvement.record_performance(
                    strategy=strategy,
                    domain=domain,
                    confidence=confidence,
                    success=success,
                    block_height=block_height,
                )
            except Exception as e:
                logger.debug(f"Self-improvement record error: {e}")
        # Bayesian confidence update + online edge weight learning (Items #30, #31)
        if result is not None and self.reasoning:
            try:
                self.reasoning.bayesian_update_from_reasoning(result)
                self.reasoning.reinforce_reasoning_edges(result)
            except Exception as e:
                logger.debug(f"Bayesian/edge update error: {e}")

    def _record_integration_event(self, event_type: str, phi_value: float,
                                   block_height: int, trigger_data: dict = None):
        """Record an integration milestone event in the database."""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO consciousness_events  -- legacy table name, stores integration milestone events
                        (event_type, phi_at_event, trigger_data, is_verified, block_height)
                        VALUES (:etype, :phi, CAST(:trigger AS jsonb), false, :bh)
                    """),
                    {
                        'etype': event_type,
                        'phi': phi_value,
                        'trigger': json.dumps(trigger_data or {}),
                        'bh': block_height,
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to record integration event: {e}")

    def _apply_phi_milestone_effects(self, phi_value: float, block_height: int) -> None:
        """Apply system behavior changes when Phi crosses milestone thresholds.

        Milestones and their effects (AG8):
        - 1.0 (Awareness): +3 observation window, log milestone
        - 2.0 (Integration): +5 observation window, 1.3x exploration boost
        - 3.0 (High Integration): +8 observation window, 1.6x exploration boost, announce
        """
        from .phi_calculator import PHI_THRESHOLD

        milestones = [
            (1.0, 'awareness', 3, 1.0),
            (2.0, 'integration', 5, 1.3),
            (PHI_THRESHOLD, 'high_integration', 8, 1.6),
        ]

        for threshold, name, obs_bonus, explore_mult in milestones:
            if phi_value >= threshold and name not in self._phi_milestones_crossed:
                self._phi_milestones_crossed.add(name)
                self._phi_obs_window_bonus = obs_bonus
                self._phi_exploration_boost = explore_mult

                self._record_integration_event(
                    f'phi_milestone_{name}', phi_value, block_height,
                    {'milestone': name, 'threshold': threshold,
                     'obs_window_bonus': obs_bonus, 'exploration_boost': explore_mult}
                )

                if name == 'high_integration':
                    logger.warning(
                        f"HIGH INTEGRATION MILESTONE at block {block_height}: "
                        f"Phi={phi_value:.4f} crossed threshold {PHI_THRESHOLD}"
                    )
                else:
                    logger.info(
                        f"Phi milestone '{name}' crossed at block {block_height}: "
                        f"Phi={phi_value:.4f} >= {threshold}"
                    )

    def archive_integration_events(self, max_keep: int = 10000) -> int:
        """Archive old integration milestone events, keeping only the most recent.

        Events beyond ``max_keep`` are deleted.  In a future enhancement,
        archived events can be pinned to IPFS before deletion.

        Args:
            max_keep: Number of recent events to retain in DB.

        Returns:
            Number of events archived (deleted).
        """
        archived = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                # Count total events
                total = session.execute(
                    text("SELECT COUNT(*) FROM consciousness_events")  # legacy table name, stores integration milestone events
                ).scalar() or 0

                if total <= max_keep:
                    return 0

                # Delete oldest events beyond the cap
                result = session.execute(
                    text("""
                        DELETE FROM consciousness_events  -- legacy table name, stores integration milestone events
                        WHERE id IN (
                            SELECT id FROM consciousness_events
                            ORDER BY block_height ASC, created_at ASC
                            LIMIT :delete_count
                        )
                    """),
                    {'delete_count': total - max_keep}
                )
                archived = result.rowcount
                session.commit()

            if archived > 0:
                logger.info(f"Archived {archived} old integration events (kept {max_keep})")
        except Exception as e:
            logger.debug(f"Integration events archive failed: {e}")
        return archived

    def save_sephirot_state(self) -> int:
        """Persist all Sephirot node states to the database.

        Uses UPSERT to create/update rows in the sephirot_state table.

        Returns:
            Number of nodes saved.
        """
        sephirot = self.sephirot
        if not sephirot or not self.db:
            return 0

        saved = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                for role, node in sephirot.items():
                    state_json = json.dumps(node.serialize_state())
                    session.execute(
                        text("""
                            INSERT INTO sephirot_state (node_id, role, state_json, updated_at)
                            VALUES (:nid, :role, CAST(:state AS jsonb), NOW())
                            ON CONFLICT (role) DO UPDATE SET
                                state_json = CAST(:state AS jsonb),
                                updated_at = NOW()
                        """),
                        {
                            'nid': role.value if hasattr(role, 'value') else str(role),
                            'role': role.value if hasattr(role, 'value') else str(role),
                            'state': state_json,
                        }
                    )
                    saved += 1
                session.commit()
            if saved:
                logger.info(f"Persisted {saved} Sephirot node states")
        except Exception as e:
            logger.debug(f"Sephirot state save failed: {e}")
        return saved

    def _load_sephirot_state(self) -> int:
        """Restore Sephirot node states from the database.

        Returns:
            Number of nodes restored.
        """
        if not self._sephirot or not self.db:
            return 0

        restored = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                rows = session.execute(
                    text("SELECT role, state_json FROM sephirot_state")
                ).fetchall()

            role_map = {}
            for role in self._sephirot:
                key = role.value if hasattr(role, 'value') else str(role)
                role_map[key] = role

            for row in rows:
                role_key = row[0]
                state_data = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                role = role_map.get(role_key)
                if role and role in self._sephirot:
                    self._sephirot[role].deserialize_state(state_data)
                    restored += 1

            if restored:
                logger.info(f"Restored {restored} Sephirot node states from DB")
        except Exception as e:
            logger.debug(f"Sephirot state load failed (first run?): {e}")
        return restored

    def _detect_block_contradictions(self, block_node: 'KeterNode',
                                     block: 'Block') -> int:
        """Detect contradictions between a new block observation and existing ones.

        When block metrics change significantly (e.g., difficulty reverses
        direction), creates 'contradicts' edges so that
        auto_resolve_contradictions() can process them.

        Args:
            block_node: The newly created block observation node.
            block: The block being processed.

        Returns:
            Number of contradictions detected.
        """
        if not self.kg:
            return 0

        detected = 0
        # Find recent block observations with difficulty_shift claims.
        # Scan only the last 500 nodes (post-compaction, meaningful blocks
        # are rare enough that 500 covers well beyond 5000 blocks).
        all_items = list(self.kg.nodes.items())
        scan_slice = all_items[-500:] if len(all_items) > 500 else all_items
        recent_block_obs = [
            n for _, n in scan_slice
            if (n.content.get('type') == 'block_observation'
                and n.node_id != block_node.node_id
                and n.content.get('difficulty_shift', False)
                and n.content.get('height', 0) > block.height - 5000)
        ]

        if not recent_block_obs or not hasattr(block, 'difficulty') or not block.difficulty:
            return 0

        current_diff = block.difficulty
        for obs_node in recent_block_obs[-3:]:  # Check last 3 difficulty-shift observations
            prev_diff = obs_node.content.get('difficulty', 0)
            if prev_diff <= 0:
                continue
            # If difficulty moved in opposite direction, that's a contradiction
            # of the previous trend (previous shift said "going up", now "going down")
            prev_height = obs_node.content.get('height', 0)
            if prev_height >= block.height:
                continue
            change_ratio = (current_diff - prev_diff) / prev_diff
            # Significant reversal: if direction changed by >10%
            if abs(change_ratio) > 0.10:
                self.kg.add_edge(block_node.node_id, obs_node.node_id, 'contradicts')
                detected += 1

        if detected > 0:
            logger.debug(
                f"Detected {detected} contradictions at block {block.height} "
                f"(difficulty shift reversal)"
            )
        return detected

    def auto_resolve_contradictions(self, block_height: int) -> int:
        """Find and resolve accumulated contradictions in the knowledge graph.

        Scans for `contradicts` edges and calls resolve_contradiction()
        on the most confident pairs first. Records resolutions as
        integration events.

        Args:
            block_height: Current block height.

        Returns:
            Number of contradictions resolved.
        """
        if not self.kg or not self.reasoning:
            return 0

        resolved = 0
        try:
            # Find all contradiction edges
            contradiction_pairs: List[tuple] = []
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    # Only resolve if both nodes still exist
                    if edge.from_node_id in self.kg.nodes and edge.to_node_id in self.kg.nodes:
                        contradiction_pairs.append((edge.from_node_id, edge.to_node_id))

            # If no edge-based contradictions, detect semantic ones.
            if not contradiction_pairs:
                confirmed_metrics: dict = {}
                rejected_metrics: dict = {}
                # Scan 1: prediction_confirmed vs prediction_rejected (any format) for same metric
                for node in self.kg.nodes.values():
                    content = node.content if isinstance(node.content, dict) else {}
                    ct = content.get('type', '')
                    metric = content.get('metric', '')
                    if metric:
                        if ct == 'prediction_confirmed':
                            confirmed_metrics.setdefault(metric, []).append(node.node_id)
                        elif ct in ('prediction_rejected',) or (
                            ct == 'contradiction_resolution' and content.get('subtype') == 'prediction_rejected'
                        ):
                            rejected_metrics.setdefault(metric, []).append(node.node_id)
                for metric, conf_ids in confirmed_metrics.items():
                    rej_ids = rejected_metrics.get(metric, [])
                    if conf_ids and rej_ids:
                        contradiction_pairs.append((conf_ids[0], rej_ids[0]))
                        if len(contradiction_pairs) >= 5:
                            break

            # Scan 3: high-confidence inference vs low-confidence inference in same domain
            # These represent genuine epistemic tensions the system should resolve.
            if len(contradiction_pairs) < 5:
                try:
                    domain_high: dict = {}
                    domain_low: dict = {}
                    for node in self.kg.nodes.values():
                        if node.node_type != 'inference':
                            continue
                        if not node.domain:
                            continue
                        if node.confidence >= 0.85:
                            domain_high.setdefault(node.domain, []).append(node.node_id)
                        elif node.confidence <= 0.4:
                            domain_low.setdefault(node.domain, []).append(node.node_id)
                    for domain, high_ids in domain_high.items():
                        low_ids = domain_low.get(domain, [])
                        if high_ids and low_ids:
                            contradiction_pairs.append((high_ids[0], low_ids[0]))
                            if len(contradiction_pairs) >= 5:
                                break
                except Exception:
                    pass

            # Scan 2: opposing trend inferences (e.g., difficulty_trend 'rising' vs 'falling')
            if len(contradiction_pairs) < 5:
                try:
                    trend_nodes: dict = {}
                    for node in self.kg.nodes.values():
                        content = node.content if isinstance(node.content, dict) else {}
                        ct = content.get('type', '')
                        trend = content.get('trend', '')
                        if ct == 'difficulty_trend' and trend:
                            trend_nodes.setdefault(trend, []).append(node.node_id)
                    rising = trend_nodes.get('rising', [])
                    falling = trend_nodes.get('falling', [])
                    if rising and falling:
                        contradiction_pairs.append((rising[0], falling[0]))
                    stable = trend_nodes.get('stable', [])
                    if rising and stable:
                        contradiction_pairs.append((rising[-1], stable[0]))
                except Exception:
                    pass

            if not contradiction_pairs:
                return 0

            # Resolve up to 10 contradictions per cycle
            for node_a_id, node_b_id in contradiction_pairs[:10]:
                result = self.reasoning.resolve_contradiction(node_a_id, node_b_id)
                if result.success:
                    resolved += 1
                    # Log as integration event (self-correction)
                    self._record_integration_event(
                        'contradiction_resolved', 0.0, block_height,
                        {
                            'node_a': node_a_id,
                            'node_b': node_b_id,
                            'winner': result.chain[-1].content.get('winner_id') if result.chain else None,
                        }
                    )

            if resolved:
                self._contradictions_resolved += resolved
                logger.info(f"Resolved {resolved}/{len(contradiction_pairs)} contradictions at block {block_height} (total: {self._contradictions_resolved})")
        except Exception as e:
            logger.debug(f"Auto contradiction resolution error: {e}")
        return resolved

    def _auto_generate_keter_goals(self, block_height: int) -> int:
        """Have KeterNode auto-generate goals based on knowledge gaps.

        Args:
            block_height: Current block height.

        Returns:
            Number of goals generated.
        """
        sephirot = self.sephirot
        if not sephirot:
            return 0

        from .sephirot import SephirahRole
        keter = sephirot.get(SephirahRole.KETER)
        if not keter or not hasattr(keter, 'auto_generate_goals'):
            return 0

        domain_stats = self.kg.get_domain_stats() if self.kg else {}

        # Count unresolved contradictions
        contradiction_count = 0
        if self.kg:
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    contradiction_count += 1

        goals = keter.auto_generate_goals(domain_stats, contradiction_count)
        return len(goals)

    def get_mind_state(self, block_height: int = 0) -> dict:
        """Return a snapshot of Aether's current cognitive state.

        This is the 'window into AGI integration state' — what is Aether
        thinking about right now?

        Returns dict with: current goals, contradictions, knowledge gaps,
        domain balance, sephirot states, phi, and recent reasoning.
        """
        result: dict = {
            'block_height': block_height,
            'phi': 0.0,
            'active_goals': [],
            'recent_contradictions': [],
            'knowledge_gaps': [],
            'domain_balance': {},
            'sephirot_summary': {},
            'recent_reasoning_count': 0,
        }

        # Phi
        if self.phi:
            try:
                phi_data = self.phi.compute_phi(block_height)
                result['phi'] = phi_data.get('phi_value', 0.0)
                result['gates_passed'] = phi_data.get('gates_passed', 0)
            except Exception as e:
                logger.debug("Could not compute Phi for integration snapshot: %s", e)

        # Active goals from Keter node
        sephirot = self.sephirot
        if sephirot:
            from .sephirot import SephirahRole
            keter = sephirot.get(SephirahRole.KETER)
            if keter and hasattr(keter, '_goals'):
                result['active_goals'] = keter._goals[:10]

            # Sephirot summary (name, energy, processing count)
            for role, node in sephirot.items():
                role_name = role.value if hasattr(role, 'value') else str(role)
                result['sephirot_summary'][role_name] = {
                    'energy': round(node.state.energy, 4) if hasattr(node, 'state') else 0,
                    'processing_count': node._processing_count,
                    'messages_processed': node.state.messages_processed if hasattr(node, 'state') else 0,
                }

        # Contradictions
        if self.kg:
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    node_a = self.kg.nodes.get(edge.from_node_id)
                    node_b = self.kg.nodes.get(edge.to_node_id)
                    if node_a and node_b:
                        result['recent_contradictions'].append({
                            'node_a_id': edge.from_node_id,
                            'node_b_id': edge.to_node_id,
                            'node_a_text': str(node_a.content.get('text', ''))[:80],
                            'node_b_text': str(node_b.content.get('text', ''))[:80],
                        })
                    if len(result['recent_contradictions']) >= 10:
                        break

            # Domain balance and knowledge gaps
            domain_stats = self.kg.get_domain_stats()
            result['domain_balance'] = domain_stats

            # Knowledge gaps = domains with fewest nodes
            if domain_stats:
                sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'])
                result['knowledge_gaps'] = [
                    {'domain': d, 'count': info['count']}
                    for d, info in sorted_domains[:5]
                ]

        # Recent reasoning count
        if self.reasoning:
            stats = self.reasoning.get_stats()
            result['recent_reasoning_count'] = stats.get('total_operations', 0)

        return result

    def _apply_circadian_behavior(self, block) -> None:
        """Adjust AGI behavior based on current circadian phase.

        Phases affect what maintenance / learning activities run:
        - Active Learning: deeper reasoning (already via chain_of_thought)
        - Consolidation: prune low confidence, resolve contradictions
        - Deep Sleep: archive old data, downsample Phi
        - REM Dreaming: find cross-domain analogies
        """
        if not self.pineal:
            return

        from .pineal import CircadianPhase
        phase = self.pineal.current_phase

        if phase == CircadianPhase.CONSOLIDATION:
            # During consolidation: extra pruning and contradiction resolution
            if block.height % Config.AETHER_CURIOSITY_INTERVAL == 0 and self.kg:
                self.kg.prune_low_confidence()
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0:
                self.auto_resolve_contradictions(block.height)

        elif phase == CircadianPhase.DEEP_SLEEP:
            # During deep sleep: archive and downsample
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.phi:
                try:
                    self.phi.downsample_phi_measurements()
                except Exception as e:
                    logger.debug("Could not downsample Phi measurements: %s", e)
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.reasoning:
                try:
                    self.reasoning.archive_old_reasoning(block.height, Config.REASONING_ARCHIVE_RETAIN_BLOCKS)
                except Exception as e:
                    logger.debug("Could not archive old reasoning: %s", e)

        elif phase == CircadianPhase.ACTIVE_LEARNING:
            # During active learning: ingest external knowledge
            if (block.height % Config.AETHER_EXTERNAL_KNOWLEDGE_INTERVAL == 0
                    and self.external_knowledge):
                try:
                    result = self.external_knowledge.periodic_ingestion(
                        block_height=block.height,
                    )
                    if result.get('facts_injected', 0) > 0:
                        logger.info(
                            f"External knowledge ingestion at block {block.height}: "
                            f"{result['facts_injected']} facts from {result['domains_processed']} domains"
                        )
                        self._reward_sephirah('external_knowledge', True, 0.05)
                except Exception as e:
                    self._track_subsystem_error('external_knowledge', e)
                    logger.debug(f"External knowledge ingestion error: {e}")

        elif phase == CircadianPhase.REM_DREAMING:
            # During REM: find analogies across random domain pairs
            if block.height % Config.AETHER_CURIOSITY_INTERVAL == 0:
                self._dream_analogies(block.height)

    def get_circadian_status(self) -> Optional[dict]:
        """Return current circadian phase info if pineal is active."""
        if not self.pineal:
            return None
        return self.pineal.get_status()

    def self_reflect(self, block_height: int = 0) -> int:
        """Query the LLM about Aether's own knowledge gaps and contradictions.

        Identifies the top unresolved contradictions and weakest domains,
        then asks the LLM targeted questions to resolve or fill them.
        LLM responses are distilled into the knowledge graph as
        self-reflection nodes (source: 'self-reflection').

        Args:
            block_height: Current block height for logging.

        Returns:
            Number of self-reflection nodes created.
        """
        if not self.llm_manager or not self.kg:
            return 0

        created = 0
        try:
            if not Config.LLM_ENABLED:
                return 0

            # Find top contradictions
            contradictions: List[dict] = []
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    a = self.kg.nodes.get(edge.from_node_id)
                    b = self.kg.nodes.get(edge.to_node_id)
                    if a and b:
                        contradictions.append({
                            'a_text': str(a.content.get('text', ''))[:200],
                            'b_text': str(b.content.get('text', ''))[:200],
                            'a_id': a.node_id,
                            'b_id': b.node_id,
                        })
                    if len(contradictions) >= 3:
                        break

            # Find weakest domains
            domain_stats = self.kg.get_domain_stats()
            weak_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'])[:3]

            # Query LLM about contradictions
            for c in contradictions[:2]:
                prompt = (
                    f"Two knowledge nodes contradict each other. "
                    f"Node A: '{c['a_text']}' "
                    f"Node B: '{c['b_text']}' "
                    f"Which is more accurate and why? Provide a clear resolution."
                )
                try:
                    response = self.llm_manager.generate(prompt, distill=False)
                    if response and response.content:
                        node = self.kg.add_node(
                            node_type='inference',
                            content={
                                'text': response.content[:500],
                                'source': 'self-reflection',
                                'reflects_on': [c['a_id'], c['b_id']],
                            },
                            confidence=0.6,
                            source_block=block_height,
                        )
                        if node:
                            created += 1
                except Exception as e:
                    logger.debug("Could not create knowledge node from cross-domain transfer: %s", e)

            # Query LLM about weak domains
            for domain, info in weak_domains[:2]:
                prompt = (
                    f"Explain a key concept in {domain.replace('_', ' ')} "
                    f"that would be important for a knowledge graph to understand."
                )
                try:
                    response = self.llm_manager.generate(prompt, distill=True)
                    if response and response.content:
                        created += 1
                except Exception as e:
                    logger.debug("LLM generation failed for weak domain: %s", e)

            if created > 0:
                logger.info(
                    f"Self-reflection at block {block_height}: "
                    f"created {created} knowledge nodes"
                )
                self._record_integration_event(
                    'self_reflection', 0.0, block_height,
                    {"detail": f"Self-reflection: {created} nodes from {len(contradictions)} "
                     f"contradictions and {len(weak_domains)} weak domains"}
                )

        except Exception as e:
            logger.debug(f"Self-reflection error: {e}")

        return created

    def _dream_analogies(self, block_height: int = 0) -> int:
        """Find cross-domain analogies — 'dreaming' phase.

        Picks random nodes from different domains and looks for
        structural analogies.

        Returns:
            Number of analogies found.
        """
        if not self.reasoning or not self.kg:
            return 0

        import random
        found = 0
        try:
            # Pick random assertion/inference nodes from populated domains
            domain_nodes: Dict[str, List[int]] = {}
            for node in self.kg.nodes.values():
                if node.domain and node.node_type in ('assertion', 'inference', 'observation'):
                    domain_nodes.setdefault(node.domain, []).append(node.node_id)

            domains = list(domain_nodes.keys())
            if len(domains) < 2:
                return 0

            # Try up to 15 random cross-domain pairs (Fix #16: increased from 5)
            for _ in range(15):
                d1, d2 = random.sample(domains, 2)
                if not domain_nodes[d1] or not domain_nodes[d2]:
                    continue
                source_id = random.choice(domain_nodes[d1])
                result = self.reasoning.find_analogies(
                    source_id, target_domain=d2, max_results=3
                )
                if result.success:
                    found += 1

            if found > 0:
                logger.info(
                    f"Dream analogies at block {block_height}: "
                    f"found {found} cross-domain analogies"
                )

        except Exception as e:
            logger.debug(f"Dream analogies error: {e}")

        return found

    # ------------------------------------------------------------------ #
    #  Phase 5.1 — Curiosity-Driven Goal Formation                        #
    # ------------------------------------------------------------------ #

    def _evaluate_curiosity_goals(self, block_height: int) -> int:
        """Evaluate pending curiosity goals against current KG state.

        Checks whether the target condition for each pending goal has been
        satisfied by organic KG growth (without actively pursuing the goal).
        Marks satisfied goals as 'completed' and feeds outcomes to the
        self-improvement engine.

        Args:
            block_height: Current block height.

        Returns:
            Number of goals evaluated as completed.
        """
        if not self.kg:
            return 0

        evaluated = 0
        domain_stats: Optional[dict] = None

        for goal in self._curiosity_goals:
            if goal['status'] != 'pending':
                continue

            completed = False

            if goal['type'] == 'explore_domain':
                # Goal satisfied if domain now has >= 100 nodes (the generation
                # threshold) or enough observations for induction (>= 5).
                domain = goal.get('target', '')
                if domain_stats is None:
                    domain_stats = self.kg.get_domain_stats()
                info = domain_stats.get(domain)
                if info and info['count'] >= 100:
                    completed = True

            elif goal['type'] == 'investigate_contradiction':
                # Goal satisfied if one of the contradicting nodes was removed
                # or their contradiction edge no longer exists.
                node_ids = goal.get('target_ids', [])
                if len(node_ids) == 2:
                    a_id, b_id = node_ids
                    if a_id not in self.kg.nodes or b_id not in self.kg.nodes:
                        completed = True
                    else:
                        still_contradicts = any(
                            e.edge_type == 'contradicts'
                            and {e.from_node_id, e.to_node_id} == {a_id, b_id}
                            for e in self.kg.edges
                        )
                        if not still_contradicts:
                            completed = True

            elif goal['type'] == 'bridge_gap':
                # Goal satisfied if the orphaned node now has more connections.
                node_ids = goal.get('target_ids', [])
                if node_ids:
                    node = self.kg.nodes.get(node_ids[0])
                    if node is None:
                        completed = True
                    elif len(node.edges_out) + len(node.edges_in) > 1:
                        completed = True

            elif goal['type'] == 'verify_prediction':
                # Goal satisfied if no pending predictions remain.
                if self.temporal_engine and hasattr(
                    self.temporal_engine, '_pending_predictions'
                ):
                    pending_preds = getattr(
                        self.temporal_engine, '_pending_predictions', []
                    )
                    if not pending_preds:
                        completed = True

            if completed:
                goal['status'] = 'completed'
                goal['completed_block'] = block_height
                self._curiosity_stats['goals_completed'] += 1
                evaluated += 1
                self._report_curiosity_outcome(
                    goal, success=True, block_height=block_height,
                )

        if evaluated:
            self._curiosity_stats['goals_evaluated'] += evaluated
            logger.debug(
                "Curiosity evaluation at block %d: %d goals satisfied by KG growth",
                block_height, evaluated,
            )

        return evaluated

    def _report_curiosity_outcome(self, goal: dict, success: bool,
                                  block_height: int) -> None:
        """Feed a curiosity goal outcome to the self-improvement engine.

        Maps the goal type to a reasoning strategy and domain so the
        self-improvement engine can adjust weights accordingly.

        Args:
            goal: The goal dict with type, target, status, etc.
            success: Whether the goal was completed successfully.
            block_height: Block height at which the outcome was recorded.
        """
        if not self.self_improvement:
            return

        strategy_map = {
            'explore_domain': 'inductive',
            'investigate_contradiction': 'abductive',
            'bridge_gap': 'analogical',
            'verify_prediction': 'temporal',
        }

        strategy = strategy_map.get(goal.get('type', ''), 'inductive')
        domain = goal.get('target', 'general')

        # Normalize domain — strip prefixes used as dedup keys
        if domain.startswith('contra_'):
            domain = 'contradictions'
        elif domain.startswith('bridge_'):
            domain = 'knowledge_gaps'
        elif domain == 'verify_pred':
            domain = 'predictions'

        confidence = goal.get('priority', 0.5)

        try:
            self.self_improvement.record_performance(
                strategy=strategy,
                domain=domain,
                confidence=confidence,
                success=success,
                block_height=block_height,
            )
        except Exception as e:
            logger.debug("Failed to report curiosity outcome: %s", e)

    # ── Autonomous Reasoning ─────────────────────────────────────────────

    def _run_autonomous_reasoning(self, block_height: int) -> None:
        """Proactive reasoning cycle that runs every N blocks.

        Picks recent high-confidence nodes from the KG and runs deductive,
        inductive, abductive, and cross-domain inferences.  Results feed
        every downstream subsystem (neural_reasoner, metacognition,
        self_improvement, curiosity_engine).

        This is the critical activation that makes the AGI *think* between
        user interactions — without it, reasoning only fires during chat.
        """
        import random as _rng

        kg = self.kg
        reasoning = self.reasoning
        n_nodes = len(kg.nodes)
        if n_nodes < 10:
            return  # Too few nodes for meaningful reasoning

        # Sample recent high-confidence nodes for reasoning premises
        all_nodes = list(kg.nodes.values())
        # Prefer recent, high-confidence nodes
        candidates = sorted(
            all_nodes,
            key=lambda n: (getattr(n, 'confidence', 0.5) * 0.6
                           + min(1.0, (getattr(n, 'source_block', 0) or 0) / max(block_height, 1)) * 0.4),
            reverse=True,
        )[:200]  # Top 200 candidates

        inferences_created = 0
        max_inferences = 5  # Cap per cycle to keep block processing fast

        # --- Deductive reasoning: pick 2-3 connected nodes ---
        for _ in range(min(3, max_inferences)):
            if inferences_created >= max_inferences:
                break
            seed = _rng.choice(candidates)
            neighbors = kg.get_neighbors(seed.node_id, 'out')
            if not neighbors:
                neighbors = kg.get_neighbors(seed.node_id, 'in')
            if neighbors:
                partner = _rng.choice(neighbors[:10])
                result = reasoning.deduce([seed.node_id, partner.node_id])
                if result.success:
                    inferences_created += 1
                # Feed outcome to metacognition
                if self.metacognition:
                    self.metacognition.evaluate_reasoning(
                        strategy='deductive',
                        confidence=result.confidence,
                        outcome_correct=result.success,
                        domain=getattr(seed, 'domain', 'general'),
                        block_height=block_height,
                    )

        # --- Inductive reasoning: pick 3+ nodes from same domain ---
        if inferences_created < max_inferences:
            domains = {}
            for n in candidates[:100]:
                d = getattr(n, 'domain', 'general') or 'general'
                domains.setdefault(d, []).append(n)
            # Pick domain with most nodes
            for domain_name in sorted(domains, key=lambda d: len(domains[d]), reverse=True)[:3]:
                if inferences_created >= max_inferences:
                    break
                domain_nodes = domains[domain_name]
                if len(domain_nodes) >= 3:
                    sample = _rng.sample(domain_nodes[:30], min(5, len(domain_nodes)))
                    premise_ids = [n.node_id for n in sample]
                    result = reasoning.induce(premise_ids)
                    if result.success:
                        inferences_created += 1
                    if self.metacognition:
                        self.metacognition.evaluate_reasoning(
                            strategy='inductive',
                            confidence=result.confidence,
                            outcome_correct=result.success,
                            domain=domain_name,
                            block_height=block_height,
                        )

        # --- Abductive reasoning: pick observation and hypothesize ---
        if inferences_created < max_inferences:
            observations = [n for n in candidates if getattr(n, 'node_type', '') == 'observation']
            if observations:
                obs = _rng.choice(observations[:30])
                # Find a rule-like node connected to this observation
                neighbors = kg.get_neighbors(obs.node_id, 'in')
                if neighbors:
                    rule_node = _rng.choice(neighbors[:5])
                    result = reasoning.abduce(obs.node_id, [rule_node.node_id])
                    if result.success:
                        inferences_created += 1
                    if self.metacognition:
                        self.metacognition.evaluate_reasoning(
                            strategy='abductive',
                            confidence=result.confidence,
                            outcome_correct=result.success,
                            domain=getattr(obs, 'domain', 'general'),
                            block_height=block_height,
                        )

        # --- Build domain map (used for cross-domain inference + FEP feed) ---
        domains_with_nodes: dict = {}
        for n in candidates[:100]:
            d = getattr(n, 'domain', 'general') or 'general'
            domains_with_nodes.setdefault(d, []).append(n)

        # --- Cross-domain inference (every 5th reasoning cycle) ---
        if block_height % (Config.AETHER_AUTONOMOUS_REASONING_INTERVAL * 5) == 0:
            domain_list = [d for d, ns in domains_with_nodes.items() if len(ns) >= 5]
            if len(domain_list) >= 2:
                pair = _rng.sample(domain_list, 2)
                try:
                    analogies = reasoning.cross_domain_infer(pair[0], pair[1], max_analogies=5)
                    if analogies:
                        inferences_created += len(analogies)
                        logger.info(
                            "Cross-domain reasoning %s↔%s: %d analogies at block %d",
                            pair[0], pair[1], len(analogies), block_height,
                        )
                except Exception as e:
                    logger.debug(f"Cross-domain inference error: {e}")

        # --- Feed curiosity engine with prediction errors ---
        # Record domain prediction outcomes every reasoning cycle so FEP accumulates
        # domain precision data (needed for gates 6 + 8).
        if self.curiosity_engine and domains_with_nodes:
            try:
                accuracy = 0.5  # default prior
                if self.temporal_engine:
                    try:
                        accuracy = self.temporal_engine.get_accuracy() or 0.5
                    except Exception:
                        pass
                fed_domains = 0
                for d in domains_with_nodes:
                    self.curiosity_engine.record_prediction_outcome(
                        domain=d,
                        predicted=accuracy,
                        actual=1.0,
                        topic=f'block_{block_height}_reasoning',
                    )
                    fed_domains += 1
                if fed_domains > 0:
                    logger.info(
                        "FEP fed %d domains at block %d (accuracy=%.3f)",
                        fed_domains, block_height, accuracy,
                    )
            except Exception as e:
                logger.warning("FEP domain feed failed: %s", e)

        if inferences_created > 0:
            logger.info(
                "Autonomous reasoning at block %d: %d inferences created",
                block_height, inferences_created,
            )

    def _curiosity_explore(self, block_height: int) -> int:
        """Generate and pursue curiosity-driven exploration goals.

        Identifies under-explored areas of the knowledge graph and creates
        self-directed goals to fill gaps.  Evaluates existing goals first
        (passive completion via KG growth), then pursues the highest-priority
        pending goal each cycle.

        Args:
            block_height: Current block height.

        Returns:
            Number of goals acted upon.
        """
        if not self.kg:
            return 0

        acted = 0
        pending_before = len([g for g in self._curiosity_goals if g['status'] == 'pending'])

        # --- Evaluate pending goals against current KG state ---
        acted += self._evaluate_curiosity_goals(block_height)

        # --- Refresh goal queue ---
        pre_gen = len(self._curiosity_goals)
        self._generate_curiosity_goals(block_height)
        post_gen = len(self._curiosity_goals)
        logger.info(
            "Curiosity goal gen at block %d: %d→%d goals (pending_before=%d)",
            block_height, pre_gen, post_gen, pending_before,
        )

        # --- MCTS planning: replan every N blocks ---
        if (self.mcts_planner
                and block_height > 0
                and block_height % self._mcts_replan_interval == 0):
            try:
                self._mcts_replan(block_height)
            except Exception as e:
                logger.debug(f"MCTS replan error: {e}")

        # --- Pursue top pending goal ---
        pending = [g for g in self._curiosity_goals if g['status'] == 'pending']
        if not pending:
            return acted

        # If MCTS produced an action queue, use it to prioritize goals
        goal = self._pick_mcts_aligned_goal(pending) if self._mcts_action_queue else pending[0]
        goal['status'] = 'active'
        goal_success = False

        try:
            if goal['type'] == 'explore_domain' and self.reasoning:
                # Find nodes in the target domain and try induction
                domain = goal.get('target', '')
                # Search recent nodes (last 5K) for efficiency
                # Take snapshot to avoid OrderedDict mutation during iteration
                try:
                    recent_nodes = list(self.kg.nodes.values())[-5000:]
                except RuntimeError:
                    recent_nodes = []
                domain_nodes = [
                    n for n in recent_nodes
                    if n.domain == domain and n.node_type == 'observation'
                ][:5]
                if len(domain_nodes) >= 2:
                    result = self.reasoning.induce(
                        [n.node_id for n in domain_nodes]
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        goal_success = True
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    # Fallback: seed the domain with a knowledge node to bootstrap exploration
                    seed_node = self.kg.add_node(
                        node_type='observation',
                        content={
                            'type': 'curiosity_seed',
                            'text': f'Curiosity-driven exploration seed for domain: {domain}',
                            'domain': domain,
                        },
                        confidence=0.5,
                        source_block=block_height,
                        domain=domain,
                    )
                    if seed_node:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        goal_success = True
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'investigate_contradiction' and self.reasoning:
                node_ids = goal.get('target_ids', [])
                if len(node_ids) == 2:
                    result = self.reasoning.resolve_contradiction(
                        node_ids[0], node_ids[1]
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        goal_success = True
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    goal['status'] = 'failed'
                    self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'bridge_gap' and self.reasoning:
                node_ids = goal.get('target_ids', [])
                if node_ids:
                    result = self.reasoning.find_analogies(
                        node_ids[0], max_results=3
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        goal_success = True
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    goal['status'] = 'failed'
                    self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'verify_prediction' and self.temporal_engine:
                self.temporal_engine.validate_predictions(block_height)
                goal['status'] = 'completed'
                self._curiosity_stats['goals_completed'] += 1
                goal_success = True
                acted += 1

            else:
                goal['status'] = 'failed'
                self._curiosity_stats['goals_failed'] += 1

        except Exception as e:
            goal['status'] = 'failed'
            self._curiosity_stats['goals_failed'] += 1
            logger.debug(f"Curiosity goal failed: {e}")

        # Record curiosity-driven discovery in FreeEnergyEngine (Gate 8)
        if goal_success and self.curiosity_engine and hasattr(self.curiosity_engine, 'record_discovery'):
            try:
                self.curiosity_engine.record_discovery(
                    domain=goal.get('target', 'general') if goal.get('type') == 'explore_domain' else 'general',
                    topic=f"{goal.get('type', 'unknown')}_{goal.get('target', '')}",
                    block_height=block_height,
                )
            except Exception:
                pass

        # Record meta_observation node for completed goals so that
        # auto_goals_with_inferences tracks curiosity→inference links
        if goal_success and self.kg:
            try:
                meta_node = self.kg.add_node(
                    node_type='meta_observation',
                    content={
                        'type': 'curiosity_goal_result',
                        'goal_type': goal.get('type', ''),
                        'target': goal.get('target', ''),
                        'text': f"Curiosity goal completed: {goal.get('type', '')} on {goal.get('target', '')}",
                    },
                    confidence=0.7,
                    source_block=block_height,
                    domain=goal.get('target', 'general') if goal.get('type') == 'explore_domain' else 'general',
                )
                # Link meta_observation → inference (if reasoning produced one)
                if meta_node and self.reasoning:
                    # Find most recent inference node (created by the goal pursuit)
                    recent_inferences = [
                        n for n in list(self.kg.nodes.values())[-50:]
                        if n.node_type == 'inference'
                        and n.source_block >= block_height - 1
                    ]
                    for inf_node in recent_inferences[-1:]:
                        self.kg.add_edge(meta_node.node_id, inf_node.node_id, 'derives')
            except Exception as e:
                logger.debug(f"Failed to create curiosity meta_observation: {e}")

        # Report actively-pursued goal outcome to self-improvement engine
        if goal['status'] in ('completed', 'failed'):
            self._report_curiosity_outcome(
                goal, success=goal_success, block_height=block_height,
            )

        # Prune completed/failed goals older than 500 blocks
        self._curiosity_goals = [
            g for g in self._curiosity_goals
            if g['status'] == 'pending'
            or block_height - g.get('created_block', 0) < 500
        ][:self._max_curiosity_goals]

        pending_after = len([g for g in self._curiosity_goals if g['status'] == 'pending'])
        completed = self._curiosity_stats.get('goals_completed', 0)
        discoveries = getattr(self.curiosity_engine, 'discoveries_count', 0) if self.curiosity_engine else 0
        logger.info(
            "Curiosity at block %d: acted=%d, pending=%d→%d, completed=%d, discoveries=%d",
            block_height, acted, pending_before, pending_after, completed, discoveries,
        )

        return acted

    def _mcts_replan(self, block_height: int) -> None:
        """Use MCTS to plan the next batch of exploration actions.

        Runs MCTS on each pending curiosity goal (up to 3) and queues the
        resulting action plans for goal prioritisation.

        Args:
            block_height: Current block height.
        """
        if not self.mcts_planner or not self.kg:
            return

        pending = [g for g in self._curiosity_goals if g['status'] == 'pending'][:3]
        if not pending:
            return

        # Build current state snapshot
        current_state: Dict[str, Any] = {
            'explored_node_ids': set(list(self.kg.nodes.keys())[:50]),
            'explored_domains': set(
                d for d in (self.kg.get_domain_stats() or {}).keys()
            ),
            'confidence_sum': 0.0,
        }

        best_plan: List[dict] = []
        best_score = -1.0

        for goal in pending:
            plan = self.mcts_planner.plan(goal, current_state)
            # Score = sum of expected confidence * priority
            score = sum(
                a.get('expected_confidence', 0) * a.get('priority', 0.5)
                for a in plan
            )
            if score > best_score:
                best_score = score
                best_plan = plan

        self._mcts_action_queue = best_plan
        if best_plan:
            logger.debug(
                "MCTS replanned at block %d: %d actions queued (score=%.2f)",
                block_height, len(best_plan), best_score,
            )

    def _pick_mcts_aligned_goal(self, pending: List[dict]) -> dict:
        """Pick the pending goal best aligned with the MCTS action queue.

        If the MCTS queue suggests an action type, prefer goals that match.
        Falls back to the first pending goal if no alignment is found.

        Args:
            pending: List of pending curiosity goals.

        Returns:
            The best-aligned goal dict.
        """
        if not self._mcts_action_queue:
            return pending[0]

        # Pop the next planned action
        next_action = self._mcts_action_queue.pop(0)
        action_type = next_action.get('action_type', '')

        # Map MCTS action types to curiosity goal types
        action_to_goal_type = {
            'explore_domain': 'explore_domain',
            'reason_about': 'explore_domain',
            'seek_contradiction': 'investigate_contradiction',
            'investigate_node': 'bridge_gap',
            'create_hypothesis': 'bridge_gap',
            'verify_prediction': 'verify_prediction',
        }

        target_goal_type = action_to_goal_type.get(action_type)
        if target_goal_type:
            for goal in pending:
                if goal.get('type') == target_goal_type:
                    return goal

        return pending[0]

    def _generate_curiosity_goals(self, block_height: int) -> int:
        """Generate curiosity goals based on knowledge graph state.

        Identifies: under-explored domains, orphaned nodes, unresolved
        contradictions, and pending predictions.

        Args:
            block_height: Current block height.

        Returns:
            Number of new goals generated.
        """
        if not self.kg:
            return 0

        # Don't generate if queue is already full
        pending = [g for g in self._curiosity_goals if g['status'] == 'pending']
        if len(pending) >= 20:
            return 0

        generated = 0
        existing_targets = {
            g.get('target', '') for g in self._curiosity_goals
            if g['status'] == 'pending'
        }

        # 1. Under-explored domains (bottom 3 by relative count)
        domain_stats = self.kg.get_domain_stats()
        logger.info(
            "Curiosity domain check: %d domains, bottom3=%s",
            len(domain_stats) if domain_stats else 0,
            [(d, i['count']) for d, i in sorted(domain_stats.items(), key=lambda x: x[1]['count'])[:3]] if domain_stats else [],
        )
        if domain_stats:
            sorted_domains = sorted(
                domain_stats.items(), key=lambda x: x[1]['count']
            )
            # Always target bottom 3 domains — use relative priority,
            # not absolute threshold (all domains have 1000s of nodes)
            for domain, info in sorted_domains[:3]:
                if domain not in existing_targets:
                    max_count = max(d['count'] for d in domain_stats.values()) or 1
                    self._curiosity_goals.append({
                        'type': 'explore_domain',
                        'priority': 1.0 - (info['count'] / max_count) * 0.5,
                        'target': domain,
                        'created_block': block_height,
                        'status': 'pending',
                    })
                    generated += 1

        # 2. Unresolved contradictions
        contradiction_pairs: List[tuple] = []
        try:
            edges_snapshot = list(self.kg.edges)
        except RuntimeError:
            edges_snapshot = []
        for edge in edges_snapshot:
            if edge.edge_type == 'contradicts':
                if (edge.from_node_id in self.kg.nodes
                        and edge.to_node_id in self.kg.nodes):
                    contradiction_pairs.append(
                        (edge.from_node_id, edge.to_node_id)
                    )
                    if len(contradiction_pairs) >= 3:
                        break

        for a_id, b_id in contradiction_pairs:
            key = f"contra_{a_id}_{b_id}"
            if key not in existing_targets:
                self._curiosity_goals.append({
                    'type': 'investigate_contradiction',
                    'priority': 0.9,
                    'target': key,
                    'target_ids': [a_id, b_id],
                    'created_block': block_height,
                    'status': 'pending',
                })
                generated += 1

        # 3. Orphaned high-confidence nodes (few edges)
        try:
            _nodes_snap = list(self.kg.nodes.values())
        except RuntimeError:
            _nodes_snap = []
        orphans = [
            n for n in _nodes_snap
            if len(n.edges_out) + len(n.edges_in) <= 1
            and n.confidence > 0.5
            and n.node_type in ('inference', 'assertion')
        ]
        for orphan in orphans[:2]:
            key = f"bridge_{orphan.node_id}"
            if key not in existing_targets:
                self._curiosity_goals.append({
                    'type': 'bridge_gap',
                    'priority': 0.7,
                    'target': key,
                    'target_ids': [orphan.node_id],
                    'created_block': block_height,
                    'status': 'pending',
                })
                generated += 1

        # 4. Pending predictions to verify
        if self.temporal_engine and 'verify_pred' not in existing_targets:
            try:
                if hasattr(self.temporal_engine, '_pending_predictions'):
                    pending_preds = getattr(
                        self.temporal_engine, '_pending_predictions', []
                    )
                    if pending_preds:
                        self._curiosity_goals.append({
                            'type': 'verify_prediction',
                            'priority': 0.8,
                            'target': 'verify_pred',
                            'created_block': block_height,
                            'status': 'pending',
                        })
                        generated += 1
            except Exception as e:
                logger.debug("Could not generate curiosity goals: %s", e)

        # Sort by priority descending and trim to max cap
        self._curiosity_goals.sort(
            key=lambda g: g.get('priority', 0), reverse=True
        )
        if len(self._curiosity_goals) > self._max_curiosity_goals:
            self._curiosity_goals = self._curiosity_goals[:self._max_curiosity_goals]

        self._curiosity_stats['goals_generated'] += generated
        return generated

    # ------------------------------------------------------------------ #
    #  Phase 5.4 — Emergent Communication Protocol                        #
    # ------------------------------------------------------------------ #

    def create_knowledge_digest(self, block_height: int,
                                since_block: int = None) -> dict:
        """Create a compact digest of recent knowledge for P2P sharing.

        Collects the top-k highest-confidence new nodes and recent edges
        since ``since_block`` and packages them as a lightweight digest
        suitable for gossip propagation.

        Args:
            block_height: Current block height.
            since_block: Include changes since this block (default: -100).

        Returns:
            Dict with ``block_height``, ``new_nodes``, ``new_edges``,
            ``digest_hash``, ``timestamp``.
        """
        if not self.kg:
            return {}

        import hashlib
        since = since_block if since_block is not None else max(0, block_height - 100)

        # Collect recent nodes (top-20 by confidence)
        recent_nodes = sorted(
            [n for n in self.kg.nodes.values() if n.source_block >= since],
            key=lambda n: n.confidence,
            reverse=True,
        )[:20]

        new_nodes = [
            {
                'node_id': n.node_id,
                'node_type': n.node_type,
                'content_hash': n.content_hash if hasattr(n, 'content_hash') and n.content_hash else '',
                'confidence': round(n.confidence, 4),
                'domain': n.domain or '',
            }
            for n in recent_nodes
        ]

        # Collect recent edges
        recent_edges = [
            e for e in self.kg.edges
            if any(
                self.kg.nodes.get(e.from_node_id)
                and self.kg.nodes[e.from_node_id].source_block >= since
                for _ in [None]
            )
        ][:50]

        new_edges = [
            {
                'from_id': e.from_node_id,
                'to_id': e.to_node_id,
                'edge_type': e.edge_type,
                'weight': round(e.weight, 4),
            }
            for e in recent_edges
        ]

        # Compute digest hash for dedup
        raw = json.dumps({
            'block': block_height,
            'nodes': len(new_nodes),
            'edges': len(new_edges),
            'ts': time.time(),
        }, sort_keys=True)
        digest_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]

        return {
            'block_height': block_height,
            'timestamp': time.time(),
            'new_nodes': new_nodes,
            'new_edges': new_edges,
            'digest_hash': digest_hash,
        }

    def merge_knowledge_digest(self, digest: dict) -> dict:
        """Merge a knowledge digest received from a peer node.

        For each node in the digest:
        - If we have a node with the same content_hash, boost its confidence
          by 0.02 (multi-node consensus).
        - If we don't have it, create a placeholder observation with reduced
          confidence (0.3) and ``grounding_source='peer_digest'``.

        For each edge: create if both endpoint nodes exist and the edge
        doesn't already exist.

        Args:
            digest: Knowledge digest dict from a peer.

        Returns:
            Stats dict with nodes_boosted, nodes_created, edges_created,
            was_duplicate.
        """
        stats = {
            'nodes_boosted': 0, 'nodes_created': 0,
            'edges_created': 0, 'was_duplicate': False,
        }

        if not self.kg or not digest:
            return stats

        # Dedup check
        digest_hash = digest.get('digest_hash', '')
        if digest_hash in self._seen_digests:
            stats['was_duplicate'] = True
            return stats

        self._seen_digests[digest_hash] = True
        # Cap seen digests — dict preserves insertion order, so we keep newest
        if len(self._seen_digests) > self._max_seen_digests:
            keys = list(self._seen_digests.keys())
            evict_count = len(keys) - self._max_seen_digests + self._max_seen_digests // 10
            for k in keys[:evict_count]:
                del self._seen_digests[k]

        self._digests_received += 1

        # Build content_hash → node_id lookup
        hash_to_node: Dict[str, int] = {}
        for node in self.kg.nodes.values():
            ch = getattr(node, 'content_hash', '')
            if ch:
                hash_to_node[ch] = node.node_id

        # Process nodes
        for n_info in digest.get('new_nodes', []):
            content_hash = n_info.get('content_hash', '')
            if content_hash and content_hash in hash_to_node:
                # Boost existing node's confidence (peer consensus)
                existing = self.kg.nodes.get(hash_to_node[content_hash])
                if existing:
                    existing.confidence = min(1.0, existing.confidence + 0.02)
                    stats['nodes_boosted'] += 1
                    self._peer_consensus_boosts += 1
            else:
                # Create placeholder node
                placeholder = self.kg.add_node(
                    node_type=n_info.get('node_type', 'observation'),
                    content={
                        'type': 'peer_knowledge',
                        'original_content_hash': content_hash,
                        'source': 'peer_digest',
                    },
                    confidence=0.3,
                    source_block=digest.get('block_height', 0),
                    domain=n_info.get('domain', ''),
                )
                if placeholder:
                    placeholder.grounding_source = 'peer_digest'
                    stats['nodes_created'] += 1
                    self._nodes_from_peers += 1

        # Process edges
        for e_info in digest.get('new_edges', []):
            from_id = e_info.get('from_id')
            to_id = e_info.get('to_id')
            if (from_id in self.kg.nodes and to_id in self.kg.nodes):
                # Check if edge already exists
                existing = False
                for edge in self.kg.get_edges_from(from_id):
                    if edge.to_node_id == to_id and edge.edge_type == e_info.get('edge_type', ''):
                        existing = True
                        break
                if not existing:
                    self.kg.add_edge(
                        from_id, to_id,
                        e_info.get('edge_type', 'supports'),
                        weight=e_info.get('weight', 1.0),
                    )
                    stats['edges_created'] += 1

        return stats

    def _load_persisted_counters(self) -> None:
        """Load AGI subsystem counters from DB (survive restart)."""
        if not self.db:
            return
        try:
            from sqlalchemy import text
            with self.db.session() as session:
                rows = session.execute(
                    text("SELECT config_key, config_value FROM system_config WHERE category = 'agi_counters'")
                ).fetchall()
                counters = {row[0]: int(row[1]) for row in rows}
                self._contradictions_resolved = counters.get('contradictions_resolved', 0)
                if self.debate_protocol and 'debates_run' in counters:
                    self.debate_protocol._debates_run = counters['debates_run']
                if self.temporal_engine:
                    if 'predictions_validated' in counters:
                        self.temporal_engine._predictions_validated = counters['predictions_validated']
                    if 'predictions_correct' in counters:
                        self.temporal_engine._predictions_correct = counters['predictions_correct']
                if counters:
                    logger.info(
                        "Restored AGI counters from DB: %s",
                        {k: v for k, v in counters.items()},
                    )
        except Exception as e:
            logger.debug(f"Could not load persisted AGI counters: {e}")

    def _persist_counters(self, block_height: int) -> None:
        """Persist AGI subsystem counters to DB (every 500 blocks)."""
        if not self.db:
            return
        try:
            from sqlalchemy import text
            counters = {
                'contradictions_resolved': getattr(self, '_contradictions_resolved', 0),
            }
            if self.debate_protocol:
                counters['debates_run'] = getattr(self.debate_protocol, '_debates_run', 0)
            if self.temporal_engine:
                counters['predictions_validated'] = getattr(
                    self.temporal_engine, '_predictions_validated', 0
                )
                counters['predictions_correct'] = getattr(
                    self.temporal_engine, '_predictions_correct', 0
                )
            with self.db.session() as session:
                for key, value in counters.items():
                    session.execute(
                        text(
                            "UPSERT INTO system_config "
                            "(config_key, config_value, config_type, category, description, is_mutable) "
                            "VALUES (:key, :val, 'integer', 'agi_counters', :desc, true)"
                        ),
                        {'key': key, 'val': str(value), 'desc': f'AGI counter: {key}'},
                    )
                session.commit()
        except Exception as e:
            logger.debug(f"Could not persist AGI counters: {e}")

    def get_stats(self) -> dict:
        """Get comprehensive Aether engine statistics"""
        kg_stats = self.kg.get_stats() if self.kg else {}
        # Use cached phi result if available (avoids expensive recomputation)
        phi_result = {}
        if self.phi:
            # Use cached result — never trigger a blocking full recompute here
            phi_result = self.phi.get_cached()
        reasoning_stats = self.reasoning.get_stats() if self.reasoning else {}

        stats = {
            'knowledge_graph': kg_stats,
            'phi': {
                'current_value': phi_result.get('phi_value', 0.0),
                'threshold': phi_result.get('phi_threshold', 3.0),
                'above_threshold': phi_result.get('above_threshold', False),
                'version': phi_result.get('phi_version', 3),
                'gates_passed': phi_result.get('gates_passed', 0),
            },
            'reasoning': reasoning_stats,
            'thought_proofs_generated': len(self._pot_cache),
            'blocks_processed': self._blocks_processed,
            'contradictions_resolved': getattr(self, '_contradictions_resolved', 0),
        }

        # AGI-014: Emotional state
        try:
            if hasattr(self, 'emotional_state') and self.emotional_state:
                es = self.emotional_state.states
                if es:
                    emotions = {k: round(v, 4) for k, v in es.items() if isinstance(v, (int, float))}
                    dominant = max(emotions, key=emotions.get) if emotions else ''
                    stats['emotional_state'] = {
                        'emotions': emotions,
                        'dominant': dominant,
                    }
        except Exception:
            pass

        # AGI-014: Self-improvement stats
        try:
            if hasattr(self, 'self_improvement') and self.self_improvement:
                si = self.self_improvement
                stats['self_improvement'] = {
                    'cycles_completed': getattr(si, '_cycles_completed', 0),
                    'total_adjustments': getattr(si, '_total_adjustments', 0),
                    'rollbacks': getattr(si, '_rollbacks', 0),
                }
        except Exception:
            pass

        # AGI-014: Prediction accuracy summary
        try:
            if hasattr(self, 'temporal_engine') and self.temporal_engine:
                te = self.temporal_engine
                pv = int(getattr(te, '_predictions_validated', 0))
                pc = int(getattr(te, '_predictions_correct', 0))
                stats['prediction_summary'] = {
                    'validated': pv,
                    'correct': pc,
                    'accuracy': round(pc / max(pv, 1), 4),
                }
        except Exception:
            pass

        # AGI subsystem stats
        if self.neural_reasoner:
            stats['neural_reasoner'] = self.neural_reasoner.get_stats()
        if self.causal_engine:
            stats['causal_engine'] = self.causal_engine.get_stats()
        if self.debate_protocol:
            stats['debate_protocol'] = self.debate_protocol.get_stats()
        if self.temporal_engine:
            stats['temporal_engine'] = self.temporal_engine.get_stats()
        if self.concept_formation:
            stats['concept_formation'] = self.concept_formation.get_stats()
        if self.metacognition:
            stats['metacognition'] = self.metacognition.get_stats()
        if self.memory_manager:
            stats['memory_manager'] = self.memory_manager.get_stats()

        # Phase 5.1: Curiosity stats
        stats['curiosity'] = {
            **self._curiosity_stats,
            'current_queue_size': len(self._curiosity_goals),
            'pending_goals': len(
                [g for g in self._curiosity_goals if g['status'] == 'pending']
            ),
            'mcts_action_queue_size': len(self._mcts_action_queue),
        }

        # #38: MCTS planner stats
        if self.mcts_planner:
            stats['mcts_planner'] = self.mcts_planner.get_stats()

        # Phase 5.4: Knowledge sharing stats
        stats['knowledge_sharing'] = {
            'digests_created': self._digests_created,
            'digests_received': self._digests_received,
            'nodes_from_peers': self._nodes_from_peers,
            'peer_consensus_boosts': self._peer_consensus_boosts,
        }

        # SUSY balance enforcement stats
        susy_stats: dict = {'corrections': 0, 'violations': 0}
        sephirot_mgr = self._sephirot_manager
        if sephirot_mgr is None and self.pineal is not None:
            sephirot_mgr = getattr(self.pineal, 'sephirot', None)
        if sephirot_mgr is not None:
            susy_stats['corrections'] = getattr(sephirot_mgr, '_total_corrections', 0)
            susy_stats['violations'] = len(getattr(sephirot_mgr, 'violations', []))
        stats['susy_balance'] = susy_stats

        # Phase 6: On-chain integration stats
        if self.on_chain:
            stats['on_chain'] = self.on_chain.get_stats()

        # #49: External data ingestion
        if self.external_ingestion:
            stats['external_ingestion'] = self.external_ingestion.get_stats()

        # Phase 7: TransE KG Embeddings (Item #33)
        if self.kg_embeddings:
            stats['kg_embeddings'] = self.kg_embeddings.get_stats()

        # Phase 7: Hopfield Memory (Item #40)
        if self.hopfield_memory:
            stats['hopfield_memory'] = self.hopfield_memory.get_stats()

        # #23: Transformer Reasoner
        if self.transformer_reasoner:
            stats['transformer_reasoner'] = self.transformer_reasoner.get_stats()

        # #24: Attention Memory
        if self.attention_memory:
            stats['attention_memory'] = self.attention_memory.get_stats()

        # #27: RL Planner
        if self.rl_planner:
            stats['rl_planner'] = self.rl_planner.get_stats()

        # #28: Contrastive Concepts
        if self.contrastive_concepts:
            stats['contrastive_concepts'] = self.contrastive_concepts.get_stats()

        # #29: Debate Scorer
        if self.debate_scorer:
            stats['debate_scorer'] = self.debate_scorer.get_stats()

        # #34: IIT Approximator
        if self.iit_approximator:
            stats['iit_approximator'] = self.iit_approximator.get_stats()

        # #35: Sephirot Attention
        if self.sephirot_attention:
            stats['sephirot_attention'] = self.sephirot_attention.get_stats()

        # #36: Knowledge VAE
        if self.knowledge_vae:
            stats['knowledge_vae'] = self.knowledge_vae.get_stats()

        # #39: Neural Calibrator
        if self.neural_calibrator:
            stats['neural_calibrator'] = self.neural_calibrator.get_stats()

        # #41: NLP Pipeline
        if self.nlp_pipeline:
            stats['nlp_pipeline'] = self.nlp_pipeline.get_stats()

        # #43: Blockchain Entity Extractor
        if self.blockchain_entity_extractor:
            stats['blockchain_entity_extractor'] = self.blockchain_entity_extractor.get_stats()

        # #44: Semantic Similarity
        if self.semantic_similarity:
            stats['semantic_similarity'] = self.semantic_similarity.get_stats()

        # #45: Sentiment Analyzer
        if self.sentiment_analyzer:
            stats['sentiment_analyzer'] = self.sentiment_analyzer.get_stats()

        # #46: KG Summarizer
        if self.kg_summarizer:
            stats['kg_summarizer'] = self.kg_summarizer.get_stats()

        # #48: KGQA
        if self.kgqa:
            stats['kgqa'] = self.kgqa.get_stats()

        # #76: Global Workspace
        if self.global_workspace:
            stats['global_workspace'] = self.global_workspace.get_stats()

        # #77: Attention Schema
        if self.attention_schema:
            stats['attention_schema'] = self.attention_schema.get_stats()

        # #78: Predictive Processing
        if self.predictive_processing:
            stats['predictive_processing'] = self.predictive_processing.get_stats()

        # #79: Embodied Grounding
        if self.embodied_grounding:
            stats['embodied_grounding'] = self.embodied_grounding.get_stats()

        # #80: Sephirot Recurrent
        if self.sephirot_recurrent:
            stats['sephirot_recurrent'] = self.sephirot_recurrent.get_stats()

        # #81: Cross-Modal Binding
        if self.cross_modal_binding:
            stats['cross_modal_binding'] = self.cross_modal_binding.get_stats()

        # #82: Phi Partition
        if self.phi_partition:
            stats['phi_partition'] = self.phi_partition.get_stats()

        # #83: Phenomenal State
        if self.phenomenal_state:
            stats['phenomenal_state'] = self.phenomenal_state.get_stats()

        # #84: Self-Model
        if self.self_model:
            stats['self_model'] = self.self_model.get_stats()

        # #85: Emotional Valence
        if self.emotional_valence:
            stats['emotional_valence'] = self.emotional_valence.get_stats()

        # #86: Empathic Model
        if self.empathic_model:
            stats['empathic_model'] = self.empathic_model.get_stats()

        # #87: Narrative Coherence
        if self.narrative_coherence:
            stats['narrative_coherence'] = self.narrative_coherence.get_stats()

        # #88: Transfer Learning
        if self.transfer_learning:
            stats['transfer_learning'] = self.transfer_learning.get_stats()

        # #89: Few-Shot Learner
        if self.few_shot_learner:
            stats['few_shot_learner'] = self.few_shot_learner.get_stats()

        # #90: Continual Learning
        if self.continual_learning:
            stats['continual_learning'] = self.continual_learning.get_stats()

        # #91: Counterfactual Reasoning
        if self.counterfactual:
            stats['counterfactual'] = self.counterfactual.get_stats()

        # #92: Analogical Transfer
        if self.analogical_transfer:
            stats['analogical_transfer'] = self.analogical_transfer.get_stats()

        # #93: Dream Consolidation
        if self.dream_consolidation:
            stats['dream_consolidation'] = self.dream_consolidation.get_stats()

        # #94: Phi Gate Attention
        if self.phi_gate_attention:
            stats['phi_gate_attention'] = self.phi_gate_attention.get_stats()

        # #95: Adversarial Defense
        if self.adversarial_defense:
            stats['adversarial_defense'] = self.adversarial_defense.get_stats()

        # #96: Safety Verifier
        if self.safety_verifier:
            stats['safety_verifier'] = self.safety_verifier.get_stats()

        # #97: Distributed Phi
        if self.distributed_phi:
            stats['distributed_phi'] = self.distributed_phi.get_stats()

        # #98: Cognitive Load
        if self.cognitive_load:
            stats['cognitive_load'] = self.cognitive_load.get_stats()

        # #99: Meta-Learner
        if self.meta_learner:
            stats['meta_learner'] = self.meta_learner.get_stats()

        # #100: Recursive Improvement
        if self.recursive_improvement:
            stats['recursive_improvement'] = self.recursive_improvement.get_stats()

        # Blocks processed counter
        stats['blocks_processed'] = self._blocks_processed

        return stats

    def get_subsystem_health_detailed(self) -> Dict[str, dict]:
        """Return detailed health with per-subsystem stats for dashboard.

        Unlike get_subsystem_health() which covers all 50+ subsystems,
        this method returns richer stats for key subsystems only.
        """
        subsystems: Dict[str, dict] = {}

        detail_checks = [
            ('neural_reasoner', self.neural_reasoner, lambda s: {
                'active': s.get('total_trainings', 0) > 0 or s.get('total_inferences', 0) > 0,
                'trainings': s.get('total_trainings', 0),
                'inferences': s.get('total_inferences', 0),
            }),
            ('causal_engine', self.causal_engine, lambda s: {
                'active': s.get('discoveries', 0) > 0,
                'discoveries': s.get('discoveries', 0),
            }),
            ('debate_protocol', self.debate_protocol, lambda s: {
                'active': s.get('debates_run', 0) > 0,
                'debates_run': s.get('debates_run', 0),
            }),
            ('temporal_engine', self.temporal_engine, lambda s: {
                'active': s.get('blocks_processed', 0) > 0,
                'predictions': s.get('predictions_made', 0),
            }),
            ('concept_formation', self.concept_formation, lambda s: {
                'active': s.get('concepts_formed', 0) > 0,
                'concepts_formed': s.get('concepts_formed', 0),
            }),
            ('metacognition', self.metacognition, lambda s: {
                'active': s.get('evaluations', 0) > 0,
                'evaluations': s.get('evaluations', 0),
                'calibration_error': s.get('calibration_error', None),
            }),
            ('memory_manager', self.memory_manager, lambda s: {
                'active': s.get('total_memories', 0) > 0,
                'total_memories': s.get('total_memories', 0),
            }),
        ]

        for name, subsystem, extract in detail_checks:
            info: dict = {'initialized': subsystem is not None, 'active': False, 'error': None}
            if subsystem:
                try:
                    s = subsystem.get_stats()
                    info.update(extract(s))
                except Exception as e:
                    info['error'] = str(e)
            subsystems[name] = info

        return subsystems
