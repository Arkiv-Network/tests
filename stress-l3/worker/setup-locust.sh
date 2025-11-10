#!/bin/bash
# Setup Locust service

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Default working directory is the stress-l3 root directory
WORKING_DIRECTORY="${3:-$(cd "$SCRIPT_DIR/.." && pwd)}"

# Source master environment configuration for MASTER_HOST and MASTER_PORT
source "$SCRIPT_DIR/../master/master-env.sh"
echo "Setting up Locust with master host: $MASTER_HOST, master port: $MASTER_PORT and working directory: $WORKING_DIRECTORY"

# Create locust service file with parameterized master host and working directory
echo "Creating locust systemd service..."
cp "$SCRIPT_DIR/locust.service.template" /tmp/locust.service

# Replace placeholders in the service file
# .env-public and LOCUST_FILE are in stress-l3 root
ENV_FILE="$SCRIPT_DIR/../.env-public"
LOCUST_FILE="$SCRIPT_DIR/../$LOCUST_FILE"

sed -i "s|ENV_FILE_PLACEHOLDER|$ENV_FILE|g" /tmp/locust.service
sed -i "s|WORKING_DIRECTORY_PLACEHOLDER|$WORKING_DIRECTORY|g" /tmp/locust.service
sed -i "s|LOCUST_FILE_PLACEHOLDER|$LOCUST_FILE|g" /tmp/locust.service
sed -i "s|MASTER_HOST_PLACEHOLDER|$MASTER_HOST|g" /tmp/locust.service
sed -i "s|MASTER_PORT_PLACEHOLDER|$MASTER_PORT|g" /tmp/locust.service

sudo mv /tmp/locust.service /etc/systemd/system/locust.service
echo "Locust systemd service created."

# Start locust service
echo "Starting locust service..."
sudo systemctl daemon-reload
sudo systemctl enable locust
sudo systemctl start locust
echo "Locust service started."

