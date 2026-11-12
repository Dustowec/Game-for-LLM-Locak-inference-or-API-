"""burt/llm_client.py — §1, §31. Async-клиент для LLM (LM Studio / OpenAI).

Чистый I/O слой: только HTTP-вызовы, без игровой логики.
Асинхронный. Тестируется через unittest.mock.AsyncMock.

Структура ответа API:
    {
        "choices": [{
            "message": {"role": "assistant", "content": "..."},
            "finish_reason": "stop"
        }]
    }

Fallback: если LLM падает 2 раза подряд — возвращаем дефолтный ответ.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import aiohttp

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------

_MODEL = config.MODEL
_TEMPERATURE = config.TEMPERATURE
_MAX_TOKENS = 512

# URLs
_BASE_URLS = {
    "lm_studio": config.LM_STUDIO_URL,
    "openai": config.OPENAI_API_URL or "",
}

# Fallback answer when LLM is unreachable twice in a row
_FALLBACK_ANSWER = "Darkness consumes. You don't remember where you were going."

# Number of retries on transient failure
_MAX_RETRIES = 1


# ---------------------------------------------------------------------
# Low-level API call
# ---------------------------------------------------------------------

async def create_chat_completion(
    messages: list[dict],
) -> dict[str, Any]:
    """POST к /v1/chat/completions. Возвращает raw JSON response."""
    backend = config.BACKEND.lower() if config.BACKEND else "lm_studio"
    base_url = _BASE_URLS.get(backend, _BASE_URLS["lm_studio"])
    
    url = f"{base_url}/chat/completions"
    
    payload = {
        "model": _MODEL,
        "messages": messages,
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 404:
                    # Try alternative endpoint (some LM Studio versions use /chat without /v1 prefix)
                    alt_url = f"{base_url}/chat/completions"
                    async with session.post(alt_url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp2:
                        data = await resp2.json()
                        return data
                
                if not (200 <= resp.status < 300):
                    body = await resp.text()
                    raise RuntimeError(f"LLM API error {resp.status}: {body[:200]}")
                
                data = await resp.json()
                return data
        except asyncio.TimeoutError:
            raise ConnectionError("LLM request timed out")
        except aiohttp.ClientError as e:
            raise ConnectionError(f"LLM network error: {e}")


# ---------------------------------------------------------------------
# High-level call
# ---------------------------------------------------------------------

async def call_llm(
    system_msg: str,
    user_msg: str,
    messages_history: Optional[list[dict]] = None,
) -> tuple[str, list[dict]]:
    """Вызвать LLM. Вернуть (ответ_текст, обновлённая_история).

    Схема:
    1. Собираем messages [system + history + user].
    2. Вызываем create_chat_completion.
    3. Парсим ответ, добавляем в историю.
    4. Если ошибка → retry 1 раз.
    5. Если второй раз ошибка → fallback_answer().

    При ошибке НЕ выбрасываем исключение — возвращаем fallback.
    """
    if messages_history is None:
        messages_history = []

    full_messages = [
        {"role": "system", "content": system_msg},
        *messages_history,
        {"role": "user", "content": user_msg},
    ]

    for attempt in range(_MAX_RETRIES + 1):
        try:
            raw = await create_chat_completion(full_messages)
            answer = extract_answer(raw)
            
            # Добавляем в историю
            messages_history.append({"role": "assistant", "content": answer})
            return answer, messages_history
            
        except Exception as e:
            logger.warning(f"LLM call failed (attempt {attempt+1}/{_MAX_RETRIES+1}): {e}")
            if attempt < _MAX_RETRIES:
                continue
            # После последнего ретрай — fallback
            logger.error("All attempts failed, using fallback")
            return _FALLBACK_ANSWER, messages_history


def extract_answer(raw_response: dict) -> str:
    """Извлечь текст ответа из raw response."""
    choices = raw_response.get("choices")
    if not choices:
        return ""
    
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        return ""
    
    return content.strip()


def extract_finish_reason(raw_response: dict) -> Optional[str]:
    """Finish reason: 'stop', 'length', etc."""
    choices = raw_response.get("choices")
    if not choices:
        return None
    return choices[0].get("finish_reason")
