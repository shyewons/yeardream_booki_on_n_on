# -*- coding: utf-8 -*-
"""① 맞춤법 교정 노드 (et5).   읽는 키: original_sentence  →  쓰는 키: revised_sentence
교정 모델을 바꿀 때: 같은 방식(seq2seq)이면 config.SPELL_MODEL_ID 만, 방식이 다르면 이 파일의 _load()/_correct() 만 바꾼다."""
from .. import config
from ..models.device import get_torch, get_device

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
