# -*- coding: utf-8 -*-
"""[임시 노드] 파일명: demo_nodes.py

모델(et5 / Kanana / bge-m3)과 벡터 DB가 없어도 화면 흐름을 시험할 수 있도록, diary_pipeline/nodes 의 모델 노드를 흉내 내는 함수들이다.
읽는 키와 쓰는 키는 진짜 노드와 똑같다 (diary_pipeline/nodes/__init__.py 표 참고). 그래서 writing_api.py 에서 노드 이름만 바꿔 끼우면 된다.
실제 교정이 아니다. 아래 DEMO_FIXES 에 있는 표현만 바꾼다.
"""
from diary_pipeline.input_validation import fit_josa       # 받침에 맞는 조사(을/를) 고르기

DEMO_FIXES = {"됬": "됐", "안되요": "안 돼요", "몇일": "며칠", "웬지": "왠지", "어떻해": "어떡해", "할께": "할게", "갈께": "갈게",
              "깨끗히": "깨끗이", "할수있다": "할 수 있다"}


def spell_correct(state: dict) -> dict:
    """① 임시: DEMO_FIXES 로만 바꾼다. 끝에 마침표를 붙이는 et5 의 버릇도 흉내 내어 ②의 문장부호 무시를 시험한다."""
    text = state["original_sentence"]
    for wrong, right in DEMO_FIXES.items():
        text = text.replace(wrong, right)
    if not text.endswith((".", "?", "!")):
        text += "."
    return {"revised_sentence": text}


def rewrite_queries(state: dict) -> dict:
    """③ 임시: 수정 1건당 쿼리 1개를 문장 틀로 만들고, 판정 유형은 전부 '①표기만'으로 둔다 (진짜 노드는 Kiwi 로 판정한다)."""
    diffs = state["difference"]
    return {"rewritten_queries": [f"'{d['before']}'와 '{d['after']}'의 맞춤법 구분 규칙" for d in diffs],
            "query_types": ["①표기만"] * len(diffs)}


def retrieve_evidence(state: dict) -> dict:
    """④ 임시: DB가 없으므로 쿼리마다 점수 0.0 의 빈 문서를 돌려준다.
    진짜 노드와 같이 대표 근거(evidence_docs)와 근거 전체 목록(evidence_lists, 수정 1건당 최대 3개)을 둘 다 낸다."""
    doc = {"doc_id": "NONE", "content": "(벡터 DB 미연결)", "score": 0.0, "part": "", "article": "", "page": 0, "source": "임시"}
    n = len(state["rewritten_queries"])
    return {"evidence_docs": [dict(doc) for _ in range(n)], "evidence_lists": [[dict(doc)] for _ in range(n)]}


def explain(state: dict) -> dict:
    """⑤ 임시: 문장 틀로 해요체 설명을 만든다 (수정 1건당 1개)."""
    out = []
    for d in state["difference"]:
        b, a = d["before"], d["after"]
        out.append(f"‘{b}’ 대신 ‘{a}’{fit_josa(a, '을')} 써요." if b and a else (f"‘{a}’ 부분을 더했어요." if a else f"‘{b}’ 부분을 뺐어요."))
    return {"explanations": out}


# ── 동화 표현 추천 (임시) ─────────────────────────────────────────────────────
# 진짜 추천 모델이 붙기 전까지 화면 흐름(선택지 → 고르기 → 저장)을 시험하려고 둔 낱말표다. 문장 속 낱말이 표에 있으면 바꿔 쓴 문장을 만든다.
DEMO_SYNONYMS = {
    "맛있었다": ["달콤했다", "새콤달콤했다"], "갔다": ["달려갔다", "걸어갔다"], "왔다": ["찾아왔다", "돌아왔다"],
    "말했다": ["외쳤다", "속삭였다"], "먹었다": ["냠냠 먹었다", "맛있게 먹었다"], "보았다": ["바라보았다", "살펴보았다"],
    "봤다": ["바라봤다", "살펴봤다"], "주웠다": ["발견했다", "집어 들었다"], "찾았다": ["발견했다", "찾아냈다"],
    "놀았다": ["뛰어놀았다", "신나게 놀았다"], "웃었다": ["방긋 웃었다", "깔깔 웃었다"], "울었다": ["엉엉 울었다", "훌쩍였다"],
    "달렸다": ["쌩쌩 달렸다", "힘차게 달렸다"], "기뻤다": ["신이 났다", "행복했다"], "슬펐다": ["속상했다", "눈물이 났다"],
    "무서웠다": ["오싹했다", "겁이 났다"], "좋았다": ["즐거웠다", "행복했다"], "재미있었다": ["신났다", "즐거웠다"],
    "살았다": ["살고 있었다", "지냈다"], "만났다": ["마주쳤다", "우연히 만났다"], "날았다": ["훨훨 날았다", "날아올랐다"],
    "예쁜": ["아름다운", "고운"], "큰": ["커다란", "엄청 큰"], "작은": ["조그만", "자그마한"], "빨리": ["재빨리", "쏜살같이"],
    "많이": ["잔뜩", "한가득"],
}


def suggest_expressions(sentence: str, limit: int = 2) -> list:
    """임시: 문장에서 낱말표에 있는 첫 낱말을 비슷한 말로 바꾼 문장들을 돌려준다 (없으면 빈 목록).
    진짜 모델로 바꿀 때도 '문장 → 바꿔 쓴 문장 목록'이라는 모양만 지키면 화면은 그대로 쓸 수 있다."""
    words = str(sentence or "").split(" ")
    for i, w in enumerate(words):
        core = w.rstrip(".!?,~")
        if core in DEMO_SYNONYMS:
            return [" ".join(words[:i] + [alt + w[len(core):]] + words[i + 1:]) for alt in DEMO_SYNONYMS[core][:limit]]
    return []


DEMO_NODES = {"spell_correct": spell_correct, "rewrite_queries": rewrite_queries,
              "retrieve_evidence": retrieve_evidence, "explain": explain}
