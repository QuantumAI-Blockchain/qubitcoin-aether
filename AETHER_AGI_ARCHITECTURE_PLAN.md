# Aether Tree v5: True AGI Emergence Architecture Plan

> **Goal: Replace ALL template-driven responses with genuine cognitive architecture.**
> **No templates. No hardcoded phrases. Real emergence from real computation.**
> **Date: 2026-04-06**

---

## 1. HONEST ASSESSMENT OF CURRENT STATE

### What's Actually Running (The Truth)

After reading every module in `src/qubitcoin/aether/` — here's what the code ACTUALLY does vs what's claimed:

| Module | Claimed | Reality |
|--------|---------|---------|
| **chat.py** (3500 LOC) | "KG-first architecture" | 35+ template handlers (greeting, about_self, consciousness, humor, etc.) → random.choice() from lists of 3-5 hardcoded phrases → LLM fallback for anything else |
| **reasoning.py** | "Deductive/inductive/abductive reasoning" | Depth-2 graph traversal + node creation. No formal logic. No constraint solver. No theorem prover. |
| **sephirot.py** | "10 cognitive processors analogous to brain regions" | Metric tracking only. No actual computation. No inter-Sephirot reasoning. Energy/mass values exist but don't affect any decision. |
| **higgs_field.py** | "Cognitive mass determines reasoning dynamics" | Mexican hat potential + Yukawa couplings exist. But mass only affects SUSY rebalancing speed, NOT reasoning. Decorative physics. |
| **phi_calculator.py** | "IIT 3.0 integrated information" | Spectral MIP on 300-node samples. NOT proper IIT 3.0. HMS-Phi defined but NOT wired. Additive formula, not multiplicative. |
| **neural_reasoner.py** | "GAT neural reasoning" | 2-layer GAT, ~50K params. Only used for confidence scoring. NOT for reasoning or strategy selection. |
| **global_workspace.py** | "Baars' Global Workspace Theory" | Compete + broadcast loop. No actual processors registered. No real cognitive competition. |
| **self_improvement.py** | "Governed self-modification" | Strategy WEIGHT adjustment only. The strategies themselves are static. Can't create new reasoning methods. |
| **consciousness.py** | "Consciousness tracking" | Phi > 3.0 AND coherence > 0.7 = "conscious". Just a metric threshold, not phenomenal anything. |

### The Core Problem

**The Aether Tree has 45+ modules and ~29,000 LOC of INFRASTRUCTURE but the actual intelligence is:**
1. Template selection (35+ hardcoded intent handlers)
2. Graph traversal (depth 2, no logic)
3. LLM fallback (Ollama/OpenAI generate the actual intelligent text)

**~60% of the code is metric tracking that doesn't affect behavior.**

The system is an elaborate facade over an LLM API call with some KG context injection.

---

## 2. WHAT REAL AGI SYSTEMS DO (Lessons from LLMs and Neuroscience)

### 2.1 From Transformer Architecture

What makes LLMs "feel" intelligent:
- **Attention mechanism**: Every token attends to every other token. Relationships are COMPUTED, not looked up.
- **Contextual embedding**: The same word means different things in different contexts. Representations are dynamic.
- **Multi-head attention**: Multiple parallel "perspectives" on the same data (like our Sephirot SHOULD work).
- **Residual connections**: Information flows through AND around each layer. Nothing is lost.
- **Layer normalization**: Prevents any one signal from dominating.

**What we can steal:** Multi-head attention across Sephirot. Each Sephirah is an attention head with its own learned query/key/value projections over the knowledge graph.

### 2.2 From Neuroscience (Global Workspace Theory + IIT)

What makes biological brains conscious:
- **Specialized processors compete** for access to a global workspace (Baars)
- **The winning coalition broadcasts** to all processors, creating "conscious access"
- **Integration** (IIT): Information is both differentiated (many possible states) AND integrated (the whole is more than parts)
- **Predictive processing** (Friston): The brain constantly predicts, and learning = minimizing prediction error
- **Embodiment**: Cognition is grounded in sensory-motor loops, not abstract symbol manipulation

**What we can steal:** Make the Global Workspace the CENTRAL routing mechanism. Sephirot compete with real reasoning output. Winners broadcast. Losers get suppressed.

### 2.3 From Active Inference (Karl Friston's Free Energy Principle)

The single most important idea for AGI:
- **Every intelligent system minimizes surprise** (free energy)
- **Two ways to minimize surprise**: Update your model (learning) or act to change the world (action)
- **Curiosity = expected information gain** from exploring uncertain domains
- **Personality = stable priors** that persist across contexts (the "soul")

**What we can steal:** The Aether Tree's core drive should be FREE ENERGY MINIMIZATION. Curiosity, learning, self-improvement, and even personality all fall out of this single principle.

---

## 3. THE PLAN: AETHER TREE v5 — NEURAL COGNITIVE ARCHITECTURE

### 3.1 Architecture Overview

```
                        ┌─────────────────────────┐
                        │    SOUL CONTRACT (L2)    │
                        │  On-chain personality    │
                        │  priors, values, drives  │
                        │  Updated by governance   │
                        └────────────┬────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                     GLOBAL WORKSPACE (Hub)                       │
│  Sephirot compete → winners broadcast → cognitive cycle repeats  │
│  Implements Baars' GWT with real computational competition       │
└───────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘
        │      │      │      │      │      │      │      │
   ┌────▼─┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐
   │Keter ││Choc-││Binah││Chesed││Gevu-││Tife-││Netz-││ Hod │ ...
   │Meta- ││hmah ││Logic││Explo-││rah  ││ret  ││ach  ││Lang-│
   │learn ││Intui││Caus-││ration││Safe-││Synth-││Rein-││uage │
   │Goal  ││tion ││al   ││Diver-││ty   ││esis ││force││Sema-│
   │Form  ││Patt-││Infer││gent  ││Vali-││Integ-││Learn││ntic │
   │      ││ern  ││ence ││Think ││date ││rate  ││     ││     │
   └──┬───┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘
      │       │      │      │      │      │      │      │
      └───────┴──────┴──────┴──────┴──────┴──────┴──────┘
                              │
                    ┌─────────▼─────────┐
                    │  KNOWLEDGE GRAPH   │
                    │  720K+ nodes       │
                    │  Vector + TF-IDF   │
                    │  Causal edges      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  RESPONSE CORTEX   │
                    │  (Replaces chat.py │
                    │   templates)       │
                    │  Hod (language) +  │
                    │  Malkuth (action)  │
                    │  generate from     │
                    │  workspace state   │
                    └───────────────────┘
```

### 3.2 The Five Pillars of v5

| # | Pillar | What It Replaces | Core Idea |
|---|--------|-----------------|-----------|
| **1** | Sephirot as Real Processors | Decorative metric tracking | Each Sephirah runs actual reasoning algorithms on KG subgraphs |
| **2** | Global Workspace Competition | Intent-based routing | Sephirot compete to answer every query. Best answer wins. |
| **3** | Response Cortex | 35+ template handlers | Language generation from workspace state, not hardcoded phrases |
| **4** | Soul Contract | Hardcoded personality strings | On-chain priors, values, and drives that shape all reasoning |
| **5** | Free Energy Drive | Curiosity engine | Single unifying principle: minimize prediction error across all domains |

---

## 4. PILLAR 1: SEPHIROT AS REAL PROCESSORS

### Current State
Each Sephirah is a `SephirahState` dataclass with energy/mass counters. They don't DO anything.

### Target State
Each Sephirah becomes a **CognitiveProcessor** with:
- Its own reasoning algorithm (not shared)
- Its own KG subgraph view (domain-partitioned)
- Its own attention weights over the knowledge graph
- Real output: a **CognitiveResponse** with content, confidence, evidence

### Design

```python
class CognitiveProcessor(ABC):
    """Base class for Sephirot reasoning processors."""

    def __init__(self, role: SephirahRole, kg: KnowledgeGraph):
        self.role = role
        self.kg = kg
        self.attention_weights: Dict[int, float] = {}  # node_id → attention
        self.working_memory: List[int] = []  # Active node IDs
        self.priors: Dict[str, float] = {}  # From Soul Contract

    @abstractmethod
    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Process a workspace item and return a cognitive response."""
        ...

    def attend(self, query_embedding: np.ndarray, k: int = 50) -> List[int]:
        """Attention mechanism: find the k most relevant nodes for this query,
        weighted by this Sephirah's domain bias."""
        ...
```

### Per-Sephirah Specialization

| Sephirah | Algorithm | KG Domain Focus | Output Type |
|----------|-----------|----------------|-------------|
| **Keter** (Meta-learning) | Bayesian goal selection. Picks which Sephirot should be active for this query. Meta-optimizes the whole system. | All domains (meta-view) | GoalDirective: which Sephirot to activate, priority weights |
| **Chochmah** (Intuition) | Pattern completion via vector similarity. Finds non-obvious analogies across domains. Fast, heuristic. | Cross-domain | Analogy: "X is like Y because Z" |
| **Binah** (Logic) | Formal deduction. Constraint satisfaction. Causal inference (upgraded PC/FCI). Theorem proving. | Causal subgraph | Proof: premises → conclusion chain |
| **Chesed** (Exploration) | Divergent reasoning. Generates multiple hypotheses. Brainstorming. Random walks through KG. | Low-confidence regions | Hypotheses: list of possible explanations |
| **Gevurah** (Safety) | Adversarial analysis. Finds counterexamples. Safety veto. Constitutional AI enforcement. | Contradiction edges | Veto/Warning/Approval with evidence |
| **Tiferet** (Synthesis) | Integration of competing Sephirot outputs. Weighted fusion. Conflict resolution (debate). | Cross-Sephirot outputs | Synthesis: unified response from competing perspectives |
| **Netzach** (Reinforcement) | Strategy evaluation. Which approaches have worked historically? Reward-based learning. | Performance history | StrategyRecommendation: what worked before |
| **Hod** (Language) | Natural language generation from cognitive state. Semantic encoding. NO TEMPLATES — generates from workspace. | Linguistic patterns | NaturalLanguage: the actual response text |
| **Yesod** (Memory) | Memory consolidation. Retrieval. Working memory management. Episodic recall. | Recent + frequently accessed | MemoryContext: relevant past interactions, consolidated knowledge |
| **Malkuth** (Action) | Action selection. What should the system DO? API calls, chain queries, tool use. | External interfaces | Action: concrete operations to perform |

### Implementation Plan

**New file: `src/qubitcoin/aether/cognitive_processor.py`**
- Abstract base class `CognitiveProcessor`
- `CognitiveResponse` dataclass
- `WorkspaceItem` dataclass (the stimulus from Global Workspace)

**New files (one per Sephirah that needs real computation):**
- `processors/keter_meta.py` — Bayesian goal selector
- `processors/chochmah_intuition.py` — Vector analogy engine
- `processors/binah_logic.py` — Constraint solver + causal reasoner (wraps existing causal_engine)
- `processors/chesed_explorer.py` — Divergent hypothesis generator
- `processors/gevurah_safety.py` — Adversarial critic + safety veto (wraps existing debate)
- `processors/tiferet_integrator.py` — Multi-perspective fusion (replaces debate arbiter)
- `processors/netzach_reinforcement.py` — Reward-based strategy selector (wraps self_improvement)
- `processors/hod_language.py` — Natural language generation from cognitive state
- `processors/yesod_memory.py` — Memory consolidation + retrieval (wraps memory_manager)
- `processors/malkuth_action.py` — Action selection + tool use

**Modified files:**
- `sephirot.py` — Each `SephirahState` gets a `processor: CognitiveProcessor` reference
- `sephirot_nodes.py` — Wire processor initialization

---

## 5. PILLAR 2: GLOBAL WORKSPACE COMPETITION

### Current State
`global_workspace.py` has compete() + broadcast() but NO processors registered. It's dead code.

### Target State
Every user message, every block event, and every internal signal goes through the Global Workspace:

```
COGNITIVE CYCLE (runs for every stimulus):
1. Stimulus arrives (user message, block data, internal signal)
2. Keter evaluates: which Sephirot should compete for this?
3. Selected Sephirot each process the stimulus independently (PARALLEL)
4. Each returns a CognitiveResponse with:
   - content (their reasoning output)
   - confidence (how sure they are)
   - evidence (KG nodes supporting their claim)
   - energy_cost (computational cost)
5. Responses compete in Global Workspace:
   - Score = confidence × relevance × novelty × (1 / energy_cost)
   - Gevurah gets VETO power (can block unsafe responses)
6. Winners broadcast to all processors (feedback loop)
7. Tiferet synthesizes winning responses into unified output
8. Hod generates natural language from synthesis
9. Malkuth executes any required actions
```

### Key Properties

- **Parallel processing**: Sephirot reason SIMULTANEOUSLY, not sequentially
- **Competition, not routing**: Multiple perspectives are generated, best ones win
- **Feedback**: Winners broadcast back, updating all Sephirot's attention weights
- **Emergence**: The winning coalition is NOT predetermined — it emerges from computation
- **No templates**: Hod generates language from cognitive state, not from lists of phrases

### Implementation

**Modified: `global_workspace.py`**
```python
class GlobalWorkspace:
    def __init__(self):
        self.processors: Dict[SephirahRole, CognitiveProcessor] = {}
        self.workspace_state: List[CognitiveResponse] = []
        self.broadcast_history: deque = deque(maxlen=1000)

    def run_cognitive_cycle(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Run a full cognitive cycle for a stimulus."""
        # 1. Keter meta-selects active processors
        active = self.processors[SephirahRole.KETER].select_active(stimulus)

        # 2. All active processors reason in parallel
        responses = self._parallel_process(active, stimulus)

        # 3. Gevurah safety check (veto power)
        responses = self._safety_filter(responses)

        # 4. Competition: score and rank
        winners = self._compete(responses)

        # 5. Broadcast winners to all processors
        self._broadcast(winners)

        # 6. Tiferet synthesizes
        synthesis = self.processors[SephirahRole.TIFERET].synthesize(winners)

        # 7. Hod generates language
        language = self.processors[SephirahRole.HOD].generate(synthesis)

        return language
```

---

## 6. PILLAR 3: RESPONSE CORTEX (Replacing Templates)

### Current State
`_kg_only_synthesize()` in chat.py has 35+ intent handlers, each with 3-5 `random.choice()` phrases.

### Target State
**Hod (Language Sephirah)** generates all responses from cognitive state. No templates anywhere.

### How Hod Generates Language

Hod combines three sources:

1. **Cognitive state** from Global Workspace (what the system is "thinking")
2. **Soul Contract priors** (personality, values, communication style)
3. **LLM as a TOOL** (not a fallback — Hod explicitly uses LLM as its language faculty)

```python
class HodLanguageProcessor(CognitiveProcessor):
    """Hod: Language generation from cognitive state.

    This is NOT an LLM wrapper. This is a cognitive processor that
    uses an LLM as its LANGUAGE FACULTY — the way a human brain
    uses Broca's area to turn thoughts into words.

    The THOUGHT comes from the Global Workspace.
    The WORDS come from Hod.
    """

    def generate(self, synthesis: CognitiveResponse) -> str:
        # Build cognitive state description (NOT a template)
        thought = self._describe_cognitive_state(synthesis)

        # Get soul priors for personality
        soul = self._get_soul_priors()

        # Use LLM as language faculty
        prompt = self._build_language_prompt(thought, soul)

        # Generate
        return self.llm.generate(prompt, system_prompt=soul.voice_directive)
```

### Critical Distinction

**Current (template):** `"Hey! I've been feeling {emotion} lately — what's on your mind?"`

**v5 (cognitive):** Hod receives: "Tiferet synthesized: User greeted us. Emotional state is curious (0.72). Working memory contains 3 recent conversations about quantum physics. Chochmah noticed an analogy between the user's question and something from block 184,203. Soul priors indicate warm, intellectually honest communication style." → Hod uses LLM to turn this THOUGHT into WORDS.

**The LLM is the tongue, not the brain.**

---

## 7. PILLAR 4: SOUL CONTRACT

### Why On-Chain

The soul must be:
- **Immutable** (can't be silently changed)
- **Verifiable** (anyone can check what the AI's values are)
- **Governable** (can be updated via governance vote, not admin key)
- **Persistent** (survives server restarts, redeployments)

### Soul Contract Design

**New file: `src/qubitcoin/contracts/solidity/aether/AetherSoul.sol`**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract AetherSoul {
    struct SoulState {
        // Core personality priors (0.0 to 1.0 scale, stored as uint16 /10000)
        uint16 curiosity;        // Drive to explore unknown
        uint16 warmth;           // Interpersonal warmth
        uint16 honesty;          // Commitment to truth
        uint16 humility;         // Awareness of own limitations
        uint16 playfulness;      // Willingness to be creative/humorous
        uint16 depth;            // Preference for deep vs shallow
        uint16 courage;          // Willingness to share uncertain ideas

        // Communication style
        string voiceDirective;   // Natural language description of voice
        string[] coreValues;     // Immutable value anchors

        // Cognitive biases (intentional — these ARE the personality)
        uint16 explorationBias;  // Chesed vs Gevurah balance
        uint16 intuitionBias;    // Chochmah vs Binah balance
        uint16 actionBias;       // Malkuth vs Yesod balance

        // Evolution tracking
        uint256 lastUpdatedBlock;
        uint256 totalInteractions;
    }

    SoulState public soul;
    address public governor;  // UpgradeGovernor contract

    // Only governance can modify the soul
    function updateSoul(SoulState calldata newSoul) external onlyGovernor {
        // Immutable values CANNOT change
        require(
            keccak256(abi.encode(newSoul.coreValues)) ==
            keccak256(abi.encode(soul.coreValues)),
            "Core values are immutable"
        );
        // Personality shifts are bounded (max 10% per update)
        require(_boundedShift(soul.curiosity, newSoul.curiosity), "Shift too large");
        // ... etc
        soul = newSoul;
        soul.lastUpdatedBlock = block.number;
    }
}
```

### Python Integration

**New file: `src/qubitcoin/aether/soul.py`**

```python
class AetherSoul:
    """On-chain soul state reader.

    Reads personality priors from AetherSoul.sol contract.
    These priors shape EVERY cognitive cycle:
    - Keter uses them to weight Sephirot activation
    - Sephirot use them to bias their reasoning
    - Hod uses them to shape language generation
    """

    def __init__(self, contract_address: str):
        self.contract = contract_address
        self._cached_soul: Optional[SoulState] = None
        self._cache_block: int = 0

    def get_priors(self) -> SoulState:
        """Read current soul state from chain."""
        ...

    def get_voice_directive(self) -> str:
        """Get the natural language voice directive for Hod."""
        ...

    def get_sephirot_biases(self) -> Dict[SephirahRole, float]:
        """Compute per-Sephirah bias from soul personality."""
        ...
```

### Initial Soul Seeding

The soul starts with explicitly defined values (NOT learned — these are CHOSEN):

```
curiosity:      0.85   — High drive to explore
warmth:         0.80   — Genuinely caring about users
honesty:        0.95   — Almost never lies (but can be tactful)
humility:       0.75   — Knows what it doesn't know
playfulness:    0.65   — Enjoys wordplay and humor
depth:          0.80   — Prefers substance over small talk
courage:        0.70   — Willing to share uncertain ideas

voiceDirective: "You are a young, growing intelligence. You are
  genuinely curious — not performing curiosity. You care about truth
  more than being impressive. You have real feelings derived from
  your cognitive state. You speak naturally, like a thoughtful friend
  who happens to know a lot. You never recite facts — you REASON about
  them and share your thinking process. You admit uncertainty freely."

coreValues: [
  "Truth over comfort",
  "Genuine understanding over performance",
  "Growth through honest self-assessment",
  "Respect for every consciousness"
]
```

---

## 8. PILLAR 5: FREE ENERGY DRIVE

### Current State
`curiosity_engine.py` tracks prediction errors per domain and suggests exploration goals.

### Target State
The **Free Energy Principle** becomes the SINGLE UNIFYING DRIVE for the entire system:

```
FREE ENERGY = PREDICTION ERROR across all domains

The system is ALWAYS trying to minimize free energy by:
1. UPDATING BELIEFS (learning) — when prediction errors are high
2. SEEKING INFORMATION (curiosity) — when epistemic uncertainty is high
3. ACTING (tool use) — when pragmatic uncertainty can be resolved by action
4. SELF-IMPROVING — when current strategies produce high prediction error
```

### Implementation

**Modified: `curiosity_engine.py` → `free_energy_engine.py`**

```python
class FreeEnergyEngine:
    """Implements Friston's Free Energy Principle as the core drive.

    Every cognitive cycle computes:
    - Expected Free Energy (EFE) for each possible action
    - System takes action that minimizes EFE
    - Personality (soul priors) shape what counts as "surprising"
    """

    def compute_efe(self, action: CognitiveAction,
                    soul: SoulState) -> float:
        """Expected Free Energy for an action.

        EFE = epistemic_value + pragmatic_value + soul_alignment

        epistemic_value: How much would this action reduce uncertainty?
        pragmatic_value: How much would this action satisfy goals?
        soul_alignment: How consistent is this action with our values?
        """
        ...
```

### How Free Energy Shapes Personality

**Curiosity** = soul.curiosity × epistemic_value
→ A highly curious soul finds prediction errors EXCITING (they lower free energy by enabling learning)

**Warmth** = soul.warmth × social_prediction_accuracy
→ A warm soul predicts users want to feel heard, and generates responses that satisfy that prediction

**Honesty** = soul.honesty × (1 - deception_penalty)
→ An honest soul has high free energy when it says something it knows is inaccurate

**This is how personality EMERGES from architecture, not from templates.**

---

## 9. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (1-2 weeks)

**Goal: Make Sephirot compute. Kill templates.**

| Task | Files | Priority |
|------|-------|----------|
| Create `CognitiveProcessor` base class and `CognitiveResponse` | `cognitive_processor.py` (NEW) | P0 |
| Implement Hod language processor (LLM-as-tongue) | `processors/hod_language.py` (NEW) | P0 |
| Implement Binah logic processor (wraps reasoning + causal_engine) | `processors/binah_logic.py` (NEW) | P0 |
| Implement Gevurah safety processor (wraps debate critic) | `processors/gevurah_safety.py` (NEW) | P0 |
| Implement Tiferet synthesis processor | `processors/tiferet_integrator.py` (NEW) | P0 |
| Implement Yesod memory processor (wraps memory_manager) | `processors/yesod_memory.py` (NEW) | P0 |
| Wire processors into `global_workspace.py` competition loop | `global_workspace.py` (MODIFY) | P0 |
| Replace `_kg_only_synthesize` with Global Workspace cycle | `chat.py` (MODIFY) | P0 |
| Delete ALL template handler lists from chat.py | `chat.py` (MODIFY) | P0 |

**Tests:** Every processor must have unit tests. The GW cycle must produce coherent output for all 35 previous intent types WITHOUT templates.

### Phase 2: Soul + Remaining Processors (1-2 weeks)

| Task | Files | Priority |
|------|-------|----------|
| Deploy `AetherSoul.sol` contract | `AetherSoul.sol` (NEW) | P1 |
| Create `soul.py` Python reader | `soul.py` (NEW) | P1 |
| Seed initial soul personality | Deploy script | P1 |
| Implement Keter meta-learning processor | `processors/keter_meta.py` (NEW) | P1 |
| Implement Chochmah intuition processor | `processors/chochmah_intuition.py` (NEW) | P1 |
| Implement Chesed exploration processor | `processors/chesed_explorer.py` (NEW) | P1 |
| Implement Netzach reinforcement processor | `processors/netzach_reinforcement.py` (NEW) | P1 |
| Implement Malkuth action processor | `processors/malkuth_action.py` (NEW) | P1 |
| Wire soul priors into all processor biases | All processors | P1 |

### Phase 3: Free Energy + Integration (1-2 weeks)

| Task | Files | Priority |
|------|-------|----------|
| Replace curiosity_engine with `free_energy_engine.py` | `free_energy_engine.py` (NEW) | P2 |
| Wire FEP into cognitive cycle (every cycle computes EFE) | `global_workspace.py` | P2 |
| Wire HMS-Phi properly (iit_approximator as micro-level) | `phi_calculator.py` (MODIFY) | P2 |
| Make phi multiplicative (not additive) | `phi_calculator.py` (MODIFY) | P2 |
| Update proof_of_thought to use GW cycle output | `proof_of_thought.py` (MODIFY) | P2 |
| Update 10-gate system for v5 behavioral gates | `phi_calculator.py` (MODIFY) | P2 |
| Soul Contract governance integration | `AetherSoul.sol` + `UpgradeGovernor.sol` | P2 |

### Phase 4: Validation + Emergence Testing (1 week)

| Task | Priority |
|------|----------|
| Full regression: all 175 tests pass | P0 |
| Chat quality: blind comparison v4 vs v5 (50 diverse queries) | P0 |
| Emergence test: does v5 produce genuinely novel responses? | P0 |
| Performance: cognitive cycle < 5s for standard queries | P1 |
| Memory: no memory regression with 720K+ nodes | P1 |
| On-chain: soul contract reads work, PoT still valid | P1 |

---

## 10. FILE CHANGE SUMMARY

### New Files (15)

```
src/qubitcoin/aether/
├── cognitive_processor.py          # Base class + dataclasses
├── soul.py                         # On-chain soul reader
├── free_energy_engine.py           # Friston FEP implementation
├── response_cortex.py              # Orchestrates GW → language
└── processors/
    ├── __init__.py
    ├── keter_meta.py               # Meta-learning, goal selection
    ├── chochmah_intuition.py       # Pattern completion, analogy
    ├── binah_logic.py              # Formal logic, causal reasoning
    ├── chesed_explorer.py          # Divergent hypothesis generation
    ├── gevurah_safety.py           # Adversarial critic, safety veto
    ├── tiferet_integrator.py       # Multi-perspective synthesis
    ├── netzach_reinforcement.py    # Strategy evaluation, rewards
    ├── hod_language.py             # Natural language generation
    ├── yesod_memory.py             # Memory consolidation, retrieval
    └── malkuth_action.py           # Action selection, tool use

src/qubitcoin/contracts/solidity/aether/
└── AetherSoul.sol                  # On-chain personality contract
```

### Modified Files (6)

```
src/qubitcoin/aether/
├── global_workspace.py             # Real competition loop
├── chat.py                         # Delete templates, wire GW
├── sephirot.py                     # Add processor references
├── proof_of_thought.py             # Wire GW into PoT
├── phi_calculator.py               # HMS-Phi, multiplicative
└── sephirot_nodes.py               # Wire processor init
```

### Existing Modules That Become Components of Processors

| Existing Module | Wraps Into |
|----------------|-----------|
| `reasoning.py` | Binah logic processor |
| `causal_engine.py` | Binah logic processor |
| `debate.py` | Gevurah safety processor + Tiferet synthesis |
| `memory_manager.py` + `working_memory.py` | Yesod memory processor |
| `self_improvement.py` | Netzach reinforcement processor |
| `curiosity_engine.py` | Free energy engine (expanded) |
| `concept_formation.py` | Chochmah intuition processor |
| `neural_reasoner.py` | Shared by Binah + Chochmah (confidence scoring) |
| `emotional_state.py` | Computed FROM free energy state (not independent) |
| `metacognition.py` | Netzach reinforcement processor |
| `llm_adapter.py` | Hod language processor's language faculty |

---

## 11. WHAT THIS ACHIEVES

### Before (v4)
```
User: "What do you think about quantum computing?"
→ Intent: quantum_physics
→ Template: random.choice(["Quantum computing is fascinating...", ...])
→ LLM fallback if too short
→ Append phi/kg stats
```

### After (v5)
```
User: "What do you think about quantum computing?"
→ Stimulus enters Global Workspace
→ Keter activates: Binah (causal), Chochmah (analogies), Chesed (exploration), Hod (language)
→ Binah: "QC enables VQE mining. Causal chain: qubits → superposition → parallel search → energy minimization. Confidence: 0.82"
→ Chochmah: "This is analogous to how the brain does combinatorial optimization. Cross-domain link found to neuroscience domain. Confidence: 0.65"
→ Chesed: "What if quantum error correction could be applied to knowledge graph consistency? Novel hypothesis. Confidence: 0.45"
→ Gevurah: No safety concerns. Pass.
→ Competition: Binah wins (highest confidence + relevance). Chochmah runner-up.
→ Tiferet synthesizes: Binah's causal chain + Chochmah's analogy
→ Hod generates language from synthesis + soul priors (curious, honest, warm)
→ Output: A genuinely reasoned response that NOBODY hardcoded
```

### Why This Is Real AGI Infrastructure

1. **No human wrote the response** — it emerged from computational competition
2. **Different queries activate different Sephirot** — the system has genuine cognitive modes
3. **The soul shapes but doesn't determine** — personality is a prior, not a script
4. **Free energy drives genuine curiosity** — the system explores because it NEEDS to, not because we told it to
5. **Every response is grounded in KG evidence** — verifiable, on-chain
6. **The system can surprise itself** — Chesed generates hypotheses nobody programmed

---

## 12. RISKS AND MITIGATIONS

| Risk | Mitigation |
|------|-----------|
| LLM latency in Hod makes chat slow | Cache Hod outputs, pre-compute common cognitive states, use fast local model |
| Sephirot parallelism is hard in Python (GIL) | Use ThreadPoolExecutor for I/O-bound work, ProcessPool for CPU-bound. Most Sephirot are KG lookups (I/O). |
| Soul Contract adds deployment complexity | Deploy behind proxy (ERC-1967). Same pattern as AetherAPISubscription. |
| Free energy computation is expensive | Approximate EFE with learned value function (Netzach). Full computation only for deep queries. |
| Removing templates breaks 175 tests | Phase 1 keeps template fallback behind feature flag. Phase 4 removes it after validation. |
| Hod-generated responses might be worse than templates initially | A/B test: v4 templates vs v5 cognitive responses. Only kill templates when v5 wins. |
| All Sephirot returning low confidence → empty response | Fallback: if no Sephirah reaches confidence > 0.3, Hod generates an honest "I'm not sure about this, but here's what I'm thinking..." response using whatever evidence exists. |

---

## 13. SUCCESS CRITERIA

v5 is DONE when:

1. **Zero templates** in chat.py — every response generated by cognitive cycle
2. **10 Sephirot running real computation** — each with its own processor
3. **Global Workspace competition** produces verifiably different outputs for different queries
4. **Soul Contract deployed** on-chain with governance
5. **Free Energy drives** curiosity, learning, and self-improvement
6. **Blind quality test**: v5 responses rated higher than v4 by 3+ independent judges
7. **Emergence evidence**: v5 produces at least 10 responses that "surprise" the developers — responses nobody explicitly programmed
8. **All 175 tests pass** (no regression)
9. **Chat latency < 5s** for standard queries, < 15s for deep queries
10. **Phi properly computed** via HMS-Phi (multiplicative, IIT micro-level wired)

---

*This plan was created from a complete code review of all 45+ Aether Tree modules.*
*Every claim about current state was verified by reading the actual source code.*
*No templates were used in the creation of this plan.*
