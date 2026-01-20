import logging
import logging.config
import time
import itertools
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import stress module
# This file is at: stress-tests/stress/l3/locustfile_raw_rpc_json.py
# We need to add stress-tests/ to the path
file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # Go up from l3/ to stress/ to stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from eth_account.signers.local import LocalAccount
from locust import FastHttpUser, task, between, events
from web3 import Web3
import web3
from eth_account import Account
from golem_base_sdk.utils import rlp_encode_transaction, GolemBaseTransaction
from golem_base_sdk.types import (
    GolemBaseCreate,
    Annotation,
    GolemBaseDelete,
    GenericBytes,
)

import stress.tools.config as config
from stress.tools.utils import launch_image, build_account_path

# JSON data as one-line Python string
# offer_json_data = b'{"offer":{"constraints":"(&\\n  (golem.srv.comp.expiration>1653219330118)\\n  (golem.node.debug.subnet=0987)\\n)","offerId":"7f2f81f213dd48549e080d774dbf1bc2-076a8cbae6546e5f158e5b4d3a869f25a8e2ae426279a691e7ee45315efa3d83","properties":{"golem":{"activity":{"caps":{"transfer":{"protocol":["http","https","gftp"]}}},"com":{"payment":{"debit-notes":{"accept-timeout?":240},"platform":{"erc20-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"},"zksync-rinkeby-tglm":{"address":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23"}}},"pricing":{"model":{"@tag":"linear","linear":{"coeffs":[0.0002777777777777778,0.001388888888888889,0.0]}}},"scheme":"payu","usage":{"vector":["golem.usage.duration_sec","golem.usage.cpu_sec"]}},"inf":{"cpu":{"architecture":"x86_64","capabilities":["sse3","pclmulqdq","dtes64","monitor","dscpl","vmx","eist","tm2","ssse3","fma","cmpxchg16b","pdcm","pcid","sse41","sse42","x2apic","movbe","popcnt","tsc_deadline","aesni","xsave","osxsave","avx","f16c","rdrand","fpu","vme","de","pse","tsc","msr","pae","mce","cx8","apic","sep","mtrr","pge","mca","cmov","pat","pse36","clfsh","ds","acpi","mmx","fxsr","sse","sse2","ss","htt","tm","pbe","fsgsbase","adjust_msr","smep","rep_movsb_stosb","invpcid","deprecate_fpu_cs_ds","mpx","rdseed","rdseed","adx","smap","clflushopt","processor_trace","sgx","sgx_lc"],"cores":6,"model":"Stepping 10 Family 6 Model 158","threads":11,"vendor":"GenuineIntel"},"mem":{"gib":28.0},"storage":{"gib":57.276745605468754}},"node":{"debug":{"subnet":"0987"},"id":{"name":"nieznanysprawiciel-laptop-Provider-2"}},"runtime":{"capabilities":["vpn"],"name":"vm","version":"0.2.10"},"srv":{"caps":{"multi-activity":true}}}},"providerId":"0x86a269498fb5270f20bdc6fdcf6039122b0d3b23","timestamp":"2022-05-22T11:35:49.290821396Z"},"proposedSignature":"NoSignature","state":"Pending","timestamp":"2022-05-22T11:35:49.290821396Z","validTo":"2022-05-22T12:35:49.280650Z"}'
offer_json_data = b"Hello Golem DB Workshop!"
Account.enable_unaudited_hdwallet_features()
id_iterator = None

founder_account: LocalAccount | None = None

logging.info(f"Using mnemonic: {config.mnemonic}, users: {config.users}")


def prepare_tx_data(account: LocalAccount, nonce: int) -> dict:
    encoded_golem_tx = rlp_encode_transaction(
        GolemBaseTransaction(
            creates=[
                GolemBaseCreate(
                    data=offer_json_data,
                    ttl=2592000,  # 20 minutes
                    string_annotations=[
                        Annotation(key="GolemBaseMarketplace", value="Offer")
                    ],
                    numeric_annotations=[],
                )
            ],
        )
    )
    return {
        "chainId": config.chain_id,
        "from": account.address,
        "to": Web3.to_checksum_address("0x0000000000000000000000000000000060138453"),
        "value": Web3.to_wei(0, "ether"),
        "data": encoded_golem_tx,
        "nonce": nonce,
        "gas": 200000,
        "maxFeePerGas": 2000000,
        "maxPriorityFeePerGas": 1000000,
    }


def topup_local_account(account: LocalAccount, w3: Web3):
    accounts = w3.eth.accounts
    tx_hash = w3.eth.send_transaction(
        {
            "from": accounts[0],
            "to": account.address,
            "value": Web3.to_wei(10, "ether"),
        }
    )
    logging.info(f"Transaction hash: {tx_hash}")


gb_container = None


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logging.info(
        f"A new test is starting with nr of users {environment.runner.target_user_count}"
    )
    global id_iterator
    id_iterator = itertools.count(0)

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
    if (
        config.chain_env == "local"
        and config.image_to_run
        and not config.fresh_container_for_each_test
    ):
        global gb_container
        if gb_container:
            gb_container.stop()
        logging.info(f"A new test is ending and the container is stopped")


class GolemBaseUser(FastHttpUser):
    wait_time = between(1, 3)

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
        self.id = next(id_iterator)
        logging.info(f"User started with id: {self.id}")

    @task
    def store_offer(self):
        gb_container = None
        try:
            if (
                config.chain_env == "local"
                and config.image_to_run
                and config.fresh_container_for_each_test
            ):
                gb_container = launch_image(config.image_to_run)

            account_path = build_account_path(self.id)
            account: LocalAccount = Account.from_mnemonic(
                config.mnemonic, account_path=account_path
            )
            logging.info(f"Account: {account.address}")

            logging.info(f"Connecting to Golem Base")
            logging.info(f"Base URL: {self.client.base_url}")
            w3 = Web3(
                web3.HTTPProvider(
                    endpoint_uri=self.client.base_url, session=self.client
                )
            )

            if w3.is_connected():
                logging.info("Connected to Golem Base")
            else:
                logging.error("Not connected to Golem Base")
                raise Exception("Not connected to Golem Base")

            balance = w3.eth.get_balance(account.address)
            logging.info(f"Balance: {balance}")
            if balance == 0:
                if config.chain_env == "local":
                    topup_local_account(account, w3)
                    logging.error("Not enough balance to send transaction")
                    time.sleep(0.5)
                else:
                    logging.error("Not enough balance to send transaction")
                    raise Exception("Not enough balance to send transaction")

            nonce = w3.eth.get_transaction_count(account.address)
            logging.info(f"Nonce: {nonce}")

            logging.info(f"Signing transaction with key: {account.key}")
            signed_tx = account.sign_transaction(prepare_tx_data(account, nonce))
            logging.debug(f"Transaction: {signed_tx}")

            response = self.client.post(
                self.client.base_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_sendRawTransaction",
                    "params": [signed_tx.raw_transaction.to_0x_hex()],
                    "id": 1,
                },
                name="eth_sendRawTransaction",
            )
            if response.status_code != 200:
                logging.error(f"Failed to send transaction: {response.json()}")
                raise Exception(f"Failed to send transaction: {response.json()}")
            logging.info(
                f"Transaction sent of user {account.address}: {response.json()}"
            )
            tx_hash = response.json().get("result", None)
            if not tx_hash:
                logging.error(f"Failed to get transaction hash: {response.json()}")
                raise Exception(f"Failed to get transaction hash: {response.json()}")

            # wair for transaaction to be mined and for the receipt to be available
            timeout = config.timeout_tx_to_be_mined
            start_time = time.time()
            while True:
                response = self.client.post(
                    self.client.base_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionByHash",
                        "params": [tx_hash],
                        "id": 1,
                    },
                    name="eth_getTransactionByHash",
                )
                logging.debug(f"Transaction: {response.json()}")

                response = self.client.post(
                    self.client.base_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionReceipt",
                        "params": [tx_hash],
                        "id": 1,
                    },
                    name="eth_getTransactionReceipt",
                )
                logging.debug(f"Transaction receipt: {response.json()}")
                if response.ok:
                    logging.debug(f"Transaction receipt result: {response.json()}")
                    receipt = response.json().get("result", None)
                    if receipt:
                        logging.info(
                            f"Transaction of user {account.address} mined: {receipt}"
                        )
                        break
                    else:
                        logging.info(f"Transaction {tx_hash} not found yet")
                if timeout and time.time() - start_time > timeout:
                    logging.error(
                        f"Transaction {tx_hash} not found after {timeout} seconds"
                    )
                    raise Exception(
                        f"Transaction {tx_hash} not found after {timeout} seconds"
                    )
                time.sleep(0.2)
        except Exception as e:
            logging.error(f"Error: {e}", exc_info=True)
            raise
        finally:
            if gb_container:
                gb_container.stop()

    # @task
    def retrieve_offers(self):
        response = self.client.post(
            self.client.base_url,
            json={
                "jsonrpc": "2.0",
                "method": "golembase_queryEntities",
                "params": ['GolemBaseMarketplace="Offer"'],
                "id": 1,
            },
            name="golembase_getEntityCount",
        )

        if response.ok:
            logging.info(f"Offers: {response.json().get('result', 0)}")
        else:
            logging.warning(
                f"Failed to retrieve offers: {response.content}, response to: {response.request.get_full_url()}"
            )
