#!/bin/bash
# Setup Locust service

# Function to normalize paths (resolve to absolute path without ..)
normalize_path() {
    local path="$1"
    if [ -d "$path" ]; then
        echo "$(cd "$path" && pwd)"
    else
        local b=$(basename "$path")
        local p=$(dirname "$path")
        echo "$(cd "$p" && pwd)/$b"
    fi
}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the stress-l3 root directory (parent of worker directory) and normalize it
STRESS_L3_DIR="$(normalize_path "$SCRIPT_DIR/..")"
# Working directory is the stress-l3 root directory
WORKING_DIRECTORY="$STRESS_L3_DIR"


# Source master environment configuration for MASTER_HOST and MASTER_PORT
source "$SCRIPT_DIR/../master/master-env.sh"
echo "Setting up Locust with master host: $MASTER_HOST, master port: $MASTER_PORT and working directory: $WORKING_DIRECTORY"

# Create locust service file with parameterized master host and working directory
echo "Creating locust systemd service..."
cp "$SCRIPT_DIR/locust.service.template" /tmp/locust.service

# Replace placeholders in the service file
# STRESS_L3_DIR is already normalized, so paths built from it are already absolute
ENV_FILE="$STRESS_L3_DIR/.env-public"

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

echo "Checking status of locust master service..."
sudo systemctl status locust.service

