# -*- coding: utf-8 -*-
"""여러 노드가 함께 쓰는 모델 불러오기 (GPU/CPU 선택, 임베딩, 대화형 LLM). 모델은 이름별로 한 번만 불러온다.
LLM을 API형 등 다른 방식으로 바꾸면 chat() 만, 임베딩 방식을 바꾸면 embed() 만 고친다."""
_cache = {}


def get_torch():
    if "torch" not in _cache:
        import torch
        _cache["torch"] = torch
        _cache["device"] = "cuda" if torch.cuda.is_available() else "cpu"
    return _cache["torch"]


def get_device() -> str:
    get_torch()
    return _cache["device"]


# ---- 임베딩 (④ 근거 검색, 벡터 DB 만들기) ----
def load_embedder(model_id: str):
    key = ("emb", model_id)
    if key not in _cache:
        torch = get_torch()
        from sentence_transformers import SentenceTransformer
        kwargs = {"dtype": torch.float16} if get_device() == "cuda" else {}
        _cache[key] = SentenceTransformer(model_id, device=get_device(), model_kwargs=kwargs)
    return _cache[key]


def embed(model_id: str, texts: list[str], show_progress: bool = False):
    """정규화한 dense 임베딩 (코사인 유사도로 비교)."""
    return load_embedder(model_id).encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=show_progress)


# ---- 대화형 LLM (⑤ 설명문) ----
def load_llm(model_id: str):
    key = ("llm", model_id)
    if key not in _cache:
        torch = get_torch()
        from transformers import AutoTokenizer, AutoModelForCausalLM
        if get_device() == "cuda":
            dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            dtype = torch.float32                      # CPU 는 float16 계산이 매우 느리거나 오류가 난다
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, device_map="auto").eval()
        _cache[key] = (tok, model)
    return _cache[key]


def chat(model_id: str, messages: list[dict], max_new_tokens: int, **gen_kwargs) -> str:
    """대화 메시지를 넘기고 모델이 새로 만든 글자만 돌려준다 (greedy)."""
    tok, model = load_llm(model_id)
    with get_torch().no_grad():
        inputs = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                         return_dict=True, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                             pad_token_id=tok.eos_token_id, **gen_kwargs)
    return tok.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
