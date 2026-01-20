from typing import Any
import json
import logging

from stress.tools.base_user import BaseUser


class JsonRpcUser(BaseUser):
    """JSON-RPC user that wraps requests to extract RPC method names."""

    abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_request_method = self.client.request

        def wrapped_request(*args, **kwargs):
            # Add any extra logic here (before calling the original method)
            call_name = None
            if args[0] == "POST":
                data = kwargs["data"]
                # data bytes into json
                data = json.loads(kwargs["data"].decode("utf-8"))
                rpc_method = data.get("method", None)
                call_name = rpc_method

            response = original_request_method(*args, name=call_name, **kwargs)

            if response.ok:
                logging.debug(f"{call_name} response: {response.json()}")
            else:
                logging.error(f"{call_name} Error response: {response.json()}")
            return response

        self.client.request = wrapped_request
