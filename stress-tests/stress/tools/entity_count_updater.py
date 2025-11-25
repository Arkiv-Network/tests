import logging
import threading

from arkiv import Arkiv
from web3 import Web3
import web3


import stress.tools.config as config
from stress.tools.metrics import Metrics


class EntityCountUpdater:
    """Background thread that periodically updates the total entity count metric."""

    instance = None

    def __init__(self, update_interval: int = 3):
        """
        Initialize the entity count updater.

        Args:
            update_interval: Interval in seconds between updates (default: 3)
        """
        self.update_interval = update_interval
        self._stop_event = threading.Event()
        self._thread = None
        self._w3 = None

    def _update_loop(self):
        """Internal method that runs in the background thread."""
        # Create a connection to Arkiv for the background thread
        self._w3 = Arkiv(web3.HTTPProvider(endpoint_uri=config.host))

        if not self._w3.is_connected():
            logging.error("EntityCountUpdater: Not connected to Arkiv L3")
            return

        logging.info("EntityCountUpdater: Started")

        while not self._stop_event.is_set():
            try:
                entity_count = self._w3.eth.get_entity_count()
                Metrics.get_metrics().total_entity_count.set(entity_count)
                logging.info(
                    f"EntityCountUpdater: Updated entity count to {entity_count}"
                )
            except Exception as e:
                logging.error(
                    f"EntityCountUpdater: Error updating entity count: {e}",
                    exc_info=True,
                )

            # Wait for update interval or until stop event is set
            self._stop_event.wait(self.update_interval)

        logging.info("EntityCountUpdater: Stopped")

    def start(self):
        """Start the background thread."""
        if self._thread is not None and self._thread.is_alive():
            logging.warning("EntityCountUpdater: Already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self._thread.start()
        logging.info("EntityCountUpdater: Started background thread")

    def stop(self, timeout: float = 5.0):
        """
        Stop the background thread.

        Args:
            timeout: Maximum time to wait for thread to stop (default: 5.0 seconds)
        """
        if self._thread is None or not self._thread.is_alive():
            return

        self._stop_event.set()
        self._thread.join(timeout=timeout)
        logging.info("EntityCountUpdater: Stopped background thread")
