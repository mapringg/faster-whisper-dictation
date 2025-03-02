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

# Run the dictation tool
echo "$(dirname "$0")"
source venv/bin/activate
python dictation.py
