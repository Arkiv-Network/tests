"""
Locust stress test for op-geth-simulator write entities endpoint.

This test generates nodes and workloads using the same logic as append_dc_data.py
and sends them to the op-geth-simulator's POST /entities endpoint.

Usage:
    locust -f locust/write_only.py --host=http://localhost:3000
"""

import os
import random
import sys
import time
from pathlib import Path
import logging
from typing import Any, Dict, Optional

import web3
from web3.types import TxParams
from arkiv import Arkiv
from arkiv.account import NamedAccount
from arkiv.types import Operations, TxHash, HexStr
from arkiv.utils import to_create_op, to_tx_params
from eth_account import Account
from eth_account.signers.local import LocalAccount
from locust import constant, events, task
from web3 import Web3

# Add the project root (stress-tests/) to Python path so we can import stress.*
file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # l3/ -> stress/ -> stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import stress.tools.config as config
from stress.tools.json_rpc_user import JsonRpcUser
from stress.tools.utils import build_account_path

# Add parent directory to path to import from src.db.append_dc_data (kept for backwards compat)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stress.tools.dc_data import (
    NODE,
    WORKLOAD,
    NodeEntity,
    WorkloadEntity,
    create_node,
    create_workload,
)

Account.enable_unaudited_hdwallet_features()


# =============================================================================
# Configuration
# =============================================================================

DEFAULT_CREATOR_ADDRESS = "0x0000000000000000000000000000000000dc0001"
DEFAULT_PAYLOAD_SIZE = 10000
REAL_DC_PAYLOAD_CONTENT = True
DEFAULT_DC_NUM = 1
DEFAULT_WORKLOADS_PER_NODE = 5
DEFAULT_BLOCK = 1  # Starting block number (will be incremented per user)
DEFAULT_BLOCK_DURATION_SECONDS = 2


# =============================================================================
# Entity Transformation (Arkiv attributes)
# =============================================================================

def node_to_arkiv_attributes(node: NodeEntity, creator_address: str) -> Dict[str, Any]:
    """
    Build Arkiv attributes for a NodeEntity.

    Note: we keep the same attribute names as the previous HTTP endpoint payloads.
    """
    entity_key = node.entity_key
    block = node.block

    # String attributes
    string_attrs: Dict[str, Any] = {
        "dc_id": node.dc_id,
        "type": NODE,
        "node_id": node.node_id,
        "region": node.region,
        "status": node.status,
        "vm_type": node.vm_type,
    }

    # Numeric attributes
    numeric_attrs: Dict[str, Any] = {
        "cpu_count": node.cpu_count,
        "ram_gb": node.ram_gb,
        "price_hour": node.price_hour,
        "avail_hours": node.avail_hours,
    }

    return {**string_attrs, **numeric_attrs}


def workload_to_arkiv_attributes(
    workload: WorkloadEntity, creator_address: str
) -> Dict[str, Any]:
    """
    Build Arkiv attributes for a WorkloadEntity.

    Note: we keep the same attribute names as the previous HTTP endpoint payloads.
    """
    entity_key = workload.entity_key
    block = workload.block

    # String attributes
    string_attrs: Dict[str, Any] = {
        "dc_id": workload.dc_id,
        "type": WORKLOAD,
        "workload_id": workload.workload_id,
        "status": workload.status,
        "assigned_node": workload.assigned_node,
        "region": workload.region,
        "vm_type": workload.vm_type
    }

    # Numeric attributes
    numeric_attrs: Dict[str, Any] = {
        "req_cpu": workload.req_cpu,
        "req_ram": workload.req_ram,
        "max_hours": workload.max_hours,
    }

    return {**string_attrs, **numeric_attrs}


# =============================================================================
# Locust User Class
# =============================================================================

class DataCenterUser(JsonRpcUser):
    """
    Locust user that generates nodes and workloads and sends them to op-geth-simulator.
    
    Each user maintains its own counters for unique entity IDs.
    """
    wait_time = constant(1)
    
    # Per-user state
    node_counter: int = 0
    workload_counter: int = 0
    current_block: int = DEFAULT_BLOCK
    seed: int = None
    creator_address: str = DEFAULT_CREATOR_ADDRESS
    payload_size: int = DEFAULT_PAYLOAD_SIZE
    dc_num: int = DEFAULT_DC_NUM
    workloads_per_node: int = DEFAULT_WORKLOADS_PER_NODE

    account: Optional[LocalAccount] = None
    w3: Optional[Arkiv] = None
    block_duration_seconds: int = DEFAULT_BLOCK_DURATION_SECONDS
    real_dc_payload_content: bytes | None = None

    if (REAL_DC_PAYLOAD_CONTENT):
        # load real dc payload content from file
        with open(f"stress/l3/sample_sys_x5.payload", "rb") as f:
            real_dc_payload_content = f.read()

    def _initialize_account_and_w3(self) -> Arkiv:
        if self.account is None or self.w3 is None:
            account_path = build_account_path(self.id)
            self.account = Account.from_mnemonic(config.mnemonic, account_path=account_path)

            self.w3 = Arkiv(
                web3.HTTPProvider(endpoint_uri=self.client.base_url, session=self.client),
                NamedAccount(name="LocalSigner", account=self.account),
            )
            if not self.w3.is_connected():
                raise RuntimeError(f"Not connected to Arkiv RPC at {self.client.base_url}")

            if config.chain_env == "local":
                self._topup_local_account()

            try:
                block_timing = self.w3.arkiv.get_block_timing()
                self.block_duration_seconds = int(getattr(block_timing, "duration", DEFAULT_BLOCK_DURATION_SECONDS))
            except Exception:
                self.block_duration_seconds = DEFAULT_BLOCK_DURATION_SECONDS

        return self.w3

    def _topup_local_account(self) -> None:
        """Top up local account with ETH from the first dev account."""
        if self.w3 is None or self.account is None:
            return
        try:
            accounts = self.w3.eth.accounts
            balance = Web3.from_wei(self.w3.eth.get_balance(self.account.address), "ether")
            if balance < 0.1:
                tx_hash = self.w3.eth.send_transaction(
                    {"from": accounts[0], "to": self.account.address, "value": Web3.to_wei(10, "ether")}
                )
                self.w3.eth.wait_for_transaction_receipt(tx_hash)
        except Exception:
            # Best-effort: if top-up fails, transactions may fail later with insufficient funds.
            return

    def _expires_in_seconds_from_blocks(self, ttl_blocks: int) -> int:
        return max(1, int(ttl_blocks) * int(self.block_duration_seconds))

    def _fire_locust_request(self, name: str, fn) -> Any:
        start = time.perf_counter()
        exc: Optional[BaseException] = None
        try:
            return fn()
        except BaseException as e:
            exc = e
            raise
        finally:
            events.request.fire(
                request_type="arkiv",
                name=name,
                response_time=(time.perf_counter() - start) * 1000,
                response_length=0,
                exception=exc,
                context={},
                response=None,
            )
    
    @task
    def write_node_with_workloads(self):
        """
        Generate one node and 5 workloads for that node, then send them to the API.
        
        This is the main task that will be executed repeatedly.
        """
        # Increment counters
        self.node_counter += 1
        self.current_block += 1
        
        # Create the node
        node = create_node(
            dc_num=self.dc_num,
            node_num=self.node_counter,
            payload_size=self.payload_size,
            payload_content=self.real_dc_payload_content,
            block=self.current_block,
            seed=self.seed,
        )

        ttl_blocks = random.randint(100, 1000)
        expires_in_seconds = self._expires_in_seconds_from_blocks(ttl_blocks)

        create_ops = [
            to_create_op(
                payload=node.payload,
                content_type="application/octet-stream",
                attributes=node_to_arkiv_attributes(node, self.creator_address),
                expires_in=expires_in_seconds,
            )
        ]
        
        # Create workloads for this node
        # First workload is assigned if node is busy
        is_busy = node.status == "busy"
        
        for wl_idx in range(self.workloads_per_node):
            self.workload_counter += 1
            
            # First workload is assigned if node is busy
            if is_busy and wl_idx == 0:
                wl_status = "running"
                wl_assigned = node.node_id
            else:
                wl_status = "pending"
                wl_assigned = ""
            
            # Create workload
            workload = create_workload(
                dc_num=self.dc_num,
                workload_num=self.workload_counter,
                nodes_per_dc=self.node_counter,  # Not used when assigned_node provided
                payload_size=self.payload_size,
                payload_content=self.real_dc_payload_content,
                block=self.current_block,
                seed=self.seed,
                status=wl_status,
                assigned_node=wl_assigned,
            )

            create_ops.append(
                to_create_op(
                    payload=workload.payload,
                    content_type="application/octet-stream",
                    attributes=workload_to_arkiv_attributes(workload, self.creator_address),
                    expires_in=expires_in_seconds,
                )
            )

        w3 = self._initialize_account_and_w3()
        operations = Operations(creates=create_ops)
        nonce = w3.eth.get_transaction_count(self.account.address)
        logging.info(f"Sending tx by user {self.id} with nonce: {nonce}, address: {self.account.address}")
        self._fire_locust_request("write_node_with_workloads", lambda: custom_execute(w3, operations, TxParams(nonce=nonce)))
        logging.info(f"Tx sent by user {self.id} with nonce: {nonce}, address: {self.account.address}")


def custom_execute(w3: Arkiv, operations: Operations, tx_params: TxParams) -> Any:
    tx_params = to_tx_params(operations, tx_params)

    # Send transaction and get tx hash
    tx_hash_bytes = w3.eth.send_transaction(tx_params)
    tx_hash = TxHash(HexStr(tx_hash_bytes.to_0x_hex()))

    # Wait for transaction to complete and return receipt
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=0.5)

    return tx_receipt