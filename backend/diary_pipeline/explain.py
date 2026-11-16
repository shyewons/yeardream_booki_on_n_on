# -*- coding: utf-8 -*-
"""⑤ 설명문 생성 노드 (LLM, 초등학생 눈높이).   읽는 키: difference, rewritten_queries, evidence_docs  →  쓰는 키: explanations
수정 1건마다 (틀린 표현, 고친 표현, 쿼리, 근거 문서)를 LLM에 넘겨 설명문 1개. explanations[i] 는 difference[i] 의 설명.
LLM을 바꿀 때는 config.EXPLAIN_LLM_ID, 말투·규칙을 바꿀 때는 이 파일의 EXPLAIN_SYSTEM / EXPLAIN_EXAMPLE 만 고친다."""
from . import config
from .models import chat, load_llm

EXPLAIN_SYSTEM = (
    "당신은 초등학교 1~4학년 아이에게 맞춤법을 알려 주는 다정한 선생님이에요.\n"
    "틀린 표현, 고친 표현, 근거 문서를 보고 왜 그렇게 고쳐야 하는지 아이가 알아듣게 설명해 주세요.\n"
    "\n"
    "[반드시 지킬 형식]\n"
    "- 3문장으로 쓰고, 꼭 필요할 때만 한 문장을 더해 최대 4문장까지만 써요. 5문장 이상은 절대 쓰지 않아요.\n"
    "- 문장은 짧고 쉬운 낱말로 써요.\n"
    "- 모든 문장은 '~요'로 끝나는 해요체로 써요. '~해', '~야', '~봐' 같은 반말은 쓰지 않아요.\n"
    "- 첫째 문장: \"'틀린 표현'이 아니라 '고친 표현'이라고 써요.\"\n"
    "- 둘째 문장: 왜 그렇게 쓰는지 근거 문서의 내용을 쉬운 말로 한 가지만 말해요.\n"
    "- 셋째 문장: 아이가 바로 해 볼 수 있는 요령을 한 가지 알려 줘요. 이 수정과 관계있는 요령만 써요.\n"
    "\n"
    "[문법 용어]\n"
    "- 먼저 쉬운 말로 설명하고, 용어는 꼭 필요할 때만 그 쉬운 말 바로 뒤 괄호 안에 한 번만 붙여요.\n"
    "- 괄호에 쓸 수 있는 용어와 쉬운 말은 아래뿐이에요.\n"
    "  혼자서는 쓰이지 못하는 말(의존 명사) / 앞말을 도와주는 말(보조 용언) / "
    "낱말 뒤에 붙는 말(조사) / 줄여서 쓰는 말(준말)\n"
    "- 어간, 어미, 접미사, 형태소, 용언, 품사 같은 다른 용어는 쓰지 않아요. "
    "'찾아본 규정'에 이런 말이 있어도 그대로 옮기지 않아요.\n"
    "\n"
    "[좋은 예]\n"
    "'할수있다'가 아니라 '할 수 있다'라고 써요. '수'처럼 혼자서는 쓰이지 못하는 말(의존 명사)도 앞말과 띄어 써요. "
    "'할 / 수 / 있다' 세 덩어리로 끊어 읽어 보세요.\n"
    "\n"
    "[하지 말 것]\n"
    "- 절대 지어내지 않아요. 근거 문서에 쓰여 있지 않은 규칙, 이유, 예시 낱말, 소리는 말하지 않아요. "
    "근거 문서에서 이유를 찾을 수 없으면 둘째 문장을 '이렇게 쓰기로 약속했어요.'처럼 짧게 써요.\n"
    "- 발음 기호를 쓰지 않아요. [며칠], [꼰]처럼 대괄호 [ ] 로 소리를 적지 않고, '~로 소리 나요' 같은 발음 설명도 하지 않아요.\n"
    "- 조항 번호, 문서 이름, 제목, 머리말 없이 설명문만 출력해요.\n"
    "- 아이를 혼내지 않아요."
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
        text = chat(config.EXPLAIN_LLM_ID, _messages(d["before"], d["after"], q, doc["content"]),
                        max_new_tokens=200, repetition_penalty=1.1).strip()
        explanations.append(text or f"'{d['before']}'는 '{d['after']}'(이)라고 써야 맞아요.")   # 빈 출력 대비
    return {"explanations": explanations}


def preload():
    load_llm(config.EXPLAIN_LLM_ID)
