from typing import Any
from locust import FastHttpUser
import json
import logging

class JsonRpcUser(FastHttpUser):
    abstract = True
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_request_method = self.client.request
        def wrapped_request(*args, **kwargs):
            # Add any extra logic here (before calling the original method)
            call_name = None
            if args[0] == 'POST':
                data = kwargs['data']
                # data bytes into json
                data = json.loads(kwargs['data'].decode('utf-8'))
                rpc_method = data.get('method', None)
                call_name = rpc_method

            return original_request_method(*args, name=call_name, **kwargs)

        self.client.request = wrapped_request
        