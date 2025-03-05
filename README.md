# Faster Dictation with ElevenLabs

A simple dictation app powered by ElevenLabs Speech-to-Text API. This app allows you to dictate text anywhere on your computer by using global keyboard shortcuts.

## Features

- Real-time speech-to-text using ElevenLabs' advanced models
- Global keyboard shortcuts for easy recording control
- Automatic text typing after transcription
- Support for multiple languages (English by default)
- Configurable maximum recording time
- Audio feedback for recording start/stop

## Prerequisites

- Python 3.7 or higher
- An ElevenLabs API key (get one at https://elevenlabs.io)
- PyAudio dependencies (see installation section)
- For Linux/macOS: ALSA/PortAudio development files

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/faster-whisper-dictation.git
cd faster-whisper-dictation
```

2. Install system dependencies:

For Ubuntu/Debian:

```bash
sudo apt-get install python3-dev portaudio19-dev
```

For macOS:

```bash
brew install portaudio
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Set up your ElevenLabs API key:
   Create a `.env` file in your home directory:

```bash
echo "ELEVENLABS_API_KEY=your_api_key_here" >> ~/.env
```

## Usage

1. Basic usage:

```bash
python dictation.py
```

2. With custom options:

```bash
python dictation.py -t 60  # Set max recording time to 60 seconds
python dictation.py -l fra  # Use French language
python dictation.py -m scribe_v1_base_base  # Use base model for faster processing
```

### Keyboard Controls

- **Windows**: Press `Win + Z` to start/stop recording
- **macOS/Linux**: Double-tap `Left Alt` to start recording, tap once to stop
  - You can change the key combination using the `-k` or `-d` options

### Command Line Options

- `-m, --model-name`: ElevenLabs model to use (default: scribe_v1_base)
- `-k, --key-combo`: Custom key combination for toggle
- `-d, --double-key`: Custom key for double-tap activation
- `-t, --max-time`: Maximum recording time in seconds (default: 30)
- `-l, --language`: Language code (default: eng)

### Available Models

- `scribe_v1_base`: High-quality transcription (default)
- `scribe_v1_base_base`: Faster, lighter model

### Language Support

The default language is English ('eng'). You can specify other languages using their language codes, for example:

- eng: English (default)
- fra: French
- deu: German
- spa: Spanish
- ita: Italian

## Troubleshooting

1. If you get PortAudio errors:

   - Make sure you have installed the system dependencies
   - Try reinstalling PyAudio: `pip uninstall pyaudio && pip install pyaudio`

2. If the app can't find your API key:
   - Ensure your `.env` file is in your home directory
   - Check that the API key is correctly formatted
   - Try setting it directly in your environment: `export ELEVENLABS_API_KEY=your_key_here`

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ElevenLabs for their excellent Speech-to-Text API
- Sound effects from freesound.org users leviclaassen and MATRIXXX\_
