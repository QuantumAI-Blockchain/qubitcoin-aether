"""
QVM Plugin Architecture — Dynamic plugin loading and lifecycle management

Plugins extend the QVM without modifying core protocol code.  Each plugin
is a Python class that implements the ``QVMPlugin`` interface and registers
domain-specific handlers (hooks) that fire during transaction execution.

Architecture:
    QVMPlugin       — base interface every plugin must implement
    PluginRegistry  — global catalog of discovered plugins
    PluginManager   — lifecycle management (load, start, stop, unload)
"""
import importlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Plugin lifecycle states ───────────────────────────────────────────
class PluginState(IntEnum):
    REGISTERED = 0
    LOADED = 1
    STARTED = 2
    STOPPED = 3
    ERROR = 4


# ── Plugin metadata ──────────────────────────────────────────────────
@dataclass
class PluginMeta:
    """Metadata about a registered plugin."""
    name: str
    version: str
    description: str
    author: str = ''
    state: int = PluginState.REGISTERED
    loaded_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'author': self.author,
            'state': PluginState(self.state).name,
            'loaded_at': self.loaded_at,
            'error': self.error,
        }


# ── Hook types ────────────────────────────────────────────────────────
class HookType(IntEnum):
    PRE_EXECUTE = 0    # Before bytecode execution
    POST_EXECUTE = 1   # After bytecode execution
    PRE_DEPLOY = 2     # Before contract deployment
    POST_DEPLOY = 3    # After contract deployment
    ON_LOG = 4         # When LOG0-LOG4 fires


# ── Base plugin interface ─────────────────────────────────────────────
class QVMPlugin(ABC):
    """Base interface that all QVM plugins must implement."""

    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...

    @abstractmethod
    def version(self) -> str:
        """Semver version string."""
        ...

    def description(self) -> str:
        return ''

    def author(self) -> str:
        return ''

    def on_load(self) -> None:
        """Called when the plugin is loaded."""
        pass

    def on_start(self) -> None:
        """Called when the plugin is started."""
        pass

    def on_stop(self) -> None:
        """Called when the plugin is stopped."""
        pass

    def hooks(self) -> Dict[int, Callable]:
        """Return a mapping of HookType → handler callable.

        Handlers receive ``(context: dict) -> Optional[dict]``.
        Returning a dict merges it into the execution context.
        """
        return {}


# ── Plugin Registry ───────────────────────────────────────────────────
class PluginRegistry:
    """Global catalog of discovered plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, QVMPlugin] = {}
        self._meta: Dict[str, PluginMeta] = {}

    def register(self, plugin: QVMPlugin) -> PluginMeta:
        """Register a plugin instance.  Returns its metadata."""
        name = plugin.name()
        if name in self._plugins:
            raise ValueError(f"Plugin '{name}' is already registered")
        meta = PluginMeta(
            name=name,
            version=plugin.version(),
            description=plugin.description(),
            author=plugin.author(),
        )
        self._plugins[name] = plugin
        self._meta[name] = meta
        logger.info(f"Plugin registered: {name} v{meta.version}")
        return meta

    def unregister(self, name: str) -> bool:
        """Remove a plugin from the registry."""
        if name in self._plugins:
            del self._plugins[name]
            del self._meta[name]
            return True
        return False

    def get(self, name: str) -> Optional[QVMPlugin]:
        return self._plugins.get(name)

    def get_meta(self, name: str) -> Optional[PluginMeta]:
        return self._meta.get(name)

    def list_plugins(self) -> List[PluginMeta]:
        return list(self._meta.values())

    def __contains__(self, name: str) -> bool:
        return name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)


# ── Plugin Manager ────────────────────────────────────────────────────
class PluginManager:
    """Lifecycle management: load, start, stop, unload plugins.

    Also dispatches hooks to all started plugins.
    """

    def __init__(self) -> None:
        self.registry = PluginRegistry()
        self._hooks: Dict[int, List[Callable]] = {ht: [] for ht in HookType}

    def register(self, plugin: QVMPlugin) -> PluginMeta:
        """Register and load a plugin."""
        meta = self.registry.register(plugin)
        return meta

    def load(self, name: str) -> bool:
        """Call on_load() for a registered plugin."""
        plugin = self.registry.get(name)
        meta = self.registry.get_meta(name)
        if not plugin or not meta:
            return False
        try:
            plugin.on_load()
            meta.state = PluginState.LOADED
            meta.loaded_at = time.time()
            logger.info(f"Plugin loaded: {name}")
            return True
        except Exception as e:
            meta.state = PluginState.ERROR
            meta.error = str(e)
            logger.error(f"Plugin load failed: {name} — {e}")
            return False

    def start(self, name: str) -> bool:
        """Start a loaded plugin and register its hooks."""
        plugin = self.registry.get(name)
        meta = self.registry.get_meta(name)
        if not plugin or not meta:
            return False
        if meta.state not in (PluginState.LOADED, PluginState.STOPPED):
            return False
        try:
            plugin.on_start()
            meta.state = PluginState.STARTED
            # Register hooks
            for hook_type, handler in plugin.hooks().items():
                self._hooks[hook_type].append(handler)
            logger.info(f"Plugin started: {name}")
            return True
        except Exception as e:
            meta.state = PluginState.ERROR
            meta.error = str(e)
            logger.error(f"Plugin start failed: {name} — {e}")
            return False

    def stop(self, name: str) -> bool:
        """Stop a running plugin and remove its hooks."""
        plugin = self.registry.get(name)
        meta = self.registry.get_meta(name)
        if not plugin or not meta:
            return False
        if meta.state != PluginState.STARTED:
            return False
        try:
            plugin.on_stop()
            meta.state = PluginState.STOPPED
            # Remove hooks for this plugin
            for hook_type, handler in plugin.hooks().items():
                if handler in self._hooks[hook_type]:
                    self._hooks[hook_type].remove(handler)
            logger.info(f"Plugin stopped: {name}")
            return True
        except Exception as e:
            meta.state = PluginState.ERROR
            meta.error = str(e)
            return False

    def unload(self, name: str) -> bool:
        """Unregister a plugin completely."""
        self.stop(name)
        return self.registry.unregister(name)

    def dispatch_hook(self, hook_type: int, context: dict) -> dict:
        """Call all registered handlers for a hook type.

        Each handler receives the context dict and may return a dict
        that gets merged back into context.
        """
        for handler in self._hooks.get(hook_type, []):
            try:
                result = handler(context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.error(f"Plugin hook error ({HookType(hook_type).name}): {e}")
        return context

    def list_plugins(self) -> List[dict]:
        """Return serialisable metadata for all plugins."""
        return [m.to_dict() for m in self.registry.list_plugins()]

    def load_from_module(self, module_path: str) -> Optional[PluginMeta]:
        """Dynamically import a module and register its plugin.

        The module must define a ``create_plugin() -> QVMPlugin`` factory.
        """
        try:
            mod = importlib.import_module(module_path)
            factory = getattr(mod, 'create_plugin', None)
            if not callable(factory):
                logger.error(f"Module {module_path} has no create_plugin()")
                return None
            plugin = factory()
            meta = self.register(plugin)
            self.load(plugin.name())
            return meta
        except Exception as e:
            logger.error(f"Failed to load plugin from {module_path}: {e}")
            return None
