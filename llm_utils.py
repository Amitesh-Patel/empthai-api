import google.generativeai as genai
from config import Config
from dotenv import load_dotenv
import os

load_dotenv()


def setup_gemini():
    """
    Setup Gemini API with your API key
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"Error setting up Gemini: {e}")
        return False


def get_llm_response(user_input, context=None):
    """
    Get a complete (non-streaming) response from Gemini.
    """
    try:
        print("Context:", context)

        if not setup_gemini():
            return "Error: Could not connect to LLM. Please check your API key."

        model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

        system_prompt = (
            Config.Prompt
            + "\n\nYou are now in a conversation with a user. Please respond to their messages with empathy and support."
            + "\n\nIMPORTANT CONTEXT USAGE INSTRUCTIONS: You may receive additional knowledge context for some queries. "
            + "Only reference or use this context when it's directly relevant to answering complex or specific questions. "
            + "For simple greetings, conversational exchanges, or general knowledge questions, rely on your own knowledge "
            + "without mentioning the provided context or retrieval process."
        )

        history = [{"role": "user", "parts": [system_prompt]}]

        if context:
            history.append(
                {
                    "role": "user",
                    "parts": [
                        f"Here is some additional information that may be relevant to the user's query. Only use this if needed for complex or specific questions:\n\n{context}"
                    ],
                }
            )

        chat = model.start_chat(history=history)

        response = chat.send_message(user_input)
        return response.text

    except Exception as e:
        return f"Error getting LLM response: {e}"


def stream_llm_response(user_input, context=None):
    """
    Stream Gemini response chunks one by one (generator).
    """
    try:
        print("Context:", context)

        if not setup_gemini():
            yield "Error: Could not connect to LLM. Please check your API key."
            return

        model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

        system_prompt = (
            Config.Prompt
            + "\n\nYou are now in a conversation with a user. Please respond to their messages with empathy and support."
            + "\n\nIMPORTANT CONTEXT USAGE INSTRUCTIONS: You may receive additional knowledge context for some queries. "
            + "Only reference or use this context when it's directly relevant to answering complex or specific questions. "
            + "For simple greetings, conversational exchanges, or general knowledge questions, rely on your own knowledge "
            + "without mentioning the provided context or retrieval process."
        )

        history = [{"role": "user", "parts": [system_prompt]}]

        if context:
            history.append(
                {
                    "role": "user",
                    "parts": [
                        f"Here is some additional information that may be relevant to the user's query. Only use this if needed for complex or specific questions:\n\n{context}"
                    ],
                }
            )

        chat = model.start_chat(history=history)

        response = chat.send_message(user_input, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        yield f"Error streaming LLM response: {e}"
