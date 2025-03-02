# Faster Whisper Dictation with Groq API

This is a modified version of the original Faster Whisper Dictation tool that uses the Groq API for speech transcription instead of local Whisper models.

## Setup

1. Install the required dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Set up your Groq API key in one of the following ways:

   **Option 1:** Set as an environment variable:

   ```
   export GROQ_API_KEY="your_groq_api_key_here"
   ```

   On Windows, use:

   ```
   set GROQ_API_KEY=your_groq_api_key_here
   ```

   **Option 2:** Create a `.env` file in your home directory:

   ```
   # On macOS/Linux
   echo "GROQ_API_KEY=your_groq_api_key_here" > ~/.env

   # On Windows
   echo GROQ_API_KEY=your_groq_api_key_here > %USERPROFILE%\.env
   ```

## Usage

Run the dictation tool:

```
python dictation.py
```

Or use the provided shell script (on macOS/Linux):

```
./run.sh
```

### Command Line Options

- `-m, --model-name`: Specify the Groq model to use (default: "whisper-large-v3-turbo")
- `-k, --key-combo`: Specify the key combination to toggle recording
- `-d, --double-key`: Specify a key for double-tap activation
- `-t, --max-time`: Maximum recording time in seconds (default: 30)
- `-l, --language`: Specify the language for better transcription accuracy

### Default Key Combinations

- Windows: Win+Z
- macOS/Linux: Double-tap Left Alt

## How It Works

1. Press the hotkey to start recording
2. Speak into your microphone
3. Press the hotkey again to stop recording
4. The audio will be transcribed using the Groq API
5. The transcribed text will be typed out at your cursor position

## Differences from Original Version

This version uses the Groq API for transcription instead of running Whisper models locally. This means:

1. You need an internet connection
2. You need a Groq API key
3. Transcription may be faster or slower depending on your internet connection and Groq API response times
4. All other functionality remains the same as the original version

## Troubleshooting

- If you get an error about the GROQ_API_KEY not being set, make sure you've set the environment variable correctly or added it to your `~/.env` file
- If transcription fails, check your internet connection and Groq API key validity
- Make sure your microphone permissions are properly set up for your operating system
