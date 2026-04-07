#!/usr/bin/env python3
"""Seed the Aether Tree knowledge graph from Grokipedia articles.

Fetches articles across diverse knowledge domains and injects them
directly into the KG via the node's internal API. Run this AFTER
the node is fully started and healthy.

Usage:
    python3 scripts/seed_from_grokipedia.py [--max-articles 200] [--dry-run]
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("grokipedia-seeder")

# ── Grokipedia config ──
GROKIPEDIA_BASE = "https://grokipedia.com"
FETCH_TIMEOUT = 30  # seconds per page fetch

# ── Node config ──
NODE_URL = "http://localhost:5000"

# ── Diverse topic list across knowledge domains ──
# Each tuple: (slug, domain, node_type)
SEED_TOPICS: List[Tuple[str, str, str]] = [
    # Physics & Quantum
    ("Quantum_computing", "physics", "axiom"),
    ("Quantum_mechanics", "physics", "axiom"),
    ("Quantum_entanglement", "physics", "axiom"),
    ("General_relativity", "physics", "axiom"),
    ("Standard_Model", "physics", "axiom"),
    ("Supersymmetry", "physics", "axiom"),
    ("String_theory", "physics", "axiom"),
    ("Dark_matter", "physics", "axiom"),
    ("Higgs_boson", "physics", "axiom"),
    ("Thermodynamics", "physics", "axiom"),
    ("Electromagnetic_radiation", "physics", "axiom"),
    ("Wave-particle_duality", "physics", "axiom"),
    # Mathematics
    ("Golden_ratio", "mathematics", "axiom"),
    ("Fibonacci_sequence", "mathematics", "axiom"),
    ("Group_theory", "mathematics", "axiom"),
    ("Topology", "mathematics", "axiom"),
    ("Game_theory", "mathematics", "axiom"),
    ("Cryptography", "mathematics", "axiom"),
    ("Information_theory", "mathematics", "axiom"),
    ("Graph_theory", "mathematics", "axiom"),
    ("Bayesian_statistics", "mathematics", "axiom"),
    ("Chaos_theory", "mathematics", "axiom"),
    # Computer Science & AI
    ("Artificial_intelligence", "computer_science", "axiom"),
    ("Machine_learning", "computer_science", "axiom"),
    ("Neural_network", "computer_science", "axiom"),
    ("Deep_learning", "computer_science", "axiom"),
    ("Natural_language_processing", "computer_science", "axiom"),
    ("Computer_vision", "computer_science", "axiom"),
    ("Blockchain", "computer_science", "axiom"),
    ("Distributed_computing", "computer_science", "axiom"),
    ("Algorithm", "computer_science", "axiom"),
    ("Turing_machine", "computer_science", "axiom"),
    ("Compiler", "computer_science", "axiom"),
    ("Operating_system", "computer_science", "axiom"),
    # Neuroscience & Consciousness
    ("Consciousness", "neuroscience", "axiom"),
    ("Neuroscience", "neuroscience", "axiom"),
    ("Integrated_information_theory", "neuroscience", "axiom"),
    ("Global_workspace_theory", "neuroscience", "axiom"),
    ("Neuroplasticity", "neuroscience", "axiom"),
    ("Memory", "neuroscience", "axiom"),
    ("Cognitive_science", "neuroscience", "axiom"),
    ("Artificial_general_intelligence", "neuroscience", "axiom"),
    ("Free_energy_principle", "neuroscience", "axiom"),
    ("Theory_of_mind", "neuroscience", "axiom"),
    # Philosophy
    ("Philosophy_of_mind", "philosophy", "axiom"),
    ("Epistemology", "philosophy", "axiom"),
    ("Ethics", "philosophy", "axiom"),
    ("Logic", "philosophy", "axiom"),
    ("Ontology", "philosophy", "axiom"),
    ("Existentialism", "philosophy", "axiom"),
    ("Phenomenology_(philosophy)", "philosophy", "axiom"),
    ("Philosophy_of_science", "philosophy", "axiom"),
    # Biology & Evolution
    ("Evolution", "biology", "axiom"),
    ("DNA", "biology", "axiom"),
    ("Cell_(biology)", "biology", "axiom"),
    ("Genetics", "biology", "axiom"),
    ("Ecology", "biology", "axiom"),
    ("Photosynthesis", "biology", "axiom"),
    ("Emergence", "biology", "axiom"),
    ("Complexity_theory", "biology", "axiom"),
    # Economics & Finance
    ("Economics", "economics", "axiom"),
    ("Cryptocurrency", "economics", "axiom"),
    ("Game_theory", "economics", "axiom"),
    ("Decentralized_finance", "economics", "axiom"),
    ("Supply_and_demand", "economics", "axiom"),
    ("Monetary_policy", "economics", "axiom"),
    # History & Culture
    ("History_of_science", "history", "axiom"),
    ("Scientific_revolution", "history", "axiom"),
    ("Industrial_Revolution", "history", "axiom"),
    ("Internet", "history", "axiom"),
    ("World_Wide_Web", "history", "axiom"),
    # Chemistry
    ("Chemistry", "chemistry", "axiom"),
    ("Periodic_table", "chemistry", "axiom"),
    ("Chemical_bond", "chemistry", "axiom"),
    ("Organic_chemistry", "chemistry", "axiom"),
    # Astronomy
    ("Black_hole", "astronomy", "axiom"),
    ("Big_Bang", "astronomy", "axiom"),
    ("Solar_System", "astronomy", "axiom"),
    ("Exoplanet", "astronomy", "axiom"),
    ("Milky_Way", "astronomy", "axiom"),
    # Engineering
    ("Electrical_engineering", "engineering", "axiom"),
    ("Semiconductor", "engineering", "axiom"),
    ("Transistor", "engineering", "axiom"),
    ("Integrated_circuit", "engineering", "axiom"),
    # Medicine
    ("Immune_system", "medicine", "axiom"),
    ("Vaccine", "medicine", "axiom"),
    ("CRISPR", "medicine", "axiom"),
    # Linguistics
    ("Linguistics", "linguistics", "axiom"),
    ("Semantics", "linguistics", "axiom"),
    ("Syntax", "linguistics", "axiom"),
    # Psychology
    ("Psychology", "psychology", "axiom"),
    ("Cognitive_bias", "psychology", "axiom"),
    ("Decision-making", "psychology", "axiom"),
    # Energy
    ("Nuclear_fusion", "energy", "axiom"),
    ("Renewable_energy", "energy", "axiom"),
    ("Entropy", "energy", "axiom"),
]


def fetch_article(slug: str) -> Optional[str]:
    """Fetch a Grokipedia article and extract clean text content."""
    url = f"{GROKIPEDIA_BASE}/page/{slug}"
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={
            "User-Agent": "AetherTree-KnowledgeSeeder/1.0 (qbc.network)",
        })
        if resp.status_code != 200:
            log.warning("Failed to fetch %s: HTTP %d", slug, resp.status_code)
            return None

        html = resp.text

        # Extract JSON-LD for metadata
        ld_match = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, re.DOTALL,
        )
        headline = slug.replace("_", " ")
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

        # Strip HTML tags to get clean text
        # Remove script and style blocks first
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<nav[^>]*>.*?</nav>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<header[^>]*>.*?</header>', '', clean, flags=re.DOTALL)
        clean = re.sub(r'<footer[^>]*>.*?</footer>', '', clean, flags=re.DOTALL)

        # Extract article body if possible (between main content markers)
        article_match = re.search(r'<article[^>]*>(.*?)</article>', clean, re.DOTALL)
        if article_match:
            clean = article_match.group(1)

        # Strip remaining tags
        clean = re.sub(r'<[^>]+>', ' ', clean)
        # Clean up whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Remove reference numbers like [1] [2]
        clean = re.sub(r'\[\d+\]', '', clean)

        if len(clean) < 100:
            log.warning("Article %s too short (%d chars)", slug, len(clean))
            return None

        # Prepend headline for context
        content = f"{headline}\n\n{clean}"

        # Cap at 50K chars (the ingest API allows up to 100K)
        if len(content) > 50000:
            content = content[:50000]

        return content

    except requests.RequestException as e:
        log.warning("Network error fetching %s: %s", slug, e)
        return None


def chunk_text(text: str, max_chunk: int = 800) -> List[str]:
    """Split text into chunks at sentence boundaries."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chunk and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if len(c) >= 20]


def inject_to_kg(
    kg,
    text: str,
    domain: str,
    node_type: str,
    source: str,
    block_height: int,
) -> int:
    """Inject chunked text directly into the knowledge graph. Returns node count."""
    chunks = chunk_text(text)
    if not chunks:
        return 0

    node_ids = []
    for chunk in chunks:
        content = {
            "text": chunk,
            "description": chunk[:200],
            "source": source,
        }
        node = kg.add_node(
            node_type=node_type,
            content=content,
            confidence=0.90,
            source_block=block_height,
            domain=domain,
        )
        node_ids.append(node.node_id)

    # Link sequential chunks
    for i in range(1, len(node_ids)):
        kg.add_edge(node_ids[i - 1], node_ids[i], edge_type="derives")

    return len(node_ids)


def wait_for_node(timeout: int = 300) -> bool:
    """Wait for the node to be healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{NODE_URL}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "healthy":
                    return True
        except requests.RequestException:
            pass
        log.info("Waiting for node to be healthy...")
        time.sleep(5)
    return False


def get_admin_key() -> str:
    """Read admin API key from .env file."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ADMIN_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def seed_via_api(
    text: str,
    domain: str,
    node_type: str,
    source: str,
    admin_key: str = "",
) -> Optional[int]:
    """Seed via the node's REST API with admin key auth."""
    chunks = chunk_text(text)
    if not chunks:
        return None

    total = 0
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        nodes_data = []
        for chunk in batch:
            nodes_data.append({
                "text": chunk,
                "domain": domain,
                "node_type": node_type,
                "confidence": 0.90,
                "source": source,
            })

        try:
            resp = requests.post(
                f"{NODE_URL}/aether/ingest/batch",
                json={"nodes": nodes_data, "_admin_key": admin_key},
                timeout=30,
            )
            if resp.status_code == 200:
                result = resp.json()
                total += result.get("nodes_created", 0)
            else:
                log.warning("Batch ingest failed: %d %s", resp.status_code, resp.text[:200])
        except requests.RequestException as e:
            log.warning("Batch ingest error: %s", e)

    return total if total > 0 else None


def seed_direct(max_articles: int = 200, dry_run: bool = False) -> Dict:
    """Main seeding function — imports node internals for direct KG access."""
    # Add project to path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    admin_key = get_admin_key()
    if not admin_key and not dry_run:
        log.error("No ADMIN_API_KEY found in .env — cannot authenticate")
        return {"error": "No admin key"}

    topics = SEED_TOPICS[:max_articles]
    stats = {
        "articles_fetched": 0,
        "articles_failed": 0,
        "total_nodes_created": 0,
        "domains_seeded": set(),
    }

    log.info("Starting Grokipedia seeding: %d topics", len(topics))

    for i, (slug, domain, node_type) in enumerate(topics):
        log.info("[%d/%d] Fetching: %s (domain: %s)", i + 1, len(topics), slug, domain)

        article_text = fetch_article(slug)
        if not article_text:
            stats["articles_failed"] += 1
            continue

        stats["articles_fetched"] += 1
        chunks = chunk_text(article_text)
        log.info("  → %d chars, %d chunks", len(article_text), len(chunks))

        if dry_run:
            log.info("  → [DRY RUN] Would inject %d nodes", len(chunks))
            stats["total_nodes_created"] += len(chunks)
            stats["domains_seeded"].add(domain)
            continue

        # Inject via API
        nodes_created = seed_via_api(
            article_text, domain, node_type,
            source=f"grokipedia:{slug}",
            admin_key=admin_key,
        )
        if nodes_created:
            stats["total_nodes_created"] += nodes_created
            stats["domains_seeded"].add(domain)
            log.info("  → Injected %d nodes", nodes_created)
        else:
            log.warning("  → Injection failed for %s", slug)

        # Be respectful — 2s between fetches
        time.sleep(2)

    stats["domains_seeded"] = list(stats["domains_seeded"])
    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed Aether Tree from Grokipedia")
    parser.add_argument("--max-articles", type=int, default=200,
                        help="Max articles to fetch (default: 200)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch but don't inject")
    parser.add_argument("--skip-health-check", action="store_true",
                        help="Skip waiting for node health")
    args = parser.parse_args()

    if not args.dry_run and not args.skip_health_check:
        log.info("Waiting for node to be healthy...")
        if not wait_for_node():
            log.error("Node not healthy after 5 minutes. Aborting.")
            sys.exit(1)
        log.info("Node is healthy!")

    stats = seed_direct(max_articles=args.max_articles, dry_run=args.dry_run)

    log.info("=" * 60)
    log.info("SEEDING COMPLETE")
    log.info("  Articles fetched: %d", stats["articles_fetched"])
    log.info("  Articles failed:  %d", stats["articles_failed"])
    log.info("  Nodes created:    %d", stats["total_nodes_created"])
    log.info("  Domains seeded:   %s", stats["domains_seeded"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()
