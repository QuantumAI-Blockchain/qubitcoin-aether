#!/usr/bin/env python3
"""Continuous Grokipedia seeder — takes a topic set number (1, 2, or 3).
Runs forever, cycling through topics. Uses the same HTML fetch as seed_from_grokipedia.py."""

import json
import logging
import os
import re
import sys
import time
from typing import List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grokipedia-continuous")

GROKIPEDIA_BASE = "https://grokipedia.com"
NODE_URL = "http://localhost:5000"
FETCH_TIMEOUT = 30

# Topic set 1: Already in seed_from_grokipedia.py (physics, math, CS, neuro, philosophy, biology, economics, history)
# Topic set 2: Advanced sciences and technology
TOPICS_SET_2: List[Tuple[str, str, str]] = [
    # Quantum Information
    ("Quantum_information", "physics", "axiom"),
    ("Quantum_error_correction", "physics", "axiom"),
    ("Quantum_cryptography", "physics", "axiom"),
    ("Quantum_teleportation", "physics", "axiom"),
    ("Superconductivity", "physics", "axiom"),
    ("Laser", "physics", "axiom"),
    ("Photon", "physics", "axiom"),
    ("Neutrino", "physics", "axiom"),
    ("Antimatter", "physics", "axiom"),
    ("Plasma_(physics)", "physics", "axiom"),
    # Advanced Math
    ("Category_theory", "mathematics", "axiom"),
    ("Abstract_algebra", "mathematics", "axiom"),
    ("Number_theory", "mathematics", "axiom"),
    ("Differential_geometry", "mathematics", "axiom"),
    ("Fourier_transform", "mathematics", "axiom"),
    ("Probability_theory", "mathematics", "axiom"),
    ("Markov_chain", "mathematics", "axiom"),
    ("Linear_algebra", "mathematics", "axiom"),
    ("Set_theory", "mathematics", "axiom"),
    ("Fractal", "mathematics", "axiom"),
    # Advanced AI
    ("Reinforcement_learning", "computer_science", "axiom"),
    ("Transformer_(machine_learning_model)", "computer_science", "axiom"),
    ("Generative_adversarial_network", "computer_science", "axiom"),
    ("Convolutional_neural_network", "computer_science", "axiom"),
    ("Recurrent_neural_network", "computer_science", "axiom"),
    ("Transfer_learning", "computer_science", "axiom"),
    ("Federated_learning", "computer_science", "axiom"),
    ("Knowledge_graph", "computer_science", "axiom"),
    ("Expert_system", "computer_science", "axiom"),
    ("Symbolic_artificial_intelligence", "computer_science", "axiom"),
    # Cryptography & Security
    ("Hash_function", "cryptography", "axiom"),
    ("Digital_signature", "cryptography", "axiom"),
    ("Zero-knowledge_proof", "cryptography", "axiom"),
    ("Elliptic-curve_cryptography", "cryptography", "axiom"),
    ("Merkle_tree", "cryptography", "axiom"),
    ("Public-key_cryptography", "cryptography", "axiom"),
    ("Advanced_Encryption_Standard", "cryptography", "axiom"),
    ("RSA_(cryptosystem)", "cryptography", "axiom"),
    # Cognitive Science
    ("Embodied_cognition", "neuroscience", "axiom"),
    ("Connectome", "neuroscience", "axiom"),
    ("Synaptic_plasticity", "neuroscience", "axiom"),
    ("Attention", "neuroscience", "axiom"),
    ("Working_memory", "neuroscience", "axiom"),
    ("Neurotransmitter", "neuroscience", "axiom"),
    ("Cerebral_cortex", "neuroscience", "axiom"),
    ("Hippocampus", "neuroscience", "axiom"),
    # Philosophy depth
    ("Qualia", "philosophy", "axiom"),
    ("Hard_problem_of_consciousness", "philosophy", "axiom"),
    ("Chinese_room", "philosophy", "axiom"),
    ("Functionalism_(philosophy_of_mind)", "philosophy", "axiom"),
    ("Panpsychism", "philosophy", "axiom"),
    ("Free_will", "philosophy", "axiom"),
    ("Determinism", "philosophy", "axiom"),
    ("Compatibilism", "philosophy", "axiom"),
]

# Topic set 3: Interdisciplinary, emergence, and frontier
TOPICS_SET_3: List[Tuple[str, str, str]] = [
    # Information Theory
    ("Kolmogorov_complexity", "mathematics", "axiom"),
    ("Lambda_calculus", "mathematics", "axiom"),
    ("Halting_problem", "computer_science", "axiom"),
    ("Church-Turing_thesis", "computer_science", "axiom"),
    ("Computability_theory", "computer_science", "axiom"),
    ("Computational_complexity_theory", "computer_science", "axiom"),
    ("NP_(complexity)", "computer_science", "axiom"),
    ("Entropy_(information_theory)", "mathematics", "axiom"),
    # Emergence & Complexity
    ("Emergence", "philosophy", "axiom"),
    ("Complex_system", "physics", "axiom"),
    ("Self-organization", "physics", "axiom"),
    ("Dissipative_system", "physics", "axiom"),
    ("Phase_transition", "physics", "axiom"),
    ("Chaos_theory", "mathematics", "axiom"),
    ("Cellular_automaton", "mathematics", "axiom"),
    ("Autopoiesis", "biology", "axiom"),
    # Consciousness Studies
    ("Neural_correlates_of_consciousness", "neuroscience", "axiom"),
    ("Binding_problem_(neuroscience)", "neuroscience", "axiom"),
    ("Predictive_coding", "neuroscience", "axiom"),
    ("Metacognition", "neuroscience", "axiom"),
    ("Blindsight", "neuroscience", "axiom"),
    ("Unconscious_mind", "neuroscience", "axiom"),
    ("Lucid_dream", "neuroscience", "axiom"),
    # Causal Inference
    ("Causality", "philosophy", "axiom"),
    ("Bayesian_network", "mathematics", "axiom"),
    ("Structural_equation_modeling", "mathematics", "axiom"),
    ("Granger_causality", "mathematics", "axiom"),
    ("Counterfactual_conditional", "philosophy", "axiom"),
    # Evolution & Adaptation
    ("Natural_selection", "biology", "axiom"),
    ("Genetic_algorithm", "computer_science", "axiom"),
    ("Evolutionary_computation", "computer_science", "axiom"),
    ("Epigenetics", "biology", "axiom"),
    ("Abiogenesis", "biology", "axiom"),
    ("RNA_world_hypothesis", "biology", "axiom"),
    ("Horizontal_gene_transfer", "biology", "axiom"),
    # Logic & Formal Systems
    ("First-order_logic", "mathematics", "axiom"),
    ("Modal_logic", "mathematics", "axiom"),
    ("Fuzzy_logic", "mathematics", "axiom"),
    ("Proof_theory", "mathematics", "axiom"),
    ("Type_theory", "mathematics", "axiom"),
    ("Curry-Howard_correspondence", "mathematics", "axiom"),
    # Distributed Systems
    ("Consensus_(computer_science)", "computer_science", "axiom"),
    ("Byzantine_fault", "computer_science", "axiom"),
    ("Distributed_computing", "computer_science", "axiom"),
    ("MapReduce", "computer_science", "axiom"),
    ("CAP_theorem", "computer_science", "axiom"),
    # Materials Science
    ("Semiconductor", "engineering", "axiom"),
    ("Transistor", "engineering", "axiom"),
    ("Integrated_circuit", "engineering", "axiom"),
    ("Graphene", "physics", "axiom"),
    ("Metamaterial", "physics", "axiom"),
    # Game Theory & Economics
    ("Nash_equilibrium", "economics", "axiom"),
    ("Mechanism_design", "economics", "axiom"),
    ("Auction_theory", "economics", "axiom"),
    ("Principal-agent_problem", "economics", "axiom"),
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
    """Fetch a Grokipedia article (HTML page) and extract clean text."""
    url = f"{GROKIPEDIA_BASE}/page/{slug}"
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={
            "User-Agent": "AetherTree-KnowledgeSeeder/1.0 (qbc.network)",
        })
        if resp.status_code != 200:
            log.warning("  → HTTP %d for %s", resp.status_code, slug)
            return None

        html = resp.text
        headline = slug.replace("_", " ")

        # Extract JSON-LD
        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, list):
                    for item in ld:
                        if item.get("@type") == "Article":
                            headline = item.get("headline", headline)
                            break
                elif isinstance(ld, dict) and ld.get("@type") == "Article":
                    headline = ld.get("headline", headline)
            except json.JSONDecodeError:
                pass

        # Clean HTML
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<nav[^>]*>.*?</nav>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<header[^>]*>.*?</header>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<footer[^>]*>.*?</footer>', '', clean, flags=re.DOTALL)

        article_match = re.search(r'<article[^>]*>(.*?)</article>', clean, re.DOTALL)
        if article_match:
            clean = article_match.group(1)

        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        clean = re.sub(r'\[\d+\]', '', clean)

        if len(clean) < 100:
            log.warning("  → Too short: %s (%d chars)", slug, len(clean))
            return None

        content = f"{headline}\n\n{clean}"
        return content[:50000]

    except requests.RequestException as e:
        log.warning("  → Network error: %s — %s", slug, e)
        return None


def chunk_text(text: str, max_chunk: int = 800) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chunk and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chunk]]


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
    topic_set = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    if topic_set == 2:
        topics = TOPICS_SET_2
    elif topic_set == 3:
        topics = TOPICS_SET_3
    else:
        log.error("Usage: %s <2|3>", sys.argv[0])
        sys.exit(1)

    admin_key = load_admin_key()
    if not admin_key:
        log.error("No ADMIN_API_KEY in .env")
        sys.exit(1)

    log.info("=== Continuous Seeder Set %d — %d topics ===", topic_set, len(topics))

    cycle = 0
    while True:
        cycle += 1
        log.info("--- Cycle %d starting ---", cycle)
        total_nodes = 0
        total_articles = 0

        for i, (slug, domain, node_type) in enumerate(topics):
            log.info("[%d/%d] %s (%s)", i + 1, len(topics), slug, domain)

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
                    "confidence": 0.88,
                    "source": f"grokipedia:{slug}",
                }
                for chunk in chunks
            ]

            if ingest_batch(nodes, admin_key):
                log.info("  → Injected %d nodes", len(nodes))
                total_nodes += len(nodes)
                total_articles += 1
            else:
                log.warning("  → Failed to ingest")

            time.sleep(2)

        log.info("=== Cycle %d complete: %d articles, %d nodes ===", cycle, total_articles, total_nodes)
        log.info("Sleeping 120s before next cycle...")
        time.sleep(120)


if __name__ == "__main__":
    main()
