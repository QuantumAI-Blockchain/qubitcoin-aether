#!/usr/bin/env python3
"""Export Aether Tree Knowledge Graph as training data for LLM fine-tuning.

Connects to CockroachDB and exports high-quality knowledge nodes + edges
as instruction/response JSONL pairs suitable for LoRA fine-tuning.

Output formats:
  - JSONL (default): One JSON object per line with instruction/input/output fields
  - Alpaca: Same format, compatible with Alpaca/Stanford/Unsloth fine-tuning

Usage:
    python3 scripts/export_kg_training_data.py --output /tmp/kg_training.jsonl
    python3 scripts/export_kg_training_data.py --min-confidence 0.6 --limit 10000
    python3 scripts/export_kg_training_data.py --domain blockchain --format alpaca
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def get_db_url() -> str:
    """Get database URL from environment or .env file."""
    url = os.environ.get('DATABASE_URL')
    if url:
        return url
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('DATABASE_URL='):
                    return line.split('=', 1)[1].strip('"').strip("'")
    return 'postgresql://root@localhost:26257/qbc?sslmode=disable'


def _extract_text_from_jsonb(content: Any) -> str:
    """Extract readable text from a JSONB content field.

    Content can be a dict (from JSONB) or a string.  For dicts, we extract
    the most informative text fields in priority order.
    """
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return content.strip()

    if not isinstance(content, dict):
        return str(content).strip()

    # Priority text fields in KG JSONB content
    text_keys = [
        'text', 'pattern', 'content', 'observation', 'insight',
        'description', 'reasoning', 'conclusion', 'summary',
        'explanation', 'prediction', 'resolution', 'axiom', 'concept',
    ]
    for key in text_keys:
        val = content.get(key)
        if val and isinstance(val, str) and len(val) > 15:
            return val.strip()

    # For deduction/induction nodes, extract from premises
    premises = content.get('from_premises', [])
    if premises and isinstance(premises, list):
        for p in premises:
            if isinstance(p, dict):
                pat = p.get('pattern') or p.get('text')
                if pat and isinstance(pat, str) and len(pat) > 15:
                    return pat.strip()

    # Fallback: concatenate string values (skip short metadata keys)
    parts = []
    for k, v in content.items():
        if isinstance(v, str) and len(v) > 15 and k not in ('type', 'source', 'model'):
            parts.append(v)
    if parts:
        return '; '.join(parts[:3])

    return ''  # Skip rather than dump raw JSON


def export_nodes(conn, min_confidence: float, limit: int,
                 domain: Optional[str]) -> List[Dict[str, Any]]:
    """Export knowledge nodes as training examples."""
    query = """
        SELECT
            n.id, n.node_type, n.content, n.confidence,
            n.domain, n.source_block, n.grounding_source,
            n.reference_count
        FROM knowledge_nodes n
        WHERE n.confidence >= %s
          AND n.content IS NOT NULL
          AND length(n.content::text) > 20
    """
    params: list = [min_confidence]

    if domain:
        query += " AND n.domain = %s"
        params.append(domain)

    query += " ORDER BY n.confidence DESC, n.reference_count DESC LIMIT %s"
    params.append(limit)

    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()

    examples = []
    for row in rows:
        nid, ntype, content_raw, conf, dom, block, grounding, refs = row

        content = _extract_text_from_jsonb(content_raw)
        if len(content) < 20:
            continue

        # Build instruction based on node type
        if ntype == 'inference':
            instruction = "What can be inferred from the Qubitcoin knowledge graph?"
        elif ntype == 'observation':
            instruction = "What has been observed on the Qubitcoin blockchain?"
        elif ntype == 'axiom':
            instruction = "What is a fundamental principle in the Qubitcoin ecosystem?"
        elif ntype == 'prediction':
            instruction = "What prediction can be made about the Qubitcoin network?"
        elif ntype == 'meta_observation':
            instruction = "What meta-level insight exists about the Qubitcoin system?"
        elif ntype == 'concept':
            instruction = "Explain a key concept in the Qubitcoin ecosystem."
        elif ntype == 'contradiction_resolution':
            instruction = "How was a contradiction resolved in Qubitcoin's knowledge graph?"
        else:
            instruction = f"What does the Qubitcoin knowledge graph know about {dom or 'this topic'}?"

        # Add domain context as input
        input_ctx = ""
        if dom and dom != 'unknown':
            input_ctx = f"Domain: {dom}"
        if grounding and grounding != 'none':
            if input_ctx:
                input_ctx += f", Source: {grounding}"
            else:
                input_ctx = f"Source: {grounding}"

        examples.append({
            'instruction': instruction,
            'input': input_ctx,
            'output': content,
            'metadata': {
                'node_id': nid,
                'node_type': ntype,
                'confidence': float(conf),
                'domain': dom,
                'source_block': block,
                'reference_count': refs,
            }
        })

    cursor.close()
    return examples


def export_edge_reasoning(conn, min_confidence: float,
                          limit: int) -> List[Dict[str, Any]]:
    """Export edge-connected node pairs as reasoning examples."""
    query = """
        SELECT
            n1.content AS source_content,
            n1.node_type AS source_type,
            n1.domain AS source_domain,
            e.edge_type,
            e.weight,
            n2.content AS target_content,
            n2.node_type AS target_type,
            n2.domain AS target_domain
        FROM knowledge_edges e
        JOIN knowledge_nodes n1 ON e.from_node_id = n1.id
        JOIN knowledge_nodes n2 ON e.to_node_id = n2.id
        WHERE n1.confidence >= %s
          AND n2.confidence >= %s
          AND n1.content IS NOT NULL
          AND n2.content IS NOT NULL
          AND length(n1.content::text) > 20
          AND length(n2.content::text) > 20
          AND e.edge_type IN ('derives', 'supports', 'contradicts',
                              'analogous_to', 'causes', 'refines')
        ORDER BY e.weight DESC
        LIMIT %s
    """

    cursor = conn.cursor()
    cursor.execute(query, [min_confidence, min_confidence, limit])
    rows = cursor.fetchall()

    examples = []
    for row in rows:
        src_raw, src_type, src_dom, edge_type, weight, \
            tgt_raw, tgt_type, tgt_dom = row

        src_content = _extract_text_from_jsonb(src_raw)
        tgt_content = _extract_text_from_jsonb(tgt_raw)
        if len(src_content) < 20 or len(tgt_content) < 20:
            continue

        # Build instruction based on edge type
        if edge_type == 'derives':
            instruction = "Given the following knowledge, what can be derived?"
        elif edge_type == 'supports':
            instruction = "What evidence supports this claim in the Qubitcoin ecosystem?"
        elif edge_type == 'contradicts':
            instruction = "What contradicts this statement in the Qubitcoin knowledge graph?"
        elif edge_type == 'analogous_to':
            instruction = "What is analogous to this concept across Qubitcoin domains?"
        elif edge_type == 'causes':
            instruction = "What does this cause in the Qubitcoin system?"
        elif edge_type == 'refines':
            instruction = "How can this knowledge be refined or improved?"
        else:
            instruction = f"How does this relate ({edge_type}) to other knowledge?"

        cross_domain = ""
        if src_dom and tgt_dom and src_dom != tgt_dom:
            cross_domain = f" [Cross-domain: {src_dom} -> {tgt_dom}]"

        examples.append({
            'instruction': instruction,
            'input': src_content,
            'output': tgt_content + cross_domain,
            'metadata': {
                'edge_type': edge_type,
                'weight': float(weight),
                'source_type': src_type,
                'target_type': tgt_type,
                'source_domain': src_dom,
                'target_domain': tgt_dom,
            }
        })

    cursor.close()
    return examples


def export_qa_pairs(conn, limit: int) -> List[Dict[str, Any]]:
    """Export high-quality axioms and inferences as Q&A pairs."""
    query = """
        SELECT content, node_type, domain, confidence
        FROM knowledge_nodes
        WHERE node_type IN ('axiom', 'inference', 'concept')
          AND confidence >= 0.7
          AND content IS NOT NULL
          AND length(content::text) > 50
        ORDER BY confidence DESC, reference_count DESC
        LIMIT %s
    """
    cursor = conn.cursor()
    cursor.execute(query, [limit])
    rows = cursor.fetchall()

    examples = []
    domain_questions = {
        'blockchain': [
            "How does the Qubitcoin blockchain work?",
            "Explain this aspect of Qubitcoin's consensus mechanism.",
            "What is important about Qubitcoin's blockchain design?",
        ],
        'quantum': [
            "How does quantum computing relate to Qubitcoin?",
            "Explain the quantum aspects of Qubitcoin mining.",
            "What role does VQE play in Qubitcoin?",
        ],
        'economics': [
            "How does Qubitcoin's economic model work?",
            "Explain the SUSY economics in Qubitcoin.",
            "What drives the value of QBC?",
        ],
        'aether': [
            "How does the Aether Tree AGI system work?",
            "Explain a key aspect of Aether Tree intelligence.",
            "What makes the Aether Tree unique?",
        ],
        'network': [
            "How does Qubitcoin's P2P network function?",
            "Explain network behavior in the Qubitcoin ecosystem.",
        ],
        'security': [
            "How does Qubitcoin ensure security?",
            "What security mechanisms protect the Qubitcoin network?",
        ],
    }
    import random
    rng = random.Random(42)

    for row in rows:
        content_raw, ntype, domain, conf = row
        content = _extract_text_from_jsonb(content_raw)
        if len(content) < 30:
            continue
        dom = domain or 'blockchain'
        questions = domain_questions.get(dom, [
            f"What does the Qubitcoin system know about {dom}?"
        ])

        examples.append({
            'instruction': rng.choice(questions),
            'input': '',
            'output': content,
            'metadata': {
                'node_type': ntype,
                'domain': dom,
                'confidence': float(conf),
            }
        })

    cursor.close()
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Export KG training data for LLM fine-tuning'
    )
    parser.add_argument(
        '--output', '-o', default='/tmp/kg_training.jsonl',
        help='Output JSONL file path (default: /tmp/kg_training.jsonl)'
    )
    parser.add_argument(
        '--min-confidence', type=float, default=0.5,
        help='Minimum node confidence threshold (default: 0.5)'
    )
    parser.add_argument(
        '--limit', type=int, default=20000,
        help='Max examples per category (default: 20000)'
    )
    parser.add_argument(
        '--domain', default=None,
        help='Filter by domain (default: all domains)'
    )
    parser.add_argument(
        '--format', choices=['jsonl', 'alpaca'], default='jsonl',
        help='Output format (default: jsonl)'
    )
    parser.add_argument(
        '--include-metadata', action='store_true', default=False,
        help='Include metadata fields in output (default: False)'
    )
    args = parser.parse_args()

    # Connect to CockroachDB
    try:
        import psycopg2
        db_url = get_db_url()
        conn = psycopg2.connect(db_url)
        print(f"Connected to database")
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}")
        sys.exit(1)

    all_examples: List[Dict[str, Any]] = []

    # 1. Knowledge nodes
    print(f"Exporting knowledge nodes (min_conf={args.min_confidence})...")
    nodes = export_nodes(conn, args.min_confidence, args.limit, args.domain)
    print(f"  -> {len(nodes)} node examples")
    all_examples.extend(nodes)

    # 2. Edge reasoning pairs
    print(f"Exporting edge reasoning pairs...")
    edges = export_edge_reasoning(conn, args.min_confidence, args.limit)
    print(f"  -> {len(edges)} edge reasoning examples")
    all_examples.extend(edges)

    # 3. Q&A pairs from high-quality nodes
    print(f"Exporting Q&A pairs...")
    qa = export_qa_pairs(conn, args.limit)
    print(f"  -> {len(qa)} Q&A examples")
    all_examples.extend(qa)

    conn.close()

    # Shuffle for training
    import random
    random.Random(42).shuffle(all_examples)

    # Write output
    with open(args.output, 'w') as f:
        for ex in all_examples:
            if not args.include_metadata and 'metadata' in ex:
                out = {k: v for k, v in ex.items() if k != 'metadata'}
            else:
                out = ex
            f.write(json.dumps(out, ensure_ascii=False) + '\n')

    size_mb = os.path.getsize(args.output) / (1024 * 1024)
    print(f"\nExported {len(all_examples)} training examples to {args.output}")
    print(f"File size: {size_mb:.1f} MB")

    # Print stats
    type_counts: Dict[str, int] = {}
    for ex in all_examples:
        meta = ex.get('metadata', {})
        t = meta.get('node_type') or meta.get('edge_type', 'unknown')
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"\nType distribution:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")


if __name__ == '__main__':
    main()
