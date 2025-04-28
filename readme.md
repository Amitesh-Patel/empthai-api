# EmpathAI Voice Chatbot API

EmpathAI is an advanced voice chatbot API that provides seamless speech-to-text and text-to-speech capabilities with intelligent conversational abilities powered by Gemini Pro LLM.

## Features

- **Speech-to-Text**: Fast and accurate transcription using Whisper
- **Text-to-Speech**: High-quality voice generation using Coqui TTS or Kokoro TTS
- **RAG Integration**: Context-aware conversations with document retrieval capabilities
- **Streaming Responses**: Real-time streaming of both text and audio responses
- **Session Management**: Maintain conversation context across multiple interactions

## Table of Contents

- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Directory Structure](#directory-structure)
- [API Documentation](#api-documentation)
  - [Endpoints](#endpoints)
  - [Session Management](#session-management)
- [Example Usage](#example-usage)
- [Contributing](#contributing)

## Installation

### Prerequisites

- Python 3.8 or higher
- [FFmpeg](https://ffmpeg.org/download.html) installed and in PATH
- CUDA-capable GPU (recommended for optimal performance)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/empathAI.git
   cd empathAI
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Install additional TTS libraries:
   - For Coqui TTS:
     ```bash
     pip install TTS
     ```
   - For Kokoro TTS (if available):
     ```bash
     pip install kokoro
     ```

5. RAG Files Setup (Do if you do not download RAG files will be created on thier own and creating them again will take time.)

  Create a rag_files folder:

      ```bash
      mkdir rag_files
      ```
  Download your documents form this [Drive Link](https://drive.google.com/drive/folders/15yBHWiIojsF-QRZ3cy0b5Zqd7E7tDWrE?usp=drive_link):


### Environment Variables

Create a `.env` file in the project root with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key
TTS_MODEL_NAME=tts_models/en/vctk/vits # Or another Coqui TTS model
SAMPLE_RATE=24000
TEMP_DIR=./temp_audio_files
```

## Quick Start

1. Start the FastAPI server using the run_api.py script:
   ```bash
   python run_api.py
   ```
   
   Additional command-line options:
   - `--reload`: Enable auto-reload for development
   - `--debug`: Enable debug mode
   - `--host`: Specify the host address (default: 0.0.0.0)
   - `--port`: Specify the port number (default: 8000)

2. Access the API documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)

3. Use the client.py to interact with the API:
   ```bash
   python client.py
   ```

## Directory Structure

```
EMPTHAI-API/
├── __pycache__/
├── assists/                   # Helper audio files for testing
├── rag_files/                 # RAG document storage
├── temp_api_recordings/       # Temporary audio recordings
├── venv/                      # Virtual environment
├── .env                       # Environment variables
├── .gitignore
├── audio_processor.py         # Audio processing utilities
├── audio_utils.py             # Audio helper functions
├── client.py                  # Client for API interaction
├── config.py                  # Configuration settings
├── embedding.py               # Vector embedding utilities for RAG
├── llm_utils.py               # LLM integration utilities
├── main.py                    # Main FastAPI application
├── readme.md                  # This documentation
├── requirements.txt           # Project dependencies
├── run_api.py                 # API server runner
├── session_utils.py           # Session management utilities
└── test.ipynb                 # Testing notebook
```

## API Documentation

### Endpoints

#### Root
- `GET /` - Test if the API is running

#### Transcription
- `POST /api/transcribe` - Transcribe an audio file to text
  - **Input**: Audio file (WAV, MP3, etc.)
  - **Output**: Transcribed text

#### Text Chat
- `POST /api/chat` - Get an LLM response for a text input
  - **Parameters**:
    - `text`: User input text
    - `session_id` (optional): Session identifier
    - `use_rag` (optional): Whether to use RAG for context (default: `true`)
    - `stream` (optional): Whether to stream the response (default: `true`)
  - **Output**: LLM response text

#### Audio Generation
- `POST /api/audio_response` - Generate audio from text
  - **Parameters**:
    - `text`: Text to convert to speech
    - `session_id` (optional): Session identifier
  - **Output**: Audio file stream

#### Voice Chat
- `POST /api/voice_chat` - Complete voice-to-voice interaction
  - **Parameters**:
    - Audio file
    - `session_id` (optional): Session identifier
    - `use_rag` (optional): Whether to use RAG for context (default: `true`)
  - **Output**: Audio response with transcription and response text headers

#### Streaming Voice Chat
- `POST /api/stream_voice_chat` - Stream voice chat response in chunks
  - **Parameters**:
    - Audio file
    - `session_id` (optional): Session identifier
    - `use_rag` (optional): Whether to use RAG for context (default: `true`)
  - **Output**: Status information and session ID

- `GET /api/get_audio_chunks` - Get audio chunks for a streaming session
  - **Parameters**:
    - `session_id`: Session identifier
  - **Output**: Array of base64-encoded audio chunks

#### Session Management
- `GET /api/session_history` - Get chat history for a session
  - **Parameters**:
    - `session_id`: Session identifier
  - **Output**: Array of messages with roles and content

- `DELETE /api/clear_session` - Clear a session's history
  - **Parameters**:
    - `session_id`: Session identifier
  - **Output**: Status confirmation

- `POST /api/stop_session` - Stop a streaming session
  - **Parameters**:
    - `session_id`: Session identifier
  - **Output**: Status confirmation

### Session Management

Each conversation is tracked with a session ID. If no session ID is provided, a new one will be generated. The session ID is used to:

- Maintain conversation history
- Track generated audio files
- Enable streaming capabilities
- Allow continuous interactions

Session data includes:
- User messages (text and audio paths)
- Assistant responses (text and audio paths)
- Current processing status
- Audio chunk buffer

## Example Usage

### Using client.py

The project includes a Python client (`client.py`) that makes it easy to interact with the API:

```python
from client import EmpathAIClient

# Initialize the client
client = EmpathAIClient()

# Example: Text chat
response = client.chat("Hello, how are you today?")
print(f"AI: {response['response']}")

# Example: Voice chat
result = client.voice_chat("recording.wav")
print(f"Transcription: {result['transcription']}")
print(f"AI Response: {result['response_text']}")
print(f"Audio saved to: {result['audio_file']}")

# Example: Streaming voice chat
client.start_streaming_voice_chat("recording.wav")
print("Streaming started... press Enter to stop")
input()  # Wait for user to press Enter
client.stop_streaming()

# Get chat history
history = client.get_history()
for msg in history["messages"]:
    print(f"{msg['role']}: {msg['content']}")
```

### cURL Example

```bash
# Transcribe audio
curl -X POST "http://localhost:8000/api/transcribe" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@my_question.wav"

# Get text response
curl -X POST "http://localhost:8000/api/chat" \
  -H "accept: application/json" \
  -d '{"text": "Tell me about artificial intelligence", "session_id": "my-session", "use_rag": true}'
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.