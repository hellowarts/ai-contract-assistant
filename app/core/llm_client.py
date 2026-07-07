from __future__ import annotations

import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_API_KEY_PATTERN = re.compile(r"^sk-(proj-)?[A-Za-z0-9_-]{20,}$")
_INVALID_KEY_MARKERS = {
    "",
    "your-api-key",
    "your_openai_api_key",
    "changeme",
    "change-me",
    "replace-me",
    "sk-xxxxxxxxxxxxxxxx",
}


def get_api_key() -> str:

    load_dotenv()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()

    if not api_key:

        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. AI 워크플로우를 실행할 수 없습니다.")

    if api_key.lower() in _INVALID_KEY_MARKERS:

        raise RuntimeError("OPENAI_API_KEY가 유효하지 않은 값입니다. AI 워크플로우를 실행할 수 없습니다.")

    if not _API_KEY_PATTERN.match(api_key):

        raise RuntimeError("OPENAI_API_KEY 형식이 올바르지 않습니다. AI 워크플로우를 실행할 수 없습니다.")

    return api_key


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:

    get_api_key()

    return ChatOpenAI(
        model="gpt-5",
        temperature=0,
    )


def verify_ai_ready() -> ChatOpenAI:

    llm = get_llm()

    try:

        response = llm.invoke("OK")

    except Exception as exc:

        raise RuntimeError("AI 호출 검증에 실패했습니다. API 키와 네트워크를 확인하세요.") from exc

    content = getattr(response, "content", None)

    if content is None and not str(response).strip():

        raise RuntimeError("AI 응답이 비어 있습니다. AI 워크플로우를 실행할 수 없습니다.")

    return llm