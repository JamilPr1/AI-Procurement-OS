"""Local LLM client — Ollama-first with optional API fallback."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class LLMClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config.get("llm", {})
        self.provider = self.config.get("provider", "ollama")
        self.model = self.config.get("model", "llama3.2")
        self.temperature = self.config.get("temperature", 0.3)
        self.max_tokens = self.config.get("max_tokens", 4096)
        self.timeout = self.config.get("timeout_seconds", 120)
        self.base_url = self.config.get("base_url", "http://localhost:11434")

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, int]:
        """Returns (response_text, duration_ms)."""
        start = time.perf_counter()
        if self.provider == "ollama":
            text = self._ollama_complete(system_prompt, user_message)
        elif self.provider == "openai":
            text = self._openai_complete(system_prompt, user_message)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        duration_ms = int((time.perf_counter() - start) * 1000)
        return text, duration_ms

    def complete_json(self, system_prompt: str, user_message: str) -> tuple[dict[str, Any], int]:
        text, duration_ms = self.complete(system_prompt, user_message)
        return self._parse_json(text), duration_ms

    def health_check(self) -> dict[str, Any]:
        if self.provider == "ollama":
            try:
                with httpx.Client(timeout=5) as client:
                    r = client.get(f"{self.base_url}/api/tags")
                    r.raise_for_status()
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    return {
                        "status": "ok",
                        "provider": "ollama",
                        "url": self.base_url,
                        "models": models,
                        "configured_model": self.model,
                        "model_available": any(self.model in m for m in models),
                    }
            except Exception as e:
                return {"status": "error", "provider": "ollama", "error": str(e)}
        return {"status": "ok", "provider": self.provider}

    def _ollama_complete(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/api/chat", json=payload)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "")

    def _openai_complete(self, system_prompt: str, user_message: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise
