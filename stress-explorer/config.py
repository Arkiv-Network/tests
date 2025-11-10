from environs import Env

env = Env()
env.read_env()

users = env.int("LOCUST_USERS", default=1)
log_level = env.str("LOG_LEVEL", default="INFO")
host = env.str("LOCUST_HOST", default="https://explorer.kaolin.hoodi.arkiv.network")
mnemonic = env.str("MNEMONIC", default="")
image_to_run = env.str("IMAGE_TO_RUN", default="")  # only for local env - it tells which image to run, empty means nothing to run (user will run it manually e.g. from sources)
fresh_container_for_each_test = env.bool("FRESH_CONTAINER_FOR_EACH_TEST", default=False)  # it will work for single user only
