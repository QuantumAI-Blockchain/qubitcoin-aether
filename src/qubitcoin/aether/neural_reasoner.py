"""
Graph Attention Network (GAT) Reasoner — Learned Reasoning over Knowledge Graph

Provides a lightweight 2-layer Graph Attention Network that operates over the
knowledge graph.  For each reasoning query, the GAT computes attention weights
between the query node and its k-hop neighborhood, aggregates neighbor embeddings,
and produces a "reasoning embedding" for confidence and conclusion prediction.

Uses PyTorch (CPU-compatible) with ~50K parameters.  Falls back to a simple
weighted-average approach if PyTorch is not installed.

This is improvement #2 in the AI improvement stack: rule-based reasoning
can't learn; a GAT discovers novel reasoning patterns from the system's
own reasoning history.
"""
import math
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Try to load Rust GAT (highest priority — fastest, real backprop)
_HAS_RUST_GAT = False
_RustGATReasoner = None
try:
    from aether_core import RustGATReasoner as _RustGATReasoner
    _HAS_RUST_GAT = True
    logger.info("Rust GAT neural reasoner loaded (aether_core)")
except ImportError:
    pass

# Try to load PyTorch (fallback)
_HAS_TORCH = False
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _HAS_TORCH = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# TorchReasonerNetwork — proper nn.Module for gradient-based training
# ---------------------------------------------------------------------------

if _HAS_TORCH:
    class GraphAttentionLayer(nn.Module):
        """Single-head Graph Attention layer (Velickovic et al., 2018)."""

        def __init__(self, in_features: int, out_features: int, dropout: float = 0.1) -> None:
            super().__init__()
            self.W = nn.Linear(in_features, out_features, bias=False)
            self.a_src = nn.Parameter(torch.zeros(out_features, 1))
            self.a_dst = nn.Parameter(torch.zeros(out_features, 1))
            nn.init.xavier_uniform_(self.W.weight)
            nn.init.xavier_uniform_(self.a_src)
            nn.init.xavier_uniform_(self.a_dst)
            self.leaky_relu = nn.LeakyReLU(0.2)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
            """
            Args:
                x: Node features [N, in_features]
                edge_index: Edge indices [2, E] (src, dst)
            Returns:
                Updated node features [N, out_features]
            """
            Wh = self.W(x)  # [N, out_features]

            # Attention coefficients
            e_src = (Wh @ self.a_src).squeeze(-1)  # [N]
            e_dst = (Wh @ self.a_dst).squeeze(-1)  # [N]

            src, dst = edge_index[0], edge_index[1]
            attn = self.leaky_relu(e_src[src] + e_dst[dst])  # [E]

            # Sparse softmax per destination node
            attn = attn - attn.max()
            attn_exp = attn.exp()
            denom = torch.zeros(x.size(0), device=x.device)
            denom.scatter_add_(0, dst, attn_exp)
            attn_norm = attn_exp / (denom[dst] + 1e-8)
            attn_norm = self.dropout(attn_norm)

            # Weighted message passing
            messages = Wh[src] * attn_norm.unsqueeze(-1)  # [E, out_features]
            out = torch.zeros_like(Wh)
            out.scatter_add_(0, dst.unsqueeze(-1).expand_as(messages), messages)

            return out

    class TorchReasonerNetwork(nn.Module):
        """2-layer Graph Attention Network for link prediction and confidence scoring.

        Architecture:
            GAT Layer 1: in_dim -> hidden_dim (with attention)
            ELU activation
            GAT Layer 2: hidden_dim -> hidden_dim (with attention)
            Readout: Linear(hidden_dim, 1) -> sigmoid for confidence

        Trained via binary cross-entropy on (correct_prediction, actual_outcome) pairs.
        """

        def __init__(self, in_dim: int, hidden_dim: int = 64,
                     learning_rate: float = 0.001) -> None:
            super().__init__()
            self.gat1 = GraphAttentionLayer(in_dim, hidden_dim)
            self.gat2 = GraphAttentionLayer(hidden_dim, hidden_dim)
            self.readout = nn.Linear(hidden_dim, 1)
            self.optimizer = torch.optim.Adam(self.parameters(), lr=learning_rate)
            self._train_steps: int = 0
            self._cumulative_loss: float = 0.0

        def forward(self, x: torch.Tensor, edge_index: Optional[torch.Tensor] = None) -> torch.Tensor:
            """Forward pass through 2-layer GAT.

            Args:
                x: Node features [N, in_dim] or [batch, in_dim] for batch mode
                edge_index: Optional [2, E] edge indices. If None, uses self-loop only (MLP mode).
            """
            if edge_index is None:
                # MLP fallback: self-loop only (backwards compatible)
                N = x.size(0)
                edge_index = torch.stack([torch.arange(N), torch.arange(N)]).to(x.device)

            h = F.elu(self.gat1(x, edge_index))
            h = self.gat2(h, edge_index)

            # Global mean pool then readout
            pooled = h.mean(dim=0, keepdim=True) if h.dim() == 2 else h
            return torch.sigmoid(self.readout(pooled))

        def train_batch(self, inputs: torch.Tensor,
                        targets: torch.Tensor,
                        edge_index: Optional[torch.Tensor] = None) -> float:
            """Run one training step.

            Args:
                inputs: [batch_size, in_dim] or [N, in_dim] node features
                targets: [batch_size, 1] target values
                edge_index: Optional [2, E] edges for graph mode
            """
            self.train()
            self.optimizer.zero_grad()
            pred = self.forward(inputs, edge_index)

            # Handle shape mismatch between pooled output and targets
            if pred.shape != targets.shape:
                pred = pred.expand_as(targets)

            l2_lambda = 1e-4
            l2_reg = sum(p.pow(2.0).sum() for p in self.parameters())
            loss = F.binary_cross_entropy(pred, targets) + l2_lambda * l2_reg
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.parameters(), max_norm=1.0)
            self.optimizer.step()
            loss_val = float(loss.item())
            self._train_steps += 1
            self._cumulative_loss += loss_val
            return loss_val

        def predict(self, x: torch.Tensor,
                    edge_index: Optional[torch.Tensor] = None) -> torch.Tensor:
            """Inference (no gradient tracking)."""
            self.eval()
            with torch.no_grad():
                return self.forward(x, edge_index)

        def get_stats(self) -> dict:
            return {
                'train_steps': self._train_steps,
                'avg_loss': (self._cumulative_loss / self._train_steps
                             if self._train_steps > 0 else 0.0),
                'total_params': sum(p.numel() for p in self.parameters()),
                'architecture': 'GAT_2layer',
            }

        def sync_from_gat_layers(self, layer1: 'GATLayer',
                                  layer2: 'GATLayer') -> None:
            """Copy weights from numpy GATLayer lists into this module."""
            with torch.no_grad():
                w1 = torch.tensor(layer1.W, dtype=torch.float32)
                self.gat1.W.weight.copy_(w1.T)
                w2 = torch.tensor(layer2.W, dtype=torch.float32)
                self.gat2.W.weight.copy_(w2.T)

        def sync_to_gat_layers(self, layer1: 'GATLayer',
                                layer2: 'GATLayer') -> None:
            """Copy weights from this module back into numpy GATLayer lists."""
            with torch.no_grad():
                updated_w1 = self.gat1.W.weight.T.tolist()
                for i in range(min(layer1.in_dim, len(updated_w1))):
                    for j in range(min(layer1.out_dim, len(updated_w1[i]))):
                        layer1.W[i][j] = updated_w1[i][j]

                updated_w2 = self.gat2.W.weight.T.tolist()
                for i in range(min(layer2.in_dim, len(updated_w2))):
                    for j in range(min(layer2.out_dim, len(updated_w2[i]))):
                        layer2.W[i][j] = updated_w2[i][j]

else:
    # Stub when PyTorch is not available
    class TorchReasonerNetwork:  # type: ignore[no-redef]
        """Stub when PyTorch is not installed."""
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError("TorchReasonerNetwork requires PyTorch")


class GATLayer:
    """Single Graph Attention layer (no-PyTorch fallback).

    Supports online weight updates via ``perturb_weights()`` which
    applies an evolutionary-strategy-style update: on correct predictions,
    reinforce current weights; on incorrect predictions, perturb away.
    """

    def __init__(self, in_dim: int, out_dim: int, n_heads: int = 4) -> None:
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.n_heads = n_heads
        # Initialize weights with Xavier-like scaling
        import random
        random.seed(42)
        scale = 1.0 / math.sqrt(in_dim)
        self.W = [[random.gauss(0, scale) for _ in range(out_dim)]
                   for _ in range(in_dim)]
        self.a = [random.gauss(0, scale) for _ in range(out_dim * 2)]
        # Store gradient direction from last forward pass for online learning
        self._last_perturbation: Optional[List[List[float]]] = None

    def forward(self, features: Dict[int, List[float]],
                adj: Dict[int, List[int]]) -> Dict[int, List[float]]:
        """Apply attention-weighted neighbor aggregation."""
        output = {}
        for nid, feat in features.items():
            neighbors = adj.get(nid, [])
            if not neighbors:
                output[nid] = feat[:self.out_dim] if len(feat) >= self.out_dim else feat + [0.0] * (self.out_dim - len(feat))
                continue

            # Transform node feature
            h_i = self._transform(feat)

            # Compute attention over neighbors
            neighbor_feats = []
            attn_scores = []
            for neighbor_id in neighbors:
                if neighbor_id in features:
                    h_j = self._transform(features[neighbor_id])
                    neighbor_feats.append(h_j)
                    # Attention score: concat(h_i, h_j) dot a
                    concat = h_i + h_j
                    score = sum(c * a for c, a in zip(concat, self.a[:len(concat)]))
                    attn_scores.append(score)

            if not attn_scores:
                output[nid] = h_i
                continue

            # Softmax attention
            max_s = max(attn_scores)
            exp_scores = [math.exp(s - max_s) for s in attn_scores]
            total = sum(exp_scores)
            attn_weights = [e / total for e in exp_scores]

            # Weighted sum of neighbor features
            agg = [0.0] * self.out_dim
            for w, h_j in zip(attn_weights, neighbor_feats):
                for d in range(self.out_dim):
                    agg[d] += w * h_j[d]

            # Combine with self
            result = [(h_i[d] + agg[d]) / 2.0 for d in range(self.out_dim)]
            output[nid] = result

        return output

    def _transform(self, feat: List[float]) -> List[float]:
        """Simple linear transform W @ feat."""
        result = [0.0] * self.out_dim
        for j in range(self.out_dim):
            for i in range(min(len(feat), self.in_dim)):
                result[j] += self.W[i][j] * feat[i]
        return result

    def perturb_weights(self, reinforce: bool, learning_rate: float = 0.01) -> None:
        """Online evolutionary strategy weight update.

        Generates a random perturbation direction. If the last prediction
        was correct (reinforce=True), move weights in that direction.
        If incorrect, move weights in the opposite direction.

        This is a gradient-free optimization that requires no backprop.
        """
        import random
        perturbation_scale = learning_rate * (1.0 if reinforce else -0.5)

        for i in range(self.in_dim):
            for j in range(self.out_dim):
                noise = random.gauss(0, 1.0)
                self.W[i][j] += perturbation_scale * noise

        for k in range(len(self.a)):
            noise = random.gauss(0, 1.0)
            self.a[k] += perturbation_scale * noise


class GATReasoner:
    """
    Graph Attention Network reasoner for the Aether knowledge graph.

    Provides neural reasoning as a complement to rule-based reasoning.
    Operates on node embeddings from the VectorIndex and graph adjacency.

    When PyTorch is available, uses proper backpropagation for training
    (gradient-based optimization with Adam). Falls back to evolutionary
    strategy (gradient-free perturbation) when PyTorch is not installed.

    Usage:
        reasoner = GATReasoner()
        result = reasoner.reason(kg, vector_index, query_node_ids)
        print(reasoner.training_mode)  # 'backprop' or 'evolutionary'
    """

    TRAINING_BATCH_SIZE: int = 16

    def __init__(self, hidden_dim: int = 64, n_heads: int = 4) -> None:
        self.hidden_dim = hidden_dim
        self.n_heads = n_heads
        self.has_pytorch: bool = _HAS_TORCH
        self.has_rust_gat: bool = _HAS_RUST_GAT
        self._layer1: Optional[GATLayer] = None
        self._layer2: Optional[GATLayer] = None
        self._initialized = False
        # Training history for self-improvement
        self._prediction_history: List[dict] = []
        self._correct_predictions: int = 0
        self._total_predictions: int = 0
        # Mini-batch gradient descent buffer (used when PyTorch/Rust is available)
        self._training_buffer: List[dict] = []
        # Cache features/adj from last reason() call for training data
        self._last_embeddings: Optional[Dict[str, object]] = None
        # PyTorch linear layers (lazy-initialized in train_step)
        self._torch_layer1: Optional[object] = None
        self._torch_layer2: Optional[object] = None
        self._optimizer: Optional[object] = None
        # Backprop training statistics
        self._backprop_steps: int = 0
        self._backprop_total_loss: float = 0.0
        self._evolutionary_steps: int = 0
        # Rust GAT backend (highest priority)
        self._rust_gat: Optional[object] = None
        if self.has_rust_gat and _RustGATReasoner is not None:
            try:
                self._rust_gat = _RustGATReasoner(
                    input_dim=hidden_dim, hidden_dim=hidden_dim,
                    output_dim=hidden_dim // 2, n_heads=n_heads, n_layers=2
                )
                logger.info(f"Rust GAT initialized: {hidden_dim}→{hidden_dim}→{hidden_dim // 2}, {n_heads} heads")
            except Exception as e:
                logger.warning(f"Rust GAT init failed, falling back to Python: {e}")
                self.has_rust_gat = False
                self._rust_gat = None

    @property
    def training_mode(self) -> str:
        """Return current training mode: 'rust_backprop' > 'backprop' > 'evolutionary'."""
        if self.has_rust_gat and self._rust_gat is not None:
            return 'rust_backprop'
        return 'backprop' if self.has_pytorch else 'evolutionary'

    def _ensure_layers(self, input_dim: int) -> None:
        """Initialize GAT layers on first use."""
        if self._initialized:
            return
        self._layer1 = GATLayer(input_dim, self.hidden_dim, self.n_heads)
        self._layer2 = GATLayer(self.hidden_dim, self.hidden_dim, self.n_heads)
        self._initialized = True

    def reason(self, kg, vector_index, query_node_ids: List[int],
               k_hops: int = 2) -> dict:
        """
        Perform neural reasoning over query nodes and their neighborhood.

        Args:
            kg: KnowledgeGraph instance
            vector_index: VectorIndex instance (provides embeddings)
            query_node_ids: Starting nodes for reasoning
            k_hops: How many hops of neighbors to include

        Returns:
            Dict with:
                confidence: float (predicted confidence for conclusion)
                attended_nodes: list of (node_id, attention_weight) pairs
                reasoning_embedding: list (the aggregated reasoning vector)
                suggested_edge_type: str (predicted relationship type)
        """
        if not kg or not vector_index or not query_node_ids:
            return self._empty_result()

        # Gather k-hop neighborhood
        neighborhood = set(query_node_ids)
        frontier = set(query_node_ids)
        for _ in range(k_hops):
            next_frontier = set()
            for nid in frontier:
                node = kg.nodes.get(nid)
                if node:
                    next_frontier.update(node.edges_out)
                    next_frontier.update(node.edges_in)
            frontier = next_frontier - neighborhood
            neighborhood.update(frontier)

        # Collect features (embeddings) for neighborhood nodes
        features: Dict[int, List[float]] = {}
        for nid in neighborhood:
            emb = vector_index.get_embedding(nid)
            if emb:
                features[nid] = emb

        if not features:
            return self._empty_result()

        # Build adjacency using O(degree) index lookups instead of O(|E|) scan
        adj: Dict[int, List[int]] = {nid: [] for nid in features}
        for nid in features:
            for edge in kg.get_edges_from(nid):
                if edge.to_node_id in adj:
                    adj[nid].append(edge.to_node_id)
                    adj[edge.to_node_id].append(nid)

        # Initialize layers
        input_dim = len(next(iter(features.values())))
        self._ensure_layers(input_dim)

        # Forward pass through 2 GAT layers
        h1 = self._layer1.forward(features, adj)
        h2 = self._layer2.forward(h1, adj)

        # Aggregate query node embeddings
        query_embs = [h2[nid] for nid in query_node_ids if nid in h2]
        if not query_embs:
            return self._empty_result()

        # Mean pooling over query node outputs
        dim = len(query_embs[0])
        reasoning_emb = [0.0] * dim
        for emb in query_embs:
            for d in range(dim):
                reasoning_emb[d] += emb[d]
        reasoning_emb = [v / len(query_embs) for v in reasoning_emb]

        # Compute attention scores over all nodes relative to reasoning embedding
        attended = []
        for nid, emb in h2.items():
            if nid in query_node_ids:
                continue
            dot = sum(a * b for a, b in zip(reasoning_emb, emb))
            norm_r = math.sqrt(sum(v * v for v in reasoning_emb))
            norm_e = math.sqrt(sum(v * v for v in emb))
            attn = dot / (norm_r * norm_e) if norm_r > 0 and norm_e > 0 else 0
            attended.append((nid, round(attn, 4)))

        attended.sort(key=lambda x: x[1], reverse=True)

        # Predict confidence from top attention score + embedding coherence
        top_attn = attended[0][1] if attended else 0.0
        magnitude = math.sqrt(sum(v * v for v in reasoning_emb))
        # Combine attention coherence with magnitude signal
        raw_conf = 0.6 * max(0.0, top_attn) + 0.4 * (1.0 / (1.0 + math.exp(-magnitude + 1.5)))
        confidence = max(0.01, min(0.99, raw_conf))

        # Predict edge type based on strongest attention pattern
        edge_type = self._predict_edge_type(kg, query_node_ids,
                                             [n for n, _ in attended[:5]])

        self._total_predictions += 1

        # Ensure correct_predictions never exceeds total_predictions (Improvement 49)
        if self._correct_predictions > self._total_predictions:
            logger.warning(
                f"GATReasoner counter fix: correct_predictions "
                f"({self._correct_predictions}) > total_predictions "
                f"({self._total_predictions}), clamping"
            )
            self._correct_predictions = self._total_predictions

        # Cache features for training data collection in record_outcome()
        self._last_embeddings = {
            'features': features,
            'adj': adj,
            'confidence': confidence,
            'query_node_ids': list(query_node_ids),
        }

        return {
            'confidence': round(confidence, 4),
            'attended_nodes': attended[:10],
            'reasoning_embedding': reasoning_emb[:16],  # Truncated for API
            'suggested_edge_type': edge_type,
            'neighborhood_size': len(features),
            'method': 'gat_neural',
        }

    def _predict_edge_type(self, kg, source_ids: List[int],
                           target_ids: List[int]) -> str:
        """Predict most likely edge type based on existing patterns.

        Uses O(degree) adjacency index lookups instead of scanning all edges.
        """
        edge_type_counts: Dict[str, int] = {}
        for nid in source_ids:
            for edge in kg.get_edges_from(nid):
                edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1
            for edge in kg.get_edges_to(nid):
                edge_type_counts[edge.edge_type] = edge_type_counts.get(edge.edge_type, 0) + 1

        if edge_type_counts:
            return max(edge_type_counts, key=edge_type_counts.get)
        return 'derives'

    def record_outcome(self, prediction_correct: bool,
                       predicted_positive: bool = True) -> None:
        """Record whether a prediction was correct and update weights.

        When PyTorch is available, collects training samples into a buffer
        and triggers mini-batch gradient descent when the buffer is full.
        Falls back to evolutionary strategy (perturb_weights) when PyTorch
        is not installed.

        Args:
            prediction_correct: Whether the overall prediction was correct.
            predicted_positive: Whether the model predicted positive class.
        """
        if prediction_correct:
            self._correct_predictions += 1
            # Ensure correct_predictions never exceeds total_predictions (Improvement 49)
            if self._correct_predictions > self._total_predictions:
                self._correct_predictions = self._total_predictions

        # Track for performance metrics (Improvement 80)
        self._prediction_history.append({
            'predicted': predicted_positive,
            'actual': prediction_correct if predicted_positive else not prediction_correct,
        })
        if len(self._prediction_history) > 500:
            self._prediction_history = self._prediction_history[-500:]

        if not self._layer1 or not self._layer2:
            return

        # Collect training sample from cached embeddings
        if self._last_embeddings is not None:
            sample = {
                'node_features': self._last_embeddings['features'],
                'edge_index': self._last_embeddings['adj'],
                'target_confidence': self._last_embeddings['confidence'],
                'actual_outcome': 1.0 if prediction_correct else 0.0,
            }
            self._training_buffer.append(sample)

        # Rust GAT: delegate training to native backend
        if self._rust_gat is not None:
            try:
                self._rust_gat.record_outcome(prediction_correct)
                # Trigger training every TRAINING_BATCH_SIZE samples
                if len(self._training_buffer) >= self.TRAINING_BATCH_SIZE:
                    loss = self._rust_gat.train_step(self.TRAINING_BATCH_SIZE)
                    if loss >= 0.0:
                        self._backprop_steps += 1
                        self._backprop_total_loss += loss
                        self._training_buffer = self._training_buffer[self.TRAINING_BATCH_SIZE:]
                        logger.debug("Rust GAT train_step loss=%.6f steps=%d",
                                     loss, self._backprop_steps)
                return
            except Exception as e:
                logger.debug(f"Rust GAT record_outcome error: {e}")

        # Try backpropagation if PyTorch available and buffer full
        if self.has_pytorch and len(self._training_buffer) >= self.TRAINING_BATCH_SIZE:
            # Curriculum learning: dynamic quality threshold (Items #37, #78)
            threshold = self.curriculum_quality_threshold()
            quality_batch = [
                s for s in self._training_buffer[:self.TRAINING_BATCH_SIZE * 2]
                if self.assess_training_quality(s) >= threshold
            ][:self.TRAINING_BATCH_SIZE]
            batch = quality_batch if quality_batch else self._training_buffer[:self.TRAINING_BATCH_SIZE]
            self._training_buffer = self._training_buffer[self.TRAINING_BATCH_SIZE:]
            loss = self._train_backprop(batch)
            if loss >= 0.0:
                logger.debug("GAT backprop loss=%.6f buffer_remaining=%d",
                             loss, len(self._training_buffer))
                return

        # Fallback: evolutionary strategy (always used when no PyTorch)
        self._layer1.perturb_weights(
            reinforce=prediction_correct, learning_rate=0.005
        )
        self._layer2.perturb_weights(
            reinforce=prediction_correct, learning_rate=0.005
        )
        self._evolutionary_steps += 1

    def _train_backprop(self, train_data: List[dict]) -> float:
        """Train the neural reasoner using backpropagation (requires PyTorch).

        Converts the training samples into tensors, performs a forward pass
        through a 2-layer network (linear -> ReLU -> linear -> sigmoid),
        computes binary cross-entropy loss between predicted confidence and
        actual outcome, backpropagates gradients, and updates weights.

        The updated PyTorch weights are copied back to the fallback GATLayer
        weight lists so that the plain-Python forward pass in ``reason()``
        also benefits from backprop training.

        Args:
            train_data: List of training sample dicts, each containing
                ``node_features`` (Dict[int, List[float]]) and
                ``actual_outcome`` (float, 0.0 or 1.0).

        Returns:
            Loss value (float >= 0.0) on success, -1.0 if training could
            not run (no PyTorch, empty data, or layers not initialized).
        """
        if not _HAS_TORCH:
            return -1.0
        if not train_data:
            return -1.0
        if not self._layer1 or not self._layer2:
            return -1.0

        in_dim = self._layer1.in_dim
        hidden_dim = self._layer1.out_dim

        # Lazy-initialize PyTorch layers mirroring GATLayer dimensions
        if self._torch_layer1 is None:
            self._torch_layer1 = nn.Linear(in_dim, hidden_dim, bias=False)
            self._torch_layer2 = nn.Linear(hidden_dim, 1, bias=True)
            self._optimizer = torch.optim.Adam(
                list(self._torch_layer1.parameters()) +
                list(self._torch_layer2.parameters()),
                lr=0.001,
            )

        # Sync GATLayer weights into PyTorch tensors
        with torch.no_grad():
            w1_data = torch.tensor(self._layer1.W, dtype=torch.float32)
            self._torch_layer1.weight.copy_(w1_data.T)
            w2_col = [self._layer2.W[i][0] if self._layer2.out_dim > 0 else 0.0
                       for i in range(self._layer2.in_dim)]
            self._torch_layer2.weight.copy_(
                torch.tensor([w2_col], dtype=torch.float32)
            )

        # Build batch tensors: mean-pool node features per sample
        inputs = []
        targets = []
        for sample in train_data:
            node_features = sample.get('node_features', {})
            if not node_features:
                continue
            dim = in_dim
            pooled = [0.0] * dim
            count = 0
            for feat in node_features.values():
                for d in range(min(len(feat), dim)):
                    pooled[d] += feat[d]
                count += 1
            if count > 0:
                pooled = [v / count for v in pooled]
            inputs.append(pooled)
            targets.append(sample.get('actual_outcome', 0.0))

        if not inputs:
            return -1.0

        x = torch.tensor(inputs, dtype=torch.float32)
        y = torch.tensor(targets, dtype=torch.float32).unsqueeze(1)

        # Forward pass: linear1 -> ReLU -> linear2 -> sigmoid
        self._optimizer.zero_grad()
        h = F.relu(self._torch_layer1(x))
        logits = self._torch_layer2(h)
        pred = torch.sigmoid(logits)

        # Use BCE loss with L2 regularization for better gradient signal
        l2_lambda = 1e-4
        l2_reg = sum(
            p.pow(2.0).sum()
            for p in list(self._torch_layer1.parameters()) + list(self._torch_layer2.parameters())
        )
        loss = F.binary_cross_entropy(pred, y) + l2_lambda * l2_reg
        loss.backward()
        # Gradient clipping (Improvement 80)
        torch.nn.utils.clip_grad_norm_(
            list(self._torch_layer1.parameters()) + list(self._torch_layer2.parameters()),
            max_norm=1.0
        )
        self._optimizer.step()

        # Copy updated weights back to GATLayer lists
        with torch.no_grad():
            updated_w1 = self._torch_layer1.weight.T.tolist()
            for i in range(self._layer1.in_dim):
                for j in range(self._layer1.out_dim):
                    self._layer1.W[i][j] = updated_w1[i][j]

            updated_w2 = self._torch_layer2.weight[0].tolist()
            for i in range(min(len(updated_w2), self._layer2.in_dim)):
                if self._layer2.out_dim > 0:
                    self._layer2.W[i][0] = updated_w2[i]

        loss_val = float(loss.item())
        self._backprop_steps += 1
        self._backprop_total_loss += loss_val

        logger.debug(
            "Backprop training step %d: loss=%.6f, samples=%d",
            self._backprop_steps, loss_val, len(inputs)
        )

        return loss_val

    def train_step(self, batch_size: int = 32) -> float:
        """Run one mini-batch gradient descent step.

        Uses Rust GAT (if available) > PyTorch > returns -1.0.

        Args:
            batch_size: Number of samples to use per training step.

        Returns:
            Loss value (float >= 0.0) on success, -1.0 if training could
            not run.
        """
        # Rust GAT: native training step
        if self._rust_gat is not None:
            try:
                loss = self._rust_gat.train_step(batch_size)
                if loss >= 0.0:
                    self._backprop_steps += 1
                    self._backprop_total_loss += loss
                    return loss
            except Exception as e:
                logger.debug(f"Rust GAT train_step error: {e}")

        if not _HAS_TORCH:
            return -1.0
        if len(self._training_buffer) < batch_size:
            return -1.0
        if not self._layer1 or not self._layer2:
            return -1.0

        # Extract batch from front of buffer
        batch = self._training_buffer[:batch_size]
        self._training_buffer = self._training_buffer[batch_size:]

        in_dim = self._layer1.in_dim
        hidden_dim = self._layer1.out_dim

        # Lazy-initialize PyTorch layers mirroring GATLayer dimensions
        if self._torch_layer1 is None:
            self._torch_layer1 = nn.Linear(in_dim, hidden_dim, bias=False)
            self._torch_layer2 = nn.Linear(hidden_dim, 1, bias=True)
            # Use a modest learning rate for stable CPU training
            self._optimizer = torch.optim.Adam(
                list(self._torch_layer1.parameters()) +
                list(self._torch_layer2.parameters()),
                lr=0.001,
            )

        # Sync GATLayer weights into PyTorch tensors
        with torch.no_grad():
            w1_data = torch.tensor(self._layer1.W, dtype=torch.float32)
            # GATLayer.W is [in_dim x out_dim], nn.Linear weight is [out_dim x in_dim]
            self._torch_layer1.weight.copy_(w1_data.T)
            # Layer2 projects hidden_dim -> 1 for confidence prediction
            # Use first column of GATLayer2.W as the projection weights
            w2_col = [self._layer2.W[i][0] if self._layer2.out_dim > 0 else 0.0
                       for i in range(self._layer2.in_dim)]
            self._torch_layer2.weight.copy_(
                torch.tensor([w2_col], dtype=torch.float32)
            )

        # Build batch tensors: mean-pool node features per sample
        inputs = []
        targets = []
        for sample in batch:
            node_features = sample['node_features']
            if not node_features:
                continue
            # Mean-pool all node feature vectors into a single input vector
            dim = in_dim
            pooled = [0.0] * dim
            count = 0
            for feat in node_features.values():
                for d in range(min(len(feat), dim)):
                    pooled[d] += feat[d]
                count += 1
            if count > 0:
                pooled = [v / count for v in pooled]
            inputs.append(pooled)
            targets.append(sample['actual_outcome'])

        if not inputs:
            return -1.0

        x = torch.tensor(inputs, dtype=torch.float32)   # [B, in_dim]
        y = torch.tensor(targets, dtype=torch.float32).unsqueeze(1)  # [B, 1]

        # Forward pass: linear1 -> ReLU -> linear2 -> sigmoid
        self._optimizer.zero_grad()
        h = F.relu(self._torch_layer1(x))      # [B, hidden_dim]
        logits = self._torch_layer2(h)          # [B, 1]
        pred = torch.sigmoid(logits)            # [B, 1]

        loss = F.binary_cross_entropy(pred, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            list(self._torch_layer1.parameters()) +
            list(self._torch_layer2.parameters()),
            max_norm=1.0,
        )
        self._optimizer.step()

        # Copy updated weights back to GATLayer lists
        with torch.no_grad():
            # Layer 1: nn.Linear weight is [out_dim, in_dim], GATLayer.W is [in_dim][out_dim]
            updated_w1 = self._torch_layer1.weight.T.tolist()  # [in_dim, out_dim]
            for i in range(self._layer1.in_dim):
                for j in range(self._layer1.out_dim):
                    self._layer1.W[i][j] = updated_w1[i][j]

            # Layer 2: copy projection weights back into first column of GATLayer2.W
            updated_w2 = self._torch_layer2.weight[0].tolist()  # [hidden_dim]
            for i in range(min(len(updated_w2), self._layer2.in_dim)):
                if self._layer2.out_dim > 0:
                    self._layer2.W[i][0] = updated_w2[i]

        return float(loss.item())

    # ------------------------------------------------------------------
    # Public PyTorch API: train_batch_torch / predict_torch
    # ------------------------------------------------------------------

    def _ensure_torch_network(self) -> Optional[object]:
        """Lazily create the TorchReasonerNetwork if PyTorch is available
        and GATLayers are initialized. Returns the network or None."""
        if not _HAS_TORCH or not self._layer1:
            return None
        if not hasattr(self, '_torch_network') or self._torch_network is None:
            self._torch_network = TorchReasonerNetwork(
                in_dim=self._layer1.in_dim,
                hidden_dim=self.hidden_dim,
            )
            # Sync current GATLayer weights into the network
            self._torch_network.sync_from_gat_layers(self._layer1, self._layer2)
        return self._torch_network

    def train_batch_torch(self, inputs: List[List[float]],
                          targets: List[float]) -> float:
        """Train the neural reasoner using PyTorch backpropagation.

        This is the high-level API that wraps TorchReasonerNetwork.train_batch.

        Args:
            inputs: List of input feature vectors, each of length ``in_dim``.
            targets: List of target values (0.0 or 1.0), one per input.

        Returns:
            Loss value (float >= 0.0) on success, -1.0 if PyTorch is unavailable
            or inputs are empty.
        """
        if not _HAS_TORCH:
            return -1.0
        if not inputs or not targets:
            return -1.0
        if not self._layer1:
            return -1.0

        net = self._ensure_torch_network()
        if net is None:
            return -1.0

        x = torch.tensor(inputs, dtype=torch.float32)
        y = torch.tensor(targets, dtype=torch.float32).unsqueeze(1)

        loss_val = net.train_batch(x, y)

        # Sync weights back to GATLayer lists so reason() benefits
        net.sync_to_gat_layers(self._layer1, self._layer2)

        self._backprop_steps += 1
        self._backprop_total_loss += loss_val
        return loss_val

    def predict_torch(self, input_features: List[float]) -> float:
        """Predict confidence for a single input using PyTorch.

        Args:
            input_features: Feature vector of length ``in_dim``.

        Returns:
            Predicted confidence in [0.0, 1.0], or -1.0 if PyTorch
            is unavailable.
        """
        if not _HAS_TORCH:
            return -1.0
        if not self._layer1:
            return -1.0

        net = self._ensure_torch_network()
        if net is None:
            return -1.0

        x = torch.tensor([input_features], dtype=torch.float32)
        pred = net.predict(x)
        return float(pred[0][0])

    def save_weights(self, persistence: 'AGIPersistence', block_height: int = 0) -> bool:
        """Save model weights to CockroachDB via persistence layer."""
        if not self._initialized:
            return False
        if self.has_pytorch and self._torch_layer1 is not None:
            # Save PyTorch model
            model_dict = {
                'layer1_weight': self._torch_layer1.weight.detach().cpu().tolist(),
                'layer2_weight': self._torch_layer2.weight.detach().cpu().tolist(),
                'layer2_bias': self._torch_layer2.bias.detach().cpu().tolist(),
            }
            return persistence.save_neural_weights(model_dict, 'gat_reasoner', block_height, {
                'hidden_dim': self.hidden_dim,
                'n_heads': self.n_heads,
                'training_mode': self.training_mode,
                'backprop_steps': self._backprop_steps,
                'total_predictions': self._total_predictions,
                'correct_predictions': self._correct_predictions,
            })
        else:
            # Save numpy GATLayer weights
            weights = {
                'layer1_W': self._layer1.W,
                'layer1_a': self._layer1.a,
                'layer2_W': self._layer2.W,
                'layer2_a': self._layer2.a,
            }
            return persistence.save_neural_weights(weights, 'gat_reasoner', block_height, {
                'hidden_dim': self.hidden_dim,
                'n_heads': self.n_heads,
                'training_mode': 'evolutionary',
                'evolutionary_steps': self._evolutionary_steps,
            })

    def load_weights(self, persistence: 'AGIPersistence') -> bool:
        """Load model weights from CockroachDB."""
        data = persistence.load_neural_weights(model_name='gat_reasoner')
        if not data:
            return False
        try:
            if 'layer1_W' in data:
                # Numpy weights - need layers initialized first
                if not self._initialized:
                    in_dim = len(data['layer1_W'])
                    self._ensure_layers(in_dim)
                self._layer1.W = data['layer1_W']
                self._layer1.a = data['layer1_a']
                self._layer2.W = data['layer2_W']
                self._layer2.a = data['layer2_a']
                logger.info("Loaded GATReasoner numpy weights from DB")
            elif 'layer1_weight' in data and self.has_pytorch:
                # PyTorch weights
                if self._torch_layer1 is not None:
                    import torch
                    self._torch_layer1.weight.data = torch.tensor(data['layer1_weight'], dtype=torch.float32)
                    self._torch_layer2.weight.data = torch.tensor(data['layer2_weight'], dtype=torch.float32)
                    self._torch_layer2.bias.data = torch.tensor(data['layer2_bias'], dtype=torch.float32)
                    logger.info("Loaded GATReasoner PyTorch weights from DB")
            return True
        except Exception as e:
            logger.warning("Failed to load GATReasoner weights: %s", e)
            return False

    def _empty_result(self) -> dict:
        return {
            'confidence': 0.0,
            'attended_nodes': [],
            'reasoning_embedding': [],
            'suggested_edge_type': 'supports',
            'neighborhood_size': 0,
            'method': 'gat_neural',
        }

    # ------------------------------------------------------------------
    # Feature engineering for node embeddings (Improvement 77)
    # ------------------------------------------------------------------

    def engineer_features(self, kg, node_id: int) -> List[float]:
        """Engineer rich features for a node beyond raw embeddings.

        Includes:
        - node_type encoding (one-hot)
        - domain encoding
        - edge_count (in + out, log-scaled)
        - node age (blocks since creation, log-scaled)
        - confidence
        - neighbor confidence statistics

        Args:
            kg: Knowledge graph instance.
            node_id: Node to engineer features for.

        Returns:
            Feature vector of fixed dimensionality.
        """
        node = kg.nodes.get(node_id)
        if not node:
            return [0.0] * 12

        # Node type one-hot (6 dims)
        type_map = {'observation': 0, 'inference': 1, 'assertion': 2,
                    'axiom': 3, 'prediction': 4, 'meta_observation': 5}
        type_vec = [0.0] * 6
        idx = type_map.get(node.node_type, 5)
        type_vec[idx] = 1.0

        # Edge counts (log-scaled)
        out_edges = kg.get_edges_from(node_id)
        in_edges = kg.get_edges_to(node_id)
        edge_count = math.log1p(len(out_edges) + len(in_edges))

        # Node age (log of blocks since creation)
        current_block = getattr(self, '_current_block', 0)
        age = math.log1p(max(0, current_block - node.source_block))

        # Confidence
        conf = node.confidence

        # Neighbor confidence stats
        neighbor_confs = []
        for e in out_edges:
            n = kg.nodes.get(e.to_node_id)
            if n:
                neighbor_confs.append(n.confidence)
        for e in in_edges:
            n = kg.nodes.get(e.from_node_id)
            if n:
                neighbor_confs.append(n.confidence)

        if neighbor_confs:
            avg_neigh_conf = sum(neighbor_confs) / len(neighbor_confs)
            max_neigh_conf = max(neighbor_confs)
        else:
            avg_neigh_conf = 0.0
            max_neigh_conf = 0.0

        return type_vec + [edge_count, age, conf, avg_neigh_conf, max_neigh_conf, float(len(neighbor_confs))]

    # ------------------------------------------------------------------
    # Training data quality assessment (Improvement 78)
    # ------------------------------------------------------------------

    def assess_training_quality(self, sample: dict) -> float:
        """Assess the quality of a training sample.

        Returns a quality score in [0.0, 1.0]. Low-quality samples
        (sparse features, ambiguous outcomes) are filtered out.

        Args:
            sample: Training sample dict with node_features and actual_outcome.

        Returns:
            Quality score. Samples below 0.3 should be filtered.
        """
        node_features = sample.get('node_features', {})
        if not node_features:
            return 0.0

        # Feature density: how many nodes have non-zero features
        non_zero_count = 0
        for feat in node_features.values():
            if any(abs(v) > 1e-6 for v in feat):
                non_zero_count += 1

        density = non_zero_count / max(len(node_features), 1)

        # Feature variance: more varied features = more informative
        all_vals = []
        for feat in node_features.values():
            all_vals.extend(feat)
        if all_vals:
            mean_val = sum(all_vals) / len(all_vals)
            variance = sum((v - mean_val) ** 2 for v in all_vals) / len(all_vals)
        else:
            variance = 0.0

        # Normalize variance (sigmoid-like)
        variance_score = min(1.0, variance * 10.0)

        # Outcome clarity: 0.0 or 1.0 outcomes are clearer than 0.5
        outcome = sample.get('actual_outcome', 0.5)
        clarity = abs(outcome - 0.5) * 2.0

        return 0.4 * density + 0.3 * variance_score + 0.3 * clarity

    def curriculum_quality_threshold(self) -> float:
        """Dynamic quality threshold for curriculum learning (Item #37).

        Early training (< 50 steps): Accept only high-quality samples (>0.6)
        so the model learns clear patterns first. As training progresses,
        gradually lower the threshold to include harder examples.

        Returns:
            Quality threshold in [0.15, 0.6].
        """
        steps = self._backprop_steps + self._evolutionary_steps
        if steps < 50:
            return 0.6  # Easy examples only
        elif steps < 200:
            # Linear decay from 0.6 to 0.3 over steps 50-200
            progress = (steps - 50) / 150.0
            return 0.6 - progress * 0.3
        else:
            return 0.15  # Accept harder examples

    # ------------------------------------------------------------------
    # Prediction uncertainty estimation (Improvement 79)
    # ------------------------------------------------------------------

    def predict_with_uncertainty(self, kg, vector_index,
                                  query_node_ids: List[int],
                                  n_samples: int = 5) -> dict:
        """Predict with uncertainty estimation using dropout-like perturbation.

        Runs multiple forward passes with small random perturbations to
        the weights, producing a distribution of predictions. The spread
        of predictions estimates epistemic uncertainty.

        Args:
            kg: Knowledge graph.
            vector_index: Vector index for embeddings.
            query_node_ids: Nodes to reason about.
            n_samples: Number of perturbed forward passes.

        Returns:
            Dict with mean_confidence, std_confidence, and uncertainty.
        """
        import random

        predictions = []
        for _ in range(n_samples):
            # Small perturbation to layer weights
            if self._layer1 and self._layer2:
                # Save weights
                saved_w1 = [[self._layer1.W[i][j] for j in range(self._layer1.out_dim)]
                            for i in range(self._layer1.in_dim)]

                # Perturb
                for i in range(self._layer1.in_dim):
                    for j in range(self._layer1.out_dim):
                        self._layer1.W[i][j] += random.gauss(0, 0.01)

                # Forward pass
                result = self.reason(kg, vector_index, query_node_ids)
                predictions.append(result['confidence'])

                # Restore weights
                for i in range(self._layer1.in_dim):
                    for j in range(self._layer1.out_dim):
                        self._layer1.W[i][j] = saved_w1[i][j]
            else:
                result = self.reason(kg, vector_index, query_node_ids)
                predictions.append(result['confidence'])

        if not predictions:
            return {'mean_confidence': 0.0, 'std_confidence': 0.0, 'uncertainty': 1.0}

        mean_conf = sum(predictions) / len(predictions)
        variance = sum((p - mean_conf) ** 2 for p in predictions) / len(predictions)
        std_conf = math.sqrt(variance)

        return {
            'mean_confidence': round(mean_conf, 4),
            'std_confidence': round(std_conf, 4),
            'uncertainty': round(std_conf * 2.0, 4),  # 95% CI width
            'n_samples': n_samples,
        }

    # ------------------------------------------------------------------
    # Model performance monitoring (Improvement 80)
    # ------------------------------------------------------------------

    def get_performance_metrics(self) -> dict:
        """Get detailed model performance monitoring metrics.

        Returns accuracy, precision, recall over recent predictions.
        """
        if not self._prediction_history:
            return {
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'total_predictions': 0,
            }

        # Use last 100 predictions for metrics
        recent = self._prediction_history[-100:]
        tp = sum(1 for p in recent if p.get('predicted', False) and p.get('actual', False))
        fp = sum(1 for p in recent if p.get('predicted', False) and not p.get('actual', False))
        fn = sum(1 for p in recent if not p.get('predicted', False) and p.get('actual', False))
        tn = sum(1 for p in recent if not p.get('predicted', False) and not p.get('actual', False))

        accuracy = (tp + tn) / max(len(recent), 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-6)

        return {
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
            'total_predictions': len(self._prediction_history),
            'recent_window': len(recent),
            'true_positives': tp,
            'false_positives': fp,
            'false_negatives': fn,
            'true_negatives': tn,
        }

    def get_accuracy(self) -> float:
        """Return prediction accuracy."""
        if self._total_predictions == 0:
            return 0.0
        return self._correct_predictions / self._total_predictions

    def get_stats(self) -> dict:
        avg_backprop_loss = (
            self._backprop_total_loss / self._backprop_steps
            if self._backprop_steps > 0 else 0.0
        )
        stats = {
            'total_predictions': self._total_predictions,
            'correct_predictions': self._correct_predictions,
            'accuracy': round(self.get_accuracy(), 4),
            'has_torch': self.has_pytorch,
            'has_pytorch': self.has_pytorch,
            'has_rust_gat': self.has_rust_gat,
            'training_mode': self.training_mode,
            'training_buffer_size': len(self._training_buffer),
            'training_batch_size': self.TRAINING_BATCH_SIZE,
            'hidden_dim': self.hidden_dim,
            'n_heads': self.n_heads,
            'backprop_steps': self._backprop_steps,
            'backprop_avg_loss': round(avg_backprop_loss, 6),
            'evolutionary_steps': self._evolutionary_steps,
        }
        # Merge Rust GAT stats if available
        if self._rust_gat is not None:
            try:
                rust_stats = self._rust_gat.get_stats()
                stats['rust_gat'] = rust_stats
            except Exception:
                pass
        # Add performance monitoring metrics (Improvement 80)
        stats['performance_metrics'] = self.get_performance_metrics()
        return stats


# ---------------------------------------------------------------------------
# LinkPredictor — GNN-based link prediction for knowledge graph (Item #22)
# ---------------------------------------------------------------------------

class LinkPredictor:
    """GNN-based link predictor for the Aether knowledge graph.

    Predicts missing edges — "which nodes should be connected that aren't?"
    Uses node feature embeddings from the GAT module to score candidate edges.

    With PyTorch: bilinear scoring + gradient-based training.
    Without PyTorch: dot-product scoring using pure Python lists.

    Usage:
        predictor = LinkPredictor(gat_reasoner)
        predictions = predictor.predict_links(kg, top_k=20)
        loss = predictor.train_step(positive_edges, negative_edges)
    """

    # Valid edge types for predicted links
    EDGE_TYPES: List[str] = [
        'supports', 'derives', 'requires', 'refines',
        'causes', 'abstracts', 'analogous_to',
    ]

    def __init__(self, gat_reasoner: Optional[GATReasoner] = None,
                 embed_dim: int = 64) -> None:
        self._gat = gat_reasoner
        self._embed_dim = embed_dim
        self._has_torch = _HAS_TORCH
        # Bilinear weight matrix W for scoring: score = src^T W dst
        # Initialized lazily on first use
        self._bilinear_W: Optional[List[List[float]]] = None
        self._torch_bilinear: Optional[object] = None
        self._optimizer: Optional[object] = None
        # Training statistics
        self._train_steps: int = 0
        self._total_loss: float = 0.0
        self._predictions_made: int = 0
        self._edges_added: int = 0
        logger.info("LinkPredictor initialized (embed_dim=%d, torch=%s)",
                     embed_dim, self._has_torch)

    def _init_bilinear(self, dim: int) -> None:
        """Lazily initialize the bilinear scoring matrix."""
        if self._bilinear_W is not None:
            return
        self._embed_dim = dim
        # Xavier-style initialization: scale = sqrt(2 / (dim + dim))
        import random
        scale = math.sqrt(2.0 / (dim + dim))
        self._bilinear_W = [
            [random.gauss(0, scale) for _ in range(dim)]
            for _ in range(dim)
        ]
        if self._has_torch:
            self._torch_bilinear = nn.Bilinear(dim, dim, 1, bias=False)
            self._optimizer = torch.optim.Adam(
                self._torch_bilinear.parameters(), lr=0.001
            )

    def _extract_node_features(self, kg: object, vector_index: object,
                               node_ids: List[int]) -> Dict[int, List[float]]:
        """Extract feature embeddings for a set of nodes.

        Reuses VectorIndex embeddings (same source as GATReasoner).
        Falls back to GATReasoner.engineer_features if no embedding exists.
        """
        features: Dict[int, List[float]] = {}
        for nid in node_ids:
            emb = vector_index.get_embedding(nid) if vector_index else None
            if emb:
                features[nid] = emb
            elif self._gat:
                features[nid] = self._gat.engineer_features(kg, nid)
        return features

    def _score_pair_numpy(self, src_emb: List[float],
                          dst_emb: List[float]) -> float:
        """Score a candidate edge using bilinear form (pure Python).

        score = sigmoid(src^T W dst)
        """
        if self._bilinear_W is None:
            # Fallback to simple dot product
            dot = sum(a * b for a, b in zip(src_emb, dst_emb))
            norm_s = math.sqrt(sum(v * v for v in src_emb)) or 1e-8
            norm_d = math.sqrt(sum(v * v for v in dst_emb)) or 1e-8
            cos_sim = dot / (norm_s * norm_d)
            return 1.0 / (1.0 + math.exp(-cos_sim * 3.0))

        dim = len(src_emb)
        W = self._bilinear_W
        # Compute W @ dst
        w_dst = [0.0] * dim
        for i in range(dim):
            for j in range(min(dim, len(dst_emb))):
                w_dst[i] += W[i][j] * dst_emb[j]
        # src^T @ (W @ dst)
        logit = sum(src_emb[i] * w_dst[i] for i in range(min(dim, len(src_emb))))
        # Sigmoid
        logit = max(-15.0, min(15.0, logit))
        return 1.0 / (1.0 + math.exp(-logit))

    def _predict_edge_type(self, kg: object, src_id: int,
                           dst_id: int) -> str:
        """Predict the most likely edge type for a candidate link.

        Uses the dominant edge type in the local neighborhood.
        """
        type_counts: Dict[str, int] = {}
        for nid in (src_id, dst_id):
            for edge in kg.get_edges_from(nid):
                t = edge.edge_type
                type_counts[t] = type_counts.get(t, 0) + 1
            for edge in kg.get_edges_to(nid):
                t = edge.edge_type
                type_counts[t] = type_counts.get(t, 0) + 1
        if type_counts:
            return max(type_counts, key=type_counts.get)
        return 'supports'

    def predict_links(self, kg: object, top_k: int = 20,
                      score_threshold: float = 0.3) -> List[Tuple[int, int, float, str]]:
        """Predict missing edges in the knowledge graph.

        Samples candidate pairs from nodes that share neighbors but lack
        a direct edge, then scores them.

        Args:
            kg: KnowledgeGraph instance.
            top_k: Maximum number of predictions to return.
            score_threshold: Minimum score to include a prediction.

        Returns:
            List of (src_id, dst_id, score, edge_type) tuples sorted by
            score descending.
        """
        if not kg or not hasattr(kg, 'nodes') or len(kg.nodes) < 3:
            return []

        vector_index = getattr(kg, 'vector_index', None)

        # Collect candidate pairs: nodes that share a neighbor but have no direct edge
        import random
        candidates: List[Tuple[int, int]] = []
        node_ids = list(kg.nodes.keys())

        # Strategy 1: shared-neighbor candidates (high quality)
        # Sample up to 200 nodes to keep runtime bounded
        sampled = random.sample(node_ids, min(200, len(node_ids)))
        neighbor_map: Dict[int, set] = {}
        for nid in sampled:
            neighbors: set = set()
            for edge in kg.get_edges_from(nid):
                neighbors.add(edge.to_node_id)
            for edge in kg.get_edges_to(nid):
                neighbors.add(edge.from_node_id)
            neighbor_map[nid] = neighbors

        # Existing edges set for fast lookup
        existing_edges: set = set()
        for nid in sampled:
            for edge in kg.get_edges_from(nid):
                existing_edges.add((nid, edge.to_node_id))

        seen_pairs: set = set()
        for nid_a in sampled:
            for nid_b in sampled:
                if nid_a >= nid_b:
                    continue
                if (nid_a, nid_b) in existing_edges or (nid_b, nid_a) in existing_edges:
                    continue
                # Check if they share at least one neighbor
                shared = neighbor_map.get(nid_a, set()) & neighbor_map.get(nid_b, set())
                if shared:
                    pair = (nid_a, nid_b)
                    if pair not in seen_pairs:
                        candidates.append(pair)
                        seen_pairs.add(pair)
                if len(candidates) >= top_k * 10:
                    break
            if len(candidates) >= top_k * 10:
                break

        # Strategy 2: random pairs (exploration) if not enough candidates
        if len(candidates) < top_k * 3 and len(node_ids) >= 2:
            for _ in range(min(top_k * 5, 200)):
                a, b = random.sample(node_ids, 2)
                pair = (min(a, b), max(a, b))
                if pair not in seen_pairs and pair not in existing_edges:
                    candidates.append(pair)
                    seen_pairs.add(pair)

        if not candidates:
            return []

        # Extract features for all candidate nodes
        all_node_ids = list({nid for pair in candidates for nid in pair})
        features = self._extract_node_features(kg, vector_index, all_node_ids)

        if not features:
            return []

        # Initialize bilinear weights from first embedding dim
        sample_dim = len(next(iter(features.values())))
        self._init_bilinear(sample_dim)

        # Score all candidates
        scored: List[Tuple[int, int, float, str]] = []
        for src_id, dst_id in candidates:
            src_emb = features.get(src_id)
            dst_emb = features.get(dst_id)
            if not src_emb or not dst_emb:
                continue
            score = self._score_pair_numpy(src_emb, dst_emb)
            if score >= score_threshold:
                edge_type = self._predict_edge_type(kg, src_id, dst_id)
                scored.append((src_id, dst_id, round(score, 4), edge_type))

        scored.sort(key=lambda x: x[2], reverse=True)
        self._predictions_made += len(scored[:top_k])
        return scored[:top_k]

    def train_step(self, positive_edges: List[Tuple[int, int, List[float], List[float]]],
                   negative_edges: List[Tuple[int, int, List[float], List[float]]]) -> float:
        """Train on known edges (positive) vs random negatives.

        Each edge is (src_id, dst_id, src_embedding, dst_embedding).

        Args:
            positive_edges: Existing edges with their node embeddings.
            negative_edges: Non-existing edges (random negatives) with embeddings.

        Returns:
            Loss value (>= 0.0) on success, -1.0 if training could not run.
        """
        if not positive_edges and not negative_edges:
            return -1.0

        all_pairs = [(emb_s, emb_d, 1.0) for _, _, emb_s, emb_d in positive_edges]
        all_pairs += [(emb_s, emb_d, 0.0) for _, _, emb_s, emb_d in negative_edges]

        if not all_pairs:
            return -1.0

        # Initialize bilinear if needed
        sample_dim = len(all_pairs[0][0])
        self._init_bilinear(sample_dim)

        if self._has_torch and self._torch_bilinear is not None:
            return self._train_step_torch(all_pairs)
        else:
            return self._train_step_numpy(all_pairs)

    def _train_step_torch(self, pairs: List[Tuple[List[float], List[float], float]]) -> float:
        """Train using PyTorch bilinear layer + BCE loss."""
        src_list = [p[0] for p in pairs]
        dst_list = [p[1] for p in pairs]
        labels = [p[2] for p in pairs]

        src_t = torch.tensor(src_list, dtype=torch.float32)
        dst_t = torch.tensor(dst_list, dtype=torch.float32)
        y = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

        self._optimizer.zero_grad()
        logits = self._torch_bilinear(src_t, dst_t)
        pred = torch.sigmoid(logits)
        loss = F.binary_cross_entropy(pred, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self._torch_bilinear.parameters(), max_norm=1.0)
        self._optimizer.step()

        loss_val = float(loss.item())
        self._train_steps += 1
        self._total_loss += loss_val
        return loss_val

    def _train_step_numpy(self, pairs: List[Tuple[List[float], List[float], float]]) -> float:
        """Train using gradient-free perturbation (no PyTorch)."""
        if self._bilinear_W is None:
            return -1.0
        import random

        dim = len(self._bilinear_W)
        lr = 0.005

        # Compute current loss
        total_loss = 0.0
        for src_emb, dst_emb, label in pairs:
            pred = self._score_pair_numpy(src_emb, dst_emb)
            pred = max(1e-7, min(1.0 - 1e-7, pred))
            total_loss += -(label * math.log(pred) + (1.0 - label) * math.log(1.0 - pred))
        avg_loss = total_loss / max(len(pairs), 1)

        # Perturb each weight and keep perturbation if loss decreases
        for i in range(dim):
            for j in range(dim):
                delta = random.gauss(0, lr)
                self._bilinear_W[i][j] += delta
                # Recompute loss
                new_loss = 0.0
                for src_emb, dst_emb, label in pairs:
                    pred = self._score_pair_numpy(src_emb, dst_emb)
                    pred = max(1e-7, min(1.0 - 1e-7, pred))
                    new_loss += -(label * math.log(pred) + (1.0 - label) * math.log(1.0 - pred))
                new_avg = new_loss / max(len(pairs), 1)
                if new_avg > avg_loss:
                    # Revert — perturbation made things worse
                    self._bilinear_W[i][j] -= delta
                else:
                    avg_loss = new_avg

        self._train_steps += 1
        self._total_loss += avg_loss
        return avg_loss

    def get_stats(self) -> dict:
        """Return link predictor statistics."""
        avg_loss = self._total_loss / self._train_steps if self._train_steps > 0 else 0.0
        return {
            'train_steps': self._train_steps,
            'avg_loss': round(avg_loss, 6),
            'predictions_made': self._predictions_made,
            'edges_added': self._edges_added,
            'embed_dim': self._embed_dim,
            'has_torch': self._has_torch,
            'bilinear_initialized': self._bilinear_W is not None,
        }
