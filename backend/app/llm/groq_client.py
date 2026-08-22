import os
from typing import Optional


class GroqClient:
    """Fast cloud LLM client using the Groq API (free tier available)."""

    def __init__(self, model: str = "llama-3.1-8b-instant"):
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "groq package not installed. Run: pip install groq"
            )
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable not set")
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 300,
        seed: int = 42,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
        )
        return response.choices[0].message.content.strip()

    def is_available(self) -> bool:
        return bool(os.environ.get("GROQ_API_KEY", ""))
