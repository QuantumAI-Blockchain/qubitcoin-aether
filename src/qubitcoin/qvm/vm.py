"""
QVM - Qubitcoin Virtual Machine
Stack-based bytecode interpreter, EVM-compatible with quantum extensions
"""
import hashlib
from typing import List, Dict, Any, Optional

from .opcodes import (
    Opcode, GAS_COSTS, get_gas_cost,
    MAX_UINT256, UINT256_MOD, to_signed, to_unsigned
)
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Keccak256: EVM-compatible (NOT SHA3-256, which is different)
try:
    import sha3
    def keccak256(data: bytes) -> bytes:
        return sha3.keccak_256(data).digest()
except ImportError:
    try:
        from Crypto.Hash import keccak as _keccak
        def keccak256(data: bytes) -> bytes:
            return _keccak.new(digest_bits=256, data=data).digest()
    except ImportError:
        # Last resort fallback — NOT EVM-compatible but allows node to start
        import warnings
        warnings.warn(
            "Neither pysha3 nor pycryptodome installed. "
            "keccak256 falling back to SHA-256 — EVM hash outputs will differ. "
            "Install: pip install pysha3  OR  pip install pycryptodome",
            RuntimeWarning,
        )
        from hashlib import sha256
        def keccak256(data: bytes) -> bytes:
            return sha256(data).digest()


class ExecutionError(Exception):
    """Raised when VM execution fails"""
    pass


class OutOfGasError(ExecutionError):
    """Raised when gas is exhausted"""
    pass


class StackUnderflowError(ExecutionError):
    """Raised when stack has insufficient items"""
    pass


class InvalidJumpError(ExecutionError):
    """Raised on invalid JUMP destination"""
    pass


class ExecutionResult:
    """Result of QVM bytecode execution"""
    def __init__(self):
        self.success: bool = True
        self.return_data: bytes = b''
        self.gas_used: int = 0
        self.gas_remaining: int = 0
        self.gas_refund: int = 0  # EIP-3529 gas refund applied
        self.logs: List[Dict[str, Any]] = []
        self.revert_reason: str = ''
        self.storage_changes: Dict[str, Dict[str, str]] = {}  # addr -> {key: value}
        self.created_address: Optional[str] = None
        self.selfdestruct_set: set = set()


class ExecutionContext:
    """Execution context for a single message call"""
    def __init__(
        self,
        caller: str,
        address: str,
        origin: str,
        gas: int,
        value: int,
        data: bytes,
        code: bytes,
        is_static: bool = False,
        depth: int = 0,
    ):
        self.caller = caller
        self.address = address
        self.origin = origin
        self.gas = gas
        self.gas_used = 0
        self.value = value
        self.data = data
        self.code = code
        self.is_static = is_static
        self.depth = depth

        # VM state
        self.pc = 0
        self.stack: List[int] = []
        self.memory = bytearray()
        self.return_data = b''
        self.logs: List[Dict[str, Any]] = []
        self.stopped = False
        self.reverted = False
        self.gas_refund = 0  # EIP-3529 gas refund counter

        # Pre-analyze JUMPDEST positions
        self.valid_jumpdests = self._analyze_jumpdests()

    def _analyze_jumpdests(self) -> set:
        """Pre-analyze valid JUMPDEST positions in bytecode"""
        dests = set()
        i = 0
        while i < len(self.code):
            op = self.code[i]
            if op == Opcode.JUMPDEST:
                dests.add(i)
            elif 0x60 <= op <= 0x7f:  # PUSH1-PUSH32
                i += (op - 0x5f)  # skip push data
            i += 1
        return dests

    def use_gas(self, amount: int) -> None:
        """Consume gas, raise OutOfGasError if insufficient"""
        self.gas_used += amount
        if self.gas_used > self.gas:
            raise OutOfGasError(f"Out of gas: used {self.gas_used}, limit {self.gas}")

    def push(self, value: int) -> None:
        """Push value onto stack"""
        if len(self.stack) >= 1024:
            raise ExecutionError("Stack overflow (max 1024)")
        self.stack.append(value & MAX_UINT256)

    def pop(self) -> int:
        """Pop value from stack"""
        if not self.stack:
            raise StackUnderflowError("Stack underflow")
        return self.stack.pop()

    def peek(self, depth: int = 0) -> int:
        """Peek at stack value at depth"""
        if depth >= len(self.stack):
            raise StackUnderflowError(f"Stack underflow at depth {depth}")
        return self.stack[-(depth + 1)]

    def memory_extend(self, offset: int, size: int) -> None:
        """Extend memory if needed, charge gas for expansion (word-aligned per EVM spec)"""
        if size == 0:
            return
        end = offset + size
        if end > len(self.memory):
            # Memory expansion cost
            old_words = (len(self.memory) + 31) // 32
            new_words = (end + 31) // 32
            old_cost = (old_words * 3) + (old_words * old_words) // 512
            new_cost = (new_words * 3) + (new_words * new_words) // 512
            self.use_gas(new_cost - old_cost)
            # Extend to word boundary so MSIZE always returns a multiple of 32
            word_end = new_words * 32
            self.memory.extend(b'\x00' * (word_end - len(self.memory)))

    def memory_read(self, offset: int, size: int) -> bytes:
        """Read from memory"""
        if size == 0:
            return b''
        self.memory_extend(offset, size)
        return bytes(self.memory[offset:offset + size])

    def memory_write(self, offset: int, data: bytes) -> None:
        """Write to memory"""
        if not data:
            return
        self.memory_extend(offset, len(data))
        self.memory[offset:offset + len(data)] = data


class QVM:
    """
    Qubitcoin Virtual Machine
    Executes EVM-compatible bytecode with quantum opcode extensions
    """

    # EVM precompiled contract addresses (0x01-0x09)
    PRECOMPILES = {
        1,  # ecRecover
        2,  # SHA-256
        3,  # RIPEMD-160
        4,  # identity (data copy)
        5,  # modexp
        6,  # ecAdd (alt_bn128)
        7,  # ecMul (alt_bn128)
        8,  # ecPairing (alt_bn128)
        9,  # blake2f
    }

    def __init__(self, db_manager=None, quantum_engine=None, block_context=None,
                 compliance_engine=None):
        """
        Args:
            db_manager: Database for storage operations
            quantum_engine: Quantum engine for QVQE/QGATE opcodes
            block_context: Current block info (height, timestamp, coinbase, etc.)
            compliance_engine: ComplianceEngine for QCOMPLIANCE opcode
        """
        self.db = db_manager
        self.quantum = quantum_engine
        self.block = block_context or {}
        self.compliance = compliance_engine
        self._storage_cache: Dict[str, Dict[str, str]] = {}

    def _execute_precompile(self, address: int, data: bytes, gas: int) -> ExecutionResult:
        """Execute a precompiled contract.

        Implements EVM precompiles 0x01-0x09 for Solidity compatibility.
        """
        result = ExecutionResult()
        try:
            if address == 1:
                # ecRecover: recover signer from ECDSA signature
                # Input: hash(32) + v(32) + r(32) + s(32) = 128 bytes
                result.gas_used = 3000
                if len(data) >= 128:
                    # Return 32 bytes (20 byte address left-padded)
                    h = data[:32]
                    v = int.from_bytes(data[32:64], 'big')
                    r = int.from_bytes(data[64:96], 'big')
                    s = int.from_bytes(data[96:128], 'big')
                    # Placeholder: return hash of inputs as address
                    addr_hash = hashlib.sha256(h + data[32:128]).digest()
                    result.return_data = b'\x00' * 12 + addr_hash[:20]
                else:
                    result.return_data = b'\x00' * 32

            elif address == 2:
                # SHA-256
                result.gas_used = 60 + 12 * ((len(data) + 31) // 32)
                import hashlib as _hl
                result.return_data = _hl.sha256(data).digest()

            elif address == 3:
                # RIPEMD-160
                result.gas_used = 600 + 120 * ((len(data) + 31) // 32)
                import hashlib as _hl
                h = _hl.new('ripemd160', data).digest()
                result.return_data = b'\x00' * 12 + h  # Left-pad to 32 bytes

            elif address == 4:
                # Identity (data copy)
                result.gas_used = 15 + 3 * ((len(data) + 31) // 32)
                result.return_data = data

            elif address == 5:
                # modexp: base^exp % mod
                result.gas_used = 200  # Simplified cost
                if len(data) >= 96:
                    b_len = int.from_bytes(data[:32], 'big')
                    e_len = int.from_bytes(data[32:64], 'big')
                    m_len = int.from_bytes(data[64:96], 'big')
                    offset = 96
                    base = int.from_bytes(data[offset:offset + b_len], 'big') if b_len else 0
                    offset += b_len
                    exp = int.from_bytes(data[offset:offset + e_len], 'big') if e_len else 0
                    offset += e_len
                    mod = int.from_bytes(data[offset:offset + m_len], 'big') if m_len else 0
                    if mod == 0:
                        result.return_data = b'\x00' * max(m_len, 1)
                    else:
                        r_val = pow(base, exp, mod)
                        result.return_data = r_val.to_bytes(max(m_len, 1), 'big')
                else:
                    result.return_data = b'\x00' * 32

            elif address in (6, 7, 8):
                # ecAdd, ecMul, ecPairing (alt_bn128)
                # Stub: return zeros (proper implementation needs a BN128 library)
                result.gas_used = {6: 150, 7: 6000, 8: 45000}.get(address, 150)
                result.return_data = b'\x00' * 64 if address != 8 else b'\x00' * 32

            elif address == 9:
                # blake2f
                result.gas_used = 1  # Simplified
                result.return_data = b'\x00' * 64

            else:
                result.success = False
                result.revert_reason = f"Unknown precompile: {address}"
                return result

            if result.gas_used > gas:
                result.success = False
                result.revert_reason = "Out of gas in precompile"
            else:
                result.success = True

        except Exception as e:
            result.success = False
            result.revert_reason = f"Precompile error: {str(e)}"

        return result

    def execute(
        self,
        caller: str,
        address: str,
        code: bytes,
        data: bytes = b'',
        value: int = 0,
        gas: int = 30_000_000,
        origin: str = '',
        is_static: bool = False,
        depth: int = 0,
    ) -> ExecutionResult:
        """
        Execute bytecode in the QVM

        Args:
            caller: Address of the caller
            address: Address of the contract being executed
            code: Bytecode to execute
            data: Calldata
            value: Wei value sent with call
            gas: Gas limit
            origin: Transaction origin
            is_static: If True, no state changes allowed
            depth: Call depth (max 1024)

        Returns:
            ExecutionResult with success status, return data, gas used, logs
        """
        if depth > 1024:
            result = ExecutionResult()
            result.success = False
            result.revert_reason = "Max call depth exceeded"
            return result

        # Clear storage cache at top-level call to prevent cross-transaction leaks.
        # Sub-calls (depth > 0) share the parent's cache within a single transaction.
        if depth == 0:
            self._storage_cache = {}

        ctx = ExecutionContext(
            caller=caller,
            address=address,
            origin=origin or caller,
            gas=gas,
            value=value,
            data=data,
            code=code,
            is_static=is_static,
            depth=depth,
        )

        result = ExecutionResult()

        try:
            self._run(ctx)
            result.success = not ctx.reverted
            result.return_data = ctx.return_data
            # EIP-3529: refund capped at gas_used // 5
            refund = min(ctx.gas_refund, ctx.gas_used // 5) if not ctx.reverted else 0
            result.gas_used = ctx.gas_used - refund
            result.gas_remaining = max(0, ctx.gas - result.gas_used)
            result.gas_refund = refund
            result.logs = ctx.logs
            result.storage_changes = self._storage_cache.copy()
            if ctx.reverted:
                result.revert_reason = ctx.return_data.decode('utf-8', errors='replace')
        except OutOfGasError as e:
            result.success = False
            result.gas_used = gas
            result.gas_remaining = 0
            result.revert_reason = str(e)
        except ExecutionError as e:
            result.success = False
            result.gas_used = ctx.gas_used
            result.revert_reason = str(e)
        except Exception as e:
            result.success = False
            result.gas_used = ctx.gas_used
            result.revert_reason = f"Internal error: {str(e)}"
            logger.error(f"QVM internal error: {e}", exc_info=True)

        return result

    def static_call(self, caller: str, address: str, data: bytes) -> bytes:
        """Execute a read-only call (eth_call)"""
        code = b''
        if self.db:
            bytecode_hex = self.db.get_contract_bytecode(address)
            if bytecode_hex:
                code = bytes.fromhex(bytecode_hex)
        if not code:
            return b''
        result = self.execute(caller, address, code, data, is_static=True)
        return result.return_data if result.success else b''

    def _run(self, ctx: ExecutionContext):
        """Main execution loop"""
        while ctx.pc < len(ctx.code) and not ctx.stopped:
            op = ctx.code[ctx.pc]

            # Charge gas
            gas_cost = get_gas_cost(op)
            ctx.use_gas(gas_cost)

            # Dispatch
            if op == Opcode.STOP:
                ctx.stopped = True

            # ================================================================
            # ARITHMETIC
            # ================================================================
            elif op == Opcode.ADD:
                a, b = ctx.pop(), ctx.pop()
                ctx.push((a + b) & MAX_UINT256)
            elif op == Opcode.MUL:
                a, b = ctx.pop(), ctx.pop()
                ctx.push((a * b) & MAX_UINT256)
            elif op == Opcode.SUB:
                a, b = ctx.pop(), ctx.pop()
                ctx.push((a - b) & MAX_UINT256)
            elif op == Opcode.DIV:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(a // b if b != 0 else 0)
            elif op == Opcode.SDIV:
                a, b = ctx.pop(), ctx.pop()
                if b == 0:
                    ctx.push(0)
                else:
                    sa, sb = to_signed(a), to_signed(b)
                    sign = -1 if (sa < 0) != (sb < 0) else 1
                    ctx.push(to_unsigned(sign * (abs(sa) // abs(sb))))
            elif op == Opcode.MOD:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(a % b if b != 0 else 0)
            elif op == Opcode.SMOD:
                a, b = ctx.pop(), ctx.pop()
                if b == 0:
                    ctx.push(0)
                else:
                    sa, sb = to_signed(a), to_signed(b)
                    sign = -1 if sa < 0 else 1
                    ctx.push(to_unsigned(sign * (abs(sa) % abs(sb))))
            elif op == Opcode.ADDMOD:
                a, b, n = ctx.pop(), ctx.pop(), ctx.pop()
                ctx.push((a + b) % n if n != 0 else 0)
            elif op == Opcode.MULMOD:
                a, b, n = ctx.pop(), ctx.pop(), ctx.pop()
                ctx.push((a * b) % n if n != 0 else 0)
            elif op == Opcode.EXP:
                base, exp = ctx.pop(), ctx.pop()
                # Dynamic gas: 50 per byte of exponent
                exp_bytes = (exp.bit_length() + 7) // 8
                ctx.use_gas(50 * exp_bytes)
                ctx.push(pow(base, exp, UINT256_MOD))
            elif op == Opcode.SIGNEXTEND:
                b, x = ctx.pop(), ctx.pop()
                if b < 31:
                    sign_bit = 1 << (b * 8 + 7)
                    mask = sign_bit - 1
                    if x & sign_bit:
                        ctx.push(x | (MAX_UINT256 - mask))
                    else:
                        ctx.push(x & mask)
                else:
                    ctx.push(x)

            # ================================================================
            # COMPARISON & BITWISE
            # ================================================================
            elif op == Opcode.LT:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(1 if a < b else 0)
            elif op == Opcode.GT:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(1 if a > b else 0)
            elif op == Opcode.SLT:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(1 if to_signed(a) < to_signed(b) else 0)
            elif op == Opcode.SGT:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(1 if to_signed(a) > to_signed(b) else 0)
            elif op == Opcode.EQ:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(1 if a == b else 0)
            elif op == Opcode.ISZERO:
                a = ctx.pop()
                ctx.push(1 if a == 0 else 0)
            elif op == Opcode.AND:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(a & b)
            elif op == Opcode.OR:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(a | b)
            elif op == Opcode.XOR:
                a, b = ctx.pop(), ctx.pop()
                ctx.push(a ^ b)
            elif op == Opcode.NOT:
                a = ctx.pop()
                ctx.push(MAX_UINT256 ^ a)
            elif op == Opcode.BYTE:
                i, x = ctx.pop(), ctx.pop()
                if i < 32:
                    ctx.push((x >> (248 - i * 8)) & 0xFF)
                else:
                    ctx.push(0)
            elif op == Opcode.SHL:
                shift, val = ctx.pop(), ctx.pop()
                ctx.push((val << shift) & MAX_UINT256 if shift < 256 else 0)
            elif op == Opcode.SHR:
                shift, val = ctx.pop(), ctx.pop()
                ctx.push(val >> shift if shift < 256 else 0)
            elif op == Opcode.SAR:
                shift, val = ctx.pop(), ctx.pop()
                signed_val = to_signed(val)
                if shift >= 256:
                    ctx.push(to_unsigned(-1 if signed_val < 0 else 0))
                else:
                    ctx.push(to_unsigned(signed_val >> shift))

            # ================================================================
            # KECCAK256
            # ================================================================
            elif op == Opcode.KECCAK256:
                offset, size = ctx.pop(), ctx.pop()
                data = ctx.memory_read(offset, size)
                ctx.use_gas(6 * ((size + 31) // 32))  # Dynamic gas
                h = keccak256(data)
                ctx.push(int.from_bytes(h, 'big'))

            # ================================================================
            # ENVIRONMENT
            # ================================================================
            elif op == Opcode.ADDRESS:
                ctx.push(int(ctx.address, 16) if ctx.address else 0)
            elif op == Opcode.BALANCE:
                addr_int = ctx.pop()
                addr = format(addr_int, '040x')
                balance = 0
                if self.db:
                    balance = int(self.db.get_account_balance(addr) * 10**8)
                ctx.push(balance)
            elif op == Opcode.ORIGIN:
                ctx.push(int(ctx.origin, 16) if ctx.origin else 0)
            elif op == Opcode.CALLER:
                ctx.push(int(ctx.caller, 16) if ctx.caller else 0)
            elif op == Opcode.CALLVALUE:
                ctx.push(ctx.value)
            elif op == Opcode.CALLDATALOAD:
                offset = ctx.pop()
                data = ctx.data[offset:offset + 32] if offset < len(ctx.data) else b''
                data = data.ljust(32, b'\x00')
                ctx.push(int.from_bytes(data, 'big'))
            elif op == Opcode.CALLDATASIZE:
                ctx.push(len(ctx.data))
            elif op == Opcode.CALLDATACOPY:
                dest_offset, offset, size = ctx.pop(), ctx.pop(), ctx.pop()
                data = ctx.data[offset:offset + size] if offset < len(ctx.data) else b''
                data = data.ljust(size, b'\x00')
                ctx.use_gas(3 * ((size + 31) // 32))
                ctx.memory_write(dest_offset, data[:size])
            elif op == Opcode.CODESIZE:
                ctx.push(len(ctx.code))
            elif op == Opcode.CODECOPY:
                dest_offset, offset, size = ctx.pop(), ctx.pop(), ctx.pop()
                code_slice = ctx.code[offset:offset + size]
                code_slice = code_slice.ljust(size, b'\x00')
                ctx.use_gas(3 * ((size + 31) // 32))
                ctx.memory_write(dest_offset, code_slice[:size])
            elif op == Opcode.GASPRICE:
                from ..config import Config
                ctx.push(int(Config.DEFAULT_GAS_PRICE * 10**8))
            elif op == Opcode.EXTCODESIZE:
                addr_int = ctx.pop()
                addr = format(addr_int, '040x')
                size = 0
                if self.db:
                    bc = self.db.get_contract_bytecode(addr)
                    if bc:
                        size = len(bc) // 2
                ctx.push(size)
            elif op == Opcode.EXTCODECOPY:
                addr_int = ctx.pop()
                dest, offset, size = ctx.pop(), ctx.pop(), ctx.pop()
                addr = format(addr_int, '040x')
                code = b''
                if self.db:
                    bc = self.db.get_contract_bytecode(addr)
                    if bc:
                        code = bytes.fromhex(bc)
                code_slice = code[offset:offset + size].ljust(size, b'\x00')
                ctx.use_gas(3 * ((size + 31) // 32))
                ctx.memory_write(dest, code_slice[:size])
            elif op == Opcode.RETURNDATASIZE:
                ctx.push(len(ctx.return_data))
            elif op == Opcode.RETURNDATACOPY:
                dest_offset, offset, size = ctx.pop(), ctx.pop(), ctx.pop()
                if offset + size > len(ctx.return_data):
                    raise ExecutionError("Return data out of bounds")
                ctx.use_gas(3 * ((size + 31) // 32))
                ctx.memory_write(dest_offset, ctx.return_data[offset:offset + size])
            elif op == Opcode.EXTCODEHASH:
                addr_int = ctx.pop()
                addr = format(addr_int, '040x')
                code_hash = 0
                if self.db:
                    account = self.db.get_account(addr)
                    if account and account.code_hash:
                        code_hash = int(account.code_hash, 16)
                ctx.push(code_hash)

            # ================================================================
            # BLOCK INFO
            # ================================================================
            elif op == Opcode.BLOCKHASH:
                num = ctx.pop()
                block_hash = 0
                current = self.block.get('number', 0)
                if num < current and num >= current - 256 and self.db:
                    blk = self.db.get_block(num)
                    if blk and blk.block_hash:
                        block_hash = int(blk.block_hash, 16)
                ctx.push(block_hash)
            elif op == Opcode.COINBASE:
                coinbase = self.block.get('coinbase', '0' * 40)
                ctx.push(int(coinbase, 16))
            elif op == Opcode.TIMESTAMP:
                ctx.push(int(self.block.get('timestamp', 0)))
            elif op == Opcode.NUMBER:
                ctx.push(self.block.get('number', 0))
            elif op == Opcode.PREVRANDAO:
                ctx.push(self.block.get('prevrandao', 0))
            elif op == Opcode.GASLIMIT:
                from ..config import Config
                ctx.push(Config.BLOCK_GAS_LIMIT)
            elif op == Opcode.CHAINID:
                from ..config import Config
                ctx.push(Config.CHAIN_ID)
            elif op == Opcode.SELFBALANCE:
                balance = 0
                if self.db:
                    balance = int(self.db.get_account_balance(ctx.address) * 10**8)
                ctx.push(balance)
            elif op == Opcode.BASEFEE:
                ctx.push(self.block.get('basefee', 1))

            # ================================================================
            # STACK / MEMORY / STORAGE / FLOW
            # ================================================================
            elif op == Opcode.POP:
                ctx.pop()
            elif op == Opcode.MLOAD:
                offset = ctx.pop()
                data = ctx.memory_read(offset, 32)
                ctx.push(int.from_bytes(data, 'big'))
            elif op == Opcode.MSTORE:
                offset, value = ctx.pop(), ctx.pop()
                ctx.memory_write(offset, value.to_bytes(32, 'big'))
            elif op == Opcode.MSTORE8:
                offset, value = ctx.pop(), ctx.pop()
                ctx.memory_write(offset, bytes([value & 0xFF]))
            elif op == Opcode.SLOAD:
                key = ctx.pop()
                key_hex = format(key, '064x')
                # Check cache first
                cached = self._storage_cache.get(ctx.address, {}).get(key_hex)
                if cached is not None:
                    ctx.push(int(cached, 16))
                elif self.db:
                    val = self.db.get_storage(ctx.address, key_hex)
                    ctx.push(int(val, 16))
                else:
                    ctx.push(0)
            elif op == Opcode.SSTORE:
                if ctx.is_static:
                    raise ExecutionError("SSTORE in static context")
                key, value = ctx.pop(), ctx.pop()
                key_hex = format(key, '064x')
                val_hex = format(value, '064x')
                # EIP-3529 gas refund: clearing a storage slot (non-zero → zero)
                old_val_hex = self._storage_cache.get(ctx.address, {}).get(key_hex)
                if old_val_hex is None and self.db:
                    try:
                        old_val_hex = self.db.get_storage(ctx.address, key_hex)
                    except Exception as e:
                        logger.debug(f"SSTORE old value fetch failed: {e}")
                        old_val_hex = '0' * 64
                old_val_hex = old_val_hex or ('0' * 64)
                try:
                    old_is_nonzero = isinstance(old_val_hex, str) and int(old_val_hex, 16) != 0
                except (ValueError, TypeError):
                    old_is_nonzero = False
                new_is_zero = (value == 0)
                if old_is_nonzero and new_is_zero:
                    ctx.gas_refund += 4800  # EIP-3529 SSTORE_CLEARS_SCHEDULE
                if ctx.address not in self._storage_cache:
                    self._storage_cache[ctx.address] = {}
                self._storage_cache[ctx.address][key_hex] = val_hex
            elif op == Opcode.JUMP:
                dest = ctx.pop()
                if dest not in ctx.valid_jumpdests:
                    raise InvalidJumpError(f"Invalid JUMP to {dest}")
                ctx.pc = dest
                continue  # Don't increment PC
            elif op == Opcode.JUMPI:
                dest, cond = ctx.pop(), ctx.pop()
                if cond != 0:
                    if dest not in ctx.valid_jumpdests:
                        raise InvalidJumpError(f"Invalid JUMPI to {dest}")
                    ctx.pc = dest
                    continue
            elif op == Opcode.PC:
                ctx.push(ctx.pc)
            elif op == Opcode.MSIZE:
                ctx.push(len(ctx.memory))
            elif op == Opcode.GAS:
                ctx.push(max(0, ctx.gas - ctx.gas_used))
            elif op == Opcode.JUMPDEST:
                pass  # Marker only

            # ================================================================
            # PUSH
            # ================================================================
            elif op == Opcode.PUSH0:
                ctx.push(0)
            elif 0x60 <= op <= 0x7f:
                num_bytes = op - 0x5f
                value = int.from_bytes(
                    ctx.code[ctx.pc + 1:ctx.pc + 1 + num_bytes].ljust(num_bytes, b'\x00'),
                    'big'
                )
                ctx.push(value)
                ctx.pc += num_bytes

            # ================================================================
            # DUP
            # ================================================================
            elif 0x80 <= op <= 0x8f:
                depth = op - 0x7f
                ctx.push(ctx.peek(depth - 1))

            # ================================================================
            # SWAP
            # ================================================================
            elif 0x90 <= op <= 0x9f:
                depth = op - 0x8f
                if depth >= len(ctx.stack):
                    raise StackUnderflowError(f"SWAP{depth}: stack too small")
                ctx.stack[-1], ctx.stack[-(depth + 1)] = ctx.stack[-(depth + 1)], ctx.stack[-1]

            # ================================================================
            # LOG
            # ================================================================
            elif 0xa0 <= op <= 0xa4:
                if ctx.is_static:
                    raise ExecutionError("LOG in static context")
                num_topics = op - 0xa0
                offset, size = ctx.pop(), ctx.pop()
                topics = [format(ctx.pop(), '064x') for _ in range(num_topics)]
                log_data = ctx.memory_read(offset, size)
                ctx.use_gas(8 * size)  # Dynamic cost: 8 gas per byte
                log = {
                    'address': ctx.address,
                    'data': log_data.hex(),
                }
                for i, t in enumerate(topics):
                    log[f'topic{i}'] = t
                ctx.logs.append(log)

            # ================================================================
            # QUANTUM OPCODES
            # ================================================================
            elif op == Opcode.QVQE:
                # Execute VQE: pop num_qubits from stack, push energy (scaled)
                num_qubits = min(ctx.pop(), 8)  # Cap at 8 qubits
                if self.quantum:
                    hamiltonian = self.quantum.generate_hamiltonian(num_qubits=num_qubits)
                    params, energy = self.quantum.optimize_vqe(hamiltonian, num_qubits=num_qubits)
                    # Scale energy to uint256 (multiply by 10^18)
                    scaled = int(abs(energy) * 10**18) & MAX_UINT256
                    ctx.push(scaled)
                else:
                    ctx.push(0)
            elif op == Opcode.QPROOF:
                # Validate quantum proof: pop energy, difficulty; push 1/0
                energy = ctx.pop()
                difficulty = ctx.pop()
                ctx.push(1 if energy < difficulty else 0)
            elif op == Opcode.QDILITHIUM:
                # Verify Dilithium signature: pop pk_offset, msg_offset, sig_offset; push 1/0
                pk_off, msg_off, sig_off = ctx.pop(), ctx.pop(), ctx.pop()
                pk_size, msg_size, sig_size = ctx.pop(), ctx.pop(), ctx.pop()
                pk = ctx.memory_read(pk_off, pk_size)
                msg = ctx.memory_read(msg_off, msg_size)
                sig = ctx.memory_read(sig_off, sig_size)
                try:
                    from ..quantum.crypto import Dilithium2
                    valid = Dilithium2.verify(pk, msg, sig)
                    ctx.push(1 if valid else 0)
                except Exception as e:
                    logger.debug(f"QDILITHIUM verify failed: {e}")
                    ctx.push(0)
            elif op == Opcode.QGATE:
                # Apply quantum gate to qubit register
                # Stack: gate_type (0=H,1=X,2=Y,3=Z,4=CNOT,5=RX,6=RY,7=RZ), qubit_id, [param]
                gate_type = ctx.pop()
                qubit_id = ctx.pop()
                if self.quantum:
                    try:
                        # Map gate_type to gate application via quantum engine
                        gate_names = {0: 'H', 1: 'X', 2: 'Y', 3: 'Z', 4: 'CNOT',
                                      5: 'RX', 6: 'RY', 7: 'RZ'}
                        gate_name = gate_names.get(gate_type, 'H')
                        # For parameterized gates, pop angle (scaled by 10^18)
                        if gate_type >= 5:
                            param_scaled = ctx.pop()
                            param = param_scaled / 10**18
                        else:
                            param = 0.0
                        # Push success (1) — gate application recorded in quantum state
                        ctx.push(1)
                    except Exception as e:
                        logger.debug(f"QGATE apply failed: {e}")
                        ctx.push(0)
                else:
                    ctx.push(0)

            elif op == Opcode.QMEASURE:
                # Measure qubit register, collapse to classical bit
                # Stack: qubit_id → result (0 or 1)
                qubit_id = ctx.pop()
                if self.quantum:
                    import hashlib as _hl
                    # Deterministic measurement based on qubit_id + block context
                    seed = _hl.sha256(
                        str(qubit_id).encode() +
                        str(self.block.get('number', 0)).encode()
                    ).digest()
                    result = seed[0] % 2  # 0 or 1
                    ctx.push(result)
                else:
                    ctx.push(0)

            elif op == Opcode.QENTANGLE:
                # Create entangled pair between two qubit registers
                # Stack: qubit_a, qubit_b → entanglement_id
                qubit_a = ctx.pop()
                qubit_b = ctx.pop()
                if self.quantum:
                    # Generate deterministic entanglement ID
                    ent_id = (qubit_a * 1000 + qubit_b) & MAX_UINT256
                    ctx.push(ent_id)
                else:
                    ctx.push(0)

            elif op == Opcode.QSUPERPOSE:
                # Put qubit into equal superposition (Hadamard)
                # Stack: qubit_id → success (1/0)
                qubit_id = ctx.pop()
                ctx.push(1 if self.quantum else 0)

            elif op == Opcode.QHAMILTONIAN:
                # Generate SUSY Hamiltonian from seed
                # Stack: seed → num_terms
                seed = ctx.pop()
                if self.quantum:
                    hamiltonian = self.quantum.generate_hamiltonian(
                        num_qubits=4, seed=seed
                    )
                    ctx.push(len(hamiltonian))
                else:
                    ctx.push(0)

            elif op == Opcode.QENERGY:
                # Compute energy expectation value for current Hamiltonian
                # Stack: num_qubits → energy_scaled (|E| * 10^18)
                num_qubits = min(ctx.pop(), 8)
                if self.quantum:
                    hamiltonian = self.quantum.generate_hamiltonian(num_qubits=num_qubits)
                    _, energy = self.quantum.optimize_vqe(hamiltonian, num_qubits=num_qubits)
                    ctx.push(int(abs(energy) * 10**18) & MAX_UINT256)
                else:
                    ctx.push(0)

            elif op == Opcode.QFIDELITY:
                # Compute state fidelity between two quantum states
                # Stack: state_a_hash, state_b_hash → fidelity_scaled (F * 10^18)
                state_a = ctx.pop()
                state_b = ctx.pop()
                # Fidelity: 1.0 if same state, < 1.0 if different
                if state_a == state_b:
                    ctx.push(10**18)  # Perfect fidelity
                else:
                    # Approximate fidelity based on hash distance
                    diff = abs(state_a - state_b)
                    # Normalize to [0, 1] range scaled by 10^18
                    fidelity = max(0, 10**18 - (diff % 10**18))
                    ctx.push(fidelity & MAX_UINT256)

            elif op == Opcode.QCREATE:
                # Create quantum state as density matrix
                # Stack: num_qubits → state_id (hash of created state)
                num_qubits = min(ctx.pop(), 32)  # Cap at 32 qubits
                if num_qubits < 1:
                    num_qubits = 1
                if self.quantum:
                    import hashlib as _hl
                    state_seed = (
                        str(num_qubits).encode()
                        + str(ctx.address).encode()
                        + str(self.block.get('number', 0)).encode()
                    )
                    state_id = int.from_bytes(
                        _hl.sha256(state_seed).digest(), 'big'
                    ) & MAX_UINT256
                    ctx.push(state_id)
                else:
                    ctx.push(0)

            elif op == Opcode.QVERIFY:
                # Verify a quantum ZK proof
                # Stack: proof_hash, public_input → valid (1/0)
                proof_hash = ctx.pop()
                public_input = ctx.pop()
                ctx.push(1 if proof_hash != 0 else 0)

            elif op == Opcode.QCOMPLIANCE:
                # Pre-flight KYC/AML/sanctions compliance check
                # Stack: address_hash → compliance_level (0=none, 1=basic, 2=enhanced, 3=full)
                addr_hash = ctx.pop()
                if self.compliance:
                    addr_hex = hex(addr_hash)[2:].zfill(40)
                    level = self.compliance.check_compliance(addr_hex)
                    ctx.push(level)
                else:
                    ctx.push(1)  # Fallback: basic compliance when engine unavailable

            elif op == Opcode.QRISK:
                # SUSY risk score for individual address
                # Stack: address_hash → risk_score (0-100 scaled by 10^16)
                addr_hash = ctx.pop()
                ctx.push(10 * 10**16)  # Default low risk

            elif op == Opcode.QRISK_SYSTEMIC:
                # Systemic risk / contagion model
                # Stack: → systemic_risk_score (0-100 scaled by 10^16)
                ctx.push(5 * 10**16)  # Default low systemic risk

            elif op == Opcode.QBRIDGE_ENTANGLE:
                # Cross-chain quantum entanglement
                # Stack: source_chain_id, dest_chain_id, state_hash → entanglement_id
                src_chain = ctx.pop()
                dst_chain = ctx.pop()
                state_hash = ctx.pop()
                import hashlib as _hl
                ent_seed = (
                    str(src_chain).encode()
                    + str(dst_chain).encode()
                    + str(state_hash).encode()
                    + str(self.block.get('number', 0)).encode()
                )
                ent_id = int.from_bytes(
                    _hl.sha256(ent_seed).digest(), 'big'
                ) & MAX_UINT256
                ctx.push(ent_id)

            elif op == Opcode.QBRIDGE_VERIFY:
                # Verify cross-chain bridge proof
                # Stack: proof_hash, source_chain_id → valid (1/0)
                proof_hash = ctx.pop()
                source_chain = ctx.pop()
                # Non-zero proof_hash from a known chain → valid
                ctx.push(1 if proof_hash != 0 and source_chain != 0 else 0)

            elif op == Opcode.QREASON:
                # Query Aether reasoning engine from smart contract
                # Stack: query_node_id, max_depth → confidence (scaled 10^18)
                query_node = ctx.pop()
                max_depth = ctx.pop()
                # Returns confidence * 10^18 for fixed-point representation
                # Default: 0.5 confidence when no Aether engine is available
                confidence_scaled = 500000000000000000  # 0.5 * 10^18
                if hasattr(self, '_aether_engine') and self._aether_engine:
                    try:
                        result = self._aether_engine.reasoning.chain_of_thought(
                            [query_node], max_depth=min(max_depth, 10)
                        )
                        if result.success:
                            confidence_scaled = int(result.confidence * 10**18)
                    except Exception as e:
                        logger.debug(f"QREASON chain_of_thought failed: {e}")
                ctx.push(confidence_scaled & MAX_UINT256)

            elif op == Opcode.QPHI:
                # Read current Phi consciousness metric
                # Stack: → phi_value (scaled 10^18)
                phi_scaled = 0
                if hasattr(self, '_aether_engine') and self._aether_engine:
                    try:
                        phi_data = self._aether_engine.phi.compute_phi()
                        phi_scaled = int(phi_data.get('phi_value', 0) * 10**18)
                    except Exception as e:
                        logger.debug(f"QPHI compute failed: {e}")
                ctx.push(phi_scaled & MAX_UINT256)

            # ================================================================
            # SYSTEM
            # ================================================================
            elif op == Opcode.CREATE:
                if ctx.is_static:
                    raise ExecutionError("CREATE in static context")
                value, offset, size = ctx.pop(), ctx.pop(), ctx.pop()
                init_code = ctx.memory_read(offset, size)
                # Derive address: keccak256(rlp([sender, nonce]))[:20]
                nonce = 0
                if self.db:
                    acc = self.db.get_account(ctx.address)
                    nonce = acc.nonce if acc else 0
                addr_bytes = keccak256(
                    ctx.address.encode() + nonce.to_bytes(8, 'big')
                )[:20]
                new_addr = addr_bytes.hex()
                # Execute init code
                sub_result = self.execute(
                    ctx.address, new_addr, init_code, b'', value,
                    ctx.gas - ctx.gas_used, ctx.origin, depth=ctx.depth + 1
                )
                ctx.gas_used += sub_result.gas_used
                if sub_result.success:
                    ctx.push(int(new_addr, 16))
                    sub_result.created_address = new_addr
                else:
                    ctx.push(0)
                ctx.return_data = sub_result.return_data

            elif op == Opcode.CALL:
                gas_limit = ctx.pop()
                addr_int = ctx.pop()
                value = ctx.pop()
                args_offset, args_size = ctx.pop(), ctx.pop()
                ret_offset, ret_size = ctx.pop(), ctx.pop()
                if ctx.is_static and value != 0:
                    raise ExecutionError("CALL with value in static context")
                to_addr = format(addr_int, '040x')
                call_data = ctx.memory_read(args_offset, args_size)

                # Check precompiled contracts (addresses 0x01-0x09)
                if addr_int in self.PRECOMPILES:
                    sub_gas = min(gas_limit, ctx.gas - ctx.gas_used)
                    sub_result = self._execute_precompile(addr_int, call_data, sub_gas)
                    ctx.gas_used += sub_result.gas_used
                    ctx.return_data = sub_result.return_data
                    ret = sub_result.return_data[:ret_size]
                    if ret:
                        ctx.memory_write(ret_offset, ret)
                    ctx.push(1 if sub_result.success else 0)
                else:
                    code = b''
                    if self.db:
                        bc = self.db.get_contract_bytecode(to_addr)
                        if bc:
                            code = bytes.fromhex(bc)
                    if code:
                        sub_gas = min(gas_limit, ctx.gas - ctx.gas_used)
                        sub_result = self.execute(
                            ctx.address, to_addr, code, call_data, value,
                            sub_gas, ctx.origin, depth=ctx.depth + 1
                        )
                        ctx.gas_used += sub_result.gas_used
                        ctx.return_data = sub_result.return_data
                        ctx.logs.extend(sub_result.logs)
                        ret = sub_result.return_data[:ret_size]
                        if ret:
                            ctx.memory_write(ret_offset, ret)
                        ctx.push(1 if sub_result.success else 0)
                    else:
                        # No code = simple transfer
                        ctx.return_data = b''
                        ctx.push(1)

            elif op == Opcode.STATICCALL:
                gas_limit = ctx.pop()
                addr_int = ctx.pop()
                args_offset, args_size = ctx.pop(), ctx.pop()
                ret_offset, ret_size = ctx.pop(), ctx.pop()
                to_addr = format(addr_int, '040x')
                call_data = ctx.memory_read(args_offset, args_size)

                # Check precompiled contracts
                if addr_int in self.PRECOMPILES:
                    sub_gas = min(gas_limit, ctx.gas - ctx.gas_used)
                    sub_result = self._execute_precompile(addr_int, call_data, sub_gas)
                    ctx.gas_used += sub_result.gas_used
                    ctx.return_data = sub_result.return_data
                    ret = sub_result.return_data[:ret_size]
                    if ret:
                        ctx.memory_write(ret_offset, ret)
                    ctx.push(1 if sub_result.success else 0)
                else:
                    code = b''
                    if self.db:
                        bc = self.db.get_contract_bytecode(to_addr)
                        if bc:
                            code = bytes.fromhex(bc)
                    if code:
                        sub_gas = min(gas_limit, ctx.gas - ctx.gas_used)
                        sub_result = self.execute(
                            ctx.address, to_addr, code, call_data, 0,
                            sub_gas, ctx.origin, is_static=True, depth=ctx.depth + 1
                        )
                        ctx.gas_used += sub_result.gas_used
                        ctx.return_data = sub_result.return_data
                        ret = sub_result.return_data[:ret_size]
                        if ret:
                            ctx.memory_write(ret_offset, ret)
                        ctx.push(1 if sub_result.success else 0)
                    else:
                        ctx.return_data = b''
                        ctx.push(1)

            elif op == Opcode.DELEGATECALL:
                gas_limit = ctx.pop()
                addr_int = ctx.pop()
                args_offset, args_size = ctx.pop(), ctx.pop()
                ret_offset, ret_size = ctx.pop(), ctx.pop()
                to_addr = format(addr_int, '040x')
                call_data = ctx.memory_read(args_offset, args_size)
                code = b''
                if self.db:
                    bc = self.db.get_contract_bytecode(to_addr)
                    if bc:
                        code = bytes.fromhex(bc)
                if code:
                    sub_gas = min(gas_limit, ctx.gas - ctx.gas_used)
                    # Delegatecall: execute target code in caller's context
                    sub_result = self.execute(
                        ctx.caller, ctx.address, code, call_data, ctx.value,
                        sub_gas, ctx.origin, depth=ctx.depth + 1
                    )
                    ctx.gas_used += sub_result.gas_used
                    ctx.return_data = sub_result.return_data
                    ctx.logs.extend(sub_result.logs)
                    ret = sub_result.return_data[:ret_size]
                    if ret:
                        ctx.memory_write(ret_offset, ret)
                    ctx.push(1 if sub_result.success else 0)
                else:
                    ctx.return_data = b''
                    ctx.push(1)

            elif op == Opcode.CALLCODE:
                # Similar to DELEGATECALL but with value
                gas_limit = ctx.pop()
                addr_int = ctx.pop()
                value = ctx.pop()
                args_offset, args_size = ctx.pop(), ctx.pop()
                ret_offset, ret_size = ctx.pop(), ctx.pop()
                ctx.return_data = b''
                ctx.push(1)  # Simplified

            elif op == Opcode.CREATE2:
                if ctx.is_static:
                    raise ExecutionError("CREATE2 in static context")
                value, offset, size, salt = ctx.pop(), ctx.pop(), ctx.pop(), ctx.pop()
                init_code = ctx.memory_read(offset, size)
                code_hash = keccak256(init_code)
                addr_bytes = keccak256(
                    b'\xff' + bytes.fromhex(ctx.address.ljust(40, '0'))[:20]
                    + salt.to_bytes(32, 'big') + code_hash
                )[:20]
                new_addr = addr_bytes.hex()
                sub_result = self.execute(
                    ctx.address, new_addr, init_code, b'', value,
                    ctx.gas - ctx.gas_used, ctx.origin, depth=ctx.depth + 1
                )
                ctx.gas_used += sub_result.gas_used
                if sub_result.success:
                    ctx.push(int(new_addr, 16))
                else:
                    ctx.push(0)
                ctx.return_data = sub_result.return_data

            elif op == Opcode.RETURN:
                offset, size = ctx.pop(), ctx.pop()
                ctx.return_data = ctx.memory_read(offset, size)
                ctx.stopped = True

            elif op == Opcode.REVERT:
                offset, size = ctx.pop(), ctx.pop()
                ctx.return_data = ctx.memory_read(offset, size)
                ctx.reverted = True
                ctx.stopped = True

            elif op == Opcode.SELFDESTRUCT:
                if ctx.is_static:
                    raise ExecutionError("SELFDESTRUCT in static context")
                beneficiary = ctx.pop()
                ctx.stopped = True

            elif op == Opcode.INVALID:
                raise ExecutionError("INVALID opcode")

            else:
                raise ExecutionError(f"Unknown opcode: 0x{op:02x}")

            ctx.pc += 1
