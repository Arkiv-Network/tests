#!/bin/bash
# Setup Locust master service

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source master environment configuration
source "$SCRIPT_DIR/master-env.sh"

# Allow command line arguments to override env variables
# Default working directory is the stress-l3 root directory
WORKING_DIRECTORY="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

echo "Setting up Locust master with working directory: $WORKING_DIRECTORY"

# Check if service is already running (before we update the service file)
SERVICE_WAS_RUNNING=false
if systemctl is-active --quiet locust-arkiv.service 2>/dev/null; then
    SERVICE_WAS_RUNNING=true
    echo "Service is currently running."
fi

# Install dependencies
echo "Installing dependencies with Poetry..."
cd "$WORKING_DIRECTORY"
poetry install
echo "Dependencies installed."

# Create locust service file with parameterized working directory
echo "Creating locust master systemd service..."
cp "$SCRIPT_DIR/locust-arkiv.service.template" /tmp/locust-arkiv.service

# Replace placeholders in the service file
ENV_FILE="$SCRIPT_DIR/../.env-public"

sed -i "s|ENV_FILE_PLACEHOLDER|$ENV_FILE|g" /tmp/locust-arkiv.service
sed -i "s|WORKING_DIRECTORY_PLACEHOLDER|$WORKING_DIRECTORY|g" /tmp/locust-arkiv.service
sed -i "s|LOCUST_FILE_PLACEHOLDER|$LOCUST_FILE|g" /tmp/locust-arkiv.service

sudo mv /tmp/locust-arkiv.service /etc/systemd/system/locust-arkiv.service
echo "Locust master systemd service created."

# Always reload daemon after updating service file
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# If service was running before, restart it to pick up changes
if [ "$SERVICE_WAS_RUNNING" = true ]; then
    echo "Restarting service to apply changes..."
    sudo systemctl restart locust-arkiv.service
    echo "Service restarted."
fi

