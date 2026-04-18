#!/usr/bin/env python3
"""Grokipedia Seeder #2 — Advanced sciences, technology, and emerging fields.
Runs continuously, restarting from the beginning when done."""

import json
import logging
import sys
import time
from typing import List, Optional, Tuple
from urllib.parse import quote

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grokipedia-seeder-2")

GROKIPEDIA_BASE = "https://grokipedia.com/api"
NODE_URL = "http://localhost:5000"
FETCH_TIMEOUT = 15
CHUNK_SIZE = 700
ADMIN_KEY = ""

SEED_TOPICS: List[Tuple[str, str, str]] = [
    # Quantum Information
    ("Quantum_information", "physics", "axiom"),
    ("Quantum_error_correction", "physics", "axiom"),
    ("Quantum_cryptography", "physics", "axiom"),
    ("Quantum_teleportation", "physics", "axiom"),
    ("Quantum_decoherence", "physics", "axiom"),
    ("Bose-Einstein_condensate", "physics", "axiom"),
    ("Superconductivity", "physics", "axiom"),
    ("Laser", "physics", "axiom"),
    ("Photon", "physics", "axiom"),
    ("Neutrino", "physics", "axiom"),
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
    ("Transformer_(deep_learning_architecture)", "computer_science", "axiom"),
    ("Generative_adversarial_network", "computer_science", "axiom"),
    ("Convolutional_neural_network", "computer_science", "axiom"),
    ("Recurrent_neural_network", "computer_science", "axiom"),
    ("Attention_(machine_learning)", "computer_science", "axiom"),
    ("Transfer_learning", "computer_science", "axiom"),
    ("Federated_learning", "computer_science", "axiom"),
    ("AutoML", "computer_science", "axiom"),
    ("Knowledge_graph", "computer_science", "axiom"),
    # Systems & Networks
    ("Complex_network", "computer_science", "axiom"),
    ("Graph_neural_network", "computer_science", "axiom"),
    ("Peer-to-peer", "computer_science", "axiom"),
    ("Consensus_(computer_science)", "computer_science", "axiom"),
    ("Byzantine_fault", "computer_science", "axiom"),
    ("Hash_function", "cryptography", "axiom"),
    ("Digital_signature", "cryptography", "axiom"),
    ("Zero-knowledge_proof", "cryptography", "axiom"),
    ("Elliptic-curve_cryptography", "cryptography", "axiom"),
    ("Merkle_tree", "cryptography", "axiom"),
    # Cognitive Science
    ("Embodied_cognition", "neuroscience", "axiom"),
    ("Mirror_neuron", "neuroscience", "axiom"),
    ("Connectome", "neuroscience", "axiom"),
    ("Synaptic_plasticity", "neuroscience", "axiom"),
    ("Attention", "neuroscience", "axiom"),
    ("Working_memory", "neuroscience", "axiom"),
    ("Executive_functions", "neuroscience", "axiom"),
    ("Neural_coding", "neuroscience", "axiom"),
    # Philosophy of Mind
    ("Qualia", "philosophy", "axiom"),
    ("Hard_problem_of_consciousness", "philosophy", "axiom"),
    ("Chinese_room", "philosophy", "axiom"),
    ("Philosophical_zombie", "philosophy", "axiom"),
    ("Functionalism_(philosophy_of_mind)", "philosophy", "axiom"),
    ("Panpsychism", "philosophy", "axiom"),
    ("Dualism_(philosophy_of_mind)", "philosophy", "axiom"),
    ("Free_will", "philosophy", "axiom"),
    # Complex Systems
    ("Self-organization", "physics", "axiom"),
    ("Autopoiesis", "biology", "axiom"),
    ("Cybernetics", "computer_science", "axiom"),
    ("Systems_theory", "philosophy", "axiom"),
    ("Swarm_intelligence", "biology", "axiom"),
    ("Cellular_automaton", "mathematics", "axiom"),
    ("Agent-based_model", "computer_science", "axiom"),
    ("Scale-free_network", "mathematics", "axiom"),
    # Emerging Tech
    ("Brain-computer_interface", "neuroscience", "axiom"),
    ("Nanotechnology", "engineering", "axiom"),
    ("Synthetic_biology", "biology", "axiom"),
    ("Quantum_supremacy", "physics", "axiom"),
    ("Neuromorphic_engineering", "engineering", "axiom"),
    ("Molecular_computing", "computer_science", "axiom"),
]


def load_admin_key() -> str:
    """Load admin API key from .env."""
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
            import re
            text = re.sub(r"<[^>]+>", " ", str(text))
            text = re.sub(r"\s+", " ", text).strip()
            return text[:50000] if text else None
        elif resp.status_code == 404:
            log.warning("  → Article not found: %s", slug)
            return None
    except Exception as e:
        log.warning("  → Fetch failed: %s — %s", slug, e)
    return None


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    words = text.split()
    chunks = []
    current = []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
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

    log.info("Seeder #2 starting — %d topics, continuous mode", len(SEED_TOPICS))

    while True:  # Continuous loop
        total_nodes = 0
        total_articles = 0

        for i, (slug, domain, node_type) in enumerate(SEED_TOPICS):
            log.info("[%d/%d] Fetching: %s (domain: %s)", i + 1, len(SEED_TOPICS), slug, domain)

            text = fetch_article(slug)
            if not text:
                continue

            chunks = chunk_text(text)
            log.info("  → %d chars, %d chunks", len(text), len(chunks))

            nodes = []
            for chunk in chunks:
                nodes.append({
                    "text": chunk,
                    "domain": domain,
                    "node_type": node_type,
                    "confidence": 0.88,
                    "source": f"grokipedia:{slug}",
                })

            if ingest_batch(nodes, admin_key):
                log.info("  → Injected %d nodes", len(nodes))
                total_nodes += len(nodes)
                total_articles += 1
            else:
                log.warning("  → Injection failed")

            time.sleep(3)  # Rate limit

        log.info("=== CYCLE COMPLETE: %d articles, %d nodes ===", total_articles, total_nodes)
        log.info("Sleeping 300s before next cycle...")
        time.sleep(300)


if __name__ == "__main__":
    main()
