"""
Locust stress test for op-geth-simulator with write + update-like operations.

Important note about "updates":
The simulator only exposes POST /entities (no PUT/PATCH). To simulate updates we
re-POST the *same entity key* with modified annotations (e.g. status changes).

This test has 4 task types with relative frequency (lowest -> highest):
  - add_node (least often)
  - update_node
  - add_workload (assigned to an existing node)
  - update_workload (most often; status + assignment)

Each Locust user keeps an in-memory pool (ring buffer) of entities:
  - up to 1000 nodes
  - up to 5000 workloads

Usage:
    locust -f locust/dc_write_and_update.py --host=http://localhost:3000
"""

import os
import random
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import web3
from arkiv import Arkiv
from arkiv.account import NamedAccount
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

# Add parent directory to path for backwards-compat imports
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
# Configuration (env-overridable)
# =============================================================================

DEFAULT_CREATOR_ADDRESS = os.getenv(
    "DC_CREATOR_ADDRESS", "0x0000000000000000000000000000000000dc0001"
)
DEFAULT_BLOCK = int(os.getenv("DC_START_BLOCK", "1"))
DEFAULT_DC_NUM = int(os.getenv("DC_NUM", "1"))

NODE_POOL_SIZE = int(os.getenv("DC_NODE_POOL_SIZE", "1000"))
WORKLOAD_POOL_SIZE = int(os.getenv("DC_WORKLOAD_POOL_SIZE", "5000"))

# Payload size is randomized per user, but bounded by these env vars
PAYLOAD_SIZE_MIN = int(os.getenv("DC_PAYLOAD_SIZE_MIN", "5000"))
PAYLOAD_SIZE_MAX = int(os.getenv("DC_PAYLOAD_SIZE_MAX", "15000"))

# Task weights (relative frequencies)
W_ADD_NODE = int(os.getenv("DC_W_ADD_NODE", "1"))
W_UPDATE_NODE = int(os.getenv("DC_W_UPDATE_NODE", "3"))
W_ADD_WORKLOAD = int(os.getenv("DC_W_ADD_WORKLOAD", "10"))
W_UPDATE_WORKLOAD = int(os.getenv("DC_W_UPDATE_WORKLOAD", "20"))

DEFAULT_BLOCK_DURATION_SECONDS = 2


# =============================================================================
# Entity Transformation (Arkiv attributes)
# =============================================================================

def node_to_arkiv_attributes(node: NodeEntity, creator_address: str) -> Dict[str, Any]:
    """
    Build Arkiv attributes for a NodeEntity.

    Note: we keep the same attribute names as the previous HTTP endpoint payloads.
    """
    # Keep attributes consistent with other dc_* tests (no $system fields here)
    string_annotations = {
        "dc_id": node.dc_id,
        "type": NODE,
        "node_id": node.node_id,
        "region": node.region,
        "status": node.status,
        "vm_type": node.vm_type,
    }

    numeric_annotations = {
        "cpu_count": node.cpu_count,
        "ram_gb": node.ram_gb,
        "price_hour": node.price_hour,
        "avail_hours": node.avail_hours,
    }

    return {**string_annotations, **numeric_annotations}


def workload_to_arkiv_attributes(
    workload: WorkloadEntity, creator_address: str
) -> Dict[str, Any]:
    """
    Build Arkiv attributes for a WorkloadEntity.

    Note: we keep the same attribute names as the previous HTTP endpoint payloads.
    """
    # Keep attributes consistent with other dc_* tests (no $system fields here)
    string_annotations = {
        "dc_id": workload.dc_id,
        "type": WORKLOAD,
        "workload_id": workload.workload_id,
        "status": workload.status,
        "assigned_node": workload.assigned_node,
        "region": workload.region,
        "vm_type": workload.vm_type,
    }

    numeric_annotations = {
        "req_cpu": workload.req_cpu,
        "req_ram": workload.req_ram,
        "max_hours": workload.max_hours,
    }

    return {**string_annotations, **numeric_annotations}


# =============================================================================
# Locust User
# =============================================================================

class DataCenterWriteAndUpdateUser(JsonRpcUser):
    """
    Locust user that does create + update-like operations via POST /entities.

    Pools are per-user to keep behavior deterministic and avoid coordination between users.
    """

    wait_time = constant(1)

    # Per-user state
    seed: int
    dc_num: int
    creator_address: str
    current_block: int
    payload_size: int

    node_counter: int
    workload_counter: int

    nodes: List[NodeEntity]
    workloads: List[WorkloadEntity]
    node_ring_idx: int
    workload_ring_idx: int

    rng: random.Random

    account: Optional[LocalAccount]
    w3: Optional[Arkiv]
    block_duration_seconds: int

    def on_start(self) -> None:
        super().on_start()
        # Keep consistent with other dc_* tests: stable per-user seed from BaseUser id
        self.seed = int(self.id)
        self.rng = random.Random(self.seed)

        self.dc_num = DEFAULT_DC_NUM
        self.creator_address = DEFAULT_CREATOR_ADDRESS
        self.current_block = DEFAULT_BLOCK

        # Keep payloads different across users but stable within a user
        self.payload_size = self.rng.randint(PAYLOAD_SIZE_MIN, PAYLOAD_SIZE_MAX)

        self.node_counter = 0
        self.workload_counter = 0

        self.nodes = []
        self.workloads = []
        self.node_ring_idx = 0
        self.workload_ring_idx = 0

        self.account = None
        self.w3 = None
        self.block_duration_seconds = DEFAULT_BLOCK_DURATION_SECONDS
        self._initialize_account_and_w3()

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
                self.block_duration_seconds = int(
                    getattr(block_timing, "duration", DEFAULT_BLOCK_DURATION_SECONDS)
                )
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

    # -------------------------------------------------------------------------
    # Pool helpers
    # -------------------------------------------------------------------------

    def _pool_put_node(self, node: NodeEntity) -> None:
        if len(self.nodes) < NODE_POOL_SIZE:
            self.nodes.append(node)
            return
        self.nodes[self.node_ring_idx] = node
        self.node_ring_idx = (self.node_ring_idx + 1) % NODE_POOL_SIZE

    def _pool_put_workload(self, workload: WorkloadEntity) -> None:
        if len(self.workloads) < WORKLOAD_POOL_SIZE:
            self.workloads.append(workload)
            return
        self.workloads[self.workload_ring_idx] = workload
        self.workload_ring_idx = (self.workload_ring_idx + 1) % WORKLOAD_POOL_SIZE

    def _pick_node(self) -> Optional[NodeEntity]:
        if not self.nodes:
            return None
        return self.rng.choice(self.nodes)

    def _pick_workload(self) -> Optional[WorkloadEntity]:
        if not self.workloads:
            return None
        return self.rng.choice(self.workloads)

    # -------------------------------------------------------------------------
    # Domain helpers (status/assignment changes)
    # -------------------------------------------------------------------------

    def _sample_node_status_for_update(self, prev: str) -> str:
        # Bias towards "available" / "busy" changes; keep "offline" rare.
        r = self.rng.random()
        if r < 0.05:
            return "offline"
        if r < 0.55:
            return "available"
        return "busy"

    def _sample_workload_status_for_update(self, prev: str) -> str:
        # Keep workloads churny: mostly running <-> pending, with occasional completed.
        r = self.rng.random()
        if r < 0.05:
            return "completed"
        if r < 0.55:
            return "running"
        return "pending"

    def _workload_assignment_for_status(self, status: str) -> str:
        if status == "running":
            node = self._pick_node()
            return node.node_id if node else ""
        # pending/completed => unassigned
        return ""

    # -------------------------------------------------------------------------
    # Core operations (Arkiv SDK)
    # -------------------------------------------------------------------------

    def _create_entity(self, payload: bytes, attributes: Dict[str, Any], name: str) -> None:
        ttl_blocks = self.rng.randint(100, 1000)
        expires_in = self._expires_in_seconds_from_blocks(ttl_blocks)
        w3 = self._initialize_account_and_w3()
        self._fire_locust_request(
            name,
            lambda: w3.arkiv.create_entity(
                payload=payload,
                content_type="application/octet-stream",
                attributes=attributes,
                expires_in=expires_in,
            ),
        )

    def _update_entity(
        self, entity_key: str, payload: bytes, attributes: Dict[str, Any], name: str
    ) -> None:
        ttl_blocks = self.rng.randint(100, 1000)
        expires_in = self._expires_in_seconds_from_blocks(ttl_blocks)
        w3 = self._initialize_account_and_w3()
        self._fire_locust_request(
            name,
            lambda: w3.arkiv.update_entity(
                entity_key,
                payload=payload,
                attributes=attributes,
                expires_in=expires_in,
            ),
        )

    # -------------------------------------------------------------------------
    # Tasks (frequency: add_node < update_node < add_workload < update_workload)
    # -------------------------------------------------------------------------

    @task(W_ADD_NODE)
    def add_node(self) -> None:
        self.node_counter += 1
        self.current_block += 1

        # Prefer available nodes; updates will flip to busy/offline.
        node = create_node(
            dc_num=self.dc_num,
            node_num=self.node_counter,
            payload_size=self.payload_size,
            block=self.current_block,
            seed=self.seed,
            status="available",
        )

        self._create_entity(
            payload=node.payload,
            attributes=node_to_arkiv_attributes(node, self.creator_address),
            name="add_node",
        )
        self._pool_put_node(node)

    @task(W_UPDATE_NODE)
    def update_node(self) -> None:
        node = self._pick_node()
        if node is None:
            # bootstrap
            self.add_node()
            return

        self.current_block += 1
        new_status = self._sample_node_status_for_update(node.status)
        updated = replace(node, status=new_status, block=self.current_block)

        key_hex = "0x" + updated.entity_key.hex()
        self._update_entity(
            key_hex,
            payload=updated.payload,
            attributes=node_to_arkiv_attributes(updated, self.creator_address),
            name="update_node",
        )

        # Persist the latest version in the pool (by replacement in-place)
        try:
            idx = self.nodes.index(node)
            self.nodes[idx] = updated
        except ValueError:
            self._pool_put_node(updated)

    @task(W_ADD_WORKLOAD)
    def add_workload(self) -> None:
        if not self.nodes:
            self.add_node()

        self.workload_counter += 1
        self.current_block += 1

        # Per requirement: new workloads are assigned to some node.
        assigned_node_id = self._pick_node().node_id if self.nodes else ""

        workload = create_workload(
            dc_num=self.dc_num,
            workload_num=self.workload_counter,
            nodes_per_dc=max(1, self.node_counter),
            payload_size=self.payload_size,
            block=self.current_block,
            seed=self.seed,
            status="running",
            assigned_node=assigned_node_id,
        )

        self._create_entity(
            payload=workload.payload,
            attributes=workload_to_arkiv_attributes(workload, self.creator_address),
            name="add_workload",
        )
        self._pool_put_workload(workload)

    @task(W_UPDATE_WORKLOAD)
    def update_workload(self) -> None:
        workload = self._pick_workload()
        if workload is None:
            # bootstrap: ensure we have at least one workload
            self.add_workload()
            return

        if not self.nodes:
            self.add_node()

        self.current_block += 1
        new_status = self._sample_workload_status_for_update(workload.status)
        new_assigned = self._workload_assignment_for_status(new_status)

        updated = replace(
            workload,
            status=new_status,
            assigned_node=new_assigned,
            block=self.current_block,
        )

        key_hex = "0x" + updated.entity_key.hex()
        self._update_entity(
            key_hex,
            payload=updated.payload,
            attributes=workload_to_arkiv_attributes(updated, self.creator_address),
            name="update_workload",
        )

        # Persist the latest version in the pool (by replacement in-place)
        try:
            idx = self.workloads.index(workload)
            self.workloads[idx] = updated
        except ValueError:
            self._pool_put_workload(updated)


