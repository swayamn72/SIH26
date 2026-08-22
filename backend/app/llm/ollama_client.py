import json
import os
from typing import Any, Optional

import ollama


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:7b-instruct", host: Optional[str] = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.client = ollama.Client(host=self.host)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 300,
        seed: int = 42,
    ) -> str:
        options = {
            "temperature": temperature,
            "top_p": 1.0,
            "seed": seed,
            "num_predict": max_tokens,
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat(
            model=self.model,
            messages=messages,
            options=options,
        )

        return response["message"]["content"].strip()

    def is_available(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False
