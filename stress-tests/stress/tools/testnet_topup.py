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
import config

from stress.tools.utils import build_account_path

logging.basicConfig(level=logging.ERROR)
Account.enable_unaudited_hdwallet_features()

golembase_l2_host = "https://l2.hoodi.arkiv.network/rpc"
golembase_l2_chain_id = 393530
golembase_l3_bridge_address = config.l3_bridge_address
deposit_abi = [
    {"type": "constructor", "inputs": [], "stateMutability": "nonpayable"},
    {"type": "receive", "stateMutability": "payable"},
    {
        "type": "function",
        "name": "MESSENGER",
        "inputs": [],
        "outputs": [
            {
                "name": "",
                "type": "address",
                "internalType": "contractCrossDomainMessenger",
            }
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "OTHER_BRIDGE",
        "inputs": [],
        "outputs": [
            {"name": "", "type": "address", "internalType": "contractStandardBridge"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "bridgeERC20",
        "inputs": [
            {"name": "_localToken", "type": "address", "internalType": "address"},
            {"name": "_remoteToken", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "bridgeERC20To",
        "inputs": [
            {"name": "_localToken", "type": "address", "internalType": "address"},
            {"name": "_remoteToken", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "bridgeETH",
        "inputs": [
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "bridgeETHTo",
        "inputs": [
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "depositERC20",
        "inputs": [
            {"name": "_l1Token", "type": "address", "internalType": "address"},
            {"name": "_l2Token", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "depositERC20To",
        "inputs": [
            {"name": "_l1Token", "type": "address", "internalType": "address"},
            {"name": "_l2Token", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "depositETH",
        "inputs": [
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "depositETHTo",
        "inputs": [
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_minGasLimit", "type": "uint32", "internalType": "uint32"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "deposits",
        "inputs": [
            {"name": "", "type": "address", "internalType": "address"},
            {"name": "", "type": "address", "internalType": "address"},
        ],
        "outputs": [{"name": "", "type": "uint256", "internalType": "uint256"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "finalizeBridgeERC20",
        "inputs": [
            {"name": "_localToken", "type": "address", "internalType": "address"},
            {"name": "_remoteToken", "type": "address", "internalType": "address"},
            {"name": "_from", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "finalizeBridgeETH",
        "inputs": [
            {"name": "_from", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "finalizeERC20Withdrawal",
        "inputs": [
            {"name": "_l1Token", "type": "address", "internalType": "address"},
            {"name": "_l2Token", "type": "address", "internalType": "address"},
            {"name": "_from", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "finalizeETHWithdrawal",
        "inputs": [
            {"name": "_from", "type": "address", "internalType": "address"},
            {"name": "_to", "type": "address", "internalType": "address"},
            {"name": "_amount", "type": "uint256", "internalType": "uint256"},
            {"name": "_extraData", "type": "bytes", "internalType": "bytes"},
        ],
        "outputs": [],
        "stateMutability": "payable",
    },
    {
        "type": "function",
        "name": "initialize",
        "inputs": [
            {
                "name": "_messenger",
                "type": "address",
                "internalType": "contractCrossDomainMessenger",
            },
            {
                "name": "_superchainConfig",
                "type": "address",
                "internalType": "contractSuperchainConfig",
            },
            {
                "name": "_systemConfig",
                "type": "address",
                "internalType": "contractSystemConfig",
            },
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
    {
        "type": "function",
        "name": "l2TokenBridge",
        "inputs": [],
        "outputs": [{"name": "", "type": "address", "internalType": "address"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "messenger",
        "inputs": [],
        "outputs": [
            {
                "name": "",
                "type": "address",
                "internalType": "contractCrossDomainMessenger",
            }
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "otherBridge",
        "inputs": [],
        "outputs": [
            {"name": "", "type": "address", "internalType": "contractStandardBridge"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "paused",
        "inputs": [],
        "outputs": [{"name": "", "type": "bool", "internalType": "bool"}],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "superchainConfig",
        "inputs": [],
        "outputs": [
            {"name": "", "type": "address", "internalType": "contractSuperchainConfig"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "systemConfig",
        "inputs": [],
        "outputs": [
            {"name": "", "type": "address", "internalType": "contractSystemConfig"}
        ],
        "stateMutability": "view",
    },
    {
        "type": "function",
        "name": "version",
        "inputs": [],
        "outputs": [{"name": "", "type": "string", "internalType": "string"}],
        "stateMutability": "view",
    },
    {
        "type": "event",
        "name": "ERC20BridgeFinalized",
        "inputs": [
            {
                "name": "localToken",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "remoteToken",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": False,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ERC20BridgeInitiated",
        "inputs": [
            {
                "name": "localToken",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "remoteToken",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": False,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ERC20DepositInitiated",
        "inputs": [
            {
                "name": "l1Token",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "l2Token",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": False,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ERC20WithdrawalFinalized",
        "inputs": [
            {
                "name": "l1Token",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "l2Token",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": False,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ETHBridgeFinalized",
        "inputs": [
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ETHBridgeInitiated",
        "inputs": [
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ETHDepositInitiated",
        "inputs": [
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "ETHWithdrawalFinalized",
        "inputs": [
            {
                "name": "from",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "to",
                "type": "address",
                "indexed": True,
                "internalType": "address",
            },
            {
                "name": "amount",
                "type": "uint256",
                "indexed": False,
                "internalType": "uint256",
            },
            {
                "name": "extraData",
                "type": "bytes",
                "indexed": False,
                "internalType": "bytes",
            },
        ],
        "anonymous": False,
    },
    {
        "type": "event",
        "name": "Initialized",
        "inputs": [
            {
                "name": "version",
                "type": "uint8",
                "indexed": False,
                "internalType": "uint8",
            }
        ],
        "anonymous": False,
    },
]


w3: Web3 = Web3(web3.HTTPProvider(endpoint_uri=golembase_l2_host))
founder_account: LocalAccount = Account.from_key(config.founder_key)

if w3.is_connected():
    logging.info(
        f"Connected to GolemBase.\nFounder account: {founder_account.address}, balance: {w3.eth.get_balance(founder_account.address)}"
    )
    contract = w3.eth.contract(address=golembase_l3_bridge_address, abi=deposit_abi)

    for i in range(config.users):
        account_path = build_account_path(i)
        account = Account.from_mnemonic(config.mnemonic, account_path=account_path)
        logging.error(
            f"Topping up account {i + 1}: {account.address} {account.key.hex()}"
        )
        nonce = w3.eth.get_transaction_count(founder_account.address)

        deposit_tx = contract.functions.bridgeETHTo(
            account.address,
            200000,
            b"",
        ).build_transaction(
            {
                "from": founder_account.address,
                "value": Web3.to_wei(0.01, "ether"),
                "nonce": nonce,
                "gas": 2000000,
                "maxFeePerGas": 2000000000,
                "maxPriorityFeePerGas": 1000000000,
            }
        )
        signed_tx = founder_account.sign_transaction(deposit_tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logging.info(f"Transaction hash: {tx_hash.hex()}")
        w3.eth.wait_for_transaction_receipt(tx_hash)
        logging.info(f"Transaction receipt: {w3.eth.get_transaction_receipt(tx_hash)}")
else:
    logging.error("Not connected to Golem Base")
    raise Exception("Not connected to Golem Base")
