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


def get_llm_response(user_input, stream=False, context=None):
    """
    Get response from Gemini with chat history and a system prompt.
    Option to stream the response and include RAG-retrieved context when beneficial.
    """
    try:
        print("Context", context)
        # Setup Gemini
        if not setup_gemini():
            return "Error: Could not connect to LLM. Please check your API key."

        # Initialize Gemini model
        model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

        # Define your system prompt with intelligent context usage guidance
        system_prompt = (
            Config.Prompt
            + "\n\nYou are now in a conversation with a user. Please respond to their messages with empathy and support."
            + "\n\nIMPORTANT CONTEXT USAGE INSTRUCTIONS: You may receive additional knowledge context for some queries. "
            + "Only reference or use this context when it's directly relevant to answering complex or specific questions. "
            + "For simple greetings, conversational exchanges, or general knowledge questions, rely on your own knowledge "
            + "without mentioning the provided context. Never explicitly mention that you're using context or reference the "
            + "retrieval process in your responses."
        )

        # Start building the conversation history
        history = []

        # Inject the system prompt as a 'user' message for context
        history.append({"role": "user", "parts": [system_prompt]})

        # Add the RAG context if provided, but instruct model on its proper use
        if context:
            context_instruction = {
                "role": "user",
                "parts": [
                    f"Here is some additional information that may be relevant to the user's query. Only use this if needed for complex or specific questions: \n\n{context}"
                ],
            }
            history.append(context_instruction)

        # Start the chat session with history
        chat = model.start_chat(history=history)

        if stream:
            # Return a generator for streaming responses
            response = chat.send_message(user_input, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        else:
            # Get Gemini's complete response
            response = chat.send_message(user_input)
            return response.text

    except Exception as e:
        error_msg = f"Error getting LLM response: {e}"
        if stream:
            yield error_msg
        else:
            return error_msg
