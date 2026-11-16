# -*- coding: utf-8 -*-
"""임베딩 모델 불러오기와 임베딩 (벡터 DB 만들기와 ④ 근거 검색이 함께 사용).
다른 임베딩 모델로 바꿀 때: config.py 의 EMBED_MODEL_ID 를 바꾸고 벡터 DB를 다시 만든다 (rag/vector_db.py)."""
from .device import get_torch, get_device

_models = {}


def load(model_id: str):
    if model_id not in _models:
        torch = get_torch()
        from sentence_transformers import SentenceTransformer
        kwargs = {"dtype": torch.float16} if get_device() == "cuda" else {}
        _models[model_id] = SentenceTransformer(model_id, device=get_device(), model_kwargs=kwargs)
    return _models[model_id]


def embed(model_id: str, texts: list[str], show_progress: bool = False):
    """정규화한 dense 임베딩 (코사인 유사도로 비교)."""
    return load(model_id).encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=show_progress)
