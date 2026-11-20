# -*- coding: utf-8 -*-
"""여러 노드가 함께 쓰는 모델 불러오기 (GPU/CPU 선택, 임베딩, 대화형 LLM). 모델은 이름별로 한 번만 불러온다.
LLM을 API형 등 다른 방식으로 바꾸면 chat() 만, 임베딩 방식을 바꾸면 embed() 만 고친다."""
import os

_cache = {}


def get_torch():
    if "torch" not in _cache:
        import torch
        _cache["torch"] = torch
        # 장치: cuda(엔비디아) → mps(맥 GPU) → cpu 순서로 고른다.
        # .env 의 MODEL_DEVICE=cpu 로 강제할 수 있다 (mps 에서 문제가 나면 바로 되돌리는 용도)
        forced = os.environ.get("MODEL_DEVICE")
        if forced:
            _cache["device"] = forced
        elif torch.cuda.is_available():
            _cache["device"] = "cuda"
        elif torch.backends.mps.is_available():
            _cache["device"] = "mps"
        else:
            _cache["device"] = "cpu"
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
        elif get_device() == "mps":
            dtype = torch.float16                      # 맥 GPU: float16 이 빠르고 메모리도 float32 의 절반 (3B 기준 약 12GB → 6GB)
        else:
            dtype = torch.float32                      # CPU 는 float16 계산이 매우 느리거나 오류가 난다
        tok = AutoTokenizer.from_pretrained(model_id)
        # mps 는 device_map="auto" 가 모델 일부를 CPU 에 남길 때가 있어서 직접 올린다
        if get_device() == "mps":
            model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype).to("mps").eval()
        else:
            model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, device_map="auto").eval()
        _cache[key] = (tok, model)
    return _cache[key]


def chat(model_id: str, messages: list[dict], max_new_tokens: int, **gen_kwargs) -> str:
    """대화 메시지를 넘기고 모델이 새로 만든 글자만 돌려준다 (기본 greedy, gen_kwargs 로 do_sample=True 등을 넘길 수 있음)."""
    tok, model = load_llm(model_id)
    gen_kwargs = {"do_sample": False, **gen_kwargs}
    with get_torch().no_grad():
        inputs = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                         return_dict=True, return_tensors="pt").to(model.device)
        out = model.generate(**inputs, max_new_tokens=max_new_tokens,
                             pad_token_id=tok.eos_token_id, **gen_kwargs)
    return tok.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
