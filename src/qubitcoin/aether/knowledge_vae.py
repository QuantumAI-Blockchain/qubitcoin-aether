"""
Variational Autoencoder for Knowledge Compression — Item #36

Compresses KG subgraphs into compact latent representations via a VAE:
- Encoder: features (dim=32) -> hidden (dim=16) -> mu + log_var (dim=8)
- Decoder: z (dim=8) -> hidden (dim=16) -> reconstructed (dim=32)
- Reparameterization trick for differentiable sampling
- Subgraph compression via averaged latent representations
"""
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    """Numerically stable sigmoid."""
    return np.where(x >= 0,
                    1.0 / (1.0 + np.exp(-x)),
                    np.exp(x) / (1.0 + np.exp(x)))


def _relu(x: np.ndarray) -> np.ndarray:
    """ReLU activation."""
    return np.maximum(x, 0)


def _relu_deriv(x: np.ndarray) -> np.ndarray:
    """ReLU derivative."""
    return (x > 0).astype(np.float64)


class KnowledgeVAE:
    """Variational Autoencoder for knowledge graph subgraph compression."""

    def __init__(self, input_dim: int = 32, hidden_dim: int = 16,
                 latent_dim: int = 8, lr: float = 0.001,
                 kl_weight: float = 0.1) -> None:
        """Initialize VAE weights.

        Args:
            input_dim: Dimension of input feature vectors.
            hidden_dim: Dimension of hidden layer.
            latent_dim: Dimension of latent space.
            lr: Learning rate for gradient updates.
            kl_weight: Weight for KL divergence term (beta-VAE).
        """
        self._input_dim = input_dim
        self._hidden_dim = hidden_dim
        self._latent_dim = latent_dim
        self._lr = lr
        self._kl_weight = kl_weight

        rng = np.random.default_rng(42)
        scale = np.sqrt(2.0 / input_dim)

        # Encoder weights
        self._enc_W1 = rng.normal(0, scale, (input_dim, hidden_dim))
        self._enc_b1 = np.zeros(hidden_dim)
        self._enc_W_mu = rng.normal(0, np.sqrt(2.0 / hidden_dim), (hidden_dim, latent_dim))
        self._enc_b_mu = np.zeros(latent_dim)
        self._enc_W_logvar = rng.normal(0, np.sqrt(2.0 / hidden_dim), (hidden_dim, latent_dim))
        self._enc_b_logvar = np.zeros(latent_dim)

        # Decoder weights
        self._dec_W1 = rng.normal(0, np.sqrt(2.0 / latent_dim), (latent_dim, hidden_dim))
        self._dec_b1 = np.zeros(hidden_dim)
        self._dec_W2 = rng.normal(0, np.sqrt(2.0 / hidden_dim), (hidden_dim, input_dim))
        self._dec_b2 = np.zeros(input_dim)

        # Training stats
        self._train_steps: int = 0
        self._total_loss: float = 0.0
        self._total_recon_loss: float = 0.0
        self._total_kl_loss: float = 0.0
        self._compressions: int = 0
        self._samples_generated: int = 0
        self._latent_store: List[np.ndarray] = []
        self._max_latent_store: int = 5000

    def encode(self, features: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Encode features to latent distribution parameters.

        Args:
            features: Input of shape (input_dim,) or (batch, input_dim).

        Returns:
            (mu, log_var) each of shape (latent_dim,) or (batch, latent_dim).
        """
        x = np.atleast_2d(features).astype(np.float64)
        h = _relu(x @ self._enc_W1 + self._enc_b1)
        mu = h @ self._enc_W_mu + self._enc_b_mu
        log_var = h @ self._enc_W_logvar + self._enc_b_logvar
        # Clamp log_var for numerical stability
        log_var = np.clip(log_var, -10, 10)

        if features.ndim == 1:
            return mu.squeeze(0), log_var.squeeze(0)
        return mu, log_var

    def _reparameterize(self, mu: np.ndarray, log_var: np.ndarray) -> np.ndarray:
        """Reparameterization trick: z = mu + std * epsilon."""
        std = np.exp(0.5 * log_var)
        eps = np.random.default_rng().standard_normal(mu.shape)
        return mu + std * eps

    def decode(self, z: np.ndarray) -> np.ndarray:
        """Decode latent vector to reconstructed features.

        Args:
            z: Latent vector of shape (latent_dim,) or (batch, latent_dim).

        Returns:
            Reconstructed features of shape (input_dim,) or (batch, input_dim).
        """
        z = np.atleast_2d(z).astype(np.float64)
        h = _relu(z @ self._dec_W1 + self._dec_b1)
        out = h @ self._dec_W2 + self._dec_b2  # Linear output
        if z.shape[0] == 1:
            return out.squeeze(0)
        return out

    def compress_subgraph(self, node_features: List[np.ndarray]) -> np.ndarray:
        """Compress a subgraph (list of node features) into a single latent vector.

        Encodes each node feature and returns the mean latent representation.

        Args:
            node_features: List of feature vectors, each (input_dim,).

        Returns:
            Averaged latent vector of shape (latent_dim,).
        """
        if not node_features:
            return np.zeros(self._latent_dim)

        self._compressions += 1
        latents = []
        for feat in node_features:
            feat = np.asarray(feat, dtype=np.float64)
            if feat.shape[0] != self._input_dim:
                if feat.shape[0] < self._input_dim:
                    feat = np.pad(feat, (0, self._input_dim - feat.shape[0]))
                else:
                    feat = feat[:self._input_dim]
            mu, _ = self.encode(feat)
            latents.append(mu)

        avg_latent = np.mean(latents, axis=0)

        # Store for later retrieval/sampling
        if len(self._latent_store) < self._max_latent_store:
            self._latent_store.append(avg_latent.copy())

        return avg_latent

    def train_step(self, features: np.ndarray) -> float:
        """One training step: forward pass, compute loss, backward pass.

        Computes reconstruction loss (MSE) + KL divergence and updates
        weights via gradient descent.

        Args:
            features: Input features of shape (input_dim,) or (batch, input_dim).

        Returns:
            Total loss (recon + kl_weight * kl).
        """
        x = np.atleast_2d(features).astype(np.float64)
        batch_size = x.shape[0]

        # --- Forward pass ---
        # Encoder
        h_enc_pre = x @ self._enc_W1 + self._enc_b1
        h_enc = _relu(h_enc_pre)
        mu = h_enc @ self._enc_W_mu + self._enc_b_mu
        log_var = np.clip(h_enc @ self._enc_W_logvar + self._enc_b_logvar, -10, 10)

        # Reparameterize
        std = np.exp(0.5 * log_var)
        eps = np.random.default_rng().standard_normal(mu.shape)
        z = mu + std * eps

        # Decoder
        h_dec_pre = z @ self._dec_W1 + self._dec_b1
        h_dec = _relu(h_dec_pre)
        x_recon = h_dec @ self._dec_W2 + self._dec_b2

        # --- Loss ---
        recon_loss = np.mean(np.sum((x - x_recon) ** 2, axis=1))
        kl_loss = -0.5 * np.mean(np.sum(1 + log_var - mu ** 2 - np.exp(log_var), axis=1))
        total_loss = recon_loss + self._kl_weight * kl_loss

        # --- Backward pass (manual gradients) ---
        # d(loss)/d(x_recon) = 2 * (x_recon - x) / batch_size
        d_xrecon = 2.0 * (x_recon - x) / batch_size

        # Decoder gradients
        d_dec_W2 = h_dec.T @ d_xrecon
        d_dec_b2 = np.sum(d_xrecon, axis=0)
        d_h_dec = d_xrecon @ self._dec_W2.T * _relu_deriv(h_dec_pre)
        d_dec_W1 = z.T @ d_h_dec
        d_dec_b1 = np.sum(d_h_dec, axis=0)

        # Gradient through z to encoder
        d_z = d_h_dec @ self._dec_W1.T

        # KL gradient contributions
        d_mu_kl = mu / batch_size * self._kl_weight
        d_logvar_kl = 0.5 * (np.exp(log_var) - 1) / batch_size * self._kl_weight

        # Through reparameterization: dL/d_mu = dL/dz + dL_kl/d_mu
        d_mu = d_z + d_mu_kl
        d_logvar = d_z * 0.5 * std * eps + d_logvar_kl

        # Encoder parameter gradients
        d_enc_W_mu = h_enc.T @ d_mu
        d_enc_b_mu = np.sum(d_mu, axis=0)
        d_enc_W_logvar = h_enc.T @ d_logvar
        d_enc_b_logvar = np.sum(d_logvar, axis=0)

        d_h_enc = d_mu @ self._enc_W_mu.T + d_logvar @ self._enc_W_logvar.T
        d_h_enc = d_h_enc * _relu_deriv(h_enc_pre)
        d_enc_W1 = x.T @ d_h_enc
        d_enc_b1 = np.sum(d_h_enc, axis=0)

        # --- Update weights ---
        lr = self._lr
        self._enc_W1 -= lr * np.clip(d_enc_W1, -5, 5)
        self._enc_b1 -= lr * np.clip(d_enc_b1, -5, 5)
        self._enc_W_mu -= lr * np.clip(d_enc_W_mu, -5, 5)
        self._enc_b_mu -= lr * np.clip(d_enc_b_mu, -5, 5)
        self._enc_W_logvar -= lr * np.clip(d_enc_W_logvar, -5, 5)
        self._enc_b_logvar -= lr * np.clip(d_enc_b_logvar, -5, 5)
        self._dec_W1 -= lr * np.clip(d_dec_W1, -5, 5)
        self._dec_b1 -= lr * np.clip(d_dec_b1, -5, 5)
        self._dec_W2 -= lr * np.clip(d_dec_W2, -5, 5)
        self._dec_b2 -= lr * np.clip(d_dec_b2, -5, 5)

        self._train_steps += 1
        self._total_loss += float(total_loss)
        self._total_recon_loss += float(recon_loss)
        self._total_kl_loss += float(kl_loss)

        return float(total_loss)

    def sample_similar(self, z: np.ndarray, n: int = 5) -> List[np.ndarray]:
        """Sample n points near a latent vector and decode them.

        Args:
            z: Center latent vector of shape (latent_dim,).
            n: Number of samples to generate.

        Returns:
            List of reconstructed feature vectors.
        """
        z = np.asarray(z, dtype=np.float64)
        rng = np.random.default_rng()
        samples = []
        for _ in range(n):
            noise = rng.normal(0, 0.3, z.shape)
            z_noisy = z + noise
            decoded = self.decode(z_noisy)
            samples.append(decoded)
        self._samples_generated += n
        return samples

    def reconstruct(self, features: np.ndarray) -> Tuple[np.ndarray, float]:
        """Encode and decode features, returning reconstruction and error.

        Args:
            features: Input of shape (input_dim,).

        Returns:
            (reconstructed, mse_error)
        """
        mu, log_var = self.encode(features)
        z = self._reparameterize(mu, log_var)
        recon = self.decode(z)
        mse = float(np.mean((features - recon) ** 2))
        return recon, mse

    def get_stats(self) -> Dict[str, Any]:
        """Return VAE statistics."""
        return {
            'train_steps': self._train_steps,
            'avg_loss': round(self._total_loss / max(self._train_steps, 1), 6),
            'avg_recon_loss': round(self._total_recon_loss / max(self._train_steps, 1), 6),
            'avg_kl_loss': round(self._total_kl_loss / max(self._train_steps, 1), 6),
            'compressions': self._compressions,
            'samples_generated': self._samples_generated,
            'latent_store_size': len(self._latent_store),
            'input_dim': self._input_dim,
            'latent_dim': self._latent_dim,
            'kl_weight': self._kl_weight,
        }
