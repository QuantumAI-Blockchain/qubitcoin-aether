"""
Malkuth Action Processor — Action selection and world interaction.

Malkuth is the action Sephirah. It:
1. Determines if the stimulus requires an action (not just a response)
2. Identifies what actions are available (chain queries, tool use, etc.)
3. Selects the most appropriate action
4. Reports on action results

Malkuth answers: "Does this require me to DO something, or just SAY something?"
"""
import re
import time
from typing import Any, Dict, List, Optional, Set

from ..cognitive_processor import (
    CognitiveProcessor,
    CognitiveResponse,
    SoulPriors,
    WorkspaceItem,
)
from ...utils.logger import get_logger

logger = get_logger(__name__)


class ActionType:
    """Classification of action types Malkuth can identify."""
    NONE = "none"                  # Conversational — no action needed
    CHAIN_QUERY = "chain_query"    # Needs live blockchain data
    MEMORY_STORE = "memory_store"  # User asked to remember something
    CALCULATION = "calculation"    # Mathematical computation needed
    KG_LOOKUP = "kg_lookup"        # Deep knowledge graph query
    SELF_REPORT = "self_report"    # Query about Aether's own state


# Keywords that signal chain data is needed
CHAIN_KEYWORDS: Set[str] = {
    "block", "height", "supply", "difficulty", "mining", "miner",
    "transaction", "tx", "hash", "chain", "network", "peer", "peers",
    "balance", "utxo", "reward", "halving", "era", "mempool",
    "gas", "fee", "node", "nodes", "uptime", "qbc",
}

# Keywords signaling the user wants Aether to remember something
MEMORY_KEYWORDS: Set[str] = {
    "remember", "dont forget", "keep in mind", "note that",
    "my name is", "i am", "call me", "i like", "i prefer",
    "save this", "store this",
}

# Keywords signaling a math or calculation request
CALCULATION_KEYWORDS: Set[str] = {
    "calculate", "compute", "how much", "how many", "what is",
    "percentage", "ratio", "average", "total", "sum", "multiply",
    "divide", "subtract", "add", "convert",
}

# Keywords about Aether's own state
SELF_REPORT_KEYWORDS: Set[str] = {
    "your phi", "your state", "how are you", "how do you feel",
    "your knowledge", "your nodes", "your gates", "your emotions",
    "your memory", "consciousness", "your thoughts", "what are you",
    "who are you", "tell me about yourself", "your capabilities",
}

# Chain data parameter patterns
CHAIN_PARAM_PATTERNS: Dict[str, str] = {
    "block_height": r"\bblock\s*(?:height|number|#)\b",
    "supply": r"\b(?:total\s*)?supply\b",
    "difficulty": r"\bdifficult[y|ies]\b",
    "balance": r"\bbalance\s+(?:of\s+)?([a-f0-9x]+)\b",
    "mining_status": r"\b(?:mining|miner|hashrate)\b",
    "peer_count": r"\b(?:peers?|nodes?|network)\b",
    "mempool": r"\b(?:mempool|pending|unconfirmed)\b",
    "reward": r"\b(?:reward|emission|block\s*reward)\b",
}


class MalkuthActionProcessor(CognitiveProcessor):
    """Action selection and execution processor.

    Classifies stimuli as conversational or action-requiring, identifies
    the specific action type, and reports what data or operations are
    needed. Malkuth stays quiet during pure conversation to avoid
    polluting the Global Workspace with unnecessary action proposals.
    """

    def __init__(self, knowledge_graph: Any = None,
                 soul: Optional[SoulPriors] = None) -> None:
        super().__init__(role="malkuth", knowledge_graph=knowledge_graph, soul=soul)
        self._actions_classified: int = 0
        self._actions_by_type: Dict[str, int] = {}

        logger.info("Malkuth action processor initialized")

    # ------------------------------------------------------------------
    # CognitiveProcessor interface
    # ------------------------------------------------------------------

    def process(self, stimulus: WorkspaceItem) -> CognitiveResponse:
        """Classify the stimulus and recommend actions if needed."""
        t0 = time.time()

        action_type, action_params, reasoning = self._classify_action(stimulus)

        self._actions_classified += 1
        self._actions_by_type[action_type] = self._actions_by_type.get(action_type, 0) + 1

        # Build content based on action type
        content = self._describe_action(action_type, action_params)

        # Confidence and relevance depend on action type
        if action_type == ActionType.NONE:
            # Pure conversation — Malkuth should not dominate
            confidence = 0.15
            relevance = 0.1
        elif action_type == ActionType.SELF_REPORT:
            # Self-report is informational, moderate relevance
            confidence = 0.6
            relevance = 0.5
        elif action_type == ActionType.MEMORY_STORE:
            # Memory requests need action but are simple
            confidence = 0.7
            relevance = 0.7
        else:
            # Chain queries, calculations, KG lookups need real action
            confidence = 0.75
            relevance = 0.8

        trace = [
            {"step": "action_classification", "type": action_type},
            {"step": "reasoning", "details": reasoning},
            {"step": "params_extracted", "count": len(action_params)},
        ]

        latency_ms = (time.time() - t0) * 1000
        self._record_metrics(latency_ms, confidence)

        return self._make_response(
            content=content,
            confidence=confidence,
            relevance=relevance,
            novelty=0.2,  # Actions are pragmatic, not novel
            trace=trace,
            metadata={
                "action_type": action_type,
                "action_params": action_params,
                "is_actionable": action_type != ActionType.NONE,
            },
        )

    # ------------------------------------------------------------------
    # Internal: Action classification
    # ------------------------------------------------------------------

    def _classify_action(
        self, stimulus: WorkspaceItem,
    ) -> tuple[str, Dict[str, Any], str]:
        """Classify the stimulus into an action type.

        Returns:
            Tuple of (action_type, action_params, reasoning_explanation).
        """
        text = stimulus.content.lower().strip()
        params: Dict[str, Any] = {}

        # Check explicit intent from upstream processing
        intent = stimulus.intent.lower() if stimulus.intent else ""
        if intent in ("chain_query", "chain_info", "blockchain"):
            chain_params = self._extract_chain_params(text)
            return ActionType.CHAIN_QUERY, chain_params, f"Intent '{intent}' signals chain data"

        # Check for memory storage requests
        if self._matches_keywords(text, MEMORY_KEYWORDS):
            memory_content = self._extract_memory_content(text)
            params["memory_content"] = memory_content
            return ActionType.MEMORY_STORE, params, "User asked to remember something"

        # Check for self-report queries
        if self._matches_keywords(text, SELF_REPORT_KEYWORDS):
            report_aspects = self._extract_self_report_aspects(text)
            params["aspects"] = report_aspects
            return ActionType.SELF_REPORT, params, "User asking about Aether's state"

        # Check for chain data needs
        chain_score = self._keyword_overlap_score(text, CHAIN_KEYWORDS)
        if chain_score >= 0.15:
            chain_params = self._extract_chain_params(text)
            return ActionType.CHAIN_QUERY, chain_params, f"Chain keywords detected (score={chain_score:.2f})"

        # Check for calculation requests
        if self._matches_keywords(text, CALCULATION_KEYWORDS):
            params["expression"] = text
            return ActionType.CALCULATION, params, "Mathematical calculation requested"

        # Check if knowledge graph lookup would help
        if self.kg is not None and stimulus.content:
            try:
                results = self.kg.search(stimulus.content, limit=3)
                if results:
                    params["suggested_nodes"] = results
                    # Only classify as KG_LOOKUP if the question seems factual
                    if any(text.startswith(w) for w in ("what", "who", "when", "where", "which")):
                        return ActionType.KG_LOOKUP, params, "Factual question with KG matches"
            except Exception:
                pass

        # Default: pure conversation, no action needed
        return ActionType.NONE, {}, "Conversational stimulus — no action required"

    def _extract_chain_params(self, text: str) -> Dict[str, Any]:
        """Extract specific chain data parameters from the text."""
        params: Dict[str, Any] = {"data_needed": []}

        for param_name, pattern in CHAIN_PARAM_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                params["data_needed"].append(param_name)
                # Extract address if present
                if param_name == "balance" and match.groups():
                    params["address"] = match.group(1)

        # If no specific params detected but chain keywords present, request overview
        if not params["data_needed"]:
            params["data_needed"] = ["chain_overview"]

        return params

    def _extract_memory_content(self, text: str) -> str:
        """Extract what the user wants Aether to remember."""
        # Remove the trigger phrase and return the rest
        for phrase in ["remember that", "remember", "dont forget",
                       "keep in mind", "note that", "save this"]:
            idx = text.find(phrase)
            if idx >= 0:
                return text[idx + len(phrase):].strip().strip(".,!?")
        return text

    def _extract_self_report_aspects(self, text: str) -> List[str]:
        """Determine which aspects of self-state are being queried."""
        aspects: List[str] = []
        aspect_map = {
            "phi": ["phi", "integration", "consciousness"],
            "emotions": ["feel", "emotion", "mood", "how are you"],
            "knowledge": ["knowledge", "nodes", "know"],
            "gates": ["gates", "milestones", "progress"],
            "identity": ["who are you", "what are you", "yourself"],
            "capabilities": ["capabilities", "can you", "able to"],
        }
        for aspect, keywords in aspect_map.items():
            if any(kw in text for kw in keywords):
                aspects.append(aspect)
        return aspects or ["general"]

    # ------------------------------------------------------------------
    # Internal: Description generation
    # ------------------------------------------------------------------

    def _describe_action(self, action_type: str,
                         params: Dict[str, Any]) -> str:
        """Generate a description of what action is recommended."""
        if action_type == ActionType.NONE:
            return "This is a conversational message. No external action needed."

        if action_type == ActionType.CHAIN_QUERY:
            data_needed = params.get("data_needed", ["chain_overview"])
            return (
                f"Live blockchain data needed: {', '.join(data_needed)}. "
                "Should query the node RPC for current values."
            )

        if action_type == ActionType.MEMORY_STORE:
            content = params.get("memory_content", "")
            return f"User wants me to remember: '{content}'. Store in user memory."

        if action_type == ActionType.CALCULATION:
            return "Mathematical calculation requested. Compute and include result."

        if action_type == ActionType.KG_LOOKUP:
            nodes = params.get("suggested_nodes", [])
            return f"Factual query — found {len(nodes)} relevant knowledge nodes to reference."

        if action_type == ActionType.SELF_REPORT:
            aspects = params.get("aspects", ["general"])
            return f"User asking about my state: {', '.join(aspects)}. Report from live metrics."

        return f"Action type '{action_type}' with params: {params}"

    # ------------------------------------------------------------------
    # Internal: Keyword matching helpers
    # ------------------------------------------------------------------

    def _matches_keywords(self, text: str, keywords: Set[str]) -> bool:
        """Check if any keyword phrase appears in the text."""
        for keyword in keywords:
            if keyword in text:
                return True
        return False

    def _keyword_overlap_score(self, text: str, keywords: Set[str]) -> float:
        """Score how much the text overlaps with a keyword set.

        Returns the fraction of text tokens that are in the keyword set.
        """
        tokens = set(text.split())
        if not tokens:
            return 0.0
        overlap = tokens & keywords
        return len(overlap) / len(tokens)

    def get_stats(self) -> Dict[str, Any]:
        """Extended stats for the action processor."""
        base = super().get_stats()
        base.update({
            "total_classifications": self._actions_classified,
            "actions_by_type": dict(self._actions_by_type),
        })
        return base
