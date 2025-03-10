#!/bin/bash

# Source .env file from home directory if it exists
if [ -f "$HOME/.env" ]; then
  source "$HOME/.env"
fi

# Make sure GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
  echo "Error: GROQ_API_KEY environment variable is not set"
  echo "Please set it in $HOME/.env file with: GROQ_API_KEY=your_api_key_here"
  exit 1
fi

# Activate virtual environment
source "$(dirname "$0")/venv/bin/activate"

# Run the dictation tool
python "$(dirname "$0")/dictation.py"