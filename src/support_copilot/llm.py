"""Multi-backend LLM client supporting deterministic MockLLM, Google Gemini, and OpenAI."""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol


class LLMError(RuntimeError):
    """Raised when an LLM provider request fails or authentication is missing."""


class LLMClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        ...


def clean_json_response(raw_output: str) -> str:
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


class MockLLM:
    """Deterministic offline LLM for reliable, testable zero-cost execution."""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        prompt_lower = user_prompt.lower()

        if "refund" in prompt_lower:
            return json.dumps({
                "response_text": (
                    "Hi there,\n\n"
                    "Thanks for reaching out. Under our Standard Refund Policy (KB-001), you are eligible "
                    "for a full refund within 14 calendar days of purchase as long as API usage has not "
                    "exceeded 100 requests. Once approved, the funds will be returned to your original "
                    "payment card within 3-5 business days.\n\n"
                    "Best regards,\nCustomer Support Team"
                ),
                "internal_notes": "Customer requested refund. Checked KB-001: within 14-day window.",
            })

        if "rate limit" in prompt_lower or "429" in prompt_lower:
            return json.dumps({
                "response_text": (
                    "Hello,\n\n"
                    "HTTP 429 indicates your application has exceeded the API rate limit (KB-002: 60 req/min "
                    "on Basic, 600 req/min on Pro). We recommend inspecting the 'Retry-After' header and "
                    "implementing exponential backoff with jitter.\n\n"
                    "Best regards,\nDeveloper Support Team"
                ),
                "internal_notes": "Technical rate limiting inquiry. Cited KB-002 backoff guidelines.",
            })

        if "2fa" in prompt_lower or "locked" in prompt_lower:
            return json.dumps({
                "response_text": (
                    "Hello,\n\n"
                    "For account security, support agents cannot manually disable 2FA over email (KB-003). "
                    "Please locate your 16-character emergency recovery codes or initiate automated "
                    "identity verification at https://app.acme.io/auth/recovery.\n\n"
                    "Best regards,\nSecurity Team"
                ),
                "internal_notes": "2FA recovery request. Directed user to automated verification.",
            })

        return json.dumps({
            "response_text": (
                "Hello,\n\n"
                "Thank you for contacting support. We have received your inquiry and a specialist will "
                "review your request shortly.\n\n"
                "Best regards,\nSupport Team"
            ),
            "internal_notes": "General inquiry response.",
        })


class GeminiLLM:
    """Live Google Gemini LLM provider using native JSON generation."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"Gemini API HTTP {exc.code}: {err_body}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Failed to connect to Gemini API: {exc.reason}") from exc

        try:
            candidates = result.get("candidates", [])
            if not candidates:
                raise LLMError(f"Gemini returned no candidates: {result}")
            parts = candidates[0].get("content", {}).get("parts", [])
            return parts[0].get("text", "{}")
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Malformed Gemini API response: {result}") from exc


class OpenAILLM:
    """Live OpenAI or OpenAI-compatible (Groq, Ollama, OpenRouter) LLM provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"OpenAI API HTTP {exc.code}: {err_body}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Failed to connect to OpenAI API: {exc.reason}") from exc

        try:
            choices = result.get("choices", [])
            if not choices:
                raise LLMError(f"OpenAI returned no choices: {result}")
            return choices[0].get("message", {}).get("content", "{}")
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Malformed OpenAI API response: {result}") from exc


def get_llm_client(
    provider: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> LLMClient:
    selected = (provider or os.environ.get("LLM_PROVIDER") or "mock").lower()

    if selected == "gemini":
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise LLMError(
                "GEMINI_API_KEY is required for Gemini provider. Set it in .env or pass --api-key."
            )
        chosen_model = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        return GeminiLLM(api_key=key, model=chosen_model)

    if selected == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise LLMError(
                "OPENAI_API_KEY is required for OpenAI provider. Set it in .env or pass --api-key."
            )
        chosen_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return OpenAILLM(api_key=key, model=chosen_model, base_url=base_url)

    if selected == "mock":
        return MockLLM()

    raise LLMError(f"Unknown LLM provider '{selected}'. Expected 'mock', 'gemini', or 'openai'.")
