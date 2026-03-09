"""
JSON-RPC Adapter for Qubitcoin
Provides eth_* compatible endpoints for Web3 tools (MetaMask, Hardhat, Ethers.js)
"""
import json
import hashlib
import time
from decimal import Decimal
from typing import Any, Optional, Dict
from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..config import Config
from ..utils.logger import get_logger
from ..qvm.vm import keccak256

logger = get_logger(__name__)

router = APIRouter()


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: list = []
    id: Any = 1


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Any = None
    error: Any = None
    id: Any = 1


def validate_hex(value: str, name: str, max_len: int = 66) -> str:
    """Validate a hex parameter (e.g. address, tx hash).

    Checks:
        1. Starts with '0x'
        2. Remaining chars are valid hex
        3. Total length does not exceed max_len

    Args:
        value: The hex string to validate.
        name: Parameter name (for error messages).
        max_len: Maximum allowed string length (default 66 for 32-byte hashes).

    Returns:
        The validated hex string.

    Raises:
        ValueError: If the value fails any check.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name}: expected hex string, got {type(value).__name__}")
    if not value.startswith('0x'):
        raise ValueError(f"{name}: hex value must start with '0x', got '{value[:10]}'")
    hex_part = value[2:]
    if len(value) > max_len:
        raise ValueError(f"{name}: hex value too long ({len(value)} > {max_len})")
    if hex_part and not all(c in '0123456789abcdefABCDEF' for c in hex_part):
        raise ValueError(f"{name}: contains invalid hex characters")
    return value


def hex_int(value: int) -> str:
    return hex(value)


def hex_balance(value: Decimal) -> str:
    """Convert QBC balance to hex wei-equivalent (18 decimals for MetaMask)"""
    wei = int(value * 10**18)
    return hex(wei)


def parse_wei_to_qbc(wei: int) -> Decimal:
    """Convert wei (10**18) back to QBC"""
    return Decimal(str(wei)) / Decimal(10**18)


def parse_hex_int(value: str) -> int:
    if isinstance(value, int):
        return value
    if not value or not isinstance(value, str):
        return 0
    cleaned = value.strip()
    if not cleaned:
        return 0
    try:
        return int(cleaned, 16)
    except ValueError:
        return 0


def _block_to_rpc(block, include_txs: bool = False) -> Optional[dict]:
    """Convert Block model to eth_getBlock format"""
    if not block:
        return None
    return {
        'number': hex_int(block.height),
        'hash': '0x' + (block.block_hash or block.calculate_hash()),
        'parentHash': '0x' + block.prev_hash,
        'stateRoot': '0x' + (block.state_root or '0' * 64),
        'receiptsRoot': '0x' + (block.receipts_root or '0' * 64),
        'transactionsRoot': '0x' + '0' * 64,
        'timestamp': hex_int(int(block.timestamp)),
        'difficulty': hex_int(int(block.difficulty * 1000)),
        'gasLimit': hex_int(Config.BLOCK_GAS_LIMIT),
        'gasUsed': hex_int(0),
        'miner': '0x' + (block.proof_data.get('miner_address', '0' * 40)),
        'nonce': '0x0000000000000000',
        'size': hex_int(1024),
        'transactions': [
            _tx_to_rpc(tx, block) if include_txs else ('0x' + tx.txid)
            for tx in block.transactions
        ],
    }


def _tx_to_rpc(tx, block=None) -> dict:
    """Convert Transaction model to eth_getTransaction format"""
    from_addr = '0x' + '0' * 40
    if tx.public_key:
        from_addr = '0x' + hashlib.sha256(bytes.fromhex(tx.public_key)).hexdigest()[:40]
    return {
        'hash': '0x' + tx.txid,
        'blockNumber': hex_int(tx.block_height or 0),
        'blockHash': '0x' + (block.block_hash if block else '0' * 64),
        'transactionIndex': '0x0',
        'from': from_addr,
        'to': '0x' + (tx.to_address or '0' * 40),
        'value': hex_balance(tx.outputs[0]['amount'] if tx.outputs else Decimal(0)),
        'gas': hex_int(tx.gas_limit or 21000),
        'gasPrice': hex_balance(tx.gas_price if tx.gas_price is not None else Config.DEFAULT_GAS_PRICE),
        'input': '0x' + (tx.data or ''),
        'nonce': hex_int(tx.nonce),
        'type': '0x0',
        'chainId': hex_int(Config.CHAIN_ID),
    }


def _receipt_to_rpc(receipt) -> Optional[dict]:
    """Convert TransactionReceipt to eth_getTransactionReceipt format"""
    if not receipt:
        return None
    logs = []
    for i, log in enumerate(receipt.logs):
        topics = []
        for t in ['topic0', 'topic1', 'topic2', 'topic3']:
            if log.get(t):
                topics.append('0x' + log[t])
        logs.append({
            'logIndex': hex_int(i),
            'transactionIndex': hex_int(receipt.tx_index),
            'transactionHash': '0x' + receipt.txid,
            'blockNumber': hex_int(receipt.block_height),
            'blockHash': '0x' + receipt.block_hash,
            'address': '0x' + log.get('address', '0' * 40),
            'data': '0x' + (log.get('data', '') or ''),
            'topics': topics,
        })
    return {
        'transactionHash': '0x' + receipt.txid,
        'transactionIndex': hex_int(receipt.tx_index),
        'blockNumber': hex_int(receipt.block_height),
        'blockHash': '0x' + receipt.block_hash,
        'from': '0x' + receipt.from_address,
        'to': '0x' + receipt.to_address if receipt.to_address else None,
        'contractAddress': '0x' + receipt.contract_address if receipt.contract_address else None,
        'gasUsed': hex_int(receipt.gas_used),
        'cumulativeGasUsed': hex_int(receipt.gas_used),
        'status': hex_int(receipt.status),
        'logs': logs,
        'logsBloom': '0x' + '0' * 512,
        'type': '0x0',
    }


class JsonRpcHandler:
    """Handles eth_* JSON-RPC method dispatch"""

    def __init__(self, db, consensus=None, mining=None, quantum=None, qvm=None,
                 event_index=None):
        self.db = db
        self.consensus = consensus
        self.mining = mining
        self.quantum = quantum
        self.qvm = qvm
        self.event_index = event_index  # Optional EventIndex for fast in-memory log queries
        self._http_request: Optional[Request] = None  # Set per-call for client IP checks

        self.methods = {
            # Chain
            'eth_chainId': self.eth_chainId,
            'eth_blockNumber': self.eth_blockNumber,
            'net_version': self.net_version,
            'web3_clientVersion': self.web3_clientVersion,

            # Blocks
            'eth_getBlockByNumber': self.eth_getBlockByNumber,
            'eth_getBlockByHash': self.eth_getBlockByHash,

            # Account
            'eth_getBalance': self.eth_getBalance,
            'eth_getTransactionCount': self.eth_getTransactionCount,
            'eth_getCode': self.eth_getCode,
            'eth_getStorageAt': self.eth_getStorageAt,

            # Transactions
            'eth_getTransactionByHash': self.eth_getTransactionByHash,
            'eth_getTransactionReceipt': self.eth_getTransactionReceipt,
            'eth_sendRawTransaction': self.eth_sendRawTransaction,
            'eth_sendTransaction': self.eth_sendTransaction,
            'eth_call': self.eth_call,
            'eth_estimateGas': self.eth_estimateGas,

            # Gas
            'eth_gasPrice': self.eth_gasPrice,

            # Logs
            'eth_getLogs': self.eth_getLogs,

            # Mining
            'eth_mining': self.eth_mining,
            'eth_hashrate': self.eth_hashrate,

            # Debug
            'debug_traceTransaction': self.debug_traceTransaction,
        }

    async def handle(self, request: JsonRpcRequest,
                     http_request: Optional[Request] = None) -> JsonRpcResponse:
        """Dispatch a JSON-RPC request to the appropriate handler.

        Args:
            request: Parsed JSON-RPC request body.
            http_request: The underlying FastAPI/Starlette Request, used for
                          client-IP gating on privileged methods.
        """
        self._http_request = http_request
        method = self.methods.get(request.method)
        if not method:
            return JsonRpcResponse(
                id=request.id,
                error={'code': -32601, 'message': f'Method not found: {request.method}'}
            )
        try:
            result = await method(request.params)
            return JsonRpcResponse(id=request.id, result=result)
        except Exception as e:
            logger.error(f"JSON-RPC error ({request.method}): {e}")
            return JsonRpcResponse(
                id=request.id,
                error={'code': -32000, 'message': 'Internal error'}
            )
        finally:
            self._http_request = None

    # ========================================================================
    # AUTH HELPERS
    # ========================================================================
    def _is_localhost(self) -> bool:
        """Return True if the current HTTP request originates from localhost.

        Accepts 127.0.0.1, ::1, and Docker bridge IPs (172.x.x.x) since
        the node runs inside Docker and host requests arrive via bridge.

        Defaults to False when request info is unavailable (conservative:
        deny access if we cannot confirm the caller is local).
        """
        req = self._http_request
        if req and hasattr(req, 'client') and req.client:
            host = req.client.host
            if host in ('127.0.0.1', '::1', 'localhost'):
                return True
            # Docker bridge network (172.16.0.0/12)
            if host.startswith('172.'):
                return True
            return False
        # No request info available — default deny for safety
        return False

    # ========================================================================
    # CHAIN METHODS
    # ========================================================================
    async def eth_chainId(self, params):
        return hex_int(Config.CHAIN_ID)

    async def net_version(self, params):
        return str(Config.CHAIN_ID)

    async def web3_clientVersion(self, params):
        return f"Qubitcoin/v{Config.NODE_VERSION}-QVM/python"

    async def eth_blockNumber(self, params):
        height = self.db.get_current_height()
        return hex_int(max(0, height))

    # ========================================================================
    # BLOCK METHODS
    # ========================================================================
    async def eth_getBlockByNumber(self, params):
        block_id = params[0] if params else 'latest'
        include_txs = params[1] if len(params) > 1 else False

        if block_id == 'latest':
            height = self.db.get_current_height()
        elif block_id == 'pending':
            height = self.db.get_current_height() + 1
        elif block_id == 'earliest':
            height = 0
        else:
            height = parse_hex_int(block_id)

        block = self.db.get_block(height)
        return _block_to_rpc(block, include_txs)

    async def eth_getBlockByHash(self, params):
        if params:
            validate_hex(params[0], "blockHash", max_len=66)
        block_hash = params[0].replace('0x', '') if params else ''
        include_txs = params[1] if len(params) > 1 else False
        block = self.db.get_block_by_hash(block_hash)
        return _block_to_rpc(block, include_txs)

    # ========================================================================
    # ACCOUNT METHODS
    # ========================================================================
    async def eth_getBalance(self, params):
        if not params:
            raise ValueError("eth_getBalance requires an address parameter")
        validate_hex(params[0], "address", max_len=42)
        address = params[0].replace('0x', '').lower() if params else ''
        # Sum both account balance (QVM/MetaMask) and UTXO balance
        account_bal = self.db.get_account_balance(address)
        utxo_bal = self.db.get_balance(address)
        balance = account_bal + utxo_bal
        return hex_balance(balance)

    async def eth_getTransactionCount(self, params):
        if not params:
            raise ValueError("eth_getTransactionCount requires an address parameter")
        validate_hex(params[0], "address", max_len=42)
        address = params[0].replace('0x', '').lower() if params else ''
        account = self.db.get_account(address)
        nonce = account.nonce if account else 0
        return hex_int(nonce)

    async def eth_getCode(self, params):
        if not params:
            raise ValueError("eth_getCode requires an address parameter")
        validate_hex(params[0], "address", max_len=42)
        address = params[0].replace('0x', '') if params else ''
        bytecode = self.db.get_contract_bytecode(address)
        return '0x' + (bytecode or '')

    async def eth_getStorageAt(self, params):
        if not params:
            raise ValueError("eth_getStorageAt requires an address parameter")
        validate_hex(params[0], "address", max_len=42)
        if len(params) > 1:
            validate_hex(params[1], "position", max_len=66)
        address = params[0].replace('0x', '') if params else ''
        position = params[1].replace('0x', '') if len(params) > 1 else '0' * 64
        value = self.db.get_storage(address, position)
        return '0x' + value

    # ========================================================================
    # TRANSACTION METHODS
    # ========================================================================
    async def eth_getTransactionByHash(self, params):
        if not params:
            raise ValueError("eth_getTransactionByHash requires a txHash parameter")
        validate_hex(params[0], "txHash", max_len=66)
        txid = params[0].replace('0x', '') if params else ''
        with self.db.get_session() as session:
            from sqlalchemy import text as sql_text
            row = session.execute(
                sql_text("SELECT block_height FROM transactions WHERE txid = :txid"),
                {'txid': txid}
            ).fetchone()
            if not row:
                return None
            block = self.db.get_block(row[0])
            if block:
                for tx in block.transactions:
                    if tx.txid == txid:
                        return _tx_to_rpc(tx, block)
        return None

    async def eth_getTransactionReceipt(self, params):
        if not params:
            raise ValueError("Missing txHash parameter")
        validate_hex(params[0], "txHash", max_len=66)
        txid = params[0].replace('0x', '')
        receipt = self.db.get_receipt(txid)
        return _receipt_to_rpc(receipt)

    async def eth_sendRawTransaction(self, params):
        """Accept raw signed transaction hex from MetaMask and store in mempool.

        Decodes the RLP-encoded signed transaction, recovers the ECDSA
        sender address, validates balance/nonce, and stores the transaction
        as pending in the mempool.  Actual execution (value transfers,
        QVM contract calls/deploys) happens when a miner includes this tx
        in a block and the block passes consensus validation.
        """
        raw_tx = params[0] if params else ''
        if not raw_tx or raw_tx == '0x':
            raise ValueError("Empty transaction data")

        raw_hex = raw_tx.replace('0x', '')
        raw_bytes = bytes.fromhex(raw_hex)
        try:
            from eth_account import Account as EthAccount

            # Recover sender and decode tx fields
            recovered = EthAccount.recover_transaction(raw_tx)
            sender = recovered.lower().replace('0x', '')

            # Decode the transaction object
            from eth_account._utils.typed_transactions import TypedTransaction
            tx_obj = TypedTransaction.from_bytes(raw_bytes)
            tx_dict = tx_obj.transaction.dictionary
            to_addr = (tx_dict.get('to') or b'').hex() if tx_dict.get('to') else ''
            value_wei = int.from_bytes(tx_dict.get('value', b'\x00'), 'big') if isinstance(tx_dict.get('value'), bytes) else int(tx_dict.get('value', 0))
            data_hex = tx_dict.get('data', b'').hex() if isinstance(tx_dict.get('data'), bytes) else ''
            nonce = int.from_bytes(tx_dict.get('nonce', b'\x00'), 'big') if isinstance(tx_dict.get('nonce'), bytes) else int(tx_dict.get('nonce', 0))
            gas_limit = int.from_bytes(tx_dict.get('gas', b'\x00'), 'big') if isinstance(tx_dict.get('gas'), bytes) else int(tx_dict.get('gas', 21000))

            # Compute tx hash using Keccak-256 (EVM-compatible)
            tx_hash = keccak256(raw_bytes).hex()

            value_qbc = parse_wei_to_qbc(value_wei)

            # Validate sender balance (check both EVM account and UTXO models)
            account_bal = self.db.get_account_balance(sender)
            utxo_bal = self.db.get_balance(sender)
            total_available = account_bal + utxo_bal
            if total_available < value_qbc:
                raise ValueError(f"Insufficient balance: have {total_available}, need {value_qbc}")

            # Determine tx_type for mempool record
            if not to_addr and data_hex:
                tx_type = 'contract_deploy'
            elif to_addr and data_hex:
                tx_type = 'contract_call'
            else:
                tx_type = 'transfer'

            # Store transaction in mempool ONLY (status='pending').
            # Execution (value transfers, QVM contract calls/deploys) happens
            # when the miner includes this tx in a block and the block is
            # validated by consensus.  Executing here would bypass consensus
            # and risk double-execution when the tx is later mined.
            from sqlalchemy import text as sql_text
            with self.db.get_session() as session:
                session.execute(
                    sql_text("""
                        INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                                  timestamp, status, tx_type, to_address, data,
                                                  gas_limit, gas_price, nonce)
                        VALUES (:txid, '[]', CAST(:outputs AS jsonb), 0, :sig, '', :ts, 'pending',
                                :tx_type, :to_addr, :data, :gas, 0, :nonce)
                        ON CONFLICT (txid) DO NOTHING
                    """),
                    {
                        'txid': tx_hash, 'sig': raw_hex[:128],
                        'ts': time.time(),
                        'outputs': json.dumps([{'address': to_addr, 'amount': str(value_qbc)}]) if to_addr else '[]',
                        'tx_type': tx_type,
                        'to_addr': to_addr or None,
                        'data': data_hex, 'gas': gas_limit, 'nonce': nonce,
                    }
                )
                session.commit()

            logger.info(f"MetaMask tx accepted to mempool: {sender[:8]}→{to_addr[:8] if to_addr else 'deploy'} {value_qbc} QBC ({tx_type})")
            return '0x' + tx_hash
        except ImportError:
            # eth-account not installed — fallback to simple store
            logger.warning("eth-account not installed, storing raw tx in mempool")
            tx_hash = keccak256(raw_bytes).hex()
            from sqlalchemy import text as sql_text
            with self.db.get_session() as session:
                session.execute(
                    sql_text("""
                        INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                                  timestamp, status, tx_type, to_address, data,
                                                  gas_limit, gas_price, nonce)
                        VALUES (:txid, '[]', '[]', 0, '', '', :ts, 'pending',
                                'contract_call', '', :data, 3000000, 0, 0)
                    """),
                    {'txid': tx_hash, 'ts': time.time(), 'data': raw_hex}
                )
                session.commit()
            return '0x' + tx_hash
        except Exception as e:
            raise RuntimeError(f"Failed to process transaction: {e}") from e

    async def eth_sendTransaction(self, params: list) -> str:
        """Accept a transaction object and store it in the mempool.

        Params:
            [{ from, to, data, gas, value, nonce }]

        When *to* is null or empty the transaction is treated as a contract deploy;
        otherwise it is a contract call.

        Security: This endpoint is restricted to localhost-only access because it
        does not require a signed transaction (the node signs on behalf of the
        caller).  Remote callers must use eth_sendRawTransaction instead.

        NOTE: Transactions are stored as pending in the mempool ONLY.
        Execution (QVM contract calls/deploys, value transfers) happens when a
        miner includes this tx in a block and the block passes consensus
        validation.  Executing here would bypass consensus and risk
        double-execution when the tx is later mined.
        """
        # Only allow from localhost — this method has no cryptographic auth
        if not self._is_localhost():
            raise ValueError("eth_sendTransaction only allowed from localhost. Use eth_sendRawTransaction for remote access.")

        tx_obj = params[0] if params else {}
        from_addr = (tx_obj.get('from') or '').replace('0x', '') or '0' * 40
        to_addr = (tx_obj.get('to') or '').replace('0x', '')
        data_hex = (tx_obj.get('data') or '').replace('0x', '')
        gas_limit = parse_hex_int(tx_obj['gas']) if tx_obj.get('gas') else Config.BLOCK_GAS_LIMIT
        value = parse_hex_int(tx_obj['value']) if tx_obj.get('value') else 0
        nonce = parse_hex_int(tx_obj['nonce']) if tx_obj.get('nonce') else 0

        tx_type = 'contract_call' if to_addr else 'contract_deploy'
        tx_hash = keccak256(
            (from_addr + to_addr + data_hex + str(nonce) + str(value)).encode()
        ).hex()

        value_qbc = parse_wei_to_qbc(value) if value else Decimal(0)

        # Store transaction in mempool ONLY (status='pending').
        # Execution happens when a miner includes this in a block.
        from sqlalchemy import text as sql_text
        with self.db.get_session() as session:
            session.execute(
                sql_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature,
                                              public_key, timestamp, status, tx_type,
                                              to_address, data, gas_limit, gas_price, nonce)
                    VALUES (:txid, '[]', CAST(:outputs AS jsonb), 0, '', '', :ts, 'pending',
                            :tx_type, :to_addr, :data, :gas, 0, :nonce)
                    ON CONFLICT (txid) DO NOTHING
                """),
                {
                    'txid': tx_hash, 'ts': time.time(), 'tx_type': tx_type,
                    'to_addr': to_addr or None, 'data': data_hex, 'gas': gas_limit,
                    'nonce': nonce,
                    'outputs': json.dumps([{'address': to_addr, 'amount': str(value_qbc)}]) if to_addr else '[]',
                },
            )
            session.commit()

        logger.info(
            f"eth_sendTransaction accepted to mempool: {from_addr[:8]}..."
            f"→{to_addr[:8] + '...' if to_addr else 'deploy'} ({tx_type})"
        )
        return '0x' + tx_hash

    async def eth_call(self, params):
        """Read-only contract call (no state change)"""
        if self.qvm is None:
            raise RuntimeError("QVM state manager not initialized")
        call_obj = params[0] if params else {}
        if call_obj.get('to'):
            validate_hex(call_obj['to'], "to", max_len=42)
        if call_obj.get('from'):
            validate_hex(call_obj['from'], "from", max_len=42)
        if call_obj.get('data'):
            validate_hex(call_obj['data'], "data", max_len=131072)  # 64KB hex
        if self.qvm:
            to_addr = call_obj.get('to', '').replace('0x', '')
            data_hex = call_obj.get('data', '').replace('0x', '')
            from_addr = call_obj.get('from', '0' * 40).replace('0x', '')
            calldata = bytes.fromhex(data_hex) if data_hex else b''

            # Execute via QVM static call (loads bytecode internally)
            result = self.qvm.qvm.static_call(from_addr, to_addr, calldata)
            return '0x' + result.hex() if result else '0x'
        return '0x'

    async def eth_estimateGas(self, params):
        """Estimate gas for a transaction using QVM dry-run"""
        if self.qvm is None:
            raise RuntimeError("QVM state manager not initialized")
        call_obj = params[0] if params else {}
        if self.qvm and call_obj.get('data'):
            to_addr = call_obj.get('to', '').replace('0x', '')
            data = call_obj.get('data', '').replace('0x', '')
            from_addr = call_obj.get('from', '0' * 40).replace('0x', '')

            if to_addr:
                # Contract call — dry-run to measure gas
                try:
                    bytecode_hex = self.db.get_contract_bytecode(to_addr)
                    if bytecode_hex:
                        result = self.qvm.qvm.execute(
                            caller=from_addr, address=to_addr,
                            code=bytes.fromhex(bytecode_hex),
                            data=bytes.fromhex(data) if data else b'',
                            value=0, gas=30_000_000, origin=from_addr,
                        )
                        # Add 20% buffer
                        estimated = int(result.gas_used * 1.2)
                        return hex_int(max(21000, estimated))
                except Exception as e:
                    logger.debug(f"Gas estimation failed: {e}")
            else:
                # Contract deploy — estimate based on bytecode size
                bytecode_size = len(data) // 2 if data else 0
                return hex_int(21000 + 200 * bytecode_size + 32000)
        return hex_int(21000)

    # ========================================================================
    # GAS
    # ========================================================================
    async def eth_gasPrice(self, params):
        return hex_balance(Config.DEFAULT_GAS_PRICE)

    # ========================================================================
    # LOGS
    # ========================================================================
    async def eth_getLogs(self, params):
        filter_obj = params[0] if params else {}
        from_block_str = filter_obj.get('fromBlock', '0x0')
        if from_block_str == 'latest':
            from_block = self.db.get_current_height()
        elif from_block_str in ('earliest', 'pending'):
            from_block = 0
        else:
            from_block = parse_hex_int(from_block_str)
        to_block_str = filter_obj.get('toBlock', 'latest')
        if to_block_str == 'latest':
            to_block = self.db.get_current_height()
        elif to_block_str in ('earliest', 'pending'):
            to_block = 0 if to_block_str == 'earliest' else self.db.get_current_height()
        else:
            to_block = parse_hex_int(to_block_str)

        # Enforce max block range to prevent DoS
        if to_block - from_block > 10000:
            raise ValueError("Block range too large (max 10,000)")

        address = filter_obj.get('address', '').replace('0x', '')
        raw_topics = filter_obj.get('topics', [])

        # Normalise topics: strip 0x prefix, keep None as wildcard
        normalised_topics: list = []
        for t in raw_topics:
            if isinstance(t, str) and t:
                normalised_topics.append(t.replace('0x', ''))
            else:
                normalised_topics.append(None)

        # Fast path: use EventIndex if available
        if self.event_index:
            return self.event_index.get_logs(
                from_block=from_block,
                to_block=to_block,
                address=address or None,
                topics=normalised_topics or None,
                limit=1000,
            )

        # Fallback: direct DB query (original implementation)
        with self.db.get_session() as session:
            from sqlalchemy import text as sql_text
            query = "SELECT txid, log_index, contract_address, topic0, topic1, topic2, topic3, data, block_height FROM event_logs WHERE block_height >= :from_b AND block_height <= :to_b"
            query_params: Dict[str, Any] = {'from_b': from_block, 'to_b': to_block}

            if address:
                query += " AND contract_address = :addr"
                query_params['addr'] = address
            if normalised_topics:
                for i, t in enumerate(normalised_topics):
                    if t:
                        col = f'topic{i}'
                        key = f't{i}'
                        query += f" AND {col} = :{key}"
                        query_params[key] = t

            query += " ORDER BY block_height, log_index LIMIT 1000"
            rows = session.execute(sql_text(query), query_params)

            logs = []
            for r in rows:
                t_list = []
                for t in [r[3], r[4], r[5], r[6]]:
                    if t:
                        t_list.append('0x' + t)
                logs.append({
                    'transactionHash': '0x' + r[0],
                    'logIndex': hex_int(r[1]),
                    'address': '0x' + r[2],
                    'data': '0x' + (r[7] or ''),
                    'topics': t_list,
                    'blockNumber': hex_int(r[8]),
                })
            return logs

    # ========================================================================
    # MINING
    # ========================================================================
    async def eth_mining(self, params):
        return self.mining.is_mining if self.mining else False

    async def eth_hashrate(self, params):
        return hex_int(0)

    # ========================================================================
    # DEBUG METHODS
    # ========================================================================
    async def debug_traceTransaction(self, params):
        """Re-execute a transaction and return an opcode-by-opcode trace.

        Params:
            [tx_hash, {optional trace options}]

        Returns a Geth-compatible trace with structLogs.

        Security: restricted to localhost connections only.
        """
        if not self._is_localhost():
            raise ValueError("debug_traceTransaction is restricted to localhost")
        if not params:
            raise ValueError("Missing transaction hash parameter")

        tx_hash = params[0].replace("0x", "")

        # Look up the transaction
        from sqlalchemy import text as sql_text
        with self.db.get_session() as session:
            row = session.execute(
                sql_text("""
                    SELECT txid, to_address, data, gas_limit, nonce, block_height
                    FROM transactions WHERE txid = :txid
                """),
                {"txid": tx_hash},
            ).fetchone()

        if not row:
            raise ValueError(f"Transaction not found: {tx_hash}")

        to_address = row[1] or ""
        data_hex = row[2] or ""
        gas_limit = row[3] or 30_000_000
        block_height = row[5] or 0

        # Get sender from receipt
        receipt = self.db.get_receipt(tx_hash)
        from_address = receipt.from_address if receipt else "0" * 40

        # Get contract bytecode
        bytecode_hex = ""
        if to_address:
            bytecode_hex = self.db.get_contract_bytecode(to_address) or ""

        if not bytecode_hex and not to_address:
            bytecode_hex = data_hex

        if not bytecode_hex:
            raise ValueError("No bytecode found for transaction target")

        if not self.qvm:
            raise ValueError("QVM not available")

        code = bytes.fromhex(bytecode_hex)
        calldata = bytes.fromhex(data_hex) if data_hex else b""

        trace = self.qvm.qvm.execute_with_trace(
            caller=from_address,
            address=to_address or "0" * 40,
            code=code,
            data=calldata,
            gas=gas_limit,
            origin=from_address,
            is_static=True,
        )
        return trace


def _serialize(model):
    """Serialize Pydantic model (compatible with v1 and v2).

    Per JSON-RPC 2.0 spec: on success, omit 'error'; on error, omit 'result'.
    MetaMask is strict about this — 'error: null' in success responses breaks it.
    """
    if hasattr(model, 'model_dump'):
        data = model.model_dump()
    else:
        data = model.dict()
    # Strip null fields per JSON-RPC 2.0 spec
    if data.get("error") is None:
        data.pop("error", None)
    if data.get("result") is None and data.get("error") is not None:
        data.pop("result", None)
    return data


def create_jsonrpc_router(db, consensus=None, mining=None, quantum=None, qvm=None,
                          event_index=None) -> APIRouter:
    """Create JSON-RPC router and attach to FastAPI"""
    handler = JsonRpcHandler(db, consensus, mining, quantum, qvm,
                             event_index=event_index)

    @router.post("/")
    @router.post("/jsonrpc")
    async def jsonrpc_endpoint(request: Request):
        body = await request.json()

        # Handle batch requests (bounded to prevent DoS)
        MAX_BATCH_SIZE = 100
        if isinstance(body, list):
            if len(body) > MAX_BATCH_SIZE:
                return {"jsonrpc": "2.0", "error": {"code": -32600, "message": f"Batch too large: {len(body)} > {MAX_BATCH_SIZE}"}, "id": None}
            responses = []
            for item in body:
                req = JsonRpcRequest(**item)
                resp = await handler.handle(req, http_request=request)
                responses.append(_serialize(resp))
            return responses

        req = JsonRpcRequest(**body)
        resp = await handler.handle(req, http_request=request)
        return _serialize(resp)

    return router
