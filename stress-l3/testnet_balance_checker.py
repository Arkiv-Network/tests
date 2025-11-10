import logging

from web3 import Account, Web3
from eth_account.signers.local import LocalAccount
import web3
import config

logging.basicConfig(level=logging.INFO)
Account.enable_unaudited_hdwallet_features()

w3: Web3 = Web3(web3.HTTPProvider(endpoint_uri=config.host))

if w3.is_connected():
    for i in range(config.users):
        account = Account.from_mnemonic(config.mnemonic, account_path=f"m/44'/60'/0'/0/{i+1}")
        balance = w3.eth.get_balance(account.address)
        logging.info(f"Account {i+1}: {account.address} balance: {balance}")
else:
    logging.error("Not connected to Golem Base")
    raise Exception("Not connected to Golem Base")









