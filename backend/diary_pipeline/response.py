# -*- coding: utf-8 -*-
"""결과 묶기 노드 (모든 경로 공통).   읽는 키: 유효성 검사 키 + 교정 단계 키  →  쓰는 키: response
백엔드(대시보드)로 넘길 JSON 형식을 바꿀 때는 이 파일만 고친다."""
import json
from datetime import datetime, timezone, timedelta

from . import config
from .input_validation import route_after_validation

KST = timezone(timedelta(hours=9))
VALIDATION_KEYS = ["is_valid", "original_sentence", "retry_message", "highlights", "display_text", "awaiting_choice",
                   "line_skipped", "validation_attempt", "previous_sentences", "choice_picks", "validation_log"]


def build_response(state: dict) -> dict:
    """유효성 검사 결과 + (통과했을 때) 교정 결과를 하나의 dict(JSON 형식)로 묶음.
    route 가 retry / skipped 면 correction 은 None(null). 고칠 곳이 없을 때(칭찬)도 같은 형식."""
    route = route_after_validation(state)                # correction / retry / skipped
    response = {"route": route}
    for k in VALIDATION_KEYS:                            # 화면이 그대로 쓰는 유효성 검사 결과 (input_validation.py 출력)
        response[k] = state.get(k)

    correction = None
    if route == "correction":
        diffs = state.get("difference", [])
        queries = state.get("rewritten_queries", [])
        docs = state.get("evidence_docs", [])
        exps = state.get("explanations", [])
        types = state.get("query_types", [])
        ev_lists = state.get("evidence_lists", [])
        corrections = []
        for i, d in enumerate(diffs):
            doc = docs[i] if i < len(docs) else None
            corrections.append({
                "index": i,
                "before": d["before"],                       # 아이가 쓴 표현
                "after": d["after"],                         # 고친 표현
                "start": d["start"], "end": d["end"],        # 원문 속 위치 (화면에서 밑줄 칠 때 사용)
                "explanation": exps[i] if i < len(exps) else None,
                "query": queries[i] if i < len(queries) else None,
                "type": types[i] if i < len(types) else None,   # ①표기만 / ②띄어쓰기+구체 / ③띄어쓰기+표기 / ④일반 띄어쓰기
                "evidence": None if doc is None else {       # 근거 문서 정보 (본문은 길어서 제외) — 대표 1개, 설명문의 근거
                    "doc_id": doc["doc_id"], "part": doc.get("part"), "article": doc["article"],
                    "page": doc["page"], "score": doc["score"],
                },
                "evidences": [                               # 최종 근거 조항 전체 (최대 3개, source: 검색/규칙)
                    {"doc_id": e["doc_id"], "part": e.get("part"), "article": e["article"], "page": e["page"], "score": e["score"],
                     "source": e.get("source")}
                    for e in (ev_lists[i] if i < len(ev_lists) else [])
                ],
            })
        correction = {
            "original_sentence": state["original_sentence"],
            "revised_sentence": state.get("revised_sentence", state["original_sentence"]),
            "has_correction": bool(diffs),
            "corrections": corrections,
            "compliment": state.get("compliment"),           # 고칠 곳이 없을 때만 값이 있음 (일기 모드)
        }
    response["correction"] = correction

    story = None                                         # 동화 모드에서 고칠 곳이 없을 때만 값이 있음
    if route == "correction" and state.get("expressions"):
        src = state["original_sentence"]
        story = {
            "guide": config.STORY_GUIDE,
            "options": [{"index": 1, "text": src, "point": config.STORY_ORIGINAL_POINT, "source": "원문"}]
                       + [{"index": k + 2, "text": e["text"], "point": e["point"], "source": e["source"]}
                          for k, e in enumerate(state["expressions"][:2])],
        }
    response["story"] = story
    response["created_at"] = datetime.now(KST).isoformat(timespec="seconds")
    return {"response": response}


def to_json(response: dict) -> str:
    """백엔드로 보낼 JSON 문자열 (한글이 깨지지 않게 ensure_ascii=False)."""
    return json.dumps(response, ensure_ascii=False, indent=2)
