"""Tests for QVM plugin architecture (Batch 15.1)."""
import pytest

from qubitcoin.qvm.plugins import (
    QVMPlugin, PluginRegistry, PluginManager,
    PluginState, PluginMeta, HookType,
)


# ── Sample plugins for testing ────────────────────────────────────────

class DummyPlugin(QVMPlugin):
    def name(self) -> str:
        return 'dummy'
    def version(self) -> str:
        return '1.0.0'
    def description(self) -> str:
        return 'A dummy plugin for testing'
    def author(self) -> str:
        return 'test'


class HookPlugin(QVMPlugin):
    """Plugin that registers hooks and records calls."""
    def __init__(self):
        self.calls: list = []

    def name(self) -> str:
        return 'hook_plugin'
    def version(self) -> str:
        return '0.1.0'

    def _pre_execute(self, ctx: dict) -> dict:
        self.calls.append('pre_execute')
        return {'hooked': True}

    def _post_execute(self, ctx: dict) -> None:
        self.calls.append('post_execute')

    def hooks(self):
        return {
            HookType.PRE_EXECUTE: self._pre_execute,
            HookType.POST_EXECUTE: self._post_execute,
        }


class FailPlugin(QVMPlugin):
    def name(self) -> str:
        return 'fail_plugin'
    def version(self) -> str:
        return '0.0.1'
    def on_load(self):
        raise RuntimeError("intentional load failure")


# ── Registry tests ────────────────────────────────────────────────────

class TestPluginRegistry:
    def test_register(self):
        reg = PluginRegistry()
        meta = reg.register(DummyPlugin())
        assert meta.name == 'dummy'
        assert meta.version == '1.0.0'
        assert meta.state == PluginState.REGISTERED

    def test_duplicate_raises(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(DummyPlugin())

    def test_get(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        assert reg.get('dummy') is not None

    def test_get_missing(self):
        reg = PluginRegistry()
        assert reg.get('nope') is None

    def test_get_meta(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        meta = reg.get_meta('dummy')
        assert meta is not None
        assert meta.description == 'A dummy plugin for testing'

    def test_unregister(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        assert reg.unregister('dummy') is True
        assert 'dummy' not in reg

    def test_unregister_missing(self):
        reg = PluginRegistry()
        assert reg.unregister('nope') is False

    def test_list_plugins(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        reg.register(HookPlugin())
        assert len(reg.list_plugins()) == 2

    def test_contains(self):
        reg = PluginRegistry()
        reg.register(DummyPlugin())
        assert 'dummy' in reg
        assert 'other' not in reg

    def test_len(self):
        reg = PluginRegistry()
        assert len(reg) == 0
        reg.register(DummyPlugin())
        assert len(reg) == 1


# ── Lifecycle tests ───────────────────────────────────────────────────

class TestPluginManager:
    def test_register_and_load(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        assert mgr.load('dummy') is True
        meta = mgr.registry.get_meta('dummy')
        assert meta.state == PluginState.LOADED
        assert meta.loaded_at is not None

    def test_start(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        mgr.load('dummy')
        assert mgr.start('dummy') is True
        assert mgr.registry.get_meta('dummy').state == PluginState.STARTED

    def test_stop(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        mgr.load('dummy')
        mgr.start('dummy')
        assert mgr.stop('dummy') is True
        assert mgr.registry.get_meta('dummy').state == PluginState.STOPPED

    def test_unload(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        mgr.load('dummy')
        assert mgr.unload('dummy') is True
        assert mgr.registry.get('dummy') is None

    def test_load_failure(self):
        mgr = PluginManager()
        mgr.register(FailPlugin())
        assert mgr.load('fail_plugin') is False
        assert mgr.registry.get_meta('fail_plugin').state == PluginState.ERROR

    def test_start_without_load(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        assert mgr.start('dummy') is False

    def test_stop_without_start(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        mgr.load('dummy')
        assert mgr.stop('dummy') is False

    def test_list_plugins(self):
        mgr = PluginManager()
        mgr.register(DummyPlugin())
        mgr.register(HookPlugin())
        listing = mgr.list_plugins()
        assert len(listing) == 2
        assert listing[0]['name'] in ('dummy', 'hook_plugin')


# ── Hook dispatch tests ───────────────────────────────────────────────

class TestHookDispatch:
    def test_pre_execute_hook(self):
        mgr = PluginManager()
        hp = HookPlugin()
        mgr.register(hp)
        mgr.load('hook_plugin')
        mgr.start('hook_plugin')
        ctx = mgr.dispatch_hook(HookType.PRE_EXECUTE, {'gas': 100})
        assert ctx.get('hooked') is True
        assert 'pre_execute' in hp.calls

    def test_post_execute_hook(self):
        mgr = PluginManager()
        hp = HookPlugin()
        mgr.register(hp)
        mgr.load('hook_plugin')
        mgr.start('hook_plugin')
        mgr.dispatch_hook(HookType.POST_EXECUTE, {})
        assert 'post_execute' in hp.calls

    def test_hooks_removed_on_stop(self):
        mgr = PluginManager()
        hp = HookPlugin()
        mgr.register(hp)
        mgr.load('hook_plugin')
        mgr.start('hook_plugin')
        mgr.stop('hook_plugin')
        hp.calls.clear()
        mgr.dispatch_hook(HookType.PRE_EXECUTE, {})
        assert len(hp.calls) == 0

    def test_no_hooks_registered(self):
        mgr = PluginManager()
        ctx = mgr.dispatch_hook(HookType.PRE_DEPLOY, {'addr': 'x'})
        assert ctx == {'addr': 'x'}

    def test_hook_error_handled(self):
        """A plugin hook error should not crash the VM."""
        def bad_hook(ctx):
            raise RuntimeError("hook boom")

        mgr = PluginManager()
        mgr._hooks[HookType.ON_LOG].append(bad_hook)
        ctx = mgr.dispatch_hook(HookType.ON_LOG, {'topic': 'test'})
        assert ctx == {'topic': 'test'}


# ── PluginMeta tests ─────────────────────────────────────────────────

class TestPluginMeta:
    def test_to_dict(self):
        meta = PluginMeta(name='x', version='1.0', description='desc')
        d = meta.to_dict()
        assert d['name'] == 'x'
        assert d['state'] == 'REGISTERED'

    def test_state_names(self):
        assert PluginState.REGISTERED.name == 'REGISTERED'
        assert PluginState.STARTED.name == 'STARTED'
        assert PluginState.ERROR.name == 'ERROR'
