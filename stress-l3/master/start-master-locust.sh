#!/bin/bash
# Start Locust master service

echo "Starting locust master service..."
sudo systemctl daemon-reload
sudo systemctl enable locust-arkiv.service
sudo systemctl start locust-arkiv.service
echo "Locust master service started."

echo "Checking status of locust master service..."
sudo systemctl status locust-arkiv.service

