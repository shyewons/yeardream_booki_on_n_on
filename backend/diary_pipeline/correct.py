# -*- coding: utf-8 -*-
"""① 맞춤법 교정(et5) → ② 바뀐 곳 추출(difflib) → (바뀐 곳이 없으면) 칭찬.
  spell_correct     읽는 키: original_sentence                   → 쓰는 키: revised_sentence
  extract_diff      읽는 키: original_sentence, revised_sentence → 쓰는 키: difference
  route_after_diff  ② 뒤 분기 (차이 없음 → compliment / 있음 → rewrite_queries)
  compliment        → 쓰는 키: compliment
교정 모델을 바꿀 때: 같은 방식(seq2seq)이면 config.SPELL_MODEL_ID 만, 방식이 다르면 _load()/_correct() 만 바꾼다."""
import difflib
import re

from . import config
from .models import get_torch, get_device

_model = {}


def _load():
    """et5 (tokenizer, model) 을 한 번만 불러온다."""
    if "et5" not in _model:
        get_torch()
        from transformers import T5ForConditionalGeneration, T5Tokenizer
        tok = T5Tokenizer.from_pretrained(config.SPELL_MODEL_ID)
        model = T5ForConditionalGeneration.from_pretrained(config.SPELL_MODEL_ID).to(get_device()).eval()
        _model["et5"] = (tok, model)
    return _model["et5"]


def _correct(text: str) -> str:
    tok, model = _load()
    with get_torch().no_grad():
        enc = tok(config.SPELL_PROMPT_PREFIX + text, return_tensors="pt").to(get_device())
        out = model.generate(**enc, max_length=128, num_beams=5, early_stopping=True)
    return tok.decode(out[0], skip_special_tokens=True).strip()


def spell_correct(state: dict) -> dict:
    """original_sentence 를 교정해 revised_sentence 로 반환.
    모델 오류가 나면 원문을 그대로 넣어 다음 단계에서 '수정 없음'으로 처리되게 한다."""
    src = state["original_sentence"]
    try:
        revised = _correct(src)
    except Exception as e:
        print("[spell_correct] 교정 실패 → 원문 유지:", e)
        revised = src
    return {"revised_sentence": revised}


def preload():
    _load()


# ---- ② diff 추출 ----
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


def compliment(state: dict) -> dict:
    return {"compliment": config.COMPLIMENT}
