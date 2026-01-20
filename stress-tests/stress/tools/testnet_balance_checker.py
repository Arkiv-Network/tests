import logging
import sys
from pathlib import Path

file_dir = Path(__file__).resolve().parent
project_root = file_dir.parent.parent  # Go up from tools/ to stress/ to stress-tests/
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from web3 import Account, Web3
from eth_account.signers.local import LocalAccount
import web3

import stress.tools.config as config
from stress.tools.utils import build_account_path

logging.basicConfig(level=logging.INFO)
Account.enable_unaudited_hdwallet_features()

w3: Web3 = Web3(web3.HTTPProvider(endpoint_uri=config.host))

if w3.is_connected():
    for i in range(config.users):
        account_path = build_account_path(i)
        account = Account.from_mnemonic(config.mnemonic, account_path=account_path)
        balance = w3.eth.get_balance(account.address)
        logging.info(f"Account {i + 1}: {account.address} balance: {balance}")
else:
    logging.error("Not connected to Golem Base")
    raise Exception("Not connected to Golem Base")
