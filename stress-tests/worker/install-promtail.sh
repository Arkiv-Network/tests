#!/bin/bash
# Install Promtail binary

echo "Installing Promtail..."
wget https://github.com/grafana/loki/releases/download/v2.9.1/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip
sudo mv promtail-linux-amd64 /usr/local/bin/promtail
echo "Promtail installed."

