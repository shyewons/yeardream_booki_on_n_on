# -*- coding: utf-8 -*-
"""④ 근거 검색 노드 (임베딩 + 벡터 DB, 벡터 검색 Top1).   읽는 키: rewritten_queries  →  쓰는 키: evidence_docs
evidence_docs[i] 는 rewritten_queries[i] (= difference[i]) 의 근거 문서.
검색 방식(하이브리드, 리랭킹 등)을 바꿀 때는 이 파일만, 임베딩 모델은 config.EMBED_MODEL_ID,
벡터 DB 종류는 rag/vector_db.py 를 바꾼다."""
from .. import config
from ..models import embedding
from ..rag import vector_db


def retrieve_evidence(state: dict) -> dict:
    queries = state["rewritten_queries"]
    vectors = embedding.embed(config.EMBED_MODEL_ID, queries)
    hits = vector_db.search(vectors, k=config.TOP_K)
    return {"evidence_docs": [h[0] for h in hits]}          # 쿼리마다 가장 유사한 1개


def preload():
    embedding.load(config.EMBED_MODEL_ID)
    vector_db.get_collection()
