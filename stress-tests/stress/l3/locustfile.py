import logging
import time
import uuid
import random
import socket
import os
import sys
from pathlib import Path
from datetime import timedelta
from itertools import combinations

# Add the parent directory to Python path so we can import stress module
# This file is at: stress-tests/stress/l3/locustfile.py
# We need to add stress-tests/ to the path
file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # Go up from l3/ to stress/ to stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from arkiv import Arkiv
from arkiv.account import NamedAccount
from arkiv.types import KEY, Operations
from arkiv.utils import to_create_op, to_query_options
from eth_account.signers.local import LocalAccount
from locust import task, between, events, constant_pacing
from locust.runners import MasterRunner, LocalRunner
from web3 import Web3
import web3
from eth_account import Account

import stress.tools.config as config
from stress.tools.utils import launch_image, build_account_path
from stress.tools.metrics import Metrics
from stress.tools.entity_count_updater import EntityCountUpdater
from stress.tools.json_rpc_user import JsonRpcUser

Account.enable_unaudited_hdwallet_features()

# Default block duration in seconds
DEFAULT_BLOCK_DURATION: int = 2

# Use a very large max_results_per_page so Arkiv controls pagination
MAX_RESULTS_PER_PAGE: int = 1_000_000_000

# Default entity expiration time
DEFAULT_EXPIRATION_TIME: timedelta = timedelta(minutes=20)

# JSON data as one-line Python string
bigger_payload = b'{"offer":{"constraints":"(&\\n  (golem.srv.comp.expiration>1653219330118)\\n  (golem.node.debug.subnet=0987)\\n)","offerId":"7f2f81f213dd48549e080d774dbf1bc2-076a8cbae6546e5f158e5b4d3a869f25a8e2ae426279a691e7ee45315efa3d83","properties":{"golem":{"activity":{"caps":{"transfer":{"protocol":["http","https","gftp"]}}},"com":{"payment":{"debit-notes":{"accept-timeout?":240},"platform":{"erc20-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"},"zksync-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"}}},"pricing":{"model":{"@tag":"linear","linear":{"coeffs":[0.0002777777777777778,0.001388888888888889,0.0]}}},"scheme":"payu","usage":{"vector":["golem.usage.duration_sec","golem.usage.cpu_sec"]}},"inf":{"cpu":{"architecture":"x86_64","capabilities":["sse3","pclmulqdq","dtes64","monitor","dscpl","vmx","eist","tm2","ssse3","fma","cmpxchg16b","pdcm","pcid","sse41","sse42","x2apic","movbe","popcnt","tsc_deadline","aesni","xsave","osxsave","avx","f16c","rdrand","fpu","vme","de","pse","tsc","msr","pae","mce","cx8","apic","sep","mtrr","pge","mca","cmov","pat","pse36","clfsh","ds","acpi","mmx","fxsr","sse","sse2","ss","htt","tm","pbe","fsgsbase","adjust_msr","smep","rep_movsb_stosb","invpcid","deprecate_fpu_cs_ds","mpx","rdseed","rdseed","adx","smap","clflushopt","processor_trace","sgx","sgx_lc"],"cores":6,"model":"Stepping 10 Family 6 Model 158","threads":11,"vendor":"GenuineIntel"},"mem":{"gib":28.0},"storage":{"gib":57.276745605468754}},"node":{"debug":{"subnet":"0987"},"id":{"name":"nieznanysprawiciel-laptop-Provider-2"}},"runtime":{"capabilities":["vpn"],"name":"vm","version":"0.2.10"},"srv":{"caps":{"multi-activity":true}}}},"providerId":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23","timestamp":"2022-05-22T11:35:49.290821396Z"},"proposedSignature":"NoSignature","state":"Pending","timestamp":"2022-05-22T11:35:49.290821396Z","validTo":"2022-05-22T12:35:49.280650Z"}'
simple_payload = b"Hello Arkiv Workshop!"


gb_container = None


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize Locust - runs once when Locust starts."""
    runner = getattr(environment, "runner", None)
    # only run on the master node or local runner
    if isinstance(runner, (MasterRunner, LocalRunner)):
        logging.info("Running on master/local runner - creating EntityCountUpdater")
        EntityCountUpdater.instance = EntityCountUpdater(environment)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    Metrics.reset_global_metrics()
    metrics = Metrics.get_metrics()
    metrics.initialize(instance_id=socket.gethostname())
    metrics.set_loadtest_status("running")

    logging.info(
        f"A new test is starting with nr of users {environment.runner.target_user_count}"
    )

    # Start/restart EntityCountUpdater (host may have changed)
    runner = getattr(environment, "runner", None)
    if isinstance(runner, (MasterRunner, LocalRunner)):
        if EntityCountUpdater.instance:
            EntityCountUpdater.instance.restart()

    if (
        config.chain_env == "local"
        and config.image_to_run
        and not config.fresh_container_for_each_test
    ):
        global gb_container
        gb_container = launch_image(config.image_to_run)
        logging.info(f"A new test is starting and a new container is launched")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    metrics = Metrics.get_metrics()
    if metrics:
        metrics.set_loadtest_status("stopped")

    if (
        config.chain_env == "local"
        and config.image_to_run
        and not config.fresh_container_for_each_test
    ):
        global gb_container
        if gb_container:
            gb_container.stop()
        logging.info(f"A new test is ending and the container is stopped")


class ArkivL3User(JsonRpcUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique_ids = set()
        self.account: LocalAccount | None = None
        self.w3: Arkiv | None = None
        self.block_duration: int = DEFAULT_BLOCK_DURATION

    def on_start(self):
        super().on_start()
        self.block_duration = self._query_block_duration()

    def _initialize_account_and_w3(self):
        """Initialize account and w3 connection if not already initialized."""
        if self.account is None or self.w3 is None:
            account_path = build_account_path(self.id)
            self.account = Account.from_mnemonic(
                config.mnemonic, account_path=account_path
            )
            logging.info(f"Account: {self.account.address} (user: {self.id})")

            logging.info(f"Connecting to Arkiv L3 (user: {self.id})")
            logging.info(f"Base URL: {self.client.base_url} (user: {self.id})")
            self.w3 = Arkiv(
                web3.HTTPProvider(
                    endpoint_uri=self.client.base_url, session=self.client
                ),
                NamedAccount(name=f"LocalSigner", account=self.account),
            )

            if not self.w3.is_connected():
                logging.error(f"Not connected to Arkiv L3 (user: {self.id})")
                raise Exception(f"Not connected to Arkiv L3 (user: {self.id})")

            logging.info(f"Connected to Arkiv L3 (user: {self.id})")

            if config.chain_env == "local":
                self._topup_local_account()

        return self.w3

    def _topup_local_account(self):
        """Top up local account with ETH from the first account."""
        accounts = self.w3.eth.accounts

        balance = Web3.from_wei(self.w3.eth.get_balance(self.account.address), "ether")
        logging.info(f"Balance: {balance} ETH (user: {self.id})")
        
        # Top up if balance is below 0.1 ETH
        if balance < 0.1:
            tx_hash = self.w3.eth.send_transaction(
                {
                    "from": accounts[0],
                    "to": self.account.address,
                    "value": Web3.to_wei(10, "ether"),
                }
            )
            logging.info(f"Transaction hash: {tx_hash} (user: {self.id})")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logging.info(f"Transaction confirmed in block: {receipt.blockNumber} (user: {self.id})")

    def _query_block_duration(self) -> int:
        """Get block duration from block timing."""
        try:
            block_timing = self.w3.arkiv.get_block_timing()
            duration = block_timing.duration
            logging.info(f"Block duration: {duration} seconds (user: {self.id})")
            return duration
        except Exception:
            return DEFAULT_BLOCK_DURATION

    def _calculate_expiration(self, duration: timedelta) -> int:
        """
        Calculate expiration time in seconds based on duration and block timing.

        Args:
            duration: Duration as timedelta

        Returns:
            Expiration time in seconds
        """
        # Convert timedelta to total seconds
        duration_seconds = int(duration.total_seconds())

        # Calculate expiration based on block duration
        # Round up to nearest block
        blocks_needed = (
            duration_seconds + self.block_duration - 1
        ) // self.block_duration
        expiration_seconds = blocks_needed * self.block_duration

        return expiration_seconds

    def _generate_payload(self, size_bytes: int) -> bytes:
        """
        Generate a payload of the specified size in bytes using
        high-entropy random data to avoid compression.
        """
        return os.urandom(size_bytes)

    def _get_annotations_for_percentages(self) -> dict[str, str]:
        """
        Get dictionary of annotation (name, value) pairs based on divisibility by powers of 2.
        
        Generates an independent random number for each power of 2 (2, 4, 8, 16, 32, 64)
        and checks divisibility. This allows independent selection for each annotation.
        Returns annotation dictionary that can be merged into attributes.
        
        Returns:
            Dictionary of annotations, e.g., {"selector2": "2", "selector4": "4"}
        """
        annotations = {}
        
        # Powers of 2 to check divisibility
        powers_of_2 = [2, 4, 8, 16, 32, 64]
        
        # Generate independent random number for each power of 2
        for power in powers_of_2:
            number = random.randint(1, 128)
            if number % power == 0:
                annotations[f"selector{power}"] = str(power)
        
        return annotations

    @task(1)
    def store_bigger_payload(self, expires_in: timedelta = DEFAULT_EXPIRATION_TIME):
        gb_container = None
        try:
            if (
                config.chain_env == "local"
                and config.image_to_run
                and config.fresh_container_for_each_test
            ):
                gb_container = launch_image(config.image_to_run)

            w3 = self._initialize_account_and_w3()

            nonce = w3.eth.get_transaction_count(self.account.address)
            logging.info(f"Nonce: {nonce}")

            start_time = time.perf_counter()
            expiration_seconds = self._calculate_expiration(expires_in)
            w3.arkiv.create_entity(
                payload=bigger_payload,
                content_type="application/json",
                attributes={"ArkivEntityType": "StressedEntity"},
                expires_in=expiration_seconds,
            )
            duration = timedelta(seconds=time.perf_counter() - start_time)

            Metrics.get_metrics().record_transaction(len(bigger_payload), duration)
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)
            raise
        finally:
            if gb_container:
                gb_container.stop()

    def _store_payload(
        self,
        size_bytes: int,
        count: int = 1,
        expires_in: timedelta = DEFAULT_EXPIRATION_TIME,
    ):
        """
        Store one or more payloads of the specified size.

        Args:
            size_bytes: Size of the payload in bytes
            count: Number of entities to create in a single transaction (default: 1)
            expires_in: Expiration time as timedelta (default: 30 minutes)
        """
        try:
            w3 = self._initialize_account_and_w3()

            # Calculate expiration in seconds based on block timing
            expiration_seconds = self._calculate_expiration(expires_in)

            # Generate payload of the specified size (same payload for all entities)
            payload = self._generate_payload(size_bytes)

            # Generate create operations for all entities
            operations = []
            total_payload_size = 0
            for _ in range(count):
                # Generate unique ID and store it in the set for use in other tasks
                unique_id = str(uuid.uuid4())
                self.unique_ids.add(unique_id)

                # Random query percentage between 1 and 100
                query_percentage = random.randint(1, 100)

                # Build attributes dictionary
                attributes = {
                    "ArkivEntityType": "StressedEntity",
                    "queryPercentage": query_percentage,  # Random percentage 1-100 for querying
                    "uniqueId": unique_id,  # Unique attribute for single entity query
                }
                
                # Generate annotations based on divisibility by powers of 2 and merge into attributes
                annotations = self._get_annotations_for_percentages()
                attributes.update(annotations)

                # Create operation for this entity
                create_op = to_create_op(
                    payload=payload,
                    content_type="text/plain",
                    attributes=attributes,
                    expires_in=expiration_seconds,
                )
                operations.append(create_op)
                total_payload_size += len(payload)

            nonce = w3.eth.get_transaction_count(self.account.address)
            logging.info(
                f"Sending transaction with nonce: {nonce}, payload size: {size_bytes} bytes, "
                f"count: {count}, user: {self.id}"
            )

            start_time = time.perf_counter()
            # Execute all create operations in a single transaction
            operations = Operations(creates=operations)
            receipt = w3.arkiv.execute(operations)
            duration = timedelta(seconds=time.perf_counter() - start_time)

            # Verify receipt
            if len(receipt.creates) != count:
                raise Exception(
                    f"Expected {count} creates, but got {len(receipt.creates)}"
                )

            Metrics.get_metrics().record_transaction(
                total_payload_size, duration, count
            )
        except Exception as e:
            logging.error(
                f"Error in _store_payload (user: {self.id}, size: {size_bytes} bytes, count: {count}): {e}",
                exc_info=True,
            )
            raise

    @task(1)
    def store_100_bytes_payload(self):
        """Store a 100 bytes payload"""
        self._store_payload(100)

    @task(1)
    def store_100_bytes_10_entities(self):
        """Store 10 entities with 100 bytes payload each"""
        self._store_payload(100, count=10)

    @task(1)
    def store_100_bytes_20_entities(self):
        """Store 20 entities with 100 bytes payload each"""
        self._store_payload(100, count=20)

    @task(1)
    def store_100_bytes_30_entities(self):
        """Store 30 entities with 100 bytes payload each"""
        self._store_payload(100, count=30)

    @task(1)
    def store_100_bytes_50_entities(self):
        """Store 50 entities with 100 bytes payload each"""
        self._store_payload(100, count=50)

    @task(1)
    def store_100_bytes_70_entities(self):
        """Store 70 entities with 100 bytes payload each"""
        self._store_payload(100, count=70)

    @task(1)
    def store_100_bytes_100_entities(self):
        """Store 100 entities with 100 bytes payload each"""
        self._store_payload(100, count=100)

    @task(1)
    def store_100_bytes_130_entities(self):
        """Store 130 entities with 100 bytes payload each"""
        self._store_payload(100, count=130)

    @task(1)
    def store_100_bytes_150_entities(self):
        """Store 150 entities with 100 bytes payload each"""
        self._store_payload(100, count=150)

    @task(1)
    def store_100_bytes_200_entities(self):
        """Store 200 entities with 100 bytes payload each"""
        self._store_payload(100, count=200)

    @task(1)
    def store_100_bytes_500_entities(self):
        """Store 200 entities with 100 bytes payload each"""
        self._store_payload(100, count=500)

    @task(1)
    def store_100_bytes_1000_entities(self):
        """Store 200 entities with 100 bytes payload each"""
        self._store_payload(100, count=1000)

    @task(2)
    def store_1kb_payload(self):
        """Store a 1 KB payload"""
        self._store_payload(1024)

    @task(1)
    def store_1kb_10_entities(self):
        """Store 10 entities with 1 KB payload each"""
        self._store_payload(1024, count=10)

    @task(1)
    def store_1kb_50_entities(self):
        """Store 50 entities with 1 KB payload each"""
        self._store_payload(1024, count=50)

    @task(1)
    def store_10kb_payload(self):
        """Store a 10 KB payload"""
        self._store_payload(10 * 1024)

    @task(1)
    def store_10kb_5_entities(self):
        """Store 5 entities with 10 KB payload each"""
        self._store_payload(10 * 1024, count=5)

    @task(1)
    def store_32kb_payload(self):
        """Store a 32 KB payload"""
        self._store_payload(32 * 1024)

    @task(1)
    def store_32kb_2_entities(self):
        """Store 2 entities with 32 KB payload each"""
        self._store_payload(32 * 1024, count=2)

    @task(1)
    def store_64kb_payload(self):
        """Store a 64 KB payload (maximum limit)"""
        self._store_payload(64 * 1024)

    @task(1)
    def query_single_entity(self):
        """
        Query a single entity by uniqueId randomly selected from previously stored payloads.
        """
        if not self.unique_ids:
            logging.info(
                f"No unique IDs available yet (user: {self.id}), skipping query_single_entity."
            )
            return

        unique_id = random.choice(tuple(self.unique_ids))

        try:
            w3 = self._initialize_account_and_w3()
            start_time = time.perf_counter()
            query = f'UniqueId="{unique_id}" && ArkivEntityType="StressedEntity"'
            result = w3.arkiv.query_entities(
                query=query,
                options=to_query_options(fields=KEY, max_results_per_page=MAX_RESULTS_PER_PAGE),
            )
            entities = [entity for entity in result]
            duration = timedelta(seconds=time.perf_counter() - start_time)

            Metrics.get_metrics().record_query(0, duration, len(entities))

            logging.info(
                f"Single-entity query for uniqueId {unique_id} returned {len(entities)} entities (user: {self.id})"
            )
        except Exception as e:
            logging.error(
                f"Error in query_single_entity (user: {self.id}, uniqueId: {unique_id}): {e}",
                exc_info=True,
            )
            raise

    def selective_query(self, percent: int = 50):
        """
        Stress test query that chooses only a selected percent of Entities
        """
        try:
            logging.info(f"Selective query with threshold: {percent} (user: {self.id})")
            w3 = self._initialize_account_and_w3()

            # Query entities with queryPercentage below threshold
            start_time = time.perf_counter()

            query = f'ArkivEntityType="StressedEntity" && queryPercentage<{percent}'
            result = w3.arkiv.query_entities(
                query=query,
                options=to_query_options(fields=KEY, max_results_per_page=MAX_RESULTS_PER_PAGE),
            )
            entities = [entity for entity in result]
            duration = timedelta(seconds=time.perf_counter() - start_time)

            Metrics.get_metrics().record_query(percent, duration, len(entities))

            logging.info(
                f"Found {len(entities)} entities with queryPercentage < {percent} (user: {self.id})"
            )
            logging.debug(f"Result: {result} (user: {self.id})")
        except Exception as e:
            logging.error(
                f"Error in selective_query (user: {self.id}, percent: {percent}): {e}",
                exc_info=True,
            )
            raise

    def _calculate_selector_approximation(self, target_percent: float) -> list[str]:
        """
        Calculate the best combination of selectors to approximate the target percentage.
        
        With independent random decisions, each selector has approximate probability:
        - selector2: ~50%, selector4: ~25%, selector8: ~12.5%, 
        - selector16: ~6.25%, selector32: ~3.125%, selector64: ~1.5625%
        
        For OR queries with independent events: P(A OR B) = P(A) + P(B) - P(A) * P(B)
        
        Args:
            target_percent: Target percentage (0-100)
            
        Returns:
            List of selector values (numbers as strings) that best approximate the target percentage
        """
        # Individual selector probabilities (as decimals)
        selector_probs = {
            "2": 0.5,
            "4": 0.25,
            "8": 0.125,
            "16": 0.0625,
            "32": 0.03125,
            "64": 0.015625,
        }
        
        target_prob = target_percent / 100.0
        best_combination = []
        best_diff = float('inf')
        
        # Try all combinations of selectors (powerset)
        selectors = list(selector_probs.keys())
        
        for r in range(1, len(selectors) + 1):
            for combo in combinations(selectors, r):
                # Calculate union probability for independent events
                # P(A OR B OR C) = 1 - (1-P(A)) * (1-P(B)) * (1-P(C))
                union_prob = 1.0
                for sel in combo:
                    union_prob *= (1.0 - selector_probs[sel])
                union_prob = 1.0 - union_prob
                
                diff = abs(union_prob - target_prob)
                if diff < best_diff:
                    best_diff = diff
                    best_combination = list(combo)
        
        return best_combination

    def selective_query_by_attribute(self, percent: int):
        """
        Stress test query that selects entities by annotation attribute values.
        
        Derives annotation selectors from the target percentage to approximate it.
        
        Args:
            percent: Target percentage (0-100)
        """
        try:
            # Calculate best approximation for the target percentage
            annotation_values = self._calculate_selector_approximation(percent)
            annotation_str = ", ".join(annotation_values)
            
            logging.info(
                f"Selective query by attribute for {percent}% with selectors: {annotation_str} (user: {self.id})"
            )
            w3 = self._initialize_account_and_w3()

            # Build query: entities with any of the specified annotations
            # Query format: selector2="2" || selector4="4"
            annotation_conditions = [
                f'selector{value}="{value}"' for value in annotation_values
            ]
            query = (
                f'ArkivEntityType="StressedEntity" && ('
                + " || ".join(annotation_conditions)
                + ")"
            )

            start_time = time.perf_counter()
            result = w3.arkiv.query_entities(
                query=query,
                options=to_query_options(fields=KEY, max_results_per_page=MAX_RESULTS_PER_PAGE),
            )
            entities = [entity for entity in result]
            duration = timedelta(seconds=time.perf_counter() - start_time)

            Metrics.get_metrics().record_query(percent, duration, len(entities))

            logging.info(
                f"Found {len(entities)} entities with selectors {annotation_str} (target: {percent}%) (user: {self.id})"
            )
            logging.debug(f"Result: {result} (user: {self.id})")
        except Exception as e:
            logging.error(
                f"Error in selective_query_by_attribute (user: {self.id}, percent: {percent}): {e}",
                exc_info=True,
            )
            raise

    @task(1)
    def selective_query_by_value_1Percent(self):
        self.selective_query(1)

    @task(1)
    def selective_query_by_value_5Percent(self):
        self.selective_query(5)

    @task(1)
    def selective_query_by_value_20Percent(self):
        self.selective_query(20)

    @task(1)
    def selective_query_by_value_40Percent(self):
        self.selective_query(40)

    @task(1)
    def selective_query_by_value_60Percent(self):
        self.selective_query(60)

    @task(1)
    def selective_query_by_value_80Percent(self):
        self.selective_query(80)

    @task(1)
    def selective_query_by_value_100Percent(self):
        self.selective_query(100)

    @task(1)
    def selective_query_by_attribute_1Percent(self):
        """Query entities for 1% target"""
        self.selective_query_by_attribute(1)

    @task(1)
    def selective_query_by_attribute_5Percent(self):
        """Query entities for 5% target"""
        self.selective_query_by_attribute(5)

    @task(1)
    def selective_query_by_attribute_20Percent(self):
        """Query entities for 20% target"""
        self.selective_query_by_attribute(20)

    @task(1)
    def selective_query_by_attribute_40Percent(self):
        """Query entities for 40% target"""
        self.selective_query_by_attribute(40)

    @task(1)
    def selective_query_by_attribute_60Percent(self):
        """Query entities for 60% target"""
        self.selective_query_by_attribute(60)

    @task(1)
    def selective_query_by_attribute_80Percent(self):
        """Query entities for 80% target"""
        self.selective_query_by_attribute(80)

    @task(1)
    def retrieve_keys_to_count(self):
        try:
            logging.info(f"Retrieving offers")
            w3 = Arkiv(
                web3.HTTPProvider(
                    endpoint_uri=self.client.base_url, session=self.client
                )
            )
            result = w3.arkiv.query_entities(
                query='ArkivEntityType="StressedEntity"',
                options=to_query_options(fields=KEY, max_results_per_page=MAX_RESULTS_PER_PAGE),
            )

            logging.debug(f"Result: {result} (user: {self.id})")
            entities = [entity for entity in result]
            logging.info(f"Keys: {len(entities)}")
        except Exception as e:
            logging.error(
                f"Error in retrieve_keys_to_count (user: {self.id}): {e}", exc_info=True
            )
            raise

    @task(1)
    def store_simple_payload(self):
        gb_container = None
        try:
            if (
                config.chain_env == "local"
                and config.image_to_run
                and config.fresh_container_for_each_test
            ):
                gb_container = launch_image(config.image_to_run)

            w3 = self._initialize_account_and_w3()

            nonce = w3.eth.get_transaction_count(self.account.address)
            logging.info(f"Nonce: {nonce}")

            start_time = time.perf_counter()
            w3.arkiv.create_entity(
                payload=simple_payload,
                content_type="application/json",
                attributes={"GolemBaseMarketplace": "Offer", "projectId": "ArkivStressTest"},
                btl=2592000,  # 30 days
            )
            duration = timedelta(seconds=time.perf_counter() - start_time)

            Metrics.get_metrics().record_transaction(len(simple_payload), duration)
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)
            raise
        finally:
            if gb_container:
                gb_container.stop()
