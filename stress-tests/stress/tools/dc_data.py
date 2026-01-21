
import random
import uuid
from dataclasses import dataclass
from typing import Iterator


# =============================================================================
# Configuration & Constants
# =============================================================================

NODE = "node"
WORKLOAD = "workload"

MAX_BLOCK = 9223372036854775807  # Max int64, represents "current" state

# System attributes added by arkiv
SYSTEM_STRING_ATTRS = ["$creator", "$key", "$owner"]
SYSTEM_NUMERIC_ATTRS = ["$createdAtBlock", "$expiration", "$opIndex", "$sequence", "$txIndex"]

DEFAULT_NODE_UPDATES_PER_BLOCK = 60
DEFAULT_WORKLOAD_UPDATES_PER_BLOCK = 600


@dataclass
class NodeEntity:
    """Represents a compute node in a data center."""
    entity_key: bytes
    dc_id: str
    node_id: str
    region: str
    status: str
    vm_type: str
    cpu_count: int
    ram_gb: int
    price_hour: int
    avail_hours: int
    payload: bytes
    block: int
    ttl: int
    tx_index: int = 0
    op_index: int = 0
    sequence: int = 0


@dataclass
class WorkloadEntity:
    """Represents a workload/job in a data center."""
    entity_key: bytes
    dc_id: str
    workload_id: str
    status: str
    assigned_node: str
    region: str
    vm_type: str
    req_cpu: int
    req_ram: int
    max_hours: int
    payload: bytes
    block: int
    ttl: int
    tx_index: int = 0
    op_index: int = 0
    sequence: int = 0


# =============================================================================
# Distribution Helpers (encapsulated for easy modification)
# =============================================================================

def get_region_distribution() -> list[tuple[str, float]]:
    """Region distribution: (value, cumulative_probability)."""
    return [
        ("eu-west", 0.40),
        ("us-east", 0.75),   # 0.40 + 0.35
        ("asia-pac", 1.00),  # 0.75 + 0.25
    ]


def get_vm_type_distribution() -> list[tuple[str, float]]:
    """VM type distribution: (value, cumulative_probability)."""
    return [
        ("cpu", 0.70),
        ("gpu", 0.95),       # 0.70 + 0.25
        ("gpu_large", 1.00), # 0.95 + 0.05
    ]


def get_node_status_distribution() -> list[tuple[str, float]]:
    """Node status distribution: (value, cumulative_probability)."""
    return [
        ("available", 0.70),
        ("busy", 0.95),      # 0.70 + 0.25
        ("offline", 1.00),   # 0.95 + 0.05
    ]


def get_workload_status_distribution() -> list[tuple[str, float]]:
    """Workload status distribution: (value, cumulative_probability)."""
    return [
        ("pending", 0.15),
        ("running", 0.95),   # 0.15 + 0.80
        ("completed", 1.00), # 0.95 + 0.05
    ]


def get_cpu_count_distribution() -> list[tuple[int, float]]:
    """CPU count distribution: (value, cumulative_probability)."""
    return [
        (4, 0.30),
        (8, 0.60),
        (16, 0.85),
        (32, 1.00),
    ]


def get_ram_gb_distribution() -> list[tuple[int, float]]:
    """RAM GB distribution: (value, cumulative_probability)."""
    return [
        (16, 0.25),
        (32, 0.55),
        (64, 0.85),
        (128, 1.00),
    ]


def get_price_hour_range() -> tuple[int, int]:
    """Price per hour range in cents: (min, max)."""
    return (50, 500)


def get_avail_hours_distribution() -> list[tuple[int, float]]:
    """Availability hours distribution: (value, cumulative_probability)."""
    return [
        (1, 0.10),
        (4, 0.30),
        (8, 0.55),
        (24, 0.80),
        (168, 1.00),  # 1 week
    ]


def get_req_cpu_distribution() -> list[tuple[int, float]]:
    """Requested CPU distribution: (value, cumulative_probability)."""
    return [
        (1, 0.40),
        (2, 0.70),
        (4, 0.90),
        (8, 1.00),
    ]


def get_req_ram_distribution() -> list[tuple[int, float]]:
    """Requested RAM distribution: (value, cumulative_probability)."""
    return [
        (4, 0.35),
        (8, 0.65),
        (16, 0.90),
        (32, 1.00),
    ]


def get_max_hours_distribution() -> list[tuple[int, float]]:
    """Max runtime hours distribution: (value, cumulative_probability)."""
    return [
        (1, 0.30),
        (2, 0.55),
        (4, 0.75),
        (8, 0.90),
        (24, 1.00),
    ]


def get_ttl_blocks_distribution() -> list[tuple[tuple[int, int], float]]:
    """
    TTL in number of blocks distribution: ((min, max), cumulative_probability).
    
    Block time = 2s, so:
    - 1 hour = 1,800 blocks
    - 1 day = 43,200 blocks
    - 1 week = 302,400 blocks
    
    Distribution:
    - 10%: 1-6 hours (short-lived)
    - 60%: 12 hours - 7 days (medium-lived)
    - 30%: 7-28 days (long-lived)
    """
    return [
        ((1800, 10800), 0.10),       # 1-6 hours
        ((21600, 302400), 0.70),     # 12 hours - 7 days
        ((302400, 1209600), 1.00),   # 7-28 days
    ]


def sample_ttl_blocks(rng: random.Random) -> int:
    """Sample TTL in blocks from the TTL distribution."""
    dist = get_ttl_blocks_distribution()
    r = rng.random()
    for (min_val, max_val), cumulative_prob in dist:
        if r <= cumulative_prob:
            return rng.randint(min_val, max_val)
    # Fallback to last range
    min_val, max_val = dist[-1][0]
    return rng.randint(min_val, max_val)


def sample_from_distribution(rng: random.Random, dist: list[tuple[any, float]]) -> any:
    """Sample a value from a cumulative probability distribution."""
    r = rng.random()
    for value, cumulative_prob in dist:
        if r <= cumulative_prob:
            return value
    return dist[-1][0]  # Fallback to last value


# =============================================================================
# ID Generation (deterministic)
# =============================================================================

def make_dc_id(dc_num: int) -> str:
    """Generate data center ID: dc_01, dc_02, ..."""
    return f"dc_{dc_num:02d}"


def make_node_id(dc_num: int, node_num: int, seed: int) -> str:
    """Generate node ID using deterministic UUID to avoid collisions."""
    # Create deterministic UUID from seed, dc_num, and node_num
    rng = random.Random(f"{seed}:node:{dc_num}:{node_num}")
    uuid_bytes = bytes(rng.getrandbits(8) for _ in range(16))
    node_uuid = uuid.UUID(bytes=uuid_bytes)
    return f"node_{node_uuid.hex[:12]}"


def make_workload_id(dc_num: int, workload_num: int, seed: int) -> str:
    """Generate workload ID using deterministic UUID to avoid collisions."""
    # Create deterministic UUID from seed, dc_num, and workload_num
    rng = random.Random(f"{seed}:workload:{dc_num}:{workload_num}")
    uuid_bytes = bytes(rng.getrandbits(8) for _ in range(16))
    workload_uuid = uuid.UUID(bytes=uuid_bytes)
    return f"wl_{workload_uuid.hex[:12]}"


def make_entity_key(id_string: str, seed: int) -> bytes:
    """Generate deterministic 32-byte entity key from ID string and seed."""
    # Use seed + id_string to generate reproducible key
    rng = random.Random(f"{seed}:{id_string}")
    return bytes(rng.getrandbits(8) for _ in range(32))


def workload_to_node_num(workload_num: int, nodes_per_dc: int) -> int:
    """Map workload number to node number (deterministic assignment)."""
    return (workload_num - 1) % nodes_per_dc + 1


# =============================================================================
# Entity Creation (high-level)
# =============================================================================

def create_node(
    dc_num: int,
    node_num: int,
    payload_size: int,
    block: int,
    seed: int,
    status: str | None = None,
) -> NodeEntity:
    """Create a single Node entity with randomized attributes.
    
    Args:
        status: If provided, use this status instead of sampling from distribution.
    """
    rng = random.Random(f"{seed}:node:{dc_num}:{node_num}")
    
    dc_id = make_dc_id(dc_num)
    node_id = make_node_id(dc_num, node_num, seed)
    entity_key = make_entity_key(node_id, seed)
    
    # Sample attributes from distributions
    region = sample_from_distribution(rng, get_region_distribution())
    if status is None:
        status = sample_from_distribution(rng, get_node_status_distribution())
    vm_type = sample_from_distribution(rng, get_vm_type_distribution())
    cpu_count = sample_from_distribution(rng, get_cpu_count_distribution())
    ram_gb = sample_from_distribution(rng, get_ram_gb_distribution())
    price_min, price_max = get_price_hour_range()
    price_hour = rng.randint(price_min, price_max)
    avail_hours = sample_from_distribution(rng, get_avail_hours_distribution())
    ttl_blocks = sample_ttl_blocks(rng)

    # Generate random payload
    payload = bytes(rng.getrandbits(8) for _ in range(payload_size))
    
    return NodeEntity(
        entity_key=entity_key,
        dc_id=dc_id,
        node_id=node_id,
        region=region,
        status=status,
        vm_type=vm_type,
        cpu_count=cpu_count,
        ram_gb=ram_gb,
        price_hour=price_hour,
        avail_hours=avail_hours,
        payload=payload,
        block=block,
        ttl=ttl_blocks
    )


def create_workload(
    dc_num: int,
    workload_num: int,
    nodes_per_dc: int,
    payload_size: int,
    block: int,
    seed: int,
    status: str | None = None,
    assigned_node: str | None = None,
) -> WorkloadEntity:
    """Create a single Workload entity with randomized attributes.
    
    Args:
        status: If provided, use this status instead of sampling from distribution.
        assigned_node: If provided, use this as the assigned node ID.
    """
    rng = random.Random(f"{seed}:workload:{dc_num}:{workload_num}")
    
    dc_id = make_dc_id(dc_num)
    workload_id = make_workload_id(dc_num, workload_num, seed)
    entity_key = make_entity_key(workload_id, seed)
    
    # Sample attributes from distributions
    if status is None:
        status = sample_from_distribution(rng, get_workload_status_distribution())
    region = sample_from_distribution(rng, get_region_distribution())
    vm_type = sample_from_distribution(rng, get_vm_type_distribution())
    req_cpu = sample_from_distribution(rng, get_req_cpu_distribution())
    req_ram = sample_from_distribution(rng, get_req_ram_distribution())
    max_hours = sample_from_distribution(rng, get_max_hours_distribution())
    ttl_blocks = sample_ttl_blocks(rng)

    # Use provided assigned_node or determine based on status
    if assigned_node is None:
        if status == "running":
            node_num = workload_to_node_num(workload_num, nodes_per_dc)
            assigned_node = make_node_id(dc_num, node_num, seed)
        else:
            assigned_node = ""
    
    # Generate random payload
    payload = bytes(rng.getrandbits(8) for _ in range(payload_size))
    
    return WorkloadEntity(
        entity_key=entity_key,
        dc_id=dc_id,
        workload_id=workload_id,
        status=status,
        assigned_node=assigned_node,
        region=region,
        vm_type=vm_type,
        req_cpu=req_cpu,
        req_ram=req_ram,
        max_hours=max_hours,
        payload=payload,
        block=block,
        ttl=ttl_blocks
    )


# =============================================================================
# Block-by-Block Entity Generation
# =============================================================================

@dataclass
class BlockData:
    """Data for a single block containing nodes and their workloads."""
    block_num: int
    nodes: list[NodeEntity]
    workloads: list[WorkloadEntity]


def generate_blocks(
    num_blocks: int,
    nodes_per_block: int,
    workloads_per_node: int,
    percentage_assigned: float,
    payload_size: int,
    start_block: int,
    seed: int,
    dc_num: int = 1,
) -> Iterator[BlockData]:
    """
    Generate blocks with nodes and their associated workloads.
    
    Each block contains:
    - N nodes (nodes_per_block)
    - For each node: M workloads (workloads_per_node)
    
    Args:
        num_blocks: Number of blocks to generate
        nodes_per_block: Number of nodes per block
        workloads_per_node: Number of workloads per node
        percentage_assigned: Fraction of nodes that are busy (0.0-1.0)
        payload_size: Size of payload in bytes
        start_block: Starting block number
        seed: Random seed
        dc_num: Data center number (default: 1)
    """
    rng = random.Random(f"{seed}:blocks")
    
    # Global counters for unique IDs
    node_counter = 0
    workload_counter = 0
    
    for block_idx in range(num_blocks):
        current_block = start_block + block_idx
        nodes = []
        workloads = []
        
        for _ in range(nodes_per_block):
            node_counter += 1
            
            # Determine if this node is busy (has assigned workload)
            is_busy = rng.random() < percentage_assigned
            node_status = "busy" if is_busy else "available"
            
            # Create the node
            node = create_node(
                dc_num=dc_num,
                node_num=node_counter,
                payload_size=payload_size,
                block=current_block,
                seed=seed,
                status=node_status,
            )
            nodes.append(node)
            
            # Create workloads for this node
            for wl_idx in range(workloads_per_node):
                workload_counter += 1
                
                # First workload is assigned if node is busy
                if is_busy and wl_idx == 0:
                    wl_status = "running"
                    wl_assigned = node.node_id
                else:
                    wl_status = "pending"
                    wl_assigned = ""
                
                workload = create_workload(
                    dc_num=dc_num,
                    workload_num=workload_counter,
                    nodes_per_dc=node_counter,  # Not used when assigned_node provided
                    payload_size=payload_size,
                    block=current_block,
                    seed=seed,
                    status=wl_status,
                    assigned_node=wl_assigned,
                )
                workloads.append(workload)
        
        yield BlockData(
            block_num=current_block,
            nodes=nodes,
            workloads=workloads,
        )

