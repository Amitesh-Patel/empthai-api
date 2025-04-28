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

### Environment Variables

Create a `.env` file in the project root with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key
TTS_MODEL_NAME=tts_models/en/vctk/vits # Or another Coqui TTS model
SAMPLE_RATE=24000
TEMP_DIR=./temp_audio_files
```

## Quick Start

1. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. Access the API documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)

3. Test a simple voice interaction:
   - Record an audio question
   - Send it to `/api/voice_chat` endpoint
   - Receive the AI response as audio and text

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

### Python Client Example

```python
import requests
import json
import base64
import time
import sounddevice as sd
import soundfile as sf
import io

BASE_URL = "http://localhost:8000"

# Start a voice chat session
def start_voice_chat(audio_file_path):
    with open(audio_file_path, "rb") as audio_file:
        files = {"audio": ("recording.wav", audio_file, "audio/wav")}
        response = requests.post(
            f"{BASE_URL}/api/stream_voice_chat", 
            files=files
        )
    
    if response.status_code == 200:
        data = response.json()
        return data["session_id"]
    else:
        print(f"Error: {response.status_code}")
        return None

# Get and play audio chunks
def get_and_play_audio_chunks(session_id):
    is_processing = True
    response_text = ""
    
    while is_processing:
        response = requests.get(
            f"{BASE_URL}/api/get_audio_chunks",
            params={"session_id": session_id}
        )
        
        data = response.json()
        chunks = data.get("chunks_data", [])
        
        # Play each audio chunk
        for chunk_b64 in chunks:
            chunk_data = base64.b64decode(chunk_b64)
            audio_data, samplerate = sf.read(io.BytesIO(chunk_data))
            sd.play(audio_data, samplerate)
            sd.wait()
        
        # Update processing status and response text
        is_processing = data.get("is_processing", False)
        response_text = data.get("response_so_far", "")
        print(f"Response so far: {response_text}")
        
        # Wait a bit before checking for more chunks
        if is_processing:
            time.sleep(0.5)
    
    return response_text

# Example usage
session_id = start_voice_chat("my_question.wav")
if session_id:
    final_response = get_and_play_audio_chunks(session_id)
    print(f"Final response: {final_response}")
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