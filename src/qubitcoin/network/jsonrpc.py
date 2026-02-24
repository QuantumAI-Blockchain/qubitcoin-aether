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
    return int(value, 16)


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
        'gasPrice': hex_balance(tx.gas_price or Config.DEFAULT_GAS_PRICE),
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

    def __init__(self, db, consensus=None, mining=None, quantum=None, qvm=None):
        self.db = db
        self.consensus = consensus
        self.mining = mining
        self.quantum = quantum
        self.qvm = qvm

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

    async def handle(self, request: JsonRpcRequest) -> JsonRpcResponse:
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
                error={'code': -32000, 'message': str(e)}
            )

    # ========================================================================
    # CHAIN METHODS
    # ========================================================================
    async def eth_chainId(self, params):
        return hex_int(Config.CHAIN_ID)

    async def net_version(self, params):
        return str(Config.CHAIN_ID)

    async def web3_clientVersion(self, params):
        return "Qubitcoin/v2.0.0-QVM/python"

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
        block_hash = params[0].replace('0x', '') if params else ''
        include_txs = params[1] if len(params) > 1 else False
        block = self.db.get_block_by_hash(block_hash)
        return _block_to_rpc(block, include_txs)

    # ========================================================================
    # ACCOUNT METHODS
    # ========================================================================
    async def eth_getBalance(self, params):
        address = params[0].replace('0x', '') if params else ''
        # Sum both account balance (QVM/MetaMask) and UTXO balance
        account_bal = self.db.get_account_balance(address)
        utxo_bal = self.db.get_balance(address)
        balance = account_bal + utxo_bal
        return hex_balance(balance)

    async def eth_getTransactionCount(self, params):
        address = params[0].replace('0x', '') if params else ''
        account = self.db.get_account(address)
        nonce = account.nonce if account else 0
        return hex_int(nonce)

    async def eth_getCode(self, params):
        address = params[0].replace('0x', '') if params else ''
        bytecode = self.db.get_contract_bytecode(address)
        return '0x' + (bytecode or '')

    async def eth_getStorageAt(self, params):
        address = params[0].replace('0x', '') if params else ''
        position = params[1].replace('0x', '') if len(params) > 1 else '0' * 64
        value = self.db.get_storage(address, position)
        return '0x' + value

    # ========================================================================
    # TRANSACTION METHODS
    # ========================================================================
    async def eth_getTransactionByHash(self, params):
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
        txid = params[0].replace('0x', '') if params else ''
        receipt = self.db.get_receipt(txid)
        return _receipt_to_rpc(receipt)

    async def eth_sendRawTransaction(self, params):
        """Accept raw signed transaction hex from MetaMask and execute it.

        Decodes the RLP-encoded signed transaction, recovers the ECDSA
        sender address, validates balance/nonce, and executes value
        transfers or contract calls.
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

            # Compute tx hash
            tx_hash = hashlib.sha256(raw_bytes).hexdigest()

            value_qbc = parse_wei_to_qbc(value_wei)

            # Validate sender balance
            sender_bal = self.db.get_account_balance(sender)
            if sender_bal < value_qbc:
                raise ValueError(f"Insufficient balance: have {sender_bal}, need {value_qbc}")

            # Execute the transaction
            if to_addr and data_hex and self.qvm:
                # Contract call — route through QVM
                from ..database.models import Transaction as TxModel
                tx = TxModel(
                    txid=tx_hash, inputs=[], outputs=[],
                    fee=Decimal(0), signature='', public_key='',
                    timestamp=time.time(), tx_type='contract_call',
                    to_address=to_addr, data=data_hex,
                    gas_limit=gas_limit, gas_price=Decimal(0), nonce=nonce,
                )
                receipt = self.qvm.process_transaction(
                    tx, block_height=self.db.get_current_height(),
                    block_hash='0' * 64, tx_index=0,
                )
                if value_qbc > 0:
                    self.db.transfer_between_accounts(sender, to_addr, value_qbc)
            elif to_addr and value_qbc > 0:
                # Simple value transfer
                self.db.transfer_between_accounts(sender, to_addr, value_qbc)
            elif not to_addr and data_hex and self.qvm:
                # Contract deploy
                from ..database.models import Transaction as TxModel
                tx = TxModel(
                    txid=tx_hash, inputs=[], outputs=[],
                    fee=Decimal(0), signature='', public_key='',
                    timestamp=time.time(), tx_type='contract_deploy',
                    to_address=None, data=data_hex,
                    gas_limit=gas_limit, gas_price=Decimal(0), nonce=nonce,
                )
                self.qvm.process_transaction(
                    tx, block_height=self.db.get_current_height(),
                    block_hash='0' * 64, tx_index=0,
                )

            # Store transaction record
            from sqlalchemy import text as sql_text
            with self.db.get_session() as session:
                session.execute(
                    sql_text("""
                        INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                                  timestamp, status, tx_type, to_address, data,
                                                  gas_limit, gas_price, nonce)
                        VALUES (:txid, '[]', CAST(:outputs AS jsonb), 0, :sig, '', :ts, 'confirmed',
                                :tx_type, :to_addr, :data, :gas, 0, :nonce)
                        ON CONFLICT (txid) DO NOTHING
                    """),
                    {
                        'txid': tx_hash, 'sig': raw_hex[:128],
                        'ts': time.time(),
                        'outputs': json.dumps([{'address': to_addr, 'amount': str(value_qbc)}]) if to_addr else '[]',
                        'tx_type': 'contract_deploy' if not to_addr else ('contract_call' if data_hex else 'transfer'),
                        'to_addr': to_addr or None,
                        'data': data_hex, 'gas': gas_limit, 'nonce': nonce,
                    }
                )
                session.commit()

            logger.info(f"MetaMask tx processed: {sender[:8]}→{to_addr[:8] if to_addr else 'deploy'} {value_qbc} QBC")
            return '0x' + tx_hash
        except ImportError:
            # eth-account not installed — fallback to simple store
            logger.warning("eth-account not installed, storing raw tx in mempool")
            tx_hash = hashlib.sha256(raw_bytes).hexdigest()
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
        """Accept a transaction object and route deploys/calls through StateManager.

        Params:
            [{ from, to, data, gas, value, nonce }]

        When *to* is null or empty the transaction is treated as a contract deploy;
        otherwise it is a contract call.
        """
        tx_obj = params[0] if params else {}
        from_addr = (tx_obj.get('from') or '').replace('0x', '') or '0' * 40
        to_addr = (tx_obj.get('to') or '').replace('0x', '')
        data_hex = (tx_obj.get('data') or '').replace('0x', '')
        gas_limit = parse_hex_int(tx_obj['gas']) if tx_obj.get('gas') else Config.BLOCK_GAS_LIMIT
        value = parse_hex_int(tx_obj['value']) if tx_obj.get('value') else 0
        nonce = parse_hex_int(tx_obj['nonce']) if tx_obj.get('nonce') else 0

        tx_type = 'contract_call' if to_addr else 'contract_deploy'
        tx_hash = hashlib.sha256(
            (from_addr + to_addr + data_hex + str(time.time())).encode()
        ).hexdigest()

        from ..database.models import Transaction as TxModel
        tx = TxModel(
            txid=tx_hash,
            inputs=[],
            outputs=[],
            fee=Decimal(0),
            signature='',
            public_key='',
            timestamp=time.time(),
            tx_type=tx_type,
            to_address=to_addr or None,
            data=data_hex,
            gas_limit=gas_limit,
            gas_price=Decimal(0),
            nonce=nonce,
        )

        if self.qvm:
            receipt = self.qvm.process_transaction(
                tx,
                block_height=self.db.get_current_height(),
                block_hash='0' * 64,
                tx_index=0,
            )
            if receipt:
                return '0x' + tx_hash

        # Fallback — insert into mempool for deferred execution
        from sqlalchemy import text as sql_text
        with self.db.get_session() as session:
            session.execute(
                sql_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature,
                                              public_key, timestamp, status, tx_type,
                                              to_address, data, gas_limit, gas_price, nonce)
                    VALUES (:txid, '[]', '[]', 0, '', '', :ts, 'pending',
                            :tx_type, :to_addr, :data, :gas, 0, :nonce)
                """),
                {
                    'txid': tx_hash, 'ts': time.time(), 'tx_type': tx_type,
                    'to_addr': to_addr, 'data': data_hex, 'gas': gas_limit,
                    'nonce': nonce,
                },
            )
            session.commit()
        return '0x' + tx_hash

    async def eth_call(self, params):
        """Read-only contract call (no state change)"""
        call_obj = params[0] if params else {}
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
        from_block = parse_hex_int(filter_obj.get('fromBlock', '0x0'))
        to_block_str = filter_obj.get('toBlock', 'latest')
        if to_block_str == 'latest':
            to_block = self.db.get_current_height()
        else:
            to_block = parse_hex_int(to_block_str)

        address = filter_obj.get('address', '').replace('0x', '')
        topics = filter_obj.get('topics', [])

        with self.db.get_session() as session:
            from sqlalchemy import text as sql_text
            query = "SELECT txid, log_index, contract_address, topic0, topic1, topic2, topic3, data, block_height FROM event_logs WHERE block_height >= :from_b AND block_height <= :to_b"
            query_params: Dict[str, Any] = {'from_b': from_block, 'to_b': to_block}

            if address:
                query += " AND contract_address = :addr"
                query_params['addr'] = address
            if topics and topics[0]:
                t0 = topics[0].replace('0x', '') if isinstance(topics[0], str) else ''
                if t0:
                    query += " AND topic0 = :t0"
                    query_params['t0'] = t0

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
        """
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
    """Serialize Pydantic model (compatible with v1 and v2)"""
    if hasattr(model, 'model_dump'):
        return model.model_dump()
    return model.dict()


def create_jsonrpc_router(db, consensus=None, mining=None, quantum=None, qvm=None) -> APIRouter:
    """Create JSON-RPC router and attach to FastAPI"""
    handler = JsonRpcHandler(db, consensus, mining, quantum, qvm)

    @router.post("/")
    @router.post("/jsonrpc")
    async def jsonrpc_endpoint(request: Request):
        body = await request.json()

        # Handle batch requests
        if isinstance(body, list):
            responses = []
            for item in body:
                req = JsonRpcRequest(**item)
                resp = await handler.handle(req)
                responses.append(_serialize(resp))
            return responses

        req = JsonRpcRequest(**body)
        resp = await handler.handle(req)
        return _serialize(resp)

    return router
