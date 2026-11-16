# -*- coding: utf-8 -*-
"""③ 쿼리 재작성 노드 (LLM).   읽는 키: difference  →  쓰는 키: rewritten_queries
difference 원소 1개마다 틀린 표현과 고친 표현을 보고 근거 규정을 찾을 검색 쿼리 1개를 만든다.
rewritten_queries[i] 는 difference[i] 에 대한 쿼리. 아이 문장 전체는 LLM에 넘기지 않는다.
LLM을 바꿀 때는 config.QUERY_LLM_ID, 프롬프트를 바꿀 때는 이 파일의 QUERY_SYSTEM / QUERY_EXAMPLES 만 고친다."""
import re

from .. import config
from ..models import llm

QUERY_SYSTEM = (
    "너는 국립국어원 「한글 맞춤법」·「표준어 규정」 해설에서 근거 조항을 찾기 위한 검색 쿼리를 만드는 도우미야. "
    "틀린 표현과 고친 표현을 비교해 무엇이 달라졌는지 보고, 이 수정이 어떤 맞춤법 규정에 해당하는지 판단한 뒤 "
    "그 규정을 찾을 수 있는 검색 문장을 한 줄로 써. "
    "규정의 핵심 개념어(준말, 된소리, 띄어쓰기, 의존 명사, 보조 용언, 어미, 부사 끝음절 '-이/-히', "
    "사이시옷, 두음 법칙, 받침, 표준어 등)를 꼭 넣고, 설명이나 따옴표 없이 검색 문장만 출력해."
)
# 작은 모델이 형식을 따르도록 예시 3개를 함께 넣음 (few-shot)
QUERY_EXAMPLES = [
    ("됬어요", "됐어요", "준말 규칙: 'ㅚ' 뒤에 '-어, -었-'이 어울려 'ㅙ, ㅙㅆ'으로 줄어들 때 준 대로 적음 (되어 → 돼, 되었다 → 됐다)"),
    ("할수있다", "할 수 있다", "의존 명사 '수'를 앞말과 띄어 쓰는 규칙"),
    ("깨끗히", "깨끗이", "부사의 끝음절을 '-이'로 적는 경우와 '-히'로 적는 경우"),
]


def _messages(before: str, after: str) -> list[dict]:
    msgs = [{"role": "system", "content": QUERY_SYSTEM}]
    for b, a, q in QUERY_EXAMPLES:
        msgs += [{"role": "user", "content": f"틀린 표현: {b}\n고친 표현: {a}"},
                 {"role": "assistant", "content": q}]
    msgs.append({"role": "user", "content": f"틀린 표현: {before}\n고친 표현: {after}"})
    return msgs


def _clean(text: str) -> str:
    """첫 줄만 남기고 '쿼리:' 같은 앞머리와 따옴표 정리."""
    q = next((l for l in text.splitlines() if l.strip()), "").strip()
    return re.sub(r"^(검색\s*)?(쿼리|문장)\s*[:：]\s*", "", q).strip(" \"“”'")


def rewrite_queries(state: dict) -> dict:
    queries = []
    for d in state["difference"]:
        q = _clean(llm.chat(config.QUERY_LLM_ID, _messages(d["before"], d["after"]), max_new_tokens=64))
        queries.append(q or f"'{d['before']}'을(를) '{d['after']}'(으)로 고치는 맞춤법 규정")   # 빈 출력이면 기본 쿼리
    return {"rewritten_queries": queries}


def preload():
    llm.load(config.QUERY_LLM_ID)
