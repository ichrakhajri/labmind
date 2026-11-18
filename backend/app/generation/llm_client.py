"""Client abstrait pour modèle de langage exécuté strictement en local."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

DEFAULT_OLLAMA_URL = os.getenv("LABMIND_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_LLM_MODEL = os.getenv("LABMIND_LLM_MODEL", "qwen2.5:1.5b")
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalLLMError(RuntimeError):
    """Erreur technique lors de l'appel au modèle local."""


@runtime_checkable
class LocalLLMClient(Protocol):
    """Interface minimale d'un modèle de langage local."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Retourne la réponse textuelle brute du modèle."""
        ...


class OllamaLLMClient:
    """Client HTTP vers une instance Ollama strictement locale (127.0.0.1/localhost)."""

    def __init__(
        self,
        model: str = DEFAULT_LLM_MODEL,
        base_url: str = DEFAULT_OLLAMA_URL,
        timeout_seconds: float = 60.0,
        allow_remote: bool = False,
    ) -> None:
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if not allow_remote and host not in _LOCAL_HOSTS:
            raise ValueError(
                f"URL non autorisée ({base_url}) : le LLM doit s'exécuter localement "
                "sur localhost ou 127.0.0.1."
            )

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LocalLLMError(
                f"Échec de communication avec Ollama ({self.base_url}) : {exc}"
            ) from exc

        message = body.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise LocalLLMError("Réponse Ollama inattendue : champ 'message.content' absent.")
        return message["content"]