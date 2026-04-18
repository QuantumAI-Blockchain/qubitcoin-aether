#!/usr/bin/env python3
"""Grokipedia Seeder #3 — Interdisciplinary, emerging research, and frontier topics.
Runs continuously, restarting from the beginning when done."""

import json
import logging
import re
import sys
import time
from typing import List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grokipedia-seeder-3")

GROKIPEDIA_BASE = "https://grokipedia.com/api"
NODE_URL = "http://localhost:5000"
FETCH_TIMEOUT = 15
CHUNK_SIZE = 700

SEED_TOPICS: List[Tuple[str, str, str]] = [
    # Information & Computation Theory
    ("Kolmogorov_complexity", "mathematics", "axiom"),
    ("Computability_theory", "computer_science", "axiom"),
    ("Lambda_calculus", "mathematics", "axiom"),
    ("Halting_problem", "computer_science", "axiom"),
    ("P_versus_NP_problem", "mathematics", "axiom"),
    ("Algorithmic_information_theory", "mathematics", "axiom"),
    ("Shannon_entropy", "mathematics", "axiom"),
    ("Mutual_information", "mathematics", "axiom"),
    # Emergence & Complexity
    ("Emergence", "philosophy", "axiom"),
    ("Complex_adaptive_system", "biology", "axiom"),
    ("Dissipative_system", "physics", "axiom"),
    ("Phase_transition", "physics", "axiom"),
    ("Criticality", "physics", "axiom"),
    ("Percolation_theory", "mathematics", "axiom"),
    ("Power_law", "mathematics", "axiom"),
    ("Small-world_network", "mathematics", "axiom"),
    # Consciousness Studies
    ("Neural_correlates_of_consciousness", "neuroscience", "axiom"),
    ("Binding_problem", "neuroscience", "axiom"),
    ("Predictive_coding", "neuroscience", "axiom"),
    ("Higher-order_theories_of_consciousness", "philosophy", "axiom"),
    ("Orchestrated_objective_reduction", "physics", "axiom"),
    ("Baars_global_workspace_theory", "neuroscience", "axiom"),
    ("Metacognition", "neuroscience", "axiom"),
    ("Blindsight", "neuroscience", "axiom"),
    # Causal Inference
    ("Causality", "philosophy", "axiom"),
    ("Causal_inference", "mathematics", "axiom"),
    ("Bayesian_network", "mathematics", "axiom"),
    ("Structural_equation_modeling", "mathematics", "axiom"),
    ("Granger_causality", "mathematics", "axiom"),
    ("Interventionism_(philosophy_of_mind)", "philosophy", "axiom"),
    # Evolution & Adaptation
    ("Natural_selection", "biology", "axiom"),
    ("Evolutionary_game_theory", "mathematics", "axiom"),
    ("Genetic_algorithm", "computer_science", "axiom"),
    ("Evolutionary_computation", "computer_science", "axiom"),
    ("Memetics", "biology", "axiom"),
    ("Epigenetics", "biology", "axiom"),
    ("Horizontal_gene_transfer", "biology", "axiom"),
    ("Baldwin_effect", "biology", "axiom"),
    # Logic & Formal Systems
    ("First-order_logic", "mathematics", "axiom"),
    ("Propositional_calculus", "mathematics", "axiom"),
    ("Modal_logic", "mathematics", "axiom"),
    ("Fuzzy_logic", "mathematics", "axiom"),
    ("Proof_theory", "mathematics", "axiom"),
    ("Model_theory", "mathematics", "axiom"),
    ("Goedel's_incompleteness_theorems", "mathematics", "axiom"),
    ("Type_theory", "mathematics", "axiom"),
    # Robotics & Embodied AI
    ("Robotics", "engineering", "axiom"),
    ("Robot_learning", "computer_science", "axiom"),
    ("Simultaneous_localization_and_mapping", "computer_science", "axiom"),
    ("Multi-agent_system", "computer_science", "axiom"),
    ("Swarm_robotics", "engineering", "axiom"),
    ("Soft_robotics", "engineering", "axiom"),
    # Quantum Biology
    ("Quantum_biology", "biology", "axiom"),
    ("Quantum_cognition", "neuroscience", "axiom"),
    ("Photosynthetic_reaction_centre", "biology", "axiom"),
    # Economics & Game Theory
    ("Mechanism_design", "economics", "axiom"),
    ("Auction_theory", "economics", "axiom"),
    ("Nash_equilibrium", "economics", "axiom"),
    ("Prisoner's_dilemma", "economics", "axiom"),
    ("Public_goods_game", "economics", "axiom"),
    ("Token_economy", "economics", "axiom"),
    # Materials & Energy
    ("Topological_insulator", "physics", "axiom"),
    ("Metamaterial", "physics", "axiom"),
    ("Graphene", "physics", "axiom"),
    ("Spintronics", "physics", "axiom"),
    ("Quantum_dot", "physics", "axiom"),
]


def load_admin_key() -> str:
    try:
        with open("/root/Qubitcoin/.env") as f:
            for line in f:
                if line.startswith("ADMIN_API_KEY="):
                    return line.strip().split("=", 1)[1].strip('"').strip("'")
    except Exception:
        pass
    return ""


def fetch_article(slug: str) -> Optional[str]:
    url = f"{GROKIPEDIA_BASE}/page/{slug}"
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("extract", data.get("content", ""))
            if not text and isinstance(data, dict):
                for key in ("body", "text", "html_content", "summary"):
                    if key in data and data[key]:
                        text = data[key]
                        break
            text = re.sub(r"<[^>]+>", " ", str(text))
            text = re.sub(r"\s+", " ", text).strip()
            return text[:50000] if text else None
        elif resp.status_code == 404:
            log.warning("  → Not found: %s", slug)
            return None
    except Exception as e:
        log.warning("  → Fetch failed: %s — %s", slug, e)
    return None


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    words = text.split()
    chunks, current, current_len = [], [], 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current, current_len = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def ingest_batch(nodes: List[dict], admin_key: str) -> bool:
    try:
        resp = requests.post(
            f"{NODE_URL}/aether/ingest/batch",
            json={"nodes": nodes, "_admin_key": admin_key},
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as e:
        log.warning("Ingest failed: %s", e)
        return False


def main():
    admin_key = load_admin_key()
    if not admin_key:
        log.error("No ADMIN_API_KEY found in .env")
        sys.exit(1)

    log.info("Seeder #3 starting — %d topics, continuous mode", len(SEED_TOPICS))

    while True:
        total_nodes = 0
        total_articles = 0

        for i, (slug, domain, node_type) in enumerate(SEED_TOPICS):
            log.info("[%d/%d] Fetching: %s (domain: %s)", i + 1, len(SEED_TOPICS), slug, domain)

            text = fetch_article(slug)
            if not text:
                continue

            chunks = chunk_text(text)
            log.info("  → %d chars, %d chunks", len(text), len(chunks))

            nodes = [
                {
                    "text": chunk,
                    "domain": domain,
                    "node_type": node_type,
                    "confidence": 0.87,
                    "source": f"grokipedia:{slug}",
                }
                for chunk in chunks
            ]

            if ingest_batch(nodes, admin_key):
                log.info("  → Injected %d nodes", len(nodes))
                total_nodes += len(nodes)
                total_articles += 1

            time.sleep(3)

        log.info("=== CYCLE COMPLETE: %d articles, %d nodes ===", total_articles, total_nodes)
        log.info("Sleeping 300s before next cycle...")
        time.sleep(300)


if __name__ == "__main__":
    main()
