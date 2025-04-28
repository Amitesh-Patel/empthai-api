# session_utils.py
import os
import time
import datetime
import json
from audio_utils import StreamingTTSManager
from typing import Dict, Any, List


class SessionManager:
    """
    Manage API sessions and their state
    """

    def __init__(self, temp_dir, tts_model, expiry_seconds=3600):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.temp_dir = temp_dir
        self.tts_model = tts_model
        self.expiry_seconds = expiry_seconds

        # Create temp directory if it doesn't exist
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

    def create_session(self, session_id):
        """
        Create a new session or reset an existing one
        """
        self.sessions[session_id] = {
            "created_at": time.time(),
            "last_activity": time.time(),
            "messages": [],
            "tts_manager": StreamingTTSManager(self.tts_model, self.temp_dir),
            "current_response": "",
            "audio_chunks": [],
            "is_processing": False,
        }
        return self.sessions[session_id]

    def get_session(self, session_id):
        """
        Get an existing session or create a new one
        """
        self.cleanup_expired_sessions()

        if session_id not in self.sessions:
            return self.create_session(session_id)

        # Update last activity time
        self.sessions[session_id]["last_activity"] = time.time()
        return self.sessions[session_id]

    def update_session(self, session_id, **updates):
        """
        Update session properties
        """
        if session_id in self.sessions:
            for key, value in updates.items():
                self.sessions[session_id][key] = value
            self.sessions[session_id]["last_activity"] = time.time()
            return True
        return False

    def delete_session(self, session_id):
        """
        Delete a session and its files
        """
        if session_id in self.sessions:
            # Clean up any session files
            for filename in os.listdir(self.temp_dir):
                if session_id in filename:
                    try:
                        os.remove(os.path.join(self.temp_dir, filename))
                    except:
                        pass

            # Delete session
            del self.sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self):
        """
        Remove expired sessions
        """
        current_time = time.time()
        expired_sessions = []

        for session_id, session_data in self.sessions.items():
            last_activity = session_data.get("last_activity", 0)
            if current_time - last_activity > self.expiry_seconds:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self.delete_session(session_id)

        return len(expired_sessions)

    def add_message(self, session_id, role, content, audio_path=None):
        """
        Add a message to the session history
        """
        session = self.get_session(session_id)
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if audio_path:
            message["audio_path"] = audio_path

        session["messages"].append(message)
        return message

    def get_messages(self, session_id):
        """
        Get all messages for a session
        """
        session = self.get_session(session_id)
        return session.get("messages", [])

    def clear_messages(self, session_id):
        """
        Clear all messages for a session
        """
        session = self.get_session(session_id)
        session["messages"] = []
        return True

    def export_session(self, session_id, file_path=None):
        """
        Export session data to JSON
        """
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]

        # Create exportable data (without tts_manager)
        export_data = {
            "session_id": session_id,
            "created_at": session.get("created_at"),
            "messages": session.get("messages", []),
        }

        if file_path:
            with open(file_path, "w") as f:
                json.dump(export_data, f, indent=2)

        return export_data
