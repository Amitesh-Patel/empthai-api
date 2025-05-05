import os
import soundfile as sf
from datetime import datetime

try:
    from TTS.api import TTS

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
from config import TTS_MODEL_NAME, SAMPLE_RATE, TEMP_DIR
import whisper
import numpy as np

# Import Kokoro
try:
    from kokoro import KPipeline

    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


# TTS Provider abstract class
class TTSProvider:
    def __init__(self):
        pass

    def load_model(self):
        """Load the TTS model"""
        pass

    def generate_speech(self, text, output_path=None):
        """Generate speech from text"""
        pass

    def get_name(self):
        """Get the name of the TTS provider"""
        pass


# Coqui TTS Provider
class CoquiTTSProvider(TTSProvider):
    def __init__(self, model_name=TTS_MODEL_NAME, gpu=True):
        super().__init__()
        self.model_name = model_name
        self.gpu = gpu
        self.model = None
        self.sample_rate = SAMPLE_RATE

    def load_model(self):
        if not TTS_AVAILABLE:
            raise ImportError("Coqui TTS is not available. Please install it first.")

        if self.model is None:
            self.model = TTS(self.model_name, gpu=self.gpu)
        return self.model

    def generate_speech(self, text, output_path=None):
        if self.model is None:
            self.load_model()

        wav = self.model.tts(text)

        if output_path:
            sf.write(output_path, wav, self.sample_rate)
            return output_path
        return wav

    def get_name(self):
        return "Coqui TTS"


# Kokoro TTS Provider
class KokoroTTSProvider(TTSProvider):
    def __init__(self, lang_code="a", device="cpu", voice="af_heart"):
        super().__init__()
        self.lang_code = lang_code
        self.device = device
        self.voice = voice
        self.model = None
        self.sample_rate = 24000  # Kokoro's default sample rate

    def load_model(self):
        if not KOKORO_AVAILABLE:
            raise ImportError("Kokoro TTS is not available. Please install it first.")

        if self.model is None:
            self.model = KPipeline(lang_code=self.lang_code, device=self.device)
        return self.model

    def generate_speech(self, text, output_path=None):
        if self.model is None:
            self.load_model()

        # Store all audio chunks
        all_audio = None

        # Use the generator to get speech chunks
        generator = self.model(text, voice=self.voice)

        for i, (gs, ps, audio) in enumerate(generator):
            if all_audio is None:
                all_audio = audio
            else:
                # If we need to append chunks, we'd need to handle that
                # This is simplified; you might need to handle audio concatenation properly
                import numpy as np

                all_audio = np.concatenate((all_audio, audio))

        if output_path:
            sf.write(output_path, all_audio, self.sample_rate)
            return output_path

        return all_audio

    def get_name(self):
        return f"Kokoro TTS ({self.voice})"


# Factory for creating TTS providers
class TTSFactory:
    @staticmethod
    def create_provider(provider_type, **kwargs):
        if provider_type.lower() == "coqui":
            return CoquiTTSProvider(**kwargs)
        elif provider_type.lower() == "kokoro":
            return KokoroTTSProvider(**kwargs)
        else:
            raise ValueError(f"Unknown TTS provider: {provider_type}")


# Enhanced streaming TTS manager that works with any provider
class StreamingTTSManager:
    def __init__(self, tts_provider, temp_dir):
        self.provider = tts_provider
        self.temp_dir = temp_dir
        self.sample_rate = getattr(tts_provider, "sample_rate", 48000)
        self.all_audio = None
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.stop_streaming = False
        self.audio_thread = None
        self.speed = 1.0
        self.memory_chunks = []

    def process_text(self, text):
        """Process entire text at once into multiple chunks"""
        import re
        import io
        import soundfile as sf
        import numpy as np

        # Split text into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)
        self.memory_chunks = []

        # Initialize all_audio as an empty numpy array if it's None
        if self.all_audio is None:
            self.all_audio = np.array([], dtype=np.float32)

        # Process each sentence
        for sentence in sentences:
            if sentence.strip():
                chunk_data = self.process_chunk(sentence)
                if chunk_data is not None:
                    # Convert numpy array to bytes
                    chunk_bytes_io = io.BytesIO()
                    sf.write(chunk_bytes_io, chunk_data, self.sample_rate, format="wav")
                    self.memory_chunks.append(chunk_bytes_io.getvalue())

        return self.memory_chunks

    def process_chunk(self, text_chunk):
        """Convert a text chunk to speech and return audio data"""
        if not text_chunk.strip():
            return None

        try:
            # Generate audio for this chunk using the provider
            audio = self.provider.generate_speech(text_chunk)

            if self.speed != 1.0:
                import pyrubberband as pyrb
                import numpy as np

                if isinstance(audio, list):
                    audio = np.array(audio, dtype=np.float32)
                audio = pyrb.time_stretch(audio, self.sample_rate, self.speed)

            # Store for complete file
            import numpy as np

            if isinstance(audio, list):
                audio = np.array(audio, dtype=np.float32)

            if self.all_audio is None:
                self.all_audio = audio
            else:
                self.all_audio = np.concatenate((self.all_audio, audio))

            return audio

        except Exception as e:
            print(f"Error processing chunk: {e}")
            raise RuntimeError(f"Error processing chunk: {e}")

    def save_complete_audio(self):
        """Save the complete audio to file"""
        if self.all_audio is None or len(self.all_audio) == 0:
            print("No audio to save")
            return None

        output_path = os.path.join(self.temp_dir, f"{self.session_id}_complete.wav")
        sf.write(output_path, self.all_audio, self.sample_rate)
        return output_path

    def reset(self):
        """Reset the streaming manager for a new session"""

        self.all_audio = np.array([], dtype=np.float32)
        self.session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self.stop_streaming = False
        self.memory_chunks = []

    def stop(self):
        """Stop the streaming process"""
        self.stop_streaming = True
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1)


# Helper functions
def load_tts_model(provider_type="coqui", **kwargs):
    """Load a TTS model using the specified provider"""
    provider = TTSFactory.create_provider(provider_type, **kwargs)
    provider.load_model()
    return provider


def text_to_speech(tts_provider, text, output_path):
    """Generate speech from text and save to file"""
    try:
        return tts_provider.generate_speech(text, output_path)
    except Exception as e:
        raise RuntimeError(f"Error generating speech: {e}")


# Transcription functions
def transcribe_audio(model, audio_path):
    """Transcribe audio file using Whisper"""
    try:
        # Load the Whisper model
        print("Transcribing audio...", audio_path)
        # Transcribe the audio
        result = model.transcribe(audio_path)
        return result["text"]
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None
