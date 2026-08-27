import os
from typing import Optional

import ollama


class OllamaClient:
    def __init__(self, model: str = "qwen2.5:7b-instruct", host: Optional[str] = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.client = ollama.Client(host=self.host)

    def availability(self) -> tuple[bool, str | None]:
        try:
            response = self.client.list()
            models = response.get("models", []) if isinstance(response, dict) else getattr(response, "models", [])
            names = {item.get("name") if isinstance(item, dict) else getattr(item, "model", None) for item in models}
            if self.model not in names:
                return False, f"ollama_model_missing: {self.model}"
            return True, None
        except Exception as exc:
            return False, f"ollama_unreachable: {exc.__class__.__name__}"

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.0, max_tokens: int = 300, seed: int = 42) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": temperature, "top_p": 1.0, "seed": seed, "num_predict": max_tokens},
        )
        return response["message"]["content"].strip()

    def is_available(self) -> bool:
        return self.availability()[0]
