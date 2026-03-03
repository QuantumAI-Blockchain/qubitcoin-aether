"""Mining client configuration — loaded from environment variables."""

import os


class MinerConfig:
    """Configuration for the VQE mining client."""

    # Substrate node WebSocket RPC endpoint
    SUBSTRATE_WS_URL: str = os.getenv("SUBSTRATE_WS_URL", "ws://127.0.0.1:9944")

    # Miner identity — sr25519 seed phrase for signing extrinsics
    # This is the Substrate account that will receive mining rewards.
    MINER_SEED: str = os.getenv("MINER_SEED", "//Alice")

    # VQE optimization parameters
    NUM_QUBITS: int = int(os.getenv("NUM_QUBITS", "4"))
    VQE_REPS: int = int(os.getenv("VQE_REPS", "2"))
    VQE_MAXITER: int = int(os.getenv("VQE_MAXITER", "200"))
    VQE_TOLERANCE: float = float(os.getenv("VQE_TOLERANCE", "1e-6"))
    MAX_MINING_ATTEMPTS: int = int(os.getenv("MAX_MINING_ATTEMPTS", "50"))

    # Quantum backend selection
    USE_GPU_AER: bool = os.getenv("USE_GPU_AER", "false").lower() == "true"
    USE_SIMULATOR: bool = os.getenv("USE_SIMULATOR", "false").lower() == "true"

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Energy scaling factor (VQE energy * 10^12 for fixed-point on-chain)
    ENERGY_SCALE: int = 10**12

    # Difficulty scaling factor (on-chain difficulty * 10^6)
    DIFFICULTY_SCALE: int = 10**6
