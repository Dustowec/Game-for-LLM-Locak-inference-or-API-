"""Тесты для burt/llm_client.py — §1, §31.

Асинхронный клиент LLM (LM Studio / OpenAI).
Все тесты через unittest.mock.AsyncMock - без реального HTTP.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config
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


def _wrap_single_response(response_json):
    """Обернуть dict в мок aiohttp-ответа с .json()."""
    mock_response = MagicMock()
    mock_response.status = 200
    
    async def rj():
        return response_json
    
    async def rtext():
        return '{"error":"test"}'
    
    mock_response.json = rj
    mock_response.text = rtext
    return mock_response


def _patch_aiohttp(captured: dict | None = None, response_json=None):
    """Патч aiohttp.ClientSession.
    
    Если captured — сохраняет kwargs POST'а в captured["post_kwargs"].
    Возвращает контекстный менеджер (patch).
    """
    if response_json is None:
        response_json = {"choices": [{"message": {"content": "ok"}}]}
    
    mock_response = _wrap_single_response(response_json)
    
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    
    mock_session = MagicMock()
    
    def post_side_effect(*args, **kwargs):
        if captured is not None:
            captured["post_kwargs"] = kwargs
        return mock_cm
    
    mock_session.post.side_effect = post_side_effect
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    
    patcher = patch("aiohttp.ClientSession")
    mock_sess_cls = patcher.start()
    mock_sess_cls.return_value = session_cm
    return patcher


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
        user = "Меню: 0. идти на north\n"
        
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {"choices": [{"message": {"content": "Я иду на north."}}]}
            
            result, history = await llm_client.call_llm(system, user, [])
            
            assert result == "Я иду на north."
            assert len(history) == 1
            assert history[0]["role"] == "assistant"
            assert history[0]["content"] == "Я иду на north."

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

    # -----------------------------------------------------------------
    # Логика валидации ответа (пустой content / finish_reason=length)
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_length_with_content_accepted_and_warned(self, caplog):
        """L2: finish_reason=length + непустой content -> принять + WARN, без ретрая."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {
                "choices": [{
                    "message": {"content": "Partial answer..."},
                    "finish_reason": "length",
                }]
            }
            
            with caplog.at_level(logging.WARNING):
                result, history = await llm_client.call_llm("sys", "user", [])
            
            assert result == "Partial answer..."
            assert len(history) == 1
            assert history[0]["content"] == "Partial answer..."
            assert mock_create.call_count == 1, "length с непустым content НЕ должен ретраиться"
            
            # WARN про обрезание
            warns = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
            assert any("length" in m.lower() for m in warns), \
                f"ожидали WARN с 'length', получили: {warns}"

    @pytest.mark.asyncio
    async def test_empty_content_retries(self):
        """L3: пустой content -> ретрай, пустая реплика НЕ аппендится в историю."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                {"choices": [{"message": {"content": ""}}]},
                {"choices": [{"message": {"content": "Ok"}}]},
            ]
            
            result, history = await llm_client.call_llm("sys", "user", [])
            
            assert result == "Ok"
            assert len(history) == 1, "в истории должна быть только успешная реплика"
            assert history[0]["content"] == "Ok"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_content_both_attempts_returns_fallback(self):
        """L4: оба пустые -> fallback, история НЕ растёт."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                {"choices": [{"message": {"content": ""}}]},
                {"choices": [{"message": {"content": ""}}]},
            ]
            
            result, history = await llm_client.call_llm("sys", "user", [])
            
            assert result == llm_client._FALLBACK_ANSWER
            assert len(history) == 0, "пустые реплики не должны попадать в историю"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_content_with_length_retries(self):
        """L5: пустой content + finish_reason=length -> тоже ретрай."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]},
                {"choices": [{"message": {"content": "Ok"}}]},
            ]
            
            result, history = await llm_client.call_llm("sys", "user", [])
            
            assert result == "Ok"
            assert len(history) == 1
            assert history[0]["content"] == "Ok"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_history_not_mutated_between_retries(self):
        """L6: после 1-й пустой попытки в истории НЕТ assistant-msg."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.side_effect = [
                {"choices": [{"message": {"content": ""}}]},
                {"choices": [{"message": {"content": "Ok"}}]},
            ]
            
            history_arg = []
            result, history = await llm_client.call_llm("sys", "user", history_arg)
            
            assert history is history_arg, "функция должна вернуть тот же объект истории"
            assert len(history) == 1
            assert history[0]["content"] == "Ok"

    # -----------------------------------------------------------------
    # Логирование usage
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_usage_logged_at_info(self, caplog):
        """L7: usage логируется на INFO: prompt, completion, finish_reason."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {
                "choices": [{
                    "message": {"content": "Hi"},
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }
            
            with caplog.at_level(logging.INFO):
                await llm_client.call_llm("sys", "user", [])
            
            infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
            assert any(
                "llm usage" in m
                and "prompt=100" in m
                and "completion=50" in m
                and "finish=stop" in m
                for m in infos
            ), f"ожидали INFO 'llm usage: prompt=100 completion=50 finish=stop', получили: {infos}"

    @pytest.mark.asyncio
    async def test_usage_absent_does_not_crash(self, caplog):
        """L8: нет usage в ответе — не падаем, INFO-строка всё равно пишется."""
        with patch.object(llm_client, "create_chat_completion") as mock_create:
            mock_create.return_value = {
                "choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}],
            }
            
            with caplog.at_level(logging.INFO):
                result, history = await llm_client.call_llm("sys", "user", [])
            
            assert result == "Hi"
            assert len(history) == 1
            
            infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
            assert any("llm usage" in m for m in infos), \
                f"INFO 'llm usage' должен быть даже без usage, получили: {infos}"


# ---------------------------------------------------------------------
# TestBackendSwitching
# ---------------------------------------------------------------------

class TestBackendSwitching:
    """Поддержка двух бэкендов."""

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
    """Константы модуля доступны для тестирования."""

    def test_max_retries_is_one(self):
        assert llm_client._MAX_RETRIES == 1

    def test_fallback_not_empty(self):
        assert llm_client._FALLBACK_ANSWER
        assert len(llm_client._FALLBACK_ANSWER) > 0


# ---------------------------------------------------------------------
# TestCreateChatCompletion (low-level mock tests)
# ---------------------------------------------------------------------

class TestCreateChatCompletion:
    """Low-level функция с моками aiohttp."""

    @pytest.mark.asyncio
    async def test_successful_post_returns_raw_data(self):
        """Успешный POST запрос возвращает JSON response."""
        expected_json = {"choices": [{"message": {"content": "test answer"}}]}
        
        patcher = _patch_aiohttp(response_json=expected_json)
        try:
            result = await llm_client.create_chat_completion([])
            assert result == expected_json
        finally:
            patcher.stop()

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
        
        captured: dict = {}
        patcher = _patch_aiohttp(
            captured=captured,
            response_json={"choices": [{"message": {"content": "Hi"}}]},
        )
        try:
            await llm_client.create_chat_completion(test_messages)
        finally:
            patcher.stop()
        
        payload = captured["post_kwargs"]["json"]
        assert "messages" in payload
        assert payload["messages"][0]["role"] == "system"
        assert payload["temperature"] == 0.95

    # -----------------------------------------------------------------
    # Контракт: max_tokens и timeout тянутся из config
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_payload_uses_config_max_tokens(self):
        """P1: payload["max_tokens"] == config.MAX_TOKENS (не хардкод 512)."""
        captured: dict = {}
        patcher = _patch_aiohttp(
            captured=captured,
            response_json={"choices": [{"message": {"content": "Hi"}}]},
        )
        try:
            await llm_client.create_chat_completion([{"role": "user", "content": "hi"}])
        finally:
            patcher.stop()
        
        payload = captured["post_kwargs"]["json"]
        assert payload["max_tokens"] == config.MAX_TOKENS, (
            f"max_tokens={payload['max_tokens']}, а config.MAX_TOKENS={config.MAX_TOKENS} — "
            "клиент обязан тянуть бюджет из конфига"
        )

        @pytest.mark.asyncio
        async def test_payload_uses_config_timeout(self):
            """P2: timeout в POST == config.LLM_TIMEOUT_SECONDS."""
        captured: dict = {}
        patcher = _patch_aiohttp(
            captured=captured,
            response_json={"choices": [{"message": {"content": "Hi"}}]},
        )
        try:
            await llm_client.create_chat_completion([{"role": "user", "content": "hi"}])
        finally:
            patcher.stop()
        
        timeout = captured["post_kwargs"]["timeout"]
        assert timeout.total == config.LLM_TIMEOUT_SECONDS, (
            f"timeout.total={timeout.total}, а config.LLM_TIMEOUT_SECONDS={config.LLM_TIMEOUT_SECONDS}"
        )

    @pytest.mark.asyncio
    async def test_http_error_body_not_truncated(self):
        """П.5: HTTP error body NOT truncated at 200 chars in message."""
        body_text = "E" * 500

        mock_response = MagicMock()
        mock_response.status = 500

        async def fake_json():
            return {"choices": []}

        async def fake_text():
            return body_text

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

            with pytest.raises(RuntimeError) as exc_info:
                await llm_client.create_chat_completion([])

        msg = str(exc_info.value)
        assert len(msg) > 300, (
            f"error body must not be truncated at 200; message len = {len(msg)}"
        )