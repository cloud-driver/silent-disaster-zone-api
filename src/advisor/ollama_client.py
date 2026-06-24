import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv


load_dotenv()


class OllamaError(Exception):
    """Raised when the local Ollama service is unavailable or returns an invalid response."""
    pass


def get_ollama_settings() -> Dict[str, str]:
    """
    Read Ollama settings from environment variables.

    Environment variables:
    - OLLAMA_BASE_URL: default http://127.0.0.1:11434
    - OLLAMA_MODEL: default qwen2.5:7b
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    return {
        "base_url": base_url,
        "model": model,
    }


def check_ollama(timeout: int = 5) -> Dict[str, Any]:
    """
    Check whether Ollama is available and list installed models.

    This should not crash the main API. It returns available=False when Ollama
    is not running or unreachable.
    """
    settings = get_ollama_settings()
    url = f"{settings['base_url']}/api/tags"

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        models = [
            item.get("name")
            for item in data.get("models", [])
            if isinstance(item, dict)
        ]

        return {
            "available": True,
            "base_url": settings["base_url"],
            "configured_model": settings["model"],
            "installed_models": models,
        }

    except Exception as e:
        return {
            "available": False,
            "base_url": settings["base_url"],
            "configured_model": settings["model"],
            "installed_models": [],
            "error": str(e),
        }


def chat_with_ollama(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    timeout: int = 120,
    response_format: str | dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Send a chat request to the local Ollama API.

    Returns:
    {
      "model": "...",
      "base_url": "...",
      "content": "...",
      "raw": {...}
    }
    """
    settings = get_ollama_settings()
    url = f"{settings['base_url']}/api/chat"

    payload = {
        "model": settings["model"],
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "options": {
            "temperature": temperature,
        },
    }

    if response_format is not None:
        payload["format"] = response_format

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")

        if not content:
            raise OllamaError("Ollama returned empty content.")

        return {
            "model": settings["model"],
            "base_url": settings["base_url"],
            "content": content,
            "raw": data,
        }

    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Ollama request failed: {e}") from e

    except Exception as e:
        raise OllamaError(f"Ollama chat failed: {e}") from e
