# -*- coding: utf-8 -*-
"""② diff 추출 노드 (difflib, 규칙 기반).   읽는 키: original_sentence, revised_sentence  →  쓰는 키: difference
글자 단위로 비교한 뒤 바뀐 곳을 어절(띄어쓰기 단위)로 넓혀 담는다. 틀린 곳이 2개면 원소도 2개.
route_after_diff: 이 노드 뒤의 분기 (차이 없음 → 칭찬 / 있음 → 쿼리 재작성)."""
import difflib
import re

from .. import config

_PUNCT = re.compile(r"[^\w\s]")


def extract_diff(state: dict) -> dict:
    original, revised = state["original_sentence"], state["revised_sentence"]

    def expand(s, i, j):          # 바뀐 범위를 앞뒤 공백까지 넓혀 어절 단위로
        while i > 0 and not s[i - 1].isspace():
            i -= 1
        while j < len(s) and not s[j].isspace():
            j += 1
        return i, j

    def trim(s, i, j):            # 앞뒤 공백(과 문장부호)을 뗌. 예: '됐어요.' → '됐어요'
        strip = (lambda c: c.isspace() or bool(_PUNCT.match(c))) if config.IGNORE_PUNCT_ONLY else str.isspace
        while i < j and strip(s[i]):
            i += 1
        while j > i and strip(s[j - 1]):
            j -= 1
        return i, j

    # 1) 글자 단위 비교 → 바뀐 범위를 어절 단위로 넓힘. 같은 어절에 걸친 수정은 하나로 합침
    spans = []                    # [원문 시작, 원문 끝, 교정 시작, 교정 끝]
    sm = difflib.SequenceMatcher(None, original, revised, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        a1, a2 = expand(original, i1, i2)
        b1, b2 = expand(revised, j1, j2)
        if spans and (a1 < spans[-1][1] or b1 < spans[-1][3]):
            p = spans[-1]
            spans[-1] = [min(p[0], a1), max(p[1], a2), min(p[2], b1), max(p[3], b2)]
        else:
            spans.append([a1, a2, b1, b2])

    # 2) 범위를 실제 표현으로 바꿔 담음. 문장부호만 바뀐 경우는 뺌
    difference = []
    for a1, a2, b1, b2 in spans:
        a1, a2 = trim(original, a1, a2)
        b1, b2 = trim(revised, b1, b2)
        before, after = original[a1:a2], revised[b1:b2]
        if before == after:
            continue
        if config.IGNORE_PUNCT_ONLY and _PUNCT.sub("", before) == _PUNCT.sub("", after):
            continue
        difference.append({"before": before, "after": after, "start": a1, "end": a2})
    return {"difference": difference}


def route_after_diff(state: dict) -> str:
    """difference 가 비어 있으면 칭찬, 있으면 쿼리 재작성으로 보냄."""
    return "rewrite_queries" if state["difference"] else "compliment"
