# Locust Master Service Setup for Arkiv

Use the automation scripts in this directory to provision and manage the Locust master systemd service.

## Prerequisites

1. Install Poetry:

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. Clone this repository to a directory accessible by the service user (for example `/root/locus-master/loadtest-yagna`) and change into it.

3. Provide the required configuration:
   - Populate `stress-l3/master/master-env.sh` with deployment-specific values (e.g. `LOCUST_FILE`, ports, environment file locations).
   - Ensure `.env-public` exists at the `stress-l3` root with the Locust environment variables referenced by the systemd unit.

## Setup

Run the automated setup script; it installs dependencies, renders the service unit, and reloads systemd:

```bash
cd /root/locus-master/loadtest-yagna/tests/stress-l3/master
./setup-master-locust.sh
```

Key actions performed by `setup-master-locust.sh`:
- Installs project dependencies with Poetry.
- Generates `/etc/systemd/system/locust-arkiv.service` from `locust-arkiv.service.template`, filling in paths from `master-env.sh`.
- Reloads systemd and restarts the service if it was already running.

## Managing the Service

- Start or restart the master service:

  ```bash
  ./start-master-locust.sh
  ```

- Check status or logs:
  - `sudo systemctl status locust-arkiv.service`
  - `sudo journalctl -u locust-arkiv.service -f`

- Stop the service:

  ```bash
  sudo systemctl stop locust-arkiv.service
  ```

## Notes

- The systemd unit exposes Locust on all interfaces (`0.0.0.0`) and restarts automatically on failure.
- Worker setup scripts live in https://github.com/golemfactory/gitops.

