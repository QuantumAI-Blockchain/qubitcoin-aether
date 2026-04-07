"""
Aether Tree v5 Sephirot Cognitive Processors.

Each module implements a CognitiveProcessor subclass that performs
real computation over the knowledge graph. Ten processors, one per
Sephirah, compete in the Global Workspace.
"""

from .binah_logic import BinahLogicProcessor
from .chesed_explorer import ChesedExplorerProcessor
from .chochmah_intuition import ChochmahIntuitionProcessor
from .gevurah_safety import GevurahSafetyProcessor
from .hod_language import HodLanguageProcessor
from .keter_meta import KeterMetaProcessor
from .malkuth_action import MalkuthActionProcessor
from .netzach_reinforcement import NetzachReinforcementProcessor
from .tiferet_integrator import TiferetIntegratorProcessor
from .yesod_memory import YesodMemoryProcessor

__all__ = [
    "BinahLogicProcessor",
    "ChesedExplorerProcessor",
    "ChochmahIntuitionProcessor",
    "GevurahSafetyProcessor",
    "HodLanguageProcessor",
    "KeterMetaProcessor",
    "MalkuthActionProcessor",
    "NetzachReinforcementProcessor",
    "TiferetIntegratorProcessor",
    "YesodMemoryProcessor",
]
