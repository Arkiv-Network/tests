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
LOCUST_FILE="$SCRIPT_DIR/../$LOCUST_FILE"

sed -i "s|ENV_FILE_PLACEHOLDER|$ENV_FILE|g" /tmp/locust-arkiv.service
sed -i "s|WORKING_DIRECTORY_PLACEHOLDER|$WORKING_DIRECTORY|g" /tmp/locust-arkiv.service
sed -i "s|LOCUST_FILE_PLACEHOLDER|$LOCUST_FILE|g" /tmp/locust-arkiv.service

sudo mv /tmp/locust-arkiv.service /etc/systemd/system/locust-arkiv.service
echo "Locust master systemd service created."

