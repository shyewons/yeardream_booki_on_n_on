# -*- coding: utf-8 -*-
"""노드 연결(엣지·분기)과 실행 함수.

  START → validate ─┬─ retry / skipped ─────────────────────────────────────────────┐
                    └─ correction → spell_correct → extract_diff ─┬─ compliment ─────┤
                                                                  └─ rewrite_queries  │
                                             → retrieve_evidence → explain ───────────┤
                                                                     build_response ◀─┘ → END

노드를 다른 구현으로 갈아끼울 때는 NODES 에서 함수만 바꾸거나 build_graph({"이름": 새 함수}) 로 넘긴다."""
from .state import PipelineState
from .input_validation import validate_node, route_after_validation
from . import correct, query, retrieve, explain, response

NODES = {
    "validate": validate_node,                       # input_validation.py (팀원 코드, 수정 없음)
    "spell_correct": correct.spell_correct,          # ① et5 교정
    "extract_diff": correct.extract_diff,            # ② 바뀐 곳
    "compliment": correct.compliment,                # 고칠 곳 없음 → 칭찬
    "rewrite_queries": query.rewrite_queries,        # ③ Kiwi 판정 + 질의 보강
    "retrieve_evidence": retrieve.retrieve_evidence, # ④ KURE 벡터 검색 + 근거 결정기
    "explain": explain.explain,                      # ⑤ Kanana 설명문
    "build_response": response.build_response,       # JSON 묶기
}


def build_graph(nodes: dict = None):
    from langgraph.graph import StateGraph, START, END
    n = {**NODES, **(nodes or {})}
    g = StateGraph(PipelineState)
    for name, fn in n.items():
        g.add_node(name, fn)
    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", route_after_validation,
                            {"correction": "spell_correct", "retry": "build_response", "skipped": "build_response"})
    g.add_edge("spell_correct", "extract_diff")
    g.add_conditional_edges("extract_diff", correct.route_after_diff, ["compliment", "rewrite_queries"])
    g.add_edge("rewrite_queries", "retrieve_evidence")
    g.add_edge("retrieve_evidence", "explain")
    g.add_edge("explain", "build_response")
    g.add_edge("compliment", "build_response")
    g.add_edge("build_response", END)
    return g.compile()


_graph = {}


def get_graph():
    if "g" not in _graph:
        _graph["g"] = build_graph()
    return _graph["g"]


def run_diary(payload: dict) -> dict:
    """화면에서 받은 값(제출 1번)으로 그래프를 실행하고, 백엔드로 넘길 결과(dict)를 반환.
    payload: user_input(str), validation_attempt(int), previous_sentences(list[str]), choice_picks(list[int])"""
    state = {
        "user_input": payload.get("user_input", "") or "",
        "validation_attempt": payload.get("validation_attempt", 0) or 0,
        "previous_sentences": list(payload.get("previous_sentences") or []),
        "choice_picks": list(payload.get("choice_picks") or []),
    }
    return get_graph().invoke(state)["response"]


def preload_models() -> None:
    """서버 시작 시 한 번 불러 두면 첫 요청이 느려지지 않는다."""
    correct.preload()
    query.preload()
    retrieve.preload()
    explain.preload()
