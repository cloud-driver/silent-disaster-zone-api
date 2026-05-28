import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv


load_dotenv()


class OllamaError(Exception):
    pass


def get_ollama_settings() -> Dict[str, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    return {
        "base_url": base_url,
        "model": model,
    }


def check_ollama(timeout: int = 5) -> Dict[str, Any]:
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
) -> Dict[str, Any]:
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