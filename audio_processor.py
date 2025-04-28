import asyncio
import base64
import io
import re
import numpy as np
import soundfile as sf
from typing import List, Dict, Any, Optional


class AudioProcessor:
    """
    Helper class to process audio in the background
    """

    def __init__(self, tts_manager, llm_response_generator):
        self.tts_manager = tts_manager
        self.llm_response_generator = llm_response_generator
        self.current_response = ""
        self.audio_chunks = []
        self.is_processing = True
        self.sentence_buffer = ""

    async def process_stream(self):
        """
        Process the LLM response stream and generate audio chunks
        """
        try:
            for chunk in self.llm_response_generator:
                if chunk and self.is_processing:
                    self.current_response += chunk

                    # Buffer text until we have complete sentences
                    self.sentence_buffer += chunk

                    # Check if we have complete sentences to process
                    sentences = re.split(r"(?<=[.!?])\s+", self.sentence_buffer)

                    if len(sentences) > 1:  # We have at least one complete sentence
                        complete_sentences = sentences[:-1]  # All but the last one
                        self.sentence_buffer = sentences[
                            -1
                        ]  # Keep the incomplete one for next time

                        for sentence in complete_sentences:
                            if sentence.strip():
                                await self._process_sentence(sentence)

                    # Small delay to prevent blocking
                    await asyncio.sleep(0.01)

            # Process any remaining text
            if self.sentence_buffer and self.is_processing:
                await self._process_sentence(self.sentence_buffer)

            return self.current_response, self.audio_chunks

        except Exception as e:
            print(f"Error processing audio stream: {e}")
            self.is_processing = False
            return self.current_response, self.audio_chunks

    async def _process_sentence(self, sentence: str):
        """
        Process a single sentence into audio
        """
        audio_data = self.tts_manager.process_chunk(sentence)
        if audio_data is not None:
            # Convert to bytes if it's a numpy array
            if isinstance(audio_data, np.ndarray):
                audio_bytes_io = io.BytesIO()
                sf.write(audio_bytes_io, audio_data, self.tts_manager.sample_rate, format="wav")
                self.audio_chunks.append(audio_bytes_io.getvalue())
            else:
                self.audio_chunks.append(audio_data)

    def stop(self):
        """
        Stop processing
        """
        self.is_processing = False

    def get_chunks(self) -> List[bytes]:
        """
        Get available chunks and clear the buffer
        """
        chunks = self.audio_chunks.copy()
        self.audio_chunks = []
        return chunks

    def encode_chunks(self, chunks: List[bytes]) -> List[str]:
        """
        Encode chunks to base64 for transmission
        """
        return [base64.b64encode(chunk).decode() for chunk in chunks]
