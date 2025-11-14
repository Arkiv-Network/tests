#!/bin/bash
# Setup Promtail config and service

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create promtail config
echo "Creating promtail config..."
sudo mkdir -p /etc/promtail
cp "$SCRIPT_DIR/promtail-config.yml" /tmp/promtail-config.yml
# Replace hostname variable with actual hostname
sed -i "s/\$(hostname)/$(hostname)/g" /tmp/promtail-config.yml
sudo mv /tmp/promtail-config.yml /etc/promtail/config.yml
echo "Promtail config created."

# Create promtail service
echo "Creating promtail systemd service..."
sudo cp "$SCRIPT_DIR/promtail.service" /etc/systemd/system/promtail.service
echo "Promtail systemd service created."

# Start promtail service
echo "Starting promtail service..."
sudo systemctl daemon-reload
sudo systemctl enable promtail
sudo systemctl start promtail
echo "Promtail service started."

