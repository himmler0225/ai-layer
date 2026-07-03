from openai import APIStatusError
import json

from app.utils.llm_errors import should_retry, user_message


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.request = None
        self.headers = {}


def test_should_retry_on_503():
    exc = APIStatusError("err", response=_FakeResponse(503), body={})
    assert should_retry(exc) is True


def test_should_retry_on_connection_drop():
    assert should_retry(json.JSONDecodeError("Expecting value", "", 0)) is True
    assert should_retry(ConnectionError("Connection reset by peer")) is True


def test_user_message_400_vietnamese():
    exc = APIStatusError("bad", response=_FakeResponse(400), body={})
    msg = user_message(exc)
    assert "LLM" in msg
    assert "prompt" in msg.lower() or "tool" in msg.lower()
