# -*- coding: utf-8 -*-
"""대화형 LLM 불러오기와 생성 (③ 쿼리 재작성, ⑤ 설명문이 사용).
다른 LLM으로 바꿀 때: config.py 의 QUERY_LLM_ID / EXPLAIN_LLM_ID 만 바꾸면 된다 (Hugging Face chat 템플릿이 있는 모델).
API형 LLM 등 방식이 아예 다르면 이 파일의 chat() 만 바꾸면 되고, 노드 파일은 그대로 둔다."""
from .device import get_torch, get_device

_models = {}


def load(model_id: str):
    """model_id 별로 (tokenizer, model)을 한 번만 불러온다."""
    if model_id not in _models:
        torch = get_torch()
        from transformers import AutoTokenizer, AutoModelForCausalLM
        dtype = torch.bfloat16 if get_device() == "cuda" and torch.cuda.is_bf16_supported() else torch.float16
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, device_map="auto").eval()
        _models[model_id] = (tok, model)
    return _models[model_id]


def chat(model_id: str, messages: list[dict], max_new_tokens: int, **gen_kwargs) -> str:
    """대화 메시지를 넘기고 모델이 새로 만든 글자만 돌려준다 (greedy)."""
    tok, model = load(model_id)
    torch = get_torch()
    with torch.no_grad():
        inputs = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                         return_dict=True, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                             pad_token_id=tok.eos_token_id, **gen_kwargs)
    return tok.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
