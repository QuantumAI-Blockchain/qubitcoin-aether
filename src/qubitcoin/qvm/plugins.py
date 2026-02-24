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
import importlib.util
import inspect
import os
import sys
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

    def discover_plugins(self, directory: str) -> List[PluginMeta]:
        """Scan a directory for Python files containing QVMPlugin subclasses.

        Each ``.py`` file in *directory* is inspected.  If it defines a
        ``create_plugin()`` factory, that is used.  Otherwise, the module
        is scanned for concrete ``QVMPlugin`` subclasses and each is
        instantiated (zero-arg constructor) and registered.

        Args:
            directory: Absolute or relative path to a directory of plugin files.

        Returns:
            List of PluginMeta for all successfully registered plugins.
        """
        discovered: List[PluginMeta] = []
        directory = os.path.abspath(directory)

        if not os.path.isdir(directory):
            logger.warning(f"Plugin directory does not exist: {directory}")
            return discovered

        for filename in sorted(os.listdir(directory)):
            if not filename.endswith('.py') or filename.startswith('_'):
                continue

            filepath = os.path.join(directory, filename)
            module_name = f"qvm_plugin_{filename[:-3]}"

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)

                # Prefer create_plugin() factory if available
                factory = getattr(mod, 'create_plugin', None)
                if callable(factory):
                    plugin = factory()
                    if plugin.name() not in self.registry:
                        meta = self.register(plugin)
                        self.load(plugin.name())
                        discovered.append(meta)
                    continue

                # Fallback: find all concrete QVMPlugin subclasses in module
                for attr_name in dir(mod):
                    obj = getattr(mod, attr_name)
                    if (inspect.isclass(obj)
                            and issubclass(obj, QVMPlugin)
                            and obj is not QVMPlugin
                            and not inspect.isabstract(obj)):
                        try:
                            plugin = obj()
                            if plugin.name() not in self.registry:
                                meta = self.register(plugin)
                                self.load(plugin.name())
                                discovered.append(meta)
                        except Exception as inst_err:
                            logger.warning(
                                f"Cannot instantiate {attr_name} from {filename}: {inst_err}"
                            )

            except Exception as e:
                logger.error(f"Failed to discover plugin from {filename}: {e}")

        logger.info(f"Discovered {len(discovered)} plugin(s) from {directory}")
        return discovered

    def reload_plugin(self, name: str) -> bool:
        """Hot-reload a plugin that was loaded from a Python module.

        This stops the running plugin, reimports the source module,
        re-creates the plugin instance via its ``create_plugin()``
        factory (or by re-instantiating the class), and restarts it.

        The plugin must already be registered.  Its module must be
        importable (present in ``sys.modules``).

        Args:
            name: The name of the plugin to reload.

        Returns:
            True if the plugin was successfully reloaded, False otherwise.
        """
        plugin = self.registry.get(name)
        meta = self.registry.get_meta(name)
        if not plugin or not meta:
            logger.error(f"Cannot reload unknown plugin: {name}")
            return False

        # Find the module that defines this plugin class
        plugin_class = type(plugin)
        module_name = plugin_class.__module__

        if module_name not in sys.modules:
            logger.error(f"Cannot reload {name}: module {module_name} not in sys.modules")
            return False

        # Stop and unregister the old instance
        self.stop(name)
        self.registry.unregister(name)

        # Reload the module
        try:
            old_module = sys.modules[module_name]
            reloaded_module = importlib.reload(old_module)

            # Prefer create_plugin() factory
            factory = getattr(reloaded_module, 'create_plugin', None)
            if callable(factory):
                new_plugin = factory()
            else:
                # Find the same class name in the reloaded module
                new_class = getattr(reloaded_module, plugin_class.__name__, None)
                if new_class is None or not issubclass(new_class, QVMPlugin):
                    logger.error(
                        f"Reloaded module {module_name} no longer defines {plugin_class.__name__}"
                    )
                    return False
                new_plugin = new_class()

            new_meta = self.register(new_plugin)
            self.load(new_plugin.name())
            self.start(new_plugin.name())
            logger.info(f"Plugin reloaded: {name} v{new_meta.version}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload plugin {name}: {e}")
            return False
