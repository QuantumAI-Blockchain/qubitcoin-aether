"""
#92: Analogical Transfer (Formal Structure Mapping)

Implements Gentner's Structure-Mapping Theory (SMT) for finding
structural correspondences between source and target domains and
generating candidate inferences from analogies.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

PHI = 1.618033988749895


@dataclass
class StructureMapping:
    """Result of a structure mapping between source and target."""
    correspondences: Dict[str, str]  # source_entity -> target_entity
    score: float
    relational_depth: int
    inferences: List[str]
    source_domain: str = ''
    target_domain: str = ''
    timestamp: float = field(default_factory=time.time)


class AnalogicalTransfer:
    """Formal structure mapping for analogical reasoning.

    Implements the core of Gentner's SMT:
      - One-to-one mapping constraint
      - Parallel connectivity (relations map if their arguments map)
      - Systematicity principle (prefer deeper relational structures)
    """

    def __init__(self, max_mappings: int = 100) -> None:
        self._max_mappings = max_mappings
        # History of found analogies
        self._analogies: List[StructureMapping] = []
        self._max_history = 500
        # Stats
        self._total_mappings = 0
        self._total_inferences = 0

    # ------------------------------------------------------------------
    # Structure mapping
    # ------------------------------------------------------------------

    def find_mapping(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        source_domain: str = '',
        target_domain: str = '',
    ) -> StructureMapping:
        """Find best structure mapping between source and target.

        Source and target are represented as dicts with:
          - 'entities': list of entity names
          - 'relations': list of (relation_name, [arg1, arg2, ...])
          - 'attributes': dict {entity: {attr: value}}

        Args:
            source: Source domain representation.
            target: Target domain representation.

        Returns:
            StructureMapping with correspondences, score, and inferences.
        """
        self._total_mappings += 1

        s_entities = source.get('entities', [])
        t_entities = target.get('entities', [])
        s_relations = source.get('relations', [])
        t_relations = target.get('relations', [])
        s_attrs = source.get('attributes', {})
        t_attrs = target.get('attributes', {})

        if not s_entities or not t_entities:
            return StructureMapping(
                correspondences={}, score=0.0, relational_depth=0,
                inferences=[], source_domain=source_domain,
                target_domain=target_domain,
            )

        # Step 1: Compute entity similarity based on attributes
        entity_sim = self._compute_entity_similarity(
            s_entities, t_entities, s_attrs, t_attrs
        )

        # Step 2: Find relation correspondences
        relation_match = self._match_relations(s_relations, t_relations)

        # Step 3: Greedy one-to-one mapping (maximizing combined score)
        correspondences = self._greedy_mapping(
            s_entities, t_entities, entity_sim, relation_match,
            s_relations, t_relations,
        )

        # Step 4: Compute relational depth (systematicity)
        depth = self._compute_relational_depth(
            correspondences, s_relations, t_relations
        )

        # Step 5: Score = structural match * relational depth
        structural_match = self._structural_match_score(
            correspondences, entity_sim, relation_match,
            s_relations, t_relations,
        )
        score = structural_match * (1.0 + depth * 0.5)

        # Step 6: Generate inferences
        inferences = self.infer_from_analogy_raw(
            correspondences, source, target
        )
        self._total_inferences += len(inferences)

        mapping = StructureMapping(
            correspondences=correspondences,
            score=score,
            relational_depth=depth,
            inferences=inferences,
            source_domain=source_domain,
            target_domain=target_domain,
        )

        self._analogies.append(mapping)
        if len(self._analogies) > self._max_history:
            self._analogies = self._analogies[-self._max_history:]

        return mapping

    def _compute_entity_similarity(
        self,
        s_entities: List[str],
        t_entities: List[str],
        s_attrs: Dict[str, Dict[str, Any]],
        t_attrs: Dict[str, Dict[str, Any]],
    ) -> Dict[Tuple[str, str], float]:
        """Compute pairwise similarity between source and target entities."""
        sim: Dict[Tuple[str, str], float] = {}
        for se in s_entities:
            s_a = s_attrs.get(se, {})
            for te in t_entities:
                t_a = t_attrs.get(te, {})
                # Jaccard-like overlap of attribute keys
                s_keys = set(s_a.keys())
                t_keys = set(t_a.keys())
                if not s_keys and not t_keys:
                    sim[(se, te)] = 0.5  # neutral
                elif not s_keys or not t_keys:
                    sim[(se, te)] = 0.1
                else:
                    overlap = len(s_keys & t_keys)
                    union = len(s_keys | t_keys)
                    sim[(se, te)] = overlap / union if union > 0 else 0.0
        return sim

    def _match_relations(
        self,
        s_relations: List[Tuple[str, List[str]]],
        t_relations: List[Tuple[str, List[str]]],
    ) -> Dict[Tuple[int, int], float]:
        """Score matches between source and target relations."""
        match: Dict[Tuple[int, int], float] = {}
        for i, (s_name, s_args) in enumerate(s_relations):
            for j, (t_name, t_args) in enumerate(t_relations):
                # Same arity required for structural mapping
                if len(s_args) != len(t_args):
                    continue
                # Name similarity (simple string overlap)
                name_sim = self._string_similarity(s_name, t_name)
                match[(i, j)] = name_sim
        return match

    def _string_similarity(self, a: str, b: str) -> float:
        """Simple string similarity (character-level Jaccard)."""
        if a == b:
            return 1.0
        set_a = set(a.lower())
        set_b = set(b.lower())
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return len(set_a & set_b) / union

    def _greedy_mapping(
        self,
        s_entities: List[str],
        t_entities: List[str],
        entity_sim: Dict[Tuple[str, str], float],
        relation_match: Dict[Tuple[int, int], float],
        s_relations: List[Tuple[str, List[str]]],
        t_relations: List[Tuple[str, List[str]]],
    ) -> Dict[str, str]:
        """Greedy one-to-one mapping maximizing similarity."""
        # Score each possible mapping
        candidates: List[Tuple[float, str, str]] = []
        for se in s_entities:
            for te in t_entities:
                score = entity_sim.get((se, te), 0.0)
                # Boost if entities participate in matching relations
                for (ri, rj), r_score in relation_match.items():
                    if ri < len(s_relations) and rj < len(t_relations):
                        if se in s_relations[ri][1] and te in t_relations[rj][1]:
                            score += r_score * 0.5
                candidates.append((score, se, te))

        # Greedy assignment
        candidates.sort(reverse=True)
        mapping: Dict[str, str] = {}
        used_targets: Set[str] = set()
        for score, se, te in candidates:
            if se not in mapping and te not in used_targets:
                mapping[se] = te
                used_targets.add(te)
        return mapping

    def _compute_relational_depth(
        self,
        correspondences: Dict[str, str],
        s_relations: List[Tuple[str, List[str]]],
        t_relations: List[Tuple[str, List[str]]],
    ) -> int:
        """Compute depth of relational chain that maps consistently."""
        depth = 0
        for s_name, s_args in s_relations:
            mapped_args = [correspondences.get(a) for a in s_args]
            if None in mapped_args:
                continue
            # Check if target has a matching relation
            for t_name, t_args in t_relations:
                if list(mapped_args) == list(t_args):
                    depth += 1
                    break
        return depth

    def _structural_match_score(
        self,
        correspondences: Dict[str, str],
        entity_sim: Dict[Tuple[str, str], float],
        relation_match: Dict[Tuple[int, int], float],
        s_relations: List[Tuple[str, List[str]]],
        t_relations: List[Tuple[str, List[str]]],
    ) -> float:
        """Compute overall structural match score."""
        if not correspondences:
            return 0.0
        # Average entity similarity of mapped pairs
        total_sim = sum(
            entity_sim.get((s, t), 0.0)
            for s, t in correspondences.items()
        )
        avg_sim = total_sim / len(correspondences)
        # Relation coverage
        total_rel = len(s_relations)
        matched_rel = sum(1.0 for v in relation_match.values() if v > 0.3)
        rel_coverage = matched_rel / max(total_rel, 1)
        return avg_sim * 0.5 + rel_coverage * 0.5

    # ------------------------------------------------------------------
    # Inference generation
    # ------------------------------------------------------------------

    def infer_from_analogy(self, mapping: StructureMapping) -> List[str]:
        """Generate candidate inferences from an existing mapping."""
        return mapping.inferences

    def infer_from_analogy_raw(
        self,
        correspondences: Dict[str, str],
        source: Dict[str, Any],
        target: Dict[str, Any],
    ) -> List[str]:
        """Generate candidate inferences from correspondences.

        Looks for relations in source that don't have counterparts in
        target and projects them as predictions.
        """
        inferences: List[str] = []
        s_relations = source.get('relations', [])
        t_relations = target.get('relations', [])
        t_rel_set = {(r[0], tuple(r[1])) for r in t_relations}

        for s_name, s_args in s_relations:
            mapped_args = [correspondences.get(a) for a in s_args]
            if None in mapped_args:
                continue
            mapped_tuple = (s_name, tuple(mapped_args))
            if mapped_tuple not in t_rel_set:
                inferences.append(
                    f"By analogy: {s_name}({', '.join(mapped_args)}) "
                    f"may hold in target domain"
                )

        return inferences[:20]  # Cap inferences

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return analogical transfer statistics."""
        avg_score = 0.0
        if self._analogies:
            avg_score = sum(a.score for a in self._analogies) / len(self._analogies)
        return {
            'total_mappings': self._total_mappings,
            'total_inferences': self._total_inferences,
            'analogies_stored': len(self._analogies),
            'average_score': avg_score,
        }
