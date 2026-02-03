import itertools
import logging
import logging.config

from locust import FastHttpUser, events

import stress.tools.config as config
from stress.tools.metrics import Metrics

# Global user ID iterator
id_iterator = None


@events.test_start.add_listener
def on_test_start_base_user(environment, **kwargs):
    """Initialize the global ID iterator when test starts."""
    global id_iterator
    id_iterator = itertools.count(20)


class BaseUser(FastHttpUser):
    """
    Base user class that handles common functionality:
    - User ID generation
    - Metrics tracking (current user count)
    - Logging configuration
    """

    abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = 0

        logging.config.dictConfig(
            {
                "version": 1,
                "formatters": {
                    "default": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "default",
                    },
                    "file": {
                        "class": "logging.FileHandler",
                        "formatter": "default",
                        "filename": "locust.log",
                    },
                },
                "root": {"handlers": ["console", "file"], "level": config.log_level},
            }
        )

    def on_start(self):
        global id_iterator
        self.id = next(id_iterator)
        Metrics.get_metrics().current_user_count.inc()
        logging.info(f"User started with id: {self.id}")

    def on_stop(self):
        Metrics.get_metrics().current_user_count.dec()
        logging.info(f"User stopped with id: {self.id}")

