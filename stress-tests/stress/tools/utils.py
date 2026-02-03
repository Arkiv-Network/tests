import logging
import os
import socket

from eth_account import Account
from eth_account.signers.local import LocalAccount
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs


def build_account_path(user_index: int) -> str:
    """
    Build account path from instance name and user index.

    The instance name follows the template: arkiv-loadtest-d2-4-worker-{region}-{timestamp}-{i}
    The instance index is extracted from the last part of the instance name.
    The final account path uses both instance index and user index.

    Args:
        user_index: Locust user index (0-based)

    Returns:
        Account path in format: m/44'/60'/{instance_index}'/0/{user_index}

    Raises:
        ValueError: If instance index cannot be extracted from instance name
    """
    instance_index = int(os.getenv("INSTANCE_INDEX", "-1"))
    if instance_index != -1:
        return f"m/44'/60'/{instance_index}'/0/{user_index}"


    instance_name = socket.gethostname()

    if not instance_name.startswith("arkiv-loadtest"):
        logging.warning(
            "Hostname '%s' does not match expected 'arkiv-loadtest' pattern. "
            "Defaulting instance index to 0.",
            instance_name,
        )
        instance_index = 0
    else:
        try:
            parts = instance_name.split("-")
            instance_index = int(parts[-1])
        except (ValueError, IndexError):
            logging.error(
                "Cannot extract index from instance name '%s'.", instance_name
            )
            raise ValueError(
                f"Cannot extract index from instance name: {instance_name}"
            ) from None


def launch_image(image_to_run: str):
    port = 8545
    golem_base = (
        DockerContainer(image_to_run)
        .with_bind_ports(port, port)
        .with_command(
            [
                "--dev",
                "--http",
                "--http.api",
                "eth,web3,net,debug,golembase",
                "--verbosity",
                "5",
                "--http.addr",
                "0.0.0.0",
                "--http.port",
                str(port),
                "--http.corsdomain",
                "*",
                "--http.vhosts",
                "*",
                "--ws",
                "--ws.addr",
                "0.0.0.0",
                "--ws.port",
                str(port),
            ]
        )
    )
    golem_base.start()
    wait_for_logs(golem_base, "HTTP server started")
    return golem_base

# for instance_index in range(50):
#     for user_index in range(50):
#         path = f"m/44'/60'/{instance_index}'/0/{user_index}"
#         Account.enable_unaudited_hdwallet_features()
#         account: LocalAccount = Account.from_mnemonic(
#             "parent picture garment parrot churn record stadium pill rocket craft fish fiscal clip virus view diary replace wealth extra kitten door enforce piece nut", account_path=path
#         )
#         print("Account:", account.address)
