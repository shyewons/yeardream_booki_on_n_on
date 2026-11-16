# -*- coding: utf-8 -*-
"""일기 모드 파이프라인: 유효성 검사 → 맞춤법 교정 → 근거 검색 → 초등학생용 설명문 → JSON.

    from diary_pipeline import run_diary, to_json, preload_models
    result = run_diary({"user_input": "...", "validation_attempt": 0, "previous_sentences": [], "choice_picks": []})
    print(to_json(result))
"""
__all__ = ["run_diary", "to_json", "build_graph", "get_graph", "preload_models"]


def __getattr__(name):
    # 필요할 때만 불러온다 (벡터 DB 만들기처럼 그래프가 필요 없는 실행에서 불필요한 import 를 막음)
    if name in ("run_diary", "build_graph", "get_graph", "preload_models"):
        from . import graph
        return getattr(graph, name)
    if name == "to_json":
        from .response import to_json
        return to_json
    raise AttributeError(name)
