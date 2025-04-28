# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime
import tempfile
import shutil
from pydub import AudioSegment
import io
import uuid
import time
import numpy as np
import soundfile as sf
import base64
import torch


# Import your existing utility functions
from audio_utils import transcribe_audio, text_to_speech, load_tts_model, StreamingTTSManager
from llm_utils import get_llm_response, stream_llm_response
from embedding import load_rag_retriver, get_context_from_rag

app = FastAPI(title="EmpathAI Voice Chatbot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create temporary directory for audio files
TEMP_DIR = os.path.join(os.getcwd(), "temp_api_recordings")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Load models on startup
tts_model = load_tts_model()
rag_retriever = load_rag_retriver()

# Store active streams
active_sessions = {}


class AudioSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.tts_manager = StreamingTTSManager(tts_model, TEMP_DIR)
        self.messages = []
        self.current_response = ""
        self.audio_chunks = []
        self.is_processing = False


@app.on_event("startup")
async def startup_event():
    print("Loading models...")
    # Models are already loaded via the global variables


@app.on_event("shutdown")
async def shutdown_event():
    # Clean up temp files
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)


@app.get("/")
async def root():
    return {"message": "EmpathAI Voice Chatbot API is running"}


@app.post("/api/transcribe")
async def transcribe_audio_endpoint(audio: UploadFile = File(...)):
    """
    Transcribe uploaded audio file using Whisper.
    """
    try:
        # Create a temporary file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_audio_path = os.path.join(TEMP_DIR, f"{timestamp}_{audio.filename}")

        # Save the uploaded file
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Transcribe the audio
        start_time = time.time()
        transcription = transcribe_audio(temp_audio_path)
        transcription_time = time.time() - start_time

        if not transcription:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

        return {
            "transcription": transcription,
            "processing_time": transcription_time,
            "audio_path": temp_audio_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")


@app.post("/api/chat")
async def chat_endpoint(
    text: str,
    session_id: str = None,
    use_rag: bool = True,
    stream: bool = True,
    background_tasks: BackgroundTasks = None,
):
    """
    Process text input and return LLM response.
    Optionally use RAG for context retrieval.
    """
    try:
        # Create or get session
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in active_sessions:
            active_sessions[session_id] = AudioSession(session_id)

        session = active_sessions[session_id]

        # Get RAG context if enabled
        context = None
        if use_rag:
            context = get_context_from_rag(rag_retriever, text)

        # Add user message to session history
        session.messages.append({"role": "user", "content": text})

        # Get LLM response (non-streaming for this endpoint)
        start_time = time.time()
        ai_response = get_llm_response(text, context=context)
        response_time = time.time() - start_time

        # Add assistant message to session history
        session.messages.append({"role": "assistant", "content": ai_response})

        return {
            "session_id": session_id,
            "response": ai_response,
            "processing_time": response_time,
            "context_used": bool(context),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@app.post("/api/audio_response")
async def audio_response_endpoint(text: str, session_id: str = None):
    """
    Generate TTS audio from text.
    """
    try:
        # Create temp file for audio
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        audio_path = os.path.join(TEMP_DIR, f"{timestamp}_response.wav")

        # Generate speech
        tts_audio_path = text_to_speech(tts_model, text, audio_path)

        if not tts_audio_path or not os.path.exists(tts_audio_path):
            raise HTTPException(status_code=500, detail="Failed to generate audio")

        # Return audio file
        def iterfile():
            with open(tts_audio_path, "rb") as file:
                yield from file

        return StreamingResponse(iterfile(), media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")


@app.post("/api/voice_chat")
async def voice_chat_endpoint(
    audio: UploadFile = File(...), session_id: str = None, use_rag: bool = True
):
    """
    Complete voice chat flow:
    1. Transcribe uploaded audio
    2. Get LLM response
    3. Generate TTS audio response
    """
    try:
        # Create a temporary file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_audio_path = os.path.join(TEMP_DIR, f"{timestamp}_{audio.filename}")

        # Save the uploaded file
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Create or get session
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in active_sessions:
            active_sessions[session_id] = AudioSession(session_id)

        session = active_sessions[session_id]

        # Transcribe the audio
        transcription = transcribe_audio(temp_audio_path)
        if not transcription:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

        # Add user message to session history
        session.messages.append(
            {"role": "user", "content": transcription, "audio_path": temp_audio_path}
        )

        # Get RAG context if enabled
        context = None
        if use_rag:
            context = get_context_from_rag(rag_retriever, transcription)

        # Get LLM response
        ai_response = get_llm_response(transcription, context=context)

        # Generate TTS audio response
        tts_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tts_file_path = os.path.join(TEMP_DIR, f"{tts_timestamp}_response.wav")
        tts_audio_path = text_to_speech(tts_model, ai_response, tts_file_path)

        if not tts_audio_path or not os.path.exists(tts_audio_path):
            raise HTTPException(status_code=500, detail="Failed to generate audio response")

        # Add assistant message to session history
        session.messages.append(
            {"role": "assistant", "content": ai_response, "audio_path": tts_audio_path}
        )

        # Return audio file
        def iterfile():
            with open(tts_audio_path, "rb") as file:
                yield from file

        return StreamingResponse(
            iterfile(),
            media_type="audio/wav",
            headers={
                "X-Transcription": transcription,
                "X-Response-Text": ai_response,
                "X-Session-ID": session_id,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in voice chat: {str(e)}")


@app.post("/api/stream_voice_chat")
async def stream_voice_chat(
    background_tasks: BackgroundTasks,  # Add this parameter
    audio: UploadFile = File(...),
    session_id: str = None,
    use_rag: bool = True,
):
    """
    Stream the voice chat response:
    1. Transcribe uploaded audio
    2. Stream LLM response
    3. Generate and stream TTS audio chunks
    """
    try:
        # Create a temporary file
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        temp_audio_path = os.path.join(TEMP_DIR, f"{timestamp}_{audio.filename}")

        # Save the uploaded file
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        # Create or get session
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in active_sessions:
            active_sessions[session_id] = AudioSession(session_id)

        session = active_sessions[session_id]
        session.is_processing = True

        # Clear previous audio chunks
        session.audio_chunks = []
        session.current_response = ""

        # Transcribe the audio
        transcription = transcribe_audio(temp_audio_path)
        if not transcription:
            raise HTTPException(status_code=400, detail="Failed to transcribe audio")

        # Add user message to session history
        session.messages.append(
            {"role": "user", "content": transcription, "audio_path": temp_audio_path}
        )

        # Get RAG context if enabled
        context = None
        if use_rag:
            context = get_context_from_rag(rag_retriever, transcription)

        # Reset the TTS manager
        session.tts_manager.reset()

        # Function to process audio in the background
        async def process_audio_stream():
            # Get streaming response from LLM
            response_generator = stream_llm_response(transcription, context=context)

            import re

            sentence_buffer = ""

            for chunk in response_generator:
                if chunk and session.is_processing:
                    session.current_response += chunk

                    # Buffer text until we have complete sentences
                    sentence_buffer += chunk
                    print(f"Buffered text: {sentence_buffer}")
                    # Check if we have complete sentences to process
                    sentences = re.split(r"(?<=[.!?])\s+", sentence_buffer)

                    if len(sentences) > 1:  # We have at least one complete sentence
                        complete_sentences = sentences[:-1]  # All but the last one
                        sentence_buffer = sentences[-1]  # Keep the incomplete one for next time

                        for sentence in complete_sentences:
                            if sentence.strip():
                                # Generate audio for this sentence
                                audio_data = session.tts_manager.process_chunk(sentence)

                                if audio_data is not None and isinstance(audio_data, torch.Tensor):
                                    audio_data = audio_data.cpu().numpy()

                                if audio_data is not None:
                                    # Convert to bytes if it's a numpy array

                                    if isinstance(audio_data, np.ndarray):
                                        audio_bytes_io = io.BytesIO()
                                        sf.write(
                                            audio_bytes_io,
                                            audio_data,
                                            session.tts_manager.sample_rate,
                                            format="wav",
                                        )
                                        session.audio_chunks.append(audio_bytes_io.getvalue())

            # Process any remaining text
            if sentence_buffer and session.is_processing:
                audio_data = session.tts_manager.process_chunk(sentence_buffer)
                if audio_data is not None:
                    if isinstance(audio_data, np.ndarray):
                        audio_bytes_io = io.BytesIO()
                        sf.write(
                            audio_bytes_io,
                            audio_data,
                            session.tts_manager.sample_rate,
                            format="wav",
                        )
                        session.audio_chunks.append(audio_bytes_io.getvalue())

            # Save the complete audio
            tts_audio_path = session.tts_manager.save_complete_audio()

            # Add assistant message to session history
            session.messages.append(
                {
                    "role": "assistant",
                    "content": session.current_response,
                    "audio_path": tts_audio_path,
                }
            )

            session.is_processing = False

        # Start background processing
        if background_tasks:
            background_tasks.add_task(process_audio_stream)

        return {
            "session_id": session_id,
            "transcription": transcription,
            "status": "processing",
            "message": "Audio is being processed. Use /api/get_audio_chunks to receive audio chunks.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in streaming voice chat: {str(e)}")


@app.get("/api/get_audio_chunks")
async def get_audio_chunks(session_id: str):
    """
    Get audio chunks for a streaming session.
    """
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = active_sessions[session_id]

        # Return any available chunks
        chunks = session.audio_chunks.copy()

        # Clear the chunks that we're returning
        if chunks:
            session.audio_chunks = []

        return {
            "session_id": session_id,
            "chunks": len(chunks),
            "is_processing": session.is_processing,
            "response_so_far": session.current_response,
            "chunks_data": [base64.b64encode(chunk).decode() for chunk in chunks] if chunks else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting audio chunks: {str(e)}")


@app.post("/api/stop_session")
async def stop_session(session_id: str):
    """
    Stop a streaming session.
    """
    try:
        if session_id in active_sessions:
            session = active_sessions[session_id]
            session.is_processing = False
            session.tts_manager.stop()

        return {"session_id": session_id, "status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping session: {str(e)}")


@app.get("/api/session_history")
async def get_session_history(session_id: str):
    """
    Get chat history for a session.
    """
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = active_sessions[session_id]

        # Prepare messages without audio paths
        messages = []
        for msg in session.messages:
            message_copy = msg.copy()
            if "audio_path" in message_copy:
                del message_copy["audio_path"]
            messages.append(message_copy)

        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting session history: {str(e)}")


@app.delete("/api/clear_session")
async def clear_session(session_id: str):
    """
    Clear a session's history and temporary files.
    """
    try:
        if session_id in active_sessions:
            session = active_sessions[session_id]

            # Stop any processing
            session.is_processing = False
            session.tts_manager.stop()

            # Clear messages
            session.messages = []

            # Delete any audio files for this session
            for filename in os.listdir(TEMP_DIR):
                if session_id in filename:
                    try:
                        os.remove(os.path.join(TEMP_DIR, filename))
                    except:
                        pass

            # Reset the TTS manager
            session.tts_manager.reset()

            return {"session_id": session_id, "status": "cleared"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing session: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
