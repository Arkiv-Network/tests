import logging
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import stress module
# This file is at: stress-tests/stress/explorer/locustfile.py
# We need to add stress-tests/ to the path
file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # Go up from explorer/ to stress/ to stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from eth_account.signers.local import LocalAccount
from locust import task, between
from eth_account import Account

import stress.tools.config as config
from stress.tools.utils import build_account_path
from stress.tools.base_user import BaseUser

Account.enable_unaudited_hdwallet_features()

logging.info(f"Using mnemonic: {config.mnemonic}, users: {config.users}")



class L3ExplorerUser(BaseUser):
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
        account_path = build_account_path(self.id)
        account: LocalAccount = Account.from_mnemonic(
            config.mnemonic, account_path=account_path
        )
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


            
            