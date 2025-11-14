import os
import logging
import threading
from prometheus_client import CollectorRegistry, push_to_gateway, Counter, Gauge, Histogram, Enum, disable_created_metrics

# Prometheus Push Gateway constants
PUSHGATEWAY_HOST = os.getenv("PUSHGATEWAY_HOST", "metrics.golem.network")
PUSHGATEWAY_PORT = os.getenv("PUSHGATEWAY_PORT", "9092")
PUSHGATEWAY_BASE_URL = f"https://{PUSHGATEWAY_HOST}:{PUSHGATEWAY_PORT}"
JOB_NAME = os.getenv("JOB_NAME", "arkiv-stress-l3")
INSTANCE_ID = os.getenv("INSTANCE_ID", None)
DEFAULT_PUSH_INTERVAL = 1  # Default interval in seconds for pushing metrics

# Global metrics instance
_metrics_instance = None

def get_metrics():
    """Get the global metrics instance"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = Metrics()
        logging.info("Created new metrics instance")
    return _metrics_instance


def reset_global_metrics():
    """Reset the global metrics instance - stops current instance and creates a new one"""
    global _metrics_instance
    if _metrics_instance:
        _metrics_instance.stop_push_task()
        logging.info("Stopped previous metrics instance")
    _metrics_instance = get_metrics()  # Create new instance


class Metrics:
    """
    A class to handle Prometheus metrics collection and pushing to push gateway
    """
    
    def __init__(self, instance_id: str = None, push_interval: int = DEFAULT_PUSH_INTERVAL):
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
    
    def initialize(self, instance_id: str = None, push_interval: int = DEFAULT_PUSH_INTERVAL):
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
            'loadtest_current_user_count',
            'Current number of active users in the load test',
            registry=self.registry
        )
        self.current_user_count.set(0)
        
        # Query metrics - counter labelled by percentile
        self.queries_by_percentile = Counter(
            'loadtest_queries_by_percentile',
            'Total number of queries executed by percentile threshold',
            ['percentile'],
            registry=self.registry
        )
        
        # Time histogram buckets incremented by 5% each (0.05s increments)
        time_buckets = [i * 0.05 for i in range(21)]  # 0, 0.05, 0.10, ..., 1.0 seconds
        
        # Query time histogram
        self.query_time = Histogram(
            'loadtest_query_time_seconds',
            'Time taken to execute queries in seconds',
            ['percentile'],
            buckets=time_buckets,
            registry=self.registry
        )
        
        # Transaction metrics
        self.transactions_count = Counter(
            'loadtest_transactions_total',
            'Total number of transactions executed',
            registry=self.registry
        )
        
        self.transaction_payload_bytes = Counter(
            'loadtest_transaction_payload_bytes_total',
            'Total number of bytes sent as payload in transactions',
            registry=self.registry
        )
        
        # Transaction time histogram
        self.transaction_time = Histogram(
            'loadtest_transaction_time_seconds',
            'Time taken to execute transactions in seconds',
            buckets=time_buckets,
            registry=self.registry
        )
        
        # Load test status metric
        self.loadtest_running = Enum(
            'loadtest_status',
            'Current status of the load test',
            states=['stopped', 'running'],
            registry=self.registry
        )
        self.loadtest_running.state('stopped')  # Start as stopped
    
    def _start_push_task(self):
        """Start the background task for periodic metric pushing"""
        self._push_thread = threading.Thread(target=self._push_metrics_loop, daemon=True)
        self._push_thread.start()
        logging.info(f"Started background metrics push task with {self.push_interval}s interval")
    
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
                "hostname": f"locust-{self.instance_id}"
            }
            
            # Merge with provided grouping key
            final_grouping_key = {**default_grouping_key, **(grouping_key or {})}
            
            push_to_gateway(
                push_url,
                job=self.job_name,
                registry=self.registry,
                grouping_key=final_grouping_key
            )
            logging.debug(f"Metrics pushed to {push_url} for job: {self.job_name}")
        except Exception as e:
            logging.error(f"Failed to push metrics to {push_url}: {e}")
    
    def get_registry(self):
        """Get the CollectorRegistry instance"""
        return self.registry
    
    def set_loadtest_status(self, status: str):
        """Set the load test status"""
        if status in ['stopped', 'running']:
            self.loadtest_running.state(status)
            logging.info(f"Load test status set to: {status}")
        else:
            logging.warning(f"Invalid load test status: {status}. Valid states: stopped, running")
        return self.registry
    
    # Simple one-liner functions for recording metrics
    def record_query(self, percentile: int, duration: float):
        """Record a query execution with percentile and duration"""
        self.queries_by_percentile.labels(percentile=str(percentile)).inc()
        self.query_time.labels(percentile=str(percentile)).observe(duration)
    
    def record_transaction(self, payload_bytes: int, duration: float):
        """Record a transaction with payload size and duration"""
        self.transactions_count.inc()
        self.transaction_payload_bytes.inc(payload_bytes)
        self.transaction_time.observe(duration)
