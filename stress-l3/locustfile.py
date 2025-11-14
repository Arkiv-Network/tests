import logging
import logging.config
import itertools
import time
import uuid
import random

from arkiv import Arkiv
from arkiv.account import NamedAccount
from arkiv.types import QueryOptions, KEY
from eth_account.signers.local import LocalAccount
from json_rpc_user import JsonRpcUser
from locust import task, between, events
from web3 import Web3
import web3
from eth_account import Account
import config
from utils import launch_image, build_account_path

# JSON data as one-line Python string
bigger_payload = b'{"offer":{"constraints":"(&\\n  (golem.srv.comp.expiration>1653219330118)\\n  (golem.node.debug.subnet=0987)\\n)","offerId":"7f2f81f213dd48549e080d774dbf1bc2-076a8cbae6546e5f158e5b4d3a869f25a8e2ae426279a691e7ee45315efa3d83","properties":{"golem":{"activity":{"caps":{"transfer":{"protocol":["http","https","gftp"]}}},"com":{"payment":{"debit-notes":{"accept-timeout?":240},"platform":{"erc20-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"},"zksync-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"}}},"pricing":{"model":{"@tag":"linear","linear":{"coeffs":[0.0002777777777777778,0.001388888888888889,0.0]}}},"scheme":"payu","usage":{"vector":["golem.usage.duration_sec","golem.usage.cpu_sec"]}},"inf":{"cpu":{"architecture":"x86_64","capabilities":["sse3","pclmulqdq","dtes64","monitor","dscpl","vmx","eist","tm2","ssse3","fma","cmpxchg16b","pdcm","pcid","sse41","sse42","x2apic","movbe","popcnt","tsc_deadline","aesni","xsave","osxsave","avx","f16c","rdrand","fpu","vme","de","pse","tsc","msr","pae","mce","cx8","apic","sep","mtrr","pge","mca","cmov","pat","pse36","clfsh","ds","acpi","mmx","fxsr","sse","sse2","ss","htt","tm","pbe","fsgsbase","adjust_msr","smep","rep_movsb_stosb","invpcid","deprecate_fpu_cs_ds","mpx","rdseed","rdseed","adx","smap","clflushopt","processor_trace","sgx","sgx_lc"],"cores":6,"model":"Stepping 10 Family 6 Model 158","threads":11,"vendor":"GenuineIntel"},"mem":{"gib":28.0},"storage":{"gib":57.276745605468754}},"node":{"debug":{"subnet":"0987"},"id":{"name":"nieznanysprawiciel-laptop-Provider-2"}},"runtime":{"capabilities":["vpn"],"name":"vm","version":"0.2.10"},"srv":{"caps":{"multi-activity":true}}}},"providerId":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23","timestamp":"2022-05-22T11:35:49.290821396Z"},"proposedSignature":"NoSignature","state":"Pending","timestamp":"2022-05-22T11:35:49.290821396Z","validTo":"2022-05-22T12:35:49.280650Z"}'
simple_payload = b'Hello Golem DB Workshop!'
Account.enable_unaudited_hdwallet_features()
id_iterator = None

founder_account: LocalAccount | None = None


def topup_local_account(account: LocalAccount, w3: Web3):
    accounts = w3.eth.accounts
    tx_hash  = w3.eth.send_transaction({
        "from": accounts[0],
        "to": account.address,
        "value": Web3.to_wei(10, "ether"),
    })
    logging.info(f"Transaction hash: {tx_hash}")


gb_container = None
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logging.info(f"A new test is starting with nr of users {environment.runner.target_user_count}")
    global id_iterator
    id_iterator = itertools.count(0)

    if config.chain_env == "local" and config.image_to_run and not config.fresh_container_for_each_test:
        global gb_container
        gb_container = launch_image(config.image_to_run)
        logging.info(f"A new test is starting and a new container is launched")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    if config.chain_env == "local" and config.image_to_run and not config.fresh_container_for_each_test:
        global gb_container
        if gb_container:
            gb_container.stop()
        logging.info(f"A new test is ending and the container is stopped")

class ArkivL3User(JsonRpcUser):
    wait_time = between(5, 10)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = 0
        self.unique_ids = set()
        self.account: LocalAccount | None = None
        self.w3: Arkiv | None = None
        
        logging.config.dictConfig({
            "version": 1,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default"
                },
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "filename": "locust.log"
                }
            },
            "root": {
                "handlers": ["console", "file"],
                "level": config.log_level
            }
        })
        
    def on_start(self):
        self.id = next(id_iterator)
        logging.info(f"User started with id: {self.id}")
    
    def _initialize_account_and_w3(self):
        """Initialize account and w3 connection if not already initialized."""
        if self.account is None or self.w3 is None:
            account_path = build_account_path(self.id)
            self.account = Account.from_mnemonic(config.mnemonic, account_path=account_path)
            logging.info(f"Account: {self.account.address} (user: {self.id})")
            
            logging.info(f"Connecting to Arkiv L3 (user: {self.id})")
            logging.info(f"Base URL: {self.client.base_url} (user: {self.id})")
            self.w3 = Arkiv(web3.HTTPProvider(endpoint_uri=self.client.base_url, session=self.client), NamedAccount(name=f"LocalSigner", account=self.account))
            
            if not self.w3.is_connected():
                logging.error(f"Not connected to Arkiv L3 (user: {self.id})")
                raise Exception(f"Not connected to Arkiv L3 (user: {self.id})")
            
            logging.info(f"Connected to Arkiv L3 (user: {self.id})")
        
        return self.w3

    @task(2)
    def store_bigger_payload(self):
        gb_container = None
        try:
            if config.chain_env == "local" and config.image_to_run and config.fresh_container_for_each_test:
                gb_container = launch_image(config.image_to_run)
            
            w3 = self._initialize_account_and_w3()

            balance = w3.eth.get_balance(self.account.address)
            logging.info(f"Balance: {balance}")
            if balance == 0:
                if config.chain_env == "local":
                    topup_local_account(self.account, w3)
                    logging.error(f"Not enough balance to send transaction (user: {self.id})")
                    time.sleep(0.5)
                else:
                    logging.error(f"Not enough balance to send transaction (user: {self.id})")
                    raise Exception("Not enough balance to send transaction")
                    
            nonce = w3.eth.get_transaction_count(self.account.address)
            logging.info(f"Nonce: {nonce}")

            w3.arkiv.create_entity(
                payload=bigger_payload, 
                content_type="application/json", 
                attributes={"ArkivEntityType": "StressedEntity"},
                btl=2592000, # 20 minutes
            )
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)
            raise
        finally:
            if gb_container:
                gb_container.stop()

    @task(2)
    def store_small_payload(self):
        # Generate unique ID and store it in the set for use in other tasks
        unique_id = str(uuid.uuid4())
        self.unique_ids.add(unique_id)
        
        # Random query percentage between 1 and 100
        query_percentage = random.randint(1, 100)
        
        w3 = self._initialize_account_and_w3()
        
        nonce = w3.eth.get_transaction_count(self.account.address)
        logging.info(f"Nonce: {nonce}")

        w3.arkiv.create_entity(
            payload=simple_payload, 
            content_type="text/plain", 
            attributes={
                "ArkivEntityType": "StressedEntity",
                "queryPercentage": query_percentage,  # Random percentage 1-100 for querying
                "uniqueId": unique_id  # Unique attribute for single entity query
            },
            btl=2592000, # 20 minutes
        )

    def selective_query(self, percent: int = 50):
        """
        Stress test query that chooses only a selected percent of Entities
        """
        logging.info(f"Selective query with threshold: {percent} (user: {self.id})")
        w3 = self._initialize_account_and_w3()
        
        # Query entities with queryPercentage below threshold
        query = f'ArkivEntityType="StressedEntity" && queryPercentage<{percent}'
        result = w3.arkiv.query_entities(query=query, options=QueryOptions(fields=KEY, max_results_per_page=0))
        
        logging.info(f"Found {len(result.entities)} entities with queryPercentage < {percent} (user: {self.id})")
        logging.debug(f"Result: {result} (user: {self.id})")

    @task(1)
    def selective_query_20Percent(self):
        self.selective_query(20)

    @task(1)
    def selective_query_40Percent(self):
        self.selective_query(40)

    @task(1)
    def selective_query_60Percent(self):
        self.selective_query(60)

    @task(1)
    def selective_query_80Percent(self):
        self.selective_query(80)

    @task(1)
    def selective_query_100Percent(self):
        self.selective_query(100)

    @task(4)
    def retrieve_keys_to_count(self):
        logging.info(f"Retrieving offers")
        w3 = Arkiv(web3.HTTPProvider(endpoint_uri=self.client.base_url, session=self.client))
        result = w3.arkiv.query_entities(query='ArkivEntityType="StressedEntity"', options=QueryOptions(fields=KEY, max_results_per_page=0))

        logging.debug(f"Result: {result} (user: {self.id})")
        #logging.info(f"Keys: {len(result.entities)}")

    
            
            