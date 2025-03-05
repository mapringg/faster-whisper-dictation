#!/bin/bash

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is required but not installed. Please install pip3 and try again."
    exit 1
fi

# Check if virtual environment exists, if not create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install or upgrade dependencies
echo "Installing/upgrading dependencies..."
pip install -r requirements.txt

# Check if .env file exists in home directory
if [ ! -f ~/.env ]; then
    echo "No .env file found in home directory."
    echo "Please create ~/.env and add your ElevenLabs API key:"
    echo "ELEVENLABS_API_KEY=your_api_key_here"
    exit 1
fi

# Check if ELEVENLABS_API_KEY is set in .env
if ! grep -q "ELEVENLABS_API_KEY" ~/.env; then
    echo "ELEVENLABS_API_KEY not found in ~/.env"
    echo "Please add your ElevenLabs API key to ~/.env:"
    echo "ELEVENLABS_API_KEY=your_api_key_here"
    exit 1
fi

# Run the dictation app
echo "Starting ElevenLabs Dictation..."
python dictation.py "$@"
