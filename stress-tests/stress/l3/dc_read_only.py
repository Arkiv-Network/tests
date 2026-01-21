"""
Locust stress test for op-geth-simulator read/query endpoints.

This test performs read queries similar to query_dc_benchmark.py, using the same
query types and weights. Sample data (node_ids, workload_ids, entity_keys) is
pre-loaded globally once when the test starts.

The test uses range queries for numeric annotations (>=, <=, >, <, !=) where
appropriate, leveraging the extended queryEntities API that supports Arkiv query
language with comparison operators.

Usage:
    locust -f locust/read_only.py --host=http://localhost:3000
"""

import os
import random
import sys
import time
from itertools import islice
from pathlib import Path
from typing import Any, List, Optional

import web3
from arkiv import Arkiv
from arkiv.account import NamedAccount
try:
    from arkiv.types import ATTRIBUTES, KEY
    _QUERY_FIELDS = KEY | ATTRIBUTES
except Exception:
    # Older SDKs may not expose ATTRIBUTES. Reads may still work, but sampling ids
    # from attributes will be limited.
    from arkiv.types import KEY

    _QUERY_FIELDS = KEY
from arkiv.utils import to_query_options
from eth_account import Account
from eth_account.signers.local import LocalAccount
from locust import constant, events, task

# Add the project root (stress-tests/) to Python path so we can import stress.*
file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # l3/ -> stress/ -> stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import stress.tools.config as config
from stress.tools.json_rpc_user import JsonRpcUser
from stress.tools.utils import build_account_path

# Add parent directory to path (kept for backwards compat)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

Account.enable_unaudited_hdwallet_features()


# =============================================================================
# Configuration
# =============================================================================

# Logging level: DEBUG, INFO, WARNING, ERROR, or NONE (to disable all debug logs)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()

# Query mix weights (must sum to 1.0)
QUERY_MIX = {
    "point_by_id": 0.20,       # 20% - Point lookup by node_id/workload_id
    "point_by_key": 0.15,      # 15% - Direct entity_key lookup
    "point_miss": 0.10,        # 10% - Non-existent entity lookup
    "node_filter": 0.25,       # 25% - Filter available nodes
    "workload_simple": 0.15,   # 15% - Find pending workloads
    "workload_specific": 0.15, # 15% - Find pending workloads with filters
}

# Sample sizes for pre-loading IDs
SAMPLE_SIZE_IDS = 1000
SAMPLE_SIZE_KEYS = 1000

# Regions and VM types for filter queries
REGIONS = ["eu-west", "us-east", "asia-pac"]
VM_TYPES = ["cpu", "gpu", "gpu_large"]

# Default result set limits
DEFAULT_NODE_LIMIT = 100
DEFAULT_WORKLOAD_LIMIT = 100

DEFAULT_BLOCK_DURATION_SECONDS = 2
MAX_RESULTS_PER_PAGE: int = 1_000_000_000


# =============================================================================
# Logging Helper
# =============================================================================

def debug_log(message: str) -> None:
    """Print debug message if LOG_LEVEL is DEBUG."""
    if LOG_LEVEL == "DEBUG":
        print(message)


# =============================================================================
# Global Sample Data (loaded once at test start)
# =============================================================================

class GlobalSampleData:
    """Global sample data loaded once at test start."""
    
    node_ids: List[str] = []
    workload_ids: List[str] = []
    entity_keys: List[str] = []  # Stored as hex strings for API
    initialized: bool = False
    
    @classmethod
    def load_from_arkiv(cls, w3: Arkiv) -> None:
        """Load sample data by querying Arkiv (no local DB dependency)."""
        if cls.initialized:
            return

        # Query nodes and workloads and extract their ids from attributes.
        # Note: requires ATTRIBUTES field support in SDK to populate ids from entity.attributes.
        try:
            node_iter = w3.arkiv.query_entities(
                query='type="node"',
                options=to_query_options(
                    fields=_QUERY_FIELDS, max_results_per_page=MAX_RESULTS_PER_PAGE
                ),
            )
            for entity in islice(node_iter, SAMPLE_SIZE_IDS):
                key = getattr(entity, "key", None)
                if key:
                    cls.entity_keys.append(str(key))
                attrs = getattr(entity, "attributes", {}) or {}
                node_id = attrs.get("node_id")
                if node_id:
                    cls.node_ids.append(str(node_id))
        except Exception as e:
            print(f"Error loading node samples from Arkiv: {e}")

        try:
            workload_iter = w3.arkiv.query_entities(
                query='type="workload"',
                options=to_query_options(
                    fields=_QUERY_FIELDS, max_results_per_page=MAX_RESULTS_PER_PAGE
                ),
            )
            for entity in islice(workload_iter, SAMPLE_SIZE_IDS):
                key = getattr(entity, "key", None)
                if key:
                    cls.entity_keys.append(str(key))
                attrs = getattr(entity, "attributes", {}) or {}
                workload_id = attrs.get("workload_id")
                if workload_id:
                    cls.workload_ids.append(str(workload_id))
        except Exception as e:
            print(f"Error loading workload samples from Arkiv: {e}")

        # Keep only a small set of keys for point lookups (but ensure at least 1 if available)
        if cls.entity_keys:
            random.shuffle(cls.entity_keys)
            cls.entity_keys = cls.entity_keys[: max(1, min(SAMPLE_SIZE_KEYS, len(cls.entity_keys)))]

        print(
            f"Loaded {len(cls.node_ids)} node IDs, {len(cls.workload_ids)} workload IDs, "
            f"{len(cls.entity_keys)} entity keys from Arkiv"
        )
        cls.initialized = True


# =============================================================================
# Locust User Class
# =============================================================================

class DataCenterReadUser(JsonRpcUser):
    """
    Locust user that performs read queries on op-geth-simulator.
    
    Each user randomly selects query types based on QUERY_MIX weights.
    """
    wait_time = constant(1)

    account: Optional[LocalAccount] = None
    w3: Optional[Arkiv] = None

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
        return self.w3

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

    def _is_not_found(self, e: BaseException) -> bool:
        msg = str(e).lower()
        return ("not found" in msg) or ("404" in msg) or ("missing" in msg) or ("does not exist" in msg)
    
    def _query_count(self, query: str, limit: Optional[int] = None) -> int:
        w3 = self._initialize_account_and_w3()
        it = w3.arkiv.query_entities(
            query=query,
            options=to_query_options(fields=KEY, max_results_per_page=MAX_RESULTS_PER_PAGE),
        )
        if limit is None:
            return sum(1 for _ in it)
        return sum(1 for _ in islice(it, limit))
    
    def on_start(self):
        """Initialize user-specific state."""
        super().on_start()
        w3 = self._initialize_account_and_w3()

        # Ensure global data is loaded
        if not GlobalSampleData.initialized:
            GlobalSampleData.load_from_arkiv(w3)
    
    @task(20)  # 20% weight
    def point_by_id(self):
        """Point lookup by node_id or workload_id."""
        if not GlobalSampleData.node_ids and not GlobalSampleData.workload_ids:
            return
        
        # Randomly choose node or workload ID
        rng = random.Random()
        entity_id = None
        id_key = None
        
        if rng.random() < 0.5 and GlobalSampleData.node_ids:
            entity_id = rng.choice(GlobalSampleData.node_ids)
            id_key = "node_id"
        elif GlobalSampleData.workload_ids:
            entity_id = rng.choice(GlobalSampleData.workload_ids)
            id_key = "workload_id"
        elif GlobalSampleData.node_ids:
            entity_id = rng.choice(GlobalSampleData.node_ids)
            id_key = "node_id"
        
        if not entity_id:
            return
        
        debug_log(f"[DEBUG] point_by_id: querying {id_key}={entity_id}")

        query = f'{id_key}="{entity_id}"'
        try:
            count = self._fire_locust_request("point_by_id", lambda: self._query_count(query))
            debug_log(f"[DEBUG] point_by_id: SUCCESS - found {count} entities for {id_key}={entity_id}")
        except Exception as e:
            debug_log(f"[DEBUG] point_by_id: FAILED - error={e}, entity_id={entity_id}")
            raise
    
    @task(15)  # 15% weight
    def point_by_key(self):
        """Direct lookup by entity_key."""
        if not GlobalSampleData.entity_keys:
            return
        
        # Use the single entity key (or first one if multiple somehow)
        entity_key = GlobalSampleData.entity_keys[0]
        debug_log(f"[DEBUG] point_by_key: querying entity_key={entity_key[:20]}...")

        w3 = self._initialize_account_and_w3()
        try:
            entity = self._fire_locust_request("point_by_key", lambda: w3.arkiv.get_entity(entity_key))
            key = getattr(entity, "key", "unknown")
            debug_log(f"[DEBUG] point_by_key: SUCCESS - found entity key={str(key)[:20]}...")
        except Exception as e:
            if self._is_not_found(e):
                debug_log(f"[DEBUG] point_by_key: NOT_FOUND - entity_key={entity_key[:20]}...")
                return
            debug_log(f"[DEBUG] point_by_key: FAILED - error={e}, entity_key={entity_key[:20]}...")
            raise
    
    @task(10)  # 10% weight
    def point_miss(self):
        """Lookup non-existent entity (guaranteed miss)."""
        # Generate a random UUID that doesn't exist
        import uuid
        nonexistent_key = "0x0000000000000000000000000000000000000000000000000000000000000001"
        debug_log(f"[DEBUG] point_miss: querying non-existent entity_key={nonexistent_key[:20]}...")

        w3 = self._initialize_account_and_w3()
        try:
            _ = self._fire_locust_request("point_miss", lambda: w3.arkiv.get_entity(nonexistent_key))
            debug_log(f"[DEBUG] point_miss: FAILED - unexpectedly found key={nonexistent_key[:20]}...")
            raise RuntimeError("Expected entity to be missing, but it existed")
        except Exception as e:
            if self._is_not_found(e):
                debug_log(f"[DEBUG] point_miss: SUCCESS - got expected not-found for key={nonexistent_key[:20]}...")
                return
            debug_log(f"[DEBUG] point_miss: FAILED - unexpected error={e} for key={nonexistent_key[:20]}...")
            raise
    
    @task(25)  # 25% weight
    def node_filter(self):
        """Find available nodes matching filter criteria using range queries."""
        rng = random.Random()
        
        region = rng.choice(REGIONS)
        vm_type = rng.choice(VM_TYPES)
        
        # Use range queries for numeric attributes (>= operator)
        # This allows finding nodes with at least the specified resources
        min_cpu = rng.choice([4, 8, 16, 32])
        min_ram = rng.choice([16, 32, 64, 128])
        
        debug_log(f"[DEBUG] node_filter: querying status=available, type=node, region={region}, "
              f"vm_type={vm_type}, cpu_count>={min_cpu}, ram_gb>={min_ram}")

        query_str = (
            f'status="available" && type="node" && region="{region}" && vm_type="{vm_type}"'
            f" && cpu_count>={min_cpu} && ram_gb>={min_ram}"
        )
        try:
            count = self._fire_locust_request(
                "node_filter", lambda: self._query_count(query_str, limit=DEFAULT_NODE_LIMIT)
            )
            debug_log(f"[DEBUG] node_filter: SUCCESS - found {count} nodes")
        except Exception as e:
            debug_log(f"[DEBUG] node_filter: FAILED - error={e}")
            raise
    
    @task(15)  # 15% weight
    def workload_simple(self):
        """Find pending workloads (status filter only)."""
        debug_log(f"[DEBUG] workload_simple: querying status=pending, type=workload")

        query_str = 'status="pending" && type="workload"'
        try:
            count = self._fire_locust_request(
                "workload_simple",
                lambda: self._query_count(query_str, limit=DEFAULT_WORKLOAD_LIMIT),
            )
            debug_log(f"[DEBUG] workload_simple: SUCCESS - found {count} workloads")
        except Exception as e:
            debug_log(f"[DEBUG] workload_simple: FAILED - error={e}")
            raise
    
    @task(15)  # 15% weight
    def workload_specific(self):
        """Find pending workloads matching region and vm_type."""
        rng = random.Random()
        
        region = rng.choice(REGIONS)
        vm_type = rng.choice(VM_TYPES)
        
        debug_log(f"[DEBUG] workload_specific: querying status=pending, type=workload, "
              f"region={region}, vm_type={vm_type}")

        query_str = (
            f'status="pending" && type="workload" && region="{region}" && vm_type="{vm_type}"'
        )
        try:
            count = self._fire_locust_request(
                "workload_specific",
                lambda: self._query_count(query_str, limit=DEFAULT_WORKLOAD_LIMIT),
            )
            debug_log(f"[DEBUG] workload_specific: SUCCESS - found {count} workloads")
        except Exception as e:
            debug_log(f"[DEBUG] workload_specific: FAILED - error={e}")
            raise


# =============================================================================
# Test Initialization Hook
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Load sample data once when test starts."""
    print("=" * 60)
    print("Initializing read-only stress test")
    print("=" * 60)
    print(f"Query mix: {QUERY_MIX}")
    print()
    print("Sample data will be loaded from Arkiv on first user start.")
    print()

