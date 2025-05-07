from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import base64
import json
import time
import shutil
from datetime import datetime
import tempfile
import asyncio
from typing import Dict, List

# Import your existing utility functions
from audio_utils import transcribe_audio, text_to_speech, load_tts_model
from llm_utils import get_llm_response
from embedding import load_rag_retriver, get_context_from_rag

# Import model libraries
import whisper

app = FastAPI(title="EmpathAI Voice Chatbot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create temporary directory for audio files
TEMP_DIR = os.path.join(os.getcwd(), "temp_api_recordings")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Load models on startup
tts_model = None
rag_retriever = None
whisper_model = None

# Store active sessions
active_connections: Dict[str, WebSocket] = {}
sessions: Dict[str, List] = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if client_id not in sessions:
            sessions[client_id] = []

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    global tts_model, rag_retriever, whisper_model
    print("Loading models...")
    tts_model = load_tts_model()
    rag_retriever = load_rag_retriver()
    whisper_model = whisper.load_model("base")


@app.on_event("shutdown")
async def shutdown_event():
    # Clean up temp files
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)


@app.get("/")
async def root():
    return {"message": "EmpathAI Voice Chatbot API is running"}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive()

            # Check if the message contains text or binary data
            if "text" in data:
                # Handle text message (commands, text input)
                message = json.loads(data["text"])
                await process_text_message(client_id, message)
            elif "bytes" in data:
                # Handle binary data (audio)
                await process_audio_message(client_id, data["bytes"])
            else:
                await manager.send_message(
                    client_id, {"type": "error", "message": "Unsupported message format"}
                )
    except WebSocketDisconnect:
        manager.disconnect(client_id)


async def process_text_message(client_id: str, message: dict):
    """Process text messages from client with streaming TTS responses"""
    if "type" not in message:
        await manager.send_message(client_id, {"type": "error", "message": "Missing message type"})
        return

    msg_type = message["type"]

    if msg_type == "text_input":
        # Process text input directly with LLM
        if "text" not in message:
            await manager.send_message(
                client_id, {"type": "error", "message": "Missing text content"}
            )
            return

        text = message["text"]
        use_rag = message.get("use_rag", True)

        # Add user message to session history
        sessions[client_id].append({"role": "user", "content": text})

        # Notify client that processing has started
        await manager.send_message(client_id, {"type": "status", "status": "processing"})

        # Get RAG context if enabled
        context = None
        if use_rag:
            context = get_context_from_rag(rag_retriever, text)

        # Get LLM response
        start_time = time.time()
        ai_response = get_llm_response(text, context=context)
        response_time = time.time() - start_time

        # Add assistant message to session history
        sessions[client_id].append({"role": "assistant", "content": ai_response})

        # Send complete text response first
        await manager.send_message(
            client_id,
            {"type": "text_response", "text": ai_response, "processing_time": response_time},
        )

        # Split the response into chunks by punctuation marks
        # We use a regex pattern to split on punctuation while keeping the punctuation marks
        import re

        # Split on period, exclamation mark, or question mark followed by space or end of string
        chunks = re.split(r"([.!?](?:\s|$))", ai_response)

        # Re-join the punctuation with the preceding text
        text_chunks = []
        i = 0
        while i < len(chunks) - 1:
            if i + 1 < len(chunks) and chunks[i + 1].strip() in [".", "!", "?"]:
                text_chunks.append(chunks[i] + chunks[i + 1])
                i += 2
            else:
                text_chunks.append(chunks[i])
                i += 1

        # Add any remaining chunk
        if i < len(chunks) and chunks[i].strip():
            text_chunks.append(chunks[i])

        # Filter out empty chunks
        text_chunks = [chunk for chunk in text_chunks if chunk.strip()]

        # Process each chunk
        for idx, chunk in enumerate(text_chunks):
            if not chunk.strip():
                continue

            # Generate TTS audio for this chunk
            tts_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            tts_file_path = os.path.join(TEMP_DIR, f"{client_id}_{tts_timestamp}_chunk{idx}.wav")

            try:
                # Generate TTS for the chunk
                tts_audio_path = text_to_speech(tts_model, chunk, tts_file_path)

                if tts_audio_path and os.path.exists(tts_audio_path):
                    # Read the audio file and send it as base64
                    with open(tts_audio_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

                        # Send audio chunk response
                        await manager.send_message(
                            client_id,
                            {
                                "type": "audio_response_chunk",
                                "text": chunk,
                                "audio": audio_base64,
                                "format": "wav",
                                "chunk_index": idx,
                                "end": idx == len(text_chunks) - 1,
                            },
                        )

                    # Clean up the audio file
                    try:
                        os.remove(tts_audio_path)
                    except:
                        pass

                    # Add a small delay between chunks to make it feel more natural
                    await asyncio.sleep(0.2)

                else:
                    await manager.send_message(
                        client_id,
                        {"type": "error", "message": f"Failed to generate audio for chunk {idx}"},
                    )
            except Exception as e:
                await manager.send_message(
                    client_id, {"type": "error", "message": f"TTS error on chunk {idx}: {str(e)}"}
                )

    elif msg_type == "clear_session":
        # Clear session history
        sessions[client_id] = []
        await manager.send_message(client_id, {"type": "status", "status": "session_cleared"})

    else:
        await manager.send_message(
            client_id, {"type": "error", "message": f"Unknown message type: {msg_type}"}
        )


async def process_audio_message(client_id: str, audio_bytes):
    """Process audio messages from client with streaming TTS responses"""
    try:
        # Create a temporary file to store the received audio
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_audio_path = os.path.join(TEMP_DIR, f"{client_id}_{timestamp}_input.wav")

        # Save the audio bytes to a file
        with open(temp_audio_path, "wb") as temp_file:
            temp_file.write(audio_bytes)

        # Notify client that processing has started
        await manager.send_message(client_id, {"type": "status", "status": "processing"})

        # Transcribe the audio
        transcription = transcribe_audio(whisper_model, temp_audio_path)
        if not transcription:
            await manager.send_message(
                client_id, {"type": "error", "message": "Failed to transcribe audio"}
            )
            return

        # Send transcription to client
        await manager.send_message(client_id, {"type": "transcription", "text": transcription})

        # Add user message to session history
        sessions[client_id].append({"role": "user", "content": transcription})

        # Get RAG context
        context = get_context_from_rag(rag_retriever, transcription)

        # Get LLM response
        ai_response = get_llm_response(transcription, context=context)

        # Add assistant message to session history
        sessions[client_id].append({"role": "assistant", "content": ai_response})

        # Send complete text response
        await manager.send_message(client_id, {"type": "text_response", "text": ai_response})

        # Clean up the input audio file
        try:
            os.remove(temp_audio_path)
        except:
            pass

        # Split the response into chunks by punctuation marks
        import re

        # Split on period, exclamation mark, or question mark followed by space or end of string
        chunks = re.split(r"([.!?](?:\s|$))", ai_response)

        # Re-join the punctuation with the preceding text
        text_chunks = []
        i = 0
        while i < len(chunks) - 1:
            if i + 1 < len(chunks) and chunks[i + 1].strip() in [".", "!", "?"]:
                text_chunks.append(chunks[i] + chunks[i + 1])
                i += 2
            else:
                text_chunks.append(chunks[i])
                i += 1

        # Add any remaining chunk
        if i < len(chunks) and chunks[i].strip():
            text_chunks.append(chunks[i])

        # Filter out empty chunks
        text_chunks = [chunk for chunk in text_chunks if chunk.strip()]

        # Process each chunk
        for idx, chunk in enumerate(text_chunks):
            if not chunk.strip():
                continue

            # Generate TTS audio for this chunk
            tts_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            tts_file_path = os.path.join(TEMP_DIR, f"{client_id}_{tts_timestamp}_chunk{idx}.wav")

            try:
                # Generate TTS for the chunk
                tts_audio_path = text_to_speech(tts_model, chunk, tts_file_path)

                if tts_audio_path and os.path.exists(tts_audio_path):
                    # Read the audio file and send it as base64
                    with open(tts_audio_path, "rb") as audio_file:
                        audio_bytes = audio_file.read()
                        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

                        # Send audio chunk response
                        await manager.send_message(
                            client_id,
                            {
                                "type": "audio_response_chunk",
                                "text": chunk,
                                "audio": audio_base64,
                                "format": "wav",
                                "chunk_index": idx,
                                "end": idx == len(text_chunks) - 1,
                            },
                        )

                    # Clean up the audio file
                    try:
                        os.remove(tts_audio_path)
                    except:
                        pass

                    # Add a small delay between chunks to make it feel more natural
                    await asyncio.sleep(0.2)

                else:
                    await manager.send_message(
                        client_id,
                        {"type": "error", "message": f"Failed to generate audio for chunk {idx}"},
                    )
            except Exception as e:
                await manager.send_message(
                    client_id, {"type": "error", "message": f"TTS error on chunk {idx}: {str(e)}"}
                )
    except Exception as e:
        await manager.send_message(
            client_id, {"type": "error", "message": f"Error processing audio: {str(e)}"}
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_v2:app", host="0.0.0.0", port=8000, reload=True)
