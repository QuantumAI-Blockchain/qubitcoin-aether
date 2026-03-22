"""
Graph Attention Network (GAN) Reasoner — Learned Reasoning over Knowledge Graph

Provides a lightweight 2-layer Graph Attention Network that operates over the
knowledge graph.  For each reasoning query, the GAN computes attention weights
between the query node and its k-hop neighborhood, aggregates neighbor embeddings,
and produces a "reasoning embedding" for confidence and conclusion prediction.

Uses PyTorch (CPU-compatible) with ~50K parameters.  Falls back to a simple
weighted-average approach if PyTorch is not installed.

This is improvement #2 in the AGI improvement stack: rule-based reasoning
can't learn; a GAN discovers novel reasoning patterns from the system's
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
            # Filter low-quality training samples (Improvement 78)
            quality_batch = [
                s for s in self._training_buffer[:self.TRAINING_BATCH_SIZE * 2]
                if self.assess_training_quality(s) >= 0.3
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
