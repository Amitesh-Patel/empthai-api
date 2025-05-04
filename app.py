# run_api.py
import os
import uvicorn
import argparse
from fastapi import FastAPI
from main import app


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run the EmpathAI Voice Chatbot API")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to run the API on (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the API on (default: 8000)"
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    print(f"Starting EmpathAI Voice Chatbot API on {args.host}:{args.port}")
    print(f"Debug mode: {args.debug}")
    print(f"Auto-reload: {args.reload}")

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )
