# QVM Plugin SDK

> **How to build, register, and deploy plugins for the Qubitcoin QVM.**

---

## 1. Overview

The QVM plugin system allows extending the virtual machine with domain-specific
functionality without modifying core protocol code. Plugins can intercept contract
execution, deployment, and event logging through a hook-based architecture.

**Built-in plugins:**
- **Privacy Plugin** — SUSY swaps, confidential transactions, ZK proof generation
- **Oracle Plugin** — Price feeds, data aggregation, quantum-secured pricing
- **Governance Plugin** — DAO implementation, voting, proposal management
- **DeFi Plugin** — Lending protocol, DEX (AMM), staking system

---

## 2. Plugin Architecture

```
┌─────────────────────────────────────────────┐
│  QVM Bytecode Interpreter                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │PRE_EXEC │→ │ EXECUTE │→ │POST_EXEC│    │
│  └────┬────┘  └─────────┘  └────┬────┘    │
│       │                          │          │
│  ┌────▼──────────────────────────▼────┐    │
│  │       Plugin Manager (dispatch)     │    │
│  └────┬──────┬──────┬──────┬─────────┘    │
│       │      │      │      │               │
│  ┌────▼─┐┌──▼──┐┌──▼──┐┌──▼──┐           │
│  │Privacy││Oracle││Gov  ││DeFi │           │
│  │Plugin ││Plugin││Plugin││Plugin│          │
│  └──────┘└─────┘└─────┘└─────┘           │
└─────────────────────────────────────────────┘
```

---

## 3. Creating a Plugin

### 3.1 Basic Structure

Every plugin must extend `QVMPlugin` and implement the required methods:

```python
from qubitcoin.qvm.plugins import QVMPlugin, HookType

class MyPlugin(QVMPlugin):
    """Example QVM plugin."""

    def name(self) -> str:
        return "my_plugin"

    def version(self) -> str:
        return "1.0.0"

    def description(self) -> str:
        return "My custom QVM plugin"

    def author(self) -> str:
        return "Your Name"

    def hooks(self) -> dict:
        return {
            HookType.PRE_EXECUTE: self._pre_execute,
            HookType.POST_EXECUTE: self._post_execute,
        }

    def on_load(self) -> None:
        """Called when plugin is loaded. Initialize resources here."""
        self._state = {}

    def on_start(self) -> None:
        """Called when plugin is started. Hooks are now active."""
        pass

    def on_stop(self) -> None:
        """Called when plugin is stopped. Clean up resources."""
        self._state.clear()

    def _pre_execute(self, context: dict) -> dict | None:
        """Called before every contract execution."""
        # Inspect or modify the execution context
        tx = context.get("transaction")
        if tx and self._should_process(tx):
            return {"my_plugin_data": "injected"}
        return None

    def _post_execute(self, context: dict) -> dict | None:
        """Called after every contract execution."""
        receipt = context.get("receipt")
        if receipt:
            self._track_result(receipt)
        return None
```

### 3.2 Factory Function (for Dynamic Loading)

If your plugin will be loaded dynamically from a module path, expose a factory:

```python
def create_plugin() -> QVMPlugin:
    """Factory function for dynamic plugin loading."""
    return MyPlugin()
```

---

## 4. Hook Types

| Hook | When | Use Cases |
|------|------|-----------|
| `PRE_EXECUTE` (0) | Before bytecode execution | Validate inputs, inject state, gate access |
| `POST_EXECUTE` (1) | After bytecode execution | Track results, generate proofs, update caches |
| `PRE_DEPLOY` (2) | Before contract deployment | Validate bytecode, check compliance, estimate fees |
| `POST_DEPLOY` (3) | After contract deployment | Index contract, register with oracle, auto-verify |
| `ON_LOG` (4) | When LOG0-LOG4 fires | Parse events, track transfers, trigger actions |

### 4.1 Hook Context

Hooks receive a `context` dictionary with execution data:

```python
# PRE_EXECUTE / POST_EXECUTE context:
{
    "transaction": Transaction,     # The transaction being executed
    "contract_address": str,        # Target contract
    "sender": str,                  # Transaction sender
    "value": int,                   # QBC value attached
    "gas_limit": int,               # Gas limit
    "bytecode": bytes,              # Contract bytecode
    "receipt": TransactionReceipt,  # (POST only) Execution result
}

# PRE_DEPLOY / POST_DEPLOY context:
{
    "deployer": str,                # Contract deployer address
    "bytecode": bytes,              # Contract bytecode
    "contract_address": str,        # (POST only) Deployed address
}

# ON_LOG context:
{
    "address": str,                 # Contract that emitted the log
    "topics": list[str],            # Log topics (indexed params)
    "data": str,                    # Log data (non-indexed params)
    "block_height": int,            # Block number
}
```

### 4.2 Hook Return Values

- Return `None` — no effect on execution context
- Return a `dict` — merged into the context (keys added/updated)
- Raise an exception — caught and logged, execution continues

---

## 5. Plugin Lifecycle

```
  register()     load()       start()      stop()       unload()
     │             │            │            │             │
     ▼             ▼            ▼            ▼             ▼
 REGISTERED ──→ LOADED ──→ STARTED ──→ STOPPED ──→ (removed)
                   │                       │
                   └──── ERROR ◄───────────┘
```

### 5.1 Registration

```python
from qubitcoin.qvm.plugins import PluginManager

manager = PluginManager()
plugin = MyPlugin()
manager.register(plugin)   # State: REGISTERED
manager.load("my_plugin")  # State: LOADED (on_load() called)
manager.start("my_plugin") # State: STARTED (hooks active)
```

### 5.2 Dynamic Loading

```python
# Load from module path (module must have create_plugin() factory)
manager.load_from_module("my_package.my_plugin")
```

### 5.3 Stopping and Unloading

```python
manager.stop("my_plugin")   # State: STOPPED (hooks removed)
manager.unload("my_plugin") # Plugin removed from registry
```

---

## 6. Built-in Plugin Reference

### 6.1 Privacy Plugin (`privacy_plugin.py`)

**Hooks:** `PRE_EXECUTE`, `POST_EXECUTE`, `ON_LOG`

**Key features:**
- Detects Susy Swap transactions and prepares Pedersen commitments
- Generates ZK range proof receipts after execution
- Filters private transaction logs to prevent information leakage
- Tracks stealth address records

```python
from qubitcoin.qvm.privacy_plugin import create_plugin
privacy = create_plugin()
```

### 6.2 Oracle Plugin (`oracle_plugin.py`)

**Hooks:** `PRE_EXECUTE`, `POST_EXECUTE`

**Key features:**
- Maintains price feeds from multiple sources
- Aggregates prices using median/mean algorithms
- Detects stale data and triggers circuit breakers
- Provides QUSD/QBC price for fee calculation

```python
from qubitcoin.qvm.oracle_plugin import create_plugin
oracle = create_plugin()
```

### 6.3 Governance Plugin (`governance_plugin.py`)

**Hooks:** `PRE_EXECUTE`

**Key features:**
- DAO proposal creation, voting, and execution
- Stake-proportional voting weight
- Configurable quorum thresholds
- Timelock execution for approved proposals
- Proposal states: PENDING → ACTIVE → PASSED/REJECTED → EXECUTED/CANCELLED

```python
from qubitcoin.qvm.governance_plugin import create_plugin
gov = create_plugin()
```

### 6.4 DeFi Plugin (`defi_plugin.py`)

**Hooks:** `PRE_EXECUTE`, `POST_EXECUTE`

**Key features:**
- Lending pools with collateralization enforcement (150% minimum)
- Liquidation checks on under-collateralized positions
- AMM (constant product x*y=k) for DEX swaps
- Staking system with configurable APR rewards

```python
from qubitcoin.qvm.defi_plugin import create_plugin
defi = create_plugin()
```

---

## 7. Testing Plugins

```python
import pytest
from unittest.mock import MagicMock
from qubitcoin.qvm.plugins import PluginManager, HookType

class TestMyPlugin:
    def test_registration(self):
        manager = PluginManager()
        plugin = MyPlugin()
        manager.register(plugin)
        assert "my_plugin" in [m.name for m in manager.list_plugins()]

    def test_pre_execute_hook(self):
        plugin = MyPlugin()
        plugin.on_load()

        context = {
            "transaction": MagicMock(tx_type="contract_call"),
            "sender": "0x" + "aa" * 20,
        }
        result = plugin._pre_execute(context)
        # Assert expected behavior

    def test_lifecycle(self):
        manager = PluginManager()
        plugin = MyPlugin()
        manager.register(plugin)
        manager.load("my_plugin")
        manager.start("my_plugin")
        # Verify hooks are dispatched
        ctx = manager.dispatch_hook(HookType.PRE_EXECUTE, {"test": True})
        manager.stop("my_plugin")
```

---

## 8. Security Considerations

1. **Plugins run with full VM access** — they can read/modify execution context
2. **Validate all hook return values** — don't blindly trust injected data
3. **Handle exceptions gracefully** — hook errors are logged but don't block execution
4. **Use typed dataclasses** — avoid raw dicts for plugin state
5. **Test extensively** — plugins affect every contract execution on the chain
6. **Audit third-party plugins** — review code before loading untrusted plugins

---

## 9. File Reference

```
src/qubitcoin/qvm/
├── plugins.py            # Plugin manager, registry, base class, hooks
├── privacy_plugin.py     # SUSY swaps, ZK proofs
├── oracle_plugin.py      # Price feeds, data aggregation
├── governance_plugin.py  # DAO, voting, proposals
└── defi_plugin.py        # Lending, DEX, staking
```
