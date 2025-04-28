import requests
import time
import base64
import json
import pyaudio
import wave
import io
import threading


class EmpathAIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session_id = None
        self.audio_chunks = []
        self.is_streaming = False

    def transcribe_audio(self, audio_file_path):
        """
        Transcribe an audio file
        """
        with open(audio_file_path, "rb") as f:
            files = {"audio": f}
            response = requests.post(f"{self.base_url}/api/transcribe", files=files)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def chat(self, text, use_rag=True):
        """
        Send a text message and get a response
        """
        params = {"text": text, "use_rag": use_rag}

        if self.session_id:
            params["session_id"] = self.session_id

        response = requests.post(f"{self.base_url}/api/chat", params=params)

        if response.status_code == 200:
            result = response.json()
            self.session_id = result["session_id"]
            return result
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def voice_chat(self, audio_file_path, use_rag=True):
        """
        Send an audio message and get an audio response
        """
        with open(audio_file_path, "rb") as f:
            files = {"audio": f}
            params = {"use_rag": use_rag}

            if self.session_id:
                params["session_id"] = self.session_id

            response = requests.post(
                f"{self.base_url}/api/voice_chat", files=files, params=params, stream=True
            )

        if response.status_code == 200:
            # Get metadata from headers
            self.session_id = response.headers.get("X-Session-ID")
            transcription = response.headers.get("X-Transcription")
            response_text = response.headers.get("X-Response-Text")

            # Save audio to file
            audio_file = f"response_{int(time.time())}.wav"
            with open(audio_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return {
                "transcription": transcription,
                "response_text": response_text,
                "audio_file": audio_file,
            }
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def start_streaming_voice_chat(self, audio_file_path, use_rag=True):
        """
        Start a streaming voice chat session
        """
        with open(audio_file_path, "rb") as f:
            files = {"audio": f}
            params = {"use_rag": use_rag}

            if self.session_id:
                params["session_id"] = self.session_id

            response = requests.post(
                f"{self.base_url}/api/stream_voice_chat", files=files, params=params
            )

        if response.status_code == 200:
            result = response.json()
            self.session_id = result["session_id"]
            self.is_streaming = True

            # Start audio chunk polling in a separate thread
            threading.Thread(target=self._poll_audio_chunks).start()

            return result
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

    def _poll_audio_chunks(self):
        """
        Poll for audio chunks and play them
        """
        p = pyaudio.PyAudio()

        # Open a stream
        stream = None

        try:
            while self.is_streaming:
                # Get audio chunks
                response = requests.get(
                    f"{self.base_url}/api/get_audio_chunks", params={"session_id": self.session_id}
                )

                if response.status_code == 200:
                    result = response.json()
                    chunks_data = result.get("chunks_data", [])

                    # Update streaming status
                    self.is_streaming = result.get("is_processing", False)

                    # Process chunks
                    for chunk_base64 in chunks_data:
                        # Decode base64
                        chunk_data = base64.b64decode(chunk_base64)

                        # Convert to audio and play
                        self._play_audio_chunk(chunk_data, p, stream)

                    # Small delay between polling
                    time.sleep(0.1)
                else:
                    print(f"Error polling chunks: {response.status_code} - {response.text}")
                    self.is_streaming = False

        finally:
            # Clean up
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()

    def _play_audio_chunk(self, chunk_data, p, stream=None):
        """
        Play an audio chunk
        """
        # Read the WAV data
        with io.BytesIO(chunk_data) as f:
            with wave.open(f, "rb") as wf:
                # Get format info
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()

                # Create or reuse stream
                if not stream:
                    stream = p.open(
                        format=p.get_format_from_width(sample_width),
                        channels=channels,
                        rate=frame_rate,
                        output=True,
                    )

                # Read and play
                data = wf.readframes(wf.getnframes())
                stream.write(data)

    def stop_streaming(self):
        """
        Stop the streaming session
        """
        if self.session_id:
            response = requests.post(
                f"{self.base_url}/api/stop_session", params={"session_id": self.session_id}
            )
            self.is_streaming = False
            return response.json() if response.status_code == 200 else None
        return None

    def get_history(self):
        """
        Get session history
        """
        if self.session_id:
            response = requests.get(
                f"{self.base_url}/api/session_history", params={"session_id": self.session_id}
            )
            return response.json() if response.status_code == 200 else None
        return None

    def clear_session(self):
        """
        Clear the current session
        """
        if self.session_id:
            response = requests.delete(
                f"{self.base_url}/api/clear_session", params={"session_id": self.session_id}
            )
            return response.json() if response.status_code == 200 else None
        return None


# Example usage
if __name__ == "__main__":
    client = EmpathAIClient()

    # Example 1: Text chat
    response = client.chat("Hello, how are you today?")
    print(f"AI: {response['response']}")

    # # Example 2: Voice chat
    # result = client.voice_chat("recording.wav")
    # print(f"Transcription: {result['transcription']}")
    # print(f"AI Response: {result['response_text']}")
    # print(f"Audio saved to: {result['audio_file']}")

    # Example 3: Streaming voice chat
    # client.start_streaming_voice_chat("assists/test.wav")
    # print("Streaming started... press Enter to stop")
    # input()
    # client.stop_streaming()

    # Get chat history
    history = client.get_history()
    for msg in history["messages"]:
        print(f"{msg['role']}: {msg['content']}")
