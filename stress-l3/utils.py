from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

def launch_image(image_to_run: str):
    port = 8545
    golem_base = DockerContainer(image_to_run) \
        .with_bind_ports(port, port) \
        .with_command(["--dev",
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
                str(port)])
    golem_base.start()
    wait_for_logs(golem_base, "HTTP server started")
    return golem_base
