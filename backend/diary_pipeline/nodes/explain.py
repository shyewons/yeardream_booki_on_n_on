# -*- coding: utf-8 -*-
"""⑤ 설명문 생성 노드 (LLM, 초등학생 눈높이).   읽는 키: difference, rewritten_queries, evidence_docs  →  쓰는 키: explanations
수정 1건마다 (틀린 표현, 고친 표현, 쿼리, 근거 문서)를 LLM에 넘겨 설명문 1개. explanations[i] 는 difference[i] 의 설명.
LLM을 바꿀 때는 config.EXPLAIN_LLM_ID, 말투·규칙을 바꿀 때는 이 파일의 EXPLAIN_SYSTEM / EXPLAIN_EXAMPLE 만 고친다."""
from .. import config
from ..models import llm

EXPLAIN_SYSTEM = (
    "너는 초등학생의 눈높이에서 맞춤법 규정을 설명하는 선생님이야.\n"
    "아이가 쓴 표현(틀린 표현)과 고친 표현, 그리고 국립국어원 맞춤법 해설에서 찾은 근거 문서를 받아서 "
    "왜 그렇게 고쳐야 하는지 초등학생에게 설명해.\n"
    "지켜야 할 규칙:\n"
    "1. 해요체로, 2~3문장으로 짧게 써.\n"
    "2. '어간', '어미', '의존 명사' 같은 어려운 문법 용어는 쓰지 말고, 꼭 필요하면 쉬운 말로 풀어서 써.\n"
    "3. 근거 문서에 있는 내용만 바탕으로 설명하고, 근거 문서에 없는 규칙은 지어내지 마.\n"
    "4. 틀린 표현과 고친 표현을 한 번씩 꼭 보여 줘.\n"
    "5. 아이를 혼내지 말고, 다음에 기억하기 쉬운 요령을 한 가지 알려 줘.\n"
    "6. 조항 번호나 문서 이름은 말하지 말고, 설명문만 출력해."
)
# 작은 모델이 말투와 길이를 따르도록 예시 1개를 함께 넣음 (few-shot)
EXPLAIN_EXAMPLE = {
    "before": "깨끗히", "after": "깨끗이",
    "query": "부사의 끝음절을 '-이'로 적는 경우와 '-히'로 적는 경우",
    "evidence": "부사의 끝음절이 분명히 '이'로만 나는 것은 '-이'로 적고, '히'로만 나거나 '이'나 '히'로 나는 것은 '-히'로 적는다. "
                "'ㅅ' 받침 뒤에서는 '-이'로 적는다. 깨끗이, 느긋이, 버젓이 …",
    "answer": "'깨끗히'가 아니라 '깨끗이'라고 써요. '깨끗'처럼 끝 글자에 'ㅅ' 받침이 있는 말 뒤에는 '히'가 아니라 '이'를 붙이기로 약속했거든요. "
              "'느긋이', '버젓이'도 같은 친구들이니까 'ㅅ 받침 뒤에는 이!'라고 기억해 보세요.",
}


def _prompt(before: str, after: str, query: str, evidence: str) -> str:
    return f"틀린 표현: {before}\n고친 표현: {after}\n찾아본 규정: {query}\n근거 문서:\n{evidence}"


def _messages(before: str, after: str, query: str, evidence: str) -> list[dict]:
    ex = EXPLAIN_EXAMPLE
    return [
        {"role": "system", "content": EXPLAIN_SYSTEM},
        {"role": "user", "content": _prompt(ex["before"], ex["after"], ex["query"], ex["evidence"])},
        {"role": "assistant", "content": ex["answer"]},
        {"role": "user", "content": _prompt(before, after, query, evidence)},
    ]


def explain(state: dict) -> dict:
    explanations = []
    for d, q, doc in zip(state["difference"], state["rewritten_queries"], state["evidence_docs"]):
        text = llm.chat(config.EXPLAIN_LLM_ID, _messages(d["before"], d["after"], q, doc["content"]),
                        max_new_tokens=200, repetition_penalty=1.1).strip()
        explanations.append(text or f"'{d['before']}'는 '{d['after']}'(이)라고 써야 맞아요.")   # 빈 출력 대비
    return {"explanations": explanations}


def preload():
    llm.load(config.EXPLAIN_LLM_ID)
