import os
import logging
import threading
from prometheus_client import (
    CollectorRegistry,
    push_to_gateway,
    Counter,
    Gauge,
    Histogram,
    Enum,
    disable_created_metrics,
)

# Prometheus Push Gateway constants
PUSHGATEWAY_HOST = os.getenv("PUSHGATEWAY_HOST", "metrics.golem.network")
PUSHGATEWAY_PORT = os.getenv("PUSHGATEWAY_PORT", "9092")
PUSHGATEWAY_BASE_URL = f"https://{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"
JOB_NAME = os.getenv("JOB_NAME", "arkiv-stress-l3")
INSTANCE_ID = os.getenv("INSTANCE_ID", None)
DEFAULT_PUSH_INTERVAL = 1  # Default interval in seconds for pushing metrics


class Metrics:
    """
    A class to handle Prometheus metrics collection and pushing to push gateway
    """

    _instance = None

    @classmethod
    def get_metrics(cls):
        """Get the global metrics instance"""
        if cls._instance is None:
            cls._instance = cls()
            logging.info("Created new metrics instance")
        return cls._instance

    @classmethod
    def reset_global_metrics(cls):
        """Reset the global metrics instance - stops current instance and creates a new one"""
        if cls._instance:
            cls._instance.stop_push_task()
            logging.info("Stopped previous metrics instance")
        cls._instance = cls()

    def __init__(
        self, instance_id: str = None, push_interval: int = DEFAULT_PUSH_INTERVAL
    ):
        """
        Initialize the Metrics class

        Args:
            instance_id: Instance ID for metrics (defaults to INSTANCE_ID constant)
            push_interval: Interval in seconds for pushing metrics to gateway (defaults to 5)
        """
        self.job_name = JOB_NAME
        self.instance_id = instance_id or INSTANCE_ID
        self.push_interval = push_interval
        self.registry = CollectorRegistry()
        self._stop_event = threading.Event()
        self._push_thread = None
        self._initialized = False

        disable_created_metrics()

        # Initialize common metrics
        self._init_metrics()

    def initialize(
        self, instance_id: str = None, push_interval: int = DEFAULT_PUSH_INTERVAL
    ):
        """
        Initialize the Metrics instance with new parameters and start background threads.
        This should only be called once per application run.

        Args:
            instance_id: Instance ID for metrics (defaults to INSTANCE_ID constant)
            push_interval: Interval in seconds for pushing metrics to gateway (defaults to 5)
        """
        self.instance_id = instance_id or INSTANCE_ID
        self.push_interval = push_interval

        if self._initialized:
            return

        # Start the background task
        self._start_push_task()
        self._initialized = True

    def _init_metrics(self):
        """Initialize metrics for Arkiv L3 stress testing"""

        # Current user count metric
        self.current_user_count = Gauge(
            "loadtest_current_user_count",
            "Current number of active users in the load test",
            registry=self.registry,
        )
        self.current_user_count.set(0)

        # Query metrics - counter labelled by percentile
        self.queries_by_percentile = Counter(
            "loadtest_queries_by_percentile",
            "Total number of queries executed by percentile threshold",
            ["percentile"],
            registry=self.registry,
        )

        # Shared time histogram buckets (in milliseconds)
        # Buckets: first bucket 50ms, second bucket 100ms, then 100ms increments
        time_buckets = [
            50,  # First bucket: 0-50ms
            100,  # Second bucket: 50-100ms
            # Then 100ms increments: 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, ...
            200,
            300,
            400,
            500,
            600,
            700,
            800,
            900,
            1000,
            1100,
            1200,
            1300,
            1400,
            1500,
            1600,
            1700,
            1800,
            1900,
            2000,
            2100,
            2200,
            2300,
            2400,
            2500,
            3000,
            4000,
            5000,
            7000,
            10000,  # Continue with larger range
        ]

        # Query time histogram (in milliseconds)
        self.query_time = Histogram(
            "loadtest_query_time_milliseconds",
            "Time taken to execute queries in milliseconds",
            ["percentile"],
            buckets=time_buckets,
            registry=self.registry,
        )

        # Query result size histogram (number of entities returned)
        result_size_buckets = [
            0,
            1,
            5,
            10,
            25,
            50,
            100,
            250,
            500,
            1000,
            2500,
            5000,
            10000,
            25000,
            50000,
            100000,
        ]
        self.query_result_size = Histogram(
            "loadtest_query_result_size",
            "Number of entities returned by queries",
            ["percentile"],
            buckets=result_size_buckets,
            registry=self.registry,
        )

        # Transaction metrics
        self.transactions_count = Counter(
            "loadtest_transactions_total",
            "Total number of transactions executed",
            registry=self.registry,
        )

        self.transaction_payload_bytes = Counter(
            "loadtest_transaction_payload_bytes_total",
            "Total number of bytes sent as payload in transactions",
            registry=self.registry,
        )

        self.entities_created = Counter(
            "loadtest_entities_created_total",
            "Total number of entities created",
            registry=self.registry,
        )

        # Transaction time histogram (in milliseconds)
        self.transaction_time = Histogram(
            "loadtest_transaction_time_milliseconds",
            "Time taken to execute transactions in milliseconds",
            buckets=time_buckets,
            registry=self.registry,
        )

        # Load test status metric
        self.loadtest_running = Enum(
            "loadtest_status",
            "Current status of the load test",
            states=["stopped", "running"],
            registry=self.registry,
        )
        self.loadtest_running.state("stopped")  # Start as stopped

        # Total entity count metric
        self.total_entity_count = Gauge(
            "arkiv_total_entity_count",
            "Total number of all entities stored on Arkiv at current moment",
            registry=self.registry,
        )
        self.total_entity_count.set(0)

    def _start_push_task(self):
        """Start the background task for periodic metric pushing"""
        self._push_thread = threading.Thread(
            target=self._push_metrics_loop, daemon=True
        )
        self._push_thread.start()
        logging.info(
            f"Started background metrics push task with {self.push_interval}s interval"
        )

    def _push_metrics_loop(self):
        """Background loop for pushing metrics at regular intervals"""
        while not self._stop_event.is_set():
            try:
                self.push_metrics()
                # Wait for the specified interval or until stop event is set
                self._stop_event.wait(self.push_interval)
            except Exception as e:
                logging.error(f"Error in metrics push loop: {e}")
                # Wait a bit before retrying
                self._stop_event.wait(5)

    def stop_push_task(self):
        """Stop the background metrics push task"""
        if self._push_thread and self._push_thread.is_alive():
            self._stop_event.set()
            self._push_thread.join(timeout=5)
            logging.info("Stopped background metrics push task")

    def push_metrics(self, grouping_key: dict = None):
        """
        Push metrics to Prometheus Push Gateway

        Args:
            grouping_key: Dictionary of labels for grouping metrics
        """
        # Don't push metrics if instance_id is not set
        if self.instance_id is None:
            logging.debug("Skipping metrics push - instance_id not set")
            return

        try:
            # Use push gateway URL with job name in path
            push_url = f"{PUSHGATEWAY_BASE_URL}"

            # Set default grouping key with instance and hostname
            default_grouping_key = {
                "job": f"{self.job_name}",
                "instance": f"{self.instance_id}",
                "hostname": f"locust-{self.instance_id}",
            }

            # Merge with provided grouping key
            final_grouping_key = {**default_grouping_key, **(grouping_key or {})}

            push_to_gateway(
                push_url,
                job=self.job_name,
                registry=self.registry,
                grouping_key=final_grouping_key,
            )
            logging.debug(f"Metrics pushed to {push_url} for job: {self.job_name}")
        except Exception as e:
            logging.error(f"Failed to push metrics to {push_url}: {e}")

    def get_registry(self):
        """Get the CollectorRegistry instance"""
        return self.registry

    def set_loadtest_status(self, status: str):
        """Set the load test status"""
        if status in ["stopped", "running"]:
            self.loadtest_running.state(status)
            logging.info(f"Load test status set to: {status}")
        else:
            logging.warning(
                f"Invalid load test status: {status}. Valid states: stopped, running"
            )
        return self.registry

    # Simple one-liner functions for recording metrics
    def record_query(self, selectivness: int, duration: float, result_size: int = 0):
        """
        Record a query execution with percentile, duration, and result size.

        Args:
            selectivness: Selectiveness percentile threshold
            duration: Duration in seconds (converted to milliseconds)
            result_size: Number of entities returned by the query
        """
        self.queries_by_percentile.labels(percentile=str(selectivness)).inc()
        # Convert duration from seconds to milliseconds
        duration_ms = duration * 1000
        self.query_time.labels(percentile=str(selectivness)).observe(duration_ms)
        self.query_result_size.labels(percentile=str(selectivness)).observe(result_size)

    def record_transaction(
        self, payload_bytes: int, duration: float, entity_count: int = 1
    ):
        """Record a transaction with payload size, duration, and entity count (duration in seconds, converted to milliseconds)"""
        self.transactions_count.inc()
        self.transaction_payload_bytes.inc(payload_bytes)
        self.entities_created.inc(entity_count)
        # Convert duration from seconds to milliseconds
        duration_ms = duration * 1000
        self.transaction_time.observe(duration_ms)
