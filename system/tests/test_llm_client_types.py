from __future__ import annotations

from llm_client_types import is_retriable
from exceptions import LLMError


def test_is_retriable_llmerror():
    err = LLMError("timeout", provider="openai", retriable=True)
    assert is_retriable(err) is True
