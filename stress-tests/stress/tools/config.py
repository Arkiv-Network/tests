from environs import Env

env = Env()
env.read_env()

users = env.int("LOCUST_USERS", default=1)
log_level = env.str("LOG_LEVEL", default="INFO")
host = env.str("LOCUST_HOST", default="http://localhost:8545")
mnemonic = env.str("MNEMONIC", default="")
chain_id = env.int("CHAIN_ID", default=1337)
chain_env = env.str("CHAIN_ENV", default="local")  # local or testnet or mainnet
l3_bridge_address = env.str(
    "L3_BRIDGE_ADDRESS", default="0x4D090d64CeC1631E90dCc220487582a9319f6596"
)
image_to_run = env.str(
    "IMAGE_TO_RUN", default=""
)  # only for local env - it tells which image to run, empty means nothing to run (user will run it manually e.g. from sources)
fresh_container_for_each_test = env.bool(
    "FRESH_CONTAINER_FOR_EACH_TEST", default=False
)  # it will work for single user only
timeout_tx_to_be_mined = env.int("TIMEOUT_TX_TO_BE_MINED", default=60)
founder_key = env.str("FOUNDER_KEY", default="")
