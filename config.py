# config.py
import os


class Config:
    # Audio settings
    SAMPLE_RATE = 24000  # Default sample rate for audio
    TTS_MODEL_NAME = "tts_models/en/vctk/vits"  # Default Coqui TTS model
    TEMP_DIR = os.path.join(os.getcwd(), "temp_recordings")

    # API settings
    MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB max audio file size
    SESSION_EXPIRY = 60 * 60  # Session expires after 1 hour

    # LLM settings
    LLM_MODEL = "models/gemini-1.5-pro-latest"  # Gemini model to use

    # RAG settings
    RAG_ENABLED = True
    CONTEXT_MAX_TOKENS = 3000

    # System prompt for the LLM
    Prompt = """
    You are EmpathAI, an empathetic and helpful voice assistant. 
    Your responses should be:
    
    1. Natural and conversational
    2. Empathetic to the user's needs and emotions
    3. Clear and concise, suitable for speaking aloud
    4. Helpful and informative
    
    When providing information, be honest about what you know and don't know.
    When explaining complex topics, break them down into simpler terms.
    
    Always maintain a friendly, supportive tone throughout the conversation.
    """


TEMP_DIR = os.path.join(os.getcwd(), "temp_recordings")
# TTS_MODEL_NAME = "tts_models/en/ljspeech/glow-tts"
TTS_MODEL_NAME = "tts_models/en/jenny/jenny"
SAMPLE_RATE = 48000
