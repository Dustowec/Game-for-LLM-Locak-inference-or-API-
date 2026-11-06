"""Тесты для burt/llm_client.py — §1, §31.

Асинхронный клиент LLM (LM Studio / OpenAI).
Все тесты через unittest.mock.AsyncMock - без реального HTTP.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from burt import llm_client


# ---------------------------------------------------------------------
# Фикстуры и помощники
# ---------------------------------------------------------------------

def _make_response(content="Привет", finish_reason=None):
    """Создать мок-ответ от API."""
    resp = MagicMock()
    resp.status = 200
    
    async def json():
        data = {"choices": [{"message": {"role": "assistant", "content": content}}]}
        if finish_reason:
            data["choices"][0]["finish_reason"] = finish_reason
        return data
    
    async def text():
        return '{"error":"test"}'
    
    resp.json = json
    resp.text = text
    return resp


# ---------------------------------------------------------------------
# Test extract_answer
# ---------------------------------------------------------------------

class TestExtractAnswer:
    """extract_answer парсит raw response и возвращает текст."""

    def test_simple_response(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": "Привет!"}}]}
        assert llm_client.extract_answer(raw) == "Привет!"

    def test_multiline_content(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": "Стр.\n  Отступ"}}]}
        assert llm_client.extract_answer(raw) == "Стр.\n  Отступ"

    def test_empty_choices(self):
        raw = {"choices": []}
        assert llm_client.extract_answer(raw) == ""

    def test_no_choices_key(self):
        raw = {}
        assert llm_client.extract_answer(raw) == ""

    def test_message_has_no_content(self):
        raw = {"choices": [{"message": {}}]}
        assert llm_client.extract_answer(raw) == ""

    def test_extra_whitespace_stripped(self):
        raw = {"choices": [{"message": {"content": "  hello  "}}]}
        assert llm_client.extract_answer(raw) == "hello"


# ---------------------------------------------------------------------
# Test extract_finish_reason
# ---------------------------------------------------------------------

class TestExtractFinishReason:
    def test_stop(self):
        raw = {"choices": [{"finish_reason": "stop"}]}
        assert llm_client.extract_finish_reason(raw) == "stop"

    def test_length(self):
        raw = {"choices": [{"finish_reason": "length"}]}
        assert llm_client.extract_finish_reason(raw) == "length"

    def test_empty_choices(self):
        raw = {"choices": []}
        assert llm_client.extract_finish_reason(raw) is None

    def test_no_choices(self):
        raw = {}
        assert llm_client.extract_finish_reason(raw) is None

# ---------------------------------------------------------------------
# Test call_llm (high-level)
# ---------------------------------------------------------------------

class TestCallLlm:
    """High-level вызов call_llm с моками create_chat_completion."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        system = "Ты Бурт."
        user = "Меню: 0. идти на север\n"
        
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {"choices": [{"message": {"content": "Я иду на север."}}]}
            
            result, history = await llm_client.call_llm(system, user, [])
            
            assert result == "Я иду на север."
            assert len(history) == 1
            assert history[0]["role"] == "assistant"
            assert history[0]["content"] == "Я иду на север."

    @pytest.mark.asyncio
    async def test_history_accumulation(self):
        """История растёт при каждом вызове."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                {"choices": [{"message": {"content": "Ответ 1"}}]},
                {"choices": [{"message": {"content": "Ответ 2"}}]},
            ]
            
            _, hist1 = await llm_client.call_llm("sys", "user1", [])
            assert len(hist1) == 1
            
            _, hist2 = await llm_client.call_llm("sys", "user2", hist1)
            assert len(hist2) == 2

    @pytest.mark.asyncio
    async def test_first_attempt_fails_second_succeeds(self):
        """Retry logic: first fail, second success."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                RuntimeError("network error"),
                {"choices": [{"message": {"content": "success"}}]},
            ]
            
            result, _ = await llm_client.call_llm("sys", "user", [])
            assert result == "success"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_double_fail_returns_fallback(self):
        """После двух неудач — fallback answer."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = RuntimeError("permanent error")
            
            result, _ = await llm_client.call_llm("sys", "user", [])
            assert result == llm_client._FALLBACK_ANSWER

    @pytest.mark.asyncio
    async def test_all_attempts_fail_uses_fallback(self):
        """Если все попытки провалились — точно fallback."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = ConnectionError("timeout")
            
            result, _ = await llm_client.call_llm("sys", "user", [])
            assert result == llm_client._FALLBACK_ANSWER

    @pytest.mark.asyncio
    async def test_system_msg_included_in_call(self):
        """system_msg передаётся в messages."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {"choices": [{"message": {"content": "OK"}}]}
            
            await llm_client.call_llm("My system prompt", "user msg", [])
            
            # Проверяем что был вызван с правильными message
            calls_args = mock_create.call_args_list[0][0][0]
            assert calls_args[0]["role"] == "system"
            assert calls_args[0]["content"] == "My system prompt"

    @pytest.mark.asyncio
    async def test_none_history_is_handled(self):
        """None переданная вместо списка - пустой список."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {"choices": [{"message": {"content": "OK"}}]}
            
            result, history = await llm_client.call_llm("sys", "user", None)
            assert result == "OK"
            assert len(history) == 1



# ---------------------------------------------------------------------
# TestBackendSwitching
# ---------------------------------------------------------------------

class TestBackendSwitching:
    """оддержка двух бэкендов."""

    def test_url_for_lm_studio(self):
        assert llm_client._BASE_URLS["lm_studio"] == "http://localhost:1234/v1"

    def test_openai_key_exists(self):
        assert "openai" in llm_client._BASE_URLS

    def test_model_from_config(self):
        assert llm_client._MODEL == "local-model"

    def test_temperature_from_config(self):
        assert llm_client._TEMPERATURE == 0.95


# ---------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------

class TestConstants:
    """онстанты модуля доступны для тестирования."""

    def test_max_retries_is_one(self):
        assert llm_client._MAX_RETRIES == 1

    def test_fallback_not_empty(self):
        assert llm_client._FALLBACK_ANSWER
        assert len(llm_client._FALLBACK_ANSWER) > 0

    def test_max_tokens_constant(self):
        assert llm_client._MAX_TOKENS == 512


# ---------------------------------------------------------------------
# TestCreateChatCompletion (low-level mock tests)
# ---------------------------------------------------------------------

class TestCreateChatCompletion:
    """Low-level функция с моками aiohttp."""

    @pytest.mark.asyncio
    async def test_successful_post_returns_raw_data(self):
        """спешный POST запрос возвращает JSON response."""
        mock_response = MagicMock()
        mock_response.status = 200
        expected_json = {"choices": [{"message": {"content": "test answer"}}]}
        
        async def fake_json():
            return expected_json
        
        mock_response.json = fake_json
        
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_cls.return_value = session_cm
            
            result = await llm_client.create_chat_completion([])
            
            assert result == expected_json

    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self):
        """HTTP 500 -> RuntimeError."""
        mock_response = MagicMock()
        mock_response.status = 500
        
        async def fake_json():
            return {"choices": []}
        
        async def fake_text():
            return '{"error":"server error"}'
        
        mock_response.json = fake_json
        mock_response.text = fake_text
        
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_cls.return_value = session_cm
            
            with pytest.raises(RuntimeError, match="LLM API error"):
                await llm_client.create_chat_completion([])


    @pytest.mark.asyncio
    async def test_timeout_raises_connection_error(self):
        """Timeout -> ConnectionError."""
        mock_response = MagicMock()
        mock_response.status = 200
        
        async def rj():
            raise asyncio.TimeoutError("timed out")
        
        mock_response.json = rj
        
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_cls.return_value = session_cm
            
            with pytest.raises(ConnectionError, match="timed out"):
                await llm_client.create_chat_completion([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_messages_passed_in_payload(self):
        """messages передаются в JSON payload."""
        test_messages = [
            {"role": "system", "content": "You are Burt"},
            {"role": "user", "content": "Hello"},
        ]
        
        captured_payloads = []
        
        # Создаём мок целиком
        mock_response = MagicMock()
        mock_response.status = 200
        
        async def rj():
            return {"choices": [{"message": {"content": "Hi"}}]}
        
        mock_response.json = rj
        
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        
        def post_side_effect(*args, **kwargs):
            captured_payloads.append(kwargs.get("json", {}))
            return mock_cm
        
        mock_session.post.side_effect = post_side_effect
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=None)
        
        with patch("aiohttp.ClientSession") as mock_sess_cls:
            mock_sess_cls.return_value = session_cm
            
            await llm_client.create_chat_completion(test_messages)
        
        # проверяем что в payload были правильные messages
        assert len(captured_payloads) == 1
        assert "messages" in captured_payloads[0]
        assert captured_payloads[0]["messages"][0]["role"] == "system"
        assert captured_payloads[0]["temperature"] == 0.95
