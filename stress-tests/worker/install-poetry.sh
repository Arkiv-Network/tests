#!/bin/bash
# Install Poetry using official installer

echo "Installing Poetry..."

curl -sSL https://install.python-poetry.org | python3 -

# Add poetry to PATH in bashrc
if ! grep -q 'export PATH=.*\.local/bin' /root/.bashrc; then
    echo 'export PATH="/root/.local/bin:$PATH"' >> /root/.bashrc
    echo "Poetry PATH ( /root/.local/bin ) added to /root/.bashrc"
fi

export PATH="/root/.local/bin:$PATH"

echo "Poetry installed."

