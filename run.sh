#!/bin/bash

# Make sure GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
  echo "Error: GROQ_API_KEY environment variable is not set"
  echo "Please set it with: export GROQ_API_KEY=your_api_key_here"
  exit 1
fi

# Run the dictation tool
python dictation.py "$@" 