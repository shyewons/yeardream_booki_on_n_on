# -*- coding: utf-8 -*-
"""그래프 연결만 담당 (노드 코드는 nodes/, 유효성 검사는 input_validation.py).

  START → validate ─┬─ retry / skipped ─────────────────────────────────────────────────────┐
                    └─ correction → spell_correct → extract_diff ─┬─ (차이 없음) compliment ──┤
                                                                  └─ (차이 있음) rewrite_queries │
                                                                       → retrieve_evidence → explain ┤
                                                                           build_response (JSON) ◀───┘ → END

노드를 다른 구현으로 갈아끼울 때는 NODES 에서 함수만 바꾸면 된다 (읽고 쓰는 State 키는 nodes/__init__.py 표 참고)."""
from .state import PipelineState
from .input_validation import validate_node, route_after_validation
from .nodes import spell_correct, extract_diff, compliment, rewrite_queries, retrieve_evidence, explain, build_response

NODES = {
    "validate": validate_node,                                   # input_validation.py (그대로)
    "spell_correct": spell_correct.spell_correct,
    "extract_diff": extract_diff.extract_diff,
    "compliment": compliment.compliment,
    "rewrite_queries": rewrite_queries.rewrite_queries,
    "retrieve_evidence": retrieve_evidence.retrieve_evidence,
    "explain": explain.explain,
    "build_response": build_response.build_response,
}


def build_graph(nodes: dict = None):
    """nodes 로 일부 노드만 바꿔 끼워 그래프를 만들 수도 있다. 예: build_graph({"spell_correct": my_new_fn})"""
    from langgraph.graph import StateGraph, START, END
    n = {**NODES, **(nodes or {})}

    g = StateGraph(PipelineState)
    for name, fn in n.items():
        g.add_node(name, fn)

    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", route_after_validation,
                            {"correction": "spell_correct", "retry": "build_response", "skipped": "build_response"})
    g.add_edge("spell_correct", "extract_diff")
    g.add_conditional_edges("extract_diff", extract_diff.route_after_diff, ["compliment", "rewrite_queries"])
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
    spell_correct.preload()
    rewrite_queries.preload()
    retrieve_evidence.preload()
    explain.preload()
