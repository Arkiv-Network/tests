#!/bin/bash
# Install Poetry using official installer

echo "Installing Poetry..."

curl -sSL https://install.python-poetry.org | python3 -

# Add poetry to PATH in bashrc
if ! grep -q '\.local/bin' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

export PATH="$HOME/.local/bin:$PATH"

echo "Poetry installed."

