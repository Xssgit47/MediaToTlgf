#!/bin/bash
# Script to set up and run the Telegram Media to Telegraph Bot

# Exit on error
set -e

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run the bot
echo "Starting the bot..."
python src/bot.py
