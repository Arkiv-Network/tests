import logging
import logging.config
import time

from arkiv import Arkiv
from arkiv.account import NamedAccount
from arkiv.types import QueryOptions, KEY
from eth_account.signers.local import LocalAccount
from locust import task, between, events, FastHttpUser
from web3 import Web3
import web3
from eth_account import Account
import config
from golem_base_sdk.utils import rlp_encode_transaction, GolemBaseTransaction
from golem_base_sdk.types import GolemBaseCreate, Annotation, GolemBaseDelete, GenericBytes

# JSON data as one-line Python string
simple_payload = b'Hello Golem DB Workshop!'
Account.enable_unaudited_hdwallet_features()
id_iterator = None

logging.info(f"Using mnemonic: {config.mnemonic}, users: {config.users}")

explorer_container = None
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    logging.info(f"A new test is starting with nr of users {environment.runner.target_user_count}")
    global id_iterator
    id_iterator = (i+1 for i in range(environment.runner.target_user_count))

    
@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    pass

class L3ExplorerUser(FastHttpUser):
    wait_time = between(2, 6)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = 0
        
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

    #@task
    def explore_blocks(self):
        response = self.client.get(f"/api/v2/blocks?type=block")
        if response.ok:
            blocks = response.json().get('items', [])
            logging.info(f"Blocks: {len(blocks)}")
        else:
            logging.warning(f"Failed to retrieve blocks: {response.content}, response to: {response.request.get_full_url()}")

        # get latest block
        if len(blocks) > 0:
            latest_block = blocks[-1]['height']
            logging.info(f"Retrieving latest block {latest_block}")
            response = self.client.get(f"/api/v2/blocks/{latest_block}", name="/api/v2/blocks/{block_number}")
            if response.ok:
                block = response.json()
                logging.info(f"Latest block {latest_block}: {block}")
            else:
                logging.warning(f"Failed to retrieve block {latest_block}: {response.content}, response to: {response.request.get_full_url()}")
        else:
            logging.warning("No blocks found")

        # get transactions for the block
        response = self.client.get(f"/api/v2/blocks/{latest_block}/transactions", name="/api/v2/blocks/{block_number}/transactions")
        if response.ok:
            transactions = response.json()
            logging.info(f"Transactions for block {latest_block}: {transactions}")
        else:
            logging.warning(f"Failed to retrieve transactions for block {latest_block}: {response.content}, response to: {response.request.get_full_url()}")
        
        # get latest transaction
        latest_transaction = transactions[-1]['hash']
        response = self.client.get(f"/api/v2/transactions/{latest_transaction}", name="/api/v2/transactions/{transaction_hash}")
        if response.ok:
            transaction = response.json()
            logging.info(f"Latest transaction {latest_transaction}: {transaction}")
        else:
            logging.warning(f"Failed to retrieve transaction {latest_transaction}: {response.content}, response to: {response.request.get_full_url()}")

    @task
    def explore_address(self):
        account: LocalAccount = Account.from_mnemonic(config.mnemonic, account_path=f"m/44'/60'/0'/0/{self.id}")
        logging.info(f"Account: {account.address}")
        response = self.client.get(f"/api/v2/addresses/{account.address}", name="/api/v2/addresses/{address}")
        if response.ok:
            address_data = response.json()
            logging.info(f"Address {account.address}: {address_data}")
            
            # get transactions for the address
            response = self.client.get(f"/api/v2/addresses/{account.address}/transactions", name="/api/v2/addresses/{address}/transactions")
            if response.ok:
                transactions = response.json().get('items', [])
                logging.info(f"Transactions for address {account.address}: {transactions}")
            else:
                logging.warning(f"Failed to retrieve transactions for address {account.address}: {response.content}, response to: {response.request.get_full_url()}")

            if len(transactions) > 0:
                latest_transaction = transactions[-1]['hash']
                response = self.client.get(f"/api/v2/transactions/{latest_transaction}", name="/api/v2/transactions/{transaction_hash}")
                if response.ok:
                    transaction = response.json()
                    logging.info(f"Latest transaction {latest_transaction}: {transaction}")
                else:
                    logging.warning(f"Failed to retrieve transaction {latest_transaction}: {response.content}, response to: {response.request.get_full_url()}")

            # get entities for the address
            response = self.client.get(f"/arkiv-indexer/api/v1/operations?operation=CREATE&page_size=50&sender={str(account.address)}", name="/arkiv-indexer/api/v1/operations?operation=CREATE&page_size=50&sender={address}")
            if response.ok:
                operations = response.json().get('items', [])
                logging.info(f"Operations for address {account.address}: {operations}")
            else:
                logging.warning(f"Failed to retrieve operations for address {account.address}: {response.content}, response to: {response.request.get_full_url()}")

            if len(operations) > 0:
                latest_entity = operations[-1]['entity_key']
                response = self.client.get(f"/arkiv-indexer/api/v1/entity/{latest_entity}", name="/arkiv-indexer/api/v1/entity/{operation_id}")
                if response.ok:
                    entity = response.json()
                    logging.info(f"Latest entity {latest_entity}: {entity}")
                else:
                    logging.warning(f"Failed to retrieve entity {latest_entity}: {response.content}, response to: {response.request.get_full_url()}")
        else:
            logging.warning(f"Failed to retrieve address {account.address}: {response.content}, response to: {response.request.get_full_url()}")


            
            