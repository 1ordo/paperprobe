import json
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 600.0,
    ):
        self.base_url = (base_url or settings.ai_api_base_url).rstrip("/")
        self.api_key = api_key or settings.ai_api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 16384,
        response_format: dict | None = None,
    ) -> str:
        model = model or settings.ai_model_primary
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
                finish_reason = data["choices"][0].get("finish_reason", "unknown")
                if finish_reason == "length":
                    logger.warning(f"AI response truncated (finish_reason=length, max_tokens={max_tokens}). Consider increasing max_tokens.")
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                logger.error(f"AI API error {e.response.status_code} for model={model}: {e.response.text[:500]}")
                # If json_object format is not supported, retry without it
                if e.response.status_code == 400 and response_format:
                    logger.info("Retrying without response_format...")
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                raise
            except Exception as e:
                logger.error(f"AI API request failed: {e}")
                raise

    async def chat_completion_json(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ) -> dict:
        # Ensure messages instruct JSON output even if response_format fails
        json_messages = list(messages)
        if json_messages and json_messages[-1]["role"] == "user":
            json_messages[-1] = {
                **json_messages[-1],
                "content": json_messages[-1]["content"] + "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no explanation, just the JSON object.",
            }

        raw = await self.chat_completion(
            messages=json_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._parse_json_response(raw)

    def _parse_json_response(self, raw: str) -> dict:
        """Parse JSON from LLM response, handling various formats."""
        import re

        if not raw or not raw.strip():
            logger.warning("Empty AI response, returning empty dict")
            return {}

        # Strip thinking blocks and special tokens (common with reasoning models)
        text = re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()
        # Strip channel/constrain/message tokens (gpt-oss / LM Studio models)
        text = re.sub(r'<\|channel\|>[^<]*', '', text)
        text = re.sub(r'<\|constrain\|>[^<]*', '', text)
        text = re.sub(r'<\|message\|>', '', text)
        text = re.sub(r'<\|[^|]*\|>', '', text)  # catch any remaining special tokens
        text = text.strip()
        if not text:
            text = raw.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parse failed: {e} | text starts with: {text[:100]!r} | text ends with: {text[-100:]!r}")
            pass

        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            try:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass
        if "```" in text:
            try:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                pass

        # Find the outermost JSON object by matching braces (respecting strings)
        start = text.find('{')
        if start != -1:
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start, len(text)):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break

        # Last resort: try to repair truncated JSON by closing open braces/brackets
        if start != -1:
            # The JSON was likely truncated — try to close all open structures
            truncated = text[start:]
            # Remove any trailing incomplete string (after last complete key-value)
            import re as _re
            # Find last complete value (ends with , or } or ] or number or "true"/"false"/"null" or quoted string)
            last_good = _re.search(r'[}\]"\d](?:,?\s*$)', truncated)
            if last_good:
                truncated = truncated[:last_good.end()].rstrip().rstrip(',')

            # Count open braces and brackets
            open_braces = truncated.count('{') - truncated.count('}')
            open_brackets = truncated.count('[') - truncated.count(']')

            # Check if we're inside a string (odd number of unescaped quotes)
            in_string = False
            quote_count = 0
            for i, ch in enumerate(truncated):
                if ch == '"' and (i == 0 or truncated[i-1] != '\\'):
                    quote_count += 1
            if quote_count % 2 == 1:
                truncated += '"'

            repair = truncated + (']' * max(0, open_brackets)) + ('}' * max(0, open_braces))
            try:
                result = json.loads(repair)
                logger.warning(f"Repaired truncated JSON ({len(raw)} chars, closed {open_braces} braces, {open_brackets} brackets)")
                return result
            except json.JSONDecodeError:
                pass

        logger.error(f"Could not parse JSON from AI response ({len(raw)} chars). First 200: {raw[:200]!r} ... Last 200: {raw[-200:]!r}")
        return {}

    async def create_embedding(self, text: str, model: str | None = None) -> list[float]:
        model = model or settings.ai_model_embedding
        payload = {
            "model": model,
            "input": text,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

    async def create_embeddings_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        model = model or settings.ai_model_embedding
        payload = {
            "model": model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
